import argparse
import csv
from datetime import datetime
import json
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage4_conditioned", "selection")
LATEST_MODEL_DIR = os.path.join(PROJECT_ROOT, "results", "stage4_conditioned", "latest_model")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from config.stage1_presets import get_capacity_conditioned_pool
from ies_shared.stage1_eval import rollout_policy
from train.stage1_runtime import build_stage1_env, resolve_device, write_json
from train.analyze_capacity_conditioned_progress import build_default_specialized_map, load_json


def parse_candidate(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ValueError(f"Invalid candidate spec: {spec}. Expected <label>=<model_path>.")
    label, model_path = spec.split("=", 1)
    label = label.strip()
    model_path = model_path.strip()
    if not label or not model_path:
        raise ValueError(f"Invalid candidate spec: {spec}.")
    return label, model_path


def normalize_model_path(model_path: str) -> str:
    return model_path[:-4] if model_path.endswith(".zip") else model_path


def evaluate_model_on_pool(
    model,
    labels: list[str],
    configs: list[dict],
    episode_horizon: int,
    safety_profile: str,
    symmetric_actions: bool,
) -> dict:
    rows = []
    full_configs = []
    for label, config in zip(labels, configs):
        _, env = build_stage1_env(
            pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
            surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
            config=config,
            episode_horizon=episode_horizon,
            random_start=False,
            safety_profile=safety_profile,
            symmetric_actions=symmetric_actions,
        )
        artifacts = rollout_policy(env=env, model=model)
        perf = artifacts.summary["performance_metrics"]
        strategy = artifacts.summary["strategy_metrics"]
        physics = artifacts.summary["physics_metrics"]
        rows.append(
            {
                "label": label,
                "annual_methanol_kg": float(perf["annual_methanol_kg"]),
                "lcom_yuan_per_kg": float(perf["lcom_yuan_per_kg"]),
                "h2_inventory_violation_count": int(physics["h2_inventory_violation_count"]),
                "co2_inventory_violation_count": int(physics["co2_inventory_violation_count"]),
                "soc_violation_count": int(physics["soc_violation_count"]),
                "avg_methanol_pull_ratio": float(strategy["avg_methanol_pull_ratio"]),
            }
        )
        full_configs.append(
            {
                "label": label,
                "config": artifacts.summary["config"],
                "performance_metrics": perf,
                "strategy_metrics": strategy,
                "physics_metrics": physics,
            }
        )
    avg_methanol = sum(row["annual_methanol_kg"] for row in rows) / max(1, len(rows))
    avg_lcom = sum(row["lcom_yuan_per_kg"] for row in rows) / max(1, len(rows))
    return {
        "pool_size": len(rows),
        "avg_annual_methanol_kg": avg_methanol,
        "avg_lcom_yuan_per_kg": avg_lcom,
        "max_h2_violation_count": max(row["h2_inventory_violation_count"] for row in rows),
        "max_co2_violation_count": max(row["co2_inventory_violation_count"] for row in rows),
        "max_soc_violation_count": max(row["soc_violation_count"] for row in rows),
        "configs": full_configs,
        "rows": rows,
    }


def compare_with_specialized(in_pool_summary: dict) -> list[dict]:
    specialized_map = build_default_specialized_map()
    by_label = {item["label"]: item for item in in_pool_summary["configs"]}
    matched_rows = []
    for label, specialized_path in specialized_map.items():
        if label not in by_label or not os.path.exists(specialized_path):
            continue
        conditioned_item = by_label[label]
        specialized_item = load_json(specialized_path)
        cond_perf = conditioned_item["performance_metrics"]
        cond_phys = conditioned_item["physics_metrics"]
        spec_perf = specialized_item["performance_metrics"]
        spec_phys = specialized_item["physics_metrics"]
        matched_rows.append(
            {
                "label": label,
                "conditioned_methanol_kg": float(cond_perf["annual_methanol_kg"]),
                "specialized_methanol_kg": float(spec_perf["annual_methanol_kg"]),
                "methanol_gap_kg": float(cond_perf["annual_methanol_kg"] - spec_perf["annual_methanol_kg"]),
                "conditioned_lcom": float(cond_perf["lcom_yuan_per_kg"]),
                "specialized_lcom": float(spec_perf["lcom_yuan_per_kg"]),
                "lcom_gap": float(cond_perf["lcom_yuan_per_kg"] - spec_perf["lcom_yuan_per_kg"]),
                "conditioned_h2_violation": int(cond_phys["h2_inventory_violation_count"]),
                "specialized_h2_violation": int(spec_phys["h2_inventory_violation_count"]),
            }
        )
    return matched_rows


def mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def build_score(summary_row: dict) -> float:
    violation_penalty = 0.0
    if summary_row["max_h2_violation_count"] > 0:
        violation_penalty += 10000.0
    if summary_row["max_co2_violation_count"] > 0:
        violation_penalty += 5000.0
    if summary_row["max_soc_violation_count"] > 0:
        violation_penalty += 5000.0

    score = 0.0
    score -= violation_penalty
    score += summary_row["holdout_avg_methanol_kg"] * 0.10
    score += summary_row["in_pool_avg_methanol_kg"] * 0.05
    score -= summary_row["holdout_avg_lcom"] * 0.50
    score -= summary_row["in_pool_avg_lcom"] * 0.25
    score -= abs(summary_row["generalization_gap_methanol_kg"]) * 0.05
    score -= abs(summary_row["generalization_gap_lcom"]) * 10.0
    score -= abs(summary_row["mean_specialized_methanol_gap_kg"]) * 0.08
    score -= max(0.0, summary_row["mean_specialized_lcom_gap"]) * 5.0
    return score


def write_csv(path: str, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Select the best capacity-conditioned model by comparing pool, holdout, and specialized-policy gaps.")
    parser.add_argument("--candidate", action="append", required=True, help="Format: <label>=<model_path>")
    parser.add_argument("--run-tag", type=str, default="round1")
    parser.add_argument("--in-pool-path", type=str, default=os.path.join(PROJECT_ROOT, "config", "stage4_conditioned_pool.json"))
    parser.add_argument("--holdout-path", type=str, default=os.path.join(PROJECT_ROOT, "config", "stage4_holdout_pool.json"))
    parser.add_argument("--episode-horizon", type=int, default=168)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--safety-profile", type=str, default="h2_guard_v1")
    parser.add_argument("--symmetric-actions", action="store_true", default=True)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    args = parser.parse_args()

    in_pool_labels, in_pool_configs, _ = get_capacity_conditioned_pool(args.in_pool_path)
    holdout_labels, holdout_configs, _ = get_capacity_conditioned_pool(args.holdout_path)
    device = resolve_device(args.device)

    run_id = f"stage4_model_selection_{args.run_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, run_id)
    os.makedirs(output_dir, exist_ok=True)

    leaderboard_rows = []
    candidate_outputs = []

    for spec in args.candidate:
        label, model_path = parse_candidate(spec)
        normalized_model_path = normalize_model_path(model_path)
        model = SAC.load(normalized_model_path, device=device)
        in_pool_summary = evaluate_model_on_pool(
            model=model,
            labels=in_pool_labels,
            configs=in_pool_configs,
            episode_horizon=args.episode_horizon,
            safety_profile=args.safety_profile,
            symmetric_actions=args.symmetric_actions,
        )
        holdout_summary = evaluate_model_on_pool(
            model=model,
            labels=holdout_labels,
            configs=holdout_configs,
            episode_horizon=args.episode_horizon,
            safety_profile=args.safety_profile,
            symmetric_actions=args.symmetric_actions,
        )
        matched_rows = compare_with_specialized(in_pool_summary)
        mean_specialized_methanol_gap = mean([row["methanol_gap_kg"] for row in matched_rows]) if matched_rows else 0.0
        mean_specialized_lcom_gap = mean([row["lcom_gap"] for row in matched_rows]) if matched_rows else 0.0
        summary_row = {
            "candidate_label": label,
            "model_path": normalized_model_path + ".zip",
            "in_pool_avg_methanol_kg": in_pool_summary["avg_annual_methanol_kg"],
            "holdout_avg_methanol_kg": holdout_summary["avg_annual_methanol_kg"],
            "in_pool_avg_lcom": in_pool_summary["avg_lcom_yuan_per_kg"],
            "holdout_avg_lcom": holdout_summary["avg_lcom_yuan_per_kg"],
            "generalization_gap_methanol_kg": holdout_summary["avg_annual_methanol_kg"] - in_pool_summary["avg_annual_methanol_kg"],
            "generalization_gap_lcom": holdout_summary["avg_lcom_yuan_per_kg"] - in_pool_summary["avg_lcom_yuan_per_kg"],
            "max_h2_violation_count": max(in_pool_summary["max_h2_violation_count"], holdout_summary["max_h2_violation_count"]),
            "max_co2_violation_count": max(in_pool_summary["max_co2_violation_count"], holdout_summary["max_co2_violation_count"]),
            "max_soc_violation_count": max(in_pool_summary["max_soc_violation_count"], holdout_summary["max_soc_violation_count"]),
            "mean_specialized_methanol_gap_kg": mean_specialized_methanol_gap,
            "mean_specialized_lcom_gap": mean_specialized_lcom_gap,
        }
        summary_row["selection_score"] = build_score(summary_row)
        leaderboard_rows.append(summary_row)
        candidate_outputs.append(
            {
                "candidate_label": label,
                "model_path": summary_row["model_path"],
                "in_pool_summary": in_pool_summary,
                "holdout_summary": holdout_summary,
                "matched_specialized_rows": matched_rows,
                "selection_score": summary_row["selection_score"],
            }
        )

    leaderboard_rows.sort(key=lambda item: item["selection_score"], reverse=True)
    for rank, row in enumerate(leaderboard_rows, start=1):
        row["rank"] = rank

    best_label = leaderboard_rows[0]["candidate_label"] if leaderboard_rows else None
    summary = {
        "run_id": run_id,
        "run_tag": args.run_tag,
        "device": device,
        "episode_horizon": args.episode_horizon,
        "safety_profile": args.safety_profile,
        "symmetric_actions": args.symmetric_actions,
        "best_candidate_label": best_label,
        "leaderboard": leaderboard_rows,
        "candidates": candidate_outputs,
    }

    write_csv(os.path.join(output_dir, "selection_leaderboard.csv"), leaderboard_rows)
    write_json(os.path.join(output_dir, "selection_summary.json"), summary)

    if leaderboard_rows:
        best_row = leaderboard_rows[0]
        latest_selected = {
            "selected_at": datetime.now().isoformat(timespec="seconds"),
            "selection_run_id": run_id,
            "selection_summary_path": os.path.join(output_dir, "selection_summary.json"),
            "best_candidate_label": best_row["candidate_label"],
            "best_model_path": best_row["model_path"],
            "episode_horizon": args.episode_horizon,
            "selection_score": best_row["selection_score"],
            "holdout_avg_methanol_kg": best_row["holdout_avg_methanol_kg"],
            "holdout_avg_lcom": best_row["holdout_avg_lcom"],
            "mean_specialized_methanol_gap_kg": best_row["mean_specialized_methanol_gap_kg"],
            "mean_specialized_lcom_gap": best_row["mean_specialized_lcom_gap"],
            "max_h2_violation_count": best_row["max_h2_violation_count"],
            "max_co2_violation_count": best_row["max_co2_violation_count"],
            "max_soc_violation_count": best_row["max_soc_violation_count"],
        }
        os.makedirs(LATEST_MODEL_DIR, exist_ok=True)
        write_json(os.path.join(LATEST_MODEL_DIR, "selected_capacity_conditioned_model.json"), latest_selected)

    md_lines = [
        "# 统一容量条件策略模型选择",
        "",
        "## 选择结论",
        "",
        f"- 最优候选: `{best_label}`" if best_label else "- 最优候选: 无",
        f"- 候选数量: `{len(leaderboard_rows)}`",
        f"- 评估步长: `{args.episode_horizon}` 小时",
        f"- 设备: `{device}`",
        "",
        "## 排行榜",
        "",
    ]
    for row in leaderboard_rows:
        md_lines.extend(
            [
                f"### 第 {row['rank']} 名: {row['candidate_label']}",
                "",
                f"- 选择分数: {row['selection_score']:.4f}",
                f"- 训练池平均甲醇: {row['in_pool_avg_methanol_kg']:.2f} kg",
                f"- 留出池平均甲醇: {row['holdout_avg_methanol_kg']:.2f} kg",
                f"- 训练池平均 LCOM: {row['in_pool_avg_lcom']:.4f}",
                f"- 留出池平均 LCOM: {row['holdout_avg_lcom']:.4f}",
                f"- 泛化差值(甲醇): {row['generalization_gap_methanol_kg']:.2f} kg",
                f"- 泛化差值(LCOM): {row['generalization_gap_lcom']:.4f}",
                f"- 平均专用策略甲醇差值: {row['mean_specialized_methanol_gap_kg']:.2f} kg",
                f"- 平均专用策略 LCOM 差值: {row['mean_specialized_lcom_gap']:.4f}",
                f"- 最大 H2/CO2/SOC 越界: {row['max_h2_violation_count']}/{row['max_co2_violation_count']}/{row['max_soc_violation_count']}",
                "",
            ]
        )

    with open(os.path.join(output_dir, "selection_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"output_dir={output_dir}")
    print(f"best_candidate_label={best_label}")
    print(f"candidate_count={len(leaderboard_rows)}")


if __name__ == "__main__":
    main()

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
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage4_conditioned")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from config.stage1_presets import get_capacity_conditioned_pool
from ies_shared.stage1_eval import rollout_policy, save_rollout_artifacts
from train.stage1_runtime import build_stage1_env, resolve_device, write_json


def _latest_model_info() -> dict:
    latest_meta = os.path.join(RESULTS_DIR, "latest_model", "latest_capacity_conditioned_model.json")
    if not os.path.exists(latest_meta):
        raise FileNotFoundError("No latest capacity-conditioned model metadata found.")
    with open(latest_meta, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_csv(path: str, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def main():
    parser = argparse.ArgumentParser(description="Evaluate a capacity-conditioned policy on a pool of standardized stage-1 configs.")
    parser.add_argument("--pool-path", type=str, required=True)
    parser.add_argument("--run-tag", type=str, default=None)
    parser.add_argument("--model-path", type=str, default=None)
    parser.add_argument("--episode-horizon", type=int, default=8760)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--safety-profile", type=str, default="h2_guard_v1")
    parser.add_argument("--symmetric-actions", action="store_true", default=None)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    args = parser.parse_args()

    labels, configs, _ = get_capacity_conditioned_pool(args.pool_path)
    latest_info = _latest_model_info()
    latest_model_path = latest_info["saved_model"]
    latest_model_path = latest_model_path[:-4] if latest_model_path.endswith(".zip") else latest_model_path
    model_path = args.model_path or latest_model_path
    symmetric_actions = (
        bool(latest_info.get("symmetric_actions", True))
        if args.symmetric_actions is None
        else bool(args.symmetric_actions)
    )
    device = resolve_device(args.device)
    model = SAC.load(model_path, device=device)

    pool_label = args.run_tag or os.path.splitext(os.path.basename(args.pool_path))[0]
    run_id = f"stage4_eval_{pool_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, "evaluations", run_id)
    os.makedirs(output_dir, exist_ok=True)

    aggregate_rows: list[dict] = []
    per_config_outputs: list[dict] = []

    for label, config in zip(labels, configs):
        _, env = build_stage1_env(
            pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
            surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
            config=config,
            episode_horizon=args.episode_horizon,
            random_start=False,
            safety_profile=args.safety_profile,
            symmetric_actions=symmetric_actions,
        )
        artifacts = rollout_policy(env=env, model=model)
        config_dir = os.path.join(output_dir, label)
        saved = save_rollout_artifacts(artifacts=artifacts, output_dir=config_dir, prefix="annual_eval")
        perf = artifacts.summary["performance_metrics"]
        strategy = artifacts.summary["strategy_metrics"]
        physics = artifacts.summary["physics_metrics"]
        row = {
            "label": label,
            "annual_methanol_kg": perf["annual_methanol_kg"],
            "lcom_yuan_per_kg": perf["lcom_yuan_per_kg"],
            "annual_total_cost_yuan": perf["annual_total_cost_yuan"],
            "annual_grid_purchase_kwh": perf["annual_grid_purchase_kwh"],
            "annual_curtailment_kwh": perf["annual_curtailment_kwh"],
            "avg_h2_target_ratio": strategy["avg_h2_inventory_target_ratio"],
            "avg_h2_target_ratio_effective": strategy["avg_h2_inventory_target_ratio_effective"],
            "avg_methanol_pull_ratio": strategy["avg_methanol_pull_ratio"],
            "avg_battery_reserve_preference": strategy["avg_battery_reserve_preference"],
            "h2_inventory_violation_count": physics["h2_inventory_violation_count"],
            "co2_inventory_violation_count": physics["co2_inventory_violation_count"],
            "soc_violation_count": physics["soc_violation_count"],
            "energy_balance_error_kw_max_abs": physics["energy_balance_error_kw_max_abs"],
            "config_r_pem": artifacts.summary["config"]["r_pem"],
            "config_r_bat_e": artifacts.summary["config"]["r_bat_e"],
            "config_r_h2": artifacts.summary["config"]["r_h2"],
            "config_r_co2": artifacts.summary["config"]["r_co2"],
        }
        aggregate_rows.append(row)
        per_config_outputs.append(
            {
                "label": label,
                "config": artifacts.summary["config"],
                "physical_params": artifacts.summary["physical_params"],
                "performance_metrics": perf,
                "strategy_metrics": strategy,
                "physics_metrics": physics,
                "reward_breakdown": artifacts.summary["reward_breakdown"],
                "saved_files": saved,
            }
        )

    summary = {
        "run_id": run_id,
        "pool_path": args.pool_path,
        "pool_label": pool_label,
        "model_path": model_path + ".zip",
        "device": device,
        "episode_horizon": args.episode_horizon,
        "safety_profile": args.safety_profile,
        "symmetric_actions": symmetric_actions,
        "pool_size": len(aggregate_rows),
        "avg_annual_methanol_kg": _mean([float(row["annual_methanol_kg"]) for row in aggregate_rows]),
        "avg_lcom_yuan_per_kg": _mean([float(row["lcom_yuan_per_kg"]) for row in aggregate_rows]),
        "max_h2_violation_count": max(int(row["h2_inventory_violation_count"]) for row in aggregate_rows),
        "max_co2_violation_count": max(int(row["co2_inventory_violation_count"]) for row in aggregate_rows),
        "max_soc_violation_count": max(int(row["soc_violation_count"]) for row in aggregate_rows),
        "configs": per_config_outputs,
    }

    _write_csv(os.path.join(output_dir, "pool_summary.csv"), aggregate_rows)
    write_json(os.path.join(output_dir, "pool_summary.json"), summary)
    md_lines = [
        f"# {pool_label}",
        "",
        "## 汇总",
        "",
        f"- 配置数量: {summary['pool_size']}",
        f"- 平均年甲醇产量: {summary['avg_annual_methanol_kg']:.2f} kg",
        f"- 平均 LCOM: {summary['avg_lcom_yuan_per_kg']:.4f} yuan/kg",
        f"- 最大 H2 越界次数: {summary['max_h2_violation_count']}",
        f"- 最大 CO2 越界次数: {summary['max_co2_violation_count']}",
        f"- 最大 SOC 越界次数: {summary['max_soc_violation_count']}",
        "",
        "## 各配置结果",
        "",
    ]
    for row in aggregate_rows:
        md_lines.extend(
            [
                f"### {row['label']}",
                "",
                f"- 年甲醇产量: {float(row['annual_methanol_kg']):.2f} kg",
                f"- LCOM: {float(row['lcom_yuan_per_kg']):.4f} yuan/kg",
                f"- H2 越界次数: {int(row['h2_inventory_violation_count'])}",
                f"- 平均甲醇拉料强度: {float(row['avg_methanol_pull_ratio']):.4f}",
                "",
            ]
        )
    with open(os.path.join(output_dir, "pool_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"output_dir={output_dir}")
    print(f"pool_size={summary['pool_size']}")
    print(f"avg_annual_methanol_kg={summary['avg_annual_methanol_kg']:.6f}")
    print(f"avg_lcom_yuan_per_kg={summary['avg_lcom_yuan_per_kg']:.6f}")


if __name__ == "__main__":
    main()

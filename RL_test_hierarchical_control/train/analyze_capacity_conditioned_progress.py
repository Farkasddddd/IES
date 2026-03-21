import argparse
from datetime import datetime
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage4_conditioned", "analysis")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_default_specialized_map() -> dict[str, str]:
    return {
        "baseline": os.path.join(
            PROJECT_ROOT,
            "results",
            "stage1",
            "evaluations",
            "stage1_eval_cmp_baseline_168h_20260320_233125",
            "annual_eval_summary.json",
        ),
        "h2_55": os.path.join(
            PROJECT_ROOT,
            "results",
            "stage1",
            "evaluations",
            "stage1_eval_cmp_h2_55_168h_20260320_233125",
            "annual_eval_summary.json",
        ),
        "bat_e_35": os.path.join(
            PROJECT_ROOT,
            "results",
            "stage1",
            "evaluations",
            "stage1_eval_cmp_bat_e_35_168h_20260320_233125",
            "annual_eval_summary.json",
        ),
    }


def load_specialized_map(path: str | None) -> dict[str, str]:
    if not path:
        return build_default_specialized_map()
    payload = load_json(path)
    if "specialized_map" in payload:
        return payload["specialized_map"]
    return payload


def main():
    parser = argparse.ArgumentParser(description="Analyze capacity-conditioned progress against specialized single-config policies.")
    parser.add_argument("--conditioned-in-pool", type=str, required=True)
    parser.add_argument("--conditioned-holdout", type=str, required=True)
    parser.add_argument("--specialized-map-path", type=str, default=None)
    parser.add_argument("--run-tag", type=str, default="round1")
    args = parser.parse_args()

    in_pool = load_json(args.conditioned_in_pool)
    holdout = load_json(args.conditioned_holdout)
    specialized_map = load_specialized_map(args.specialized_map_path)

    by_label = {item["label"]: item for item in in_pool["configs"]}
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
                "conditioned_methanol_kg": cond_perf["annual_methanol_kg"],
                "specialized_methanol_kg": spec_perf["annual_methanol_kg"],
                "methanol_gap_kg": cond_perf["annual_methanol_kg"] - spec_perf["annual_methanol_kg"],
                "conditioned_lcom": cond_perf["lcom_yuan_per_kg"],
                "specialized_lcom": spec_perf["lcom_yuan_per_kg"],
                "lcom_gap": cond_perf["lcom_yuan_per_kg"] - spec_perf["lcom_yuan_per_kg"],
                "conditioned_h2_violation": cond_phys["h2_inventory_violation_count"],
                "specialized_h2_violation": spec_phys["h2_inventory_violation_count"],
            }
        )

    summary = {
        "run_tag": args.run_tag,
        "conditioned_in_pool_path": args.conditioned_in_pool,
        "conditioned_holdout_path": args.conditioned_holdout,
        "specialized_map_path": args.specialized_map_path,
        "in_pool_avg_methanol_kg": in_pool["avg_annual_methanol_kg"],
        "holdout_avg_methanol_kg": holdout["avg_annual_methanol_kg"],
        "in_pool_avg_lcom": in_pool["avg_lcom_yuan_per_kg"],
        "holdout_avg_lcom": holdout["avg_lcom_yuan_per_kg"],
        "generalization_gap_methanol_kg": holdout["avg_annual_methanol_kg"] - in_pool["avg_annual_methanol_kg"],
        "generalization_gap_lcom": holdout["avg_lcom_yuan_per_kg"] - in_pool["avg_lcom_yuan_per_kg"],
        "max_in_pool_h2_violation": in_pool["max_h2_violation_count"],
        "max_holdout_h2_violation": holdout["max_h2_violation_count"],
        "matched_specialized_rows": matched_rows,
    }

    run_id = f"conditioned_vs_specialized_{args.run_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, run_id)
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "comparison_summary.json")
    md_path = os.path.join(output_dir, "comparison_summary.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    lines = [
        "# 统一策略阶段进展对照",
        "",
        "## 训练池与留出池",
        "",
        f"- 训练池平均甲醇产量: {summary['in_pool_avg_methanol_kg']:.2f} kg",
        f"- 留出池平均甲醇产量: {summary['holdout_avg_methanol_kg']:.2f} kg",
        f"- 训练池平均 LCOM: {summary['in_pool_avg_lcom']:.4f} yuan/kg",
        f"- 留出池平均 LCOM: {summary['holdout_avg_lcom']:.4f} yuan/kg",
        f"- 泛化差值(甲醇): {summary['generalization_gap_methanol_kg']:.2f} kg",
        f"- 泛化差值(LCOM): {summary['generalization_gap_lcom']:.4f} yuan/kg",
        f"- 训练池最大 H2 越界: {summary['max_in_pool_h2_violation']}",
        f"- 留出池最大 H2 越界: {summary['max_holdout_h2_violation']}",
        "",
        "## 与单配置专用策略对照",
        "",
    ]
    for row in matched_rows:
        lines.extend(
            [
                f"### {row['label']}",
                "",
                f"- 统一策略甲醇产量: {row['conditioned_methanol_kg']:.2f} kg",
                f"- 专用策略甲醇产量: {row['specialized_methanol_kg']:.2f} kg",
                f"- 甲醇差值: {row['methanol_gap_kg']:.2f} kg",
                f"- 统一策略 LCOM: {row['conditioned_lcom']:.4f}",
                f"- 专用策略 LCOM: {row['specialized_lcom']:.4f}",
                f"- LCOM 差值: {row['lcom_gap']:.4f}",
                f"- 统一策略 H2 越界: {row['conditioned_h2_violation']}",
                f"- 专用策略 H2 越界: {row['specialized_h2_violation']}",
                "",
            ]
        )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"output_dir={output_dir}")
    print(f"json_path={json_path}")
    print(f"md_path={md_path}")


if __name__ == "__main__":
    main()

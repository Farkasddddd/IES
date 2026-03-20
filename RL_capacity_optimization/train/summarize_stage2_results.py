import csv
from datetime import datetime
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
STAGE2_RUNS_DIR = os.path.join(RESULTS_DIR, "stage2_runs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.stage2_candidates import STAGE2_CANDIDATES


def load_stage1_baseline(candidate) -> dict | None:
    source_csv = os.path.join(RESULTS_DIR, "search_runs", candidate.source_run_id, "results_table.csv")
    if not os.path.exists(source_csv):
        return None
    with open(source_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if (
            float(row["pv_kw"]) == candidate.pv_kw
            and int(float(row["n_dac"])) == candidate.n_dac
            and float(row["pem_kw"]) == candidate.pem_kw
            and float(row["battery_kwh"]) == candidate.battery_kwh
            and float(row["co2_tank_capacity_mol"]) == candidate.co2_tank_capacity_mol
            and float(row["h2_tank_capacity_mol"]) == candidate.h2_tank_capacity_mol
        ):
            return row
    return None


def find_latest_evaluated_run(candidate_id: str) -> str | None:
    if not os.path.isdir(STAGE2_RUNS_DIR):
        return None
    matches = [
        name
        for name in os.listdir(STAGE2_RUNS_DIR)
        if name.startswith(f"stage2_finetune_{candidate_id}_")
        and os.path.exists(os.path.join(STAGE2_RUNS_DIR, name, "annual_eval_summary.json"))
    ]
    if not matches:
        return None
    matches.sort()
    return os.path.join(STAGE2_RUNS_DIR, matches[-1])


def main():
    rows = []
    for candidate_id, candidate in STAGE2_CANDIDATES.items():
        run_dir = find_latest_evaluated_run(candidate_id)
        if run_dir is None:
            continue
        with open(os.path.join(run_dir, "annual_eval_summary.json"), "r", encoding="utf-8") as f:
            payload = json.load(f)
        stage1 = load_stage1_baseline(candidate)
        stage2_eval = payload["economic_evaluation"]
        stage2_summary = payload["annual_rollout_summary"]
        green_base = stage2_eval["economics"]["scenario_results"]["green_base"]

        row = {
            "candidate_id": candidate_id,
            "label": candidate.label,
            "transfer_risk": candidate.transfer_risk,
            "source_run_id": candidate.source_run_id,
            "run_dir": run_dir,
            "pv_kw": candidate.pv_kw,
            "n_dac": candidate.n_dac,
            "pem_kw": candidate.pem_kw,
            "battery_kwh": candidate.battery_kwh,
            "co2_tank_capacity_mol": candidate.co2_tank_capacity_mol,
            "h2_tank_capacity_mol": candidate.h2_tank_capacity_mol,
            "stage1_green_base_profit_yuan": float(stage1["green_base_annual_profit_yuan"]) if stage1 else None,
            "stage1_lcom_yuan_per_kg": float(stage1["lcom_yuan_per_kg"]) if stage1 else None,
            "stage2_green_base_profit_yuan": green_base["annual_profit_yuan"],
            "stage2_lcom_yuan_per_kg": stage2_eval["economics"]["lcom_yuan_per_kg"],
            "profit_delta_yuan": (
                green_base["annual_profit_yuan"] - float(stage1["green_base_annual_profit_yuan"])
                if stage1
                else None
            ),
            "lcom_delta_yuan_per_kg": (
                stage2_eval["economics"]["lcom_yuan_per_kg"] - float(stage1["lcom_yuan_per_kg"])
                if stage1
                else None
            ),
            "annual_methanol_kg": stage2_summary["annual_methanol_kg"],
            "annual_grid_purchase_kwh": stage2_summary["annual_grid_purchase_kwh"],
            "annual_curtailment_kwh": stage2_summary["annual_curtailment_kwh"],
            "feasible": stage2_eval["feasible"],
            "safety_margin": stage2_eval["safety_margin"],
            "hard_safety_margin": stage2_eval["hard_safety_margin"],
        }
        rows.append(row)

    rows.sort(key=lambda item: (item["stage2_green_base_profit_yuan"], -item["safety_margin"]), reverse=True)

    csv_path = os.path.join(RESULTS_DIR, "stage2_final_summary.csv")
    json_path = os.path.join(RESULTS_DIR, "stage2_final_summary.json")
    md_path = os.path.join(RESULTS_DIR, "stage2_final_summary.md")

    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

        medium_rows = [row for row in rows if row["transfer_risk"] == "medium"]
        high_rows = [row for row in rows if row["transfer_risk"] == "high"]

        lines = [
            f"# Stage-2 Final Summary ({datetime.now().isoformat()})",
            "",
            "## Ranked Results",
            "",
        ]
        for idx, row in enumerate(rows, start=1):
            lines.extend(
                [
                    f"### Rank {idx}: {row['candidate_id']}",
                    f"- transfer risk: {row['transfer_risk']}",
                    f"- stage1 profit: {row['stage1_green_base_profit_yuan']:.2f} yuan" if row["stage1_green_base_profit_yuan"] is not None else "- stage1 profit: n/a",
                    f"- stage2 profit: {row['stage2_green_base_profit_yuan']:.2f} yuan",
                    f"- profit delta: {row['profit_delta_yuan']:.2f} yuan" if row["profit_delta_yuan"] is not None else "- profit delta: n/a",
                    f"- stage1 LCOM: {row['stage1_lcom_yuan_per_kg']:.4f} yuan/kg" if row["stage1_lcom_yuan_per_kg"] is not None else "- stage1 LCOM: n/a",
                    f"- stage2 LCOM: {row['stage2_lcom_yuan_per_kg']:.4f} yuan/kg",
                    f"- LCOM delta: {row['lcom_delta_yuan_per_kg']:.4f} yuan/kg" if row["lcom_delta_yuan_per_kg"] is not None else "- LCOM delta: n/a",
                    f"- annual methanol: {row['annual_methanol_kg']:.2f} kg",
                    f"- annual grid purchase: {row['annual_grid_purchase_kwh']:.2f} kWh",
                    f"- annual curtailment: {row['annual_curtailment_kwh']:.2f} kWh",
                    f"- feasible: {row['feasible']}",
                    f"- safety margin: {row['safety_margin']:.6f}",
                    f"- hard safety margin: {row['hard_safety_margin']:.6f}",
                    "",
                ]
            )

        if medium_rows:
            best_medium = medium_rows[0]
            lines.extend(
                [
                    "## Best Medium-Risk Candidate",
                    "",
                    f"- candidate_id: {best_medium['candidate_id']}",
                    f"- stage2 profit: {best_medium['stage2_green_base_profit_yuan']:.2f} yuan",
                    f"- stage2 LCOM: {best_medium['stage2_lcom_yuan_per_kg']:.4f} yuan/kg",
                    "",
                ]
            )

        if high_rows:
            best_high = high_rows[0]
            lines.extend(
                [
                    "## Best High-Risk Candidate",
                    "",
                    f"- candidate_id: {best_high['candidate_id']}",
                    f"- stage2 profit: {best_high['stage2_green_base_profit_yuan']:.2f} yuan",
                    f"- stage2 LCOM: {best_high['stage2_lcom_yuan_per_kg']:.4f} yuan/kg",
                    "",
                ]
            )

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"saved_csv={csv_path}")
        print(f"saved_json={json_path}")
        print(f"saved_md={md_path}")
        print(f"n_candidates={len(rows)}")


if __name__ == "__main__":
    main()

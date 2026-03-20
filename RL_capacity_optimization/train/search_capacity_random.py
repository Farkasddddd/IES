import csv
import argparse
from datetime import datetime
import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
SEARCH_RUNS_DIR = os.path.join(RESULTS_DIR, "search_runs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.capacity_search_space import DEFAULT_SEARCH_SPACE
from config.market_scenarios import DEFAULT_PAPER_SCENARIOS, to_dict as scenario_to_dict
from metrics.dispatch_evaluator import evaluate_candidate, load_reference_policy


def flatten_result(result: dict) -> dict:
    row = {}
    row.update(result["config"])
    row.update(result["dispatch_summary"])
    row["feasible"] = result["feasible"]
    row["infeasible_reasons"] = "; ".join(result["infeasible_reasons"])
    row["safety_margin"] = result["safety_margin"]
    row["hard_safety_margin"] = result["hard_safety_margin"]
    row["transfer_distance"] = result["transfer_distance"]
    row["transfer_risk"] = result["transfer_risk"]
    row["annualized_capex_yuan"] = result["economics"]["annualized_capex_yuan"]
    row["annual_grid_cost_yuan"] = result["economics"]["annual_grid_cost_yuan"]
    row["lcom_yuan_per_kg"] = result["economics"]["lcom_yuan_per_kg"]
    row["ranking_key"] = result["ranking_key"]
    row["evaluation_seconds"] = result["evaluation_seconds"]

    for name, scenario in result["economics"]["scenario_results"].items():
        row[f"{name}_methanol_price_yuan_per_kg"] = scenario["methanol_price_yuan_per_kg"]
        row[f"{name}_annual_revenue_yuan"] = scenario["annual_revenue_yuan"]
        row[f"{name}_annual_profit_yuan"] = scenario["annual_profit_yuan"]
        row[f"{name}_margin_yuan_per_kg"] = scenario["margin_yuan_per_kg"]
    return row


def build_shortlist(results: list[dict]) -> list[dict]:
    candidates = [
        item
        for item in results
        if item["feasible"] and item["transfer_risk"] in {"low", "medium"}
    ]
    candidates.sort(
        key=lambda item: (
            item["economics"]["scenario_results"]["green_base"]["annual_profit_yuan"],
            item["safety_margin"],
            item["hard_safety_margin"],
            -item["transfer_distance"],
        ),
        reverse=True,
    )
    return candidates[:10]


def main():
    parser = argparse.ArgumentParser(description="Stage-1 random capacity screening with fixed hierarchical policy.")
    parser.add_argument("--n-trials", type=int, default=12, help="Number of candidate configurations to evaluate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for candidate sampling.")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(SEARCH_RUNS_DIR, exist_ok=True)

    n_trials = args.n_trials
    seed = args.seed
    rng = random.Random(seed)
    model = load_reference_policy()
    results = []

    run_id = f"random_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = os.path.join(SEARCH_RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    for i in range(n_trials):
        decision = DEFAULT_SEARCH_SPACE.sample(rng)
        result = evaluate_candidate(
            capacity_config=decision.to_capacity_config(),
            sizing_kwargs=decision.to_env_kwargs(),
            model=model,
        )
        results.append(result)
        print(
            f"[{i + 1}/{n_trials}] feasible={result['feasible']} "
            f"base_profit={result['economics']['scenario_results']['green_base']['annual_profit_yuan']:.2f} "
            f"config={decision.to_dict()}"
        )

    results.sort(key=lambda item: item["ranking_key"], reverse=True)

    json_path = os.path.join(run_dir, "results_raw.json")
    csv_path = os.path.join(run_dir, "results_table.csv")
    metadata_path = os.path.join(run_dir, "run_metadata.json")
    summary_path = os.path.join(run_dir, "run_summary.md")
    shortlist_csv_path = os.path.join(run_dir, "shortlist.csv")
    shortlist_md_path = os.path.join(run_dir, "shortlist.md")

    metadata = {
        "run_id": run_id,
        "run_type": "random_search_stage1_fixed_policy",
        "timestamp_local": datetime.now().isoformat(),
        "reference_policy_name": "sac_hierarchical_reference",
        "n_trials": n_trials,
        "random_seed": seed,
        "ranking_rule": "Feasibility first, then green_base annual profit descending",
        "feasibility_rules": [
            "CO2 overflow == 0",
            "H2 overflow == 0",
            "CO2 tank ratio within 20%-80%",
            "H2 tank ratio within 20%-80%",
            "Battery SOC within 20%-80%",
        ],
        "transferability_note": "Transfer risk is reported relative to the hierarchical reference configuration; lower is safer for fixed-policy reuse.",
        "safety_metric_note": "safety_margin uses the tighter 25%-75% operational comfort band; hard_safety_margin uses the hard 20%-80% feasibility band.",
        "price_scenarios": [scenario_to_dict(item) for item in DEFAULT_PAPER_SCENARIOS],
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    flat_rows = [flatten_result(item) for item in results]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    feasible = [item for item in results if item["feasible"]]
    best = feasible[0] if feasible else None
    shortlist = build_shortlist(results)

    summary_lines = [
        f"# Search Run {run_id}",
        "",
        "## Run Setup",
        "",
        f"- run type: {metadata['run_type']}",
        f"- reference policy: {metadata['reference_policy_name']}",
        f"- number of trials: {n_trials}",
        f"- random seed: {seed}",
        f"- ranking rule: {metadata['ranking_rule']}",
        "",
        "## Result Counts",
        "",
        f"- total candidates: {len(results)}",
        f"- feasible candidates: {len(feasible)}",
        f"- shortlist candidates: {len(shortlist)}",
    ]

    if best is not None:
        summary_lines.extend(
            [
                "",
                "## Selected Best Candidate",
                "",
                f"- green_base annual profit: {best['economics']['scenario_results']['green_base']['annual_profit_yuan']:.2f} yuan",
                f"- LCOM: {best['economics']['lcom_yuan_per_kg']:.4f} yuan/kg",
                f"- safety margin: {best['safety_margin']:.6f}",
                f"- hard safety margin: {best['hard_safety_margin']:.6f}",
                f"- transfer distance: {best['transfer_distance']:.6f}",
                f"- transfer risk: {best['transfer_risk']}",
                f"- config: {best['config']}",
            ]
        )
    else:
        summary_lines.extend(
            [
                "",
                "## Selected Best Candidate",
                "",
                "- no feasible candidate found in this run",
            ]
        )

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    shortlist_rows = [flatten_result(item) for item in shortlist]
    if shortlist_rows:
        with open(shortlist_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(shortlist_rows[0].keys()))
            writer.writeheader()
            writer.writerows(shortlist_rows)

        shortlist_lines = [
            f"# Shortlist For {run_id}",
            "",
            "Candidates are filtered using:",
            "",
            "- feasible == True",
            "- transfer_risk in {low, medium}",
            "- sorted by green_base annual profit descending",
            "- tie-break by operational safety margin, then hard safety margin",
            "",
            "## Top Candidates",
            "",
        ]
        for idx, item in enumerate(shortlist, start=1):
            shortlist_lines.extend(
                [
                    f"### Rank {idx}",
                    f"- green_base annual profit: {item['economics']['scenario_results']['green_base']['annual_profit_yuan']:.2f} yuan",
                    f"- LCOM: {item['economics']['lcom_yuan_per_kg']:.4f} yuan/kg",
                    f"- safety margin: {item['safety_margin']:.6f}",
                    f"- hard safety margin: {item['hard_safety_margin']:.6f}",
                    f"- transfer distance: {item['transfer_distance']:.6f}",
                    f"- transfer risk: {item['transfer_risk']}",
                    f"- config: {item['config']}",
                    "",
                ]
            )
        with open(shortlist_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(shortlist_lines))

    latest_json = os.path.join(RESULTS_DIR, "capacity_search_random_results.json")
    latest_csv = os.path.join(RESULTS_DIR, "capacity_search_random_results.csv")
    latest_summary = os.path.join(RESULTS_DIR, "capacity_search_random_latest_summary.md")
    latest_metadata = os.path.join(RESULTS_DIR, "capacity_search_random_latest_metadata.json")
    latest_shortlist_csv = os.path.join(RESULTS_DIR, "capacity_search_random_latest_shortlist.csv")
    latest_shortlist_md = os.path.join(RESULTS_DIR, "capacity_search_random_latest_shortlist.md")

    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(latest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)
    with open(latest_summary, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    with open(latest_metadata, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    if shortlist_rows:
        with open(latest_shortlist_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(shortlist_rows[0].keys()))
            writer.writeheader()
            writer.writerows(shortlist_rows)
        with open(latest_shortlist_md, "w", encoding="utf-8") as f:
            f.write("\n".join(shortlist_lines))

    print(f"run_dir={run_dir}")
    print(f"saved_json={json_path}")
    print(f"saved_csv={csv_path}")
    print(f"saved_summary={summary_path}")
    if shortlist_rows:
        print(f"saved_shortlist_csv={shortlist_csv_path}")
        print(f"saved_shortlist_md={shortlist_md_path}")
    print(f"n_total={len(results)}")
    print(f"n_feasible={len(feasible)}")
    print(f"n_shortlist={len(shortlist)}")
    if best is not None:
        print(f"best_green_base_profit={best['economics']['scenario_results']['green_base']['annual_profit_yuan']:.2f}")
        print(f"best_lcom={best['economics']['lcom_yuan_per_kg']:.4f}")
        print(f"best_config={best['config']}")


if __name__ == "__main__":
    main()

import argparse
import csv
from datetime import datetime
import itertools
import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
SEARCH_RUNS_DIR = os.path.join(RESULTS_DIR, "search_runs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.capacity_search_space import DEFAULT_SEARCH_SPACE, SizingDecision
from config.market_scenarios import DEFAULT_PAPER_SCENARIOS, to_dict as scenario_to_dict
from metrics.dispatch_evaluator import evaluate_candidate, load_reference_policy
from train.search_capacity_random import build_shortlist, flatten_result


ANCHOR_RUN_IDS = (
    "random_search_20260319_214103",
    "random_search_20260319_215805",
)


def row_to_decision(row: dict) -> SizingDecision:
    return SizingDecision(
        pv_scale=float(row["pv_kw"]) / 1000.0,
        pem_capacity_kw=float(row["pem_kw"]),
        n_dac=int(float(row["n_dac"])),
        battery_capacity_kwh=float(row["battery_kwh"]),
        co2_tank_capacity_mol=float(row["co2_tank_capacity_mol"]),
        h2_tank_capacity_mol=float(row["h2_tank_capacity_mol"]),
    )


def load_anchor_rows(anchor_run_ids: tuple[str, ...], top_k_per_run: int = 3) -> list[dict]:
    anchors = []
    for run_id in anchor_run_ids:
        csv_path = os.path.join(SEARCH_RUNS_DIR, run_id, "results_table.csv")
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows = [row for row in rows if row["feasible"] == "True"]
        rows.sort(key=lambda row: float(row["green_base_annual_profit_yuan"]), reverse=True)
        anchors.extend(rows[:top_k_per_run])
    return anchors


def build_local_pool(
    anchors: list[dict],
    radius: int = 1,
) -> list[SizingDecision]:
    pool = {}
    for row in anchors:
        center = row_to_decision(row)
        choices = DEFAULT_SEARCH_SPACE.local_choice_map(center, radius=radius)
        keys = (
            "pv_scale",
            "pem_capacity_kw",
            "n_dac",
            "battery_capacity_kwh",
            "co2_tank_capacity_mol",
            "h2_tank_capacity_mol",
        )
        value_grid = [choices[key] for key in keys]
        for combo in itertools.product(*value_grid):
            decision = SizingDecision(
                pv_scale=float(combo[0]),
                pem_capacity_kw=float(combo[1]),
                n_dac=int(combo[2]),
                battery_capacity_kwh=float(combo[3]),
                co2_tank_capacity_mol=float(combo[4]),
                h2_tank_capacity_mol=float(combo[5]),
            )
            pool[decision.to_dict().__repr__()] = decision
    return list(pool.values())


def main():
    parser = argparse.ArgumentParser(description="Stage-1 local capacity screening around archived elite candidates.")
    parser.add_argument("--n-trials", type=int, default=80, help="Number of local candidates to evaluate.")
    parser.add_argument("--seed", type=int, default=20260319, help="Random seed for local sampling.")
    parser.add_argument("--radius", type=int, default=1, help="Neighborhood radius over the discrete search grid.")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(SEARCH_RUNS_DIR, exist_ok=True)

    rng = random.Random(args.seed)
    model = load_reference_policy()

    anchor_rows = load_anchor_rows(ANCHOR_RUN_IDS, top_k_per_run=3)
    if not anchor_rows:
        raise RuntimeError("No archived anchor runs found for local search.")

    local_pool = build_local_pool(anchor_rows, radius=args.radius)
    rng.shuffle(local_pool)
    selected = local_pool[: min(args.n_trials, len(local_pool))]

    run_id = f"local_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = os.path.join(SEARCH_RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    results = []
    for i, decision in enumerate(selected):
        result = evaluate_candidate(
            capacity_config=decision.to_capacity_config(),
            sizing_kwargs=decision.to_env_kwargs(),
            model=model,
        )
        results.append(result)
        print(
            f"[{i + 1}/{len(selected)}] feasible={result['feasible']} "
            f"base_profit={result['economics']['scenario_results']['green_base']['annual_profit_yuan']:.2f} "
            f"safety_margin={result['safety_margin']:.4f} "
            f"config={decision.to_dict()}"
        )

    results.sort(key=lambda item: item["ranking_key"], reverse=True)
    feasible = [item for item in results if item["feasible"]]
    shortlist = build_shortlist(results)
    best = feasible[0] if feasible else None

    json_path = os.path.join(run_dir, "results_raw.json")
    csv_path = os.path.join(run_dir, "results_table.csv")
    metadata_path = os.path.join(run_dir, "run_metadata.json")
    summary_path = os.path.join(run_dir, "run_summary.md")
    shortlist_csv_path = os.path.join(run_dir, "shortlist.csv")
    shortlist_md_path = os.path.join(run_dir, "shortlist.md")

    metadata = {
        "run_id": run_id,
        "run_type": "local_search_stage1_fixed_policy",
        "timestamp_local": datetime.now().isoformat(),
        "reference_policy_name": "sac_hierarchical_reference",
        "n_trials": len(selected),
        "random_seed": args.seed,
        "radius": args.radius,
        "anchor_run_ids": list(ANCHOR_RUN_IDS),
        "anchor_count": len(anchor_rows),
        "candidate_pool_size": len(local_pool),
        "ranking_rule": "Feasibility first, then green_base annual profit descending",
        "price_scenarios": [scenario_to_dict(item) for item in DEFAULT_PAPER_SCENARIOS],
        "selection_note": "Anchors are taken from archived profitable random-search candidates; local neighborhood uses adjacent discrete design choices.",
        "safety_metric_note": "safety_margin uses the tighter 25%-75% operational comfort band; hard_safety_margin uses the hard 20%-80% feasibility band.",
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

    summary_lines = [
        f"# Search Run {run_id}",
        "",
        "## Run Setup",
        "",
        f"- run type: {metadata['run_type']}",
        f"- reference policy: {metadata['reference_policy_name']}",
        f"- evaluated candidates: {len(selected)}",
        f"- random seed: {args.seed}",
        f"- neighborhood radius: {args.radius}",
        f"- anchor runs: {', '.join(ANCHOR_RUN_IDS)}",
        f"- anchor count: {len(anchor_rows)}",
        f"- candidate pool size: {len(local_pool)}",
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

    latest_json = os.path.join(RESULTS_DIR, "capacity_search_local_results.json")
    latest_csv = os.path.join(RESULTS_DIR, "capacity_search_local_results.csv")
    latest_summary = os.path.join(RESULTS_DIR, "capacity_search_local_latest_summary.md")
    latest_metadata = os.path.join(RESULTS_DIR, "capacity_search_local_latest_metadata.json")
    latest_shortlist_csv = os.path.join(RESULTS_DIR, "capacity_search_local_latest_shortlist.csv")
    latest_shortlist_md = os.path.join(RESULTS_DIR, "capacity_search_local_latest_shortlist.md")

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
        print(f"best_safety_margin={best['safety_margin']:.6f}")
        print(f"best_transfer_risk={best['transfer_risk']}")
        print(f"best_config={best['config']}")


if __name__ == "__main__":
    main()

import argparse
import csv
from datetime import datetime
import json
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
STAGE2_RUNS_DIR = os.path.join(RESULTS_DIR, "stage2_runs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.stage2_candidates import DEFAULT_STAGE2_CANDIDATE_ID, STAGE2_CANDIDATES
from env.ies_capacity_env import IESBilevelEnv
from metrics.capacity_objectives import AnnualDispatchSummary, CapacityConfig, evaluate_capacity_combination


def find_latest_run_dir(candidate_id: str) -> str:
    if not os.path.isdir(STAGE2_RUNS_DIR):
        raise FileNotFoundError("No stage2_runs directory found.")
    prefixes = [name for name in os.listdir(STAGE2_RUNS_DIR) if name.startswith(f"stage2_finetune_{candidate_id}_")]
    if not prefixes:
        raise FileNotFoundError(f"No stage-2 run found for candidate_id={candidate_id}.")
    prefixes.sort()
    return os.path.join(STAGE2_RUNS_DIR, prefixes[-1])


def main():
    parser = argparse.ArgumentParser(description="Evaluate a fine-tuned stage-2 policy on a full 8760h rollout.")
    parser.add_argument("--candidate-id", type=str, default=DEFAULT_STAGE2_CANDIDATE_ID)
    parser.add_argument("--run-dir", type=str, default=None)
    args = parser.parse_args()

    if args.candidate_id not in STAGE2_CANDIDATES:
        raise KeyError(f"Unknown candidate_id: {args.candidate_id}")

    candidate = STAGE2_CANDIDATES[args.candidate_id]
    run_dir = args.run_dir or find_latest_run_dir(candidate.candidate_id)
    model_path = os.path.join(run_dir, "models", "policy_finetuned")
    metadata_path = os.path.join(run_dir, "run_metadata.json")

    if not os.path.exists(model_path + ".zip"):
        raise FileNotFoundError(f"Model not found: {model_path}.zip")

    env = IESBilevelEnv(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        dt_hours=1.0,
        episode_horizon=8760,
        random_start=False,
        **candidate.to_env_kwargs(),
    )
    model = SAC.load(model_path)

    obs, _ = env.reset()
    done = False
    truncated = False

    hourly_rows = []
    annual_reward = 0.0
    annual_methanol_kg = 0.0
    annual_grid_purchase_kwh = 0.0
    annual_curtailment_kwh = 0.0
    co2_overflow_total_mol = 0.0
    h2_overflow_total_mol = 0.0
    methanol_hist = []
    tank_co2_hist = []
    tank_h2_hist = []
    battery_hist = []

    while not (done or truncated):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(action)
        annual_reward += float(reward)
        annual_methanol_kg += float(info["methanol_kg_h"]) * env.dt_hours
        annual_grid_purchase_kwh += float(info["grid_kw"]) * env.dt_hours
        annual_curtailment_kwh += float(info["curtail_kw"]) * env.dt_hours
        co2_overflow_total_mol += float(info["co2_overflow_mol"])
        h2_overflow_total_mol += float(info["h2_overflow_mol"])

        methanol_hist.append(float(info["methanol_kg_h"]))
        tank_co2_hist.append(float(info["tank_co2_ratio"]))
        tank_h2_hist.append(float(info["tank_h2_ratio"]))
        battery_hist.append(float(info["battery_soc"]))

        hourly_rows.append(
            {
                "hour_index": len(hourly_rows),
                "methanol_kg_h": float(info["methanol_kg_h"]),
                "grid_kw": float(info["grid_kw"]),
                "curtail_kw": float(info["curtail_kw"]),
                "pem_kw": float(info["pem_kw"]),
                "dac_kw": float(info["dac_kw"]),
                "tank_co2_ratio": float(info["tank_co2_ratio"]),
                "tank_h2_ratio": float(info["tank_h2_ratio"]),
                "battery_soc": float(info["battery_soc"]),
                "co2_overflow_mol": float(info["co2_overflow_mol"]),
                "h2_overflow_mol": float(info["h2_overflow_mol"]),
                "co2_target_ratio": float(info["co2_target_ratio"]),
                "h2_target_ratio": float(info["h2_target_ratio"]),
                "battery_target_ratio": float(info["battery_target_ratio"]),
                "methanol_pull": float(info["methanol_pull"]),
                "n_ready": int(info["n_ready"]),
                "n_saturated": int(info["n_saturated"]),
                "n_ads": int(info["n_ads"]),
                "n_des": int(info["n_des"]),
                "n_cool": int(info["n_cool"]),
            }
        )

    hourly_csv = os.path.join(run_dir, "annual_eval_hourly.csv")
    with open(hourly_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(hourly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(hourly_rows)

    summary = {
        "candidate_id": candidate.candidate_id,
        "run_dir": run_dir,
        "evaluated_at": datetime.now().isoformat(),
        "annual_reward": annual_reward,
        "annual_methanol_kg": annual_methanol_kg,
        "annual_grid_purchase_kwh": annual_grid_purchase_kwh,
        "annual_curtailment_kwh": annual_curtailment_kwh,
        "co2_overflow_total_mol": co2_overflow_total_mol,
        "h2_overflow_total_mol": h2_overflow_total_mol,
        "tank_co2_ratio_min": float(np.min(tank_co2_hist)),
        "tank_co2_ratio_max": float(np.max(tank_co2_hist)),
        "tank_h2_ratio_min": float(np.min(tank_h2_hist)),
        "tank_h2_ratio_max": float(np.max(tank_h2_hist)),
        "battery_soc_min": float(np.min(battery_hist)),
        "battery_soc_max": float(np.max(battery_hist)),
        "methanol_fluctuation_index": float(np.mean(np.abs(np.diff(np.asarray(methanol_hist, dtype=np.float64)))))
        if len(methanol_hist) > 1
        else 0.0,
    }

    annual_eval = evaluate_capacity_combination(
        config=CapacityConfig(
            pv_kw=candidate.pv_kw,
            n_dac=candidate.n_dac,
            pem_kw=candidate.pem_kw,
            battery_kwh=candidate.battery_kwh,
            co2_tank_capacity_mol=candidate.co2_tank_capacity_mol,
            h2_tank_capacity_mol=candidate.h2_tank_capacity_mol,
        ),
        summary=AnnualDispatchSummary(
            annual_methanol_kg=annual_methanol_kg,
            annual_grid_purchase_kwh=annual_grid_purchase_kwh,
            annual_curtailment_kwh=annual_curtailment_kwh,
            co2_overflow_total_mol=co2_overflow_total_mol,
            h2_overflow_total_mol=h2_overflow_total_mol,
            tank_co2_ratio_min=float(np.min(tank_co2_hist)),
            tank_co2_ratio_max=float(np.max(tank_co2_hist)),
            tank_h2_ratio_min=float(np.min(tank_h2_hist)),
            tank_h2_ratio_max=float(np.max(tank_h2_hist)),
            battery_soc_min=float(np.min(battery_hist)),
            battery_soc_max=float(np.max(battery_hist)),
            methanol_fluctuation_index=summary["methanol_fluctuation_index"],
        ),
    )

    training_metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            training_metadata = json.load(f)

    evaluation_payload = {
        "training_metadata": training_metadata,
        "annual_rollout_summary": summary,
        "economic_evaluation": annual_eval,
    }

    json_path = os.path.join(run_dir, "annual_eval_summary.json")
    md_path = os.path.join(run_dir, "annual_eval_summary.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_payload, f, ensure_ascii=False, indent=2)

    green_base = annual_eval["economics"]["scenario_results"]["green_base"]
    md_lines = [
        f"# Annual Evaluation For {os.path.basename(run_dir)}",
        "",
        "## Fixed Capacity",
        "",
        f"- candidate_id: {candidate.candidate_id}",
        f"- config: {candidate.to_dict()}",
        "",
        "## Annual Rollout Summary",
        "",
        f"- annual reward: {summary['annual_reward']:.2f}",
        f"- annual methanol: {summary['annual_methanol_kg']:.2f} kg",
        f"- annual grid purchase: {summary['annual_grid_purchase_kwh']:.2f} kWh",
        f"- annual curtailment: {summary['annual_curtailment_kwh']:.2f} kWh",
        f"- CO2 overflow: {summary['co2_overflow_total_mol']:.2f} mol",
        f"- H2 overflow: {summary['h2_overflow_total_mol']:.2f} mol",
        f"- CO2 tank ratio range: {summary['tank_co2_ratio_min']:.6f} ~ {summary['tank_co2_ratio_max']:.6f}",
        f"- H2 tank ratio range: {summary['tank_h2_ratio_min']:.6f} ~ {summary['tank_h2_ratio_max']:.6f}",
        f"- battery SOC range: {summary['battery_soc_min']:.6f} ~ {summary['battery_soc_max']:.6f}",
        f"- methanol fluctuation index: {summary['methanol_fluctuation_index']:.6f}",
        "",
        "## Economic Evaluation",
        "",
        f"- feasible: {annual_eval['feasible']}",
        f"- safety margin: {annual_eval['safety_margin']:.6f}",
        f"- hard safety margin: {annual_eval['hard_safety_margin']:.6f}",
        f"- transfer risk: {annual_eval['transfer_risk']}",
        f"- LCOM: {annual_eval['economics']['lcom_yuan_per_kg']:.4f} yuan/kg",
        f"- green_base annual profit: {green_base['annual_profit_yuan']:.2f} yuan",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    latest_json = os.path.join(RESULTS_DIR, "stage2_latest_annual_eval.json")
    latest_md = os.path.join(RESULTS_DIR, "stage2_latest_annual_eval.md")
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(evaluation_payload, f, ensure_ascii=False, indent=2)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"run_dir={run_dir}")
    print(f"saved_hourly_csv={hourly_csv}")
    print(f"saved_json={json_path}")
    print(f"saved_md={md_path}")
    print(f"green_base_profit={green_base['annual_profit_yuan']:.2f}")
    print(f"lcom={annual_eval['economics']['lcom_yuan_per_kg']:.4f}")
    print(f"feasible={annual_eval['feasible']}")


if __name__ == "__main__":
    main()

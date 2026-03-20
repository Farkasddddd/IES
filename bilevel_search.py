import json
import os
import random

from train_lower_rl import train_once


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(PROJECT_ROOT, "results")


def annualized_capex(config: dict):
    pv_kw = 1000.0 * config["pv_scale"]
    pem_kw = config["pem_capacity_kw"]
    bat_kwh = config["battery_capacity_kwh"]
    n_dac = config["n_dac"]
    co2_cap = config["tank_co2_capacity_mol"]
    h2_cap = config["tank_h2_capacity_mol"]
    meoh_scale = config["methanol_scale"]

    cost_pv_per_kw = 3000
    cost_pem_per_kw = 5000
    cost_bat_per_kwh = 1200
    cost_dac_per_unit = 20000
    cost_co2_tank_per_mol = 2.0
    cost_h2_tank_per_mol = 4.0
    cost_meoh_scale_unit = 50000

    total_capex = (
        pv_kw * cost_pv_per_kw
        + pem_kw * cost_pem_per_kw
        + bat_kwh * cost_bat_per_kwh
        + n_dac * cost_dac_per_unit
        + co2_cap * cost_co2_tank_per_mol
        + h2_cap * cost_h2_tank_per_mol
        + meoh_scale * cost_meoh_scale_unit
    )

    crf = 0.1
    return total_capex * crf


def evaluate_upper_objectives(config: dict, lower_summary: dict):
    annual_capex = annualized_capex(config)

    annual_profit = (
        lower_summary["annual_revenue"] - lower_summary["annual_grid_cost"] - annual_capex
    )

    return {
        "f_cost": float(-annual_profit),
        "f_curtail": float(lower_summary["curtail_rate"]),
        "f_grid": float(lower_summary["annual_grid_kwh"]),
        "annual_profit": float(annual_profit),
        "annual_methanol_kg": float(lower_summary["annual_methanol_kg"]),
    }


def sample_config(base_config: dict):
    cfg = dict(base_config)
    cfg["pv_scale"] = random.choice([0.8, 1.0, 1.2, 1.5])
    cfg["pem_capacity_kw"] = random.choice([500, 800, 1000, 1200, 1500])
    cfg["n_dac"] = random.choice([5, 10, 15, 20])
    cfg["tank_co2_capacity_mol"] = random.choice([300, 500, 1000, 1500])
    cfg["tank_h2_capacity_mol"] = random.choice([1000, 1500, 2500, 4000])
    cfg["battery_capacity_kwh"] = random.choice([500, 1000, 2000, 4000])
    cfg["methanol_scale"] = random.choice([0.5, 1.0, 1.5, 2.0])
    return cfg


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)

    base_config = {
        "dt_hours": 1.0,
        "pv_scale": 1.0,
        "pem_capacity_kw": 1000.0,
        "n_dac": 10,
        "tank_co2_capacity_mol": 500.0,
        "tank_h2_capacity_mol": 1500.0,
        "battery_capacity_kwh": 2000.0,
        "methanol_scale": 1.0,
        "grid_price_per_kwh": 0.6,
        "methanol_price_per_kg": 2.5,
        "allow_grid": True,
    }

    n_trials = 6
    results = []

    for i in range(n_trials):
        print(f"\n================ Trial {i + 1}/{n_trials} ================")
        config = sample_config(base_config)

        _, lower_summary = train_once(
            config=config,
            total_timesteps=8000,
            model_save_name=None,
        )

        upper_obj = evaluate_upper_objectives(config, lower_summary)

        result = {
            "config": config,
            "lower_summary": lower_summary,
            "upper_objectives": upper_obj,
        }
        results.append(result)

        print("Config:", config)
        print("Objectives:", upper_obj)

    result_path = os.path.join(RESULT_DIR, "bilevel_random_search.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n已保存结果到: {result_path}")

    best = max(results, key=lambda x: x["upper_objectives"]["annual_profit"])
    print("\n===== 当前最好结果（按 annual_profit）=====")
    print(json.dumps(best, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

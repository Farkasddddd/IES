import csv
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
MODELS_DIR = os.path.join(RESULTS_DIR, "models")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from env.ies_bilevel_env_fixed import IESBilevelEnv


def main():
    model_name = "sac_fixed_config_v3"
    model_path = os.path.join(MODELS_DIR, model_name)

    env = IESBilevelEnv(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        dt_hours=1.0,
        pv_scale=1.0,
        pem_capacity_kw=400,
        n_dac=600,
        tank_co2_capacity_mol=50_000,
        tank_h2_capacity_mol=150_000,
        battery_capacity_kwh=2000,
        episode_horizon=8760,
        random_start=False,
    )

    model = SAC.load(model_path)

    obs, _ = env.reset()
    done = False
    truncated = False
    total_reward = 0.0
    rows = []

    while not (done or truncated):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(action)
        total_reward += reward
        rows.append(
            {
                "reward": float(reward),
                "methanol_kg_h": info["methanol_kg_h"],
                "methanol_comp_kw": info["methanol_comp_kw"],
                "grid_kw": info["grid_kw"],
                "curtail_kw": info["curtail_kw"],
                "pem_kw": info["pem_kw"],
                "dac_kw": info["dac_kw"],
                "co2_prod_mol": info["co2_prod_mol"],
                "h2_prod_mol": info["h2_prod_mol"],
                "co2_used_mol": info["co2_used_mol"],
                "h2_used_mol": info["h2_used_mol"],
                "co2_overflow_mol": info["co2_overflow_mol"],
                "h2_overflow_mol": info["h2_overflow_mol"],
                "tank_co2_ratio": info["tank_co2_ratio"],
                "tank_h2_ratio": info["tank_h2_ratio"],
                "n_ready": info["n_ready"],
                "n_saturated": info["n_saturated"],
                "n_ads": info["n_ads"],
                "n_des": info["n_des"],
                "n_cool": info["n_cool"],
            }
        )

    output_csv = os.path.join(RESULTS_DIR, "annual_eval_v3.csv")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def col(name):
        return np.array([row[name] for row in rows], dtype=np.float64)

    methanol_total_kg = float(col("methanol_kg_h").sum() * env.dt_hours)
    grid_total_kwh = float(col("grid_kw").sum() * env.dt_hours)
    curtail_total_kwh = float(col("curtail_kw").sum() * env.dt_hours)
    co2_overflow_total_mol = float(col("co2_overflow_mol").sum())
    h2_overflow_total_mol = float(col("h2_overflow_mol").sum())
    co2_min = float(col("tank_co2_ratio").min())
    co2_max = float(col("tank_co2_ratio").max())
    h2_min = float(col("tank_h2_ratio").min())
    h2_max = float(col("tank_h2_ratio").max())

    pv_total_kwh = float(env.pv_power_kw[: len(rows)].sum() * env.dt_hours)
    state_share = {
        "ready": float(col("n_ready").mean() / env.n_dac_total),
        "ads": float(col("n_ads").mean() / env.n_dac_total),
        "saturated": float(col("n_saturated").mean() / env.n_dac_total),
        "des": float(col("n_des").mean() / env.n_dac_total),
        "cool": float(col("n_cool").mean() / env.n_dac_total),
    }

    print(f"hours={len(rows)}")
    print(f"total_reward={total_reward:.6f}")
    print(f"methanol_total_kg={methanol_total_kg:.6f}")
    print(f"grid_total_kwh={grid_total_kwh:.6f}")
    print(f"curtail_total_kwh={curtail_total_kwh:.6f}")
    print(f"pv_total_kwh={pv_total_kwh:.6f}")
    print(f"co2_overflow_total_mol={co2_overflow_total_mol:.6f}")
    print(f"h2_overflow_total_mol={h2_overflow_total_mol:.6f}")
    print(f"tank_co2_ratio_min={co2_min:.6f}")
    print(f"tank_co2_ratio_max={co2_max:.6f}")
    print(f"tank_h2_ratio_min={h2_min:.6f}")
    print(f"tank_h2_ratio_max={h2_max:.6f}")
    print(f"dac_share_ready={state_share['ready']:.6f}")
    print(f"dac_share_ads={state_share['ads']:.6f}")
    print(f"dac_share_saturated={state_share['saturated']:.6f}")
    print(f"dac_share_des={state_share['des']:.6f}")
    print(f"dac_share_cool={state_share['cool']:.6f}")
    print(f"output_csv={output_csv}")


if __name__ == "__main__":
    main()

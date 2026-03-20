import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import matplotlib.pyplot as plt
import numpy as np
from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
MODELS_DIR = os.path.join(RESULTS_DIR, "models")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from env.ies_bilevel_env_hierarchical import IESBilevelEnv


def main():
    model_path = os.path.join(MODELS_DIR, "sac_hierarchical_v1")
    output_dir = os.path.join(RESULTS_DIR, "figures")
    os.makedirs(output_dir, exist_ok=True)

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
    rows = []

    while not (done or truncated):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(action)
        rows.append(
            {
                "reward": float(reward),
                "methanol_kg_h": info["methanol_kg_h"],
                "grid_kw": info["grid_kw"],
                "curtail_kw": info["curtail_kw"],
                "pem_kw": info["pem_kw"],
                "dac_kw": info["dac_kw"],
                "tank_co2_ratio": info["tank_co2_ratio"],
                "tank_h2_ratio": info["tank_h2_ratio"],
                "battery_soc": info["battery_soc"],
            }
        )

    t = np.arange(len(rows), dtype=np.int32)
    days = t / 24.0

    def series(key):
        return np.array([row[key] for row in rows], dtype=np.float64)

    tank_co2 = series("tank_co2_ratio")
    tank_h2 = series("tank_h2_ratio")
    battery_soc = series("battery_soc")
    methanol = series("methanol_kg_h")
    grid = series("grid_kw")
    curtail = series("curtail_kw")
    pem = series("pem_kw")
    dac = series("dac_kw")

    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(14, 5), dpi=150)
    ax.plot(days, tank_co2, label="CO2 tank ratio", linewidth=1.4)
    ax.plot(days, tank_h2, label="H2 tank ratio", linewidth=1.4)
    ax.axhline(0.2, color="#c0392b", linestyle="--", linewidth=1.0, label="Safe band")
    ax.axhline(0.8, color="#c0392b", linestyle="--", linewidth=1.0)
    ax.set_title("Annual Tank Inventory Ratios")
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Fill ratio")
    ax.set_ylim(0.0, 1.0)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "annual_tank_ratios.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 5), dpi=150)
    ax.plot(days, battery_soc, color="#2c7fb8", linewidth=1.3)
    ax.axhline(0.2, color="#c0392b", linestyle="--", linewidth=1.0, label="Safe band")
    ax.axhline(0.8, color="#c0392b", linestyle="--", linewidth=1.0)
    ax.set_title("Annual Battery SOC")
    ax.set_xlabel("Day of year")
    ax.set_ylabel("SOC")
    ax.set_ylim(0.0, 1.0)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "annual_battery_soc.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 5), dpi=150)
    ax.plot(days, methanol, color="#1b9e77", linewidth=1.0)
    ax.set_title("Annual Methanol Production")
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Methanol (kg/h)")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "annual_methanol_production.png"))
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), dpi=150, sharex=True)
    axes[0].plot(days, pem, label="PEM power", color="#d95f02", linewidth=1.0)
    axes[0].plot(days, dac, label="DAC power", color="#7570b3", linewidth=1.0)
    axes[0].set_ylabel("kW")
    axes[0].set_title("Annual Power Dispatch")
    axes[0].legend()

    axes[1].plot(days, grid, label="Grid import", color="#e7298a", linewidth=1.0)
    axes[1].plot(days, curtail, label="Curtailment", color="#66a61e", linewidth=1.0)
    axes[1].set_ylabel("kW")
    axes[1].legend()

    axes[2].plot(days, tank_co2, label="CO2 tank ratio", linewidth=1.0)
    axes[2].plot(days, tank_h2, label="H2 tank ratio", linewidth=1.0)
    axes[2].plot(days, battery_soc, label="Battery SOC", linewidth=1.0)
    axes[2].axhline(0.2, color="#c0392b", linestyle="--", linewidth=1.0)
    axes[2].axhline(0.8, color="#c0392b", linestyle="--", linewidth=1.0)
    axes[2].set_ylabel("Ratio")
    axes[2].set_xlabel("Day of year")
    axes[2].legend()

    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "annual_dispatch_overview.png"))
    plt.close(fig)

    print(os.path.join(output_dir, "annual_tank_ratios.png"))
    print(os.path.join(output_dir, "annual_battery_soc.png"))
    print(os.path.join(output_dir, "annual_methanol_production.png"))
    print(os.path.join(output_dir, "annual_dispatch_overview.png"))


if __name__ == "__main__":
    main()

import os
import sys
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "results", "models")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from env.ies_capacity_env import IESBilevelEnv
from metrics.capacity_objectives import (
    AnnualDispatchSummary,
    CapacityConfig,
    evaluate_capacity_combination,
)


REFERENCE_MODEL_NAME = "sac_hierarchical_reference"


def load_reference_policy(model_name: str = REFERENCE_MODEL_NAME):
    model_path = os.path.join(MODELS_DIR, model_name)
    return SAC.load(model_path)


def run_annual_dispatch_for_config(
    sizing_kwargs: dict,
    model=None,
) -> AnnualDispatchSummary:
    if model is None:
        model = load_reference_policy()

    env = IESBilevelEnv(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        dt_hours=1.0,
        episode_horizon=8760,
        random_start=False,
        **sizing_kwargs,
    )

    obs, _ = env.reset()
    done = False
    truncated = False

    methanol_hist = []
    battery_hist = [env.soc]

    annual_methanol_kg = 0.0
    annual_grid_purchase_kwh = 0.0
    annual_curtailment_kwh = 0.0
    co2_overflow_total_mol = 0.0
    h2_overflow_total_mol = 0.0
    tank_co2_min = float("inf")
    tank_co2_max = float("-inf")
    tank_h2_min = float("inf")
    tank_h2_max = float("-inf")

    while not (done or truncated):
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, truncated, info = env.step(action)

        methanol = float(info["methanol_kg_h"])
        annual_methanol_kg += methanol * env.dt_hours
        annual_grid_purchase_kwh += float(info["grid_kw"]) * env.dt_hours
        annual_curtailment_kwh += float(info["curtail_kw"]) * env.dt_hours
        co2_overflow_total_mol += float(info["co2_overflow_mol"])
        h2_overflow_total_mol += float(info["h2_overflow_mol"])

        tank_co2 = float(info["tank_co2_ratio"])
        tank_h2 = float(info["tank_h2_ratio"])
        tank_co2_min = min(tank_co2_min, tank_co2)
        tank_co2_max = max(tank_co2_max, tank_co2)
        tank_h2_min = min(tank_h2_min, tank_h2)
        tank_h2_max = max(tank_h2_max, tank_h2)

        methanol_hist.append(methanol)
        battery_hist.append(float(info["battery_soc"]))

    methanol_fluctuation_index = 0.0
    if len(methanol_hist) > 1:
        methanol_arr = np.asarray(methanol_hist, dtype=np.float64)
        methanol_fluctuation_index = float(np.mean(np.abs(np.diff(methanol_arr))))

    battery_arr = np.asarray(battery_hist, dtype=np.float64)

    return AnnualDispatchSummary(
        annual_methanol_kg=float(annual_methanol_kg),
        annual_grid_purchase_kwh=float(annual_grid_purchase_kwh),
        annual_curtailment_kwh=float(annual_curtailment_kwh),
        co2_overflow_total_mol=float(co2_overflow_total_mol),
        h2_overflow_total_mol=float(h2_overflow_total_mol),
        tank_co2_ratio_min=float(tank_co2_min),
        tank_co2_ratio_max=float(tank_co2_max),
        tank_h2_ratio_min=float(tank_h2_min),
        tank_h2_ratio_max=float(tank_h2_max),
        battery_soc_min=float(battery_arr.min()),
        battery_soc_max=float(battery_arr.max()),
        methanol_fluctuation_index=float(methanol_fluctuation_index),
    )


def evaluate_candidate(
    capacity_config: CapacityConfig,
    sizing_kwargs: dict,
    model=None,
) -> dict:
    start = time.time()
    summary = run_annual_dispatch_for_config(sizing_kwargs=sizing_kwargs, model=model)
    result = evaluate_capacity_combination(config=capacity_config, summary=summary)
    result["evaluation_seconds"] = time.time() - start
    return result

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .stage1_config import (
    CO2_KG_PER_MOL,
    H2_KG_PER_MOL,
    annualized_capex,
)


@dataclass(frozen=True)
class RolloutArtifacts:
    hourly_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _sum(rows: list[dict[str, Any]], key: str) -> float:
    return float(sum(float(row.get(key, 0.0)) for row in rows))


def rollout_policy(env, model=None, action_fn: Callable[[np.ndarray, int], np.ndarray] | None = None) -> RolloutArtifacts:
    obs, _ = env.reset()
    done = False
    truncated = False
    rows: list[dict[str, Any]] = []
    step = 0

    while not (done or truncated):
        if action_fn is not None:
            action = action_fn(obs, step)
        elif model is not None:
            action, _ = model.predict(obs, deterministic=True)
        else:
            action = np.full(env.action_space.shape, 0.5, dtype=np.float32)

        obs, reward, done, truncated, info = env.step(action)
        row = {"hour_index": step, "reward": float(reward)}
        row.update(info)
        rows.append(row)
        step += 1

    summary = summarize_rollout(rows=rows, env=env)
    return RolloutArtifacts(hourly_rows=rows, summary=summary)


def summarize_rollout(rows: list[dict[str, Any]], env) -> dict[str, Any]:
    if not rows:
        raise ValueError("No rollout rows provided.")

    base_env = env
    for attr in ("dt_hours", "physical_params", "economic_config", "describe_config"):
        if not hasattr(base_env, attr) and hasattr(base_env, "unwrapped"):
            base_env = base_env.unwrapped
            break

    dt_hours = float(base_env.dt_hours)
    physical = base_env.physical_params
    economic = base_env.economic_config

    annual_methanol_kg = _sum(rows, "methanol_kg_h") * dt_hours
    annual_co2_capture_mol = _sum(rows, "co2_prod_mol")
    annual_h2_production_mol = _sum(rows, "h2_prod_mol")
    annual_pv_generation_kwh = _sum(rows, "pv_abs_kw") * dt_hours
    annual_grid_purchase_kwh = _sum(rows, "grid_kw") * dt_hours
    annual_grid_sale_kwh = _sum(rows, "sell_kw") * dt_hours
    annual_curtailment_kwh = _sum(rows, "curtail_kw") * dt_hours
    annual_battery_charge_kwh = _sum(rows, "battery_charge_kwh")
    annual_battery_discharge_kwh = _sum(rows, "battery_discharge_kwh")
    annual_total_reward = _sum(rows, "reward")

    annualized_capex_yuan = annualized_capex(physical=physical, economic=economic)
    electricity_cost_yuan = annual_grid_purchase_kwh * economic.grid_purchase_price_per_kwh
    electricity_sale_revenue_yuan = annual_grid_sale_kwh * economic.grid_sell_price_per_kwh
    annual_total_cost_yuan = annualized_capex_yuan + electricity_cost_yuan - electricity_sale_revenue_yuan
    lcom_yuan_per_kg = annual_total_cost_yuan / max(annual_methanol_kg, 1e-9)

    total_load_kwh = (_sum(rows, "dac_kw") + _sum(rows, "pem_kw") + _sum(rows, "methanol_comp_kw")) * dt_hours
    external_grid_dependency_ratio = annual_grid_purchase_kwh / max(total_load_kwh, 1e-9)
    energy_self_sufficiency_ratio = max(0.0, 1.0 - external_grid_dependency_ratio)
    co2_self_sufficiency_ratio = 1.0 if _sum(rows, "co2_used_mol") > 0.0 else 0.0
    carbon_intensity_kgco2_per_kg_meoh = (
        annual_grid_purchase_kwh * economic.grid_emission_factor_kgco2_per_kwh / max(annual_methanol_kg, 1e-9)
    )

    co2_targets = [float(row["co2_target_ratio"]) for row in rows]
    h2_targets = [float(row["h2_target_ratio"]) for row in rows]
    co2_targets_effective = [float(row.get("co2_target_ratio_effective", row["co2_target_ratio"])) for row in rows]
    h2_targets_effective = [float(row.get("h2_target_ratio_effective", row["h2_target_ratio"])) for row in rows]
    meoh_pull = [float(row["methanol_pull"]) for row in rows]
    battery_pref = [float(row["battery_target_ratio"]) for row in rows]
    co2_ratio = [float(row["tank_co2_ratio"]) for row in rows]
    h2_ratio = [float(row["tank_h2_ratio"]) for row in rows]
    soc_ratio = [float(row["battery_soc"]) for row in rows]

    performance_metrics = {
        "annual_methanol_kg": annual_methanol_kg,
        "annual_co2_capture_mol": annual_co2_capture_mol,
        "annual_co2_capture_kg": annual_co2_capture_mol * CO2_KG_PER_MOL,
        "annual_h2_production_mol": annual_h2_production_mol,
        "annual_h2_production_kg": annual_h2_production_mol * H2_KG_PER_MOL,
        "annual_pv_generation_kwh": annual_pv_generation_kwh,
        "annual_grid_purchase_kwh": annual_grid_purchase_kwh,
        "annual_grid_sale_kwh": annual_grid_sale_kwh,
        "annual_curtailment_kwh": annual_curtailment_kwh,
        "annual_battery_charge_kwh": annual_battery_charge_kwh,
        "annual_battery_discharge_kwh": annual_battery_discharge_kwh,
        "annual_total_cost_yuan": annual_total_cost_yuan,
        "annualized_capex_yuan": annualized_capex_yuan,
        "electricity_cost_yuan": electricity_cost_yuan,
        "electricity_sale_revenue_yuan": electricity_sale_revenue_yuan,
        "lcom_yuan_per_kg": lcom_yuan_per_kg,
        "external_grid_dependency_ratio": external_grid_dependency_ratio,
        "energy_self_sufficiency_ratio": energy_self_sufficiency_ratio,
        "co2_self_sufficiency_ratio": co2_self_sufficiency_ratio,
        "carbon_intensity_kgco2_per_kg_meoh": carbon_intensity_kgco2_per_kg_meoh,
        "co2_tank_ratio_min": min(co2_ratio),
        "co2_tank_ratio_max": max(co2_ratio),
        "h2_tank_ratio_min": min(h2_ratio),
        "h2_tank_ratio_max": max(h2_ratio),
        "battery_soc_min": min(soc_ratio),
        "battery_soc_max": max(soc_ratio),
    }

    strategy_metrics = {
        "avg_co2_inventory_target_ratio": _mean(co2_targets),
        "avg_h2_inventory_target_ratio": _mean(h2_targets),
        "avg_co2_inventory_target_ratio_effective": _mean(co2_targets_effective),
        "avg_h2_inventory_target_ratio_effective": _mean(h2_targets_effective),
        "avg_methanol_pull_ratio": _mean(meoh_pull),
        "avg_battery_reserve_preference": _mean(battery_pref),
        "avg_dac_load_ratio": _mean([float(row["dac_load_ratio"]) for row in rows]),
        "avg_pem_load_ratio": _mean([float(row["pem_load_ratio"]) for row in rows]),
        "avg_meoh_load_ratio": _mean([float(row["meoh_load_ratio"]) for row in rows]),
        "battery_cycle_count_approx": annual_battery_discharge_kwh / max(2.0 * physical.battery_capacity_kwh, 1e-9),
        "co2_inventory_wave_span": float(max(co2_ratio) - min(co2_ratio)),
        "h2_inventory_wave_span": float(max(h2_ratio) - min(h2_ratio)),
        "soc_wave_span": float(max(soc_ratio) - min(soc_ratio)),
    }

    physics_metrics = {
        "co2_inventory_violation_count": int(sum(int(row["co2_inventory_violation"]) for row in rows)),
        "h2_inventory_violation_count": int(sum(int(row["h2_inventory_violation"]) for row in rows)),
        "soc_violation_count": int(sum(int(row["soc_violation"]) for row in rows)),
        "feed_shortage_count": int(sum(int(row["feed_shortage"]) for row in rows)),
        "pem_limit_hit_count": int(sum(int(row["pem_limit_hit"]) for row in rows)),
        "dac_limit_hit_count": int(sum(int(row["dac_limit_hit"]) for row in rows)),
        "energy_balance_error_kw_max_abs": float(max(abs(float(row["energy_balance_error_kw"])) for row in rows)),
        "energy_balance_error_kw_mean_abs": _mean([abs(float(row["energy_balance_error_kw"])) for row in rows]),
        "co2_balance_error_mol_max_abs": float(max(abs(float(row["co2_balance_error_mol"])) for row in rows)),
        "co2_balance_error_mol_mean_abs": _mean([abs(float(row["co2_balance_error_mol"])) for row in rows]),
        "h2_balance_error_mol_max_abs": float(max(abs(float(row["h2_balance_error_mol"])) for row in rows)),
        "h2_balance_error_mol_mean_abs": _mean([abs(float(row["h2_balance_error_mol"])) for row in rows]),
    }

    reward_breakdown = {
        "methanol_revenue": _sum(rows, "reward_methanol_revenue"),
        "grid_cost": _sum(rows, "reward_grid_cost"),
        "curtailment": _sum(rows, "reward_curtailment"),
        "fluctuation": _sum(rows, "reward_fluctuation"),
        "overflow": _sum(rows, "reward_overflow"),
        "tank_band": _sum(rows, "reward_tank_band"),
        "battery_band": _sum(rows, "reward_battery_band"),
        "power_shortfall": _sum(rows, "reward_power_shortfall"),
        "h2_buffer": _sum(rows, "reward_h2_buffer"),
        "h2_violation_extra": _sum(rows, "reward_h2_violation_extra"),
        "h2_overflow_extra": _sum(rows, "reward_h2_overflow_extra"),
        "total_reward": annual_total_reward,
    }

    return {
        "config": base_env.describe_config()["config"],
        "physical_params": base_env.describe_config()["physical_params"],
        "economic_config": base_env.describe_config()["economic_config"],
        "interface_mode": base_env.describe_config().get("interface_mode", "stage1"),
        "safety_profile": base_env.describe_config().get("safety_profile", "baseline"),
        "performance_metrics": performance_metrics,
        "strategy_metrics": strategy_metrics,
        "physics_metrics": physics_metrics,
        "reward_breakdown": reward_breakdown,
    }


def save_rollout_artifacts(artifacts: RolloutArtifacts, output_dir: str | Path, prefix: str) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_path = output_path / f"{prefix}_hourly.csv"
    json_path = output_path / f"{prefix}_summary.json"
    md_path = output_path / f"{prefix}_summary.md"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(artifacts.hourly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(artifacts.hourly_rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(artifacts.summary, f, ensure_ascii=False, indent=2)

    perf = artifacts.summary["performance_metrics"]
    strategy = artifacts.summary["strategy_metrics"]
    physics = artifacts.summary["physics_metrics"]
    md_lines = [
        f"# {prefix}",
        "",
        "## Performance",
        "",
        f"- annual methanol: {perf['annual_methanol_kg']:.2f} kg",
        f"- annual PV generation: {perf['annual_pv_generation_kwh']:.2f} kWh",
        f"- annual grid purchase: {perf['annual_grid_purchase_kwh']:.2f} kWh",
        f"- annual curtailment: {perf['annual_curtailment_kwh']:.2f} kWh",
        f"- annual total cost: {perf['annual_total_cost_yuan']:.2f} yuan",
        f"- LCOM: {perf['lcom_yuan_per_kg']:.4f} yuan/kg",
        "",
        "## Strategy",
        "",
        f"- avg CO2 target ratio: {strategy['avg_co2_inventory_target_ratio']:.4f}",
        f"- avg H2 target ratio: {strategy['avg_h2_inventory_target_ratio']:.4f}",
        f"- avg methanol pull ratio: {strategy['avg_methanol_pull_ratio']:.4f}",
        f"- avg battery reserve preference: {strategy['avg_battery_reserve_preference']:.4f}",
        "",
        "## Physics",
        "",
        f"- CO2 violation count: {physics['co2_inventory_violation_count']}",
        f"- H2 violation count: {physics['h2_inventory_violation_count']}",
        f"- SOC violation count: {physics['soc_violation_count']}",
        f"- energy balance error max abs: {physics['energy_balance_error_kw_max_abs']:.6f}",
        f"- CO2 balance error max abs: {physics['co2_balance_error_mol_max_abs']:.6f}",
        f"- H2 balance error max abs: {physics['h2_balance_error_mol_max_abs']:.6f}",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "md": str(md_path),
    }

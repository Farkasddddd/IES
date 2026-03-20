from dataclasses import asdict, dataclass
from math import inf
from typing import Iterable

from config.economic_params import (
    DEFAULT_ECONOMIC_PARAMS,
    EconomicParams,
    estimate_annualized_capex,
    estimate_grid_cost,
)
from config.market_scenarios import DEFAULT_PAPER_SCENARIOS, MethanolPriceScenario


@dataclass(frozen=True)
class CapacityConfig:
    pv_kw: float
    n_dac: int
    pem_kw: float
    battery_kwh: float
    co2_tank_capacity_mol: float
    h2_tank_capacity_mol: float


@dataclass(frozen=True)
class AnnualDispatchSummary:
    annual_methanol_kg: float
    annual_grid_purchase_kwh: float
    annual_curtailment_kwh: float
    co2_overflow_total_mol: float
    h2_overflow_total_mol: float
    tank_co2_ratio_min: float
    tank_co2_ratio_max: float
    tank_h2_ratio_min: float
    tank_h2_ratio_max: float
    battery_soc_min: float | None = None
    battery_soc_max: float | None = None
    methanol_fluctuation_index: float | None = None


REFERENCE_CAPACITY_CONFIG = CapacityConfig(
    pv_kw=1000.0,
    n_dac=600,
    pem_kw=400.0,
    battery_kwh=2000.0,
    co2_tank_capacity_mol=50000.0,
    h2_tank_capacity_mol=150000.0,
)


def is_feasible(
    summary: AnnualDispatchSummary,
    safe_low: float = 0.20,
    safe_high: float = 0.80,
) -> tuple[bool, list[str]]:
    reasons = []

    if summary.co2_overflow_total_mol > 1e-9:
        reasons.append("CO2 overflow > 0")
    if summary.h2_overflow_total_mol > 1e-9:
        reasons.append("H2 overflow > 0")
    if summary.tank_co2_ratio_min < safe_low:
        reasons.append("CO2 tank below safe lower bound")
    if summary.tank_co2_ratio_max > safe_high:
        reasons.append("CO2 tank above safe upper bound")
    if summary.tank_h2_ratio_min < safe_low:
        reasons.append("H2 tank below safe lower bound")
    if summary.tank_h2_ratio_max > safe_high:
        reasons.append("H2 tank above safe upper bound")
    if summary.battery_soc_min is not None and summary.battery_soc_min < safe_low:
        reasons.append("Battery SOC below safe lower bound")
    if summary.battery_soc_max is not None and summary.battery_soc_max > safe_high:
        reasons.append("Battery SOC above safe upper bound")

    return len(reasons) == 0, reasons


def estimate_safety_margin(
    summary: AnnualDispatchSummary,
    safe_low: float = 0.20,
    safe_high: float = 0.80,
) -> float:
    return estimate_operational_safety_margin(
        summary=summary,
        target_low=safe_low,
        target_high=safe_high,
    )


def estimate_hard_safety_margin(
    summary: AnnualDispatchSummary,
    safe_low: float = 0.20,
    safe_high: float = 0.80,
) -> float:
    margins = [
        summary.tank_co2_ratio_min - safe_low,
        safe_high - summary.tank_co2_ratio_max,
        summary.tank_h2_ratio_min - safe_low,
        safe_high - summary.tank_h2_ratio_max,
    ]
    if summary.battery_soc_min is not None:
        margins.append(summary.battery_soc_min - safe_low)
    if summary.battery_soc_max is not None:
        margins.append(safe_high - summary.battery_soc_max)
    return float(min(margins))


def estimate_operational_safety_margin(
    summary: AnnualDispatchSummary,
    target_low: float = 0.25,
    target_high: float = 0.75,
) -> float:
    margins = [
        summary.tank_co2_ratio_min - target_low,
        target_high - summary.tank_co2_ratio_max,
        summary.tank_h2_ratio_min - target_low,
        target_high - summary.tank_h2_ratio_max,
    ]
    if summary.battery_soc_min is not None:
        margins.append(summary.battery_soc_min - target_low)
    if summary.battery_soc_max is not None:
        margins.append(target_high - summary.battery_soc_max)
    return float(min(margins))


def estimate_transfer_distance(
    config: CapacityConfig,
    reference: CapacityConfig = REFERENCE_CAPACITY_CONFIG,
) -> float:
    rel_errors = [
        abs(config.pv_kw - reference.pv_kw) / max(reference.pv_kw, 1e-9),
        abs(config.n_dac - reference.n_dac) / max(reference.n_dac, 1),
        abs(config.pem_kw - reference.pem_kw) / max(reference.pem_kw, 1e-9),
        abs(config.battery_kwh - reference.battery_kwh) / max(reference.battery_kwh, 1e-9),
        abs(config.co2_tank_capacity_mol - reference.co2_tank_capacity_mol)
        / max(reference.co2_tank_capacity_mol, 1e-9),
        abs(config.h2_tank_capacity_mol - reference.h2_tank_capacity_mol)
        / max(reference.h2_tank_capacity_mol, 1e-9),
    ]
    return float(sum(rel_errors))


def classify_transfer_risk(transfer_distance: float) -> str:
    if transfer_distance <= 1.0:
        return "low"
    if transfer_distance <= 2.0:
        return "medium"
    return "high"


def estimate_lcom(
    config: CapacityConfig,
    summary: AnnualDispatchSummary,
    economic_params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
) -> float:
    annualized_capex = estimate_annualized_capex(
        pv_kw=config.pv_kw,
        n_dac=config.n_dac,
        pem_kw=config.pem_kw,
        battery_kwh=config.battery_kwh,
        co2_tank_capacity=config.co2_tank_capacity_mol,
        h2_tank_capacity=config.h2_tank_capacity_mol,
        params=economic_params,
    )
    annual_grid_cost = estimate_grid_cost(summary.annual_grid_purchase_kwh, params=economic_params)
    annual_methanol_kg = max(summary.annual_methanol_kg, 1e-9)
    return (annualized_capex + annual_grid_cost) / annual_methanol_kg


def evaluate_scenarios(
    config: CapacityConfig,
    summary: AnnualDispatchSummary,
    price_scenarios: Iterable[MethanolPriceScenario] = DEFAULT_PAPER_SCENARIOS,
    economic_params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
) -> dict:
    annualized_capex = estimate_annualized_capex(
        pv_kw=config.pv_kw,
        n_dac=config.n_dac,
        pem_kw=config.pem_kw,
        battery_kwh=config.battery_kwh,
        co2_tank_capacity=config.co2_tank_capacity_mol,
        h2_tank_capacity=config.h2_tank_capacity_mol,
        params=economic_params,
    )
    annual_grid_cost = estimate_grid_cost(summary.annual_grid_purchase_kwh, params=economic_params)
    lcom_yuan_per_kg = estimate_lcom(config, summary, economic_params=economic_params)

    scenario_results = {}
    for scenario in price_scenarios:
        annual_revenue = scenario.methanol_price_yuan_per_kg * summary.annual_methanol_kg
        annual_profit = annual_revenue - annualized_capex - annual_grid_cost
        scenario_results[scenario.name] = {
            "methanol_price_yuan_per_kg": scenario.methanol_price_yuan_per_kg,
            "annual_revenue_yuan": annual_revenue,
            "annual_profit_yuan": annual_profit,
            "margin_yuan_per_kg": scenario.methanol_price_yuan_per_kg - lcom_yuan_per_kg,
        }

    return {
        "annualized_capex_yuan": annualized_capex,
        "annual_grid_cost_yuan": annual_grid_cost,
        "lcom_yuan_per_kg": lcom_yuan_per_kg,
        "scenario_results": scenario_results,
    }


def evaluate_capacity_combination(
    config: CapacityConfig,
    summary: AnnualDispatchSummary,
    price_scenarios: Iterable[MethanolPriceScenario] = DEFAULT_PAPER_SCENARIOS,
    economic_params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
    safe_low: float = 0.20,
    safe_high: float = 0.80,
) -> dict:
    feasible, infeasible_reasons = is_feasible(summary, safe_low=safe_low, safe_high=safe_high)
    economics = evaluate_scenarios(
        config=config,
        summary=summary,
        price_scenarios=price_scenarios,
        economic_params=economic_params,
    )
    hard_safety_margin = estimate_hard_safety_margin(summary, safe_low=safe_low, safe_high=safe_high)
    safety_margin = estimate_operational_safety_margin(summary)
    transfer_distance = estimate_transfer_distance(config)
    transfer_risk = classify_transfer_risk(transfer_distance)

    result = {
        "config": asdict(config),
        "dispatch_summary": asdict(summary),
        "feasible": feasible,
        "infeasible_reasons": infeasible_reasons,
        "safety_margin": safety_margin,
        "hard_safety_margin": hard_safety_margin,
        "transfer_distance": transfer_distance,
        "transfer_risk": transfer_risk,
        "economics": economics,
        "ranking_key": economics["scenario_results"]["green_base"]["annual_profit_yuan"] if feasible else -inf,
    }
    return result

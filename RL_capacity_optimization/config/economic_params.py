from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class EconomicParams:
    # CAPEX unit costs
    pv_cost_per_kw: float = 2700.0
    dac_cost_per_unit: float = 8000.0
    pem_cost_per_kw: float = 5000.0
    battery_cost_per_kwh: float = 1500.0

    # Tank cost coefficients copied from the provided document.
    # Keep these values editable here until unit definitions are finalized.
    co2_tank_cost_per_mol: float = 0.1
    h2_tank_cost_per_mol: float = 8.0

    # Finance parameters
    discount_rate: float = 0.05
    project_lifetime_years: int = 20

    # Operating economics
    grid_purchase_price_per_kwh: float = 0.65

    # Notes from the source document
    co2_tank_unit_note: str = "Confirmed unit: yuan per mol."
    h2_tank_unit_note: str = "Confirmed unit: yuan per mol."
    scope_note: str = (
        "Current OPEX includes only grid electricity cost. "
        "Fixed O&M, water, catalyst, labor, and other variable costs are not yet included."
    )


DEFAULT_ECONOMIC_PARAMS = EconomicParams()


def capital_recovery_factor(params: EconomicParams = DEFAULT_ECONOMIC_PARAMS) -> float:
    r = params.discount_rate
    n = params.project_lifetime_years
    return (r * (1.0 + r) ** n) / ((1.0 + r) ** n - 1.0)


def estimate_total_capex(
    pv_kw: float,
    n_dac: int,
    pem_kw: float,
    battery_kwh: float,
    co2_tank_capacity: float,
    h2_tank_capacity: float,
    params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
) -> float:
    return (
        pv_kw * params.pv_cost_per_kw
        + n_dac * params.dac_cost_per_unit
        + pem_kw * params.pem_cost_per_kw
        + battery_kwh * params.battery_cost_per_kwh
        + co2_tank_capacity * params.co2_tank_cost_per_mol
        + h2_tank_capacity * params.h2_tank_cost_per_mol
    )


def estimate_annualized_capex(
    pv_kw: float,
    n_dac: int,
    pem_kw: float,
    battery_kwh: float,
    co2_tank_capacity: float,
    h2_tank_capacity: float,
    params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
) -> float:
    total_capex = estimate_total_capex(
        pv_kw=pv_kw,
        n_dac=n_dac,
        pem_kw=pem_kw,
        battery_kwh=battery_kwh,
        co2_tank_capacity=co2_tank_capacity,
        h2_tank_capacity=h2_tank_capacity,
        params=params,
    )
    return total_capex * capital_recovery_factor(params)


def estimate_grid_cost(
    annual_grid_purchase_kwh: float,
    params: EconomicParams = DEFAULT_ECONOMIC_PARAMS,
) -> float:
    return annual_grid_purchase_kwh * params.grid_purchase_price_per_kwh


def to_dict(params: EconomicParams = DEFAULT_ECONOMIC_PARAMS) -> dict:
    return asdict(params)

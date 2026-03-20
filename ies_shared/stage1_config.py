from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping


PV_REF_KW = 1000.0
DEFAULT_H2_CO2_RATIO = 3.0
DEFAULT_FEED_BASE_MOL_S = 0.15
PEM_FULL_LOAD_EFFICIENCY = 0.65
PEM_HHV_J_PER_MOL = 286000.0
CO2_KG_PER_MOL = 44e-3
H2_KG_PER_MOL = 2e-3


@dataclass(frozen=True)
class Stage1EconomicConfig:
    grid_purchase_price_per_kwh: float = 0.65
    grid_sell_price_per_kwh: float = 0.0
    grid_import_limit_kw: float | None = None
    grid_export_limit_kw: float = 0.0
    grid_emission_factor_kgco2_per_kwh: float = 0.556

    pv_cost_per_kw: float = 2700.0
    dac_cost_per_unit: float = 8000.0
    pem_cost_per_kw: float = 5000.0
    battery_cost_per_kwh: float = 1500.0
    co2_tank_cost_per_mol: float = 0.1
    h2_tank_cost_per_mol: float = 8.0

    discount_rate: float = 0.05
    project_lifetime_years: int = 20


@dataclass(frozen=True)
class Stage1Config:
    pv_ref_kw: float = PV_REF_KW
    pv_scale: float = 1.0
    r_dac: float = 600.0
    r_pem: float = 0.4
    r_bat_e: float = 2.0
    r_bat_p: float = 1.0
    r_h2: float = 45.8
    r_co2: float = 92.6
    r_meoh: float = 1.0
    mode: str = "grid"


@dataclass(frozen=True)
class PhysicalParams:
    pv_ref_kw: float
    pv_scale: float
    pv_effective_kw: float
    r_dac: float
    r_pem: float
    r_bat_e: float
    r_bat_p: float
    r_h2: float
    r_co2: float
    r_meoh: float
    n_dac_total: int
    pem_capacity_kw: float
    battery_capacity_kwh: float
    battery_max_power_kw: float
    tank_h2_capacity_mol: float
    tank_co2_capacity_mol: float
    meoh_max_feed_mol_s: float
    mode: str


def stage1_baseline_config() -> Stage1Config:
    return Stage1Config()


def single_factor_scan_configs() -> dict[str, list[Stage1Config]]:
    base = stage1_baseline_config()
    return {
        "r_pem": [base, replace(base, r_pem=0.6), replace(base, r_pem=0.8)],
        "r_bat_e": [base, replace(base, r_bat_e=3.0), replace(base, r_bat_e=4.0)],
        "r_h2": [base, replace(base, r_h2=60.0), replace(base, r_h2=80.0)],
        "r_co2": [base, replace(base, r_co2=120.0), replace(base, r_co2=150.0)],
    }


def combo_scan_configs() -> list[Stage1Config]:
    base = stage1_baseline_config()
    configs = []
    for r_pem in (0.4, 0.6, 0.8):
        for r_bat_e in (2.0, 3.0, 4.0):
            for r_h2 in (45.8, 60.0, 80.0):
                configs.append(replace(base, r_pem=r_pem, r_bat_e=r_bat_e, r_h2=r_h2))
    return configs


def pem_full_load_h2_mol_per_hour(pem_capacity_kw: float) -> float:
    mol_s = (float(pem_capacity_kw) * 1000.0 * PEM_FULL_LOAD_EFFICIENCY) / PEM_HHV_J_PER_MOL
    return mol_s * 3600.0


def build_physical_params(config: Stage1Config) -> PhysicalParams:
    pv_ref_kw = float(config.pv_ref_kw)
    pv_scale = float(config.pv_scale)
    pv_effective_kw = pv_ref_kw * pv_scale
    pem_capacity_kw = float(config.r_pem) * pv_ref_kw
    battery_capacity_kwh = float(config.r_bat_e) * pv_ref_kw
    battery_max_power_kw = float(config.r_bat_p) * pv_ref_kw
    n_dac_total = max(1, int(round(float(config.r_dac) * max(pv_scale, 1e-9))))

    h2_rate_mol_per_hour = pem_full_load_h2_mol_per_hour(pem_capacity_kw)
    tank_h2_capacity_mol = float(config.r_h2) * h2_rate_mol_per_hour

    meoh_max_feed_mol_s = float(config.r_meoh) * DEFAULT_FEED_BASE_MOL_S
    co2_reference_rate_mol_per_hour = meoh_max_feed_mol_s * 3600.0
    tank_co2_capacity_mol = float(config.r_co2) * co2_reference_rate_mol_per_hour

    return PhysicalParams(
        pv_ref_kw=pv_ref_kw,
        pv_scale=pv_scale,
        pv_effective_kw=pv_effective_kw,
        r_dac=float(config.r_dac),
        r_pem=float(config.r_pem),
        r_bat_e=float(config.r_bat_e),
        r_bat_p=float(config.r_bat_p),
        r_h2=float(config.r_h2),
        r_co2=float(config.r_co2),
        r_meoh=float(config.r_meoh),
        n_dac_total=n_dac_total,
        pem_capacity_kw=pem_capacity_kw,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_max_power_kw=battery_max_power_kw,
        tank_h2_capacity_mol=tank_h2_capacity_mol,
        tank_co2_capacity_mol=tank_co2_capacity_mol,
        meoh_max_feed_mol_s=meoh_max_feed_mol_s,
        mode=config.mode,
    )


def capital_recovery_factor(economic: Stage1EconomicConfig) -> float:
    r = economic.discount_rate
    n = economic.project_lifetime_years
    return (r * (1.0 + r) ** n) / ((1.0 + r) ** n - 1.0)


def annualized_capex(physical: PhysicalParams, economic: Stage1EconomicConfig) -> float:
    total = (
        physical.pv_effective_kw * economic.pv_cost_per_kw
        + physical.n_dac_total * economic.dac_cost_per_unit
        + physical.pem_capacity_kw * economic.pem_cost_per_kw
        + physical.battery_capacity_kwh * economic.battery_cost_per_kwh
        + physical.tank_co2_capacity_mol * economic.co2_tank_cost_per_mol
        + physical.tank_h2_capacity_mol * economic.h2_tank_cost_per_mol
    )
    return total * capital_recovery_factor(economic)


def config_to_dict(config: Stage1Config) -> dict[str, Any]:
    return asdict(config)


def economic_to_dict(economic: Stage1EconomicConfig) -> dict[str, Any]:
    return asdict(economic)


def physical_to_dict(physical: PhysicalParams) -> dict[str, Any]:
    return asdict(physical)


def _pick(mapping: Mapping[str, Any], key: str, default: Any) -> Any:
    return mapping.get(key, default)


def coerce_stage1_config(config: Stage1Config | Mapping[str, Any] | None = None, **legacy_kwargs: Any) -> Stage1Config:
    if isinstance(config, Stage1Config):
        return config
    if config is not None:
        mapping = dict(config)
        return Stage1Config(
            pv_ref_kw=float(_pick(mapping, "pv_ref_kw", PV_REF_KW)),
            pv_scale=float(_pick(mapping, "pv_scale", 1.0)),
            r_dac=float(_pick(mapping, "r_dac", 600.0)),
            r_pem=float(_pick(mapping, "r_pem", 0.4)),
            r_bat_e=float(_pick(mapping, "r_bat_e", 2.0)),
            r_bat_p=float(_pick(mapping, "r_bat_p", 1.0)),
            r_h2=float(_pick(mapping, "r_h2", 45.8)),
            r_co2=float(_pick(mapping, "r_co2", 92.6)),
            r_meoh=float(_pick(mapping, "r_meoh", 1.0)),
            mode=str(_pick(mapping, "mode", "grid")),
        )

    pv_ref_kw = float(legacy_kwargs.get("pv_ref_kw", PV_REF_KW))
    pv_scale = float(legacy_kwargs.get("pv_scale", 1.0))
    pem_capacity_kw = float(legacy_kwargs.get("pem_capacity_kw", 400.0))
    n_dac = int(legacy_kwargs.get("n_dac", 600))
    battery_capacity_kwh = float(legacy_kwargs.get("battery_capacity_kwh", 2000.0))
    battery_max_power_kw = legacy_kwargs.get("battery_max_power_kw")
    if battery_max_power_kw is None:
        battery_max_power_kw = legacy_kwargs.get("r_bat_p", 0.5 * battery_capacity_kwh)
    battery_max_power_kw = float(battery_max_power_kw)
    tank_h2_capacity_mol = float(legacy_kwargs.get("tank_h2_capacity_mol", 150000.0))
    tank_co2_capacity_mol = float(legacy_kwargs.get("tank_co2_capacity_mol", 50000.0))
    meoh_max_feed_mol_s = float(legacy_kwargs.get("meoh_max_feed_mol_s", DEFAULT_FEED_BASE_MOL_S))

    h2_ref = max(1e-9, pem_full_load_h2_mol_per_hour(pem_capacity_kw))
    co2_ref = max(1e-9, meoh_max_feed_mol_s * 3600.0)

    return Stage1Config(
        pv_ref_kw=pv_ref_kw,
        pv_scale=pv_scale,
        r_dac=float(n_dac) / max(pv_scale, 1e-9),
        r_pem=pem_capacity_kw / max(pv_ref_kw, 1e-9),
        r_bat_e=battery_capacity_kwh / max(pv_ref_kw, 1e-9),
        r_bat_p=battery_max_power_kw / max(pv_ref_kw, 1e-9),
        r_h2=tank_h2_capacity_mol / h2_ref,
        r_co2=tank_co2_capacity_mol / co2_ref,
        r_meoh=meoh_max_feed_mol_s / max(DEFAULT_FEED_BASE_MOL_S, 1e-9),
        mode=str(legacy_kwargs.get("mode", "grid")),
    )


def coerce_economic_config(economic: Stage1EconomicConfig | Mapping[str, Any] | None = None) -> Stage1EconomicConfig:
    if isinstance(economic, Stage1EconomicConfig):
        return economic
    if economic is None:
        return Stage1EconomicConfig()
    mapping = dict(economic)
    return Stage1EconomicConfig(
        grid_purchase_price_per_kwh=float(_pick(mapping, "grid_purchase_price_per_kwh", 0.65)),
        grid_sell_price_per_kwh=float(_pick(mapping, "grid_sell_price_per_kwh", 0.0)),
        grid_import_limit_kw=_pick(mapping, "grid_import_limit_kw", None),
        grid_export_limit_kw=float(_pick(mapping, "grid_export_limit_kw", 0.0)),
        grid_emission_factor_kgco2_per_kwh=float(_pick(mapping, "grid_emission_factor_kgco2_per_kwh", 0.556)),
        pv_cost_per_kw=float(_pick(mapping, "pv_cost_per_kw", 2700.0)),
        dac_cost_per_unit=float(_pick(mapping, "dac_cost_per_unit", 8000.0)),
        pem_cost_per_kw=float(_pick(mapping, "pem_cost_per_kw", 5000.0)),
        battery_cost_per_kwh=float(_pick(mapping, "battery_cost_per_kwh", 1500.0)),
        co2_tank_cost_per_mol=float(_pick(mapping, "co2_tank_cost_per_mol", 0.1)),
        h2_tank_cost_per_mol=float(_pick(mapping, "h2_tank_cost_per_mol", 8.0)),
        discount_rate=float(_pick(mapping, "discount_rate", 0.05)),
        project_lifetime_years=int(_pick(mapping, "project_lifetime_years", 20)),
    )


def load_config_file(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

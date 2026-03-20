from __future__ import annotations

import csv
import os
from math import cos, pi, sin
from typing import Any, Mapping

import gymnasium as gym
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from gymnasium import spaces

from .stage1_config import (
    DEFAULT_FEED_BASE_MOL_S,
    DEFAULT_H2_CO2_RATIO,
    Stage1Config,
    Stage1EconomicConfig,
    build_physical_params,
    coerce_economic_config,
    coerce_stage1_config,
    config_to_dict,
    economic_to_dict,
    physical_to_dict,
)


class MethanolMLP(nn.Module):
    def __init__(self, input_dim: int = 2, output_dim: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, x):
        return self.net(x)


class IESBilevelEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        pv_data_path: str,
        surrogate_path: str,
        *,
        config: Stage1Config | Mapping[str, Any] | None = None,
        economic_config: Stage1EconomicConfig | Mapping[str, Any] | None = None,
        interface_mode: str = "legacy",
        dt_hours: float = 1.0,
        pv_scale: float = 1.0,
        pem_capacity_kw: float = 400.0,
        n_dac: int = 600,
        tank_co2_capacity_mol: float = 50000.0,
        tank_h2_capacity_mol: float = 150000.0,
        battery_capacity_kwh: float = 2000.0,
        battery_max_power_kw: float | None = None,
        meoh_max_feed_mol_s: float = DEFAULT_FEED_BASE_MOL_S,
        safety_profile: str = "baseline",
        episode_horizon: int = 168,
        random_start: bool = True,
        **_: Any,
    ):
        super().__init__()

        self.interface_mode = str(interface_mode)
        self.safety_profile = str(safety_profile)
        self.dt_hours = float(dt_hours)
        self.dt_seconds = self.dt_hours * 3600.0
        self.episode_horizon = int(episode_horizon)
        self.random_start = bool(random_start)

        self.config = coerce_stage1_config(
            config,
            pv_scale=pv_scale,
            pem_capacity_kw=pem_capacity_kw,
            n_dac=n_dac,
            tank_co2_capacity_mol=tank_co2_capacity_mol,
            tank_h2_capacity_mol=tank_h2_capacity_mol,
            battery_capacity_kwh=battery_capacity_kwh,
            battery_max_power_kw=battery_max_power_kw,
            meoh_max_feed_mol_s=meoh_max_feed_mol_s,
        )
        self.economic_config = coerce_economic_config(economic_config)
        self.physical_params = build_physical_params(self.config)

        self.pem_min_load = 0.05
        self.tank_safe_low = 0.20
        self.tank_safe_high = 0.80
        self.tank_target_low = 0.30
        self.tank_target_high = 0.70
        self.battery_safe_low = 0.20
        self.battery_safe_high = 0.80

        self.P_HEAT_kw = 1.0
        self.P_FAN_kw = 0.05
        self.TIME_ADS = 2
        self.TIME_DES = 1
        self.TIME_COOL = 1
        self.CO2_RATE_UNIT_mol_min = 0.0367
        self.DEFAULT_H2_CO2_RATIO = DEFAULT_H2_CO2_RATIO
        self.h2_guard_buffer = 0.05
        self.h2_guard_recovery = 0.10

        self.pv_ref_profile_kw = self._load_pv(pv_data_path)
        self.pv_power_kw = self.pv_ref_profile_kw * self.physical_params.pv_scale
        self.pv_norm = np.clip(
            self.pv_power_kw / max(1e-6, self.physical_params.pv_effective_kw),
            0.0,
            1.5,
        ).astype(np.float32)
        self.max_steps = len(self.pv_power_kw)
        self.step_idx = 0
        self.episode_step = 0
        self.last_info: dict[str, Any] | None = None

        self.methanol_model, self.X_mean, self.X_std, self.Y_mean, self.Y_std = self._load_methanol_model(
            surrogate_path
        )

        if self.interface_mode == "stage1":
            self.action_space = spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32)
            self.observation_space = spaces.Box(low=-2.0, high=2.0, shape=(24,), dtype=np.float32)
        else:
            self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
            self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(13,), dtype=np.float32)

        self._reset_storage_states()
        self._reset_dac_states()
        self.prev_methanol_kg = 0.0

    @property
    def n_dac_total(self) -> int:
        return self.physical_params.n_dac_total

    @property
    def pem_capacity_kw(self) -> float:
        return self.physical_params.pem_capacity_kw

    @property
    def tank_co2_capacity_mol(self) -> float:
        return self.physical_params.tank_co2_capacity_mol

    @property
    def tank_h2_capacity_mol(self) -> float:
        return self.physical_params.tank_h2_capacity_mol

    @property
    def battery_capacity_kwh(self) -> float:
        return self.physical_params.battery_capacity_kwh

    @property
    def battery_max_power_kw(self) -> float:
        return self.physical_params.battery_max_power_kw

    @property
    def meoh_max_feed_mol_s(self) -> float:
        return self.physical_params.meoh_max_feed_mol_s

    def describe_config(self) -> dict[str, Any]:
        return {
            "config": config_to_dict(self.config),
            "physical_params": physical_to_dict(self.physical_params),
            "economic_config": economic_to_dict(self.economic_config),
            "interface_mode": self.interface_mode,
            "safety_profile": self.safety_profile,
        }

    def _reset_storage_states(self):
        self.soc = 0.5
        self.tank_co2_mol = 0.5 * self.tank_co2_capacity_mol
        self.tank_h2_mol = 0.5 * self.tank_h2_capacity_mol

    def _reset_dac_states(self):
        self.n_ready = self.n_dac_total
        self.n_saturated = 0
        self.timer_ads = np.zeros(self.TIME_ADS, dtype=np.int32)
        self.timer_des = np.zeros(self.TIME_DES, dtype=np.int32)
        self.timer_cool = np.zeros(self.TIME_COOL, dtype=np.int32)

    def _active_ads(self) -> int:
        return int(self.timer_ads.sum())

    def _active_des(self) -> int:
        return int(self.timer_des.sum())

    def _active_cool(self) -> int:
        return int(self.timer_cool.sum())

    def _load_pv(self, path: str) -> np.ndarray:
        if not os.path.exists(path):
            raise FileNotFoundError(f"PV data file not found: {path}")

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        header_idx = None
        for i, row in enumerate(rows):
            if "AC System Output (W)" in row:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Missing 'AC System Output (W)' column in PVWatts file.")

        df = pd.DataFrame(rows[header_idx + 1 :], columns=rows[header_idx])
        df = df.apply(pd.to_numeric, errors="coerce")
        power_kw = df["AC System Output (W)"].fillna(0.0).to_numpy(dtype=np.float32) / 1000.0
        return np.maximum(power_kw, 0.0)

    def _load_methanol_model(self, path: str):
        bundle = torch.load(path, map_location="cpu", weights_only=False)
        model = MethanolMLP(input_dim=len(bundle["input_cols"]), output_dim=len(bundle["output_cols"]))
        model.load_state_dict(bundle["model_state_dict"])
        model.eval()
        return (
            model,
            np.array(bundle["X_mean"], dtype=np.float32),
            np.array(bundle["X_std"], dtype=np.float32),
            np.array(bundle["Y_mean"], dtype=np.float32),
            np.array(bundle["Y_std"], dtype=np.float32),
        )

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self.random_start and self.episode_horizon < self.max_steps:
            high = self.max_steps - self.episode_horizon + 1
            self.step_idx = int(self.np_random.integers(0, high))
        else:
            self.step_idx = 0

        self.episode_step = 0
        self._reset_storage_states()
        self._reset_dac_states()
        self.prev_methanol_kg = 0.0
        self.last_info = None
        return self._get_obs(), {}

    def _hour_of_day(self) -> float:
        return float((self.step_idx % 24) / 24.0)

    def _day_of_year(self) -> float:
        return float((self.step_idx % 8760) / 24.0 / 365.0)

    def _stage1_obs(self) -> np.ndarray:
        pv_kw = float(self.pv_power_kw[self.step_idx])
        pv_norm = float(self.pv_norm[self.step_idx])
        dac_kw = float(self.last_info["dac_kw"]) if self.last_info else 0.0
        pem_kw = float(self.last_info["pem_kw"]) if self.last_info else 0.0
        meoh_kw = float(self.last_info["methanol_comp_kw"]) if self.last_info else 0.0
        grid_kw = float(self.last_info["grid_kw"]) if self.last_info else 0.0
        sell_kw = float(self.last_info["sell_kw"]) if self.last_info else 0.0

        hour_angle = 2.0 * pi * self._hour_of_day()
        day_angle = 2.0 * pi * self._day_of_year()

        return np.array(
            [
                pv_kw / max(1e-6, self.physical_params.pv_ref_kw),
                pv_norm,
                self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol),
                self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol),
                self.soc,
                dac_kw / max(1e-6, self.n_dac_total * self.P_HEAT_kw),
                pem_kw / max(1e-6, self.pem_capacity_kw),
                meoh_kw / max(1e-6, max(float(self.last_info["meoh_max_comp_kw"]) if self.last_info else 1.0, 1.0)),
                grid_kw / max(1e-6, self.physical_params.pv_ref_kw),
                sell_kw / max(1e-6, self.physical_params.pv_ref_kw),
                sin(hour_angle),
                cos(hour_angle),
                sin(day_angle),
                cos(day_angle),
                self.config.r_dac / 1000.0,
                self.config.r_pem,
                self.config.r_bat_e / 10.0,
                self.config.r_bat_p / 10.0,
                self.config.r_h2 / 100.0,
                self.config.r_co2 / 100.0,
                self.config.r_meoh,
                1.0 if self.config.mode == "offgrid" else 0.0,
                1.0 if self.config.mode == "semi_offgrid" else 0.0,
                1.0 if self.config.mode == "grid" else 0.0,
            ],
            dtype=np.float32,
        )

    def _legacy_obs(self) -> np.ndarray:
        pv_now = float(self.pv_power_kw[self.step_idx])
        return np.array(
            [
                pv_now / max(1.0, float(self.pv_power_kw.max())),
                self.soc,
                self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol),
                self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol),
                self.n_ready / max(1, self.n_dac_total),
                self._active_ads() / max(1, self.n_dac_total),
                self.n_saturated / max(1, self.n_dac_total),
                self._active_des() / max(1, self.n_dac_total),
                self._active_cool() / max(1, self.n_dac_total),
                self.prev_methanol_kg / max(1.0, 1000.0 * self.config.r_meoh),
                self._hour_of_day(),
                self.episode_step / max(1, self.episode_horizon - 1),
                (self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol))
                - (self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)),
            ],
            dtype=np.float32,
        )

    def _get_obs(self) -> np.ndarray:
        if self.interface_mode == "stage1":
            return self._stage1_obs()
        return self._legacy_obs()

    def _normalize_action(self, action: np.ndarray) -> np.ndarray:
        action = np.asarray(action, dtype=np.float32)
        if self.interface_mode == "stage1":
            return np.clip(action, 0.0, 1.0)
        return np.clip((action + 1.0) / 2.0, 0.0, 1.0)

    def _dac_cluster(self, co2_target_ratio: float):
        finished_cool = int(self.timer_cool[0])
        if self.TIME_COOL > 1:
            self.timer_cool[:-1] = self.timer_cool[1:]
        self.timer_cool[-1] = 0
        self.n_ready += finished_cool

        finished_des = int(self.timer_des[0])
        if self.TIME_DES > 1:
            self.timer_des[:-1] = self.timer_des[1:]
        self.timer_des[-1] = 0
        self.timer_cool[-1] += finished_des

        finished_ads = int(self.timer_ads[0])
        if self.TIME_ADS > 1:
            self.timer_ads[:-1] = self.timer_ads[1:]
        self.timer_ads[-1] = 0
        self.n_saturated += finished_ads

        co2_ratio = self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)
        deficit = max(0.0, co2_target_ratio - co2_ratio)
        deficit_scale = np.clip(deficit / max(1e-6, self.tank_target_high - self.tank_safe_low), 0.0, 1.0)

        n_new_des = min(self.n_saturated, int(round(self.n_saturated * deficit_scale)))
        if deficit > 0.05:
            n_new_des = max(n_new_des, min(self.n_saturated, max(1, self.n_dac_total // 120)))
        self.n_saturated -= n_new_des
        self.timer_des[-1] += n_new_des

        if co2_ratio < self.tank_safe_high:
            ads_priority = np.clip(
                (self.tank_safe_high - co2_ratio) / max(1e-6, self.tank_safe_high - self.tank_safe_low),
                0.0,
                1.0,
            )
            desired_ads = max(deficit_scale, 0.35 * ads_priority)
            n_new_ads = min(self.n_ready, int(round(self.n_ready * desired_ads)))
        else:
            n_new_ads = 0
        self.n_ready -= n_new_ads
        self.timer_ads[-1] += n_new_ads

        active_ads = self._active_ads()
        active_des = self._active_des()
        active_cool = self._active_cool()
        dac_kw = active_ads * self.P_FAN_kw + active_des * self.P_HEAT_kw
        co2_prod_mol_min = active_des * self.CO2_RATE_UNIT_mol_min

        total_units = self.n_ready + self.n_saturated + active_ads + active_des + active_cool
        if total_units != self.n_dac_total:
            raise RuntimeError(f"DAC count mismatch: {total_units} != {self.n_dac_total}")

        return dac_kw, co2_prod_mol_min, {
            "n_new_ads": n_new_ads,
            "n_new_des": n_new_des,
            "n_ready": self.n_ready,
            "n_saturated": self.n_saturated,
            "n_ads": active_ads,
            "n_des": active_des,
            "n_cool": active_cool,
        }

    def _pem_electrolyzer(self, desired_h2_prod_mol: float):
        desired_h2_prod_mol_s = max(0.0, desired_h2_prod_mol / max(1e-6, self.dt_seconds))
        if desired_h2_prod_mol_s <= 1e-8:
            return 0.0, 0.0, 0.0

        plr_grid = np.linspace(self.pem_min_load, 1.0, 96, dtype=np.float32)
        eta_grid = np.clip(-0.15 * (plr_grid**2) + 0.05 * plr_grid + 0.75, 0.0, 1.0)
        mol_s_grid = (plr_grid * self.pem_capacity_kw * 1000.0 * eta_grid) / 286000.0
        idx = int(np.searchsorted(mol_s_grid, desired_h2_prod_mol_s, side="left"))
        idx = min(idx, len(plr_grid) - 1)
        power_kw = float(plr_grid[idx] * self.pem_capacity_kw)
        mol_min = float(mol_s_grid[idx] * 60.0)
        max_mol_step = float(mol_s_grid[-1] * self.dt_seconds)
        return power_kw, mol_min, max_mol_step

    def _methanol_predict(self, co2_feed_mol_s: float, h2_ratio: float):
        x = np.array([co2_feed_mol_s, h2_ratio], dtype=np.float32)
        x_scaled = (x - self.X_mean) / self.X_std
        x_t = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            y_scaled = self.methanol_model(x_t).cpu().numpy().squeeze()
        y = y_scaled * self.Y_std + self.Y_mean
        return max(0.0, float(y[0])), max(0.0, float(y[1]))

    def _band_penalty(self, ratio: float, low: float, high: float):
        if ratio < low:
            return (low - ratio) / max(low, 1e-6)
        if ratio > high:
            return (ratio - high) / max(1e-6, 1.0 - high)
        return 0.0

    def _buffer_penalty(self, ratio: float, low: float, high: float, buffer: float):
        if buffer <= 0.0:
            return 0.0
        if ratio < low or ratio > high:
            return 0.0
        if ratio < low + buffer:
            return (low + buffer - ratio) / max(buffer, 1e-6)
        if ratio > high - buffer:
            return (ratio - (high - buffer)) / max(buffer, 1e-6)
        return 0.0

    def _effective_h2_target_ratio(self, requested_ratio: float, current_ratio: float) -> tuple[float, int]:
        if self.safety_profile != "h2_guard_v1":
            return float(max(requested_ratio, self.tank_safe_low)), 0

        lower = self.tank_safe_low + self.h2_guard_buffer
        upper = self.tank_safe_high - self.h2_guard_buffer
        effective = float(np.clip(requested_ratio, lower, upper))
        shield_active = 0
        if current_ratio < lower:
            effective = max(effective, self.tank_safe_low + self.h2_guard_recovery)
            shield_active = 1
        elif current_ratio > upper:
            effective = min(effective, self.tank_safe_high - self.h2_guard_recovery)
            shield_active = 1
        return float(effective), shield_active

    def step(self, action):
        normalized_action = self._normalize_action(action)
        pv_kw = float(self.pv_power_kw[self.step_idx])
        pv_norm = float(self.pv_norm[self.step_idx])
        current_h2_ratio = self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol)

        co2_target_ratio_requested = float(normalized_action[0])
        h2_target_ratio_requested = float(normalized_action[1])
        methanol_pull = float(normalized_action[2])
        battery_target_ratio_requested = float(normalized_action[3])
        battery_target_ratio = float(
            np.clip(
                self.battery_safe_low + battery_target_ratio_requested * (self.battery_safe_high - self.battery_safe_low),
                self.battery_safe_low,
                self.battery_safe_high,
            )
        )
        co2_target_ratio_effective = float(max(co2_target_ratio_requested, self.tank_safe_low))
        h2_target_ratio_effective, h2_target_shield_active = self._effective_h2_target_ratio(
            h2_target_ratio_requested,
            current_h2_ratio,
        )

        co2_before_mol = self.tank_co2_mol
        h2_before_mol = self.tank_h2_mol
        soc_before = self.soc

        dac_kw, co2_prod_mol_min, dac_info = self._dac_cluster(co2_target_ratio_requested)
        co2_prod_mol = co2_prod_mol_min * 60.0 * self.dt_hours
        max_dac_prod_mol_step = self.n_dac_total * self.CO2_RATE_UNIT_mol_min * 60.0 * self.dt_hours

        co2_room = max(0.0, self.tank_co2_capacity_mol - self.tank_co2_mol)
        co2_stored_mol = min(co2_prod_mol, co2_room)
        co2_overflow_mol = max(0.0, co2_prod_mol - co2_stored_mol)
        self.tank_co2_mol += co2_stored_mol

        co2_safe_floor_mol = self.tank_safe_low * self.tank_co2_capacity_mol
        h2_safe_floor_mol = self.tank_safe_low * self.tank_h2_capacity_mol
        co2_target_mol = co2_target_ratio_effective * self.tank_co2_capacity_mol
        h2_target_mol = h2_target_ratio_effective * self.tank_h2_capacity_mol

        co2_drawable_mol = max(0.0, self.tank_co2_mol - co2_safe_floor_mol)
        co2_feed_cap_mol_s = min(self.meoh_max_feed_mol_s, co2_drawable_mol / max(1e-6, self.dt_seconds))
        desired_co2_feed_mol_s = min(methanol_pull * self.meoh_max_feed_mol_s, co2_feed_cap_mol_s)

        h2_needed_for_feed_mol = desired_co2_feed_mol_s * self.DEFAULT_H2_CO2_RATIO * self.dt_seconds
        desired_h2_inventory_post_mol = max(h2_target_mol, h2_safe_floor_mol)
        desired_h2_prod_mol = max(0.0, h2_needed_for_feed_mol + desired_h2_inventory_post_mol - self.tank_h2_mol)
        pem_kw, h2_prod_mol_min, pem_max_h2_step_mol = self._pem_electrolyzer(desired_h2_prod_mol)
        h2_prod_mol = h2_prod_mol_min * 60.0 * self.dt_hours

        h2_room = max(0.0, self.tank_h2_capacity_mol - self.tank_h2_mol)
        h2_stored_mol = min(h2_prod_mol, h2_room)
        h2_overflow_mol = max(0.0, h2_prod_mol - h2_stored_mol)
        self.tank_h2_mol += h2_stored_mol

        co2_available_mol_s = max(0.0, self.tank_co2_mol - co2_safe_floor_mol) / max(1e-6, self.dt_seconds)
        h2_available_mol_s = max(0.0, self.tank_h2_mol - h2_safe_floor_mol) / max(1e-6, self.dt_seconds)
        actual_co2_feed_mol_s = min(
            desired_co2_feed_mol_s,
            co2_available_mol_s,
            h2_available_mol_s / self.DEFAULT_H2_CO2_RATIO,
        )
        actual_h2_feed_mol_s = actual_co2_feed_mol_s * self.DEFAULT_H2_CO2_RATIO

        if actual_co2_feed_mol_s <= 1e-8:
            methanol_kg_h = 0.0
            methanol_comp_kw = 0.0
            meoh_max_comp_kw = 1.0
            co2_used_mol = 0.0
            h2_used_mol = 0.0
        else:
            methanol_kg_h, methanol_comp_kw = self._methanol_predict(actual_co2_feed_mol_s, self.DEFAULT_H2_CO2_RATIO)
            _, meoh_max_comp_kw = self._methanol_predict(self.meoh_max_feed_mol_s, self.DEFAULT_H2_CO2_RATIO)
            co2_used_mol = actual_co2_feed_mol_s * self.dt_seconds
            h2_used_mol = actual_h2_feed_mol_s * self.dt_seconds

        self.tank_co2_mol = float(np.clip(self.tank_co2_mol - co2_used_mol, 0.0, self.tank_co2_capacity_mol))
        self.tank_h2_mol = float(np.clip(self.tank_h2_mol - h2_used_mol, 0.0, self.tank_h2_capacity_mol))

        total_load_kw = dac_kw + pem_kw + methanol_comp_kw
        net_kw = pv_kw - total_load_kw

        grid_kw = 0.0
        sell_kw = 0.0
        curtail_kw = 0.0
        battery_charge_kwh = 0.0
        battery_discharge_kwh = 0.0
        power_shortfall_kw = 0.0

        if net_kw >= 0.0:
            charge_room_kwh = max(0.0, battery_target_ratio - self.soc) * self.battery_capacity_kwh
            charge_kwh = min(
                net_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                charge_room_kwh,
            )
            battery_charge_kwh = charge_kwh
            self.soc += charge_kwh / max(1e-6, self.battery_capacity_kwh)
            residual_kw = max(0.0, net_kw - (charge_kwh / max(1e-6, self.dt_hours)))
            export_limit = max(0.0, self.economic_config.grid_export_limit_kw)
            if self.config.mode == "grid" and export_limit > 0.0:
                sell_kw = min(residual_kw, export_limit)
                curtail_kw = max(0.0, residual_kw - sell_kw)
            else:
                curtail_kw = residual_kw
        else:
            deficit_kw = abs(net_kw)
            discharge_available_kwh = max(0.0, self.soc - self.battery_safe_low) * self.battery_capacity_kwh
            if self.soc > battery_target_ratio:
                discharge_available_kwh = max(0.0, self.soc - battery_target_ratio) * self.battery_capacity_kwh
            discharge_kwh = min(
                deficit_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                discharge_available_kwh,
            )
            battery_discharge_kwh = discharge_kwh
            self.soc -= discharge_kwh / max(1e-6, self.battery_capacity_kwh)
            residual_deficit_kw = max(0.0, deficit_kw - (discharge_kwh / max(1e-6, self.dt_hours)))
            if self.config.mode == "offgrid":
                power_shortfall_kw = residual_deficit_kw
            else:
                import_limit = self.economic_config.grid_import_limit_kw
                allowed_grid_kw = residual_deficit_kw if import_limit is None else min(residual_deficit_kw, import_limit)
                grid_kw = max(0.0, allowed_grid_kw)
                power_shortfall_kw = max(0.0, residual_deficit_kw - grid_kw)

        self.soc = float(np.clip(self.soc, self.battery_safe_low, self.battery_safe_high))

        tank_co2_ratio = self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)
        tank_h2_ratio = self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol)

        methanol_kg_step = methanol_kg_h * self.dt_hours
        methanol_fluct_penalty = abs(methanol_kg_step - self.prev_methanol_kg)
        self.prev_methanol_kg = methanol_kg_step

        overflow_penalty = 2500.0 * (
            co2_overflow_mol / max(1.0, self.tank_co2_capacity_mol)
            + h2_overflow_mol / max(1.0, self.tank_h2_capacity_mol)
        )
        tank_band_penalty = 100.0 * (
            self._band_penalty(tank_co2_ratio, self.tank_safe_low, self.tank_safe_high)
            + self._band_penalty(tank_h2_ratio, self.tank_safe_low, self.tank_safe_high)
        )
        battery_band_penalty = 20.0 * self._band_penalty(self.soc, self.battery_safe_low, self.battery_safe_high)
        shortfall_penalty = 10.0 * power_shortfall_kw * self.dt_hours
        h2_buffer_penalty = 0.0
        h2_violation_penalty_extra = 0.0
        h2_overflow_penalty_extra = 0.0
        if self.safety_profile == "h2_guard_v1":
            h2_buffer_penalty = 80.0 * self._buffer_penalty(
                tank_h2_ratio,
                self.tank_safe_low,
                self.tank_safe_high,
                self.h2_guard_buffer,
            )
            h2_violation_penalty_extra = 400.0 * self._band_penalty(
                tank_h2_ratio,
                self.tank_safe_low,
                self.tank_safe_high,
            )
            h2_overflow_penalty_extra = 4000.0 * (h2_overflow_mol / max(1.0, self.tank_h2_capacity_mol))

        reward_components = {
            "methanol_revenue": 8.0 * methanol_kg_step,
            "grid_cost": -2.5 * (grid_kw * self.dt_hours),
            "curtailment": -0.5 * (curtail_kw * self.dt_hours),
            "fluctuation": -0.6 * methanol_fluct_penalty,
            "overflow": -overflow_penalty,
            "tank_band": -tank_band_penalty,
            "battery_band": -battery_band_penalty,
            "power_shortfall": -shortfall_penalty,
            "h2_buffer": -h2_buffer_penalty,
            "h2_violation_extra": -h2_violation_penalty_extra,
            "h2_overflow_extra": -h2_overflow_penalty_extra,
        }
        reward = float(sum(reward_components.values()))

        energy_balance_error_kw = (
            pv_kw
            + grid_kw
            + (battery_discharge_kwh / max(1e-6, self.dt_hours))
            - dac_kw
            - pem_kw
            - methanol_comp_kw
            - (battery_charge_kwh / max(1e-6, self.dt_hours))
            - sell_kw
            - curtail_kw
            - power_shortfall_kw
        )
        co2_balance_error_mol = co2_before_mol + co2_prod_mol - co2_used_mol - co2_overflow_mol - self.tank_co2_mol
        h2_balance_error_mol = h2_before_mol + h2_prod_mol - h2_used_mol - h2_overflow_mol - self.tank_h2_mol

        info = {
            "pv_abs_kw": float(pv_kw),
            "pv_norm": float(pv_norm),
            "methanol_kg_h": float(methanol_kg_h),
            "methanol_comp_kw": float(methanol_comp_kw),
            "meoh_max_comp_kw": float(max(meoh_max_comp_kw, methanol_comp_kw, 1.0)),
            "grid_kw": float(grid_kw),
            "sell_kw": float(sell_kw),
            "curtail_kw": float(curtail_kw),
            "power_shortfall_kw": float(power_shortfall_kw),
            "battery_charge_kwh": float(battery_charge_kwh),
            "battery_discharge_kwh": float(battery_discharge_kwh),
            "pem_kw": float(pem_kw),
            "dac_kw": float(dac_kw),
            "co2_prod_mol": float(co2_prod_mol),
            "h2_prod_mol": float(h2_prod_mol),
            "co2_used_mol": float(co2_used_mol),
            "h2_used_mol": float(h2_used_mol),
            "co2_overflow_mol": float(co2_overflow_mol),
            "h2_overflow_mol": float(h2_overflow_mol),
            "actual_co2_feed_mol_s": float(actual_co2_feed_mol_s),
            "actual_h2_feed_mol_s": float(actual_h2_feed_mol_s),
            "desired_co2_feed_mol_s": float(desired_co2_feed_mol_s),
            "desired_h2_prod_mol": float(desired_h2_prod_mol),
            "tank_co2_ratio": float(tank_co2_ratio),
            "tank_h2_ratio": float(tank_h2_ratio),
            "battery_soc": float(self.soc),
            "battery_soc_before": float(soc_before),
            "co2_target_ratio": float(co2_target_ratio_requested),
            "h2_target_ratio": float(h2_target_ratio_requested),
            "battery_target_ratio": float(battery_target_ratio),
            "co2_target_ratio_requested": float(co2_target_ratio_requested),
            "h2_target_ratio_requested": float(h2_target_ratio_requested),
            "battery_target_ratio_requested": float(battery_target_ratio_requested),
            "co2_target_ratio_effective": float(co2_target_ratio_effective),
            "h2_target_ratio_effective": float(h2_target_ratio_effective),
            "battery_target_ratio_effective": float(battery_target_ratio),
            "h2_target_shield_active": int(h2_target_shield_active),
            "methanol_pull": float(methanol_pull),
            "dac_load_ratio": float(dac_kw / max(1e-6, self.n_dac_total * self.P_HEAT_kw)),
            "pem_load_ratio": float(pem_kw / max(1e-6, self.pem_capacity_kw)),
            "meoh_load_ratio": float(actual_co2_feed_mol_s / max(1e-6, self.meoh_max_feed_mol_s)),
            "overflow_penalty": float(overflow_penalty),
            "tank_band_penalty": float(tank_band_penalty),
            "battery_band_penalty": float(battery_band_penalty),
            "energy_balance_error_kw": float(energy_balance_error_kw),
            "co2_balance_error_mol": float(co2_balance_error_mol),
            "h2_balance_error_mol": float(h2_balance_error_mol),
            "co2_inventory_violation": int(tank_co2_ratio < self.tank_safe_low or tank_co2_ratio > self.tank_safe_high),
            "h2_inventory_violation": int(tank_h2_ratio < self.tank_safe_low or tank_h2_ratio > self.tank_safe_high),
            "soc_violation": int(self.soc < self.battery_safe_low or self.soc > self.battery_safe_high),
            "feed_shortage": int(desired_co2_feed_mol_s - actual_co2_feed_mol_s > 1e-8),
            "pem_limit_hit": int(desired_h2_prod_mol > pem_max_h2_step_mol + 1e-8),
            "dac_limit_hit": int(max(0.0, co2_target_mol - co2_before_mol) > max_dac_prod_mol_step + 1e-8),
            "mode_grid": int(self.config.mode == "grid"),
            "mode_semi": int(self.config.mode == "semi_offgrid"),
            "mode_offgrid": int(self.config.mode == "offgrid"),
            "n_ready": int(dac_info["n_ready"]),
            "n_saturated": int(dac_info["n_saturated"]),
            "n_ads": int(dac_info["n_ads"]),
            "n_des": int(dac_info["n_des"]),
            "n_cool": int(dac_info["n_cool"]),
            "n_new_ads": int(dac_info["n_new_ads"]),
            "n_new_des": int(dac_info["n_new_des"]),
            "reward_total": float(reward),
            "reward_methanol_revenue": float(reward_components["methanol_revenue"]),
            "reward_grid_cost": float(reward_components["grid_cost"]),
            "reward_curtailment": float(reward_components["curtailment"]),
            "reward_fluctuation": float(reward_components["fluctuation"]),
            "reward_overflow": float(reward_components["overflow"]),
            "reward_tank_band": float(reward_components["tank_band"]),
            "reward_battery_band": float(reward_components["battery_band"]),
            "reward_power_shortfall": float(reward_components["power_shortfall"]),
            "reward_h2_buffer": float(reward_components["h2_buffer"]),
            "reward_h2_violation_extra": float(reward_components["h2_violation_extra"]),
            "reward_h2_overflow_extra": float(reward_components["h2_overflow_extra"]),
            "config_r_dac": float(self.config.r_dac),
            "config_r_pem": float(self.config.r_pem),
            "config_r_bat_e": float(self.config.r_bat_e),
            "config_r_bat_p": float(self.config.r_bat_p),
            "config_r_h2": float(self.config.r_h2),
            "config_r_co2": float(self.config.r_co2),
            "config_r_meoh": float(self.config.r_meoh),
            "safety_profile": self.safety_profile,
        }
        self.last_info = info

        self.step_idx += 1
        self.episode_step += 1
        terminated = (self.step_idx >= self.max_steps) or (self.episode_step >= self.episode_horizon)
        obs = self._get_obs() if not terminated else np.zeros(self.observation_space.shape, dtype=np.float32)
        return obs, reward, terminated, False, info

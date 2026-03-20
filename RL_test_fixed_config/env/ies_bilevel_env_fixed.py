import csv
import os

import gymnasium as gym
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from gymnasium import spaces


class MethanolMLP(nn.Module):
    def __init__(self, input_dim=2, output_dim=2):
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
        pv_data_path,
        surrogate_path,
        dt_hours=1.0,
        pv_scale=1.0,
        pem_capacity_kw=400.0,
        n_dac=600,
        tank_co2_capacity_mol=50000.0,
        tank_h2_capacity_mol=150000.0,
        battery_capacity_kwh=2000.0,
        episode_horizon=168,
        random_start=True,
    ):
        super().__init__()

        self.dt_hours = float(dt_hours)
        self.dt_seconds = self.dt_hours * 3600.0

        self.pv_scale = float(pv_scale)
        self.pem_capacity_kw = float(pem_capacity_kw)
        self.n_dac_total = int(n_dac)
        self.tank_co2_capacity_mol = float(tank_co2_capacity_mol)
        self.tank_h2_capacity_mol = float(tank_h2_capacity_mol)
        self.battery_capacity_kwh = float(battery_capacity_kwh)
        self.battery_max_power_kw = 0.5 * self.battery_capacity_kwh
        self.pem_min_load = 0.05
        self.episode_horizon = int(episode_horizon)
        self.random_start = bool(random_start)
        self.tank_safe_low = 0.20
        self.tank_safe_high = 0.80

        self.P_HEAT_kw = 1.0
        self.P_FAN_kw = 0.05
        self.TIME_ADS = 2
        self.TIME_DES = 1
        self.TIME_COOL = 1
        self.CO2_RATE_UNIT_mol_min = 0.0367

        self.pv_power_kw = self._load_pv(pv_data_path) * self.pv_scale
        self.max_steps = len(self.pv_power_kw)
        self.step_idx = 0
        self.episode_start = 0
        self.episode_step = 0

        self.methanol_model, self.X_mean, self.X_std, self.Y_mean, self.Y_std = self._load_methanol_model(
            surrogate_path
        )
        self.methanol_scale = 1.0

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(5,), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(12,), dtype=np.float32)

        self._reset_storage_states()
        self._reset_dac_states()
        self.prev_methanol_kg = 0.0

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

    def _active_ads(self):
        return int(self.timer_ads.sum())

    def _active_des(self):
        return int(self.timer_des.sum())

    def _active_cool(self):
        return int(self.timer_cool.sum())

    def _load_pv(self, path):
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

    def _load_methanol_model(self, path):
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
            self.episode_start = int(self.np_random.integers(0, high))
        else:
            self.episode_start = 0

        self.step_idx = self.episode_start
        self.episode_step = 0
        self._reset_storage_states()
        self._reset_dac_states()
        self.prev_methanol_kg = 0.0

        return self._get_obs(), {}

    def _get_obs(self):
        pv_now = float(self.pv_power_kw[self.step_idx])
        hour_of_day = (self.step_idx % max(1, int(round(24.0 / self.dt_hours)))) / max(
            1, int(round(24.0 / self.dt_hours)) - 1
        )
        episode_progress = self.episode_step / max(1, self.episode_horizon - 1)

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
                self.prev_methanol_kg / max(1.0, 1000.0 * self.methanol_scale),
                hour_of_day,
                episode_progress,
            ],
            dtype=np.float32,
        )

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        pv_kw = float(self.pv_power_kw[self.step_idx])

        pem_set_kw = ((float(action[0]) + 1.0) / 2.0) * self.pem_capacity_kw
        ads_frac = (float(action[1]) + 1.0) / 2.0
        des_frac = (float(action[2]) + 1.0) / 2.0
        feed_frac = (float(action[3]) + 1.0) / 2.0
        ratio_target = 2.8 + ((float(action[4]) + 1.0) / 2.0) * (3.4 - 2.8)

        dac_kw, co2_prod_mol_min, dac_info = self._dac_cluster(ads_frac, des_frac)
        pem_kw, h2_prod_mol_min = self._pem_electrolyzer(pem_set_kw)

        co2_prod_mol = co2_prod_mol_min * 60.0 * self.dt_hours
        h2_prod_mol = h2_prod_mol_min * 60.0 * self.dt_hours

        co2_room = max(0.0, self.tank_co2_capacity_mol - self.tank_co2_mol)
        h2_room = max(0.0, self.tank_h2_capacity_mol - self.tank_h2_mol)

        co2_stored_mol = min(co2_prod_mol, co2_room)
        h2_stored_mol = min(h2_prod_mol, h2_room)
        co2_overflow_mol = max(0.0, co2_prod_mol - co2_stored_mol)
        h2_overflow_mol = max(0.0, h2_prod_mol - h2_stored_mol)

        self.tank_co2_mol += co2_stored_mol
        self.tank_h2_mol += h2_stored_mol

        co2_safe_floor_mol = self.tank_safe_low * self.tank_co2_capacity_mol
        h2_safe_floor_mol = self.tank_safe_low * self.tank_h2_capacity_mol

        co2_drawable_mol = max(0.0, self.tank_co2_mol - co2_safe_floor_mol)
        h2_drawable_mol = max(0.0, self.tank_h2_mol - h2_safe_floor_mol)

        co2_request_mol_s = feed_frac * max(0.0, co2_drawable_mol / self.dt_seconds)
        h2_request_mol_s = co2_request_mol_s * ratio_target

        co2_available_mol_s = co2_drawable_mol / self.dt_seconds
        h2_available_mol_s = h2_drawable_mol / self.dt_seconds

        actual_co2_feed_mol_s = min(
            co2_request_mol_s,
            co2_available_mol_s,
            h2_available_mol_s / max(ratio_target, 1e-6),
        )
        actual_h2_feed_mol_s = actual_co2_feed_mol_s * ratio_target

        if actual_co2_feed_mol_s <= 1e-8:
            methanol_kg_h = 0.0
            methanol_comp_kw = 0.0
            co2_used_mol = 0.0
            h2_used_mol = 0.0
            actual_ratio = ratio_target
        else:
            actual_ratio = actual_h2_feed_mol_s / max(actual_co2_feed_mol_s, 1e-8)
            methanol_kg_h, methanol_comp_kw = self._methanol_predict(actual_co2_feed_mol_s, actual_ratio)
            co2_used_mol = actual_co2_feed_mol_s * self.dt_seconds
            h2_used_mol = actual_h2_feed_mol_s * self.dt_seconds

        self.tank_co2_mol = np.clip(self.tank_co2_mol - co2_used_mol, 0.0, self.tank_co2_capacity_mol)
        self.tank_h2_mol = np.clip(self.tank_h2_mol - h2_used_mol, 0.0, self.tank_h2_capacity_mol)

        total_load_kw = dac_kw + pem_kw + methanol_comp_kw
        net_kw = pv_kw - total_load_kw

        grid_kw = 0.0
        curtail_kw = 0.0
        if net_kw >= 0.0:
            charge_kwh = min(
                net_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                (1.0 - self.soc) * self.battery_capacity_kwh,
            )
            self.soc += charge_kwh / max(1e-6, self.battery_capacity_kwh)
            curtail_kw = max(0.0, (net_kw * self.dt_hours - charge_kwh) / max(1e-6, self.dt_hours))
        else:
            deficit_kw = abs(net_kw)
            discharge_kwh = min(
                deficit_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                self.soc * self.battery_capacity_kwh,
            )
            self.soc -= discharge_kwh / max(1e-6, self.battery_capacity_kwh)
            grid_kw = max(0.0, (deficit_kw * self.dt_hours - discharge_kwh) / max(1e-6, self.dt_hours))

        self.soc = float(np.clip(self.soc, 0.0, 1.0))

        methanol_kg_step = methanol_kg_h * self.dt_hours
        fluct_penalty = abs(methanol_kg_step - self.prev_methanol_kg)
        self.prev_methanol_kg = methanol_kg_step

        tank_co2_ratio = self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)
        tank_h2_ratio = self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol)

        overflow_penalty = 2000.0 * (
            co2_overflow_mol / max(1.0, self.tank_co2_capacity_mol)
            + h2_overflow_mol / max(1.0, self.tank_h2_capacity_mol)
        )

        def band_penalty(ratio):
            if ratio < self.tank_safe_low:
                return (self.tank_safe_low - ratio) / self.tank_safe_low
            if ratio > self.tank_safe_high:
                return (ratio - self.tank_safe_high) / (1.0 - self.tank_safe_high)
            return 0.0

        tank_band_penalty = 80.0 * (band_penalty(tank_co2_ratio) + band_penalty(tank_h2_ratio))

        hard_boundary_penalty = 0.0
        if tank_co2_ratio <= 1e-5 or tank_h2_ratio <= 1e-5:
            hard_boundary_penalty += 5000.0
        if tank_co2_ratio >= 1.0 - 1e-5 or tank_h2_ratio >= 1.0 - 1e-5:
            hard_boundary_penalty += 5000.0

        reward = 0.0
        reward += 8.0 * methanol_kg_step
        reward -= 2.0 * (grid_kw * self.dt_hours)
        reward -= 0.5 * (curtail_kw * self.dt_hours)
        reward -= 0.5 * fluct_penalty
        reward -= overflow_penalty
        reward -= tank_band_penalty
        reward -= hard_boundary_penalty

        self.step_idx += 1
        self.episode_step += 1
        terminated = (self.step_idx >= self.max_steps) or (self.episode_step >= self.episode_horizon)

        obs = self._get_obs() if not terminated else np.zeros(self.observation_space.shape, dtype=np.float32)
        info = {
            "methanol_kg_h": float(methanol_kg_h),
            "methanol_comp_kw": float(methanol_comp_kw),
            "grid_kw": float(grid_kw),
            "curtail_kw": float(curtail_kw),
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
            "actual_h2_co2_ratio": float(actual_ratio),
            "tank_co2_ratio": float(tank_co2_ratio),
            "tank_h2_ratio": float(tank_h2_ratio),
            "tank_band_penalty": float(tank_band_penalty),
            "hard_boundary_penalty": float(hard_boundary_penalty),
            "n_ready": int(self.n_ready),
            "n_saturated": int(self.n_saturated),
            "n_ads": int(self._active_ads()),
            "n_des": int(self._active_des()),
            "n_cool": int(self._active_cool()),
            "n_new_ads": int(dac_info["n_new_ads"]),
            "n_new_des": int(dac_info["n_new_des"]),
        }
        return obs, float(reward), terminated, False, info

    def _dac_cluster(self, ads_frac, des_frac):
        active_ads_before = self._active_ads()
        active_des_before = self._active_des()

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

        n_new_des = min(self.n_saturated, int(round(des_frac * self.n_saturated)))
        self.n_saturated -= n_new_des
        self.timer_des[-1] += n_new_des

        n_new_ads = min(self.n_ready, int(round(ads_frac * self.n_ready)))
        self.n_ready -= n_new_ads
        self.timer_ads[-1] += n_new_ads

        active_ads = self._active_ads()
        active_des = self._active_des()

        dac_kw = active_ads * self.P_FAN_kw + active_des * self.P_HEAT_kw
        co2_prod_mol_min = active_des * self.CO2_RATE_UNIT_mol_min

        total_units = self.n_ready + self.n_saturated + active_ads + active_des + self._active_cool()
        if total_units != self.n_dac_total:
            raise RuntimeError(f"DAC count mismatch: {total_units} != {self.n_dac_total}")

        return dac_kw, co2_prod_mol_min, {
            "n_new_ads": n_new_ads,
            "n_new_des": n_new_des,
            "active_ads_before": active_ads_before,
            "active_des_before": active_des_before,
            "active_ads_after": active_ads,
            "active_des_after": active_des,
        }

    def _pem_electrolyzer(self, power_set_kw):
        power_kw = min(float(power_set_kw), self.pem_capacity_kw)
        plr = power_kw / max(1e-6, self.pem_capacity_kw)
        if plr < self.pem_min_load:
            return 0.0, 0.0

        eta = np.clip(-0.15 * (plr**2) + 0.05 * plr + 0.75, 0.0, 1.0)
        mol_s = (power_kw * 1000.0 * eta) / 286000.0
        return power_kw, mol_s * 60.0

    def _methanol_predict(self, co2_feed_mol_s, h2_ratio):
        x = np.array([co2_feed_mol_s, h2_ratio], dtype=np.float32)
        x_scaled = (x - self.X_mean) / self.X_std
        x_t = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            y_scaled = self.methanol_model(x_t).cpu().numpy().squeeze()
        y = y_scaled * self.Y_std + self.Y_mean
        return max(0.0, float(y[0])), max(0.0, float(y[1]))

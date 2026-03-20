import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

import csv

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
        pv_data_path: str,
        surrogate_path: str,
        dt_hours: float = 1.0,
        pv_scale: float = 1.0,
        pem_capacity_kw: float = 1000.0,
        n_dac: int = 10,
        tank_co2_capacity_mol: float = 500.0,
        tank_h2_capacity_mol: float = 1500.0,
        battery_capacity_kwh: float = 2000.0,
        methanol_scale: float = 1.0,
        grid_price_per_kwh: float = 0.6,
        methanol_price_per_kg: float = 2.5,
        allow_grid: bool = True,
        terminate_on_tank_violation: bool = True,
        random_seed: int = 42,
    ):
        super().__init__()

        self.rng = np.random.default_rng(random_seed)

        self.dt_hours = dt_hours
        self.dt_seconds = dt_hours * 3600.0

        self.pv_scale = pv_scale
        self.pem_capacity_kw = pem_capacity_kw
        self.n_dac_total = int(n_dac)
        self.tank_co2_capacity_mol = tank_co2_capacity_mol
        self.tank_h2_capacity_mol = tank_h2_capacity_mol
        self.battery_capacity_kwh = battery_capacity_kwh
        self.methanol_scale = methanol_scale

        self.grid_price_per_kwh = grid_price_per_kwh
        self.methanol_price_per_kg = methanol_price_per_kg
        self.allow_grid = allow_grid
        self.terminate_on_tank_violation = terminate_on_tank_violation

        self.battery_max_power_kw = 0.5 * self.battery_capacity_kwh

        self.pem_min_load = 0.05
        self.pem_max_load = 1.20

        self.P_HEAT_kw = 1.0
        self.P_FAN_kw = 0.05
        self.TIME_ADS_steps = max(1, int(round(2.0 / self.dt_hours)))
        self.TIME_DES_steps = max(1, int(round(1.0 / self.dt_hours)))
        self.TIME_COOL_steps = max(1, int(round(1.0 / self.dt_hours)))
        self.CO2_RATE_PER_UNIT_mol_min = 0.0367

        self.pv_power_kw = self._load_pvwatts_hourly_data(pv_data_path) * self.pv_scale
        self.max_steps = len(self.pv_power_kw)

        self._load_surrogate(surrogate_path)

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-10.0, high=10.0, shape=(12,), dtype=np.float32)

        self.reset()

    def _load_pvwatts_hourly_data(self, path: str) -> np.ndarray:
        if not os.path.exists(path):
            raise FileNotFoundError(f"未找到光伏数据文件: {path}")

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        header_idx = None
        for i, row in enumerate(rows):
            if "AC System Output (W)" in row:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("未找到 'AC System Output (W)' 列，请检查 PVWatts 文件格式。")

        header = rows[header_idx]
        data_rows = rows[header_idx + 1 :]

        df = pd.DataFrame(data_rows, columns=header)
        df = df.apply(pd.to_numeric, errors="coerce")

        if "AC System Output (W)" not in df.columns:
            raise ValueError("PV 数据中缺少 'AC System Output (W)' 列。")

        power_kw = df["AC System Output (W)"].fillna(0.0).values / 1000.0
        power_kw = np.maximum(power_kw, 0.0)

        print(f"已加载 PVWatts 小时级数据，共 {len(power_kw)} 步")
        return power_kw

    def _load_surrogate(self, surrogate_path: str):
        self.surrogate_available = False

        if not os.path.exists(surrogate_path):
            print(f"未找到代理模型文件: {surrogate_path}")
            self.input_cols = []
            self.output_cols = []
            self.X_mean = self.X_std = self.Y_mean = self.Y_std = None
            self.methanol_model = None
            return

        bundle = torch.load(surrogate_path, map_location="cpu", weights_only=False)
        self.input_cols = bundle["input_cols"]
        self.output_cols = bundle["output_cols"]
        self.X_mean = np.array(bundle["X_mean"], dtype=np.float32)
        self.X_std = np.array(bundle["X_std"], dtype=np.float32)
        self.Y_mean = np.array(bundle["Y_mean"], dtype=np.float32)
        self.Y_std = np.array(bundle["Y_std"], dtype=np.float32)

        self.methanol_model = MethanolMLP(
            input_dim=len(self.input_cols),
            output_dim=len(self.output_cols),
        )
        self.methanol_model.load_state_dict(bundle["model_state_dict"])
        self.methanol_model.eval()
        self.surrogate_available = True
        print(f"已加载甲醇代理模型，输入维度={len(self.input_cols)}")

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.step_idx = 0

        self.soc = 0.5
        self.tank_co2_mol = 0.5 * self.tank_co2_capacity_mol
        self.tank_h2_mol = 0.5 * self.tank_h2_capacity_mol

        self.n_ready = self.n_dac_total
        self.n_saturated = 0
        self.timer_ads = np.zeros(self.TIME_ADS_steps, dtype=int)
        self.timer_des = np.zeros(self.TIME_DES_steps, dtype=int)
        self.timer_cool = np.zeros(self.TIME_COOL_steps, dtype=int)

        self.prev_methanol_kg = 0.0
        self.annual_grid_kwh = 0.0
        self.annual_curtail_kwh = 0.0
        self.annual_methanol_kg = 0.0
        self.annual_pv_kwh = 0.0
        self.annual_revenue = 0.0
        self.annual_grid_cost = 0.0

        obs = self._get_obs()
        info = self._build_info(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return obs, info

    def _get_obs(self):
        pv_now = self.pv_power_kw[self.step_idx]
        day_steps = max(1, int(round(24 / self.dt_hours)))
        hour_of_day = (self.step_idx % day_steps) / max(1, day_steps - 1)
        progress = self.step_idx / max(1, self.max_steps - 1)

        active_ads = self.timer_ads.sum()
        active_des = self.timer_des.sum()
        active_cool = self.timer_cool.sum()

        return np.array(
            [
                pv_now / max(1.0, self.pv_power_kw.max()),
                self.soc,
                self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol),
                self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol),
                self.n_ready / max(1, self.n_dac_total),
                active_ads / max(1, self.n_dac_total),
                self.n_saturated / max(1, self.n_dac_total),
                active_des / max(1, self.n_dac_total),
                active_cool / max(1, self.n_dac_total),
                hour_of_day,
                progress,
                self.prev_methanol_kg / max(1.0, 1000.0 * self.methanol_scale),
            ],
            dtype=np.float32,
        )

    def step(self, action):
        action = np.clip(action, -1.0, 1.0)

        pv_kw = self.pv_power_kw[self.step_idx]
        self.annual_pv_kwh += pv_kw * self.dt_hours

        pem_set_kw = ((action[0] + 1.0) / 2.0) * (self.pem_max_load * self.pem_capacity_kw)
        dac_power_budget_kw = ((action[1] + 1.0) / 2.0) * pv_kw
        methanol_feed_ratio = (action[2] + 1.0) / 2.0

        dac_kw, co2_prod_mol_min = self._dac_cluster(dac_power_budget_kw)
        co2_comp_kw = self._co2_compressor_kw(co2_prod_mol_min)
        pem_kw, h2_prod_mol_min = self._pem_electrolyzer(pem_set_kw)

        self.tank_co2_mol += co2_prod_mol_min * 60.0 * self.dt_hours
        self.tank_h2_mol += h2_prod_mol_min * 60.0 * self.dt_hours

        co2_feed_max_mol_s = max(0.0, self.tank_co2_mol / self.dt_seconds)
        co2_feed_mol_s = methanol_feed_ratio * co2_feed_max_mol_s

        h2_co2_ratio = np.clip(self.tank_h2_mol / max(self.tank_co2_mol, 1e-6), 2.0, 4.0)

        methanol_kg_h, methanol_comp_kw = self._methanol_surrogate_predict(
            feed_co2_mol_s=co2_feed_mol_s,
            h2_co2_ratio=h2_co2_ratio,
        )

        co2_used_mol = co2_feed_mol_s * self.dt_seconds
        h2_used_mol = co2_feed_mol_s * h2_co2_ratio * self.dt_seconds

        self.tank_co2_mol = max(0.0, self.tank_co2_mol - co2_used_mol)
        self.tank_h2_mol = max(0.0, self.tank_h2_mol - h2_used_mol)

        total_load_kw = dac_kw + co2_comp_kw + pem_kw + methanol_comp_kw
        net_kw = pv_kw - total_load_kw

        grid_kw = 0.0
        curtail_kw = 0.0

        if net_kw >= 0:
            energy_room_kwh = (1.0 - self.soc) * self.battery_capacity_kwh
            charge_kwh = min(
                net_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                energy_room_kwh,
            )
            self.soc += charge_kwh / max(1e-6, self.battery_capacity_kwh)
            curtail_kwh = net_kw * self.dt_hours - charge_kwh
            curtail_kw = curtail_kwh / self.dt_hours if self.dt_hours > 0 else 0.0
        else:
            deficit_kw = abs(net_kw)
            available_kwh = self.soc * self.battery_capacity_kwh
            discharge_kwh = min(
                deficit_kw * self.dt_hours,
                self.battery_max_power_kw * self.dt_hours,
                available_kwh,
            )
            self.soc -= discharge_kwh / max(1e-6, self.battery_capacity_kwh)
            unmet_kwh = deficit_kw * self.dt_hours - discharge_kwh
            grid_kw = unmet_kwh / self.dt_hours if self.dt_hours > 0 else 0.0

            if (not self.allow_grid) and unmet_kwh > 1e-8:
                grid_kw = deficit_kw

        self.soc = np.clip(self.soc, 0.0, 1.0)

        methanol_kg_step = methanol_kg_h * self.dt_hours
        self.annual_methanol_kg += methanol_kg_step
        self.annual_grid_kwh += grid_kw * self.dt_hours
        self.annual_curtail_kwh += curtail_kw * self.dt_hours
        self.annual_revenue += methanol_kg_step * self.methanol_price_per_kg
        self.annual_grid_cost += grid_kw * self.dt_hours * self.grid_price_per_kwh

        fluct_penalty = abs(methanol_kg_step - self.prev_methanol_kg)
        self.prev_methanol_kg = methanol_kg_step

        reward = 0.0
        reward += 8.0 * methanol_kg_step
        reward -= 2.0 * (grid_kw * self.dt_hours)
        reward -= 0.5 * (curtail_kw * self.dt_hours)
        reward -= 0.5 * fluct_penalty

        tank_co2_ratio = self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)
        tank_h2_ratio = self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol)

        violated = (
            tank_co2_ratio < 0.02
            or tank_co2_ratio > 1.0
            or tank_h2_ratio < 0.02
            or tank_h2_ratio > 1.0
        )
        if violated:
            reward -= 300.0

        terminated = False
        truncated = False

        if violated and self.terminate_on_tank_violation:
            terminated = True

        self.step_idx += 1
        if self.step_idx >= self.max_steps:
            terminated = True

        obs = (
            self._get_obs()
            if not terminated
            else np.zeros(self.observation_space.shape, dtype=np.float32)
        )
        info = self._build_info(
            methanol_kg_h,
            grid_kw,
            curtail_kw,
            pem_kw,
            dac_kw + co2_comp_kw,
            methanol_comp_kw,
        )

        if terminated:
            info["episode_summary"] = self.get_episode_summary()

        return obs, reward, terminated, truncated, info

    def _dac_cluster(self, power_budget_kw: float):
        active_ads = self.timer_ads.sum()
        active_des = self.timer_des.sum()
        rigid_kw = active_des * self.P_HEAT_kw + active_ads * self.P_FAN_kw

        finished_cool = self.timer_cool[0]
        self.n_ready += finished_cool
        self.timer_cool[:-1] = self.timer_cool[1:]
        self.timer_cool[-1] = 0

        finished_des = self.timer_des[0]
        self.timer_cool[-1] += finished_des
        self.timer_des[:-1] = self.timer_des[1:]
        self.timer_des[-1] = 0

        finished_ads = self.timer_ads[0]
        self.n_saturated += finished_ads
        self.timer_ads[:-1] = self.timer_ads[1:]
        self.timer_ads[-1] = 0

        surplus_kw = max(0.0, power_budget_kw - rigid_kw)

        if self.n_saturated > 0 and surplus_kw >= self.P_HEAT_kw:
            n_new_des = min(self.n_saturated, int(surplus_kw // self.P_HEAT_kw))
            self.n_saturated -= n_new_des
            self.timer_des[-1] += n_new_des
            surplus_kw -= n_new_des * self.P_HEAT_kw

        if self.n_ready > 0 and surplus_kw >= self.P_FAN_kw:
            n_new_ads = min(self.n_ready, int(surplus_kw // self.P_FAN_kw))
            self.n_ready -= n_new_ads
            self.timer_ads[-1] += n_new_ads

        active_ads = self.timer_ads.sum()
        active_des = self.timer_des.sum()

        total_kw = active_des * self.P_HEAT_kw + active_ads * self.P_FAN_kw
        co2_prod_mol_min = active_des * self.CO2_RATE_PER_UNIT_mol_min
        return total_kw, co2_prod_mol_min

    def _co2_compressor_kw(self, co2_rate_mol_min: float) -> float:
        R = 8.314
        T_in = 298.15
        k = 1.28
        eta_is = 0.75
        eta_mech = 0.95
        P_in = 1.0
        P_out = 30.0
        n_stage = 3

        pr_stage = (P_out / P_in) ** (1.0 / n_stage)
        term1 = n_stage * (k / (k - 1.0)) * R * T_in
        term2 = pr_stage ** ((k - 1.0) / k) - 1.0
        w_specific_j_mol = (term1 * term2) / (eta_is * eta_mech)

        mol_s = co2_rate_mol_min / 60.0
        power_w = mol_s * w_specific_j_mol
        return power_w / 1000.0

    def _pem_electrolyzer(self, power_set_kw: float):
        HHV_H2_J_mol = 286000.0
        power_kw = min(power_set_kw, self.pem_capacity_kw * self.pem_max_load)
        plr = power_kw / max(1e-6, self.pem_capacity_kw)

        if plr < self.pem_min_load:
            return 0.0, 0.0

        eta = -0.15 * (plr**2) + 0.05 * plr + 0.75
        mol_s = (power_kw * 1000.0 * eta) / HHV_H2_J_mol
        mol_min = mol_s * 60.0
        return power_kw, mol_min

    def _methanol_surrogate_predict(self, feed_co2_mol_s: float, h2_co2_ratio: float):
        if not self.surrogate_available:
            return 0.0, 0.0

        x_dict = {
            "Feed_CO2_mol_s": feed_co2_mol_s,
            "Feed_Ratio_H2_CO2": h2_co2_ratio,
        }
        x = np.array([x_dict.get(col, 0.0) for col in self.input_cols], dtype=np.float32)
        x_scaled = (x - self.X_mean) / self.X_std
        x_t = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            y_scaled = self.methanol_model(x_t).cpu().numpy().squeeze(0)

        y = y_scaled * self.Y_std + self.Y_mean
        methanol_kg_h = float(y[0]) * self.methanol_scale
        comp_kw = float(y[1]) * self.methanol_scale

        return max(0.0, methanol_kg_h), max(0.0, comp_kw)

    def _build_info(self, methanol_kg_h, grid_kw, curtail_kw, pem_kw, dac_kw, methanol_kw):
        return {
            "methanol_kg_h": float(methanol_kg_h),
            "grid_kw": float(grid_kw),
            "curtail_kw": float(curtail_kw),
            "pem_kw": float(pem_kw),
            "dac_kw": float(dac_kw),
            "methanol_kw": float(methanol_kw),
            "soc": float(self.soc),
            "tank_co2_ratio": float(
                self.tank_co2_mol / max(1e-6, self.tank_co2_capacity_mol)
            ),
            "tank_h2_ratio": float(
                self.tank_h2_mol / max(1e-6, self.tank_h2_capacity_mol)
            ),
        }

    def get_episode_summary(self):
        curtail_rate = self.annual_curtail_kwh / max(1e-6, self.annual_pv_kwh)
        return {
            "annual_methanol_kg": float(self.annual_methanol_kg),
            "annual_grid_kwh": float(self.annual_grid_kwh),
            "annual_curtail_kwh": float(self.annual_curtail_kwh),
            "annual_pv_kwh": float(self.annual_pv_kwh),
            "curtail_rate": float(curtail_rate),
            "annual_revenue": float(self.annual_revenue),
            "annual_grid_cost": float(self.annual_grid_cost),
        }

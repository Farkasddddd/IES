from dataclasses import asdict, dataclass
import random

from metrics.capacity_objectives import CapacityConfig


PV_BASE_KW = 1000.0


@dataclass(frozen=True)
class SizingDecision:
    pv_scale: float
    pem_capacity_kw: float
    n_dac: int
    battery_capacity_kwh: float
    co2_tank_capacity_mol: float
    h2_tank_capacity_mol: float

    def to_capacity_config(self) -> CapacityConfig:
        return CapacityConfig(
            pv_kw=PV_BASE_KW * self.pv_scale,
            n_dac=int(self.n_dac),
            pem_kw=float(self.pem_capacity_kw),
            battery_kwh=float(self.battery_capacity_kwh),
            co2_tank_capacity_mol=float(self.co2_tank_capacity_mol),
            h2_tank_capacity_mol=float(self.h2_tank_capacity_mol),
        )

    def to_env_kwargs(self) -> dict:
        return {
            "pv_scale": float(self.pv_scale),
            "pem_capacity_kw": float(self.pem_capacity_kw),
            "n_dac": int(self.n_dac),
            "battery_capacity_kwh": float(self.battery_capacity_kwh),
            "tank_co2_capacity_mol": float(self.co2_tank_capacity_mol),
            "tank_h2_capacity_mol": float(self.h2_tank_capacity_mol),
        }

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CapacitySearchSpace:
    pv_scale_choices: tuple[float, ...] = (0.6, 0.8, 1.0, 1.2, 1.5)
    pem_capacity_kw_choices: tuple[float, ...] = (200.0, 300.0, 400.0, 500.0, 700.0)
    n_dac_choices: tuple[int, ...] = (300, 450, 600, 750, 900)
    battery_capacity_kwh_choices: tuple[float, ...] = (1000.0, 1500.0, 2000.0, 3000.0, 4000.0)
    co2_tank_capacity_mol_choices: tuple[float, ...] = (30000.0, 50000.0, 70000.0, 100000.0)
    h2_tank_capacity_mol_choices: tuple[float, ...] = (80000.0, 120000.0, 150000.0, 200000.0, 250000.0)

    def sample(self, rng: random.Random) -> SizingDecision:
        return SizingDecision(
            pv_scale=rng.choice(self.pv_scale_choices),
            pem_capacity_kw=rng.choice(self.pem_capacity_kw_choices),
            n_dac=rng.choice(self.n_dac_choices),
            battery_capacity_kwh=rng.choice(self.battery_capacity_kwh_choices),
            co2_tank_capacity_mol=rng.choice(self.co2_tank_capacity_mol_choices),
            h2_tank_capacity_mol=rng.choice(self.h2_tank_capacity_mol_choices),
        )

    @staticmethod
    def _neighbor_choices(value, choices: tuple, radius: int = 1) -> tuple:
        idx = choices.index(value)
        low = max(0, idx - radius)
        high = min(len(choices), idx + radius + 1)
        return choices[low:high]

    def local_choice_map(self, decision: SizingDecision, radius: int = 1) -> dict:
        return {
            "pv_scale": self._neighbor_choices(decision.pv_scale, self.pv_scale_choices, radius=radius),
            "pem_capacity_kw": self._neighbor_choices(
                decision.pem_capacity_kw,
                self.pem_capacity_kw_choices,
                radius=radius,
            ),
            "n_dac": self._neighbor_choices(decision.n_dac, self.n_dac_choices, radius=radius),
            "battery_capacity_kwh": self._neighbor_choices(
                decision.battery_capacity_kwh,
                self.battery_capacity_kwh_choices,
                radius=radius,
            ),
            "co2_tank_capacity_mol": self._neighbor_choices(
                decision.co2_tank_capacity_mol,
                self.co2_tank_capacity_mol_choices,
                radius=radius,
            ),
            "h2_tank_capacity_mol": self._neighbor_choices(
                decision.h2_tank_capacity_mol,
                self.h2_tank_capacity_mol_choices,
                radius=radius,
            ),
        }


DEFAULT_SEARCH_SPACE = CapacitySearchSpace()

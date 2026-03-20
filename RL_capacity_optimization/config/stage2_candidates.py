from dataclasses import asdict, dataclass


PV_BASE_KW = 1000.0


@dataclass(frozen=True)
class Stage2Candidate:
    candidate_id: str
    label: str
    source_run_id: str
    rationale: str
    pv_kw: float
    n_dac: int
    pem_kw: float
    battery_kwh: float
    co2_tank_capacity_mol: float
    h2_tank_capacity_mol: float
    transfer_risk: str

    @property
    def pv_scale(self) -> float:
        return self.pv_kw / PV_BASE_KW

    def to_env_kwargs(self) -> dict:
        return {
            "pv_scale": float(self.pv_scale),
            "pem_capacity_kw": float(self.pem_kw),
            "n_dac": int(self.n_dac),
            "battery_capacity_kwh": float(self.battery_kwh),
            "tank_co2_capacity_mol": float(self.co2_tank_capacity_mol),
            "tank_h2_capacity_mol": float(self.h2_tank_capacity_mol),
        }

    def to_dict(self) -> dict:
        data = asdict(self)
        data["pv_scale"] = self.pv_scale
        return data


STAGE2_CANDIDATES = {
    "m1_profit_medium": Stage2Candidate(
        candidate_id="m1_profit_medium",
        label="Medium-risk shortlist profit leader",
        source_run_id="local_search_20260319_220946",
        rationale="Highest green-base annual profit among medium transfer-risk candidates in the latest local shortlist.",
        pv_kw=800.0,
        n_dac=300,
        pem_kw=400.0,
        battery_kwh=1000.0,
        co2_tank_capacity_mol=50000.0,
        h2_tank_capacity_mol=80000.0,
        transfer_risk="medium",
    ),
    "m2_profit_medium": Stage2Candidate(
        candidate_id="m2_profit_medium",
        label="Medium-risk balanced shortlist candidate",
        source_run_id="local_search_20260319_220946",
        rationale="Second-best green-base annual profit among medium transfer-risk candidates, with larger H2 storage than m1.",
        pv_kw=800.0,
        n_dac=300,
        pem_kw=300.0,
        battery_kwh=1000.0,
        co2_tank_capacity_mol=50000.0,
        h2_tank_capacity_mol=150000.0,
        transfer_risk="medium",
    ),
    "m3_profit_medium": Stage2Candidate(
        candidate_id="m3_profit_medium",
        label="Reference-nearer medium-risk candidate",
        source_run_id="local_search_20260319_220946",
        rationale="Positive-profit medium-risk candidate with reference PV scale and enlarged CO2 tank.",
        pv_kw=1000.0,
        n_dac=300,
        pem_kw=400.0,
        battery_kwh=1000.0,
        co2_tank_capacity_mol=70000.0,
        h2_tank_capacity_mol=80000.0,
        transfer_risk="medium",
    ),
    "h1_profit_high": Stage2Candidate(
        candidate_id="h1_profit_high",
        label="High-profit exploratory high-risk candidate",
        source_run_id="local_search_20260319_220946",
        rationale="Best raw green-base annual profit in the latest local search, retained as an exploratory benchmark.",
        pv_kw=800.0,
        n_dac=300,
        pem_kw=200.0,
        battery_kwh=1000.0,
        co2_tank_capacity_mol=70000.0,
        h2_tank_capacity_mol=120000.0,
        transfer_risk="high",
    ),
    "h2_storage_high": Stage2Candidate(
        candidate_id="h2_storage_high",
        label="High-risk enlarged-CO2-storage candidate",
        source_run_id="local_search_20260319_220946",
        rationale="High-risk profitable local-search candidate with larger CO2 tank and battery than the medium-risk shortlist leaders.",
        pv_kw=800.0,
        n_dac=300,
        pem_kw=300.0,
        battery_kwh=1500.0,
        co2_tank_capacity_mol=100000.0,
        h2_tank_capacity_mol=80000.0,
        transfer_risk="high",
    ),
    "h3_pv_upscale_high": Stage2Candidate(
        candidate_id="h3_pv_upscale_high",
        label="High-risk PV-upscaled candidate",
        source_run_id="random_search_20260319_215805",
        rationale="Best raw profit candidate from the archived global random search, with higher PV scale and larger CO2 storage.",
        pv_kw=1200.0,
        n_dac=300,
        pem_kw=200.0,
        battery_kwh=1000.0,
        co2_tank_capacity_mol=100000.0,
        h2_tank_capacity_mol=80000.0,
        transfer_risk="high",
    ),
}


DEFAULT_STAGE2_CANDIDATE_ID = "m1_profit_medium"

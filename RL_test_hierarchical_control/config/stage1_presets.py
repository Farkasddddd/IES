import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from ies_shared.stage1_config import (
    Stage1Config,
    coerce_stage1_config,
    combo_scan_configs,
    load_config_file,
    single_factor_scan_configs,
    stage1_baseline_config,
)


PRESET_CONFIGS = {
    "shanghai_baseline": stage1_baseline_config(),
}

DEFAULT_CONDITIONED_POOL_PATH = os.path.join(PROJECT_ROOT, "config", "stage4_conditioned_pool.json")


def get_stage1_config(config_name: str = "shanghai_baseline", config_path: str | None = None) -> Stage1Config:
    if config_path:
        return coerce_stage1_config(load_config_file(config_path))
    if config_name not in PRESET_CONFIGS:
        raise KeyError(f"Unknown config preset: {config_name}")
    return PRESET_CONFIGS[config_name]


def get_single_factor_scans() -> dict[str, list[Stage1Config]]:
    return single_factor_scan_configs()


def get_combo_scan_configs() -> list[Stage1Config]:
    return combo_scan_configs()


def get_capacity_conditioned_pool(pool_path: str | None = None) -> tuple[list[str], list[Stage1Config], str]:
    resolved_path = pool_path or DEFAULT_CONDITIONED_POOL_PATH
    payload = load_config_file(resolved_path)
    sample_mode = str(payload.get("sample_mode", "random"))
    entries = payload.get("configs", [])
    labels: list[str] = []
    configs: list[Stage1Config] = []
    for idx, entry in enumerate(entries):
        label = str(entry.get("label", f"config_{idx:02d}"))
        config_payload = entry.get("config", entry)
        labels.append(label)
        configs.append(coerce_stage1_config(config_payload))
    if not configs:
        raise ValueError(f"No conditioned configs found in pool file: {resolved_path}")
    return labels, configs, sample_mode

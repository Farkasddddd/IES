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

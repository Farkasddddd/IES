import json
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
from gymnasium.wrappers import RescaleAction
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from env.ies_bilevel_env_hierarchical import IESBilevelEnv
from env.capacity_conditioned_stage1_env import CapacityConditionedStage1Env


def resolve_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def build_stage1_env(
    *,
    pv_data_path: str,
    surrogate_path: str,
    config,
    episode_horizon: int,
    random_start: bool,
    safety_profile: str = "baseline",
    symmetric_actions: bool = True,
    monitor_dir: str | None = None,
    seed: int | None = None,
):
    raw_env = IESBilevelEnv(
        pv_data_path=pv_data_path,
        surrogate_path=surrogate_path,
        config=config,
        interface_mode="stage1",
        episode_horizon=episode_horizon,
        random_start=random_start,
        safety_profile=safety_profile,
    )
    if seed is not None:
        raw_env.reset(seed=seed)

    wrapped_env = raw_env
    if symmetric_actions:
        wrapped_env = RescaleAction(wrapped_env, min_action=-1.0, max_action=1.0)
    if monitor_dir is not None:
        wrapped_env = Monitor(wrapped_env, monitor_dir)
    return raw_env, wrapped_env


def build_conditioned_stage1_env(
    *,
    pv_data_path: str,
    surrogate_path: str,
    config_labels,
    config_pool,
    episode_horizon: int,
    random_start: bool,
    safety_profile: str = "baseline",
    sample_mode: str = "random",
    symmetric_actions: bool = True,
    monitor_dir: str | None = None,
    seed: int | None = None,
):
    raw_env = CapacityConditionedStage1Env(
        pv_data_path=pv_data_path,
        surrogate_path=surrogate_path,
        config_pool=config_pool,
        config_labels=config_labels,
        episode_horizon=episode_horizon,
        random_start=random_start,
        safety_profile=safety_profile,
        sample_mode=sample_mode,
    )
    if seed is not None:
        raw_env.reset(seed=seed)

    wrapped_env = raw_env
    if symmetric_actions:
        wrapped_env = RescaleAction(wrapped_env, min_action=-1.0, max_action=1.0)
    if monitor_dir is not None:
        wrapped_env = Monitor(wrapped_env, monitor_dir)
    return raw_env, wrapped_env


def build_checkpoint_callback(run_dir: str, save_freq: int) -> CheckpointCallback:
    checkpoint_dir = os.path.join(run_dir, "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)
    return CheckpointCallback(
        save_freq=max(1, save_freq),
        save_path=checkpoint_dir,
        name_prefix="policy_stage1_standardized",
        save_replay_buffer=False,
        save_vecnormalize=False,
    )


def write_json(path: str, payload: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

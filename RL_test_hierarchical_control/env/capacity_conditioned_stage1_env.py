from __future__ import annotations

from typing import Any, Mapping

import gymnasium as gym
import numpy as np

from ies_shared.stage1_config import Stage1Config, coerce_stage1_config, config_to_dict

from .ies_bilevel_env_hierarchical import IESBilevelEnv


class CapacityConditionedStage1Env(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        pv_data_path: str,
        surrogate_path: str,
        config_pool: list[Stage1Config | Mapping[str, Any]],
        config_labels: list[str] | None = None,
        economic_config: Mapping[str, Any] | None = None,
        episode_horizon: int = 168,
        random_start: bool = True,
        safety_profile: str = "baseline",
        sample_mode: str = "random",
    ):
        super().__init__()
        if not config_pool:
            raise ValueError("config_pool must contain at least one configuration.")

        self.pv_data_path = pv_data_path
        self.surrogate_path = surrogate_path
        self.config_pool = [coerce_stage1_config(config) for config in config_pool]
        self.config_labels = config_labels or [f"config_{idx:02d}" for idx in range(len(self.config_pool))]
        if len(self.config_labels) != len(self.config_pool):
            raise ValueError("config_labels length must match config_pool length.")

        self.economic_config = economic_config
        self.episode_horizon = int(episode_horizon)
        self.random_start = bool(random_start)
        self.safety_profile = str(safety_profile)
        self.sample_mode = str(sample_mode)
        self.current_config_index = 0
        self.episode_count = 0

        self._raw_env = self._build_raw_env(self.current_config_index)
        self.action_space = self._raw_env.action_space
        self.observation_space = self._raw_env.observation_space
        self.last_info: dict[str, Any] | None = None

    def _build_raw_env(self, config_index: int) -> IESBilevelEnv:
        config = self.config_pool[config_index]
        return IESBilevelEnv(
            pv_data_path=self.pv_data_path,
            surrogate_path=self.surrogate_path,
            config=config,
            economic_config=self.economic_config,
            interface_mode="stage1",
            episode_horizon=self.episode_horizon,
            random_start=self.random_start,
            safety_profile=self.safety_profile,
        )

    def _next_config_index(self) -> int:
        if self.sample_mode == "cycle":
            return int(self.episode_count % len(self.config_pool))
        if self.sample_mode == "fixed":
            return 0
        return int(self.np_random.integers(0, len(self.config_pool)))

    def describe_pool(self) -> dict[str, Any]:
        return {
            "sample_mode": self.sample_mode,
            "pool_size": len(self.config_pool),
            "configs": [
                {
                    "label": label,
                    "config": config_to_dict(config),
                }
                for label, config in zip(self.config_labels, self.config_pool)
            ],
        }

    def describe_current_config(self) -> dict[str, Any]:
        description = self._raw_env.describe_config()
        description["pool_label"] = self.config_labels[self.current_config_index]
        description["pool_index"] = self.current_config_index
        description["pool_size"] = len(self.config_pool)
        return description

    def reset(self, *, seed: int | None = None, options: Mapping[str, Any] | None = None):
        super().reset(seed=seed)
        options = dict(options or {})
        requested_index = options.get("config_index")
        if requested_index is None:
            config_index = self._next_config_index()
        else:
            config_index = int(requested_index)
        config_index = max(0, min(config_index, len(self.config_pool) - 1))

        self.current_config_index = config_index
        self._raw_env = self._build_raw_env(config_index)
        obs, info = self._raw_env.reset(seed=seed)
        info = dict(info)
        info["conditioned_config_index"] = self.current_config_index
        info["conditioned_config_label"] = self.config_labels[self.current_config_index]
        self.last_info = info
        self.episode_count += 1
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self._raw_env.step(action)
        info = dict(info)
        info["conditioned_config_index"] = self.current_config_index
        info["conditioned_config_label"] = self.config_labels[self.current_config_index]
        self.last_info = info
        return obs, reward, terminated, truncated, info

    def render(self):
        return None

    def close(self):
        if self._raw_env is not None:
            self._raw_env.close()

import argparse
from datetime import datetime
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
from stable_baselines3 import SAC
from stable_baselines3.common.env_checker import check_env


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage4_conditioned")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from config.stage1_presets import get_capacity_conditioned_pool
from train.stage1_runtime import (
    build_checkpoint_callback,
    build_conditioned_stage1_env,
    resolve_device,
    write_json,
)


def main():
    parser = argparse.ArgumentParser(description="Train a capacity-conditioned SAC policy on the standardized stage-1 interface.")
    parser.add_argument("--pool-path", type=str, default=None)
    parser.add_argument("--run-tag", type=str, default="conditioned_pool")
    parser.add_argument("--init-model-path", type=str, default=None)
    parser.add_argument("--timesteps", type=int, default=60_000)
    parser.add_argument("--episode-horizon", type=int, default=168)
    parser.add_argument("--seed", type=int, default=20260320)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--save-freq", type=int, default=5000)
    parser.add_argument("--safety-profile", type=str, default="h2_guard_v1")
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-starts", type=int, default=1000)
    parser.add_argument("--symmetric-actions", action="store_true", default=True)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    args = parser.parse_args()

    config_labels, config_pool, sample_mode = get_capacity_conditioned_pool(args.pool_path)
    run_id = f"stage4_conditioned_{args.run_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = os.path.join(RESULTS_DIR, "training_runs", run_id)
    os.makedirs(os.path.join(run_dir, "models"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "tensorboard"), exist_ok=True)

    raw_env, env = build_conditioned_stage1_env(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        config_labels=config_labels,
        config_pool=config_pool,
        episode_horizon=args.episode_horizon,
        random_start=True,
        safety_profile=args.safety_profile,
        sample_mode=sample_mode,
        symmetric_actions=args.symmetric_actions,
        monitor_dir=run_dir,
        seed=args.seed,
    )
    check_env(env, warn=True)
    device = resolve_device(args.device)
    tensorboard_dir = os.path.join(run_dir, "tensorboard")

    if args.init_model_path:
        model = SAC.load(args.init_model_path, env=env, device=device)
        model.tensorboard_log = tensorboard_dir
        model.verbose = 1
        training_mode = "finetune_capacity_conditioned"
        reset_num_timesteps = False
    else:
        model = SAC(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=args.learning_rate,
            batch_size=args.batch_size,
            learning_starts=args.learning_starts,
            seed=args.seed,
            device=device,
            tensorboard_log=tensorboard_dir,
        )
        training_mode = "scratch_capacity_conditioned"
        reset_num_timesteps = True
    checkpoint_callback = build_checkpoint_callback(run_dir=run_dir, save_freq=args.save_freq)
    model.learn(
        total_timesteps=args.timesteps,
        progress_bar=True,
        callback=checkpoint_callback,
        reset_num_timesteps=reset_num_timesteps,
    )

    model_path = os.path.join(run_dir, "models", "policy_capacity_conditioned_stage1")
    model.save(model_path)

    metadata = {
        "run_id": run_id,
        "run_tag": args.run_tag,
        "pool_path": args.pool_path,
        "sample_mode": sample_mode,
        "pool_size": len(config_pool),
        "config_pool": raw_env.describe_pool()["configs"],
        "timesteps": args.timesteps,
        "episode_horizon": args.episode_horizon,
        "seed": args.seed,
        "interface_mode": "stage1",
        "training_mode": training_mode,
        "init_model_path": args.init_model_path,
        "safety_profile": args.safety_profile,
        "device_requested": args.device,
        "device_resolved": device,
        "torch_cuda_available": torch.cuda.is_available(),
        "symmetric_actions": args.symmetric_actions,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "learning_starts": args.learning_starts,
        "checkpoint_dir": os.path.join(run_dir, "checkpoints"),
        "checkpoint_freq": args.save_freq,
        "saved_model": model_path + ".zip",
    }
    write_json(os.path.join(run_dir, "run_metadata.json"), metadata)

    latest_dir = os.path.join(RESULTS_DIR, "latest_model")
    os.makedirs(latest_dir, exist_ok=True)
    write_json(os.path.join(latest_dir, "latest_capacity_conditioned_model.json"), metadata)

    print(f"run_dir={run_dir}")
    print(f"saved_model={model_path}.zip")
    print(f"device={device}")


if __name__ == "__main__":
    main()

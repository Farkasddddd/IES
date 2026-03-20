import argparse
from datetime import datetime
import json
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from stable_baselines3 import SAC
from stable_baselines3.common.monitor import Monitor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
MODELS_DIR = os.path.join(RESULTS_DIR, "models")
STAGE2_RUNS_DIR = os.path.join(RESULTS_DIR, "stage2_runs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.stage2_candidates import DEFAULT_STAGE2_CANDIDATE_ID, STAGE2_CANDIDATES
from env.ies_capacity_env import IESBilevelEnv


REFERENCE_MODEL_NAME = "sac_hierarchical_reference"


def main():
    parser = argparse.ArgumentParser(description="Stage-2 policy fine-tuning for a fixed shortlisted capacity configuration.")
    parser.add_argument("--candidate-id", type=str, default=DEFAULT_STAGE2_CANDIDATE_ID)
    parser.add_argument("--timesteps", type=int, default=60_000)
    parser.add_argument("--seed", type=int, default=20260319)
    parser.add_argument("--episode-horizon", type=int, default=168)
    args = parser.parse_args()

    if args.candidate_id not in STAGE2_CANDIDATES:
        raise KeyError(f"Unknown candidate_id: {args.candidate_id}")

    candidate = STAGE2_CANDIDATES[args.candidate_id]

    os.makedirs(STAGE2_RUNS_DIR, exist_ok=True)
    run_id = f"stage2_finetune_{candidate.candidate_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = os.path.join(STAGE2_RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.join(run_dir, "models"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "tensorboard"), exist_ok=True)

    env = IESBilevelEnv(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        dt_hours=1.0,
        episode_horizon=args.episode_horizon,
        random_start=True,
        **candidate.to_env_kwargs(),
    )
    env.reset(seed=args.seed)
    env = Monitor(env, run_dir)

    reference_model_path = os.path.join(MODELS_DIR, REFERENCE_MODEL_NAME)
    model = SAC.load(
        reference_model_path,
        env=env,
        tensorboard_log=os.path.join(run_dir, "tensorboard"),
        seed=args.seed,
    )

    metadata = {
        "run_id": run_id,
        "run_type": "stage2_policy_finetune",
        "timestamp_local": datetime.now().isoformat(),
        "candidate": candidate.to_dict(),
        "reference_model_name": REFERENCE_MODEL_NAME,
        "timesteps": args.timesteps,
        "seed": args.seed,
        "episode_horizon": args.episode_horizon,
        "random_start": True,
        "goal": "Fine-tune the hierarchical dispatch policy for a fixed shortlisted capacity configuration.",
    }

    metadata_path = os.path.join(run_dir, "run_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    model.learn(
        total_timesteps=args.timesteps,
        reset_num_timesteps=False,
        progress_bar=True,
        tb_log_name=run_id,
    )

    model_path = os.path.join(run_dir, "models", "policy_finetuned")
    model.save(model_path)

    summary_lines = [
        f"# Stage-2 Fine-Tune {run_id}",
        "",
        "## Setup",
        "",
        f"- candidate_id: {candidate.candidate_id}",
        f"- label: {candidate.label}",
        f"- source run: {candidate.source_run_id}",
        f"- transfer risk: {candidate.transfer_risk}",
        f"- timesteps: {args.timesteps}",
        f"- episode horizon: {args.episode_horizon} h",
        f"- seed: {args.seed}",
        f"- reference model: {REFERENCE_MODEL_NAME}",
        f"- saved model: {model_path}.zip",
        "",
        "## Fixed Capacity",
        "",
        f"- config: {candidate.to_dict()}",
    ]

    summary_path = os.path.join(run_dir, "training_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    latest_metadata = os.path.join(RESULTS_DIR, "stage2_latest_finetune_metadata.json")
    latest_summary = os.path.join(RESULTS_DIR, "stage2_latest_finetune_summary.md")
    with open(latest_metadata, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    with open(latest_summary, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    print(f"run_dir={run_dir}")
    print(f"saved_model={model_path}.zip")
    print(f"saved_metadata={metadata_path}")
    print(f"saved_summary={summary_path}")


if __name__ == "__main__":
    main()

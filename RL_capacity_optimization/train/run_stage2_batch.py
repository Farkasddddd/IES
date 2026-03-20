import argparse
from datetime import datetime
import json
import os
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
STAGE2_RUNS_DIR = os.path.join(RESULTS_DIR, "stage2_runs")
PYTHON_EXE = sys.executable

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.stage2_candidates import STAGE2_CANDIDATES


DEFAULT_BATCH_ORDER = [
    "m1_profit_medium",
    "m2_profit_medium",
    "m3_profit_medium",
    "h1_profit_high",
    "h2_storage_high",
    "h3_pv_upscale_high",
]


def find_latest_completed_run(candidate_id: str) -> str | None:
    if not os.path.isdir(STAGE2_RUNS_DIR):
        return None
    matches = [
        name
        for name in os.listdir(STAGE2_RUNS_DIR)
        if name.startswith(f"stage2_finetune_{candidate_id}_")
        and os.path.exists(os.path.join(STAGE2_RUNS_DIR, name, "annual_eval_summary.json"))
    ]
    if not matches:
        return None
    matches.sort()
    return os.path.join(STAGE2_RUNS_DIR, matches[-1])


def run_subprocess(cmd: list[str]):
    completed = subprocess.run(cmd, check=True)
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description="Run stage-2 fine-tuning and annual evaluation for all selected candidates.")
    parser.add_argument("--timesteps", type=int, default=60_000)
    parser.add_argument("--seed", type=int, default=20260319)
    parser.add_argument("--episode-horizon", type=int, default=168)
    parser.add_argument("--skip-completed", action="store_true", help="Skip candidates with an existing completed annual evaluation.")
    args = parser.parse_args()

    os.makedirs(STAGE2_RUNS_DIR, exist_ok=True)
    batch_id = f"stage2_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    batch_dir = os.path.join(STAGE2_RUNS_DIR, batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    batch_meta = {
        "batch_id": batch_id,
        "timestamp_local": datetime.now().isoformat(),
        "candidate_ids": DEFAULT_BATCH_ORDER,
        "timesteps": args.timesteps,
        "seed": args.seed,
        "episode_horizon": args.episode_horizon,
        "skip_completed": args.skip_completed,
    }
    with open(os.path.join(batch_dir, "batch_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(batch_meta, f, ensure_ascii=False, indent=2)

    executed = []
    for candidate_id in DEFAULT_BATCH_ORDER:
        if candidate_id not in STAGE2_CANDIDATES:
            continue

        existing = find_latest_completed_run(candidate_id)
        if args.skip_completed and existing is not None:
            print(f"[skip] {candidate_id} -> {existing}")
            executed.append({"candidate_id": candidate_id, "status": "skipped_completed", "run_dir": existing})
            continue

        finetune_cmd = [
            PYTHON_EXE,
            os.path.join(PROJECT_ROOT, "train", "finetune_stage2_candidate.py"),
            "--candidate-id",
            candidate_id,
            "--timesteps",
            str(args.timesteps),
            "--seed",
            str(args.seed),
            "--episode-horizon",
            str(args.episode_horizon),
        ]
        run_subprocess(finetune_cmd)

        latest_run = find_latest_completed_run(candidate_id)
        if latest_run is None:
            candidate_prefix = f"stage2_finetune_{candidate_id}_"
            runs = [name for name in os.listdir(STAGE2_RUNS_DIR) if name.startswith(candidate_prefix)]
            runs.sort()
            if not runs:
                raise RuntimeError(f"Could not find stage2 run for {candidate_id}")
            latest_run = os.path.join(STAGE2_RUNS_DIR, runs[-1])

        eval_cmd = [
            PYTHON_EXE,
            os.path.join(PROJECT_ROOT, "train", "evaluate_stage2_candidate.py"),
            "--candidate-id",
            candidate_id,
            "--run-dir",
            latest_run,
        ]
        run_subprocess(eval_cmd)

        executed.append({"candidate_id": candidate_id, "status": "completed", "run_dir": latest_run})

    with open(os.path.join(batch_dir, "batch_execution_log.json"), "w", encoding="utf-8") as f:
        json.dump(executed, f, ensure_ascii=False, indent=2)

    print(f"batch_dir={batch_dir}")
    print(f"completed={len([item for item in executed if item['status'] == 'completed'])}")
    print(f"skipped={len([item for item in executed if item['status'] == 'skipped_completed'])}")


if __name__ == "__main__":
    main()

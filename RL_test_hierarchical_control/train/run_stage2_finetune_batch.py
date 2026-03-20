import argparse
import csv
from datetime import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage1")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from train.stage1_runtime import write_json


PHASE_DEFAULTS = {
    "screen": 2_000,
    "promote": 10_000,
    "final": 60_000,
}


def _python_executable(explicit: str | None) -> str:
    return explicit or sys.executable


def _config_files(config_dir: str) -> list[Path]:
    return sorted(Path(config_dir).glob("*.json"))


def _run_command(command: list[str], workdir: str) -> dict[str, str]:
    completed = subprocess.run(
        command,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def _load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten(record: dict) -> dict:
    summary = record["evaluation_summary"]
    perf = summary["performance_metrics"]
    strategy = summary["strategy_metrics"]
    physics = summary["physics_metrics"]
    row = {
        "config_key": record["config_key"],
        "phase": record["phase"],
        "config_path": record["config_path"],
        "train_run_dir": record["train_run_dir"],
        "eval_run_dir": record["eval_run_dir"],
        "init_model_path": record["init_model_path"],
        "timesteps": record["timesteps"],
    }
    row.update(summary["config"])
    row.update(perf)
    row.update(strategy)
    row.update(physics)
    return row


def _flush(output_dir: str, rows: list[dict], manifest: dict):
    csv_path = os.path.join(output_dir, "batch_summary.csv")
    json_path = os.path.join(output_dir, "batch_summary.json")
    md_path = os.path.join(output_dir, "batch_summary.md")
    manifest_path = os.path.join(output_dir, "batch_manifest.json")
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        write_json(json_path, rows)
        best_lcom = min(rows, key=lambda x: (x["h2_inventory_violation_count"], x["lcom_yuan_per_kg"]))
        best_methanol = max(rows, key=lambda x: x["annual_methanol_kg"])
        md_lines = [
            f"# {manifest['run_id']}",
            "",
            f"- phase: {manifest['phase']}",
            f"- config count completed: {len(rows)}",
            f"- best zero-violation LCOM candidate: {best_lcom['config_key']} ({best_lcom['lcom_yuan_per_kg']:.4f})",
            f"- best methanol candidate: {best_methanol['config_key']} ({best_methanol['annual_methanol_kg']:.2f} kg)",
        ]
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        manifest["saved_csv"] = csv_path
        manifest["saved_json"] = json_path
        manifest["saved_md"] = md_path
    write_json(manifest_path, manifest)


def main():
    parser = argparse.ArgumentParser(description="Batch warm-start fine-tune runner for stage2 capacity experiments.")
    parser.add_argument("--config-dir", type=str, required=True)
    parser.add_argument("--init-model-path", type=str, required=True)
    parser.add_argument("--phase", type=str, choices=sorted(PHASE_DEFAULTS.keys()), default="screen")
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--episode-horizon", type=int, default=168)
    parser.add_argument("--eval-horizon", type=int, default=8760)
    parser.add_argument("--seed", type=int, default=20260320)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--python-exe", type=str, default=None)
    parser.add_argument("--save-freq", type=int, default=1000)
    parser.add_argument("--safety-profile", type=str, default="h2_guard_v1")
    parser.add_argument("--symmetric-actions", action="store_true", default=True)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    parser.add_argument("--run-tag-prefix", type=str, default=None)
    args = parser.parse_args()

    config_files = _config_files(args.config_dir)
    if not config_files:
        raise FileNotFoundError(f"No config json files found under: {args.config_dir}")

    python_exe = _python_executable(args.python_exe)
    timesteps = int(args.timesteps or PHASE_DEFAULTS[args.phase])
    tag_prefix = args.run_tag_prefix or Path(args.config_dir).name
    run_id = f"stage2_batch_{tag_prefix}_{args.phase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, "stage_archives", run_id)
    os.makedirs(output_dir, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "phase": args.phase,
        "timesteps": timesteps,
        "config_dir": args.config_dir,
        "init_model_path": args.init_model_path,
        "episode_horizon": args.episode_horizon,
        "eval_horizon": args.eval_horizon,
        "seed": args.seed,
        "device": args.device,
        "safety_profile": args.safety_profile,
        "symmetric_actions": args.symmetric_actions,
        "configs": [str(path) for path in config_files],
        "completed": [],
    }

    rows: list[dict] = []
    _flush(output_dir, rows, manifest)

    train_script = os.path.join(PROJECT_ROOT, "train", "train_sac_stage1_standardized.py")
    eval_script = os.path.join(PROJECT_ROOT, "train", "evaluate_stage1_standardized.py")

    for config_path in config_files:
        config_key = config_path.stem
        run_tag = f"{tag_prefix}_{args.phase}_{config_key}"
        train_cmd = [
            python_exe,
            train_script,
            "--config-name",
            "shanghai_baseline",
            "--config-path",
            str(config_path),
            "--run-tag",
            run_tag,
            "--init-model-path",
            args.init_model_path,
            "--timesteps",
            str(timesteps),
            "--episode-horizon",
            str(args.episode_horizon),
            "--seed",
            str(args.seed),
            "--device",
            args.device,
            "--save-freq",
            str(args.save_freq),
            "--safety-profile",
            args.safety_profile,
            "--no-update-latest",
        ]
        train_cmd.append("--symmetric-actions" if args.symmetric_actions else "--no-symmetric-actions")
        train_out = _run_command(train_cmd, workdir=WORKSPACE_ROOT)
        train_run_dir = train_out["run_dir"]
        model_path = train_out["saved_model"][:-4] if train_out["saved_model"].endswith(".zip") else train_out["saved_model"]

        eval_cmd = [
            python_exe,
            eval_script,
            "--config-name",
            "shanghai_baseline",
            "--config-path",
            str(config_path),
            "--run-tag",
            run_tag,
            "--model-path",
            model_path,
            "--episode-horizon",
            str(args.eval_horizon),
            "--device",
            args.device,
            "--safety-profile",
            args.safety_profile,
        ]
        eval_cmd.append("--symmetric-actions" if args.symmetric_actions else "--no-symmetric-actions")
        eval_out = _run_command(eval_cmd, workdir=WORKSPACE_ROOT)
        eval_run_dir = eval_out["output_dir"]
        eval_summary = _load_json(os.path.join(eval_run_dir, "annual_eval_summary.json"))

        record = {
            "config_key": config_key,
            "phase": args.phase,
            "config_path": str(config_path),
            "init_model_path": args.init_model_path,
            "timesteps": timesteps,
            "train_run_dir": train_run_dir,
            "eval_run_dir": eval_run_dir,
            "evaluation_summary": eval_summary,
        }
        manifest["completed"].append(
            {
                "config_key": config_key,
                "config_path": str(config_path),
                "train_run_dir": train_run_dir,
                "eval_run_dir": eval_run_dir,
            }
        )
        rows.append(_flatten(record))
        _flush(output_dir, rows, manifest)
        print(f"completed={config_key}")

    print(f"output_dir={output_dir}")
    print(f"saved_csv={os.path.join(output_dir, 'batch_summary.csv')}")
    print(f"n_rows={len(rows)}")


if __name__ == "__main__":
    main()

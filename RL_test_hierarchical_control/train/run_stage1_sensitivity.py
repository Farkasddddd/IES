import argparse
import csv
from datetime import datetime
import json
import os
import sys

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from stable_baselines3 import SAC


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "stage1")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from config.stage1_presets import get_combo_scan_configs, get_single_factor_scans, get_stage1_config
from ies_shared.stage1_eval import rollout_policy
from train.stage1_runtime import build_stage1_env, resolve_device, write_json


def _latest_model_info() -> dict:
    latest_meta = os.path.join(RESULTS_DIR, "latest_model", "latest_stage1_model.json")
    if not os.path.exists(latest_meta):
        raise FileNotFoundError("No latest stage1 model metadata found.")
    with open(latest_meta, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten(group_name: str, config_name: str, summary: dict) -> dict:
    perf = summary["performance_metrics"]
    strategy = summary["strategy_metrics"]
    physics = summary["physics_metrics"]
    row = {"group_name": group_name, "config_name": config_name}
    row.update(summary["config"])
    row.update({f"physical_{k}": v for k, v in summary["physical_params"].items()})
    row.update(perf)
    row.update(strategy)
    row.update(physics)
    return row


def _evaluate_config(config, model, episode_horizon: int, symmetric_actions: bool) -> dict:
    _, env = build_stage1_env(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        config=config,
        episode_horizon=episode_horizon,
        random_start=False,
        symmetric_actions=symmetric_actions,
    )
    return rollout_policy(env=env, model=model).summary


def _flush_results(output_dir: str, results: list[dict]):
    csv_path = os.path.join(output_dir, "scan_summary.csv")
    json_path = os.path.join(output_dir, "scan_summary.json")
    if not results:
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    write_json(json_path, results)


def main():
    parser = argparse.ArgumentParser(description="Run baseline, single-factor, and small-grid stage1 sensitivity scans.")
    parser.add_argument("--model-path", type=str, default=None)
    parser.add_argument("--episode-horizon", type=int, default=8760)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--symmetric-actions", action="store_true", default=None)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    args = parser.parse_args()

    latest_info = _latest_model_info()
    latest_model_path = latest_info["saved_model"]
    latest_model_path = latest_model_path[:-4] if latest_model_path.endswith(".zip") else latest_model_path
    symmetric_actions = (
        bool(latest_info.get("symmetric_actions", True))
        if args.symmetric_actions is None
        else bool(args.symmetric_actions)
    )
    model = SAC.load(args.model_path or latest_model_path, device=resolve_device(args.device))
    run_id = f"stage1_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, "scans", run_id)
    os.makedirs(output_dir, exist_ok=True)

    results = []
    baseline = get_stage1_config()
    baseline_summary = _evaluate_config(
        baseline,
        model=model,
        episode_horizon=args.episode_horizon,
        symmetric_actions=symmetric_actions,
    )
    results.append(_flatten("baseline", "shanghai_baseline", baseline_summary))
    _flush_results(output_dir, results)

    for group_name, configs in get_single_factor_scans().items():
        for idx, config in enumerate(configs):
            results.append(
                _flatten(
                    group_name,
                    f"{group_name}_{idx}",
                    _evaluate_config(
                        config,
                        model,
                        args.episode_horizon,
                        symmetric_actions=symmetric_actions,
                    ),
                )
            )
            _flush_results(output_dir, results)

    for idx, config in enumerate(get_combo_scan_configs()):
        results.append(
            _flatten(
                "combo_grid",
                f"combo_{idx:02d}",
                _evaluate_config(
                    config,
                    model,
                    args.episode_horizon,
                    symmetric_actions=symmetric_actions,
                ),
            )
        )
        _flush_results(output_dir, results)

    csv_path = os.path.join(output_dir, "scan_summary.csv")
    json_path = os.path.join(output_dir, "scan_summary.json")
    md_path = os.path.join(output_dir, "scan_summary.md")

    md_lines = [
        f"# Stage1 Scan {run_id}",
        "",
        f"- baseline runs: 1",
        f"- single-factor runs: {sum(len(v) for v in get_single_factor_scans().values())}",
        f"- combo runs: {len(get_combo_scan_configs())}",
        "",
        "Key outputs are stored in `scan_summary.csv` and `scan_summary.json`.",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    write_json(
        os.path.join(output_dir, "scan_metadata.json"),
        {
            "run_id": run_id,
            "model_path": (args.model_path or latest_model_path) + ".zip",
            "device": resolve_device(args.device),
            "saved_csv": csv_path,
            "saved_json": json_path,
            "saved_md": md_path,
            "n_rows": len(results),
        },
    )

    print(f"output_dir={output_dir}")
    print(f"saved_csv={csv_path}")
    print(f"n_rows={len(results)}")


if __name__ == "__main__":
    main()

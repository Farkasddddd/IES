import argparse
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

from config.stage1_presets import get_stage1_config
from ies_shared.stage1_eval import rollout_policy, save_rollout_artifacts
from train.stage1_runtime import build_stage1_env, resolve_device, write_json


def _latest_model_info() -> dict:
    latest_meta = os.path.join(RESULTS_DIR, "latest_model", "latest_stage1_model.json")
    if not os.path.exists(latest_meta):
        raise FileNotFoundError("No latest stage1 model metadata found.")
    with open(latest_meta, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Evaluate the stage-1 standardized policy for a full-year rollout.")
    parser.add_argument("--config-name", type=str, default="shanghai_baseline")
    parser.add_argument("--config-path", type=str, default=None)
    parser.add_argument("--run-tag", type=str, default=None)
    parser.add_argument("--model-path", type=str, default=None)
    parser.add_argument("--episode-horizon", type=int, default=8760)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--safety-profile", type=str, default="baseline")
    parser.add_argument("--symmetric-actions", action="store_true", default=None)
    parser.add_argument("--no-symmetric-actions", action="store_false", dest="symmetric_actions")
    args = parser.parse_args()

    config = get_stage1_config(config_name=args.config_name, config_path=args.config_path)
    config_label = args.run_tag or args.config_name
    latest_info = _latest_model_info()
    latest_model_path = latest_info["saved_model"]
    latest_model_path = latest_model_path[:-4] if latest_model_path.endswith(".zip") else latest_model_path
    model_path = args.model_path or latest_model_path
    symmetric_actions = (
        bool(latest_info.get("symmetric_actions", True))
        if args.symmetric_actions is None
        else bool(args.symmetric_actions)
    )
    device = resolve_device(args.device)

    raw_env, env = build_stage1_env(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
        config=config,
        episode_horizon=args.episode_horizon,
        random_start=False,
        safety_profile=args.safety_profile,
        symmetric_actions=symmetric_actions,
    )
    model = SAC.load(model_path, device=device)
    artifacts = rollout_policy(env=env, model=model)

    run_id = f"stage1_eval_{config_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = os.path.join(RESULTS_DIR, "evaluations", run_id)
    saved = save_rollout_artifacts(artifacts=artifacts, output_dir=output_dir, prefix="annual_eval")

    write_json(
        os.path.join(output_dir, "evaluation_metadata.json"),
        {
            "run_id": run_id,
            "config_name": args.config_name,
            "config_label": config_label,
            "config_path": args.config_path,
            "model_path": model_path + ".zip",
            "device": device,
            "safety_profile": args.safety_profile,
            "symmetric_actions": symmetric_actions,
            "config": raw_env.describe_config()["config"],
            "physical_params": raw_env.describe_config()["physical_params"],
            "economic_config": raw_env.describe_config()["economic_config"],
            "saved_files": saved,
        },
    )

    perf = artifacts.summary["performance_metrics"]
    print(f"output_dir={output_dir}")
    print(f"saved_json={saved['json']}")
    print(f"annual_methanol_kg={perf['annual_methanol_kg']:.6f}")
    print(f"lcom_yuan_per_kg={perf['lcom_yuan_per_kg']:.6f}")


if __name__ == "__main__":
    main()

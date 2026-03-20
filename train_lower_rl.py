import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

from stable_baselines3 import SAC
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from ies_env_bilevel import IESBilevelEnv


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")


def build_env(config: dict):
    env = IESBilevelEnv(
        pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
        surrogate_path=os.path.join(DATA_DIR, "methanol_surrogate_bundle.pth"),
        dt_hours=config["dt_hours"],
        pv_scale=config["pv_scale"],
        pem_capacity_kw=config["pem_capacity_kw"],
        n_dac=config["n_dac"],
        tank_co2_capacity_mol=config["tank_co2_capacity_mol"],
        tank_h2_capacity_mol=config["tank_h2_capacity_mol"],
        battery_capacity_kwh=config["battery_capacity_kwh"],
        methanol_scale=config["methanol_scale"],
        grid_price_per_kwh=config["grid_price_per_kwh"],
        methanol_price_per_kg=config["methanol_price_per_kg"],
        allow_grid=config["allow_grid"],
        terminate_on_tank_violation=True,
    )
    return env


def train_once(config: dict, total_timesteps: int = 30000, model_save_name: str = None):
    raw_env = build_env(config)
    check_env(raw_env, warn=True)

    env = Monitor(raw_env)

    model = SAC(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        batch_size=256,
        tensorboard_log=os.path.join(PROJECT_ROOT, "sac_tensorboard"),
    )

    model.learn(total_timesteps=total_timesteps, progress_bar=True)

    if model_save_name is not None:
        os.makedirs(MODEL_DIR, exist_ok=True)
        model.save(os.path.join(MODEL_DIR, model_save_name))

    obs, info = env.reset()
    done = False
    total_reward = 0.0

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        done = terminated or truncated

    summary = info.get("episode_summary", {})
    summary["eval_total_reward"] = float(total_reward)
    return model, summary


if __name__ == "__main__":
    config = {
        "dt_hours": 1.0,
        "pv_scale": 1.0,
        "pem_capacity_kw": 1000.0,
        "n_dac": 10,
        "tank_co2_capacity_mol": 500.0,
        "tank_h2_capacity_mol": 1500.0,
        "battery_capacity_kwh": 2000.0,
        "methanol_scale": 1.0,
        "grid_price_per_kwh": 0.6,
        "methanol_price_per_kg": 2.5,
        "allow_grid": True,
    }

    model, summary = train_once(
        config=config,
        total_timesteps=20000,
        model_save_name="sac_ies_lower",
    )

    print("\n年度评估结果：")
    for k, v in summary.items():
        print(f"{k}: {v}")

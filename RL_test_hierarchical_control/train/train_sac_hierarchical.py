import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from stable_baselines3 import SAC
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

import sys

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from env.ies_bilevel_env_hierarchical import IESBilevelEnv


# --------------------------
# 创建文件夹
# --------------------------
os.makedirs(os.path.join(RESULTS_DIR, "models"), exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, "tensorboard"), exist_ok=True)


# --------------------------
# 初始化环境
# --------------------------
env = IESBilevelEnv(
    pv_data_path=os.path.join(DATA_DIR, "pvwatts_hourly_shanghai.csv"),
    surrogate_path=os.path.join(DATA_DIR, "methanol_mlp_model.pth"),
    dt_hours=1.0,
    pv_scale=1.0,
    pem_capacity_kw=400,
    n_dac=600,
    tank_co2_capacity_mol=50_000,
    tank_h2_capacity_mol=150_000,
    battery_capacity_kwh=2000,
    episode_horizon=168,
    random_start=True,
)
check_env(env, warn=True)
env = Monitor(env, RESULTS_DIR)


# --------------------------
# 初始化 SAC
# --------------------------
model = SAC(
    "MlpPolicy",
    env,
    verbose=1,
    learning_rate=3e-4,
    batch_size=256,
    learning_starts=1000,
    tensorboard_log=os.path.join(RESULTS_DIR, "tensorboard"),
)


# --------------------------
# 开始训练
# --------------------------
model.learn(total_timesteps=60_000, progress_bar=True)


# --------------------------
# 保存模型
# --------------------------
model.save(os.path.join(RESULTS_DIR, "models", "sac_hierarchical_v1"))

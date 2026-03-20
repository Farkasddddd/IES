import csv
import os

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
FIGURES_DIR = os.path.join(RESULTS_DIR, "figures")


def moving_average(x, window):
    if len(x) < window:
        return x.copy()
    kernel = np.ones(window, dtype=np.float64) / window
    valid = np.convolve(x, kernel, mode="valid")
    prefix = np.full(window - 1, np.nan)
    return np.concatenate([prefix, valid])


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    monitor_path = os.path.join(RESULTS_DIR, "monitor.csv")

    with open(monitor_path, newline="", encoding="utf-8") as f:
        next(f)
        rows = list(csv.DictReader(f))

    rewards = np.array([float(row["r"]) for row in rows], dtype=np.float64)
    episodes = np.arange(1, len(rewards) + 1, dtype=np.int32)
    reward_ma_10 = moving_average(rewards, 10)
    reward_ma_30 = moving_average(rewards, 30)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(14, 6), dpi=160)
    ax.plot(episodes, rewards, color="#9ecae1", linewidth=1.0, alpha=0.9, label="Episode reward")
    ax.plot(episodes, reward_ma_10, color="#3182bd", linewidth=2.0, label="Moving average (10)")
    ax.plot(episodes, reward_ma_30, color="#08519c", linewidth=2.4, label="Moving average (30)")
    ax.set_title("Hierarchical RL Training Reward")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Episode reward")
    ax.legend()
    fig.tight_layout()

    output_path = os.path.join(FIGURES_DIR, "training_reward_curve.png")
    fig.savefig(output_path)
    plt.close(fig)

    print(output_path)


if __name__ == "__main__":
    main()

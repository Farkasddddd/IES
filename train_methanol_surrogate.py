import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


class MethanolMLP(nn.Module):
    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, x):
        return self.net(x)


def standardize(x: np.ndarray):
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return (x - mean) / std, mean, std


def main():
    data_path = os.path.join(DATA_DIR, "Methanol_IES_AutoSave_Updated.xlsx")
    save_path = os.path.join(DATA_DIR, "methanol_surrogate_bundle.pth")
    meta_path = os.path.join(DATA_DIR, "methanol_surrogate_meta.json")

    df = pd.read_excel(data_path)
    print(f"读取甲醇数据成功: {df.shape[0]} 行, {df.shape[1]} 列")
    print("列名:", df.columns.tolist())

    input_cols = [
        "Feed_CO2_mol_s",
        "Feed_Ratio_H2_CO2",
    ]
    output_cols = [
        "Methanol_Production_kg_h",
        "Total_COMP_Power_kW",
    ]

    for c in input_cols + output_cols:
        if c not in df.columns:
            raise ValueError(f"缺少列: {c}")

    x_raw = df[input_cols].values.astype(np.float32)
    y_raw = df[output_cols].values.astype(np.float32)

    x_scaled, x_mean, x_std = standardize(x_raw)
    y_scaled, y_mean, y_std = standardize(y_raw)

    x_train, x_val, y_train, y_val = train_test_split(
        x_scaled, y_scaled, test_size=0.2, random_state=42
    )

    x_train_t = torch.tensor(x_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    x_val_t = torch.tensor(x_val, dtype=torch.float32)
    y_val_t = torch.tensor(y_val, dtype=torch.float32)

    model = MethanolMLP(input_dim=len(input_cols), output_dim=len(output_cols))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    patience = 100
    patience_count = 0
    epochs = 2000

    print("开始训练甲醇代理模型...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        pred = model(x_train_t)
        loss = loss_fn(pred, y_train_t)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(x_val_t)
            val_loss = loss_fn(val_pred, y_val_t).item()

        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_count = 0
        else:
            patience_count += 1

        if (epoch + 1) % 200 == 0:
            print(
                f"Epoch {epoch + 1:4d} | train_loss={loss.item():.6f} | "
                f"val_loss={val_loss:.6f}"
            )

        if patience_count >= patience:
            print(f"Early stopping at epoch {epoch + 1}")
            break

    model.load_state_dict(best_state)
    model.eval()

    with torch.no_grad():
        y_val_pred_scaled = model(x_val_t).cpu().numpy()
    y_val_pred = y_val_pred_scaled * y_std + y_mean
    y_val_true = y_val * y_std + y_mean

    print("\n验证集指标:")
    for i, col in enumerate(output_cols):
        r2 = r2_score(y_val_true[:, i], y_val_pred[:, i])
        mae = mean_absolute_error(y_val_true[:, i], y_val_pred[:, i])
        print(f"{col:>28s} | R2={r2:.5f} | MAE={mae:.5f}")

    os.makedirs(DATA_DIR, exist_ok=True)

    bundle = {
        "model_state_dict": model.state_dict(),
        "input_cols": input_cols,
        "output_cols": output_cols,
        "X_mean": x_mean,
        "X_std": x_std,
        "Y_mean": y_mean,
        "Y_std": y_std,
    }
    torch.save(bundle, save_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "input_cols": input_cols,
                "output_cols": output_cols,
                "best_val_loss": best_val,
                "n_samples": int(df.shape[0]),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n模型已保存到: {save_path}")
    print(f"元信息已保存到: {meta_path}")


if __name__ == "__main__":
    main()

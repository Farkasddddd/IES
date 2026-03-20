# 新电脑迁移说明

## 推荐 Python 版本

- 当前这台机器已经验证可用的解释器版本是 `Python 3.13.9`
- 新电脑建议优先安装 `Python 3.13.x`
- 推荐先新建独立环境，再通过 `requirements.txt` 安装依赖

## 需要复制的内容

建议直接复制整个项目根目录，而不是只复制某一个子文件夹。至少应包含：

- `RL_test_fixed_config/`
- `RL_test_hierarchical_control/`
- `RL_capacity_optimization/`
- `data/`
- `requirements.txt`
- `PROJECT_VERSION_INDEX.md`
- `SETUP_NEW_MACHINE.md`

这样可以同时保留：

- 源代码
- 已训练模型
- 阶段归档结果
- 年度评估结果

## 推荐安装步骤

### 方案 A：Conda

```powershell
conda create -n ies python=3.13 -y
conda activate ies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 方案 B：venv

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 快速校验

安装完成后，在项目根目录运行：

```powershell
python -m py_compile RL_test_hierarchical_control\train\train_sac_hierarchical.py
python -m py_compile RL_capacity_optimization\train\finetune_stage2_candidate.py
```

如果这两条能通过，说明当前训练主线至少在语法层面可用。

## 常用运行命令

### 分层调度训练

```powershell
python RL_test_hierarchical_control\train\train_sac_hierarchical.py
```

### 容量阶段 1 搜索

```powershell
python RL_capacity_optimization\train\search_capacity_random.py --n-trials 60 --seed 20260319
python RL_capacity_optimization\train\search_capacity_local.py --n-trials 60 --seed 20260319 --radius 1
```

### 容量阶段 2 微调

```powershell
python RL_capacity_optimization\train\finetune_stage2_candidate.py --candidate-id m1_profit_medium --timesteps 60000 --seed 20260319 --episode-horizon 168
python RL_capacity_optimization\train\evaluate_stage2_candidate.py --candidate-id m1_profit_medium
```

### 阶段 2 批量运行

```powershell
python RL_capacity_optimization\train\run_stage2_batch.py --timesteps 60000 --seed 20260319 --episode-horizon 168 --skip-completed
```

## 迁移时需要注意

- 现在项目脚本基本都使用项目内相对路径，因此新电脑不需要保持和旧电脑完全一致的绝对路径
- `data/` 和 `results/` 需要和代码一起复制，否则历史结果和模型无法衔接
- 如果想直接接着已有策略继续训练，别忘了把对应的 `.zip` 模型文件一起带上
- 如果新电脑因为 Python 主版本不同出现依赖兼容问题，优先先对齐到 `Python 3.13.x`

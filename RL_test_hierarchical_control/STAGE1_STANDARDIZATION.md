# 第一阶段标准化说明

## 目标

这一阶段不推翻现有分层控制范式，而是在原有可收敛版本上完成以下升级：

- 引入 `1 MW` 上海光伏参考基座
- 容量参数改为比例化配置
- 高层动作改为相对量
- observation 中加入配置态
- 年度评估输出更加完整

## 新的共享核心

标准化后的环境与评估逻辑集中在：

- `ies_shared/stage1_config.py`
- `ies_shared/stage1_env.py`
- `ies_shared/stage1_eval.py`

原有环境入口文件仍然保留原导入路径，但内部已经转发到共享实现：

- `RL_test_hierarchical_control/env/ies_bilevel_env_hierarchical.py`
- `RL_capacity_optimization/env/ies_capacity_env.py`

## 接口模式

当前支持两种接口模式：

- `legacy`
  保留旧版动作和 observation 接口，保证历史脚本和历史模型不会立刻失效。
- `stage1`
  使用新的标准化接口，包括：
  - 动作空间为 `[0, 1]^4`
  - observation 同时包含运行态、时间态、配置态和模式标记
  - `info` 中额外输出 reward breakdown 与物理诊断项

## 配置管理

项目内的第一阶段预设配置在：

- `RL_test_hierarchical_control/config/stage1_presets.py`
- `RL_test_hierarchical_control/config/baseline_stage1_shanghai.json`

当前上海基准配置为：

- `pv_ref_kw = 1000`
- `pv_scale = 1.0`
- `r_dac = 600`
- `r_pem = 0.4`
- `r_bat_e = 2.0`
- `r_bat_p = 1.0`
- `r_h2 = 45.8`
- `r_co2 = 92.6`
- `r_meoh = 1.0`
- `mode = grid`

## 常用命令

### 训练第一阶段标准化策略

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\train_sac_stage1_standardized.py --config-name shanghai_baseline --timesteps 60000 --episode-horizon 168
```

### 按 8760 小时做年度评估

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_stage1_standardized.py --config-name shanghai_baseline --episode-horizon 8760
```

### 运行基准配置、单因子扫描和小网格扫描

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\run_stage1_sensitivity.py --episode-horizon 8760
```

## 输出内容

新的年度评估结果至少包括：

- 性能指标
- 策略特征指标
- 物理可行性指标
- reward breakdown

逐时 rollout 导出中还包含：

- `pv_abs_kw`、`pv_norm`
- 动作目标比例
- 各设备负荷率
- 电池充放电
- reward 分项
- 能量和物料守恒残差
- 越界计数与限幅计数

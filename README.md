# IES Bilevel Optimization Prototype

## 项目简介

这是一个面向综合能源系统（IES）的第一版双层优化原型工程。

当前版本包含三部分：

1. 使用 Aspen 导出样本训练甲醇合成代理模型
2. 构建带光伏、PEM、电池、DAC、甲醇段的下层强化学习调度环境
3. 通过上层容量配置搜索与下层 RL 调度形成双层闭环

本项目当前目标是先把数据接口、代理模型、环境建模、强化学习训练和上层搜索流程打通，作为后续升级 NSGA-II、多目标优化和更真实机理建模的基础版本。

## 项目结构

```text
IES/
├─ data/
│  ├─ Methanol_IES_AutoSave_Updated.xlsx
│  ├─ pvwatts_hourly_shanghai.csv
│  ├─ methanol_surrogate_bundle.pth
│  └─ methanol_surrogate_meta.json
├─ models/
├─ results/
│  └─ bilevel_random_search.json
├─ sac_tensorboard/
├─ train_methanol_surrogate.py
├─ ies_env_bilevel.py
├─ train_lower_rl.py
├─ bilevel_search.py
├─ requirements.txt
└─ README.md
```

## 数据说明

### 1. 甲醇代理模型训练数据

输入文件：
`data/Methanol_IES_AutoSave_Updated.xlsx`

当前脚本使用的输入列：

- `Feed_CO2_mol_s`
- `Feed_Ratio_H2_CO2`

当前脚本使用的输出列：

- `Methanol_Production_kg_h`
- `Total_COMP_Power_kW`

### 2. PVWatts 小时级光伏数据

输入文件：
`data/pvwatts_hourly_shanghai.csv`

该文件前部包含说明行，不是纯净表格。环境代码会自动扫描真实表头，并读取：

- `AC System Output (W)`

作为小时级交流侧光伏输出功率列。

## 环境依赖

建议使用独立 Python 环境。

安装依赖：

```bash
pip install -r requirements.txt
```

等价手动安装列表：

```bash
pip install numpy pandas torch scikit-learn gymnasium stable-baselines3 openpyxl tensorboard
```

## 运行顺序

在项目根目录执行以下命令。

### 第一步：训练甲醇代理模型

```bash
python train_methanol_surrogate.py
```

输出：

- `data/methanol_surrogate_bundle.pth`
- `data/methanol_surrogate_meta.json`

### 第二步：固定容量训练下层 RL

```bash
python train_lower_rl.py
```

输出：

- 下层 SAC 训练日志
- `models/sac_ies_lower.zip`
- `sac_tensorboard/` 日志目录

### 第三步：执行上层随机搜索

```bash
python bilevel_search.py
```

输出：

- `results/bilevel_random_search.json`

## 已验证运行结果

以下结果基于本地实际执行所得。

### 1. 代理模型训练结果

样本数：
`964`

验证集指标：

- `Methanol_Production_kg_h`: `R2=0.99589`, `MAE=13.48320`
- `Total_COMP_Power_kW`: `R2=0.99830`, `MAE=1.12006`

说明：
代理模型对当前数据集拟合效果较好，可以作为第一版环境中的甲醇段替代模型。

### 2. 固定容量 RL 训练结果

`train_lower_rl.py` 默认配置下，年度评估结果为：

- `annual_methanol_kg = 187.7641`
- `annual_grid_kwh = 0.0`
- `annual_curtail_kwh = 0.0`
- `annual_pv_kwh = 1846.304349`
- `curtail_rate = 0.0`
- `annual_revenue = 469.4102`
- `annual_grid_cost = 0.0`
- `eval_total_reward = 1188.5555`

### 3. 双层随机搜索结果

当前随机搜索共评估 6 组容量配置。

按 `annual_profit` 排序的当前最优方案为：

- `pv_scale = 1.2`
- `pem_capacity_kw = 500`
- `n_dac = 15`
- `tank_co2_capacity_mol = 300`
- `tank_h2_capacity_mol = 1000`
- `battery_capacity_kwh = 500`
- `methanol_scale = 1.5`

对应结果为：

- `annual_methanol_kg = 335.5882`
- `annual_curtail_kwh = 187.5139`
- `annual_pv_kwh = 530.7124`
- `curtail_rate = 0.3533249`
- `annual_revenue = 838.9705`
- `annual_profit = -707121.0295`

结果文件位置：
`results/bilevel_random_search.json`

## 当前模型假设

### 1. 甲醇段代理模型

当前甲醇代理模型只基于两维输入：

- CO2 进料流量
- H2/CO2 比值

这是一个简化代理模型，尚未显式描述设备规模、催化剂体积、空速等缩放因素。

### 2. `methanol_scale`

当前 `methanol_scale` 是一个占位式规模参数。
它通过比例放缩甲醇产量和甲醇压缩功率，使上层优化可以先把“甲醇段规模”当作变量纳入搜索。

这不是严格的机理缩放模型，后续建议重新采样并加入：

- `Catalyst_Volume`
- `GHSV`

再训练可缩放代理模型。

### 3. DAC 量级

当前 DAC 放散 CO2 的量级与甲醇段代理模型的进料量级仍可能不匹配，因此本版结果更适合作为“流程打通验证”，不适合直接做最终经济性结论。

## 当前局限

### 1. 经济性结果暂不可信

当前所有随机搜索方案的 `annual_profit` 都为负，说明：

- 设备成本参数偏大
- 产甲醇收益偏低
- 或系统各子模块量级尚未校准一致

因此本版重点是验证双层接口和训练流程，不是给出最终设计结论。

### 2. 上层还不是正式多目标算法

当前上层使用的是随机搜索，只用于验证“上层给容量、下层回调度结果、上层接收目标值”这条链路已经跑通。

后续可升级为：

- NSGA-II
- 贝叶斯优化
- 进化算法与 RL 的嵌套联合优化

### 3. 下层训练长度仍偏短

当前 `train_lower_rl.py` 使用 `20000` timesteps，`bilevel_search.py` 中每次 trial 使用 `8000` timesteps。

这足以验证流程，但不足以说明策略已经完全收敛。

## 已处理的兼容性问题

在当前 PyTorch 版本下，加载代理模型时需要显式使用：

```python
torch.load(surrogate_path, map_location="cpu", weights_only=False)
```

否则会因默认的 `weights_only=True` 导致 bundle 中的 numpy 数据无法加载。

该兼容性修复已经写入：
`ies_env_bilevel.py`

## 建议的下一步

推荐按以下顺序继续升级：

1. 重新校准 DAC、储罐、甲醇段的物料和功率量级
2. 用带规模变量的新 Aspen 数据重训甲醇代理模型
3. 将上层随机搜索替换为 NSGA-II 多目标优化
4. 增加结果可视化，包括 Pareto 前沿、年运行曲线和容量敏感性分析

## 说明

本 README 对应的是当前第一版可运行原型。
如果后续继续扩展 NSGA-II、补充可视化或引入更严格的机理约束，建议同步更新本文件。

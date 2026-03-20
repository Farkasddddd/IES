# 统一容量条件策略说明

## 目的

这一部分对应项目的阶段 4 预备工作，目标不是立刻宣称“一个策略适配一切容量”，而是先建立一个统一训练入口，让策略能够在预先定义的容量范围内学习“看到配置后再决定行为”。

## 当前实现范围

目前只完成训练脚手架，不做大规模正式实验结论：

- 保留现有 `stage1` 标准化环境
- 每个 episode 开始时，从一个容量池里采样配置
- observation 中继续包含配置态
- 动作接口仍然沿用 `stage1`

## 默认容量池

默认训练池位于：

- `RL_test_hierarchical_control/config/stage4_conditioned_pool.json`

当前先放入一小组已经在阶段 2 和阶段 3 中验证过、有代表性的容量点：

- `baseline`
- `h2_55`
- `h2_60`
- `bat_e_30`
- `bat_e_35`

这样做的目的，是先让统一策略在“已经比较清楚的局部容量邻域”里学习，而不是一下子铺到很大的容量空间。

## 留出测试池

为了避免只在训练池里自我验证，另外准备了一组留出容量点：

- `RL_test_hierarchical_control/config/stage4_holdout_pool.json`

这些点不放入默认训练池，主要用于后续检验：

- 统一策略在邻域内插值时是否稳定
- 对未直接见过的容量点是否还能保持零越界或低越界
- 性能是否明显劣化

## 训练命令

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\train_sac_capacity_conditioned.py --timesteps 60000 --episode-horizon 168 --pool-path RL_test_hierarchical_control\config\stage4_conditioned_pool.json
```

## 评估命令

### 评估训练池内配置

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_capacity_conditioned.py --pool-path RL_test_hierarchical_control\config\stage4_conditioned_pool.json --episode-horizon 8760
```

### 评估留出容量点

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_capacity_conditioned.py --pool-path RL_test_hierarchical_control\config\stage4_holdout_pool.json --episode-horizon 8760
```

## 当前定位

这一步是工程准备，不是最终论文结论。真正要回答“统一策略是否具备有意义的容量泛化能力”，还需要后续做：

- 训练分布内测试
- 留出容量点测试
- 和单配置微调策略对比
- 策略特征随配置变化的解释分析

## 当前验证记录

当前已经完成一轮极短的冒烟训练，用来确认链路可运行：

- 运行标签：`smoke`
- 配置池大小：`5`
- 训练步数：`200`
- episode 长度：`48`
- 设备：`cuda`
- 结果目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_smoke_20260320_230202/`

这轮不用于评价策略质量，只用于确认以下内容已经打通：

- 多配置采样训练环境可正常 reset 和切换配置
- SAC 可以在该环境上正常启动训练
- 元数据、模型和 checkpoint 可以正常落盘

统一评估脚本已经补齐，后续可以直接输出：

- 训练池内配置汇总
- 留出配置汇总
- 每个配置的年度评估文件
- 汇总 `csv/json/md`

## 当前阶段结果更新

### 1. 冒烟模型双池评估

基于 `smoke` 模型，已经完成：

- 训练池内短周期评估：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_in_pool_smoke_20260320_231456/`
- 留出池短周期评估：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_holdout_smoke_20260320_231456/`

结果说明：

- 训练池内和留出池都能正常完成汇总
- 两边 `H2/CO2/SOC` 越界都为 `0`
- 但这只是链路验证，策略质量几乎没有参考价值

### 2. `pilot5k` 小规模统一训练

基于默认训练池，已经跑完一轮更像样的小规模训练：

- 训练目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_pilot5k_20260320_231617/`
- 训练步数：`5000`
- episode 长度：`168`
- 设备：`cuda`

训练过程中，episode reward 已经从明显负值爬升到正区间，说明统一策略至少开始学到某种有约束的运行偏好。

### 3. `pilot5k` 双池评估初步结论

对应评估结果在：

- 训练池内：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_in_pool_pilot5k_20260320_231735/`
- 留出池：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_holdout_pilot5k_20260320_231735/`

当前最重要的结论有两条：

- 训练池内和留出池在短周期下都保持 `H2/CO2/SOC` 零越界
- 两边平均表现接近，说明在当前这个很小的容量邻域里，统一策略已经出现了早期的“配置感知而非只记住单点”的迹象

但同样要明确：

- 这还只是 `5000` 步的小规模训练
- 当前产量和 `LCOM` 还远不能和单配置精调策略相比
- 现在最多只能说“统一策略链路已经打通，并出现了早期泛化迹象”，不能说阶段 4 已经完成

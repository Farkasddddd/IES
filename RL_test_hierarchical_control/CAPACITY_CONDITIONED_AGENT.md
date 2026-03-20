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

## 训练命令

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\train_sac_capacity_conditioned.py --timesteps 60000 --episode-horizon 168 --pool-path RL_test_hierarchical_control\config\stage4_conditioned_pool.json
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

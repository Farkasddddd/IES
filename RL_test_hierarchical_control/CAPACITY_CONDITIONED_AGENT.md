# 统一容量条件策略说明

## 目标

这一部分对应项目的阶段 4 预备工作。目标不是宣称“一个策略适配一切容量”，而是先训练一个能够读取容量配置上下文、并在预定义容量范围内自动调整行为的统一策略。

更准确地说，这里要验证的是：

- 同一个策略能否在一组相近但不同的容量配置上稳定运行
- 在训练池内外，策略是否都能保持零越界或近零越界
- 性能是否能逐步逼近单配置精调策略

## 当前实现范围

目前已经具备以下基础能力：

- 复用现有 `stage1` 标准化环境接口
- 每个 episode 开始时，从容量池中采样一个配置
- observation 中保留配置态输入
- 动作接口继续沿用 `stage1`
- 支持从已有统一策略继续 warm-start 微调
- 支持训练池和留出池的批量评估
- 支持和单配置专用策略做同口径对照

## 训练池与留出池

默认训练池在：

- `RL_test_hierarchical_control/config/stage4_conditioned_pool.json`

当前训练池包含 5 个代表性容量点：

- `baseline`
- `h2_55`
- `h2_60`
- `bat_e_30`
- `bat_e_35`

默认留出池在：

- `RL_test_hierarchical_control/config/stage4_holdout_pool.json`

留出池用于检查统一策略在训练池外附近容量点上的稳定性与性能退化情况。

## 主要脚本

训练统一策略：

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\train_sac_capacity_conditioned.py --timesteps 60000 --episode-horizon 168 --pool-path RL_test_hierarchical_control\config\stage4_conditioned_pool.json
```

评估训练池：

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_capacity_conditioned.py --pool-path RL_test_hierarchical_control\config\stage4_conditioned_pool.json --episode-horizon 168
```

评估留出池：

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_capacity_conditioned.py --pool-path RL_test_hierarchical_control\config\stage4_holdout_pool.json --episode-horizon 168
```

分析统一策略与单配置专用策略的差距：

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\analyze_capacity_conditioned_progress.py --conditioned-in-pool <训练池汇总json> --conditioned-holdout <留出池汇总json> --run-tag <标签>
```

做统一策略模型选择：

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\select_capacity_conditioned_model.py --candidate "<标签>=<模型路径>" --candidate "<标签>=<模型路径>"
```

## 当前验证记录

### 1. smoke 冒烟链路

最早先做了一轮极短的冒烟训练，用于确认多配置采样、统一训练入口、模型保存和评估链路全部打通：

- 运行目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_smoke_20260320_230202/`
- 训练步数：`200`
- episode 长度：`48`
- 设备：`cuda`

这一步只验证链路，不用于性能判断。

### 2. pilot5k

第一轮小规模统一训练：

- 运行目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_pilot5k_20260320_231617/`
- 训练步数：`5000`
- episode 长度：`168`
- 设备：`cuda`

对应双池评估：

- 训练池：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_in_pool_pilot5k_20260320_231735/`
- 留出池：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_holdout_pilot5k_20260320_231735/`

主要现象：

- 训练池和留出池都保持 `H2/CO2/SOC = 0` 越界
- 训练池与留出池均值已经比较接近，出现早期局部泛化信号
- 但和单配置专用策略相比，仍有明显性能差距

### 3. pilot20k_ft

第二轮从 `pilot5k` 继续 warm-start：

- 运行目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_pilot20k_ft_20260320_233319/`

对应双池评估：

- 训练池均值：甲醇 `2792.77 kg`，`LCOM 418.6589`
- 留出池均值：甲醇 `2786.28 kg`，`LCOM 417.1475`
- 三类越界仍为 `0`

这一轮最重要的进步是：

- `h2_55` 这个关键容量点上，统一策略与专用策略的差距明显缩小
- 留出池和训练池的差值依然很小，说明训练更久后没有明显破坏局部泛化

### 4. pilot60k_ft

第三轮从 `pilot20k_ft` 继续 warm-start 到更接近正式规模：

- 运行目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_pilot60k_ft_20260320_234109/`
- 追加训练步数：`40000`
- 本轮训练结束时 `ep_rew_mean` 大约提升到 `2.15e4`

对应双池评估：

- 训练池：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_pilot60k_ft_in_pool_20260320_235128/`
- 留出池：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_pilot60k_ft_holdout_20260320_235128/`
- 对照分析：
  `RL_test_hierarchical_control/results/stage4_conditioned/analysis/conditioned_vs_specialized_pilot60k_ft_20260320_235148/`

本轮结果：

- 训练池均值：甲醇 `2788.99 kg`，`LCOM 419.1223`
- 留出池均值：甲醇 `2775.26 kg`，`LCOM 418.8289`
- 训练池和留出池三类越界仍全部为 `0`
- 训练池与留出池的均值差仍然很小，说明局部泛化信号还在

与单配置专用策略对照后的结论：

- `baseline`：统一策略仍落后于专用策略
- `h2_55`：统一策略仍落后，但差距没有消失
- `bat_e_35`：统一策略已经非常接近专用策略

### 5. 当前阶段的模型选择结果

为了避免只凭最后一次训练结果选模型，当前已经加入统一策略模型选择流程，会同时参考：

- 训练池均值
- 留出池均值
- 泛化差值
- 与单配置专用策略的平均差距
- 全部约束越界是否为 0

在第一轮 7 个候选模型的比较中，当前最优候选不是 `pilot60k_final`，而是：

- `pilot60k_ckpt55k`

对应结果目录：

- `RL_test_hierarchical_control/results/stage4_conditioned/selection/stage4_model_selection_round1_7candidates_20260321_135627/`

当前这个候选的关键表现是：

- 训练池平均甲醇：`2841.80 kg`
- 留出池平均甲醇：`2833.67 kg`
- 训练池平均 LCOM：`411.3456`
- 留出池平均 LCOM：`410.1271`
- 平均专用策略甲醇差值：`-56.77 kg`
- 平均专用策略 LCOM 差值：`+7.7340`
- `H2/CO2/SOC` 越界仍全部为 `0`

这说明当前阶段已经可以明确一条工程结论：

- 统一策略不应只按“训练步数越大越好”来选
- 对 conditioned policy 来说，中间 checkpoint 可能优于最终 checkpoint
- 后续阶段 4 的继续训练与年度验证，应优先基于 `pilot60k_ckpt55k` 往前推进

## 当前判断

目前可以确认 3 件事：

1. 统一容量条件策略链路已经打通，并且能够稳定训练
2. 在当前这组上海基准附近容量点上，统一策略已经表现出局部泛化能力
3. 统一策略仍未全面追平单配置专用策略，尤其在 `baseline` 和 `h2_55` 这两个点上还有差距

同时也出现了一个很重要的现象：

- 从 `pilot20k_ft` 继续训练到 `pilot60k_ft` 后，训练 reward 继续上涨
- 但池内均值和部分关键点对照并没有同步单调改善

这说明阶段 4 后面不能只盯训练 reward，还需要更明确地做模型选择，例如同时参考：

- 训练池均值
- 留出池均值
- 与专用策略的差距
- 全年零越界约束

关于当前阶段已经形成的正式年度结论，见：

- `RL_test_hierarchical_control/STAGE4_CONDITIONED_FINAL_CONCLUSION.md`

## 当前阶段结论

统一策略已经从“只有脚手架”推进到了“有局部泛化信号、且可稳定零越界运行”的状态，但还不能宣布完成阶段 4。

更准确的结论是：

- 阶段 4 已经具备继续推进的工程基础
- 当前最好把它视作“统一策略原型”而不是正式替代专用策略的最终模型
- 后续需要继续做更严谨的模型选择、留出验证和年度长周期验证

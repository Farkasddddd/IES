# 项目版本索引

## 目的

这个文件用于概览工作区内几个主要实验目录的定位，避免后续继续开发时把不同阶段的代码和结果混在一起。

## 1. `RL_test_fixed_config`

路径：

`C:\Users\27878\Desktop\IES\RL_test_fixed_config`

定位：

- 较早期的固定配置 RL 实验目录
- 采用平面或半平面控制结构
- 主要用于调试光伏解析、模型加载、DAC 状态转移和年度评估流程

代表文件：

- 环境：
  `RL_test_fixed_config/env/ies_bilevel_env_fixed.py`
- 训练：
  `RL_test_fixed_config/train/train_sac_fixed.py`
- 年度评估：
  `RL_test_fixed_config/train/evaluate_policy_8760.py`

代表结果：

- `sac_fixed_config_v3.zip`
- 年度评估已经能跑满 `8760h`，但 `CO2` 库存长期贴近下边界，`H2` 仍出现过溢出

解释：

- 适合作为调试和过渡版本参考
- 不适合作为最终正式调度结构

## 2. `RL_test_hierarchical_control`

路径：

`C:\Users\27878\Desktop\IES\RL_test_hierarchical_control`

定位：

- 当前主线的分层调度版本
- 规则层负责守住物理安全
- RL 只优化高层运行偏好

代表文件：

- 环境：
  `RL_test_hierarchical_control/env/ies_bilevel_env_hierarchical.py`
- 训练：
  `RL_test_hierarchical_control/train/train_sac_hierarchical.py`
- 年度评估：
  `RL_test_hierarchical_control/train/evaluate_policy_8760.py`
- 年度图表：
  `RL_test_hierarchical_control/results/figures/`
- 说明文档：
  `RL_test_hierarchical_control/README_hierarchical_model.md`

代表结果：

- `sac_hierarchical_v1.zip`
- 年甲醇产量约 `147427 kg`
- 无 `CO2` 溢出
- 无 `H2` 溢出
- `CO2` 与 `H2` 储罐比例基本维持在 `20% ~ 80%`

解释：

- 这是当前调度层的正式基线
- 相比固定配置平面控制版本，更安全、更易解释
- 适合作为容量优化阶段的参考策略来源

## 3. `RL_capacity_optimization`

路径：

`C:\Users\27878\Desktop\IES\RL_capacity_optimization`

定位：

- 上层容量配置优化工作区
- 第一阶段使用分层调度策略作为固定下层控制器
- 用于候选配置筛选、排序以及后续协同优化

代表文件：

- 环境副本：
  `RL_capacity_optimization/env/ies_capacity_env.py`
- 经济参数：
  `RL_capacity_optimization/config/economic_params.py`
- 甲醇市场场景：
  `RL_capacity_optimization/config/market_scenarios.py`
- 容量排序逻辑：
  `RL_capacity_optimization/metrics/capacity_objectives.py`
- 分层调度参考说明：
  `RL_capacity_optimization/docs/hierarchical_dispatch_reference.md`
- 参考策略副本：
  `RL_capacity_optimization/results/models/sac_hierarchical_reference.zip`

当前任务：

- 在固定调度策略下筛选容量组合
- 先排除明显不可行配置
- 再按不同甲醇价格场景下的年度经济性进行排序

## 推荐使用原则

- `RL_test_hierarchical_control` 保持为调度层基准目录
- 新的容量搜索逻辑不要覆盖旧结果
- 所有上层容量优化脚本和输出尽量都保留在 `RL_capacity_optimization` 下

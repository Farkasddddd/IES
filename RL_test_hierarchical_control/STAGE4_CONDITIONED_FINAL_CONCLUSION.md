# 阶段 4 当前最终结论

## 结论一句话

在当前上海基准附近的容量邻域内，统一容量条件策略已经可以作为**当前阶段的正式 conditioned 基线**：它在 `8760h` 年尺度下对训练池和留出池都保持 `H2/CO2/SOC = 0` 越界，泛化差距很小，且与单配置专用策略相比，平均 `LCOM` 已经基本打平。

但它还不能被表述为“全面替代所有单配置专用策略”。更准确的结论是：

- 它已经是一个**稳定、可信、可泛化的统一策略原型**
- 在当前覆盖的局部容量范围内，它已经具备**实用价值**
- 若已知单一容量点并允许专门微调，单配置专用策略在部分点上仍然更强

## 当前选中的统一策略模型

当前最佳 conditioned 候选不是最后一个训练点，而是中间 checkpoint：

- `pilot60k_ckpt55k`

对应模型路径：

- `RL_test_hierarchical_control/results/stage4_conditioned/training_runs/stage4_conditioned_pilot60k_ft_20260320_234109/checkpoints/policy_stage1_standardized_55000_steps.zip`

选择记录在：

- `RL_test_hierarchical_control/results/stage4_conditioned/latest_model/selected_capacity_conditioned_model.json`
- `RL_test_hierarchical_control/results/stage4_conditioned/selection/stage4_model_selection_round1_7candidates_refresh_20260321_135753/`

这说明对于统一策略，不能简单按“训练步数越多越好”来选模型，中间 checkpoint 可能优于最终 checkpoint。

## 年尺度验证结果

本轮使用 `pilot60k_ckpt55k` 对训练池和留出池都做了 `8760h` 评估。

训练池结果：

- 结果目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_selected55k_annual_in_pool_clean_20260321_140922/`
- 平均年甲醇产量：`136720.24 kg`
- 平均 `LCOM`：`8.5892 yuan/kg`
- 最大 `H2/CO2/SOC` 越界：`0/0/0`

留出池结果：

- 结果目录：
  `RL_test_hierarchical_control/results/stage4_conditioned/evaluations/stage4_eval_selected55k_annual_holdout_clean_20260321_140922/`
- 平均年甲醇产量：`136800.12 kg`
- 平均 `LCOM`：`8.5388 yuan/kg`
- 最大 `H2/CO2/SOC` 越界：`0/0/0`

直接判断：

- 训练池和留出池在年尺度下都保持了零越界
- 留出池与训练池均值极为接近
- 当前这个统一策略在已覆盖邻域里表现出稳定的局部泛化能力

## 与单配置专用策略的年度对照

年度对照结果在：

- `RL_test_hierarchical_control/results/stage4_conditioned/analysis/conditioned_vs_specialized_selected55k_annual_20260321_140734/`
- `RL_test_hierarchical_control/results/stage4_conditioned/analysis/conditioned_vs_specialized_selected55k_annual_clean_20260321_141110/`

对 3 个关键参考配置的对照如下。

### 1. baseline

- 统一策略：甲醇 `135786.22 kg`，`LCOM 8.1406`
- 专用策略：甲醇 `120497.78 kg`，`LCOM 9.1718`

结论：

- 统一策略显著优于当前 baseline 专用策略

### 2. h2_55

- 统一策略：甲醇 `135132.79 kg`，`LCOM 8.3204`
- 专用策略：甲醇 `147980.54 kg`，`LCOM 7.6509`

结论：

- 在当前最优 `H2` 扩容点上，专用策略仍明显强于统一策略

### 3. bat_e_35

- 统一策略：甲醇 `139352.41 kg`，`LCOM 9.2167`
- 专用策略：甲醇 `145517.09 kg`，`LCOM 8.8716`

结论：

- 在电池扩容点上，统一策略已经比较接近专用策略，但仍略逊

## 综合判断

把这 3 个参考点放在一起看：

- 平均甲醇差值：`-1241.33 kg`
- 平均 `LCOM` 差值：`-0.0055 yuan/kg`

这两个数非常关键。

它意味着：

- 从平均经济性看，统一策略已经和这组参考专用策略**基本打平**
- 从平均产量看，统一策略略低，但差距已经不大
- 统一策略最大的短板，主要集中在 `h2_55` 这种更强定向扩容的点上

## 当前阶段的正式判断

基于目前结果，我给出的正式判断是：

1. 阶段 4 还没有完成到“统一策略全面替代专用策略”的程度。
2. 但阶段 4 已经完成到“拿出一个可信的统一 conditioned 基线”的程度。
3. 这个基线满足当前阶段最重要的工程标准：
   - 年尺度零越界
   - 留出池稳定
   - 平均 `LCOM` 不劣于参考专用策略
   - 平均产量差距不大
   - 训练与模型选择链路已规范化

因此，当前最合理的项目表述是：

> 我们已经得到一个在局部容量邻域内可泛化、年尺度稳定、经济性接近单配置专用策略的统一容量条件策略基线，但在特定优势容量点上，专用微调策略仍然更优。

## 下一阶段建议

如果继续推进，后面最值得做的是：

1. 以当前选中的 `pilot60k_ckpt55k` 为统一策略正式起点，而不是回到 `pilot60k_final`
2. 扩大训练池，但仍保持在“可解释的局部邻域”内，避免一下子铺太大
3. 增加年度模型选择标准，而不是只看短周期或训练 reward
4. 重点补强 `h2_55` 这类定向扩容点，让统一策略对“高价值容量方向”适配得更好

## 当前阶段结束语

到今天这一步，统一容量条件策略已经不再只是“概念验证脚手架”，而是有了明确的模型选择结果、年尺度验证结果和与专用策略的年度对照结果。

这意味着阶段 4 已经进入了“可以严肃写进论文方法与结果部分”的状态。

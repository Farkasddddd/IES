# IES 项目总览

这是一个面向综合能源系统调度与容量研究的工作区，当前重点是上海单地区场景下的分层控制、容量参数化、容量到策略映射，以及年度性能评估。

## 当前重点

- 在上海基准容量下得到稳定、可信、可解释的高层策略
- 完成第一阶段标准化环境接口
- 基于基准策略做容量变化下的 warm-start 微调
- 提炼“容量变化如何影响策略与系统表现”的规律

## 主要目录

- `RL_test_hierarchical_control/`
  当前主线目录，包含 `stage1` 标准化环境、训练、评估以及阶段 2 容量微调实验
- `RL_capacity_optimization/`
  容量候选评估、二阶段微调和容量搜索相关脚本
- `ies_shared/`
  共享环境、标准化配置和评估逻辑
- `data/`
  输入数据和代理模型文件

## 关键说明文件

- `SETUP_NEW_MACHINE.md`
  新电脑迁移与环境安装说明
- `PROJECT_EXECUTION_STAGES.md`
  项目四阶段推进思路与当前执行规则
- `STAGE2_ACCELERATION_WORKFLOW.md`
  阶段 2 的加速实验流程
- `GIT_BACKUP_QUICKSTART.md`
  Git 提交、推送和云端备份说明
- `RL_test_hierarchical_control/STAGE1_STANDARDIZATION.md`
  第一阶段标准化接口说明
- `RL_test_hierarchical_control/CAPACITY_CONDITIONED_AGENT.md`
  统一容量条件策略的脚手架说明

## 当前研究结论入口

当前已经整理出的“容量-策略-性能”映射结果可以直接查看：

- `RL_test_hierarchical_control/results/stage1/stage_archives/mapping_final_20260320/mapping_conclusions.md`
- `RL_test_hierarchical_control/results/stage1/stage_archives/mapping_final_20260320/mapping_ranked_leaderboard.md`

## Git 备份

当前仓库已经完成 Git 初始化并连接远端仓库。日常保存推荐使用：

```powershell
git status
git add .
git commit -m "本次更新说明"
git push
```

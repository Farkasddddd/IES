# Git 云端备份快速说明

本项目已经完成本地 Git 初始化。

当前 `.gitignore` 的设计原则是：

- 保留代码、配置、文档和整理后的阶段归档
- 忽略体积较大的训练输出、evaluation 全量结果、checkpoint、tensorboard 和根目录模型 zip

## 1. 设置 Git 身份

如果新机器还没有配置 Git 身份，可以执行：

```powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

如果只想给当前项目设置：

```powershell
git config user.name "你的名字"
git config user.email "你的邮箱"
```

## 2. 查看当前改动

```powershell
cd C:\Users\Farkas\Desktop\IES
git status
```

## 3. 提交当前版本

```powershell
git add .
git commit -m "本次更新说明"
```

## 4. 推送到远端仓库

```powershell
git push
```

如果是第一次连接远端仓库，通常需要：

```powershell
git branch -M main
git remote add origin <远端仓库地址>
git push -u origin main
```

## 5. 日常备份流程

后续每次做完一版，推荐执行：

```powershell
git status
git add .
git commit -m "说明这次改了什么"
git push
```

## 6. 如果以后想把大模型文件也纳入版本控制

当前规则默认忽略 `.zip`、部分大文件和训练产物。

如果后续确实要把这些大文件也同步到云端，更推荐使用 Git LFS：

```powershell
git lfs install
git lfs track "*.zip"
git lfs track "*.pth"
git add .gitattributes
git add .
git commit -m "启用 Git LFS 管理模型文件"
git push
```

## 7. 当前最推荐的做法

当前项目更适合做分层备份：

- Git 仓库存：
  - 代码
  - 配置
  - 文档
  - 阶段归档表
- 其他云备份存：
  - 原始训练输出
  - 全量年度评估文件
  - checkpoint
  - 大模型文件

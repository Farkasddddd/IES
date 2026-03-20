# 更新记录数据库说明

这个目录用于保存项目版本更新记录。

当前包含两层内容：

- `update_history.db`
  SQLite 数据库，记录每次更新的提交时间、提交内容、提交哈希、作者、分支和变更文件列表
- `update_history_latest.json`
  从数据库导出的结构化摘要
- `update_history_latest.md`
  便于直接阅读的中文版本摘要

## 同步方式

当本地有新提交后，执行：

```powershell
E:\anaconda\python.exe scripts\sync_update_history_db.py --limit 50
```

这个脚本会：

- 读取最近的 Git 提交
- 更新或插入数据库记录
- 自动导出最新的 `json` 和 `md`

## 记录字段

数据库会记录：

- 提交哈希
- 提交时间
- 作者
- 分支
- 更新标题
- 更新内容摘要
- 变更文件数
- 变更文件列表
- 当前是否已经出现在 `origin/main`
- 本次写入数据库的时间

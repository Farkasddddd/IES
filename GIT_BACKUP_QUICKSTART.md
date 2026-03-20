# Git Backup Quickstart

This project has been initialized as a local Git repository.

The `.gitignore` is set up to:
- keep source code, configs, docs, and curated stage archives
- ignore bulky training runs, evaluations, checkpoints, tensorboard logs, and root model zip files

## 1. Set your Git identity

Git commit is not ready yet because `user.name` and `user.email` are not configured on this machine.

Set them once:

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

If you only want to set identity for this project:

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

## 2. Review what will be committed

```powershell
cd C:\Users\Farkas\Desktop\IES
git status
```

## 3. Create the first commit

```powershell
git add .
git commit -m "Initial project snapshot"
```

## 4. Create a remote repository

Create an empty repository on one of:
- GitHub
- Gitee
- GitLab

Then connect and push:

```powershell
git branch -M main
git remote add origin <your-remote-url>
git push -u origin main
```

Examples:

```powershell
git remote add origin https://github.com/<user>/<repo>.git
```

```powershell
git remote add origin https://gitee.com/<user>/<repo>.git
```

## 5. Daily backup workflow

After later edits:

```powershell
git status
git add .
git commit -m "Describe the update"
git push
```

## 6. If you want to track model zip or pth files

The current `.gitignore` excludes large model artifacts by default.

If you later want cloud versioning for large files, use Git LFS:

```powershell
git lfs install
git lfs track "*.zip"
git lfs track "*.pth"
git add .gitattributes
git add .
git commit -m "Enable Git LFS for model artifacts"
git push
```

## 7. Recommended current practice

For this project, a practical split is:
- Git: source code, configs, docs, summary csv/json/md archives
- separate cloud backup: raw training outputs, full evaluation folders, model checkpoints

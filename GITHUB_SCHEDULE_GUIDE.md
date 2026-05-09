# GitHub Pages 本地定期更新说明

你的网页地址：

```text
https://zhangqi3182627-sketch.github.io/China-HousingCycle/
```

## 当前方案

采用“本地跑完整 Python + 推送 GitHub + GitHub Pages 自动发布”：

```text
CodeBuddy 本地定期任务
→ bash scripts/monthly_update_and_push.sh
→ python3 scripts/run_monthly_update.py
→ git commit && git push
→ GitHub Actions 只发布 reports/ 到 Pages
```

这样可以继续使用你本地已有的 `westock-data` 环境，不需要再找公开 Python 数据源。

## GitHub Actions 做什么

文件：

```text
.github/workflows/pages.yml
```

它现在只负责：

1. 你推送 `reports/` 后，自动发布 GitHub Pages；
2. 支持你在 GitHub 网页上手动点 `Run workflow` 重新部署已有 `reports/`。

它不再在 GitHub 云端运行：

```bash
python scripts/run_monthly_update.py
```

原因：GitHub 云端没有你的本地 `westock-data` 环境，云端跑 Python 会导致部分 westock 数据源缺失，可能覆盖成不完整报告。

## 本地月度推送脚本

脚本：

```text
scripts/monthly_update_and_push.sh
```

它会：

```text
检查本月是否已经推送
→ 未推送则运行 python3 scripts/run_monthly_update.py
→ 提交 reports、数据库、手工数据和配置
→ 推送到 GitHub
→ GitHub Pages 自动部署
```

手动运行：

```bash
cd /Users/qizhang/CodeBuddy/Claw/HousingCycle
bash scripts/monthly_update_and_push.sh
```

## CodeBuddy 定期任务

已创建本地自动化任务：

```text
房产月度本地推送
```

调度方式：

```text
每周一 10:00 检查一次
```

脚本内部有月份戳：

```text
.update-stamps/monthly-github-push.txt
```

所以即使每周检查，实际效果也是：

```text
每月最多推送一次
```

## GitHub Desktop 需要提交的改动

如果你看到 GitHub Desktop 有以下改动：

```text
.github/workflows/pages.yml
GITHUB_SCHEDULE_GUIDE.md
scripts/monthly_update_and_push.sh
.gitignore
```

左下角 Summary 填：

```text
use local monthly update and pages deploy only
```

然后点：

```text
Commit to main
Push origin
```

推送后，GitHub Actions 会自动把 `reports/` 发布到：

```text
https://zhangqi3182627-sketch.github.io/China-HousingCycle/
```

## 重要提醒

- 你的 Mac / CodeBuddy 需要在任务执行时间附近能运行，否则本地定期任务不会触发。
- 如果某个月错过了，手动运行 `bash scripts/monthly_update_and_push.sh` 即可补发。
- 如果将来希望完全脱离本机，就用云服务器安装同样的本地环境，再用 crontab 每月运行这个脚本。

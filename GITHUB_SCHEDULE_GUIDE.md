# GitHub Pages 定期自动更新说明

你的网页地址：

```text
https://zhangqi3182627-sketch.github.io/China-HousingCycle/
```

## 已配置的自动化

文件：

```text
.github/workflows/pages.yml
```

它会做两件事：

1. 每次你推送 `reports/`、`scripts/`、`data/manual/` 等文件时，自动发布 GitHub Pages；
2. 每月自动跑一次 Python 更新：

```bash
python scripts/run_monthly_update.py
```

## 定时时间

当前设置为：

```text
每月 20 日，北京时间 10:00
```

对应 GitHub Actions 里的 UTC 时间：

```yaml
- cron: "0 2 20 * *"
```

原因：央行、统计局、70 城数据通常在每月中旬发布，20 日更新比较稳。

## 第一次需要你做什么

用 GitHub Desktop 提交并推送这批文件：

- `.github/workflows/pages.yml`
- `.gitignore`
- `requirements.txt`
- `data/housing_cycle.sqlite`
- `reports/dashboard.html`
- `reports/index.html`
- `reports/monthly/housing_cycle_2026-03.md`
- `scripts/*.py`
- `data/manual/*.csv`
- `GITHUB_SCHEDULE_GUIDE.md`

### GitHub Desktop 操作

1. 打开 GitHub Desktop
2. 选择仓库 `HousingCycle` / `China-HousingCycle`
3. 左下角 Summary 填：

```text
add scheduled monthly update
```

4. 点击：

```text
Commit to main
```

5. 点击：

```text
Push origin
```

## 如何手动触发一次更新

打开 GitHub 仓库页面：

```text
Actions → Update and Deploy HousingCycle Dashboard → Run workflow
```

点击运行后，它会：

1. 安装 Python；
2. 安装 `requirements.txt`；
3. 执行 `scripts/run_monthly_update.py`；
4. 自动提交更新后的 `reports/dashboard.html` 和数据库；
5. 自动发布 GitHub Pages。

## 重要限制

当前 GitHub Actions 可以自动更新：

- 央行居民贷款；
- 央行信贷表；
- 70 城房价；
- 国房景气指数 / 新增贷款等 AkShare/Eastmoney 可访问数据；
- Dashboard 和月度报告。

但 `westock-data` 是你本地环境里的专用工具，GitHub Actions 里没有，所以：

- 房地产开发销售、资金来源等 westock 相关数据，在 GitHub 云端可能不会自动新增；
- 当前 workflow 会依赖已提交的 `data/housing_cycle.sqlite` 保留历史数据；
- 如果要让这些数据也完全云端自动更新，后续需要把 westock 数据源替换为公开 Python 数据源，或使用你自己的服务器/云函数跑本地环境。

现阶段建议：

```text
GitHub 每月自动更新可公开抓取部分；
如果你本地跑了完整更新，再用 GitHub Desktop 推送一次，网页会立刻更新到完整版。
```

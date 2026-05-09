# GitHub 发布房地产 Dashboard：小白步骤

## 你最终会得到什么

一个外部可访问的网址，用来打开：

```text
reports/dashboard.html
```

以后你本地运行：

```bash
python3 scripts/run_monthly_update.py
```

再把更新推送到 GitHub，网站就会更新。

---

## 第 0 步：先注册 GitHub

入口：

```text
https://github.com/signup
```

注册后登录 GitHub。

---

## 第 1 步：新建仓库

打开：

```text
https://github.com/new
```

建议这样填：

| 项目 | 填写 |
|---|---|
| Repository name | `housing-cycle-dashboard` |
| Description | `China housing cycle monthly dashboard` |
| Public / Private | 建议先选 `Private` |
| Add a README file | 不要勾选 |
| Add .gitignore | 不要选 |
| Choose a license | 不要选 |

然后点击：

```text
Create repository
```

创建后，你会看到一个仓库地址，类似：

```text
https://github.com/你的用户名/housing-cycle-dashboard.git
```

先复制这个地址。

---

## 第 2 步：在本地初始化并上传

在终端执行，把下面的 `你的用户名` 改成你的 GitHub 用户名：

```bash
cd /Users/qizhang/CodeBuddy/Claw/HousingCycle

git init
git branch -M main
git add .
git commit -m "init housing cycle dashboard"
git remote add origin https://github.com/你的用户名/housing-cycle-dashboard.git
git push -u origin main
```

如果 `git push` 要你登录：

- 用户名：填你的 GitHub 用户名；
- 密码：不要填 GitHub 登录密码，要填 Personal Access Token。

如果你觉得 Token 麻烦，建议安装 **GitHub Desktop**，更适合新手：

```text
https://desktop.github.com/
```

---

## 第 3 步：开启 GitHub Pages

进入你的 GitHub 仓库页面：

```text
https://github.com/你的用户名/housing-cycle-dashboard
```

依次点击：

```text
Settings → Pages
```

在 `Build and deployment` 里：

| 项目 | 选择 |
|---|---|
| Source | `GitHub Actions` |

保存后，回到仓库顶部点击：

```text
Actions
```

等待 `Deploy HousingCycle Dashboard` 运行成功。

---

## 第 4 步：打开网站

发布成功后，GitHub Pages 地址通常是：

```text
https://你的用户名.github.io/housing-cycle-dashboard/
```

这个地址会自动跳转到：

```text
dashboard.html
```

---

## 第 5 步：以后每月怎么更新

本地执行：

```bash
cd /Users/qizhang/CodeBuddy/Claw/HousingCycle
python3 scripts/run_monthly_update.py
```

然后上传更新：

```bash
git add reports data/manual scripts README.md requirements.txt .github .gitignore
git commit -m "monthly update"
git push
```

GitHub 会自动重新发布网站。

---

## 当前我已经帮你准备好的文件

| 文件 | 用途 |
|---|---|
| `.gitignore` | 避免提交本地 SQLite、原始缓存和临时文件 |
| `requirements.txt` | Python 依赖清单 |
| `.github/workflows/pages.yml` | GitHub Pages 自动发布配置 |
| `reports/index.html` | 网站首页，自动跳到 Dashboard |
| `reports/.nojekyll` | 让 GitHub Pages 原样发布静态文件 |

---

## 注意

当前 GitHub Actions 只负责发布静态网页。

完整自动抓数据还需要进一步把本地依赖替换成 GitHub Actions 能运行的公开 Python 数据源。现阶段建议：

```text
本地跑月度更新 → 推送 GitHub → GitHub 自动发布网页
```

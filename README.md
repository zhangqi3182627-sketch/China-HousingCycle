# HousingCycle — 全国商品房走势跟踪框架

## 核心逻辑

用户假设：**房即是债，债即是房**。

房价见底的核心观测指标不是房价本身，而是居民部门是否重新扩表：

```text
居民每月新增贷款 6M 均值 > 3000亿
且 12M 均值 > 3000亿
且 6M 自下而上穿越 12M
且向上发散形成多头排列
```

## 数据库

默认生成：

```text
data/housing_cycle.sqlite
```

表：

- `series`：指标元数据
- `observations`：月度观测值
- `model_signals`：模型信号
- `source_log`：数据源拉取日志

## 当前数据源

| 模块 | 数据源 | 状态 |
|---|---|---|
| 居民新增贷款 | PBOC 金融机构人民币信贷收支表 + 月度金融统计报告校验 | 自动抓取央行年度信贷表，由住户贷款余额月差生成；早年缺按部门口径则不估算 |
| 70城新房/二手房价格 | Eastmoney/NBS release mirror | 可自动拉取 |
| 国房景气指数 | Eastmoney/AkShare | 可自动拉取 |
| 新增人民币贷款总额 | Eastmoney/AkShare | 可自动拉取；仅作信用环境代理 |
| 商品房销售/新开工 | westock-data macro investment / NBS 口径镜像 | 已自动入库，覆盖 2000-02 至今 |
| 房地产开发投资/竣工/待售/资金来源 | westock-data macro investment | 已自动入库，覆盖 2000-02 至今 |
| 二手房销售 | 城市住建委/贝壳/中指等 | 无全国统一官方月度源，后续分城市补 |
| NeoData 校验 | NeoData Financial Search | 已作为校验层接入，适合查最新与交叉验证，不作为主库 |

## 运行

```bash
cd /Users/qizhang/CodeBuddy/Claw/HousingCycle
python3 scripts/build_housing_cycle_db.py
```

## 可视化 Dashboard / 月度更新

完整月度流水线：抓取最新数据、重建数据库、生成 HTML Dashboard、输出历史回测报告和月度 Markdown 报告。

```bash
cd /Users/qizhang/CodeBuddy/Claw/HousingCycle
python3 scripts/run_monthly_update.py
# 或
bash scripts/update_dashboard.sh
```

输出文件：

```text
reports/dashboard.html
reports/backtest.html
reports/backtest_summary.csv
reports/monthly/housing_cycle_YYYY-MM.md
```

如果只想基于现有数据库重画网页：

```bash
python3 scripts/generate_dashboard.py
```

手工/授权数据模板：

```text
data/manual/pbc_real_estate_loan_quarterly.csv
data/manual/creis_top10_second_hand_listing.csv
data/manual/model_weight_scheme.csv
```

## 重要限制

当前模型已接入央行官方信贷表自动抓取，但早年若没有住户贷款按部门口径，不强行估算。

正式信号至少要求 `household_new_loans` 连续覆盖 12 个月；覆盖越长，均线和穿越判断越可靠。

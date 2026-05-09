# 房地产周期月度追踪报告 — 2026-03

生成时间：2026-05-09 12:03:09

## 主信号

| 指标 | 数值 |
|---|---:|
| 最新月份 | 2026-03 |
| 主信号 | RED_NO_BOTTOM |
| 居民新增贷款 | 4,908.94 亿 |
| 6M 均值 | -607.67 亿 |
| 12M 均值 | -254.27 亿 |
| 6M-12M 利差 | -353.40 亿 |
| 综合分 | 0 |

结论：居民加杠杆趋势未确认

## 可视化入口

- HTML Dashboard：`reports/dashboard.html`

## 数据源状态

| source                             | status   |   rows | message                                                      | run_at              |
|:-----------------------------------|:---------|-------:|:-------------------------------------------------------------|:--------------------|
| pbc_credit_tables                  | ok       |   1383 | stock_months=231 monthly_diffs=230 coverage=2007-01..2026-03 | 2026-05-09T12:03:08 |
| pbc_household_manual               | ok       |      9 | manual seed; not complete 2000-now series                    | 2026-05-09T12:02:49 |
| pbc_household_monthly_from_reports | ok       |      6 | monthly values parsed or derived from YTD snippets           | 2026-05-09T12:02:49 |
| pbc_report_snippets                | ok       |      4 | parsed PBOC monthly/YTD snippets                             | 2026-05-09T12:02:49 |
| neodata_validation                 | ok       |      3 | validation queries completed                                 | 2026-05-09T12:02:49 |
| westock_investment                 | ok       |   3088 | years=2000-2026                                              | 2026-05-09T12:02:48 |
| real_estate_climate                | ok       |    326 |                                                              | 2026-05-09T12:02:48 |
| new_financial_credit               | ok       |    219 |                                                              | 2026-05-09T12:02:47 |
| 70_city_house_price                | ok       |  51606 | raw rows=12834; unique city rows=12810; fresh                | 2026-05-09T12:02:47 |

## 备注

- 国家统计局房地产开发销售数据为累计口径，且 1 月份不单独调查/发布。
- 十大城市二手房挂牌价来自中指数据公开图文/手工录入，需持续核验。
- 核心10城二手房库存变化暂无稳定可验证数据源，已从当前模型和 Dashboard 移除。

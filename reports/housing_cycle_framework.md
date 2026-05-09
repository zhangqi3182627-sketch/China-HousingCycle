# 全国商品房走势预测框架 v0.1

## 核心假设

房即是债，债即是房。房价见底的先导信号不是价格本身，而是居民部门重新扩表。

## 主信号

- 居民每月新增贷款 6个月滚动均值 > 3000亿元
- 居民每月新增贷款 12个月滚动均值 > 3000亿元
- 6M 均线自下而上穿越 12M 均线，并向上发散
- 建议增加连续3个月确认，过滤政策脉冲和春节扰动

## 辅助指标

1. 70城新房/二手房环比上涨城市占比
2. 国房景气指数及其6个月变化
3. westock-data macro investment：商品房销售面积、销售额、新开工、竣工、待售、开发投资、房企资金来源
4. 新增人民币贷款总额作为信用环境代理变量
5. 二手房成交：当前暂无全国统一官方月度源，后续按城市住建委/贝壳/中指分层补

## 当前模型最新输出

```json
[
  {
    "date": "2026-03-01 00:00:00",
    "household_new_loans": 4908.939999999944,
    "is_estimated": 0,
    "household_ma6": -607.6683333333349,
    "household_ma12": -254.2683333333407,
    "household_spread": -353.3999999999942,
    "new_breadth": 20.0,
    "second_breadth": 18.571428571428573,
    "price_breadth_score": 19.285714285714285,
    "climate_score": NaN,
    "main_signal": "RED_NO_BOTTOM",
    "recommendation": "居民加杠杆趋势未确认",
    "composite_score": 0.0,
    "notes": ""
  }
]
```

## 数据覆盖

| series_id                        |     n | start      | end        |
|:---------------------------------|------:|:-----------|:-----------|
| china_new_financial_credit       |   219 | 2008-01-01 | 2026-03-01 |
| household_loan_stock             |   231 | 2007-01-01 | 2026-03-01 |
| household_medium_long_loan_stock |   231 | 2007-01-01 | 2026-03-01 |
| household_medium_long_new_loans  |   230 | 2007-02-01 | 2026-03-01 |
| household_new_loans              |   230 | 2007-02-01 | 2026-03-01 |
| household_short_loan_stock       |   231 | 2007-01-01 | 2026-03-01 |
| household_short_new_loans        |   230 | 2007-02-01 | 2026-03-01 |
| new_home_positive_city_share     |   183 | 2011-01-01 | 2026-03-01 |
| new_home_price_mom               | 12810 | 2011-01-01 | 2026-03-01 |
| new_home_price_yoy               | 12810 | 2011-01-01 | 2026-03-01 |
| re_cap_deposit_cum               |   288 | 2000-02-01 | 2026-03-01 |
| re_cap_loan_cum                  |   288 | 2000-02-01 | 2026-03-01 |
| re_cap_self_cum                  |   288 | 2000-02-01 | 2026-03-01 |
| re_completion_area_cum           |   288 | 2000-02-01 | 2026-03-01 |
| re_for_sale_area                 |   261 | 2000-02-01 | 2026-03-01 |
| re_investment_cum                |   288 | 2000-02-01 | 2026-03-01 |
| re_investment_current            |   261 | 2000-03-01 | 2026-03-01 |
| re_new_start_area_cum            |   288 | 2000-02-01 | 2026-03-01 |
| re_sales_area_cum                |   288 | 2000-02-01 | 2026-03-01 |
| re_sales_area_current            |   261 | 2000-03-01 | 2026-03-01 |
| re_sales_revenue_cum             |   288 | 2000-02-01 | 2026-03-01 |
| real_estate_climate_index        |   326 | 1998-01-01 | 2025-12-01 |
| second_home_positive_city_share  |   183 | 2011-01-01 | 2026-03-01 |
| second_home_price_mom            | 12810 | 2011-01-01 | 2026-03-01 |
| second_home_price_yoy            | 12810 | 2011-01-01 | 2026-03-01 |

## PBC 居民贷款解析样本

| period_end   | period_type   |   household_new_loans |   household_short_new_loans |   household_medium_long_new_loans |   confidence | notes                                          |
|:-------------|:--------------|----------------------:|----------------------------:|----------------------------------:|-------------:|:-----------------------------------------------|
| 2025-01-01   | monthly       |                  4438 |                        -497 |                              4935 |         0.85 | 新闻转载央行月报，单月口径                     |
| 2025-12-01   | annual        |                  4417 |                       -8351 |                             12800 |         0.8  | 全年累计口径；用于年度校验，不直接参与单月信号 |
| 2026-02-01   | ytd           |                 -1942 |                       -3596 |                              1654 |         0.9  | 1-2月累计口径                                  |
| 2026-03-01   | ytd           |                  2967 |                       -1640 |                              4607 |         0.95 | 一季度累计口径，可与前两月相减倒推3月          |

## PBC 官方信贷表抓取日志

|   year | title                                                                                                                     | status            | message    |
|-------:|:--------------------------------------------------------------------------------------------------------------------------|:------------------|:-----------|
|   2026 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=3  |
|   2025 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2024 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2023 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2022 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2021 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2020 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2019 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2018 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2017 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2016 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2015 | 金融机构人民币信贷收支表 Summary of Sources And Uses of Credit Funds of Financial Institutions（in RMB）                  | ok                | records=12 |
|   2014 | 金融机构人民币信贷收支表（按部门分类） Sources & Uses of Credit Funds of Financial Institutions（by Sectors） 单位：亿元  | ok                | records=12 |
|   2013 | 金融机构人民币信贷收支表（按部门分类） Sources & Uses  of Credit Funds of Financial Institutions（by Sectors） 单位：亿元 | ok                | records=12 |
|   2012 | 金融机构人民币信贷收支表（按部门分类） Sources & Uses  of Credit Funds of Financial Institutions（by Sectors） 单位：亿元 | ok                | records=12 |
|   2011 | 金融机构人民币信贷收支表（按部门分类） Sources & Uses  of Credit Funds of Financial Institutions（by Sectors） 单位：亿元 | ok                | records=12 |
|   2010 | 金融机构人民币信贷收支表(按部门分类) Sources & Uses  of Credit Funds of Financial Institutions(by Sectors) 单位：亿元     | ok                | records=12 |
|   2009 | 金融机构人民币信贷收支表(按部门分类) Sources & Uses  of Credit Funds of Financial Institutions(by Sectors) 单位：亿元     | ok                | records=12 |
|   2008 | 金融机构人民币信贷收支表(按部门分类) Sources & Uses of Credit Funds of Financial Institutions(by Sectors) 单位：亿元      | ok                | records=12 |
|   2007 | 金融机构人民币信贷收支表(按部门分类) Sources & Uses of Credit Funds of Financial Institutions(by Sectors) 单位：亿元      | ok                | records=12 |
|   2006 | 金融机构人民币信贷收支表 Sources And Uses of Credit Funds of Financial Institutions                                       | no_household_rows | records=0  |
|   2005 | 金融机构人民币信贷收支表 Sources And Uses of Credit Funds of Financial Institutions                                       | no_household_rows | records=0  |
|   2004 | 金融机构人民币信贷收支表 Sources And Uses of Credit Funds of Financial Institutions                                       | no_household_rows | records=0  |
|   2003 | 金融机构人民币信贷收支表 Sources And Uses of Credit Funds of Financial Institutions                                       | no_household_rows | records=0  |
|   2002 | 金融机构人民币信贷收支表 Sources And Uses of Credit Funds of Financial Institutions                                       | no_household_rows | records=0  |
|   2001 | 金融机构人民币信贷收支表 单位：亿元 项目                                                                                  | no_household_rows | records=0  |
|   2000 | 金融机构人民币信贷收支表 单位：亿元 项目                                                                                  | no_household_rows | records=0  |

## NeoData 校验层

| query                                              | code   |   suc | recall_types   | status   | message                                                                     | run_at              |
|:---------------------------------------------------|:-------|------:|:---------------|:---------|:----------------------------------------------------------------------------|:--------------------|
| 70城新房 二手房 价格指数                           |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:02:49 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 房地产开发投资 商品房销售面积 新开工面积 月度 数据 |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:02:49 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 居民贷款 住户贷款 中长期贷款 月度 数据             |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:02:49 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 70城新房 二手房 价格指数                           |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:01:19 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 房地产开发投资 商品房销售面积 新开工面积 月度 数据 |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:01:19 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 居民贷款 住户贷款 中长期贷款 月度 数据             |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T12:01:18 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 70城新房 二手房 价格指数                           |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T11:41:11 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 房地产开发投资 商品房销售面积 新开工面积 月度 数据 |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T11:41:11 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 居民贷款 住户贷款 中长期贷款 月度 数据             |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T11:41:10 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |
| 70城新房 二手房 价格指数                           |        |     0 | []             | error    | Token 缓存已过期（超过 12 小时），需要重新获取                              | 2026-05-09T11:39:51 |
|                                                    |        |       |                |          | 错误: 未找到有效 token。请先运行 --save-token 保存，或使用 --token 参数传入 |                     |

## 最近数据源日志

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

## 重要限制

- PBC 居民新增贷款已优先用央行金融机构人民币信贷收支表余额月差自动生成；早年如缺少按部门住户贷款口径则不强行估算。
- 金融统计口径会因机构范围/统计制度调整产生跳变，重大月份需用央行月度金融统计报告文字交叉校验。
- westock-data 已覆盖房地产开发投资、商品房销售面积、销售额、新开工、竣工、待售和房企资金来源，可作为房地产供需主通道。
- NeoData 对居民贷款和房地产宏观查询可作为校验/搜索层，但自然语言召回存在噪声，不作为主库。
- 国家统计局官网接口当前可能返回403；本版用 Eastmoney/AkShare 镜像拉取70城房价和国房景气指数，并在数据库中保留 source 字段。
- 二手房成交套数没有统一全国官方月度序列，后续应按城市住建委/贝壳/中指等建立分层数据源。

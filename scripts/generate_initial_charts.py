#!/usr/bin/env python3
"""Generate China housing-cycle indicator charts."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "housing_cycle.sqlite"
CHART_DIR = ROOT / "reports" / "charts"
REPORT_PATH = ROOT / "reports" / "initial_indicator_charts.md"
START_DATE = "2018-01-01"

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 140


def load_obs() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT o.series_id, o.date, o.value, o.region, s.name, s.unit
        FROM observations o JOIN series s USING(series_id)
        """,
        conn,
        parse_dates=["date"],
    )
    conn.close()
    return df


def cn_pivot(obs: pd.DataFrame) -> pd.DataFrame:
    return obs[obs["region"] == "CN"].pivot_table(index="date", columns="series_id", values="value", aggfunc="last").sort_index()


def cn70_pivot(obs: pd.DataFrame) -> pd.DataFrame:
    return obs[obs["region"] == "CN70"].pivot_table(index="date", columns="series_id", values="value", aggfunc="last").sort_index()


def savefig(fig: plt.Figure, name: str) -> str:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return f"charts/{name}"


def format_axis(ax):
    ax.grid(True, axis="y", alpha=0.25)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for label in ax.get_xticklabels():
        label.set_rotation(0)
        label.set_fontsize(8)


def plot_window(series: pd.Series) -> pd.Series:
    return series.dropna().loc[START_DATE:]


def same_month_yoy(series: pd.Series) -> pd.Series:
    """Year-over-year change by calendar month; robust to NBS no-January publishing gaps."""
    s = series.dropna().sort_index()
    prev = s.copy()
    prev.index = prev.index + pd.DateOffset(years=1)
    prev = prev.reindex(s.index)
    return (s / prev - 1) * 100


def monthly_flow_from_cum(cum: pd.Series) -> pd.Series:
    """Convert NBS YTD cumulative series to published monthly flow.

    NBS real-estate development data has no standalone January release; Jan-Feb is
    published as February cumulative. This function preserves the official cadence.
    """
    cum = cum.dropna().sort_index()
    out = pd.Series(index=cum.index, dtype="float64")
    for dt, val in cum.items():
        if dt.month <= 2:
            out.loc[dt] = val
            continue
        prev_dt = dt - pd.DateOffset(months=1)
        if prev_dt in cum.index and prev_dt.year == dt.year:
            out.loc[dt] = val - cum.loc[prev_dt]
    return out.dropna()


def plot_credit_total(cn: pd.DataFrame) -> str:
    s = plot_window(cn["household_new_loans"])
    ma6 = s.rolling(6).mean()
    ma12 = s.rolling(12).mean()
    fig, ax = plt.subplots(figsize=(13, 5.4))
    colors = ["#9ecae1" if v >= 0 else "#f4a3a8" for v in s]
    ax.bar(s.index, s.values, width=20, color=colors, alpha=0.65, label="单月值")
    ax.plot(ma6.index, ma6, color="#0b5c6b", linewidth=2.2, label="6个月滚动平均")
    ax.plot(ma12.index, ma12, color="#d62728", linewidth=2.2, label="12个月滚动平均")
    ax.axhline(3000, color="#666", linestyle="--", linewidth=1, alpha=0.6, label="3000亿阈值")
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_title("全国居民每月新增贷款：主信号", fontsize=15, weight="bold")
    ax.set_ylabel("亿元")
    ax.legend(ncol=4, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "01_household_new_loans_ma.png")


def plot_credit_medium_long(cn: pd.DataFrame) -> str:
    s = plot_window(cn["household_medium_long_new_loans"])
    ma6 = s.rolling(6).mean()
    ma12 = s.rolling(12).mean()
    fig, ax = plt.subplots(figsize=(13, 5.4))
    colors = ["#9ecae1" if v >= 0 else "#f4a3a8" for v in s]
    ax.bar(s.index, s.values, width=20, color=colors, alpha=0.65, label="中长期单月值")
    ax.plot(ma6.index, ma6, color="#1f77b4", linewidth=2.2, label="6个月均值")
    ax.plot(ma12.index, ma12, color="#ff7f0e", linewidth=2.2, label="12个月均值")
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_title("住户中长期新增贷款：更贴近按揭需求", fontsize=15, weight="bold")
    ax.set_ylabel("亿元")
    ax.legend(ncol=3, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "02_household_medium_long_loans_ma.png")


def plot_sales_yoy(cn: pd.DataFrame) -> str:
    area_yoy = same_month_yoy(cn["re_sales_area_current"])
    avg_price = cn["re_sales_revenue_cum"] / cn["re_sales_area_cum"]
    price_yoy = same_month_yoy(avg_price)
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.plot(plot_window(area_yoy).index, plot_window(area_yoy), color="#1f77b4", linewidth=2, marker="o", markersize=2.5, label="商品房销售面积当月同比")
    ax.plot(plot_window(price_yoy).index, plot_window(price_yoy), color="#d62728", linewidth=2, marker="o", markersize=2.5, label="全国新房累计销售均价同比")
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_title("需求与价格质量：销售面积同比 vs 销售均价同比", fontsize=15, weight="bold")
    ax.set_ylabel("%")
    ax.legend(ncol=2, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "03_sales_area_and_price_yoy.png")


def plot_price_breadth(br: pd.DataFrame) -> str:
    br = br.loc[START_DATE:]
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.plot(br.index, br["new_home_positive_city_share"], color="#1f77b4", linewidth=2, label="新房环比上涨城市占比")
    ax.plot(br.index, br["second_home_positive_city_share"], color="#2ca02c", linewidth=2, label="二手房环比上涨城市占比")
    ax.axhline(50, color="#d62728", linestyle="--", linewidth=1, alpha=0.7, label="50%扩散线")
    ax.axhline(30, color="#ff7f0e", linestyle="--", linewidth=1, alpha=0.6, label="30%观察线")
    ax.set_title("70城价格扩散：环比上涨城市占比", fontsize=15, weight="bold")
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.legend(ncol=4, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "04_70city_price_breadth.png")


def plot_supply_demand(cn: pd.DataFrame) -> str:
    sales_area = cn["re_sales_area_cum"] / 10000
    ratio_start = cn["re_new_start_area_cum"] / 10000 / sales_area
    ratio_completion = cn["re_completion_area_cum"] / 10000 / sales_area
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.plot(plot_window(ratio_start).index, plot_window(ratio_start), color="#9467bd", linewidth=2, marker="o", markersize=2.5, label="新开工/销售面积累计比")
    ax.plot(plot_window(ratio_completion).index, plot_window(ratio_completion), color="#8c564b", linewidth=2, marker="o", markersize=2.5, label="竣工/销售面积累计比")
    ax.axhline(1, color="#d62728", linestyle="--", linewidth=1, alpha=0.7, label="供需平衡线=1")
    ax.set_title("供给收缩：新开工、竣工相对销售", fontsize=15, weight="bold")
    ax.set_ylabel("倍")
    ax.legend(ncol=3, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "05_supply_demand_ratio.png")


def plot_funding(cn: pd.DataFrame) -> str:
    deposit_yoy = same_month_yoy(cn["re_cap_deposit_cum"])
    loan_yoy = same_month_yoy(cn["re_cap_loan_cum"])
    self_yoy = same_month_yoy(cn["re_cap_self_cum"])
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.plot(plot_window(deposit_yoy).index, plot_window(deposit_yoy), linewidth=2, marker="o", markersize=2.5, label="定金及预收款累计同比")
    ax.plot(plot_window(loan_yoy).index, plot_window(loan_yoy), linewidth=2, marker="o", markersize=2.5, label="国内贷款累计同比")
    ax.plot(plot_window(self_yoy).index, plot_window(self_yoy), linewidth=2, marker="o", markersize=2.5, label="自筹资金累计同比")
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_title("房企资金来源：销售回款与融资端", fontsize=15, weight="bold")
    ax.set_ylabel("%")
    ax.legend(ncol=3, fontsize=9, loc="upper right")
    format_axis(ax)
    return savefig(fig, "06_developer_funding_yoy.png")


def plot_inventory(cn: pd.DataFrame) -> str:
    for_sale = cn["re_for_sale_area"].dropna()
    sales_flow = monthly_flow_from_cum(cn["re_sales_area_cum"] / 10000)
    ttm_sales = sales_flow.rolling(12, min_periods=9).sum()
    months = (for_sale / ttm_sales * 12).replace([float("inf"), -float("inf")], pd.NA)
    fig, ax1 = plt.subplots(figsize=(13, 5.4))
    ax1.plot(plot_window(for_sale).index, plot_window(for_sale), color="#1f77b4", linewidth=2, label="商品房待售面积")
    ax1.set_ylabel("万平方米", color="#1f77b4")
    ax2 = ax1.twinx()
    ax2.plot(plot_window(months).index, plot_window(months), color="#d62728", linewidth=2, label="粗略去化月数")
    ax2.set_ylabel("月", color="#d62728")
    ax1.set_title("库存压力：待售面积与粗略去化月数", fontsize=15, weight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, ncol=2, fontsize=9, loc="upper left")
    format_axis(ax1)
    return savefig(fig, "07_inventory_destocking.png")


def plot_climate_investment(cn: pd.DataFrame) -> str:
    climate = cn["real_estate_climate_index"].dropna()
    inv_yoy = same_month_yoy(cn["re_investment_cum"])
    fig, ax1 = plt.subplots(figsize=(13, 5.4))
    ax1.plot(plot_window(climate).index, plot_window(climate), color="#1f77b4", linewidth=2, label="国房景气指数")
    ax1.axhline(95, color="#ff7f0e", linestyle="--", linewidth=1, alpha=0.7, label="95低景气线")
    ax1.axhline(100, color="#2ca02c", linestyle="--", linewidth=1, alpha=0.5, label="100适中线")
    ax1.set_ylabel("指数点", color="#1f77b4")
    ax2 = ax1.twinx()
    ax2.plot(plot_window(inv_yoy).index, plot_window(inv_yoy), color="#d62728", linewidth=1.8, alpha=0.85, marker="o", markersize=2.5, label="开发投资累计同比")
    ax2.axhline(0, color="#333", linewidth=0.7)
    ax2.set_ylabel("%", color="#d62728")
    ax1.set_title("开发景气：国房景气指数与开发投资同比", fontsize=15, weight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, ncol=4, fontsize=9, loc="upper right")
    format_axis(ax1)
    return savefig(fig, "08_climate_and_investment.png")


def write_report(paths: list[tuple[str, str, str]]) -> None:
    content = [
        "# 地产辅助指标可视化初版\n",
        f"\n生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n",
        "\n## 口径更新\n",
        "\n- 图表时间范围统一为 `2018-至今`。\n",
        "- 国家统计局房地产开发销售数据为 `1-2月、1-3月...` 累计口径，且官方说明 `1月份除外`，因此 1 月缺口不是抓取错误。\n",
        "- 同比计算改为按同一自然月份对比，避免 `pct_change(12)` 在缺 1 月时错配月份。\n",
        "\n## 初版图表清单\n",
    ]
    for i, (title, path, note) in enumerate(paths, 1):
        content.append(f"\n### {i}. {title}\n\n{note}\n\n![{title}]({path})\n")
    REPORT_PATH.write_text("".join(content), encoding="utf-8")


def main() -> int:
    obs = load_obs()
    cn = cn_pivot(obs)
    br = cn70_pivot(obs)
    chart_paths = [
        ("全国居民每月新增贷款：主信号", plot_credit_total(cn), "你的核心指标，观察 6M/12M 是否双站上 3000 亿并上穿。"),
        ("销售面积同比 vs 销售均价同比", plot_sales_yoy(cn), "销售面积采用同月同比；均价由销售额/销售面积估算。"),
        ("70城价格扩散：上涨城市占比", plot_price_breadth(br), "观察新房/二手房价格修复是否从少数城市扩散到多数城市。"),
        ("供给收缩：新开工、竣工相对销售", plot_supply_demand(cn), "销售强于新开工/竣工时，有利于库存出清。"),
        ("房企资金来源：销售回款与融资端", plot_funding(cn), "定金预收款反映购房付款，国内贷款反映房企融资修复。"),
        ("库存压力：待售面积与粗略去化月数", plot_inventory(cn), "待售面积是狭义库存，去化月数用于观察库存压力。"),
        ("开发景气：国房景气指数与开发投资同比", plot_climate_investment(cn), "国房景气指数是统计局综合景气指标，投资同比按同月累计口径计算。"),
    ]
    write_report(chart_paths)
    print(REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

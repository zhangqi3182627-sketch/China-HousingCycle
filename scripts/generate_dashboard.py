#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard for the housing-cycle tracker."""
from __future__ import annotations

import argparse
import base64
import html
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import generate_initial_charts as chartlib

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "housing_cycle.sqlite"
MANUAL_DIR = ROOT / "data" / "manual"
REPORT_DIR = ROOT / "reports"
DASHBOARD_PATH = REPORT_DIR / "dashboard.html"
BUILD_SCRIPT = ROOT / "scripts" / "build_housing_cycle_db.py"
START_DATE = "2018-01-01"
TOP10_CITIES = ["北京", "上海", "深圳", "广州", "杭州", "南京", "天津", "成都", "武汉", "重庆"]

CHART_SPECS = [
    ("主信号：居民每月新增贷款", chartlib.plot_credit_total, "credit_total", "观察 6M/12M 是否双站上 3000 亿并形成多头排列。"),
    ("需求与价格：销售面积同比 vs 销售均价同比", chartlib.plot_sales_yoy, "sales_yoy", "销售面积采用同月同比，均价由销售额/销售面积估算。"),
    ("价格扩散：70城环比上涨城市占比", chartlib.plot_price_breadth, "price_breadth", "观察修复是否从少数城市扩散到多数城市。"),
    ("供给收缩：新开工、竣工相对销售", chartlib.plot_supply_demand, "supply_demand", "销售强于新开工/竣工时，有利于库存出清。"),
    ("房企资金来源：销售回款与融资端", chartlib.plot_funding, "funding", "定金预收款看销售回款，国内贷款看房企融资修复。"),
    ("库存压力：待售面积与粗略去化月数", chartlib.plot_inventory, "inventory", "狭义现房库存口径，适合观察库存压力方向。"),
    ("开发景气：国房景气指数与投资同比", chartlib.plot_climate_investment, "climate", "综合景气与开发端收缩/修复观察项。"),
]


def run_refresh_data() -> None:
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def read_sql(conn: sqlite3.Connection, sql: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, parse_dates=parse_dates)


def read_csv_safe(path: Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=parse_dates)


def fmt_num(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}{suffix}"


def fmt_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return pd.to_datetime(value).strftime("%Y-%m")


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def image_data_uri(relative_path: str) -> str:
    path = REPORT_DIR / relative_path
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_charts() -> list[dict[str, str]]:
    obs = chartlib.load_obs()
    cn = chartlib.cn_pivot(obs)
    br = chartlib.cn70_pivot(obs)
    chart_rows = []
    for title, func, anchor, note in CHART_SPECS:
        relative = func(br) if func is chartlib.plot_price_breadth else func(cn)
        chart_rows.append({"title": title, "anchor": anchor, "note": note, "relative": relative, "data_uri": image_data_uri(relative)})
    return chart_rows


def latest_top10_nbs(obs: pd.DataFrame) -> pd.DataFrame:
    rows = obs[(obs["region"].isin(TOP10_CITIES)) & (obs["series_id"].isin(["second_home_price_mom", "second_home_price_yoy"]))]
    if rows.empty:
        return pd.DataFrame()
    latest_date = rows["date"].max()
    pivot = rows[rows["date"] == latest_date].pivot_table(index="region", columns="series_id", values="value", aggfunc="last")
    pivot = pivot.reindex(TOP10_CITIES).reset_index().rename(columns={"region": "city"})
    pivot["date"] = latest_date
    pivot["mom_pct"] = pivot["second_home_price_mom"] - 100
    pivot["yoy_pct"] = pivot["second_home_price_yoy"] - 100
    return pivot[["date", "city", "second_home_price_mom", "mom_pct", "second_home_price_yoy", "yoy_pct"]]


def load_dashboard_data() -> dict[str, Any]:
    conn = connect()
    model = read_sql(conn, "SELECT * FROM model_signals ORDER BY date", parse_dates=["date"])
    sources = read_sql(
        conn,
        """
        SELECT s.source,s.status,s.rows,s.message,s.run_at
        FROM source_log s
        JOIN (SELECT source, MAX(id) AS id FROM source_log GROUP BY source) latest USING(source,id)
        ORDER BY s.id DESC
        """,
    )
    obs = read_sql(conn, "SELECT o.series_id,o.date,o.value,o.region,s.unit FROM observations o JOIN series s USING(series_id)", parse_dates=["date"])
    conn.close()

    cn = obs[obs["region"] == "CN"].pivot_table(index="date", columns="series_id", values="value", aggfunc="last").sort_index()
    br = obs[obs["region"] == "CN70"].pivot_table(index="date", columns="series_id", values="value", aggfunc="last").sort_index()
    latest = model.iloc[-1] if not model.empty else pd.Series(dtype=object)
    latest_date = latest.get("date") if not latest.empty else None

    aux_rows: list[dict[str, str]] = []

    def add_aux(name: str, value: Any, unit: str, date: Any, note: str, good_rule: str = "") -> None:
        aux_rows.append({"name": name, "value": fmt_num(value, 2), "unit": unit, "date": fmt_date(date), "note": note, "good_rule": good_rule})

    if not cn.empty:
        target_date = latest_date if latest_date in cn.index else cn.index.max()
        sales = cn.get("re_sales_area_current")
        if sales is not None:
            add_aux("商品房销售面积当月同比", chartlib.same_month_yoy(sales).get(target_date), "%", target_date, "需求端成交热度", ">0 或降幅持续收窄")
        if "re_sales_revenue_cum" in cn and "re_sales_area_cum" in cn:
            avg_price = cn["re_sales_revenue_cum"] / cn["re_sales_area_cum"]
            add_aux("全国新房累计销售均价同比", chartlib.same_month_yoy(avg_price).get(target_date), "%", target_date, "销售额/销售面积", ">0 或止跌")
        if "re_new_start_area_cum" in cn and "re_sales_area_cum" in cn:
            sales_area = cn["re_sales_area_cum"] / 10000
            add_aux("新开工/销售面积累计比", (cn["re_new_start_area_cum"] / 10000 / sales_area).get(target_date), "倍", target_date, "供给扩张/收缩强度", "低位有利去库存")
        if "re_completion_area_cum" in cn and "re_sales_area_cum" in cn:
            sales_area = cn["re_sales_area_cum"] / 10000
            add_aux("竣工/销售面积累计比", (cn["re_completion_area_cum"] / 10000 / sales_area).get(target_date), "倍", target_date, "交付压力与库存释放", "下行代表压力缓和")
        if "re_for_sale_area" in cn and "re_sales_area_cum" in cn:
            flow = chartlib.monthly_flow_from_cum(cn["re_sales_area_cum"] / 10000)
            months = cn["re_for_sale_area"] / flow.rolling(12, min_periods=9).sum() * 12
            inv_date = months.dropna().index.max() if not months.dropna().empty else target_date
            add_aux("商品房待售去化月数", months.get(inv_date), "月", inv_date, "狭义现房库存压力", "持续下降更优")
        for sid, name in [("re_cap_deposit_cum", "定金及预收款累计同比"), ("re_cap_loan_cum", "房企国内贷款累计同比"), ("re_cap_self_cum", "房企自筹资金累计同比")]:
            if sid in cn:
                add_aux(name, chartlib.same_month_yoy(cn[sid]).get(target_date), "%", target_date, "房企资金来源修复", ">0 或降幅收窄")
        if "real_estate_climate_index" in cn:
            climate = cn["real_estate_climate_index"].dropna()
            if not climate.empty:
                add_aux("国房景气指数", climate.iloc[-1], "点", climate.index[-1], "统计局综合景气指标", ">95 修复，>100 偏热")

    if not br.empty:
        br_date = br.dropna(how="all").index.max()
        for sid, name in [("new_home_positive_city_share", "70城新房上涨城市占比"), ("second_home_positive_city_share", "70城二手房上涨城市占比")]:
            if sid in br:
                add_aux(name, br[sid].get(br_date), "%", br_date, "价格修复扩散度", ">30% 观察，>50% 扩散")

    loan_quarterly = read_csv_safe(MANUAL_DIR / "pbc_real_estate_loan_quarterly.csv", parse_dates=["date"])
    creis_top10 = read_csv_safe(MANUAL_DIR / "creis_top10_second_hand_listing.csv", parse_dates=["date"])
    weights = read_csv_safe(MANUAL_DIR / "model_weight_scheme.csv")
    nbs_top10 = latest_top10_nbs(obs)

    return {
        "model": model,
        "latest": latest,
        "sources": sources,
        "aux_rows": aux_rows,
        "loan_quarterly": loan_quarterly,
        "creis_top10": creis_top10,
        "nbs_top10": nbs_top10,
        "weights": weights,
    }


def render_table(df: pd.DataFrame, columns: list[str], headers: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "<p class='muted'>暂无数据。</p>"
    view = df.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    head = "".join(f"<th>{html_escape(h)}</th>" for h in headers)
    rows = []
    for _, row in view.iterrows():
        cells = "".join(f"<td>{html_escape(row.get(col, ''))}</td>" for col in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def prepare_display_tables(data: dict[str, Any]) -> dict[str, str]:
    loan = data["loan_quarterly"].copy()
    if not loan.empty:
        loan["date"] = loan["date"].dt.strftime("%Y-%m")
        for col in [c for c in loan.columns if c.endswith("_trillion_cny") or c.endswith("_pct") or c.endswith("_yi")]:
            loan[col] = loan[col].map(lambda x: fmt_num(x, 2))
    loan_table = render_table(
        loan,
        ["date", "personal_mortgage_balance_trillion_cny", "personal_mortgage_yoy_pct", "personal_mortgage_qoq_change_yi", "real_estate_loan_balance_trillion_cny", "real_estate_loan_yoy_pct", "developer_loan_balance_trillion_cny", "developer_loan_yoy_pct", "source"],
        ["季度", "个人住房贷款余额(万亿)", "同比%", "当季增减(亿)", "房地产贷款余额(万亿)", "同比%", "开发贷余额(万亿)", "同比%", "来源"],
        max_rows=8,
    )

    creis = data["creis_top10"].copy()
    if not creis.empty:
        creis["date"] = creis["date"].dt.strftime("%Y-%m")
        for col in ["listing_price_yuan_sqm", "mom_pct", "yoy_pct"]:
            creis[col] = creis[col].map(lambda x: fmt_num(x, 2))
    creis_table = render_table(creis, ["date", "city", "listing_price_yuan_sqm", "mom_pct", "yoy_pct", "source"], ["月份", "城市", "挂牌均价 元/㎡", "环比%", "同比%", "来源"])

    nbs = data["nbs_top10"].copy()
    if not nbs.empty:
        nbs["date"] = nbs["date"].dt.strftime("%Y-%m")
        for col in ["second_home_price_mom", "mom_pct", "second_home_price_yoy", "yoy_pct"]:
            nbs[col] = nbs[col].map(lambda x: fmt_num(x, 2))
    nbs_table = render_table(nbs, ["date", "city", "second_home_price_mom", "mom_pct", "second_home_price_yoy", "yoy_pct"], ["月份", "城市", "NBS二手房环比指数", "换算环比%", "NBS二手房同比指数", "换算同比%"])

    weights = data["weights"].copy()
    weight_table = render_table(weights, ["module", "weight", "indicators", "score_rule", "notes"], ["模块", "权重", "指标", "评分规则", "说明"])
    return {"loan_table": loan_table, "creis_table": creis_table, "nbs_table": nbs_table, "weight_table": weight_table}


def render_html(data: dict[str, Any], chart_rows: list[dict[str, str]]) -> str:
    latest = data["latest"]
    signal = str(latest.get("main_signal", "DATA_INSUFFICIENT")) if not latest.empty else "DATA_INSUFFICIENT"
    signal_class = "red" if signal.startswith("RED") else "yellow" if signal.startswith("YELLOW") else "green"
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tables = prepare_display_tables(data)

    cards = [
        ("最新月份", fmt_date(latest.get("date") if not latest.empty else None), "数据模型最新月"),
        ("主信号", signal, latest.get("recommendation", "") if not latest.empty else ""),
        ("居民新增贷款", f"{fmt_num(latest.get('household_new_loans') if not latest.empty else None)} 亿", "单月值"),
        ("6M 均值", f"{fmt_num(latest.get('household_ma6') if not latest.empty else None)} 亿", "核心阈值 3000 亿"),
        ("12M 均值", f"{fmt_num(latest.get('household_ma12') if not latest.empty else None)} 亿", "核心阈值 3000 亿"),
        ("综合分", fmt_num(latest.get("composite_score") if not latest.empty else None, 0), "当前旧版模型分数"),
    ]
    card_html = "".join(
        f"<div class='card {signal_class if title == '主信号' else ''}'><div class='card-title'>{html_escape(title)}</div><div class='card-value'>{html_escape(value)}</div><div class='card-note'>{html_escape(note)}</div></div>"
        for title, value, note in cards
    )

    aux_df = pd.DataFrame(data["aux_rows"])
    aux_table = render_table(aux_df, ["name", "date", "value", "unit", "good_rule", "note"], ["指标", "日期", "数值", "单位", "观察阈值", "说明"])

    src = data["sources"].copy()
    if not src.empty:
        src["run_at"] = src["run_at"].astype(str).str.replace("T", " ", regex=False)
    src_table = render_table(src, ["source", "status", "rows", "message", "run_at"], ["数据源", "状态", "行数", "信息", "更新时间"])

    chart_html = "".join(
        f"""
        <section class='chart-card' id='{html_escape(c['anchor'])}'>
          <div class='chart-head'>
            <h3>{html_escape(c['title'])}</h3>
            <p>{html_escape(c['note'])}</p>
          </div>
          <img src='{c['data_uri']}' alt='{html_escape(c['title'])}'>
        </section>
        """
        for c in chart_rows
    )

    nav = "".join(f"<a href='#{html_escape(c['anchor'])}'>{i}. {html_escape(c['title'])}</a>" for i, c in enumerate(chart_rows, 1))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>房地产周期月度追踪 Dashboard</title>
  <style>
    :root {{ --bg:#f5f7fb; --panel:#ffffff; --ink:#182033; --muted:#667085; --line:#e6eaf2; --red:#b42318; --yellow:#b54708; --green:#027a48; --blue:#155eef; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif; color:var(--ink); background:var(--bg); }}
    header {{ padding:34px 42px 26px; background:linear-gradient(135deg,#102a43,#155eef); color:#fff; }}
    header h1 {{ margin:0 0 10px; font-size:30px; }}
    header p {{ margin:4px 0; color:#dbe7ff; }}
    main {{ max-width:1400px; margin:0 auto; padding:26px 28px 60px; }}
    .toolbar {{ display:flex; gap:10px; flex-wrap:wrap; margin:0 0 22px; }}
    .toolbar a {{ color:#155eef; background:#fff; border:1px solid var(--line); border-radius:999px; padding:8px 12px; text-decoration:none; font-size:13px; }}
    .cards {{ display:grid; grid-template-columns:repeat(6,minmax(150px,1fr)); gap:14px; margin-bottom:22px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(16,42,67,.06); }}
    .card-title {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
    .card-value {{ font-size:24px; font-weight:800; word-break:break-word; }}
    .card-note {{ color:var(--muted); font-size:12px; margin-top:8px; line-height:1.45; }}
    .card.red .card-value {{ color:var(--red); }} .card.yellow .card-value {{ color:var(--yellow); }} .card.green .card-value {{ color:var(--green); }}
    .section {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:20px; margin:20px 0; box-shadow:0 8px 24px rgba(16,42,67,.05); }}
    .section h2 {{ margin:0 0 12px; font-size:22px; }}
    .section h3 {{ margin:18px 0 10px; font-size:17px; }}
    .chart-card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; margin:20px 0; box-shadow:0 8px 24px rgba(16,42,67,.05); }}
    .chart-head {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:8px; }}
    .chart-head h3 {{ margin:0; font-size:20px; }}
    .chart-head p,.muted {{ margin:0; color:var(--muted); line-height:1.55; }}
    img {{ width:100%; border-radius:12px; border:1px solid var(--line); background:#fff; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:9px 8px; text-align:left; vertical-align:top; }}
    th {{ color:#344054; background:#f8fafc; position:sticky; top:0; }}
    .table-wrap {{ overflow:auto; max-height:560px; border:1px solid var(--line); border-radius:12px; }}
    code {{ background:#eef2ff; color:#1d2939; padding:2px 6px; border-radius:6px; }}
    pre {{ background:#111827; color:#f9fafb; padding:14px 16px; border-radius:12px; overflow:auto; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
    @media (max-width:1100px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} .grid2 {{ grid-template-columns:1fr; }} header {{ padding:26px 22px; }} main {{ padding:20px 16px 42px; }} }}
  </style>
</head>
<body>
<header>
  <h1>房地产周期月度追踪 Dashboard</h1>
  <p>核心逻辑：居民部门重新扩表是商品房周期见底的主信号；销售、二手房价格趋势、库存去化、供给和资金为辅助确认。</p>
  <p>图表范围：2018 至今 ｜ 生成时间：{html_escape(update_time)} ｜ 文件：<code>reports/dashboard.html</code></p>
</header>
<main>
  <nav class="toolbar">{nav}</nav>
  <div class="cards">{card_html}</div>

  <section class="section">
    <h2>怎么随时调用</h2>
    <p>本页是自包含 HTML，图片已内嵌，打开 <code>HousingCycle/reports/dashboard.html</code> 即可查看。刷新最新数据和网页：</p>
    <pre>cd /Users/qizhang/CodeBuddy/Claw/HousingCycle
python3 scripts/run_monthly_update.py</pre>
    <p>如果只想基于现有数据库重画网页：</p>
    <pre>python3 scripts/generate_dashboard.py</pre>
  </section>

  <section class="section">
    <h2>模型权重方案 v0.1</h2>
    <p class="muted">主信号按你的要求固定 50%；其余指标只做辅助确认，不替代主信号。正式分档建议后续在你确认权重后写入模型表。</p>
    <div class="table-wrap">{tables['weight_table']}</div>
  </section>

  <section class="section">
    <h2>辅助指标快照</h2>
    <div class="table-wrap">{aux_table}</div>
  </section>

  <section class="section">
    <h2>新增数据表</h2>
    <h3>个人住房贷款余额 / 房地产贷款余额 / 开发贷余额</h3>
    <div class="table-wrap">{tables['loan_table']}</div>
    <h3>核心10城二手房成交/调查价格趋势：NBS 价格指数代理</h3>
    <div class="table-wrap">{tables['nbs_table']}</div>
    <h3>十大城市二手房挂牌价：中指数据 CREIS</h3>
    <div class="table-wrap">{tables['creis_table']}</div>
  </section>

  {chart_html}

  <section class="section">
    <h2>数据源最新状态</h2>
    <div class="table-wrap">{src_table}</div>
  </section>
</main>
</body>
</html>
"""


def write_dashboard(refresh_data: bool = False) -> Path:
    if refresh_data:
        run_refresh_data()
    chart_rows = generate_charts()
    data = load_dashboard_data()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(render_html(data, chart_rows), encoding="utf-8")
    return DASHBOARD_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HousingCycle HTML dashboard.")
    parser.add_argument("--refresh-data", action="store_true", help="Run build_housing_cycle_db.py before rendering dashboard.")
    args = parser.parse_args()
    print(write_dashboard(refresh_data=args.refresh_data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

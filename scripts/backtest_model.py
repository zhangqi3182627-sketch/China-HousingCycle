#!/usr/bin/env python3
"""Backtest HousingCycle signals and v0.3 composite score."""
from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "housing_cycle.sqlite"
REPORT_DIR = ROOT / "reports"
BACKTEST_HTML = REPORT_DIR / "backtest.html"
BACKTEST_SUMMARY = REPORT_DIR / "backtest_summary.csv"


def fmt(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (int, float, np.floating)):
        return f"{float(value):,.{digits}f}"
    return str(value)


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def table_html(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "<p class='muted'>暂无数据。</p>"
    view = df.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    head = "".join(f"<th>{escape(c)}</th>" for c in view.columns)
    rows = []
    for _, row in view.iterrows():
        rows.append("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in row.tolist()) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def same_month_yoy(series: pd.Series) -> pd.Series:
    s = series.dropna().sort_index()
    prev = s.copy()
    prev.index = prev.index + pd.DateOffset(years=1)
    prev = prev.reindex(s.index)
    return (s / prev - 1) * 100


def load_series(conn: sqlite3.Connection, series_id: str, region: str | None = None) -> pd.Series:
    sql = "SELECT date,value FROM observations WHERE series_id=?"
    params: list[Any] = [series_id]
    if region:
        sql += " AND region=?"
        params.append(region)
    sql += " ORDER BY date"
    df = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
    if df.empty:
        return pd.Series(dtype="float64")
    return df.drop_duplicates("date").set_index("date")["value"].sort_index()


def build_panel(conn: sqlite3.Connection) -> pd.DataFrame:
    model = pd.read_sql_query("SELECT * FROM model_signals ORDER BY date", conn, parse_dates=["date"]).set_index("date")
    new_share = load_series(conn, "new_home_positive_city_share", "CN70")
    second_share = load_series(conn, "second_home_positive_city_share", "CN70")
    sales = load_series(conn, "re_sales_area_current", "CN")
    sales_yoy = same_month_yoy(sales)
    panel = model.join(pd.DataFrame({"new_share": new_share, "second_share": second_share, "sales_yoy": sales_yoy}), how="left")
    return panel


def future_average(panel: pd.DataFrame, col: str, months: int) -> pd.Series:
    values = []
    for dt in panel.index:
        window = panel.loc[(panel.index > dt) & (panel.index <= dt + pd.DateOffset(months=months)), col].dropna()
        values.append(np.nan if window.empty else float(window.mean()))
    return pd.Series(values, index=panel.index)


def add_targets(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    for h in (6, 12):
        out[f"f{h}_new_share_avg"] = future_average(out, "new_share", h)
        out[f"f{h}_second_share_avg"] = future_average(out, "second_share", h)
        out[f"f{h}_sales_yoy_avg"] = future_average(out, "sales_yoy", h)
        out[f"f{h}_price_recovery"] = (out[f"f{h}_new_share_avg"] >= 50) | (out[f"f{h}_second_share_avg"] >= 50)
        out[f"f{h}_sales_recovery"] = out[f"f{h}_sales_yoy_avg"] >= 0
        out[f"f{h}_combined_recovery"] = out[f"f{h}_price_recovery"] & out[f"f{h}_sales_recovery"]
    return out


def rate(x: pd.Series) -> float:
    if len(x) == 0:
        return np.nan
    return float(x.mean() * 100)


def build_summary(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    accuracy_rows: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    target_map = {
        "price_recovery": "未来价格扩散修复",
        "sales_recovery": "未来销售同比转正",
        "combined_recovery": "未来价格+销售同时修复",
    }
    score_bins = [-np.inf, 40, 60, 75, np.inf]
    score_labels = ["<40", "40-59", "60-74", "75+"]

    for h in (6, 12):
        valid = panel.index <= (panel.index.max() - pd.DateOffset(months=h))
        bt = panel[valid & (panel["main_signal"] != "DATA_INSUFFICIENT")].copy()
        bt["score_bucket"] = pd.cut(bt["composite_score"], bins=score_bins, labels=score_labels, right=False)
        for key, title in target_map.items():
            target = f"f{h}_{key}"
            for signal, grp in bt.groupby("main_signal", dropna=False):
                rows.append({
                    "horizon": f"{h}M",
                    "target": title,
                    "group_type": "main_signal",
                    "group": signal,
                    "n": int(len(grp)),
                    "future_hit_rate_pct": rate(grp[target]),
                })
            for bucket, grp in bt.groupby("score_bucket", observed=False):
                if len(grp) == 0:
                    continue
                bucket_rows.append({
                    "horizon": f"{h}M",
                    "target": title,
                    "score_bucket": str(bucket),
                    "n": int(len(grp)),
                    "future_hit_rate_pct": rate(grp[target]),
                    "avg_score": float(grp["composite_score"].mean()),
                })
            judged = bt[bt["main_signal"].isin(["GREEN_CANDIDATE", "RED_NO_BOTTOM"])].copy()
            if not judged.empty:
                hits = np.where(judged["main_signal"].eq("GREEN_CANDIDATE"), judged[target], ~judged[target])
                accuracy_rows.append({
                    "horizon": f"{h}M",
                    "target": title,
                    "judged_signals": "GREEN predicts True; RED predicts False; YELLOW excluded",
                    "n": int(len(judged)),
                    "directional_accuracy_pct": float(np.mean(hits) * 100),
                })
    return pd.DataFrame(rows), pd.DataFrame(bucket_rows), pd.DataFrame(accuracy_rows)


def format_output(summary: pd.DataFrame, buckets: pd.DataFrame, accuracy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    def clean(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in ["future_hit_rate_pct", "directional_accuracy_pct", "avg_score"]:
            if col in out:
                out[col] = out[col].map(lambda x: fmt(x, 1))
        return out
    return clean(summary), clean(buckets), clean(accuracy)


def render_html(panel: pd.DataFrame, summary: pd.DataFrame, buckets: pd.DataFrame, accuracy: pd.DataFrame) -> str:
    latest = panel.iloc[-1] if not panel.empty else pd.Series(dtype=object)
    display_summary, display_buckets, display_accuracy = format_output(summary, buckets, accuracy)
    latest_month = panel.index.max().strftime("%Y-%m") if not panel.empty else "—"
    start_month = panel.index.min().strftime("%Y-%m") if not panel.empty else "—"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>房地产周期模型历史回测</title>
  <style>
    :root {{ --bg:#f5f7fb; --panel:#fff; --line:#e6eaf2; --ink:#182033; --muted:#667085; --blue:#155eef; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif; color:var(--ink); background:var(--bg); }}
    header {{ padding:34px 42px 26px; color:#fff; background:linear-gradient(135deg,#102a43,#155eef); }}
    header h1 {{ margin:0 0 10px; }} header p {{ color:#dbe7ff; margin:4px 0; }}
    main {{ max-width:1280px; margin:0 auto; padding:26px 28px 60px; }}
    .section {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:20px; margin:20px 0; box-shadow:0 8px 24px rgba(16,42,67,.05); }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(160px,1fr)); gap:14px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; }}
    .card-title {{ color:var(--muted); font-size:13px; }} .card-value {{ font-size:24px; font-weight:800; margin-top:8px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ border-bottom:1px solid var(--line); padding:9px 8px; text-align:left; vertical-align:top; }} th {{ background:#f8fafc; }}
    .table-wrap {{ overflow:auto; max-height:620px; border:1px solid var(--line); border-radius:12px; }} .muted {{ color:var(--muted); line-height:1.6; }}
    a {{ color:var(--blue); }}
  </style>
</head>
<body>
<header>
  <h1>房地产周期模型历史回测</h1>
  <p>回测区间：{escape(start_month)} 至 {escape(latest_month)} ｜ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  <p>说明：当前为方向性回测，检验信贷主信号和 v0.3 综合分对未来价格扩散、销售修复的预测能力。</p>
</header>
<main>
  <div class="cards">
    <div class="card"><div class="card-title">最新月份</div><div class="card-value">{escape(latest_month)}</div></div>
    <div class="card"><div class="card-title">最新主信号</div><div class="card-value">{escape(latest.get('main_signal', '—'))}</div></div>
    <div class="card"><div class="card-title">最新综合分</div><div class="card-value">{fmt(latest.get('composite_score'), 0)}</div></div>
    <div class="card"><div class="card-title">历史样本数</div><div class="card-value">{len(panel)}</div></div>
  </div>

  <section class="section">
    <h2>方向性准确率</h2>
    <p class="muted">只评价明确的 GREEN/RED：GREEN 预测未来修复，RED 预测未来不修复；YELLOW 作为观察区，不纳入命中率。</p>
    <div class="table-wrap">{table_html(display_accuracy)}</div>
  </section>

  <section class="section">
    <h2>不同主信号后的未来表现</h2>
    <p class="muted">表中命中率表示该信号出现后，未来 6/12 个月目标成立的比例。</p>
    <div class="table-wrap">{table_html(display_summary)}</div>
  </section>

  <section class="section">
    <h2>v0.3 综合分分层表现</h2>
    <p class="muted">用于检验综合分越高，未来修复概率是否越高。</p>
    <div class="table-wrap">{table_html(display_buckets)}</div>
  </section>

  <section class="section">
    <h2>回测口径</h2>
    <ul class="muted">
      <li>价格修复：未来窗口内 70 城新房或二手房环比上涨城市占比均值 ≥ 50%。</li>
      <li>销售修复：未来窗口内商品房销售面积当月同比均值 ≥ 0。</li>
      <li>综合修复：价格修复和销售修复同时成立。</li>
      <li>该回测是方向性验证，不等同于交易收益回测，也未处理数据发布滞后；正式版可继续加入发布时间滞后和样本外验证。</li>
    </ul>
  </section>
</main>
</body>
</html>
"""


def write_backtest() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    panel = add_targets(build_panel(conn))
    conn.close()
    summary, buckets, accuracy = build_summary(panel)
    summary.to_csv(BACKTEST_SUMMARY, index=False)
    BACKTEST_HTML.write_text(render_html(panel, summary, buckets, accuracy), encoding="utf-8")
    return BACKTEST_HTML


def main() -> int:
    path = write_backtest()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

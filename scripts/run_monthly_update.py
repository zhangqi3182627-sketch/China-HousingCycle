#!/usr/bin/env python3
"""Monthly HousingCycle update pipeline.

Steps:
1. refresh source database;
2. render self-contained HTML dashboard;
3. write a compact monthly markdown report for archive/search.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import generate_dashboard

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "housing_cycle.sqlite"
REPORT_DIR = ROOT / "reports"
MONTHLY_DIR = REPORT_DIR / "monthly"
BUILD_SCRIPT = ROOT / "scripts" / "build_housing_cycle_db.py"


def run_build() -> None:
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)


def latest_tables() -> tuple[pd.Series, pd.DataFrame]:
    conn = sqlite3.connect(DB_PATH)
    model = pd.read_sql_query("SELECT * FROM model_signals ORDER BY date DESC LIMIT 1", conn, parse_dates=["date"])
    sources = pd.read_sql_query(
        """
        SELECT s.source,s.status,s.rows,s.message,s.run_at
        FROM source_log s
        JOIN (SELECT source, MAX(id) AS id FROM source_log GROUP BY source) latest USING(source,id)
        ORDER BY s.id DESC
        """,
        conn,
    )
    conn.close()
    latest = model.iloc[0] if not model.empty else pd.Series(dtype=object)
    return latest, sources


def fmt(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (int, float)):
        return f"{float(value):,.{digits}f}"
    return str(value)


def write_monthly_report(dashboard_path: Path) -> Path:
    latest, sources = latest_tables()
    if latest.empty:
        period = datetime.now().strftime("%Y-%m")
    else:
        period = latest["date"].strftime("%Y-%m")
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    path = MONTHLY_DIR / f"housing_cycle_{period}.md"
    src_md = sources.to_markdown(index=False) if not sources.empty else "暂无"
    content = f"""# 房地产周期月度追踪报告 — {period}

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 主信号

| 指标 | 数值 |
|---|---:|
| 最新月份 | {period} |
| 主信号 | {fmt(latest.get('main_signal')) if not latest.empty else '—'} |
| 居民新增贷款 | {fmt(latest.get('household_new_loans')) if not latest.empty else '—'} 亿 |
| 6M 均值 | {fmt(latest.get('household_ma6')) if not latest.empty else '—'} 亿 |
| 12M 均值 | {fmt(latest.get('household_ma12')) if not latest.empty else '—'} 亿 |
| 6M-12M 利差 | {fmt(latest.get('household_spread')) if not latest.empty else '—'} 亿 |
| 综合分 | {fmt(latest.get('composite_score'), 0) if not latest.empty else '—'} |

结论：{fmt(latest.get('recommendation')) if not latest.empty else '暂无'}

## 可视化入口

- HTML Dashboard：`{dashboard_path.relative_to(ROOT)}`

## 数据源状态

{src_md}

## 备注

- 国家统计局房地产开发销售数据为累计口径，且 1 月份不单独调查/发布。
- 十大城市二手房挂牌价来自中指数据公开图文/手工录入，需持续核验。
- 核心10城二手房库存变化暂无稳定可验证数据源，已从当前模型和 Dashboard 移除。
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    run_build()
    dashboard_path = generate_dashboard.write_dashboard(refresh_data=False)
    report_path = write_monthly_report(dashboard_path)
    print(dashboard_path)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

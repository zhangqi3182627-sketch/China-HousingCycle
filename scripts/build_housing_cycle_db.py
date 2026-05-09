#!/usr/bin/env python3
"""Build a local China housing-cycle database and signal model.

The database intentionally separates:
- official/near-official pulled series that are programmatically available now;
- manual PBOC household-loan seed data that must be expanded before formal signals.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_DIR = DATA_DIR / "manual"
REPORT_DIR = ROOT / "reports"
DB_PATH = DATA_DIR / "housing_cycle.sqlite"

EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PBC_BASE_URL = "https://www.pbc.gov.cn"
PBC_STATS_INDEX_URL = f"{PBC_BASE_URL}/diaochatongjisi/116219/116319/index.html"
PBC_HEADERS = {"User-Agent": "Mozilla/5.0 HousingCycle/0.1"}
WESTOCK_BIN = Path.home() / ".codebuddy/bin/westock-data"
NEODATA_SKILL_DIR = Path.home() / ".codebuddy/skills-marketplace/skills/neodata-financial-search"
NEODATA_QUERY = NEODATA_SKILL_DIR / "scripts/query.py"


@dataclass(frozen=True)
class SeriesMeta:
    series_id: str
    name: str
    frequency: str
    unit: str
    source: str
    source_url: str
    notes: str = ""


SERIES = [
    SeriesMeta("household_new_loans", "住户新增贷款", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "主信号；由央行人民币信贷收支表住户贷款余额月差计算"),
    SeriesMeta("household_short_new_loans", "住户短期新增贷款", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "由央行人民币信贷收支表短期住户贷款余额月差计算"),
    SeriesMeta("household_medium_long_new_loans", "住户中长期新增贷款", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "由央行人民币信贷收支表中长期住户贷款余额月差计算；房贷相关性更强"),
    SeriesMeta("household_loan_stock", "住户贷款余额", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "央行金融机构人民币信贷收支表/按部门表"),
    SeriesMeta("household_short_loan_stock", "住户短期贷款余额", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "央行金融机构人民币信贷收支表；旧表由短期消费+短期经营合成"),
    SeriesMeta("household_medium_long_loan_stock", "住户中长期贷款余额", "M", "亿元", "PBOC", "http://www.pbc.gov.cn/", "央行金融机构人民币信贷收支表；旧表由中长期消费+中长期经营合成"),
    SeriesMeta("china_new_financial_credit", "新增人民币贷款总额", "M", "亿元", "Eastmoney/AkShare", "https://data.eastmoney.com/cjsj/xzxd.html", "总信贷代理变量，不能替代住户贷款"),
    SeriesMeta("real_estate_climate_index", "国房景气指数", "M", "点", "Eastmoney/AkShare", "https://data.eastmoney.com/cjsj/hyzs_list_EMM00121987.html", "房地产开发景气辅助指标"),
    SeriesMeta("new_home_price_mom", "70城新建商品住宅价格环比指数", "M", "上月=100", "Eastmoney/NBS release mirror", "https://data.eastmoney.com/cjsj/newhouse.html", "城市维度"),
    SeriesMeta("new_home_price_yoy", "70城新建商品住宅价格同比指数", "M", "上年同月=100", "Eastmoney/NBS release mirror", "https://data.eastmoney.com/cjsj/newhouse.html", "城市维度"),
    SeriesMeta("second_home_price_mom", "70城二手住宅价格环比指数", "M", "上月=100", "Eastmoney/NBS release mirror", "https://data.eastmoney.com/cjsj/newhouse.html", "城市维度"),
    SeriesMeta("second_home_price_yoy", "70城二手住宅价格同比指数", "M", "上年同月=100", "Eastmoney/NBS release mirror", "https://data.eastmoney.com/cjsj/newhouse.html", "城市维度"),
    SeriesMeta("new_home_positive_city_share", "70城新房环比上涨城市占比", "M", "%", "Derived", "local", "由新房环比指数>100的城市数/总城市数计算"),
    SeriesMeta("second_home_positive_city_share", "70城二手房环比上涨城市占比", "M", "%", "Derived", "local", "由二手房环比指数>100的城市数/总城市数计算"),
    SeriesMeta("re_investment_cum", "房地产开发投资完成额累计值", "M", "亿元", "westock-data", "westock-data macro investment", "INV_REALESTATE_AMT_COMPLETE_CUM"),
    SeriesMeta("re_investment_current", "房地产开发投资额当期值", "M", "亿元", "westock-data", "westock-data macro investment", "INV_REALESTATE_AMT_CUR"),
    SeriesMeta("re_sales_area_cum", "房屋销售面积累计值", "M", "平方米", "westock-data", "westock-data macro investment", "INV_REALESTATE_SALED_CUM"),
    SeriesMeta("re_sales_area_current", "房屋销售面积当期值", "M", "万平方米", "westock-data", "westock-data macro investment", "INV_REALESTATE_SALED_CUR"),
    SeriesMeta("re_sales_revenue_cum", "房屋销售额累计值", "M", "元", "westock-data", "westock-data macro investment", "INV_REALESTATE_REVENUE_CUM"),
    SeriesMeta("re_new_start_area_cum", "房屋新开工面积累计值", "M", "平方米", "westock-data", "westock-data macro investment", "INV_REALESTATE_NEW_CUM"),
    SeriesMeta("re_completion_area_cum", "房屋竣工面积累计值", "M", "平方米", "westock-data", "westock-data macro investment", "INV_REALESTATE_COMPLETE_CUM"),
    SeriesMeta("re_for_sale_area", "商品房待售面积", "M", "万平方米", "westock-data", "westock-data macro investment", "INV_REALESTATE_FORSALE"),
    SeriesMeta("re_cap_loan_cum", "房地产开发资金来源：国内贷款累计值", "M", "元", "westock-data", "westock-data macro investment", "INV_REALESTATE_CAP_LOAN_CUM"),
    SeriesMeta("re_cap_deposit_cum", "房地产开发资金来源：定金及预收款累计值", "M", "元", "westock-data", "westock-data macro investment", "INV_REALESTATE_CAP_DEPOSIT_CUM"),
    SeriesMeta("re_cap_self_cum", "房地产开发资金来源：自筹资金累计值", "M", "元", "westock-data", "westock-data macro investment", "INV_REALESTATE_CAP_SELF_CUM"),
]

WESTOCK_INVESTMENT_FIELDS = {
    "INV_REALESTATE_AMT_COMPLETE_CUM": "re_investment_cum",
    "INV_REALESTATE_AMT_CUR": "re_investment_current",
    "INV_REALESTATE_SALED_CUM": "re_sales_area_cum",
    "INV_REALESTATE_SALED_CUR": "re_sales_area_current",
    "INV_REALESTATE_REVENUE_CUM": "re_sales_revenue_cum",
    "INV_REALESTATE_NEW_CUM": "re_new_start_area_cum",
    "INV_REALESTATE_COMPLETE_CUM": "re_completion_area_cum",
    "INV_REALESTATE_FORSALE": "re_for_sale_area",
    "INV_REALESTATE_CAP_LOAN_CUM": "re_cap_loan_cum",
    "INV_REALESTATE_CAP_DEPOSIT_CUM": "re_cap_deposit_cum",
    "INV_REALESTATE_CAP_SELF_CUM": "re_cap_self_cum",
}


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS series (
            series_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            unit TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS observations (
            series_id TEXT NOT NULL,
            date TEXT NOT NULL,
            value REAL,
            region TEXT DEFAULT 'CN',
            source TEXT,
            is_estimated INTEGER DEFAULT 0,
            notes TEXT,
            PRIMARY KEY(series_id, date, region),
            FOREIGN KEY(series_id) REFERENCES series(series_id)
        );
        CREATE TABLE IF NOT EXISTS model_signals (
            date TEXT PRIMARY KEY,
            household_new_loans REAL,
            household_ma6 REAL,
            household_ma12 REAL,
            household_spread REAL,
            main_signal TEXT,
            price_breadth_score REAL,
            climate_score REAL,
            composite_score REAL,
            recommendation TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS source_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            rows INTEGER DEFAULT 0,
            message TEXT
        );
        CREATE TABLE IF NOT EXISTS pbc_report_snippets (
            period_end TEXT PRIMARY KEY,
            period_type TEXT,
            title TEXT,
            source_url TEXT,
            raw_text TEXT,
            household_new_loans REAL,
            household_short_new_loans REAL,
            household_medium_long_new_loans REAL,
            confidence REAL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS neodata_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            query TEXT NOT NULL,
            code TEXT,
            suc INTEGER,
            recall_types TEXT,
            preview TEXT,
            status TEXT,
            message TEXT
        );
        CREATE TABLE IF NOT EXISTS pbc_credit_table_files (
            year INTEGER,
            url TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            message TEXT,
            parsed_at TEXT NOT NULL
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO series(series_id,name,frequency,unit,source,source_url,notes) VALUES(?,?,?,?,?,?,?)",
        [(s.series_id, s.name, s.frequency, s.unit, s.source, s.source_url, s.notes) for s in SERIES],
    )
    conn.commit()


def log_source(conn: sqlite3.Connection, source: str, status: str, rows: int = 0, message: str = "") -> None:
    conn.execute(
        "INSERT INTO source_log(run_at, source, status, rows, message) VALUES(?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), source, status, rows, message[:1000]),
    )
    conn.commit()


def upsert_observations(conn: sqlite3.Connection, rows: Iterable[tuple]) -> int:
    rows = list(rows)
    conn.executemany(
        """
        INSERT OR REPLACE INTO observations(series_id,date,value,region,source,is_estimated,notes)
        VALUES(?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_all_city_house_prices() -> pd.DataFrame:
    all_rows = []
    page = 1
    pages = None
    while pages is None or page <= pages:
        params = {
            "reportName": "RPT_ECONOMY_HOUSE_PRICE",
            "columns": "REPORT_DATE,CITY,FIRST_COMHOUSE_SAME,FIRST_COMHOUSE_SEQUENTIAL,FIRST_COMHOUSE_BASE,SECOND_HOUSE_SAME,SECOND_HOUSE_SEQUENTIAL,SECOND_HOUSE_BASE,REPORT_DAY",
            "pageNumber": str(page),
            "pageSize": "500",
            "sortColumns": "REPORT_DATE,CITY",
            "sortTypes": "-1,-1",
            "source": "WEB",
            "client": "WEB",
        }
        r = requests.get(EASTMONEY_URL, params=params, timeout=30)
        r.raise_for_status()
        result = r.json().get("result") or {}
        pages = int(result.get("pages") or 0)
        data = result.get("data") or []
        all_rows.extend(data)
        page += 1
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    rename = {
        "REPORT_DATE": "date",
        "CITY": "city",
        "FIRST_COMHOUSE_SAME": "new_yoy",
        "FIRST_COMHOUSE_SEQUENTIAL": "new_mom",
        "FIRST_COMHOUSE_BASE": "new_base",
        "SECOND_HOUSE_SAME": "second_yoy",
        "SECOND_HOUSE_SEQUENTIAL": "second_mom",
        "SECOND_HOUSE_BASE": "second_base",
    }
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-01")
    for col in ["new_yoy", "new_mom", "new_base", "second_yoy", "second_mom", "second_base"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["date", "city", "new_yoy", "new_mom", "new_base", "second_yoy", "second_mom", "second_base"]]


def load_house_prices(conn: sqlite3.Connection) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / "eastmoney_70_city_house_price.csv"
    try:
        df = fetch_all_city_house_prices()
        df.to_csv(cache_path, index=False)
        source_note = "fresh"
    except Exception as e:
        if not cache_path.exists():
            log_source(conn, "70_city_house_price", "error", 0, repr(e))
            return
        df = pd.read_csv(cache_path)
        source_note = f"cache_after_error: {type(e).__name__}"
    raw_row_count = len(df)
    df = df.drop_duplicates(subset=["date", "city"], keep="last")
    rows = []
    mapping = {
        "new_mom": "new_home_price_mom",
        "new_yoy": "new_home_price_yoy",
        "second_mom": "second_home_price_mom",
        "second_yoy": "second_home_price_yoy",
    }
    for _, r in df.iterrows():
        for col, sid in mapping.items():
            rows.append((sid, r["date"], None if pd.isna(r[col]) else float(r[col]), r["city"], "Eastmoney/NBS mirror", 0, "70-city city-level price index"))
    n = upsert_observations(conn, rows)
    # Derived breadth indicators
    derived = []
    for date, g in df.groupby("date"):
        if g["new_mom"].notna().any():
            derived.append(("new_home_positive_city_share", date, float((g["new_mom"] > 100).mean() * 100), "CN70", "Derived", 0, "share of cities with MoM index > 100"))
        if g["second_mom"].notna().any():
            derived.append(("second_home_positive_city_share", date, float((g["second_mom"] > 100).mean() * 100), "CN70", "Derived", 0, "share of cities with MoM index > 100"))
    n += upsert_observations(conn, derived)
    log_source(conn, "70_city_house_price", "ok", n, f"raw rows={raw_row_count}; unique city rows={len(df)}; {source_note}")


def load_akshare_macro(conn: sqlite3.Connection) -> None:
    import akshare as ak

    # Total new credit proxy
    try:
        df = ak.macro_china_new_financial_credit()
        df.to_csv(RAW_DIR / "akshare_new_financial_credit.csv", index=False)
        rows = []
        for _, r in df.iterrows():
            date = pd.to_datetime(str(r["月份"]).replace("年", "-").replace("月份", "-01"), errors="coerce")
            if pd.isna(date):
                continue
            rows.append(("china_new_financial_credit", date.strftime("%Y-%m-01"), float(r["当月"]), "CN", "Eastmoney/AkShare", 0, "total new RMB loans, not household loans"))
        log_source(conn, "new_financial_credit", "ok", upsert_observations(conn, rows), "")
    except Exception as e:
        log_source(conn, "new_financial_credit", "error", 0, repr(e))

    # Real estate climate index
    try:
        df = ak.macro_china_real_estate()
        df.to_csv(RAW_DIR / "akshare_real_estate_climate.csv", index=False)
        rows = []
        for _, r in df.iterrows():
            rows.append(("real_estate_climate_index", pd.to_datetime(r["日期"]).strftime("%Y-%m-01"), float(r["最新值"]), "CN", "Eastmoney/AkShare", 0, ""))
        log_source(conn, "real_estate_climate", "ok", upsert_observations(conn, rows), "")
    except Exception as e:
        log_source(conn, "real_estate_climate", "error", 0, repr(e))


def _pbc_soup(url: str):
    from bs4 import BeautifulSoup

    r = requests.get(url, headers=PBC_HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def _normalize_label(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value).replace("\xa0", ""))


def _to_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").replace("\xa0", "").strip()
    if not text or text.lower() == "nan" or text in {"-", "--"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else None


def _safe_raw_name(url: str) -> str:
    name = url.rstrip("/").split("/")[-1] or "index.html"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def discover_pbc_credit_links(start_year: int = 2000, end_year: int | None = None) -> dict[int, list[dict[str, str]]]:
    """Discover PBOC annual credit-funds table links from the official statistics index."""
    if end_year is None:
        end_year = datetime.now().year
    soup = _pbc_soup(PBC_STATS_INDEX_URL)
    year_pages: dict[int, str] = {}
    for a in soup.find_all("a"):
        text = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        m = re.search(r"(\d{4})年统计数据", text)
        if m and href:
            year = int(m.group(1))
            if start_year <= year <= end_year:
                year_pages[year] = urljoin(PBC_BASE_URL, href)

    links_by_year: dict[int, list[dict[str, str]]] = {}
    excluded = ("存款类", "中资", "大型", "四家", "中小型", "国有", "商业银行")
    for year, year_url in sorted(year_pages.items()):
        try:
            year_soup = _pbc_soup(year_url)
            credit_url = year_url
            for a in year_soup.find_all("a"):
                text = a.get_text(" ", strip=True)
                href = a.get("href") or ""
                if "金融机构信贷收支统计" in text and href:
                    credit_url = urljoin(PBC_BASE_URL, href)
                    break

            credit_soup = _pbc_soup(credit_url)
            links = []
            for a in credit_soup.find_all("a"):
                text = a.get_text(" ", strip=True)
                href = a.get("href") or ""
                lower_href = href.lower()
                if lower_href.endswith((".xlsx", ".xls")):
                    links.append({"text": text, "url": urljoin(PBC_BASE_URL, href), "kind": "excel"})
                elif lower_href.endswith(".htm") and "金融机构人民币信贷收支表" in text and not any(x in text for x in excluded):
                    links.append({"text": text, "url": urljoin(PBC_BASE_URL, href), "kind": "html"})
            links.sort(key=lambda item: (0 if "按部门" in item["text"] else 1, item["kind"] != "excel"))
            links_by_year[year] = links
        except Exception as e:
            links_by_year[year] = [{"text": "", "url": year_url, "kind": "error", "error": repr(e)}]
    return links_by_year


def _read_pbc_table(url: str) -> tuple[pd.DataFrame, str]:
    raw_dir = RAW_DIR / "pbc_credit_tables"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / _safe_raw_name(url)
    content = None
    last_error: Exception | None = None
    for _ in range(3):
        try:
            r = requests.get(url, headers=PBC_HEADERS, timeout=45)
            r.raise_for_status()
            content = r.content
            raw_path.write_bytes(content)
            break
        except Exception as e:
            last_error = e
    if content is None:
        if raw_path.exists():
            content = raw_path.read_bytes()
        elif last_error is not None:
            raise last_error
        else:
            raise RuntimeError(f"failed to fetch {url}")

    if url.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), header=None, dtype=object)
    else:
        last_error = None
        df = pd.DataFrame()
        for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin1"):
            try:
                tables = pd.read_html(io.StringIO(content.decode(enc, errors="replace")))
                if tables:
                    candidate = tables[0]
                    first_col = "".join(_normalize_label(x) for x in candidate.iloc[:40, 0].tolist())
                    if any(k in first_col for k in ("住户贷款", "居民户贷款", "消费性贷款", "经营性贷款")) or df.empty:
                        df = candidate
                    if any(k in first_col for k in ("住户贷款", "居民户贷款")):
                        break
            except Exception as e:
                last_error = e
        if df.empty and last_error is not None:
            raise last_error
    title = " ".join(str(x) for x in df.iloc[:3, 0].dropna().tolist()) if not df.empty else ""
    return df, title


def _is_target_pbc_credit_table(title: str, link_text: str) -> bool:
    text = _normalize_label(f"{title}{link_text}")
    if "金融机构人民币信贷收支表" not in text:
        return False
    return not any(x in text for x in ("存款类", "中资", "大型", "四家", "中小型", "国有", "商业银行"))


def _month_columns_from_pbc_table(df: pd.DataFrame) -> dict[int, str]:
    for row_idx in range(min(10, len(df))):
        row = df.iloc[row_idx]
        years = []
        for value in row.iloc[1:13].tolist():
            m = re.search(r"(20\d{2})", str(value))
            if m:
                years.append(int(m.group(1)))
        if len(years) >= 2:
            year = max(set(years), key=years.count)
            return {col: f"{year}-{col:02d}-01" for col in range(1, min(13, len(row)))}
    return {}


def _find_pbc_household_rows(df: pd.DataFrame) -> tuple[int | None, int | None, int | None, list[int], list[int]]:
    labels = [_normalize_label(x) for x in df.iloc[:, 0].tolist()]
    total_idx = None
    for idx, label in enumerate(labels):
        if ("住户贷款" in label or "居民户贷款" in label) and "存款" not in label:
            total_idx = idx
            break
    if total_idx is None:
        return None, None, None, [], []

    window = range(total_idx + 1, min(total_idx + 12, len(labels)))
    direct_short = None
    direct_medium = None
    short_parts = []
    medium_parts = []
    for idx in window:
        label = labels[idx]
        if any(stop in label for stop in ("企（事）业单位贷款", "非金融", "Non-financial", "Nonfinancial", "境外贷款", "OverseasLoans", "有价证券", "Portfolio", "二、")):
            break
        if "短期消费" in label or "短期经营" in label:
            short_parts.append(idx)
            continue
        if "中长期消费" in label or "中长期经营" in label:
            medium_parts.append(idx)
            continue
        if "短期贷款" in label and "短期贷款及票据" not in label:
            direct_short = idx
        if "中长期贷款" in label:
            direct_medium = idx
    return total_idx, direct_short, direct_medium, short_parts, medium_parts


def _extract_pbc_household_stocks(df: pd.DataFrame, source_url: str, title: str) -> list[dict[str, object]]:
    month_cols = _month_columns_from_pbc_table(df)
    if not month_cols:
        return []
    total_idx, direct_short, direct_medium, short_parts, medium_parts = _find_pbc_household_rows(df)
    if total_idx is None:
        return []
    records = []
    for col, date in month_cols.items():
        total = _to_float(df.iat[total_idx, col]) if col < df.shape[1] else None
        if total is None:
            continue
        if direct_short is not None:
            short = _to_float(df.iat[direct_short, col]) if col < df.shape[1] else None
        else:
            parts = [_to_float(df.iat[idx, col]) for idx in short_parts if col < df.shape[1]]
            short = sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
        if direct_medium is not None:
            medium = _to_float(df.iat[direct_medium, col]) if col < df.shape[1] else None
        else:
            parts = [_to_float(df.iat[idx, col]) for idx in medium_parts if col < df.shape[1]]
            medium = sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
        records.append({
            "date": date,
            "household_loan_stock": total,
            "household_short_loan_stock": short,
            "household_medium_long_loan_stock": medium,
            "source_url": source_url,
            "title": title,
        })
    return records


def load_pbc_credit_tables(conn: sqlite3.Connection, start_year: int = 2000, end_year: int | None = None) -> None:
    """Fetch PBOC credit-funds tables and derive monthly household loan increments from stock changes."""
    if end_year is None:
        end_year = datetime.now().year
    try:
        links_by_year = discover_pbc_credit_links(start_year=start_year, end_year=end_year)
    except Exception as e:
        log_source(conn, "pbc_credit_tables", "error", 0, repr(e))
        return

    conn.execute("DELETE FROM pbc_credit_table_files")
    conn.commit()
    file_rows = []
    stock_records: list[dict[str, object]] = []
    for year, links in links_by_year.items():
        parsed_for_year = False
        if links and links[0].get("kind") == "error":
            file_rows.append((year, links[0]["url"], "", "error", links[0].get("error", ""), datetime.now().isoformat(timespec="seconds")))
            continue
        for link in links:
            url = link["url"]
            title = ""
            try:
                df, title = _read_pbc_table(url)
                if not _is_target_pbc_credit_table(title, link.get("text", "")):
                    file_rows.append((year, url, title, "skipped", "not target RMB household credit table", datetime.now().isoformat(timespec="seconds")))
                    continue
                records = _extract_pbc_household_stocks(df, url, title)
                status = "ok" if records else "no_household_rows"
                file_rows.append((year, url, title, status, f"records={len(records)}", datetime.now().isoformat(timespec="seconds")))
                if records:
                    stock_records.extend(records)
                    parsed_for_year = True
                    break
            except Exception as e:
                file_rows.append((year, url, title, "error", repr(e)[:500], datetime.now().isoformat(timespec="seconds")))
        if not parsed_for_year and not links:
            file_rows.append((year, "", "", "missing", "no credit table links discovered", datetime.now().isoformat(timespec="seconds")))

    conn.executemany(
        "INSERT OR REPLACE INTO pbc_credit_table_files(year,url,title,status,message,parsed_at) VALUES(?,?,?,?,?,?)",
        file_rows,
    )
    conn.commit()

    if not stock_records:
        log_source(conn, "pbc_credit_tables", "empty", 0, "no household loan stock rows parsed")
        return

    stock_df = pd.DataFrame(stock_records).drop_duplicates(subset=["date"], keep="last")
    stock_df["date"] = pd.to_datetime(stock_df["date"])
    stock_df = stock_df.sort_values("date")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stock_df.to_csv(RAW_DIR / "pbc_household_loan_stocks.csv", index=False)

    obs_rows = []
    stock_mapping = {
        "household_loan_stock": "household_loan_stock",
        "household_short_loan_stock": "household_short_loan_stock",
        "household_medium_long_loan_stock": "household_medium_long_loan_stock",
    }
    for r in stock_df.itertuples(index=False):
        date_s = r.date.strftime("%Y-%m-01")
        for col, sid in stock_mapping.items():
            val = getattr(r, col)
            if pd.notna(val):
                obs_rows.append((sid, date_s, float(val), "CN", "PBOC credit funds table", 0, str(r.source_url)))

    diff_df = stock_df.copy()
    for col in stock_mapping:
        diff_df[f"{col}_diff"] = diff_df[col].diff()
    diff_mapping = {
        "household_loan_stock_diff": "household_new_loans",
        "household_short_loan_stock_diff": "household_short_new_loans",
        "household_medium_long_loan_stock_diff": "household_medium_long_new_loans",
    }
    prev_dates = diff_df["date"].shift(1)
    month_index = diff_df["date"].dt.year * 12 + diff_df["date"].dt.month
    prev_month_index = prev_dates.dt.year * 12 + prev_dates.dt.month
    monthly_mask = prev_dates.notna() & ((month_index - prev_month_index) == 1)
    for idx, r in diff_df[monthly_mask].iterrows():
        date_s = r["date"].strftime("%Y-%m-01")
        for col, sid in diff_mapping.items():
            val = r[col]
            if pd.notna(val):
                obs_rows.append((sid, date_s, float(val), "CN", "PBOC credit funds table MoM stock diff", 0, "official stock balance difference"))
    n = upsert_observations(conn, obs_rows)
    first_date = stock_df["date"].min().strftime("%Y-%m")
    last_date = stock_df["date"].max().strftime("%Y-%m")
    monthly_count = int(monthly_mask.sum())
    log_source(conn, "pbc_credit_tables", "ok", n, f"stock_months={len(stock_df)} monthly_diffs={monthly_count} coverage={first_date}..{last_date}")


def _extract_amount_yi(text: str, label_pattern: str) -> float | None:
    """Extract an amount in 亿元 from Chinese macro text."""
    patterns = [
        rf"{label_pattern}[^，。；;]*?(增加|减少)([0-9.]+)万亿元",
        rf"{label_pattern}[^，。；;]*?(增加|减少)([0-9.]+)亿元",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        sign = -1 if m.group(1) == "减少" else 1
        val = float(m.group(2))
        if "万亿元" in pat:
            val *= 10000
        return sign * val
    return None


def parse_pbc_household_text(text: str) -> dict[str, float | None]:
    return {
        "household_new_loans": _extract_amount_yi(text, r"住户贷款"),
        "household_short_new_loans": _extract_amount_yi(text, r"短期贷款"),
        "household_medium_long_new_loans": _extract_amount_yi(text, r"中长期贷款"),
    }


def load_pbc_report_snippets(conn: sqlite3.Connection) -> None:
    """Parse PBOC report/news snippets; supports monthly and cumulative YTD text."""
    path = MANUAL_DIR / "pbc_report_snippets.csv"
    if not path.exists():
        log_source(conn, "pbc_report_snippets", "missing", 0, str(path))
        return

    report_rows = []
    monthly_rows = []
    ytd_by_year: dict[int, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            parsed = parse_pbc_household_text(r.get("raw_text", ""))
            period_end = pd.to_datetime(r["period_end"]).strftime("%Y-%m-01")
            item = {
                "period_end": period_end,
                "period_type": r.get("period_type", ""),
                "source_url": r.get("source_url", ""),
                "confidence": float(r.get("confidence") or 0),
                "notes": r.get("notes", ""),
                **parsed,
            }
            report_rows.append((
                period_end, item["period_type"], r.get("title", ""), item["source_url"], r.get("raw_text", ""),
                parsed["household_new_loans"], parsed["household_short_new_loans"], parsed["household_medium_long_new_loans"],
                item["confidence"], item["notes"],
            ))
            if item["period_type"] == "monthly":
                for sid, key in [
                    ("household_new_loans", "household_new_loans"),
                    ("household_short_new_loans", "household_short_new_loans"),
                    ("household_medium_long_new_loans", "household_medium_long_new_loans"),
                ]:
                    if parsed[key] is not None:
                        monthly_rows.append((sid, period_end, float(parsed[key]), "CN", item["source_url"] or "PBOC report", 0, item["notes"]))
            elif item["period_type"] == "ytd":
                ytd_by_year.setdefault(pd.to_datetime(period_end).year, []).append(item)

    conn.executemany(
        """
        INSERT OR REPLACE INTO pbc_report_snippets(period_end,period_type,title,source_url,raw_text,
        household_new_loans,household_short_new_loans,household_medium_long_new_loans,confidence,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        report_rows,
    )
    # Convert sequential YTD records into monthly estimates.
    for _, items in ytd_by_year.items():
        items = sorted(items, key=lambda x: x["period_end"])
        prev = None
        for item in items:
            if prev is None:
                prev = item
                continue
            date = item["period_end"]
            for sid, key in [
                ("household_new_loans", "household_new_loans"),
                ("household_short_new_loans", "household_short_new_loans"),
                ("household_medium_long_new_loans", "household_medium_long_new_loans"),
            ]:
                if item[key] is not None and prev[key] is not None:
                    val = float(item[key]) - float(prev[key])
                    monthly_rows.append((sid, date, val, "CN", item["source_url"] or "PBOC YTD diff", 1, f"YTD diff: {prev['period_end']} -> {date}; {item['notes']}"))
            prev = item

    conn.commit()
    log_source(conn, "pbc_report_snippets", "ok", len(report_rows), "parsed PBOC monthly/YTD snippets")
    log_source(conn, "pbc_household_monthly_from_reports", "ok", upsert_observations(conn, monthly_rows), "monthly values parsed or derived from YTD snippets")


def load_manual_pbc_household(conn: sqlite3.Connection) -> None:
    path = MANUAL_DIR / "pbc_household_loans_seed.csv"
    if not path.exists():
        log_source(conn, "pbc_household_manual", "missing", 0, str(path))
        return
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            date = pd.to_datetime(r["date"]).strftime("%Y-%m-01")
            estimated = 1 if "倒推" in r.get("source", "") or "估算" in r.get("notes", "") else 0
            for sid, col in [
                ("household_new_loans", "household_new_loans"),
                ("household_short_new_loans", "household_short_new_loans"),
                ("household_medium_long_new_loans", "household_medium_long_new_loans"),
            ]:
                val = r.get(col, "")
                if val == "":
                    continue
                rows.append((sid, date, float(val), "CN", r.get("source", "PBOC"), estimated, r.get("notes", "")))
    log_source(conn, "pbc_household_manual", "ok", upsert_observations(conn, rows), "manual seed; not complete 2000-now series")


def load_westock_investment(conn: sqlite3.Connection, start_year: int = 2000, end_year: int | None = None) -> None:
    """Load real-estate supply/demand metrics from westock-data macro investment."""
    if end_year is None:
        end_year = datetime.now().year
    if not WESTOCK_BIN.exists():
        log_source(conn, "westock_investment", "missing", 0, str(WESTOCK_BIN))
        return
    cmd = [str(WESTOCK_BIN), "macro", "investment", "--start", str(start_year), "--end", str(end_year), "--raw"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            log_source(conn, "westock_investment", "error", 0, proc.stderr[:500])
            return
        raw = proc.stdout
        json_start = raw.find("{")
        if json_start < 0:
            log_source(conn, "westock_investment", "error", 0, "no JSON object in output")
            return
        data, _ = json.JSONDecoder().raw_decode(raw[json_start:])
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / "westock_macro_investment_raw.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        rows = []
        for block in data.values():
            for item in block.get("items", []):
                enddate = str(item.get("INVEST_ENDDATE", ""))
                if len(enddate) < 6:
                    continue
                date = pd.to_datetime(enddate[:6] + "01", format="%Y%m%d", errors="coerce")
                if pd.isna(date):
                    continue
                date_s = date.strftime("%Y-%m-01")
                for field, sid in WESTOCK_INVESTMENT_FIELDS.items():
                    val = item.get(field)
                    if val in (None, "", "-"):
                        continue
                    rows.append((sid, date_s, float(val), "CN", "westock-data macro investment", 0, field))
        log_source(conn, "westock_investment", "ok", upsert_observations(conn, rows), f"years={start_year}-{end_year}")
    except Exception as e:
        log_source(conn, "westock_investment", "error", 0, repr(e))


def load_neodata_validation(conn: sqlite3.Connection) -> None:
    """Use NeoData as validation/search layer; do not store credentials."""
    if not NEODATA_QUERY.exists():
        log_source(conn, "neodata_validation", "missing", 0, str(NEODATA_QUERY))
        return
    queries = [
        "居民贷款 住户贷款 中长期贷款 月度 数据",
        "房地产开发投资 商品房销售面积 新开工面积 月度 数据",
        "70城新房 二手房 价格指数",
    ]
    rows = []
    for q in queries:
        try:
            proc = subprocess.run(
                [sys.executable, str(NEODATA_QUERY), "--query", q, "--data-type", "api"],
                cwd=str(NEODATA_SKILL_DIR), capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                rows.append((datetime.now().isoformat(timespec="seconds"), q, None, 0, "[]", "", "error", proc.stderr[:500]))
                continue
            res = json.loads(proc.stdout)
            api = (res.get("data") or {}).get("apiData") or {}
            recalls = api.get("apiRecall") or []
            types = [r.get("type") for r in recalls]
            preview = " | ".join(str(r.get("content", "")).replace("\n", " ")[:300] for r in recalls[:2])
            rows.append((
                datetime.now().isoformat(timespec="seconds"), q, str(res.get("code")), 1 if res.get("suc") else 0,
                json.dumps(types, ensure_ascii=False), preview, "ok", str(res.get("msg", "")),
            ))
        except Exception as e:
            rows.append((datetime.now().isoformat(timespec="seconds"), q, None, 0, "[]", "", "error", repr(e)[:500]))
    conn.executemany(
        "INSERT INTO neodata_validation(run_at,query,code,suc,recall_types,preview,status,message) VALUES(?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    log_source(conn, "neodata_validation", "ok", len(rows), "validation queries completed")


def read_series(conn: sqlite3.Connection, series_id: str, region: str | None = None) -> pd.DataFrame:
    sql = "SELECT date, value, region, is_estimated FROM observations WHERE series_id=?"
    params: list = [series_id]
    if region:
        sql += " AND region=?"
        params.append(region)
    df = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
    return df.sort_values("date")


def build_model(conn: sqlite3.Connection) -> pd.DataFrame:
    """Build v0.3 scoring model.

    The main signal remains credit expansion only. The composite score implements the
    approved auxiliary weights: credit 50, sales 18, price 15, inventory/supply 12,
    developer financing 3, climate/policy 2.
    """
    hh = read_series(conn, "household_new_loans", "CN")
    if hh.empty:
        return pd.DataFrame()

    top10_cities = ["北京", "上海", "深圳", "广州", "杭州", "南京", "天津", "成都", "武汉", "重庆"]

    def one_series(series_id: str, region: str = "CN") -> pd.Series:
        data = read_series(conn, series_id, region)
        if data.empty:
            return pd.Series(dtype="float64")
        return data.drop_duplicates("date").set_index("date")["value"].sort_index()

    def city_avg(series_id: str, regions: list[str] | None = None) -> pd.Series:
        data = read_series(conn, series_id)
        if data.empty:
            return pd.Series(dtype="float64")
        if regions is not None:
            data = data[data["region"].isin(regions)]
        if data.empty:
            return pd.Series(dtype="float64")
        return data.groupby("date")["value"].mean().sort_index()

    def same_month_yoy(series: pd.Series) -> pd.Series:
        s = series.dropna().sort_index()
        prev = s.copy()
        prev.index = prev.index + pd.DateOffset(years=1)
        prev = prev.reindex(s.index)
        return (s / prev - 1) * 100

    def improved(series: pd.Series, months: int = 3) -> pd.Series:
        return (series > 0) | (series > series.shift(months))

    def score_when(condition: pd.Series, points: float) -> pd.Series:
        return condition.fillna(False).astype(float) * points

    df = hh[["date", "value", "is_estimated"]].rename(columns={"value": "household_new_loans"}).set_index("date").sort_index()
    df["household_ma6"] = df["household_new_loans"].rolling(6, min_periods=6).mean()
    df["household_ma12"] = df["household_new_loans"].rolling(12, min_periods=12).mean()
    df["household_spread"] = df["household_ma6"] - df["household_ma12"]

    new_breadth = one_series("new_home_positive_city_share", "CN70")
    second_breadth = one_series("second_home_positive_city_share", "CN70")
    df["new_breadth"] = new_breadth.reindex(df.index)
    df["second_breadth"] = second_breadth.reindex(df.index)
    df["price_breadth_score"] = df[["new_breadth", "second_breadth"]].mean(axis=1)

    second_yoy_avg = city_avg("second_home_price_yoy") - 100
    core10_second_mom = city_avg("second_home_price_mom", top10_cities) - 100
    df["second_yoy_avg"] = second_yoy_avg.reindex(df.index)
    df["core10_second_mom"] = core10_second_mom.reindex(df.index)

    creis_path = MANUAL_DIR / "creis_top10_second_hand_listing.csv"
    if creis_path.exists() and creis_path.stat().st_size > 0:
        creis = pd.read_csv(creis_path, parse_dates=["date"])
        creis_avg = creis.groupby("date")[["mom_pct", "yoy_pct"]].mean().sort_index()
        df["creis_mom"] = creis_avg["mom_pct"].reindex(df.index)
        df["creis_yoy"] = creis_avg["yoy_pct"].reindex(df.index)
    else:
        df["creis_mom"] = pd.NA
        df["creis_yoy"] = pd.NA

    sales_current = one_series("re_sales_area_current")
    sales_area_cum = one_series("re_sales_area_cum")
    sales_revenue_cum = one_series("re_sales_revenue_cum")
    deposit_cum = one_series("re_cap_deposit_cum")
    cap_loan_cum = one_series("re_cap_loan_cum")
    new_start_cum = one_series("re_new_start_area_cum")
    completion_cum = one_series("re_completion_area_cum")
    for_sale_area = one_series("re_for_sale_area")
    climate = one_series("real_estate_climate_index")

    df["sales_area_yoy"] = same_month_yoy(sales_current).reindex(df.index)
    if not sales_revenue_cum.empty and not sales_area_cum.empty:
        avg_price = sales_revenue_cum / sales_area_cum
        df["avg_price_yoy"] = same_month_yoy(avg_price).reindex(df.index)
    else:
        df["avg_price_yoy"] = pd.NA
    df["deposit_yoy"] = same_month_yoy(deposit_cum).reindex(df.index)
    df["cap_loan_yoy"] = same_month_yoy(cap_loan_cum).reindex(df.index)

    if not for_sale_area.empty and not sales_current.empty:
        monthly_absorption = sales_current.rolling(12, min_periods=9).sum() / 12
        df["months_to_sell"] = (for_sale_area / monthly_absorption).reindex(df.index)
    else:
        df["months_to_sell"] = pd.NA
    if not new_start_cum.empty and not sales_area_cum.empty:
        df["new_start_sales_ratio"] = (new_start_cum / sales_area_cum).reindex(df.index)
    else:
        df["new_start_sales_ratio"] = pd.NA
    if not completion_cum.empty and not sales_area_cum.empty:
        df["completion_sales_ratio"] = (completion_cum / sales_area_cum).reindex(df.index)
    else:
        df["completion_sales_ratio"] = pd.NA

    df["climate"] = climate.reindex(df.index)
    df["climate_score"] = df["climate"].diff(6)

    valid_credit = df["household_ma6"].notna() & df["household_ma12"].notna()
    df["credit_score"] = 0.0
    df.loc[valid_credit, "credit_score"] += score_when(df["household_ma6"] > 3000, 20)
    df.loc[valid_credit, "credit_score"] += score_when(df["household_ma12"] > 3000, 20)
    df.loc[valid_credit, "credit_score"] += score_when((df["household_spread"] > 0) & (df["household_ma6"] > df["household_ma6"].shift(3)), 10)

    df["sales_score"] = (
        score_when(improved(df["sales_area_yoy"]), 10)
        + score_when(improved(df["avg_price_yoy"]), 5)
        + score_when(improved(df["deposit_yoy"]), 3)
    )
    df["price_score"] = (
        score_when(df["price_breadth_score"] > 50, 5)
        + score_when((df["second_breadth"] > 30) | improved(df["second_yoy_avg"]), 4)
        + score_when(improved(df["core10_second_mom"]), 4)
        + score_when((df["creis_mom"] >= 0) | (df["creis_yoy"] >= 0), 2)
    )
    df["inventory_score"] = (
        score_when(df["months_to_sell"] < df["months_to_sell"].shift(3), 6)
        + score_when((df["new_start_sales_ratio"] < 1.0) | (df["new_start_sales_ratio"] < df["new_start_sales_ratio"].shift(3)), 3)
        + score_when(df["completion_sales_ratio"] < df["completion_sales_ratio"].shift(3), 3)
    )
    df["financing_score"] = score_when(improved(df["cap_loan_yoy"]), 3)
    df["climate_policy_score"] = score_when(df["climate_score"] > 0, 1) + score_when((df["climate"] > 95) | (df["climate"] > df["climate"].shift(3)), 1)

    module_cols = ["credit_score", "sales_score", "price_score", "inventory_score", "financing_score", "climate_policy_score"]
    df["composite_score"] = df[module_cols].sum(axis=1)
    df.loc[~valid_credit, "composite_score"] = 0.0

    def classify(r) -> tuple[str, str]:
        if pd.isna(r["household_ma6"]) or pd.isna(r["household_ma12"]):
            return "DATA_INSUFFICIENT", "居民新增贷款月度序列不足12个月，不能正式判定"
        if r["credit_score"] >= 50:
            return "GREEN_CANDIDATE", "主信号满足阈值和多头排列；需连续3个月确认"
        if r["credit_score"] >= 10:
            return "YELLOW_WATCH", "信贷主信号有修复迹象，但未完全确认"
        return "RED_NO_BOTTOM", "居民加杠杆趋势未确认"

    labels = df.apply(classify, axis=1, result_type="expand")
    df["main_signal"] = labels[0]
    df["recommendation"] = labels[1]
    df["notes"] = df.apply(
        lambda r: (
            "contains estimated/manual loan data; " if r.get("is_estimated") else ""
        )
        + f"v0.3 module scores: credit={r.credit_score:.0f}, sales={r.sales_score:.0f}, price={r.price_score:.0f}, inventory={r.inventory_score:.0f}, financing={r.financing_score:.0f}, climate={r.climate_policy_score:.0f}",
        axis=1,
    )
    df = df.reset_index()

    conn.execute("DELETE FROM model_signals")
    conn.executemany(
        """
        INSERT OR REPLACE INTO model_signals(date, household_new_loans, household_ma6, household_ma12,
        household_spread, main_signal, price_breadth_score, climate_score, composite_score, recommendation, notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                r.date.strftime("%Y-%m-01"),
                None if pd.isna(r.household_new_loans) else float(r.household_new_loans),
                None if pd.isna(r.household_ma6) else float(r.household_ma6),
                None if pd.isna(r.household_ma12) else float(r.household_ma12),
                None if pd.isna(r.household_spread) else float(r.household_spread),
                r.main_signal,
                None if pd.isna(r.price_breadth_score) else float(r.price_breadth_score),
                None if pd.isna(r.climate_score) else float(r.climate_score),
                None if pd.isna(r.composite_score) else float(r.composite_score),
                r.recommendation,
                r.notes,
            )
            for r in df.itertuples()
        ],
    )
    conn.commit()
    return df


def write_report(conn: sqlite3.Connection, model_df: pd.DataFrame) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    src = pd.read_sql_query("""
        SELECT s.source,s.status,s.rows,s.message,s.run_at
        FROM source_log s
        JOIN (SELECT source, MAX(id) AS id FROM source_log GROUP BY source) latest USING(source,id)
        ORDER BY s.id DESC
    """, conn)
    obs = pd.read_sql_query("SELECT series_id, COUNT(*) AS n, MIN(date) AS start, MAX(date) AS end FROM observations GROUP BY series_id ORDER BY series_id", conn)
    pbc = pd.read_sql_query("SELECT period_end,period_type,household_new_loans,household_short_new_loans,household_medium_long_new_loans,confidence,notes FROM pbc_report_snippets ORDER BY period_end", conn)
    pbc_files = pd.read_sql_query("SELECT year,title,status,message FROM pbc_credit_table_files WHERE status <> 'skipped' ORDER BY year DESC LIMIT 30", conn)
    neo = pd.read_sql_query("SELECT query,code,suc,recall_types,status,message,run_at FROM neodata_validation ORDER BY id DESC LIMIT 10", conn)
    latest = model_df.tail(1).to_dict("records") if not model_df.empty else []
    path = REPORT_DIR / "housing_cycle_framework.md"
    path.write_text(
        "# 全国商品房走势预测框架 v0.1\n\n"
        "## 核心假设\n\n"
        "房即是债，债即是房。房价见底的先导信号不是价格本身，而是居民部门重新扩表。\n\n"
        "## 主信号\n\n"
        "- 居民每月新增贷款 6个月滚动均值 > 3000亿元\n"
        "- 居民每月新增贷款 12个月滚动均值 > 3000亿元\n"
        "- 6M 均线自下而上穿越 12M 均线，并向上发散\n"
        "- 建议增加连续3个月确认，过滤政策脉冲和春节扰动\n\n"
        "## 辅助指标\n\n"
        "1. 70城新房/二手房环比上涨城市占比\n"
        "2. 国房景气指数及其6个月变化\n"
        "3. westock-data macro investment：商品房销售面积、销售额、新开工、竣工、待售、开发投资、房企资金来源\n"
        "4. 新增人民币贷款总额作为信用环境代理变量\n"
        "5. 二手房成交：当前暂无全国统一官方月度源，后续按城市住建委/贝壳/中指分层补\n\n"
        "## 当前模型最新输出\n\n"
        f"```json\n{json.dumps(latest, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        "## 数据覆盖\n\n"
        f"{obs.to_markdown(index=False)}\n\n"
        "## PBC 居民贷款解析样本\n\n"
        f"{pbc.to_markdown(index=False) if not pbc.empty else '暂无'}\n\n"
        "## PBC 官方信贷表抓取日志\n\n"
        f"{pbc_files.to_markdown(index=False) if not pbc_files.empty else '暂无'}\n\n"
        "## NeoData 校验层\n\n"
        f"{neo.to_markdown(index=False) if not neo.empty else '暂无'}\n\n"
        "## 最近数据源日志\n\n"
        f"{src.to_markdown(index=False)}\n\n"
        "## 重要限制\n\n"
        "- PBC 居民新增贷款已优先用央行金融机构人民币信贷收支表余额月差自动生成；早年如缺少按部门住户贷款口径则不强行估算。\n"
        "- 金融统计口径会因机构范围/统计制度调整产生跳变，重大月份需用央行月度金融统计报告文字交叉校验。\n"
        "- westock-data 已覆盖房地产开发投资、商品房销售面积、销售额、新开工、竣工、待售和房企资金来源，可作为房地产供需主通道。\n"
        "- NeoData 对居民贷款和房地产宏观查询可作为校验/搜索层，但自然语言召回存在噪声，不作为主库。\n"
        "- 国家统计局官网接口当前可能返回403；本版用 Eastmoney/AkShare 镜像拉取70城房价和国房景气指数，并在数据库中保留 source 字段。\n"
        "- 二手房成交套数没有统一全国官方月度序列，后续应按城市住建委/贝壳/中指等建立分层数据源。\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true", help="只重建模型，不重新拉取外部数据")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()
    init_db(conn)
    if not args.skip_fetch:
        load_house_prices(conn)
        load_akshare_macro(conn)
        load_westock_investment(conn, start_year=2000, end_year=datetime.now().year)
        load_neodata_validation(conn)
    load_pbc_report_snippets(conn)
    load_manual_pbc_household(conn)
    if not args.skip_fetch:
        load_pbc_credit_tables(conn, start_year=2000, end_year=datetime.now().year)
    model_df = build_model(conn)
    report = write_report(conn, model_df)
    print(f"DB: {DB_PATH}")
    print(f"REPORT: {report}")
    if model_df.empty:
        print("MODEL: DATA_INSUFFICIENT")
    else:
        print(model_df.tail(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

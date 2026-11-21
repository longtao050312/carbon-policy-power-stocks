"""Fetch current security names for the sample codes from Eastmoney quote API.

The result is a reference table only: names reflect the most recent listing
name, not necessarily the name used at each policy event date.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "raw" / "TRD_Dalyr.xlsx"
REF_DIR = BASE / "data" / "reference"
REF_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def secid(code: str) -> str:
    # 6/9 prefix -> Shanghai (1); 0/2/3 prefix -> Shenzhen (0)
    return ("1." if code[0] in {"5", "6", "9"} else "0.") + code


def board(code: str) -> str:
    if code.startswith(("200", "900")):
        return "B股"
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("600", "601", "603", "605")):
        return "沪市主板"
    if code.startswith(("000", "001", "002", "003")):
        return "深市主板"
    return "其他"


def exchange(code: str) -> str:
    return "上海" if code[0] in {"5", "6", "9"} else "深圳"


def fetch_name(code: str) -> tuple[str, str]:
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={secid(code)}&fields=f57,f58,f107"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network hiccup: report, do not fabricate
        return "", f"ERROR: {exc}"
    data = payload.get("data") or {}
    name = data.get("f58") or ""
    return name, "" if name else "NO_DATA"


def main() -> None:
    # The CSMAR export puts the field-name row in DataFrame row 0 and a unit
    # row in row 1, so the two label rows must be dropped after reading.
    stocks = pd.read_excel(RAW, usecols=["Stkcd"]).iloc[2:]
    codes = (
        stocks["Stkcd"].astype("string").str.replace(r"\.0$", "", regex=True).str.zfill(6)
        .dropna().unique().tolist()
    )
    codes = sorted(c for c in codes if c.isdigit())

    rows = []
    for code in codes:
        name, note = fetch_name(code)
        rows.append(
            {
                "Stkcd": code,
                "股票名称": name,
                "交易所": exchange(code),
                "板块": board(code),
                "备注": note,
            }
        )
        print(f"{code}\t{name}\t{note}")
        time.sleep(0.25)

    table = pd.DataFrame(rows)
    out = REF_DIR / "stock_names.csv"
    table.to_csv(out, index=False, encoding="utf-8-sig")
    missing = table[table["股票名称"].eq("")]
    print(f"\nSaved {len(table)} codes to {out}; missing/blank names: {len(missing)}")
    if not missing.empty:
        print(missing.to_string(index=False))


if __name__ == "__main__":
    main()

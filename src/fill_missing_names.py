"""Fill the blank rows in the stock-name reference table.

Uses Eastmoney's batch quote endpoint (ulist.np) so that rate limiting is
avoided, retries the remaining codes a few times, and rewrites the CSV in place.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
REF = BASE / "data" / "reference" / "stock_names.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def secid(code: str) -> str:
    return ("1." if code[0] in {"5", "6", "9"} else "0.") + code


def fetch_batch(codes: list[str]) -> dict[str, str]:
    secids = ",".join(secid(c) for c in codes)
    url = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get"
        f"?secids={secids}&fields=f12,f14&fltt=2&invt=2"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    diff = (payload.get("data") or {}).get("diff") or []
    return {str(item.get("f12", "")): str(item.get("f14", "")) for item in diff}


def main() -> None:
    table = pd.read_csv(REF, dtype={"Stkcd": str})
    table["Stkcd"] = table["Stkcd"].str.zfill(6)
    target = table.loc[table["股票名称"].isna() | table["股票名称"].eq(""), "Stkcd"].tolist()

    for attempt in range(1, 6):
        if not target:
            break
        print(f"attempt {attempt}, {len(target)} codes pending")
        resolved: dict[str, str] = {}
        for start in range(0, len(target), 10):
            chunk = target[start : start + 10]
            try:
                resolved.update(fetch_batch(chunk))
            except Exception as exc:
                print(f"  chunk failed: {chunk} -> {exc}")
            time.sleep(1.5)
        target = [c for c in target if not resolved.get(c)]
        for code, name in resolved.items():
            table.loc[table["Stkcd"].eq(code), "股票名称"] = name
            table.loc[table["Stkcd"].eq(code), "备注"] = ""
        time.sleep(3)

    still = table.loc[table["股票名称"].isna() | table["股票名称"].eq(""), "Stkcd"].tolist()
    for code in still:
        table.loc[table["Stkcd"].eq(code), "备注"] = "NAME_UNRESOLVED"

    table.to_csv(REF, index=False, encoding="utf-8-sig")
    print(f"Saved {len(table)} rows to {REF}; unresolved: {still}")


if __name__ == "__main__":
    main()

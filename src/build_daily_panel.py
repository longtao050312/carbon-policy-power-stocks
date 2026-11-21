"""Build the daily stock-market panel used by the event study.

Steps
1. Read the two CSMAR exports, dropping the Chinese-label and unit rows.
2. Normalise codes to six digits and dates to datetime.
3. Attach current security names from data/reference/stock_names.csv.
4. Merge the Markettype = 21 market return onto each stock-day by trading date.
5. Write the panel plus a merge report; no observations are dropped here.

Cleaning filters (B shares, suspensions, insufficient estimation windows) are
deliberately left to the event-study sample step so that every exclusion can be
logged separately.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
REPORT = BASE / "outputs" / "data_prep"

MARKET_TYPE = 21  # CSMAR 综合A股市场，流通市值加权
STOCK_FIELDS = {
    "Stkcd": "Stkcd",
    "Trddt": "Trddt",
    "Clsprc": "Clsprc",
    "Dnshrtrd": "Dnshrtrd",
    "Dnvaltrd": "Dnvaltrd",
    "Dsmvosd": "Dsmvosd",
    "Dretwd": "Dretwd",
    "Dretnd": "Dretnd",
    "Markettype": "stock_markettype",
    "Trdsta": "Trdsta",
}


def read_csmar(path: Path, usecols: list[str]) -> pd.DataFrame:
    frame = pd.read_excel(path, usecols=usecols)
    # Row 0 repeats field names in Chinese, row 1 holds units.
    return frame.iloc[2:].copy()


def normalise_code(series: pd.Series) -> pd.Series:
    text = (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(6)
    )
    return text.where(text.str.fullmatch(r"\d{6}", na=False))


def load_names() -> pd.DataFrame:
    names = pd.read_csv(
        BASE / "data" / "reference" / "stock_names.csv", dtype={"Stkcd": str}
    )
    names["Stkcd"] = names["Stkcd"].str.zfill(6)
    return names[["Stkcd", "股票名称", "交易所", "板块"]]


def build_stock_table() -> pd.DataFrame:
    raw = read_csmar(RAW / "TRD_Dalyr.xlsx", list(STOCK_FIELDS))
    data = raw.rename(columns=STOCK_FIELDS)
    data["Stkcd"] = normalise_code(data["Stkcd"])
    data["Trddt"] = pd.to_datetime(data["Trddt"], errors="coerce")
    for column in ["Clsprc", "Dnshrtrd", "Dnvaltrd", "Dsmvosd", "Dretwd", "Dretnd",
                   "stock_markettype", "Trdsta"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["Stkcd", "Trddt"])
    data = data.sort_values(["Stkcd", "Trddt"]).drop_duplicates(
        ["Stkcd", "Trddt"], keep="last"
    )
    return data.reset_index(drop=True)


def build_market_table() -> pd.DataFrame:
    raw = read_csmar(RAW / "TRD_Cndalym.xlsx", ["Markettype", "Trddt", "Cdretwdos", "Cdretwdtl"])
    data = raw.rename(
        columns={"Cdretwdos": "market_return_vw", "Cdretwdtl": "market_return_tv"}
    )
    data["Markettype"] = pd.to_numeric(data["Markettype"], errors="coerce")
    data["Trddt"] = pd.to_datetime(data["Trddt"], errors="coerce")
    for column in ["market_return_vw", "market_return_tv"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["Markettype", "Trddt"])
    data = data[data["Markettype"].eq(MARKET_TYPE)]
    data = data.sort_values("Trddt").drop_duplicates("Trddt", keep="last")
    return data[["Trddt", "market_return_vw", "market_return_tv"]].reset_index(drop=True)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)

    stocks = build_stock_table()
    market = build_market_table()
    names = load_names()

    before = len(stocks)
    panel = stocks.merge(names, on="Stkcd", how="left", validate="many_to_one")
    panel = panel.merge(
        market, on="Trddt", how="left", validate="many_to_one", indicator="market_merge"
    )
    panel["market_matched"] = panel["market_merge"].eq("both").astype(int)
    panel = panel.drop(columns="market_merge")

    order = [
        "Stkcd", "股票名称", "交易所", "板块", "Trddt", "Clsprc", "Dretwd", "Dretnd",
        "Dsmvosd", "Dnshrtrd", "Dnvaltrd", "stock_markettype", "Trdsta",
        "market_return_vw", "market_return_tv", "market_matched",
    ]
    panel = panel[order].sort_values(["Stkcd", "Trddt"]).reset_index(drop=True)

    panel.to_csv(PROCESSED / "daily_returns_merged.csv", index=False, encoding="utf-8-sig")
    panel.to_excel(PROCESSED / "daily_returns_merged.xlsx", index=False)

    # ---- diagnostics -------------------------------------------------------
    unmatched_market = panel.loc[panel["market_matched"].eq(0)]
    missing_name = panel.loc[panel["股票名称"].isna(), "Stkcd"].unique().tolist()
    missing_return = int(panel["Dretwd"].isna().sum())
    market_days = market["Trddt"].nunique()
    stock_days = panel["Trddt"].nunique()

    lines = [
        "# 行情合并报告",
        "",
        "## 结果概览",
        "",
        f"- 合并后记录数：{len(panel):,}（原始个股记录 {before:,}）",
        f"- 股票代码数：{panel['Stkcd'].nunique()}",
        f"- 覆盖交易日数：{stock_days}，市场日历交易日数：{market_days}",
        f"- 日期范围：{panel['Trddt'].min().date()} 至 {panel['Trddt'].max().date()}",
        f"- `Dretwd` 缺失记录：{missing_return:,}",
        f"- 市场收益未匹配记录：{len(unmatched_market):,}",
        f"- 名称未匹配代码：{missing_name if missing_name else '无'}",
        "",
        "## 字段说明",
        "",
        "| 输出字段 | 来源 | 含义 |",
        "| --- | --- | --- |",
        "| `Stkcd` | TRD_Dalyr | 六位证券代码 |",
        "| `股票名称` | Eastmoney 行情接口 | 当前证券简称（非事件当时名称） |",
        "| `Trddt` | 两表 | 交易日 |",
        "| `Clsprc` | TRD_Dalyr | 日收盘价（元） |",
        "| `Dretwd` | TRD_Dalyr | 考虑现金红利再投资的日个股回报率 |",
        "| `Dretnd` | TRD_Dalyr | 不考虑现金红利的日个股回报率 |",
        "| `Dsmvosd` | TRD_Dalyr | 日个股流通市值（千元） |",
        "| `Dnshrtrd` | TRD_Dalyr | 日个股交易股数 |",
        "| `Dnvaltrd` | TRD_Dalyr | 日个股交易金额（元） |",
        "| `stock_markettype` | TRD_Dalyr | 个股所属市场类型 |",
        "| `Trdsta` | TRD_Dalyr | 交易状态（1 正常，2/3 停牌或特殊） |",
        "| `market_return_vw` | TRD_Cndalym `Cdretwdos` | 综合A股流通市值加权日市场回报率（Markettype=21） |",
        "| `market_return_tv` | TRD_Cndalym `Cdretwdtl` | 综合A股总市值加权日市场回报率（Markettype=21） |",
        "| `market_matched` | 合并指示 | 1 表示该交易日找到市场收益 |",
        "",
        "## 说明",
        "",
        "- 合并键仅为 `Trddt`，市场表每个交易日唯一，因此为多对一合并，不改变个股记录数。",
        "- 本步骤不做剔除：B 股、停牌、上市不足等样本筛选留到事件研究样本步骤，便于逐条记录剔除原因。",
        "- 股票名称为 2026-11 抓取的当前简称，涉及改名或退市前后的公司需在事件窗口核对当时名称。",
    ]

    if not unmatched_market.empty:
        rows = (
            unmatched_market.groupby("Stkcd")
            .agg(记录数=("Trddt", "size"), 最早=("Trddt", "min"), 最晚=("Trddt", "max"))
            .reset_index()
            .sort_values("记录数", ascending=False)
        )
        rows["最早"] = rows["最早"].dt.date
        rows["最晚"] = rows["最晚"].dt.date
        name_map = panel.drop_duplicates("Stkcd").set_index("Stkcd")["股票名称"]
        rows["股票名称"] = rows["Stkcd"].map(name_map)
        rows = rows[["Stkcd", "股票名称", "记录数", "最早", "最晚"]]
        lines += ["", "## 未匹配市场收益的代码", "", rows.to_markdown(index=False)]
        rows.to_csv(REPORT / "unmatched_market_dates.csv", index=False, encoding="utf-8-sig")

    (REPORT / "merge_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"panel rows={len(panel):,} codes={panel['Stkcd'].nunique()}")
    print(f"unmatched market rows={len(unmatched_market):,}, Dretwd missing={missing_return}")
    print(f"missing names={missing_name}")
    print(f"market calendar days={market_days}, stock days={stock_days}")


if __name__ == "__main__":
    main()

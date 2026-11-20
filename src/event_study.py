"""Market-model event study for the carbon-policy thesis.

This script does not ship with data. See data/README.md for the expected
licensed CSMAR exports.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


STOCK_COLUMNS = {"Stkcd", "Trddt", "Dretwd"}
MARKET_COLUMNS = {"Markettype", "Trddt", "Cdretwdos"}
WINDOWS = {
    "car_0_1": (0, 1),
    "car_m1_1": (-1, 1),
    "car_0_3": (0, 3),
    "car_m5_m2": (-5, -2),
}


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def normalize_stock_code(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    return cleaned.str.zfill(6)


def prepare_stock_data(frame: pd.DataFrame) -> pd.DataFrame:
    missing = STOCK_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Stock data missing columns: {sorted(missing)}")

    data = frame.copy()
    data["Stkcd"] = normalize_stock_code(data["Stkcd"])
    data["Trddt"] = pd.to_datetime(data["Trddt"], errors="coerce")
    data["Dretwd"] = pd.to_numeric(data["Dretwd"], errors="coerce")
    if "Dsmvosd" in data:
        data["Dsmvosd"] = pd.to_numeric(data["Dsmvosd"], errors="coerce")
    if "Trdsta" in data:
        data["Trdsta"] = pd.to_numeric(data["Trdsta"], errors="coerce")

    # CSMAR Excel exports may include Chinese-description and unit rows.
    data = data.dropna(subset=["Stkcd", "Trddt", "Dretwd"])
    data = data[data["Stkcd"].str.fullmatch(r"\d{6}", na=False)]
    return data.sort_values(["Stkcd", "Trddt"]).drop_duplicates(
        ["Stkcd", "Trddt"], keep="last"
    )


def prepare_market_data(frame: pd.DataFrame, market_type: int = 21) -> pd.DataFrame:
    missing = MARKET_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Market data missing columns: {sorted(missing)}")

    data = frame.copy()
    data["Markettype"] = pd.to_numeric(data["Markettype"], errors="coerce")
    data["Trddt"] = pd.to_datetime(data["Trddt"], errors="coerce")
    data["Cdretwdos"] = pd.to_numeric(data["Cdretwdos"], errors="coerce")
    data = data.dropna(subset=["Markettype", "Trddt", "Cdretwdos"])
    data = data[data["Markettype"] == market_type]
    return (
        data[["Trddt", "Cdretwdos"]]
        .sort_values("Trddt")
        .drop_duplicates("Trddt", keep="last")
    )


def map_event_to_trading_day(
    official_date: pd.Timestamp, trading_dates: pd.DatetimeIndex
) -> pd.Timestamp:
    candidates = trading_dates[trading_dates >= official_date]
    if candidates.empty:
        raise ValueError(f"No trading day on or after {official_date.date()}")
    return pd.Timestamp(candidates[0])


def estimate_company_event(
    company: pd.DataFrame,
    market: pd.DataFrame,
    event_id: str,
    requested_event_date: pd.Timestamp,
    min_estimation_days: int = 60,
) -> tuple[pd.DataFrame, dict] | None:
    merged = company.merge(market, on="Trddt", how="inner")
    if merged.empty:
        return None

    trading_dates = pd.DatetimeIndex(market["Trddt"].sort_values().unique())
    event_date = map_event_to_trading_day(requested_event_date, trading_dates)
    event_position = trading_dates.get_loc(event_date)
    positions = pd.Series(
        np.arange(len(trading_dates)), index=trading_dates, dtype="int64"
    )
    merged["rel_day"] = merged["Trddt"].map(positions) - event_position

    estimation = merged[merged["rel_day"].between(-120, -21)].dropna(
        subset=["Dretwd", "Cdretwdos"]
    )
    if len(estimation) < min_estimation_days:
        return None

    x = np.column_stack(
        [np.ones(len(estimation)), estimation["Cdretwdos"].to_numpy()]
    )
    y = estimation["Dretwd"].to_numpy()
    alpha, beta = np.linalg.lstsq(x, y, rcond=None)[0]

    event_data = merged[merged["rel_day"].between(-5, 3)].copy()
    event_data["expected_return"] = alpha + beta * event_data["Cdretwdos"]
    event_data["abnormal_return"] = (
        event_data["Dretwd"] - event_data["expected_return"]
    )
    event_data["event_id"] = event_id
    event_data["event_date"] = event_date

    result = {
        "event_id": event_id,
        "event_date": event_date,
        "Stkcd": company["Stkcd"].iloc[0],
        "alpha": alpha,
        "beta": beta,
        "estimation_days": len(estimation),
    }
    if "Dsmvosd" in merged:
        pre_size = merged.loc[merged["rel_day"] < 0, "Dsmvosd"].dropna()
        result["pre_event_market_value"] = (
            pre_size.iloc[-1] if not pre_size.empty else np.nan
        )

    for name, (start, end) in WINDOWS.items():
        values = event_data.loc[
            event_data["rel_day"].between(start, end), "abnormal_return"
        ]
        result[name] = values.sum(min_count=1)

    return event_data, result


def run_event_study(
    stocks: pd.DataFrame,
    market: pd.DataFrame,
    events: pd.DataFrame,
    min_estimation_days: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ar_frames: list[pd.DataFrame] = []
    company_results: list[dict] = []

    for event in events.itertuples(index=False):
        requested_date = pd.Timestamp(event.event_date)
        for _, company in stocks.groupby("Stkcd", sort=False):
            estimated = estimate_company_event(
                company,
                market,
                str(event.event_id),
                requested_date,
                min_estimation_days,
            )
            if estimated is None:
                continue
            event_ar, company_result = estimated
            ar_frames.append(event_ar)
            company_results.append(company_result)

    ar = pd.concat(ar_frames, ignore_index=True) if ar_frames else pd.DataFrame()
    company_car = pd.DataFrame(company_results)
    if company_car.empty:
        return ar, company_car, pd.DataFrame()

    value_columns = list(WINDOWS)
    summary = (
        company_car.groupby("event_id")[value_columns]
        .agg(["count", "mean", "median", "std"])
        .reset_index()
    )
    summary.columns = [
        "_".join(str(item) for item in column if item)
        if isinstance(column, tuple)
        else str(column)
        for column in summary.columns
    ]
    return ar, company_car, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stocks", type=Path, required=True)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument(
        "--events", type=Path, default=Path("config/events.csv")
    )
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/event_study"))
    parser.add_argument("--market-type", type=int, default=21)
    parser.add_argument("--min-estimation-days", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stocks = prepare_stock_data(read_table(args.stocks))
    market = prepare_market_data(read_table(args.market), args.market_type)
    events = pd.read_csv(args.events, parse_dates=["event_date"])
    events = events[events["sample_role"] == "core"].copy()

    ar, company_car, summary = run_event_study(
        stocks, market, events, args.min_estimation_days
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ar.to_csv(args.out_dir / "abnormal_returns.csv", index=False)
    company_car.to_csv(args.out_dir / "company_event_car.csv", index=False)
    summary.to_csv(args.out_dir / "event_summary.csv", index=False)

    print(
        f"Saved {len(ar):,} abnormal-return rows and "
        f"{len(company_car):,} company-event rows to {args.out_dir}"
    )


if __name__ == "__main__":
    main()

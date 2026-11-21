"""Run the market-model event study on the screened company-event sample.

Inputs
- outputs/sample/analysis_sample.csv        eligible company-event pairs
- data/processed/daily_returns_ashare.csv   stock returns, market returns, cap

Design
- estimation window [-120, -21], minimum 60 usable days
- R_it = alpha_i + beta_i * R_mt + e_it, estimated by OLS
- AR_it = R_it - (alpha_i + beta_i * R_mt)
- windows: [0,+1] main, [-1,+1], [0,+3], [-5,-2] pre-event
- events are reported separately; no pooled average is produced

Also produced: market-adjusted robustness, cap-weighted mean, +1 day shift,
and the pre-declared alternative dates.

Outputs go to outputs/event_study/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE = Path(__file__).resolve().parents[1]
PANEL = BASE / "data" / "processed" / "daily_returns_ashare.csv"
SAMPLE = BASE / "outputs" / "sample" / "analysis_sample.csv"
EVENTS = BASE / "config" / "events.csv"
OUT = BASE / "outputs" / "event_study"

EST_WINDOW = (-120, -21)
MIN_EST_DAYS = 60
AR_RANGE = (-10, 10)
WINDOWS = {
    "car_0_1": (0, 1),
    "car_m1_1": (-1, 1),
    "car_0_3": (0, 3),
    "car_m5_m2": (-5, -2),
}


def load_panel() -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    data = pd.read_csv(PANEL, dtype={"Stkcd": str}, parse_dates=["Trddt"])
    data["Stkcd"] = data["Stkcd"].str.zfill(6)
    data = data.dropna(subset=["Dretwd", "market_return_vw"])
    data = data.sort_values(["Stkcd", "Trddt"]).reset_index(drop=True)
    calendar = pd.DatetimeIndex(sorted(data["Trddt"].unique()))
    return data, calendar


def estimate_one(
    group: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    event_day: pd.Timestamp,
) -> dict | None:
    positions = pd.Series(np.arange(len(calendar)), index=calendar)
    g = group.set_index("Trddt")
    if event_day not in g.index:
        return None
    idx = int(positions[event_day])

    est_start = calendar[max(idx + EST_WINDOW[0], 0)]
    est_end = calendar[idx + EST_WINDOW[1]]
    est = g.loc[(g.index >= est_start) & (g.index <= est_end)]
    if len(est) < MIN_EST_DAYS:
        return None

    y = est["Dretwd"].to_numpy()
    x = est["market_return_vw"].to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    alpha, beta = np.linalg.lstsq(X, y, rcond=None)[0]

    lo = calendar[max(idx + AR_RANGE[0], 0)]
    hi = calendar[min(idx + AR_RANGE[1], len(calendar) - 1)]
    win = g.loc[(g.index >= lo) & (g.index <= hi)].copy()
    win["rel_day"] = positions.reindex(win.index).astype(int) - idx
    win["expected"] = alpha + beta * win["market_return_vw"]
    win["AR"] = win["Dretwd"] - win["expected"]
    win["AR_market_adj"] = win["Dretwd"] - win["market_return_vw"]

    cap = g.loc[g.index < event_day, "Dsmvosd"].dropna()
    result = {
        "Stkcd": group["Stkcd"].iloc[0],
        "alpha": alpha,
        "beta": beta,
        "est_days": len(est),
        "resid_sd": float(np.std(y - X @ np.array([alpha, beta]), ddof=2)),
        "pre_cap": float(cap.iloc[-1]) if not cap.empty else np.nan,
    }
    for name, (a, b) in WINDOWS.items():
        sub = win[win["rel_day"].between(a, b)]
        result[name] = float(sub["AR"].sum()) if len(sub) else np.nan
        result[f"{name}_ma"] = float(sub["AR_market_adj"].sum()) if len(sub) else np.nan
    return {"ar": win.reset_index()[["Trddt", "rel_day", "Dretwd", "market_return_vw", "AR", "AR_market_adj"]], "summary": result}


def describe(values: pd.Series) -> dict:
    v = values.dropna().to_numpy()
    n = len(v)
    if n < 3:
        return {"N": n}
    mean = float(np.mean(v))
    sd = float(np.std(v, ddof=1))
    se = sd / np.sqrt(n)
    t = mean / se if se > 0 else np.nan
    p = float(2 * stats.t.sf(abs(t), df=n - 1)) if np.isfinite(t) else np.nan
    return {
        "N": n,
        "mean": mean,
        "median": float(np.median(v)),
        "sd": sd,
        "t": float(t),
        "p": p,
        "pct_positive": float((v > 0).mean()),
        "min": float(np.min(v)),
        "max": float(np.max(v)),
    }


def run(shift: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel, calendar = load_panel()
    sample = pd.read_csv(SAMPLE, dtype={"Stkcd": str}, parse_dates=["event_date"])
    sample = sample[sample["eligible"].eq(1)].copy()
    sample["Stkcd"] = sample["Stkcd"].str.zfill(6)

    by_code = {code: g for code, g in panel.groupby("Stkcd")}
    summaries, ar_frames = [], []
    for row in sample.itertuples(index=False):
        group = by_code.get(row.Stkcd)
        if group is None or group.empty:
            continue
        ev_day = pd.Timestamp(row.event_date)
        pos = pd.DatetimeIndex(calendar).get_loc(ev_day) + shift
        if pos < 0 or pos >= len(calendar):
            continue
        ev = calendar[pos]
        out = estimate_one(group, calendar, ev)
        if out is None:
            continue
        s = out["summary"]
        s.update(
            {
                "event_id": row.event_id,
                "sample_role": row.sample_role,
                "event_date": ev.date(),
                "股票名称": row.股票名称,
                "shift": shift,
            }
        )
        summaries.append(s)
        ar = out["ar"]
        ar["event_id"] = row.event_id
        ar["event_date"] = ev.date()
        ar["Stkcd"] = row.Stkcd
        ar["shift"] = shift
        ar_frames.append(ar)
    return pd.DataFrame(summaries), pd.concat(ar_frames, ignore_index=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    car, ar = run(shift=0)
    car_shift, _ = run(shift=1)

    order = ["event_id", "sample_role", "event_date", "Stkcd", "股票名称",
             "alpha", "beta", "est_days", "resid_sd", "pre_cap"] + list(WINDOWS) + [f"{w}_ma" for w in WINDOWS]
    car = car[order]
    car.to_csv(OUT / "company_event_car.csv", index=False, encoding="utf-8-sig")
    ar.to_csv(OUT / "abnormal_returns.csv", index=False, encoding="utf-8-sig")

    # per-event statistics for each window and model variant
    rows = []
    for event_id, sub in car.groupby("event_id", sort=False):
        for window in WINDOWS:
            for label, col in (("市场模型", window), ("市场调整", f"{window}_ma")):
                d = describe(sub[col])
                d.update({"event_id": event_id, "window": window, "model": label,
                          "event_date": sub["event_date"].iloc[0]})
                rows.append(d)
    summary = pd.DataFrame(rows)

    # cap-weighted mean
    cap_rows = []
    for event_id, sub in car.groupby("event_id", sort=False):
        w = sub["pre_cap"].to_numpy()
        for window in WINDOWS:
            v = sub[window].to_numpy()
            ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
            cap_rows.append({
                "event_id": event_id,
                "event_date": sub["event_date"].iloc[0],
                "window": window,
                "cap_weighted_mean": float(np.sum(v[ok] * w[ok]) / np.sum(w[ok])) if ok.any() else np.nan,
                "N": int(ok.sum()),
            })
    cap_summary = pd.DataFrame(cap_rows)

    # +1 day shift robustness on the main window
    shift_rows = []
    for event_id, sub in car_shift.groupby("event_id", sort=False):
        for window in ("car_0_1", "car_m1_1"):
            d = describe(sub[window])
            d.update({"event_id": event_id, "window": window, "event_date": sub["event_date"].iloc[0]})
            shift_rows.append(d)
    shift_summary = pd.DataFrame(shift_rows)

    summary.to_csv(OUT / "event_summary.csv", index=False, encoding="utf-8-sig")
    cap_summary.to_csv(OUT / "summary_capweighted.csv", index=False, encoding="utf-8-sig")
    shift_summary.to_csv(OUT / "summary_shift1.csv", index=False, encoding="utf-8-sig")

    print(summary.to_string(index=False))
    print("\ncap weighted:\n", cap_summary[cap_summary["window"].eq("car_0_1")].to_string(index=False))
    print("\nshift+1:\n", shift_summary.to_string(index=False))


if __name__ == "__main__":
    main()

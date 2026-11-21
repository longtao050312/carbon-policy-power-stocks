"""Build the estimation sample and a full exclusion ledger.

Record-level screen
- drop B shares (200xxx / 900xxx);
- suspension needs no deletion here because CSMAR's TRD_Dalyr omits suspended
  days, so they appear as gaps against the market calendar. Gaps are counted and
  written out instead of being deleted.

Company-event level screen (applied per policy event, in order)
1. NO_RECORD_ON_EVENT        no row on the event trading day (not yet listed,
                             suspended, or delisted)
2. LISTED_TOO_LATE           first trading day after the estimation-window start
3. INSUFFICIENT_ESTIMATION   fewer than 60 usable days in [-120, -21]
4. INCOMPLETE_MAIN_WINDOW    event day or +1 missing, so CAR[0, +1] is not
                             the full two-day sum
5. ELIGIBLE

Nothing is averaged across events and no return is computed here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PANEL = BASE / "data" / "processed" / "daily_returns_merged.csv"
PROCESSED = BASE / "data" / "processed"
OUT = BASE / "outputs" / "sample"
OUT.mkdir(parents=True, exist_ok=True)

EST_WINDOW = (-120, -21)
MIN_EST_DAYS = 60
B_SHARE_PREFIX = ("200", "900")
WINDONS_LABEL = "0,+1"


def md_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table without the tabulate dependency."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in frame.astype(object).itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider] + body)


def load_panel() -> pd.DataFrame:
    data = pd.read_csv(PANEL, dtype={"Stkcd": str}, parse_dates=["Trddt"])
    data["Stkcd"] = data["Stkcd"].str.zfill(6)
    return data.sort_values(["Stkcd", "Trddt"]).reset_index(drop=True)


def record_screen(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_b = panel["Stkcd"].str.startswith(B_SHARE_PREFIX)
    kept = panel.loc[~is_b].copy()
    dropped = panel.loc[is_b].copy()
    dropped["exclusion_reason"] = "B_SHARE"
    kept["is_st"] = kept["Trdsta"].isin([2, 3]).astype(int)
    return kept.reset_index(drop=True), dropped.reset_index(drop=True)


def count_suspensions(kept: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(sorted(kept["Trddt"].unique()))
    rows = []
    for code, group in kept.groupby("Stkcd"):
        first, last = group["Trddt"].min(), group["Trddt"].max()
        expected = calendar[(calendar >= first) & (calendar <= last)]
        missing = expected.difference(pd.DatetimeIndex(group["Trddt"]))
        rows.append(
            {
                "Stkcd": code,
                "股票名称": group["股票名称"].iloc[0],
                "首个交易日": first.date(),
                "末个交易日": last.date(),
                "区间应有交易日": len(expected),
                "实际记录数": len(group),
                "缺失交易日数": len(missing),
                "缺失交易日": ";".join(d.strftime("%Y-%m-%d") for d in missing),
            }
        )
    return pd.DataFrame(rows).sort_values("Stkcd")


def main() -> None:
    panel = load_panel()
    kept, b_share = record_screen(panel)
    suspensions = count_suspensions(kept)

    kept.to_csv(PROCESSED / "daily_returns_ashare.csv", index=False, encoding="utf-8-sig")
    suspensions.to_csv(OUT / "suspension_gaps.csv", index=False, encoding="utf-8-sig")

    calendar = pd.DatetimeIndex(sorted(panel["Trddt"].unique()))
    events = pd.read_csv(BASE / "config" / "events.csv", parse_dates=["event_date"])

    rows = []
    for event in events.itertuples(index=False):
        event_date = pd.Timestamp(event.event_date)
        candidates = calendar[calendar >= event_date]
        if candidates.empty:
            raise ValueError(f"No trading day on or after {event_date.date()}")
        event_day = pd.Timestamp(candidates[0])
        idx = calendar.get_loc(event_day)
        est_start_idx = idx + EST_WINDOW[0]
        est_end_idx = idx + EST_WINDOW[1]
        est_start = calendar[est_start_idx] if est_start_idx >= 0 else calendar[0]

        for code, group in kept.groupby("Stkcd"):
            name = group["股票名称"].iloc[0]
            first_day = group["Trddt"].min()
            last_day = group["Trddt"].max()
            day_map = group.set_index("Trddt")

            has_event_day = event_day in day_map.index
            has_plus1 = (idx + 1) in range(len(calendar)) and calendar[idx + 1] in day_map.index

            def window_missing(start: int, end: int) -> list[str]:
                positions = range(idx + start, idx + end + 1)
                return [
                    calendar[p].strftime("%Y-%m-%d")
                    for p in positions
                    if 0 <= p < len(calendar) and calendar[p] not in day_map.index
                ]

            missing_m1_1 = window_missing(-1, 1)
            missing_0_1 = window_missing(0, 1)
            missing_0_3 = window_missing(0, 3)

            est = group[group["Trddt"].between(est_start, calendar[est_end_idx])]
            est = est.dropna(subset=["Dretwd", "market_return_vw"])
            est_days = len(est)

            # ST/*ST screen: a special-treatment day carries +/-5% price limits,
            # which distorts both the market-model beta and the event-window AR.
            # ST days are counted inside the two windows actually used: the
            # estimation window [-120, -21] and the event window [-1, +3].
            window_high = calendar[min(idx + 3, len(calendar) - 1)]
            span = group[group["Trddt"].between(est_start, window_high)]
            est_mask = span["Trddt"].le(calendar[est_end_idx])
            event_mask = span["Trddt"].ge(calendar[max(idx - 1, 0)])
            st_days_est = int(span.loc[est_mask, "is_st"].sum())
            st_days_event = int(span.loc[event_mask, "is_st"].sum())
            st_days_span = st_days_est + st_days_event

            if not has_event_day:
                reason = "NO_RECORD_ON_EVENT"
            elif first_day > est_start:
                reason = "LISTED_TOO_LATE"
            elif st_days_span > 0:
                reason = "ST_IN_WINDOW"
            elif est_days < MIN_EST_DAYS:
                reason = "INSUFFICIENT_ESTIMATION"
            elif not has_plus1:
                reason = "INCOMPLETE_MAIN_WINDOW"
            else:
                reason = "ELIGIBLE"

            trdsta = int(day_map.loc[event_day, "Trdsta"]) if has_event_day else pd.NA

            detail = {
                "NO_RECORD_ON_EVENT": (
                    "退市" if last_day < event_day else ("上市晚于事件日" if first_day > event_day else "事件日停牌")
                ),
                "LISTED_TOO_LATE": "上市日晚于估计窗起始日",
                "ST_IN_WINDOW": f"窗口内 ST/*ST {st_days_span} 天（估计窗 {st_days_est}，事件窗 {st_days_event}）",
                "INSUFFICIENT_ESTIMATION": f"估计窗有效交易日 {est_days} < {MIN_EST_DAYS}",
                "INCOMPLETE_MAIN_WINDOW": "事件日+1 无记录（停牌/退市）",
                "ELIGIBLE": "",
            }[reason]

            rows.append(
                {
                    "event_id": event.event_id,
                    "market_type": event.market_type,
                    "sample_role": event.sample_role,
                    "policy_name": event.policy_name,
                    "event_date": event_day.date(),
                    "Stkcd": code,
                    "股票名称": name,
                    "首个交易日": first_day.date(),
                    "末个交易日": last_day.date(),
                    "估计窗起始": est_start.date(),
                    "估计窗有效交易日": est_days,
                    "事件日有记录": int(has_event_day),
                    "事件日+1有记录": int(has_plus1),
                    "事件日交易状态": trdsta,
                    "事件日ST标记": int(trdsta in (2, 3)) if has_event_day else pd.NA,
                    "窗口内ST天数": st_days_span,
                    "估计窗ST天数": st_days_est,
                    "事件窗ST天数": st_days_event,
                    "窗口m1_1完整": int(not missing_m1_1),
                    "窗口0_1完整": int(not missing_0_1),
                    "窗口0_3完整": int(not missing_0_3),
                    "缺失日_m1_1": ";".join(missing_m1_1),
                    "缺失日_0_3": ";".join(missing_0_3),
                    "eligible": int(reason == "ELIGIBLE"),
                    "exclusion_reason": reason,
                    "reason_detail": detail,
                }
            )

    sample = pd.DataFrame(rows)
    sample.to_csv(OUT / "company_event_sample.csv", index=False, encoding="utf-8-sig")

    analysis = sample.loc[sample["eligible"].eq(1)].copy()
    analysis.to_csv(OUT / "analysis_sample.csv", index=False, encoding="utf-8-sig")

    ledger = sample.loc[sample["eligible"].eq(0)].copy()
    ledger.to_csv(OUT / "exclusion_ledger.csv", index=False, encoding="utf-8-sig")

    # ---- funnel per event --------------------------------------------------
    funnel = []
    for event in events.itertuples(index=False):
        sub = sample[sample["event_id"].eq(event.event_id)]
        n0 = len(sub) + int(b_share["Stkcd"].nunique())
        funnel.append(
            {
                "event_id": event.event_id,
                "sample_role": event.sample_role,
                "event_date": sub["event_date"].iloc[0],
                "原始代码数": n0,
                "-B股": b_share["Stkcd"].nunique(),
                "A股代码数": len(sub),
                "-事件日无记录": int(sub["exclusion_reason"].eq("NO_RECORD_ON_EVENT").sum()),
                "-上市不足": int(sub["exclusion_reason"].eq("LISTED_TOO_LATE").sum()),
                "-ST/*ST": int(sub["exclusion_reason"].eq("ST_IN_WINDOW").sum()),
                "-估计窗不足": int(sub["exclusion_reason"].eq("INSUFFICIENT_ESTIMATION").sum()),
                "-主窗口不完整": int(sub["exclusion_reason"].eq("INCOMPLETE_MAIN_WINDOW").sum()),
                "可用样本数": int(sub["eligible"].sum()),
            }
        )
    funnel_df = pd.DataFrame(funnel)
    funnel_df.to_csv(OUT / "sample_funnel.csv", index=False, encoding="utf-8-sig")

    # ---- report ------------------------------------------------------------
    lines = [
        "# 样本筛选报告",
        "",
        f"事件窗口口径：估计窗 `[-120, -21]`，最低有效交易日 {MIN_EST_DAYS}，主窗口 `[{WINDONS_LABEL}]`。",
        "逐事件筛选，不合并事件，不计算任何收益。",
        "",
        "## 1. 记录级筛选：B 股",
        "",
        f"- 剔除代码：{', '.join(sorted(b_share['Stkcd'].unique()))}",
        f"- 剔除记录数：{len(b_share):,}",
        f"- 剩余 A 股记录数：{len(kept):,}，代码数 {kept['Stkcd'].nunique()}",
        "",
        "## 2. 停牌处理",
        "",
        "CSMAR `TRD_Dalyr` 不保留停牌日记录，停牌表现为「区间内应有交易日与实际记录数之差」，",
        "因此记录级不存在可删除的停牌行；处理方式为：",
        "",
        "1. 逐代码登记缺失交易日（`outputs/sample/suspension_gaps.csv`）；",
        "2. 估计窗只统计实际存在的交易日，有效日数不足 60 即剔除该公司—事件；",
        "3. 事件日或 +1 日缺失，主窗口 `[0, +1]` 无法构成完整两日累计，剔除。",
        "",
        f"存在缺口的代码数：{int((suspensions['缺失交易日数'] > 0).sum())}，"
        f"缺口合计 {int(suspensions['缺失交易日数'].sum())} 个交易日。",
        "",
        "## 3. ST/*ST 剔除",
        "",
        "ST/*ST 期间股票适用 ±5% 涨跌停，既会扭曲市场模型 β，也会压缩事件窗 AR，",
        "因此剔除口径为：估计窗 `[-120, -21]` 或事件窗 `[-1, +3]` 内出现任一",
        "`Trdsta` 为 2（ST）或 3（*ST）的交易日，即剔除该公司—事件，而不是只看事件日当天。",
        "",
        "该样本中 ST 区间跨度较大，若只按事件日判定，会保留大量估计窗内为 ST 的观测",
        "（例如惠天热电、华电辽能在 2024-07-02 事件日已摘帽，但估计窗内仍有 96 天和 100 天为 ST）。",
        "下表含已被其他规则剔除的观测，用于说明 ST 覆盖面：",
        "",
        md_table(
            sample[sample["窗口内ST天数"].gt(0)]
            .groupby(["Stkcd", "股票名称"])
            .agg(
                涉及事件数=("event_id", "nunique"),
                涉及事件=("event_id", lambda s: "、".join(sorted(s))),
                估计窗ST天数=("估计窗ST天数", "sum"),
                事件窗ST天数=("事件窗ST天数", "sum"),
            )
            .reset_index()
        ),
        "",
        "## 4. 逐事件样本漏斗",
        "",
        md_table(funnel_df),
        "",
        "## 5. 可用样本的事件日状态与窗口完整性",
        "",
        md_table(
            analysis.groupby("event_id")
            .agg(
                可用样本数=("Stkcd", "nunique"),
                窗口内ST天数=("窗口内ST天数", "sum"),
                窗口m1_1完整=("窗口m1_1完整", "sum"),
                窗口0_1完整=("窗口0_1完整", "sum"),
                窗口0_3完整=("窗口0_3完整", "sum"),
            )
            .reset_index()
        ),
        "",
        "## 6. 剔除原因明细（按事件）",
        "",
    ]

    for event_id, sub in ledger.groupby("event_id", sort=False):
        lines.append(f"### 事件 {event_id}（{sub['event_date'].iloc[0]}）")
        lines.append("")
        detail = (
            sub.groupby(["exclusion_reason"])
            .agg(代码数=("Stkcd", "nunique"), 公司=("股票名称", lambda s: "、".join(sorted(s))))
            .reset_index()
        )
        lines.append(md_table(detail))
        lines.append("")

    lines += [
        "## 7. 口径说明",
        "",
        "- `NO_RECORD_ON_EVENT` 的 `reason_detail` 区分退市、上市晚于事件日、事件日停牌三种情形。",
        "- 判定顺序为：事件日无记录 → 上市不足 → ST/*ST → 估计窗不足 → 主窗口不完整，同一公司—事件只记一个主因。",
        "- `ST_IN_WINDOW` 以估计窗 `[-120, -21]` 与事件窗 `[-1, +3]` 的并集判定；`事件日ST标记` 仅保留为对照，不再作为剔除条件。",
        "- 补充窗口 `[-1, +1]`、`[0, +3]` 的完整性以独立列给出；主样本只要求 `[0, +1]` 完整。",
        "- 最终分析样本为 `analysis_sample.csv`（`eligible = 1`），共 "
        f"{len(analysis)} 个公司—事件、{analysis['event_id'].nunique()} 个事件。",
        "- 本步骤只输出样本资格，不产生 CAR，不对政策方向作任何推断。",
    ]
    (OUT / "sample_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    sample.to_excel(OUT / "company_event_sample.xlsx", index=False)
    analysis.to_excel(OUT / "analysis_sample.xlsx", index=False)

    print(f"A-share records={len(kept):,} codes={kept['Stkcd'].nunique()}")
    print(f"company-event rows={len(sample)}, eligible={int(sample['eligible'].sum())}")
    print(funnel_df.to_string(index=False))


if __name__ == "__main__":
    main()

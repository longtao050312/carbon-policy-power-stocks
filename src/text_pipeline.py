"""Clean and aggregate Eastmoney Guba main-post data.

Dictionary labels generated here are candidate labels for manual review. They
must not be treated as validated sentiment or uncertainty labels without a
double-coded validation sample.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


REQUIRED_COLUMNS = {
    "帖子ID",
    "股吧代码",
    "帖子标题",
    "帖子内容(原始)",
    "帖子发表者ID",
    "帖子发表者昵称",
    "帖子发布时间",
    "帖子来源",
}

A_SHARE_PATTERN = re.compile(
    r"^(000|001|002|003|300|301|600|601|603|605|688|689)\d{3}$"
)

MEDIA_AUTHOR_PATTERNS = (
    "东方财富资讯",
    "金融界",
    "格隆汇",
    "证券时报",
    "财联社",
    "中国证券报",
    "上海证券报",
    "资讯",
)

POLICY_TERMS = (
    "碳市场",
    "碳排放",
    "碳配额",
    "配额",
    "履约",
    "清缴",
    "碳价",
    "ccer",
    "自愿减排",
    "方法学",
    "绿证",
    "基准值",
    "排放权",
)

UNCERTAINTY_TERMS = (
    "是否",
    "能否",
    "会不会",
    "怎么",
    "如何",
    "多少",
    "不确定",
    "不清楚",
    "没看懂",
    "适不适用",
    "什么意思",
    "？",
    "?",
)

POSITIVE_TERMS = (
    "利好",
    "受益",
    "增收",
    "收益",
    "降低成本",
    "超预期",
    "看好",
)

NEGATIVE_TERMS = (
    "利空",
    "成本上升",
    "增加成本",
    "亏损",
    "压力",
    "不及预期",
    "看空",
)


def read_posts(path: Path, sheet_name: str = "帖子详情表") -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def normalize_code(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = re.sub(r"\.0$", "", str(value).strip())
    if text.isdigit():
        text = text.zfill(6)
    return text if A_SHARE_PATTERN.fullmatch(text) else None


def html_to_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def classify_sentiment(text: str) -> str:
    positive = sum(term in text for term in POSITIVE_TERMS)
    negative = sum(term in text for term in NEGATIVE_TERMS)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def clean_posts(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Guba data missing columns: {sorted(missing)}")

    data = frame.copy()
    data["stock_code"] = data["股吧代码"].map(normalize_code)
    data["published_at"] = pd.to_datetime(
        data["帖子发布时间"], errors="coerce"
    )
    data["title_clean"] = data["帖子标题"].fillna("").map(html_to_text)
    data["content_clean"] = data["帖子内容(原始)"].map(html_to_text)
    data["text"] = (
        data["title_clean"].str.strip() + " " + data["content_clean"].str.strip()
    ).str.strip()
    data["author_name"] = data["帖子发表者昵称"].fillna("").astype(str)
    data["is_media_candidate"] = data["author_name"].map(
        lambda value: any(term in value for term in MEDIA_AUTHOR_PATTERNS)
    )

    data = data.dropna(subset=["帖子ID", "stock_code", "published_at"])
    data = data[data["text"].ne("")]
    data = data.drop_duplicates("帖子ID", keep="first")

    # These are candidate labels. Validate them manually before analysis.
    data["policy_relevant_candidate"] = data["text"].map(
        lambda value: contains_any(value, POLICY_TERMS)
    )
    data["uncertainty_candidate"] = data["text"].map(
        lambda value: contains_any(value, UNCERTAINTY_TERMS)
    ) & data["policy_relevant_candidate"]
    data["sentiment_candidate"] = data["text"].map(classify_sentiment)
    data["post_date"] = data["published_at"].dt.normalize()
    return data.sort_values(["stock_code", "published_at"])


def aggregate_daily(cleaned: pd.DataFrame) -> pd.DataFrame:
    valid = cleaned[~cleaned["is_media_candidate"]].copy()
    valid["policy_post"] = valid["policy_relevant_candidate"].astype(int)
    valid["uncertainty_post"] = valid["uncertainty_candidate"].astype(int)
    valid["positive_post"] = (
        valid["sentiment_candidate"].eq("positive")
        & valid["policy_relevant_candidate"]
    ).astype(int)
    valid["negative_post"] = (
        valid["sentiment_candidate"].eq("negative")
        & valid["policy_relevant_candidate"]
    ).astype(int)

    daily = (
        valid.groupby(["stock_code", "post_date"], as_index=False)
        .agg(
            valid_posts=("帖子ID", "count"),
            policy_posts=("policy_post", "sum"),
            uncertainty_posts=("uncertainty_post", "sum"),
            positive_policy_posts=("positive_post", "sum"),
            negative_policy_posts=("negative_post", "sum"),
        )
    )
    daily["policy_attention"] = daily["policy_posts"] / daily["valid_posts"]
    daily["uncertainty_share"] = daily["uncertainty_posts"].div(
        daily["policy_posts"].replace(0, pd.NA)
    )
    daily["net_sentiment"] = (
        daily["positive_policy_posts"] - daily["negative_policy_posts"]
    ).div(daily["policy_posts"].replace(0, pd.NA))
    return daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", type=Path, required=True)
    parser.add_argument("--sheet", default="帖子详情表")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/text"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cleaned = clean_posts(read_posts(args.posts, args.sheet))
    daily = aggregate_daily(cleaned)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.out_dir / "posts_cleaned_candidates.csv", index=False)
    daily.to_csv(args.out_dir / "daily_candidate_metrics.csv", index=False)
    print(
        f"Saved {len(cleaned):,} cleaned posts and "
        f"{len(daily):,} stock-date rows to {args.out_dir}"
    )


if __name__ == "__main__":
    main()

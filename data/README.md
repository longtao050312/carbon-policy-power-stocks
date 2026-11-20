# Data setup

Raw and processed datasets are intentionally excluded from Git because they may be licensed, purchased, or contain platform user data.

## Expected local layout

```text
data/
├── raw/
│   ├── TRD_Dalyr.xlsx
│   ├── TRD_Cndalym.xlsx
│   ├── guba_posts.xlsx
│   └── company_exposure.xlsx
└── processed/
```

## Required CSMAR fields

### `TRD_Dalyr`

- `Stkcd`: six-digit security code
- `Trddt`: trading date
- `Trdsta`: trading status
- `Dretwd`: daily stock return with cash dividends reinvested
- `Dsmvosd`: circulating market value

Optional fields: close price, trading value, and trading volume.

### `TRD_Cndalym`

- `Markettype`
- `Trddt`
- `Cdretwdos`: value-weighted daily market return with cash dividends reinvested

The primary market portfolio is `Markettype = 21`.

## Required Guba post fields

The purchased data must contain all posts for the selected stocks and date windows, not only keyword matches.

- 帖子ID
- 股吧代码
- 股吧名称
- 帖子标题
- 帖子内容(原始)
- 帖子发表者ID
- 帖子发表者昵称
- 帖子发布时间, preferably precise to seconds
- 帖子来源
- 阅读量
- 评论数

The provider must also document collection coverage, missing periods, deduplication, deleted-post handling, and whether a zero count means no posts or a missing archive.

Replies, followers, and full user profiles are not required for the core study. A joinable author-account-type mapping is useful if inexpensive.

## Current data status

The initial CSMAR trial exports were incomplete:

- `TRD_Dalyr`: 102,902 records and 89 codes, but only `Stkcd` was exported.
- `TRD_Cndalym`: 27,645 records and 19 market types, but only `Markettype` was exported.
- Codes `200037`, `200539`, and `900937` are B shares and must be excluded.

No empirical result should be reported until dates and return fields are re-exported and validated.

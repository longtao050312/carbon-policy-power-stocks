# Agent guidance

## Project purpose

This repository supports an undergraduate finance thesis on major Chinese
national carbon-market policy announcements, A-share power-company returns,
and Eastmoney Guba discussion.

Use Chinese for research-facing prose and English for code identifiers.

## Non-negotiable research rules

1. Never invent empirical results, sample sizes, significance levels, or data coverage.
2. Keep the five core policy events separate. Do not estimate a general average
   carbon-policy effect unless the event sample is explicitly expanded and revalidated.
3. Do not describe Guba discussion as a mediator or causal driver of stock returns.
   The supported language is content explanation, temporal association, or incremental
   predictive information.
4. Do not change event windows, sample rules, or event inclusion after inspecting CAR signs.
5. Preserve the distinction between document date, first public date, effective date,
   and stock-market event date.
6. Strong and voluntary carbon-market policies must be identified separately.
7. Exposure variables must use information publicly available before each event.
8. Do not commit licensed CSMAR data, purchased Guba data, user-level data, or Word drafts.

## Event-study defaults

- Estimation window: `[-120, -21]`
- Minimum estimation observations: `60`
- Main event window: `[0, +1]`
- Additional windows: `[-1, +1]`, `[0, +3]`
- Pre-event diagnostic: `[-5, -2]`
- Primary market portfolio: CSMAR `Markettype = 21`
- Stock return: `Dretwd`
- Market return: `Cdretwdos`

Report each event separately. Cross-sectional company counts do not replace the
number of independent policy events.

## Text-analysis defaults

- The denominator for attention is all valid ordinary-user main posts for a
  stock-date, not keyword-hit posts.
- Exclude media accounts, automated news, announcement scraping, and duplicates.
- Keep unrelated ordinary-user posts because they belong in the attention denominator.
- Dictionary labels are candidates only. Validate on a double-coded manual sample.
- Use first publication time, not last activity time.
- A discussion window must end before the return window begins for temporal tests.

## Data handling

Raw data belongs under `data/raw/` and is ignored by Git. Generated files belong
under `outputs/` and are also ignored. Document every filter and preserve a
sample-exclusion reason table.

Before changing code, read:

- `README.md`
- `docs/research-design.md`
- `docs/workflow.md`
- `data/README.md`
- `config/events.csv`

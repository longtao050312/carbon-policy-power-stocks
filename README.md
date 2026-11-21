# 全国碳市场政策、电力股反应与投资者讨论

本科金融学论文的研究资料与可复现分析骨架。项目研究五项典型全国碳市场政策首次公开后，A股发电公司的短期异常收益，并利用东方财富股吧文本解释投资者关注的政策内容。

## 研究主线

1. 使用事件研究法逐项估计政策发布后的异常收益和累计异常收益（CAR）；
2. 使用文本分析法度量同一政策前后的股吧关注度和不确定性表达；
3. 将政策新增条款、企业事前业务暴露、CAR和投资者讨论放在同一事件表中；
4. 仅在讨论发生时间严格早于股票结果窗口时，探索早期讨论与后续行情的时序关联。

本项目不把五项典型事件外推为全部碳政策的一般平均影响，也不把股吧讨论设定为中介变量。

## 当前状态

- [x] 五项核心政策和一个补充政策的官方日期已核查；
- [x] 事件研究窗口、文本变量和连接方案已确定；
- [x] CSMAR 行情已合并为 99,275 行、86 个 A 股代码（2021-01-04 至 2025-12-31），市场收益取 `Markettype = 21`；
- [x] 公司—事件样本已核定 484 个（A 80、B 80、C 81、D 81、E 81、F 81），剔除台账与停牌缺口已保存；
- [x] 事件研究已完成，稳健性、事前市值分组与极值核查已完成；
- [x] CnOpenData 股吧样例字段与发帖密度已体检；
- [x] 论文第五章已按实测结果填表；
- [ ] 逐事件煤电暴露与公告前 CCER 适用项目分组；
- [ ] 按政策窗口采购全量股吧主帖；
- [ ] 回填第六章表 6-1、表 6-2。

主窗口 `[0, +1]` 等权 CAR：A +1.14%、B +1.81%、C −4.18%、D −0.39%、E +0.16%、F +0.18%。五项核心事件中 A、B 为正、C 为负，D 与 E 在当日不显著；E 的反应后移至次日。同一事件的个股异常收益高度同向，表内 t 值只能作描述性参考，口径、稳健性与限制见 [`docs/event-study-report.md`](docs/event-study-report.md)，过程决定见 [`docs/session-log-2026-11-21.md`](docs/session-log-2026-11-21.md)。

本仓库只保存可复现的分析代码与文档，不保存论文稿、结果工作簿与授权数据。

## 政策事件

核心事件：

- A：2021、2022年度发电行业配额方案，股票事件日为2023-03-15；
- B：首批CCER项目方法学，股票事件日为2023-10-24；
- C：《碳排放权交易管理暂行条例》，周日晚公开，股票事件日为2024-02-05；
- D：2023、2024年度配额方案征求意见稿，股票事件日为2024-07-02；
- E：2023、2024年度配额方案正式稿，主口径为2024-10-21，2024-10-16作敏感性日期。

补充事件：

- F：绿证与CCER衔接通知，2024-08-27与2024-09-11分别检验。

完整日期、类别和官方来源见 [`config/events.csv`](config/events.csv)。

## 方法

### 事件研究

- 估计窗口：`[-120, -21]`
- 最低有效交易日：`60`
- 主窗口：`[0, +1]`
- 补充窗口：`[-1, +1]`、`[0, +3]`
- 提前反应窗口：`[-5, -2]`
- 个股收益：CSMAR `Dretwd`
- 市场收益：`Markettype = 21`对应的`Cdretwdos`

五项政策逐项报告。强制市场和自愿市场不合并解释。

### 股吧文本

核心变量：

- 政策关注度＝政策相关普通用户主帖数／全部有效普通用户主帖数；
- 不确定性占比＝不确定性政策帖数／政策相关帖数；
- 净情绪＝正面政策帖占比－负面政策帖占比；
- 意见分歧用于解释绝对异常收益或波动，不用于直接判断涨跌方向。

帖子必须来自公司—日期的全量主帖，关键词命中数据不能构成关注度分母。

### 股吧与股价的连接

最低要求是逐事件综合对照。时序检验按以下优先级进行：

1. 公告后至开盘前讨论 → 开盘后异常收益或波动；
2. 第0日讨论 → 第1至第3日行情，并控制第0日已经发生的收益；
3. 同一政策内部控制业务暴露和事前公司特征的公司比较。

结论只能表述为内容解释、时序关联或增量预测信息。

## 项目结构

```text
.
├── AGENTS.md
├── README.md
├── config/
│   └── events.csv
├── data/
│   ├── README.md
│   └── reference/
│       └── stock_names.csv
├── docs/
│   ├── research-design.md
│   ├── workflow.md
│   ├── event-study-report.md
│   ├── session-log-2026-11-21.md
│   └── figures/
│       ├── fig5_1_car_curves.png
│       └── fig5_2_car_bar.png
├── src/
│   ├── build_daily_panel.py
│   ├── build_sample.py
│   ├── event_study_main.py
│   ├── build_event_results.py
│   ├── build_panel_xlsx.py
│   ├── fetch_stock_names.py
│   ├── fill_missing_names.py
│   ├── event_study.py
│   └── text_pipeline.py
└── requirements.txt
```

Word论文稿、CSMAR数据和股吧样本保留在本地，不提交GitHub。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

按[`data/README.md`](data/README.md)准备本地数据。样本构建与事件研究的完整流程：

```bash
python src/build_daily_panel.py    # 合并两张 CSMAR 表，生成日度面板
python src/build_sample.py         # 核定公司—事件样本与剔除台账
python src/event_study_main.py     # 估计 AR 与各窗口 CAR
python src/build_event_results.py  # 生成结果工作簿与论文配图
```

路径为脚本内置的 `data/processed/` 与 `outputs/`，不需要额外参数；`src/event_study.py` 是早期带命令行参数的独立版本，仅用于核对。

运行股吧清洗和候选标签：

```bash
python src/text_pipeline.py \
  --posts data/raw/guba_posts.xlsx
```

输出默认写入`outputs/`，该目录不会提交Git。

## 给Codex或其他编码代理

开始工作前请依次阅读：

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/research-design.md`](docs/research-design.md)
3. [`docs/workflow.md`](docs/workflow.md)
4. [`docs/event-study-report.md`](docs/event-study-report.md)
5. [`docs/session-log-2026-11-21.md`](docs/session-log-2026-11-21.md)
6. [`data/README.md`](data/README.md)
7. [`config/events.csv`](config/events.csv)

优先任务是数据验证和可复现计算，不是补写“预期结果”。任何新增分析都必须保留事件日、窗口、样本剔除和字段来源记录。

## 数据与隐私

仓库为私有仓库，但仍不提交：

- CSMAR或Wind授权数据；
- 购买的股吧历史数据；
- 用户级原始文本和账号信息；
- 本地Word论文稿；
- 自动生成的结果文件。

这些文件均由`.gitignore`排除。

# -*- coding: utf-8 -*-
"""生成事件研究结果工作簿（中文表头）与论文用图"""
import os
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import xlsxwriter

BASE = r"D:\毕业论文\毕业论文11月\carbon-policy-power-stocks"
ES = os.path.join(BASE, "outputs", "event_study")
FIG = os.path.join(ES, "figures")
os.makedirs(FIG, exist_ok=True)

# ---------- 中文字体 ----------
for f in ["SimHei", "Microsoft YaHei", "SimSun"]:
    try:
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [f]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

ev = pd.read_csv(os.path.join(BASE, "config", "events.csv"))
EV = ev.set_index("event_id")
EV_LABEL = {
    "A": "A 配额方案(2021-2022年度)",
    "B": "B 首批CCER方法学",
    "C": "C 碳排放权交易管理暂行条例",
    "D": "D 配额方案征求意见稿",
    "F": "F 绿证与CCER衔接通知",
    "E": "E 配额方案正式稿",
}
SHORT = {"A": "A", "B": "B", "C": "C", "D": "D", "F": "F", "E": "E"}
ORDER = ["A", "B", "C", "D", "F", "E"]

car = pd.read_csv(os.path.join(ES, "company_event_car.csv"), dtype={"Stkcd": str})
ar = pd.read_csv(os.path.join(ES, "abnormal_returns.csv"), dtype={"Stkcd": str}, parse_dates=["Trddt"])
summ = pd.read_csv(os.path.join(ES, "event_summary.csv"))
capw = pd.read_csv(os.path.join(ES, "summary_capweighted.csv"))
shift = pd.read_csv(os.path.join(ES, "summary_shift1.csv"))

car["Stkcd"] = car["Stkcd"].str.zfill(6)
ar["Stkcd"] = ar["Stkcd"].str.zfill(6)

WIN_LABEL = {"car_0_1": "[0,+1]", "car_m1_1": "[-1,+1]", "car_0_3": "[0,+3]", "car_m5_m2": "[-5,-2]"}
WIN_ORDER = ["car_0_1", "car_m1_1", "car_0_3", "car_m5_m2"]


def stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.1 else ""))


# ---------- 表1：主结果（市场模型） ----------
def tidy(df, model_label):
    d = df.copy()
    d = d[d["model"] == "市场模型"] if "model" in d.columns else d
    d["事件"] = d["event_id"]
    d["窗口"] = d["window"].map(WIN_LABEL)
    d["显著性"] = d["p"].apply(stars)
    return d


main = tidy(summ, "市场模型")
main["政策类型"] = main["event_id"].map(lambda x: "强制" if EV.loc[x, "market_type"] == "mandatory" else "自愿")
main["政策名称"] = main["event_id"].map(lambda x: EV.loc[x, "policy_name"])
main["样本角色"] = main["event_id"].map(lambda x: {"core": "核心事件", "supplementary": "补充事件"}[EV.loc[x, "sample_role"]])
main["事件序"] = main["event_id"].map({k: i for i, k in enumerate(ORDER)})
main["窗口序"] = main["window"].map({k: i for i, k in enumerate(WIN_ORDER)})
main = main.sort_values(["事件序", "窗口序"]).drop(columns=["window"])

COLS_CN = {
    "event_id": "事件",
    "policy_type": "政策类型",
    "policy_name": "政策名称",
    "sample_role": "样本角色",
    "event_date": "事件日(股票)",
    "window": "窗口",
    "N": "样本数N",
    "mean": "平均CAR",
    "median": "中位CAR",
    "sd": "截面标准差",
    "t": "t值",
    "p": "p值",
    "pct_positive": "CAR为正占比",
    "min": "最小值",
    "max": "最大值",
    "显著性": "显著性",
}
SHEET1 = main[["event_id", "政策类型", "政策名称", "样本角色", "event_date", "窗口", "N",
               "mean", "median", "sd", "t", "p", "pct_positive", "min", "max", "显著性"]].rename(
    columns={k: v for k, v in COLS_CN.items() if k != "window"})

# ---------- 表2：稳健性 ----------
rob = []
for label, df, wcol in [("市场调整模型（等权）", summ[summ["model"] == "市场调整"], "window"),
                        ("流通市值加权（市场模型）", capw, "window")]:
    d = df.copy()
    if label.startswith("流通"):
        d["mean"] = d["cap_weighted_mean"]
        d["p"] = np.nan
        d["t"] = np.nan
        d["median"] = np.nan
        d["sd"] = np.nan
        d["pct_positive"] = np.nan
        d["min"] = np.nan
        d["max"] = np.nan
    d["检验"] = label
    rob.append(d)
d = shift.copy()
d["检验"] = "事件日顺延1个交易日（市场模型）"
rob.append(d)
rob = pd.concat(rob, ignore_index=True)
rob["窗口"] = rob["window"].map(WIN_LABEL)
rob["显著性"] = rob["p"].apply(stars)
rob["政策类型"] = rob["event_id"].map(lambda x: "强制" if EV.loc[x, "market_type"] == "mandatory" else "自愿")
rob["检验序"] = rob["检验"].map({k: i for i, k in enumerate(["市场调整模型（等权）", "流通市值加权（市场模型）", "事件日顺延1个交易日（市场模型）"])})
rob["事件序"] = rob["event_id"].map({k: i for i, k in enumerate(ORDER)})
rob["窗口序"] = rob["window"].map({k: i for i, k in enumerate(WIN_ORDER)})
rob = rob.sort_values(["检验序", "事件序", "窗口序"]).drop(columns=["window", "检验序", "事件序", "窗口序"])
SHEET2 = rob[["检验", "event_id", "政策类型", "event_date", "窗口", "N", "mean", "median", "sd", "t", "p",
              "pct_positive", "min", "max", "显著性"]].rename(
    columns={"检验": "检验口径", "event_id": "事件", "event_date": "事件日(所用)", "N": "样本数N",
             "mean": "平均CAR", "median": "中位CAR", "sd": "截面标准差", "t": "t值", "p": "p值",
             "pct_positive": "CAR为正占比", "min": "最小值", "max": "最大值"})

# ---------- 表3：公司—事件明细 ----------
det = car.copy()
det["事件"] = det["event_id"]
det["政策名称"] = det["event_id"].map(lambda x: EV.loc[x, "policy_name"])
det["事件日"] = det["event_date"]
det["证券代码"] = det["Stkcd"]
det["股票简称"] = det["股票名称"]
det = det.sort_values(["event_id", "Stkcd"], key=lambda s: s.map({k: i for i, k in enumerate(ORDER)}) if s.name == "event_id" else s)
SHEET3 = det[["事件", "政策名称", "事件日", "证券代码", "股票简称", "beta", "alpha", "est_days", "resid_sd",
              "pre_cap", "car_0_1", "car_m1_1", "car_0_3", "car_m5_m2",
              "car_0_1_ma", "car_m1_1_ma", "car_0_3_ma", "car_m5_m2_ma"]].rename(columns={
    "beta": "市场模型β", "alpha": "市场模型α(日)", "est_days": "估计窗有效交易日",
    "resid_sd": "残差标准差", "pre_cap": "事件前流通市值(千元)",
    "car_0_1": "CAR[0,+1]", "car_m1_1": "CAR[-1,+1]", "car_0_3": "CAR[0,+3]", "car_m5_m2": "CAR[-5,-2]",
    "car_0_1_ma": "市场调整CAR[0,+1]", "car_m1_1_ma": "市场调整CAR[-1,+1]",
    "car_0_3_ma": "市场调整CAR[0,+3]", "car_m5_m2_ma": "市场调整CAR[-5,-2]"})

# ---------- 表4：日度平均异常收益 ----------
day = (ar[ar["rel_day"].between(-5, 5)]
       .groupby(["event_id", "rel_day"])
       .agg(N=("AR", "size"), AR均值=("AR", "mean"), AR中位数=("AR", "median"),
            AR为正占比=("AR", lambda s: float((s > 0).mean())))
       .reset_index()
       .rename(columns={"event_id": "事件", "rel_day": "相对事件日"}))
day["AR均值"] = day["AR均值"]
day = day.sort_values(["事件", "相对事件日"], key=lambda s: s.map({k: i for i, k in enumerate(ORDER)}) if s.name == "事件" else s)
SHEET4 = day

# ---------- 表5：口径说明 ----------
notes = [
    ["项目", "内容"],
    ["数据来源", "CSMAR 日个股回报率文件（TRD_Dalyr）+ 综合日市场回报率文件（TRD_Cndalym，Markettype=21 流通市值加权）"],
    ["股票池", "A 股发电行业上市公司（火电/水电/核电/风电光伏及其他发电），已剔除 B 股、事件窗内停牌、事件日无交易记录、上市不足、ST/*ST"],
    ["样本规模", "84 只股票，484 个公司—事件观测；各事件 A80/B80/C81/D81/F81/E81"],
    ["事件日", "以政策首次公开后首个可交易日的股票事件日为准：A 2023-03-15、B 2023-10-24、C 2024-02-05（公开日 02-04，周日）、D 2024-07-02、F 2024-08-27、E 2024-10-21"],
    ["估计窗", "事件日前 [-120,-21] 的交易日，最少 60 个有效交易日；本样本实际 90~100 个"],
    ["正常收益模型", "市场模型：R_it = α_i + β_i·R_mt + ε_it，AR_it = R_it − (α_i + β_i·R_mt)"],
    ["市场收益", "CSMAR 综合日市场回报率文件，Markettype=21：上证A股（不含科创板）＋深证A股（不含创业板）＋创业板，即沪深A股整体（不含科创板、北证），流通市值加权（Cdretwdos）"],
    ["市场收益口径说明", "Markettype 为板块位掩码（1 上证A、2 上证B、4 深证A、8 深证B、16 创业板、32 科创板、64 北证）；21=1+4+16。样本 84 只无科创板股票，基准覆盖完整；该文件不含行业指数"],
    ["主窗口", "[0,+1] 两日累计；补充窗口 [-1,+1]、[0,+3]；提前反应窗口 [-5,-2]"],
    ["CAR 含义", "累计异常收益，正值为相对市场模型的超额上涨；单位均为小数（工作簿已设为百分比格式）"],
    ["显著性检验", "对公司—事件 CAR 做截面单样本 t 检验；p 值为双侧"],
    ["显著性标记", "*** p<0.01，** p<0.05，* p<0.1"],
    ["重要提示", "同一事件的个股 AR 高度同向（行业共同冲击），截面 t 值会高估独立信息量，属描述性统计；不宜据此直接推断总体显著性"],
    ["公司—事件重复", "同一股票在多个事件中重复出现，跨事件合并统计会重复计权，因此本工作簿不做跨事件平均"],
    ["复现脚本", r"src\event_study_main.py；输入 data\processed\daily_returns_ashare.csv 与 outputs\sample\analysis_sample.csv"],
    ["生成日期", "2026-11-20"],
]

# ---------- 写 Excel ----------
out = os.path.join(ES, "事件研究结果.xlsx")
if os.path.exists(out):
    shutil.copy(out, out + ".bak")
wb = xlsxwriter.Workbook(out)
fmt_pct = wb.add_format({"num_format": "0.00%"})
fmt_pct3 = wb.add_format({"num_format": "0.000%"})
fmt_num3 = wb.add_format({"num_format": "0.000"})
fmt_num2 = wb.add_format({"num_format": "0.00"})
fmt_big = wb.add_format({"num_format": "#,##0"})
fmt_sci = wb.add_format({"num_format": "0.00E+00"})
hdr = wb.add_format({"bold": True, "bg_color": "#DCE6F1", "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True})
wrap = wb.add_format({"text_wrap": True, "valign": "top"})


def write_sheet(name, df, pct_cols=(), pct3_cols=(), num3_cols=(), num2_cols=(), big_cols=(), widths=None, wrap_cols=(), sci_cols=()):
    ws = wb.add_worksheet(name)
    for j, c in enumerate(df.columns):
        ws.write(0, j, c, hdr)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, (c, v) in enumerate(zip(df.columns, row)):
            f = None
            if c in pct_cols:
                f = fmt_pct
            elif c in pct3_cols:
                f = fmt_pct3
            elif c in sci_cols:
                f = fmt_sci
            elif c in num3_cols:
                f = fmt_num3
            elif c in num2_cols:
                f = fmt_num2
            elif c in big_cols:
                f = fmt_big
            elif c in wrap_cols:
                f = wrap
            if isinstance(v, float) and (pd.isna(v)):
                ws.write(i, j, "", f)
            elif isinstance(v, (np.floating,)):
                ws.write(i, j, float(v), f)
            elif isinstance(v, (np.integer,)):
                ws.write(i, j, int(v), f)
            else:
                ws.write(i, j, v, f)
    ws.freeze_panes(1, 0)
    if len(df) > 0:
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)
    ws.set_row(0, 30)
    for j, c in enumerate(df.columns):
        w = (widths or {}).get(c, max(10, min(34, int(max([len(str(c))] + [len(str(x)) for x in df[c].head(50)]) * 1.6) + 2)))
        ws.set_column(j, j, w)


# 说明
ws = wb.add_worksheet("说明")
ws.write(0, 0, "全国碳市场政策事件研究：结果汇总说明", wb.add_format({"bold": True, "font_size": 14}))
ws.set_row(0, 24)
for i, (a, b) in enumerate(notes, start=1):
    ws.write(i, 0, a, hdr if i == 1 else wb.add_format({"bold": True, "valign": "top", "text_wrap": True, "border": 1}))
    ws.write(i, 1, b, hdr if i == 1 else wrap)
ws.set_column(0, 0, 16)
ws.set_column(1, 1, 100)
ws.freeze_panes(1, 0)

write_sheet("表1_主结果_市场模型", SHEET1,
            pct_cols=("平均CAR", "中位CAR", "截面标准差", "CAR为正占比", "最小值", "最大值"),
            num2_cols=("t值",), sci_cols=("p值",), widths={"政策名称": 44})

write_sheet("表2_稳健性", SHEET2,
            pct_cols=("平均CAR", "中位CAR", "截面标准差", "CAR为正占比", "最小值", "最大值"),
            num2_cols=("t值",), sci_cols=("p值",), widths={"检验口径": 30})

write_sheet("表3_公司事件明细", SHEET3,
            pct_cols=("CAR[0,+1]", "CAR[-1,+1]", "CAR[0,+3]", "CAR[-5,-2]",
                      "市场调整CAR[0,+1]", "市场调整CAR[-1,+1]", "市场调整CAR[0,+3]", "市场调整CAR[-5,-2]",
                      "残差标准差"),
            pct3_cols=("市场模型α(日)",), num3_cols=("市场模型β",), big_cols=("事件前流通市值(千元)",),
            widths={"政策名称": 40})

write_sheet("表4_日度异常收益", SHEET4,
            pct_cols=("AR均值", "AR中位数", "AR为正占比"))

wb.close()
print("工作簿已生成:", out)

# ---------- 图1：分事件累计异常收益曲线 ----------
fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.2), sharex=True)
rel = list(range(-5, 6))
for ax, e in zip(axes.ravel(), ORDER):
    sub = ar[(ar["event_id"] == e) & (ar["rel_day"].between(-5, 5))]
    cum = sub.groupby("rel_day")["AR"].mean().reindex(rel, fill_value=np.nan)
    c = cum.cumsum()
    se = sub.groupby("rel_day")["AR"].agg(lambda s: s.std() / np.sqrt(len(s))).reindex(rel)
    lo = c - 1.96 * se.cumsum()
    hi = c + 1.96 * se.cumsum()
    ax.fill_between(rel, lo * 100, hi * 100, alpha=0.18)
    ax.plot(rel, c * 100, marker="o", ms=3.2, lw=1.6)
    ax.axvline(0, color="grey", ls="--", lw=0.8)
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_title(f"{EV_LABEL[e]}（{EV.loc[e,'event_date']}）", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(alpha=0.25, lw=0.5)
axes[0, 0].set_ylabel("累计异常收益 CAR（%）", fontsize=9)
axes[1, 0].set_ylabel("累计异常收益 CAR（%）", fontsize=9)
for ax in axes[1]:
    ax.set_xlabel("相对事件日（0 = 股票事件日）", fontsize=9)
fig.suptitle("图5-1  分事件累计异常收益（市场模型，阴影为截面±1.96倍标准误）", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.95])
p1 = os.path.join(FIG, "fig5_1_car_curves.png")
fig.savefig(p1, dpi=200)
plt.close(fig)

# ---------- 图2：CAR[0,+1] 分事件对比（等权 vs 市值加权） ----------
mm = summ[(summ["model"] == "市场模型") & (summ["window"] == "car_0_1")].set_index("event_id").reindex(ORDER)
cw = capw[capw["window"] == "car_0_1"].set_index("event_id").reindex(ORDER)
x = np.arange(len(ORDER))
fig, ax = plt.subplots(figsize=(8.2, 4.2))
ax.bar(x - 0.19, mm["mean"] * 100, width=0.36, label="等权平均", color="#3b6ea5")
ax.bar(x + 0.19, cw["cap_weighted_mean"] * 100, width=0.36, label="流通市值加权", color="#c8873a")
ax.errorbar(x - 0.19, mm["mean"] * 100, yerr=1.96 * mm["sd"] / np.sqrt(mm["N"]) * 100,
            fmt="none", ecolor="#1f3f5c", capsize=3, lw=1)
ax.axhline(0, color="grey", lw=0.8)
ax.set_xticks(x)
ax.set_xticklabels([f"{e}\n{EV.loc[e,'event_date'][5:]}" for e in ORDER], fontsize=9)
ax.set_ylabel("CAR[0,+1]（%）", fontsize=9)
ax.set_title("图5-2  事件窗口[0,+1]累计异常收益：等权与市值加权对比", fontsize=10)
ax.legend(fontsize=8, frameon=False)
ax.grid(axis="y", alpha=0.25, lw=0.5)
fig.tight_layout()
p2 = os.path.join(FIG, "fig5_2_car_bar.png")
fig.savefig(p2, dpi=200)
plt.close(fig)
print("图已生成:", p1, p2)
print("行数:", len(SHEET1), len(SHEET2), len(SHEET3), len(SHEET4))

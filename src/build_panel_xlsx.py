"""Render the A-share daily panel as a formatted workbook with Chinese headers.

The CSV keeps its English identifiers because downstream scripts and Stata read
them; this workbook is the presentation layer and carries Chinese column names,
a frozen header row, per-column number formats and a field-mapping sheet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "data" / "processed" / "daily_returns_ashare.csv"
DST = BASE / "data" / "processed" / "daily_returns_ashare.xlsx"

RENAME = {
    "Stkcd": "证券代码",
    "股票名称": "股票简称",
    "交易所": "交易所",
    "板块": "板块",
    "Trddt": "交易日期",
    "Clsprc": "收盘价(元)",
    "Dretwd": "日收益率(含红利再投资)",
    "Dretnd": "日收益率(不含红利)",
    "Dsmvosd": "流通市值(千元)",
    "Dnshrtrd": "成交股数(股)",
    "Dnvaltrd": "成交金额(元)",
    "stock_markettype": "个股市场类型",
    "Trdsta": "交易状态",
    "market_return_vw": "市场收益率(流通市值加权)",
    "market_return_tv": "市场收益率(总市值加权)",
    "market_matched": "市场收益匹配",
    "is_st": "ST标记",
}

RETURN_COLS = ["日收益率(含红利再投资)", "日收益率(不含红利)",
               "市场收益率(流通市值加权)", "市场收益率(总市值加权)"]
NUM_COLS = ["流通市值(千元)", "成交股数(股)", "成交金额(元)"]
CENTER_COLS = ["证券代码", "个股市场类型", "交易状态", "市场收益匹配", "ST标记"]

FIELDS = [
    ("证券代码", "Stkcd", "六位证券代码，文本存储以保留前导零", "TRD_Dalyr"),
    ("股票简称", "股票名称", "当前证券简称，非事件当时简称", "东方财富行情接口"),
    ("交易所", "交易所", "上海 / 深圳", "按代码段推断"),
    ("板块", "板块", "沪市主板 / 深市主板 / 创业板", "按代码段推断"),
    ("交易日期", "Trddt", "交易日", "TRD_Dalyr / TRD_Cndalym"),
    ("收盘价(元)", "Clsprc", "日收盘价", "TRD_Dalyr"),
    ("日收益率(含红利再投资)", "Dretwd", "考虑现金红利再投资的日个股回报率，小数（0.0132 即 1.32%）", "TRD_Dalyr"),
    ("日收益率(不含红利)", "Dretnd", "不考虑现金红利的日个股回报率，小数", "TRD_Dalyr"),
    ("流通市值(千元)", "Dsmvosd", "日个股流通市值", "TRD_Dalyr"),
    ("成交股数(股)", "Dnshrtrd", "日个股交易股数", "TRD_Dalyr"),
    ("成交金额(元)", "Dnvaltrd", "日个股交易金额", "TRD_Dalyr"),
    ("个股市场类型", "stock_markettype", "CSMAR 个股所属市场类型编码", "TRD_Dalyr"),
    ("交易状态", "Trdsta", "1 正常，2 ST，3 *ST", "TRD_Dalyr"),
    ("市场收益率(流通市值加权)", "market_return_vw", "综合A股流通市值加权日市场回报率（Markettype=21）", "TRD_Cndalym Cdretwdos"),
    ("市场收益率(总市值加权)", "market_return_tv", "综合A股总市值加权日市场回报率（Markettype=21）", "TRD_Cndalym Cdretwdtl"),
    ("市场收益匹配", "market_matched", "1 表示该交易日匹配到市场收益", "合并指示"),
    ("ST标记", "is_st", "1 表示当日为 ST/*ST，由交易状态生成", "派生变量"),
]


def main() -> None:
    data = pd.read_csv(SRC, dtype={"Stkcd": str}, parse_dates=["Trddt"])
    data["Stkcd"] = data["Stkcd"].str.zfill(6)
    data = data.rename(columns=RENAME)

    notes = pd.DataFrame(
        [{"字段名": a, "原字段名": b, "含义与口径": c, "来源": d} for a, b, c, d in FIELDS]
    )

    with pd.ExcelWriter(DST, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        data.to_excel(writer, sheet_name="行情面板", index=False)
        notes.to_excel(writer, sheet_name="字段说明", index=False)

        wb = writer.book
        header_fmt = wb.add_format(
            {
                "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E79",
                "align": "center", "valign": "vcenter", "border": 1,
                "border_color": "#1F4E79", "font_size": 10, "text_wrap": True,
            }
        )
        ret_fmt = wb.add_format({"num_format": "0.000000"})
        price_fmt = wb.add_format({"num_format": "0.00"})
        num_fmt = wb.add_format({"num_format": "#,##0"})
        code_fmt = wb.add_format({"num_format": "@", "align": "center"})
        center_fmt = wb.add_format({"align": "center"})

        ws = writer.sheets["行情面板"]
        ws.set_row(0, 40)

        widths = {
            "证券代码": 11, "股票简称": 10, "交易所": 7, "板块": 10, "交易日期": 12,
            "收盘价(元)": 10, "日收益率(含红利再投资)": 20, "日收益率(不含红利)": 17,
            "流通市值(千元)": 15, "成交股数(股)": 14, "成交金额(元)": 16,
            "个股市场类型": 12, "交易状态": 9, "市场收益率(流通市值加权)": 22,
            "市场收益率(总市值加权)": 19, "市场收益匹配": 11, "ST标记": 8,
        }
        for idx, name in enumerate(data.columns):
            if name in RETURN_COLS:
                fmt = ret_fmt
            elif name == "收盘价(元)":
                fmt = price_fmt
            elif name in NUM_COLS:
                fmt = num_fmt
            elif name == "证券代码":
                fmt = code_fmt
            elif name in CENTER_COLS:
                fmt = center_fmt
            else:
                fmt = None
            ws.set_column(idx, idx, widths.get(name, 12), fmt)

        for idx, name in enumerate(data.columns):
            ws.write(0, idx, name, header_fmt)

        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(data), len(data.columns) - 1)

        notes_ws = writer.sheets["字段说明"]
        notes_ws.set_row(0, 26)
        notes_ws.set_column(0, 0, 26)
        notes_ws.set_column(1, 1, 22)
        notes_ws.set_column(2, 2, 58)
        notes_ws.set_column(3, 3, 24)
        for idx, name in enumerate(notes.columns):
            notes_ws.write(0, idx, name, header_fmt)
        notes_ws.freeze_panes(1, 0)

        wb.worksheets()[0].set_tab_color("#1F4E79")
        wb.worksheets()[1].set_tab_color("#808080")
        wb.set_properties({"title": "A股日度行情面板", "subject": "全国碳市场政策与电力股研究"})

    print(f"rows={len(data):,} cols={len(data.columns)} -> {DST}")
    print("headers:", " | ".join(data.columns))


if __name__ == "__main__":
    main()

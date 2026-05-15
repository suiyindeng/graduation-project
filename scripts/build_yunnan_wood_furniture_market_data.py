from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "真实数据_中国云南木材家具"

OUT_CSV = ROOT / "云南木制家具市场销售数据_官方统计版.csv"
OUT_XLSX = ROOT / "云南木制家具市场销售数据_官方统计版.xlsx"
OUT_RAW_CSV = ROOT / "云南木制家具市场销售数据_官方统计原始汇总版.csv"
OUT_RAW_XLSX = ROOT / "云南木制家具市场销售数据_官方统计原始汇总版.xlsx"
OUT_CLEAN_CSV = ROOT / "云南木制家具市场销售数据_官方统计清洗版.csv"
OUT_CLEAN_XLSX = ROOT / "云南木制家具市场销售数据_官方统计清洗版.xlsx"
OUT_SOURCE = ROOT / "云南木制家具市场销售数据_来源说明.md"


SOURCE_URLS = {
    2025: "https://stats.yn.gov.cn/Pages_22_7674.aspx",
    2024: "https://stats.yn.gov.cn/Pages_22_6933.aspx",
    2023: "https://stats.yn.gov.cn/Pages_22_3785.aspx",
    2022: "https://stats.yn.gov.cn/Pages_22_2309.aspx",
    2021: "云南省统计局统计年鉴栏目公开下载的 2021 云南统计年鉴压缩包",
    2020: "云南省统计局统计年鉴栏目公开下载的 2020 云南统计年鉴压缩包",
    2019: "云南省统计局统计年鉴栏目公开下载的 2019 云南统计年鉴压缩包",
}


COMMODITY_SALES_FILES = {
    2025: ("云南统计年鉴2025_解压/2025云南统计年鉴/4.城乡市场消费/四、城乡市场消费(1-17).xlsx", None),
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/4.城乡市场消费/4-4  限额以上批发和零售业商品销售情况（2022-2023年）续表.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/4.城乡市场消费   Urban and Rrual Consumption/4-4  限额以上批发和零售业商品销售情况-续表.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/4/4-4-sb.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/04/4-4-sb.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/04/4-4-sb--1.xls", None),
    2019: ("云南统计年鉴2019_解压/04/4-4-sb--1.xls", None),
}


ENTERPRISE_SALES_FILES = {
    2025: ("云南统计年鉴2025_解压/2025云南统计年鉴/4.城乡市场消费/四、城乡市场消费(1-17).xlsx", None),
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/4.城乡市场消费/4-5  限额以上批发和零售业法人企业商品购进、销售、库存总额（2023年）续表1.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/4.城乡市场消费   Urban and Rrual Consumption/4-5  限额以上批发和零售业法人企业商品购进、销售、库存总额-续表1.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/4/4-5-sb1.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/04/4-5-sb1.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/04/4-5-sb1--1.xls", None),
    2019: ("云南统计年鉴2019_解压/04/4-5-sb1--1.xls", None),
}


FINANCE_FILES = {
    2025: ("云南统计年鉴2025_解压/2025云南统计年鉴/4.城乡市场消费/四、城乡市场消费(1-17).xlsx", None),
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/4.城乡市场消费/4-6  限额以上批发和零售业法人企业财务状况（2023 年）续表1.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/4.城乡市场消费   Urban and Rrual Consumption/4-6  限额以上批发和零售业法人企业财务状况-续表1.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/4/4-6-sb1.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/04/4-6-sb1.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/04/4-6-sb1--1.xls", None),
    2019: ("云南统计年鉴2019_解压/04/4-6-sb1--1.xls", None),
}


REGION_RETAIL_FILES = {
    2025: ("云南统计年鉴2025_解压/2025云南统计年鉴/18.县域经济概况/十八、县域经济概况(1-50).xlsx", "18-10各州市县社会消费品零售总额（2023-2024年）"),
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/18.县域经济概况/18-12  各州市县社会消费品零售总额（2022-2023年）.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/18.县域经济概况   Survey of Intra-county Economies/18-12  各州市县社会消费品零售总额.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/18/18-12.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/18/18-12.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/18/18-12--1.xls", None),
    2019: ("云南统计年鉴2019_解压/04/4-3--1.xls", None),
}


REGION_RETAIL_CONTINUED_FILES = {
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/18.县域经济概况/18-12  各州市县社会消费品零售总额（2022-2023年）-续表.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/18.县域经济概况   Survey of Intra-county Economies/18-12  各州市县社会消费品零售总额-续表.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/18/18-12-sb.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/18/18-12-sb.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/18/18-12-sb--1.xls", None),
    2019: ("云南统计年鉴2019_解压/18/18-12-sb--1.xls", None),
}


PREFECTURE_RETAIL_FILES = {
    2024: ("云南统计年鉴2024_解压/云南统计年鉴2024/4.城乡市场消费/4-3  各州市社会消费品零售总额.xlsx", None),
    2023: ("云南统计年鉴2023_解压/2023云南统计年鉴/4.城乡市场消费   Urban and Rrual Consumption/4-3  各州市社会消费品零售总额.xls", None),
    2022: ("云南统计年鉴2022_解压/2022年云南统计年鉴EXCEL下载版/4/4-3.xls", None),
    2021: ("云南统计年鉴2021_解压/2021年云南统计年鉴/04/4-3.xls", None),
    2020: ("云南统计年鉴2020_解压/2020╘╞─╧═│╝╞─Ω╝°/04/4-3.xls", None),
    2019: ("云南统计年鉴2019_解压/04/4-3--1.xls", None),
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u2003", " ").replace("\ue003", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_excel(path: Path, sheet: str | int | None = None) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, sheet_name=sheet or 0, header=None, engine="openpyxl")
    return pd.read_excel(path, sheet_name=sheet or 0, header=None, engine="xlrd")


def source_file(rel_path: str) -> Path:
    path = SOURCE_ROOT / rel_path
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def add_record(
    records: list[dict],
    *,
    year: int,
    region: str,
    region_en: str,
    region_level: str,
    category: str,
    category_en: str,
    subject: str,
    metric: str,
    unit: str,
    value: float | None,
    source_yearbook: int,
    table_name: str,
    source_path: Path,
    scope_note: str,
):
    if value is None:
        return
    records.append(
        {
            "国家": "中国",
            "省份": "云南省",
            "地区": region,
            "地区英文": region_en,
            "地区层级": region_level,
            "年份": year,
            "数据大类": category,
            "英文大类": category_en,
            "统计对象": subject,
            "统计指标": metric,
            "单位": unit,
            "数值": round(value, 6),
            "年鉴年份": source_yearbook,
            "来源表": table_name,
            "来源文件": str(source_path.relative_to(ROOT)),
            "官方来源": SOURCE_URLS.get(source_yearbook, "云南省统计局统计年鉴栏目"),
            "口径说明": scope_note,
        }
    )


def extract_years_from_frame(df: pd.DataFrame) -> list[int]:
    years: list[int] = []
    for row in df.iloc[:12].itertuples(index=False):
        for cell in row:
            num = to_number(cell)
            if num and 1900 <= int(num) <= 2100 and int(num) not in years:
                years.append(int(num))
    return years


def extract_commodity_sales(records: list[dict]) -> None:
    metrics = [
        ("商品销售额", "亿元", "限额以上批发和零售业按商品类别统计的商品销售额"),
        ("批发额", "亿元", "限额以上批发和零售业按商品类别统计的批发额"),
        ("零售额", "亿元", "限额以上批发和零售业按商品类别统计的零售额"),
    ]
    targets = {
        "家具类": ("Furniture", "家具类"),
        "木材及制品类": ("Timber and Related Products", "木材及制品类"),
    }

    # 2025 年鉴改版后不再提供 4-4 商品类别表，使用企业行业明细表补充家具零售口径。
    for source_yearbook, (rel_path, sheet) in COMMODITY_SALES_FILES.items():
        if source_yearbook == 2025:
            continue
        path = source_file(rel_path)
        df = read_excel(path, sheet)
        years = extract_years_from_frame(df)
        if len(years) < 2:
            continue
        years = years[-2:]
        table_name = "4-4 限额以上批发和零售业商品销售情况"

        for _, row in df.iterrows():
            label = clean_text(row.iloc[0] if len(row) > 0 else "")
            if label not in targets:
                continue
            category_en, subject = targets[label]
            for metric_index, (metric, unit, note) in enumerate(metrics):
                for year_index, year in enumerate(years):
                    col = 2 + metric_index * 2 + year_index
                    value = to_number(row.iloc[col] if col < len(row) else None)
                    add_record(
                        records,
                        year=year,
                        region="云南省",
                        region_en="Yunnan",
                        region_level="省级",
                        category="木制家具及木材销售",
                        category_en="Wood furniture and timber sales",
                        subject=subject,
                        metric=metric,
                        unit=unit,
                        value=value,
                        source_yearbook=source_yearbook,
                        table_name=table_name,
                        source_path=path,
                        scope_note=note,
                    )


def find_sheet_by_keyword(path: Path, keyword: str) -> str | int:
    if path.suffix.lower() != ".xlsx":
        return 0
    xl = pd.ExcelFile(path, engine="openpyxl")
    for sheet in xl.sheet_names:
        if keyword in sheet:
            return sheet
    return 0


def extract_enterprise_purchase_sales(records: list[dict]) -> None:
    columns = [
        (2, "法人企业数", "个"),
        (3, "从业人员数", "万人"),
        (4, "商品购进总额", "亿元"),
        (5, "进口额", "亿元"),
        (6, "商品销售总额", "亿元"),
        (7, "批发额", "亿元"),
        (8, "出口额", "亿元"),
        (9, "零售额", "亿元"),
        (10, "年末库存总额", "亿元"),
        (11, "年末零售营业面积", "万平方米"),
    ]
    targets = ["五金、家具及室内装饰材料专门零售", "家具零售", "#家具零售"]

    for source_yearbook, (rel_path, sheet) in ENTERPRISE_SALES_FILES.items():
        path = source_file(rel_path)
        if source_yearbook == 2025:
            sheet = find_sheet_by_keyword(path, "4-4-1")
        df = read_excel(path, sheet)
        year = source_yearbook - 1
        table_name = "限额以上批发和零售业法人企业商品购进、销售、库存总额"

        for _, row in df.iterrows():
            label = clean_text(row.iloc[0] if len(row) > 0 else "")
            label_normalized = label.replace(" ", "").replace("#", "")
            if not any(t.replace(" ", "").replace("#", "") == label_normalized for t in targets):
                continue
            subject = "家具零售" if "家具零售" in label_normalized else "五金、家具及室内装饰材料专门零售"
            subject_en = "Furniture Merchandise" if subject == "家具零售" else "Special Retail of Hardware, Furniture and Decoration Materials"
            for col, metric, unit in columns:
                value = to_number(row.iloc[col] if col < len(row) else None)
                add_record(
                    records,
                    year=year,
                    region="云南省",
                    region_en="Yunnan",
                    region_level="省级",
                    category="家具零售企业经营",
                    category_en="Furniture retail enterprise operation",
                    subject=subject,
                    metric=metric,
                    unit=unit,
                    value=value,
                    source_yearbook=source_yearbook,
                    table_name=table_name,
                    source_path=path,
                    scope_note=f"限额以上批发和零售业法人企业行业明细；英文分类：{subject_en}",
                )


def extract_finance(records: list[dict]) -> None:
    columns_by_year = {
        "default": [
            (2, "法人企业数", "个"),
            (3, "资产总计", "亿元"),
            (4, "流动资产合计", "亿元"),
            (5, "负债合计", "亿元"),
            (6, "所有者权益合计", "亿元"),
            (7, "营业收入", "亿元"),
            (8, "营业成本", "亿元"),
            (9, "税金及附加", "亿元"),
            (10, "营业利润", "亿元"),
        ],
        2019: [
            (2, "法人企业数", "个"),
            (3, "资产总计", "亿元"),
            (4, "流动资产合计", "亿元"),
            (5, "固定资产合计", "亿元"),
            (6, "负债合计", "亿元"),
            (7, "所有者权益合计", "亿元"),
            (8, "主营业务收入", "亿元"),
            (9, "主营业务成本", "亿元"),
            (10, "主营业务税金及附加", "亿元"),
            (11, "主营业务利润", "亿元"),
        ],
    }
    targets = ["五金、家具及室内装饰材料专门零售", "家具零售"]

    for source_yearbook, (rel_path, sheet) in FINANCE_FILES.items():
        path = source_file(rel_path)
        if source_yearbook == 2025:
            sheet = find_sheet_by_keyword(path, "4-5-1")
        df = read_excel(path, sheet)
        year = source_yearbook - 1
        columns = columns_by_year.get(source_yearbook, columns_by_year["default"])
        table_name = "限额以上批发和零售业法人企业财务状况"

        for _, row in df.iterrows():
            label = clean_text(row.iloc[0] if len(row) > 0 else "")
            label_normalized = label.replace(" ", "").replace("#", "")
            if not any(t.replace(" ", "") == label_normalized for t in targets):
                continue
            subject = "家具零售" if "家具零售" in label_normalized else "五金、家具及室内装饰材料专门零售"
            subject_en = "Furniture Merchandise" if subject == "家具零售" else "Special Retail of Hardware, Furniture and Decoration Materials"
            for col, metric, unit in columns:
                value = to_number(row.iloc[col] if col < len(row) else None)
                add_record(
                    records,
                    year=year,
                    region="云南省",
                    region_en="Yunnan",
                    region_level="省级",
                    category="家具零售企业财务",
                    category_en="Furniture retail enterprise finance",
                    subject=subject,
                    metric=metric,
                    unit=unit,
                    value=value,
                    source_yearbook=source_yearbook,
                    table_name=table_name,
                    source_path=path,
                    scope_note=f"限额以上批发和零售业法人企业财务状况行业明细；英文分类：{subject_en}",
                )


def extract_region_retail_block(records: list[dict], *, source_yearbook: int, path: Path, sheet: str | int | None, region_level_hint: str) -> None:
    df = read_excel(path, sheet)
    table_name = "各州市县社会消费品零售总额"

    # Most region sheets place two independent blocks side by side. Merged cells
    # make the English column sometimes appear at +1 and sometimes at +4, so the
    # block must be detected from the row that contains "Region" and the year
    # columns, not from fixed offsets.
    blocks: list[tuple[int, int, list[tuple[int, int]], int]] = []
    for row_idx in range(min(10, len(df))):
        row = df.iloc[row_idx]
        for en_col, cell in enumerate(row):
            if clean_text(cell) != "Region":
                continue
            start_col = None
            for col in range(en_col - 1, max(-1, en_col - 6), -1):
                text = clean_text(row.iloc[col])
                if text and any(mark in text for mark in ("州", "市", "县")):
                    start_col = col
                    break
            if start_col is None:
                continue
            year_cols: list[tuple[int, int]] = []
            for col in range(en_col + 1, min(df.shape[1], en_col + 7)):
                year = to_number(row.iloc[col])
                if year and 1900 <= int(year) <= 2100:
                    year_cols.append((col, int(year)))
                if len(year_cols) == 2:
                    break
            if len(year_cols) == 2:
                blocks.append((start_col, en_col, year_cols, row_idx))

    if not blocks:
        years = extract_years_from_frame(df)
        if len(years) < 2:
            return
        fallback_year_cols = [(2, years[-2]), (3, years[-1])]
        blocks = [(0, 1, fallback_year_cols, 4)]

    seen = set()
    seen = set()
    for start, en_col, year_cols, header_row in blocks:
        for _, row in df.iloc[header_row + 1 :].iterrows():
            region = clean_text(row.iloc[start] if start < len(row) else "")
            region_en = clean_text(row.iloc[en_col] if en_col < len(row) else "")
            if not region or region in {"州 市 县", "州市县", "州 市", "州市", "Region"}:
                continue
            if not region_en or region_en == "Region":
                continue
            values = [to_number(row.iloc[col] if col < len(row) else None) for col, _ in year_cols]
            if not any(v is not None for v in values):
                continue
            region_level = region_level_hint
            if region in {"全省", "全 省", "全    省", "全     省"} or region_en == "Yunnan":
                region_level = "省级"
            elif region.endswith(("市", "州")) and len(region.replace(" ", "")) <= 5:
                region_level = "州市级"
            elif region_level_hint != "州市级":
                region_level = "县区级"
            for (col, year), value in zip(year_cols, values):
                key = (source_yearbook, region, year, start, en_col, col, value)
                if key in seen:
                    continue
                seen.add(key)
                add_record(
                    records,
                    year=year,
                    region=region.replace(" ", ""),
                    region_en=region_en,
                    region_level=region_level,
                    category="区域消费市场规模",
                    category_en="Regional consumer market scale",
                    subject="社会消费品零售总额",
                    metric="社会消费品零售总额",
                    unit="亿元",
                    value=value,
                    source_yearbook=source_yearbook,
                    table_name=table_name,
                    source_path=path,
                    scope_note="区域消费市场规模，用于云南木制家具市场分析的地区消费背景，不等同于家具单品销售额",
                )


def extract_region_retail(records: list[dict]) -> None:
    for source_yearbook, (rel_path, sheet) in REGION_RETAIL_FILES.items():
        path = source_file(rel_path)
        extract_region_retail_block(
            records,
            source_yearbook=source_yearbook,
            path=path,
            sheet=sheet,
            region_level_hint="县区级",
        )
    for source_yearbook, (rel_path, sheet) in REGION_RETAIL_CONTINUED_FILES.items():
        path = source_file(rel_path)
        extract_region_retail_block(
            records,
            source_yearbook=source_yearbook,
            path=path,
            sheet=sheet,
            region_level_hint="县区级",
        )


def extract_prefecture_retail(records: list[dict]) -> None:
    for source_yearbook, (rel_path, sheet) in PREFECTURE_RETAIL_FILES.items():
        path = source_file(rel_path)
        extract_region_retail_block(
            records,
            source_yearbook=source_yearbook,
            path=path,
            sheet=sheet,
            region_level_hint="州市级",
        )


def mark_latest_observations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    latest_key = [
        "地区",
        "地区层级",
        "年份",
        "数据大类",
        "统计对象",
        "统计指标",
        "单位",
    ]
    latest_yearbook = df.groupby(latest_key, dropna=False)["年鉴年份"].transform("max")
    df = df.copy()
    df["是否最新口径"] = (df["年鉴年份"] == latest_yearbook).map({True: "是", False: "否"})
    return df


def deduplicate(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    # Prefer the latest yearbook when the same statistical year was revised in a later yearbook.
    df = df.sort_values(["年鉴年份", "来源文件"], ascending=[False, True])
    subset = [
        "地区",
        "地区层级",
        "年份",
        "数据大类",
        "统计对象",
        "统计指标",
        "单位",
    ]
    df = df.drop_duplicates(subset=subset, keep="first")
    df["是否最新口径"] = "是"
    df = df.sort_values(["数据大类", "统计对象", "地区层级", "地区", "年份", "统计指标"]).reset_index(drop=True)
    return df


def write_source_note(raw_df: pd.DataFrame, clean_df: pd.DataFrame) -> None:
    years = f"{int(raw_df['年份'].min())}-{int(raw_df['年份'].max())}" if not raw_df.empty else ""
    source_yearbooks = ", ".join(str(y) for y in sorted(raw_df["年鉴年份"].dropna().unique())) if not raw_df.empty else ""
    category_counts = raw_df["数据大类"].value_counts().to_dict() if not raw_df.empty else {}

    lines = [
        "# 云南木制家具市场销售数据来源说明",
        "",
        "## 数据性质",
        "",
        "本数据集来自云南省统计局公开发布的《云南统计年鉴》Excel 原表，属于真实官方统计数据，不是随机生成数据，也不是电商店铺订单明细。",
        "",
        "## 数据口径",
        "",
        "- 核心销售口径：云南省限额以上批发和零售业中的“家具类”“木材及制品类”商品销售额、批发额、零售额。",
        "- 家具零售企业口径：云南省限额以上批发和零售业法人企业中“家具零售”“五金、家具及室内装饰材料专门零售”的购进、销售、库存、营业收入、营业成本、利润等指标。",
        "- 区域背景口径：云南省各州市县社会消费品零售总额，用于分析地区消费市场规模，不等同于家具单品销售额。",
        "",
        "## 覆盖范围",
        "",
        f"- 统计年份：{years}",
        f"- 使用年鉴：{source_yearbooks}",
        f"- 原始汇总版记录数：{len(raw_df)}",
        f"- 清洗版记录数：{len(clean_df)}",
        "",
        "## 分类记录数",
        "",
    ]
    for key, value in category_counts.items():
        lines.append(f"- {key}：{value} 条")

    lines.extend(
        [
            "",
            "## 官方来源",
            "",
            "- 云南省统计局统计年鉴栏目：https://stats.yn.gov.cn/list22.aspx",
            "- 2025 云南统计年鉴：https://stats.yn.gov.cn/Pages_22_7674.aspx",
            "- 2024 云南统计年鉴：https://stats.yn.gov.cn/Pages_22_6933.aspx",
            "- 2023 云南统计年鉴：https://stats.yn.gov.cn/Pages_22_3785.aspx",
            "- 2022 云南统计年鉴：https://stats.yn.gov.cn/Pages_22_2309.aspx",
            "",
            "## 使用建议",
            "",
            "在系统中做清洗和可视化时，建议先按“数据大类”筛选：如果要看木制家具销售趋势，优先使用“木制家具及木材销售”和“家具零售企业经营”；如果要做地区对比，可以使用“区域消费市场规模”。",
        ]
    )
    OUT_SOURCE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    records: list[dict] = []
    extract_commodity_sales(records)
    extract_enterprise_purchase_sales(records)
    extract_finance(records)
    extract_region_retail(records)
    extract_prefecture_retail(records)

    raw_df = pd.DataFrame(records)
    raw_df = raw_df.sort_values(["数据大类", "统计对象", "地区层级", "地区", "年份", "年鉴年份", "统计指标"]).reset_index(drop=True)
    raw_df = mark_latest_observations(raw_df)
    clean_df = deduplicate(records)

    raw_df.to_csv(OUT_RAW_CSV, index=False, encoding="utf-8-sig")
    raw_df.to_excel(OUT_RAW_XLSX, index=False)
    clean_df.to_csv(OUT_CLEAN_CSV, index=False, encoding="utf-8-sig")
    clean_df.to_excel(OUT_CLEAN_XLSX, index=False)
    # Keep the simple "官方统计版" name as the raw, cleaning-friendly data set.
    raw_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    raw_df.to_excel(OUT_XLSX, index=False)
    write_source_note(raw_df, clean_df)

    print(f"raw_records={len(raw_df)}")
    print(f"clean_records={len(clean_df)}")
    print(f"years={int(raw_df['年份'].min())}-{int(raw_df['年份'].max())}")
    print(raw_df["数据大类"].value_counts())
    print(OUT_CSV)
    print(OUT_XLSX)
    print(OUT_RAW_CSV)
    print(OUT_CLEAN_CSV)
    print(OUT_SOURCE)


if __name__ == "__main__":
    main()

"""
宏观经济数据接口
数据来源: akshare (国家统计局、中国人民银行等权威机构)
覆盖: GDP、CPI、PPI、PMI、经济日历
"""
import logging
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from fastapi import APIRouter
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/macro", tags=["macro"])

# ── 简单内存缓存 ─────────────────────────────────────────────────
_cache = {}
_cache_ttl = {}
CACHE_DURATION = 300  # 5分钟缓存

def get_cached(key):
    """获取缓存数据"""
    if key in _cache and key in _cache_ttl:
        if datetime.now() < _cache_ttl[key]:
            logger.info(f"[Cache HIT] {key}")
            return _cache[key]
    logger.info(f"[Cache MISS] {key}")
    return None

def set_cached(key, value):
    """设置缓存数据"""
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)
    logger.info(f"[Cache SET] {key}, expires at {_cache_ttl[key]}")

# ── 响应标准化工具 ─────────────────────────────────────────────────
def success_response(data, message="success"):
    return {
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }

def error_response(message, code=500):
    return {
        "code": code,
        "message": message,
        "data": None,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }

# ── GDP数据 ────────────────────────────────────────────────────────
@router.get("/gdp")
async def get_gdp_data(limit: int = 20):
    """
    获取中国GDP数据
    
    - **limit**: 返回最近N个季度（默认20，即5年）
    """
    try:
        df = ak.macro_china_gdp()
        # 取最近N条（数据按时间降序排列，最新在最前）
        df = df.head(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "quarter": row["季度"],
                "gdp_absolute": float(row["国内生产总值-绝对值"]) if pd.notna(row["国内生产总值-绝对值"]) else None,
                "gdp_yoy": float(row["国内生产总值-同比增长"]) if pd.notna(row["国内生产总值-同比增长"]) else None,
                "primary_yoy": float(row["第一产业-同比增长"]) if pd.notna(row["第一产业-同比增长"]) else None,
                "secondary_yoy": float(row["第二产业-同比增长"]) if pd.notna(row["第二产业-同比增长"]) else None,
                "tertiary_yoy": float(row["第三产业-同比增长"]) if pd.notna(row["第三产业-同比增长"]) else None,
            })
        
        return success_response({
            "indicator": "GDP",
            "name": "国内生产总值",
            "unit": "亿元",
            "frequency": "季度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] GDP fetch error: {e}")
        return error_response(f"GDP数据获取失败: {str(e)}")

# ── CPI数据 ────────────────────────────────────────────────────────
@router.get("/cpi")
async def get_cpi_data(limit: int = 24):
    """
    获取中国CPI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    try:
        df = ak.macro_china_cpi()
        df = df.head(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["月份"],
                "nation_current": float(row["全国-当月"]) if pd.notna(row["全国-当月"]) else None,
                "nation_yoy": float(row["全国-同比增长"]) if pd.notna(row["全国-同比增长"]) else None,
                "nation_mom": float(row["全国-环比增长"]) if pd.notna(row["全国-环比增长"]) else None,
                "city_yoy": float(row["城市-同比增长"]) if pd.notna(row["城市-同比增长"]) else None,
                "rural_yoy": float(row["农村-同比增长"]) if pd.notna(row["农村-同比增长"]) else None,
            })
        
        return success_response({
            "indicator": "CPI",
            "name": "居民消费价格指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] CPI fetch error: {e}")
        return error_response(f"CPI数据获取失败: {str(e)}")

# ── PPI数据 ────────────────────────────────────────────────────────
@router.get("/ppi")
async def get_ppi_data(limit: int = 24):
    """
    获取中国PPI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    try:
        df = ak.macro_china_ppi()
        df = df.head(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["月份"],
                "current": float(row["当月"]) if pd.notna(row["当月"]) else None,
                "yoy": float(row["当月同比增长"]) if pd.notna(row["当月同比增长"]) else None,
                "cumulative": float(row["累计"]) if pd.notna(row["累计"]) else None,
            })
        
        return success_response({
            "indicator": "PPI",
            "name": "工业生产者出厂价格指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] PPI fetch error: {e}")
        return error_response(f"PPI数据获取失败: {str(e)}")

# ── PMI数据 ────────────────────────────────────────────────────────
@router.get("/pmi")
async def get_pmi_data(limit: int = 24):
    """
    获取中国PMI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    try:
        df = ak.macro_china_pmi()
        df = df.head(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["月份"],
                "manufacturing_index": float(row["制造业-指数"]) if pd.notna(row["制造业-指数"]) else None,
                "manufacturing_yoy": float(row["制造业-同比增长"]) if pd.notna(row["制造业-同比增长"]) else None,
                "non_manufacturing_index": float(row["非制造业-指数"]) if pd.notna(row["非制造业-指数"]) else None,
                "non_manufacturing_yoy": float(row["非制造业-同比增长"]) if pd.notna(row["非制造业-同比增长"]) else None,
            })
        
        return success_response({
            "indicator": "PMI",
            "name": "采购经理指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] PMI fetch error: {e}")
        return error_response(f"PMI数据获取失败: {str(e)}")

# ── 综合宏观经济指标 ────────────────────────────────────────────────
@router.get("/overview")
async def get_macro_overview():
    """
    获取宏观经济综合概览（最新一期各指标）
    """
    # 检查缓存
    cached = get_cached("macro_overview")
    if cached:
        return cached
    
    try:
        # GDP（最新季度）- akshare数据按时间降序排列，最新在第一行
        gdp_df = ak.macro_china_gdp()
        gdp_latest = gdp_df.iloc[0] if len(gdp_df) > 0 else None
        
        # CPI（最新月份）
        cpi_df = ak.macro_china_cpi()
        cpi_latest = cpi_df.iloc[0] if len(cpi_df) > 0 else None
        
        # PPI（最新月份）
        ppi_df = ak.macro_china_ppi()
        ppi_latest = ppi_df.iloc[0] if len(ppi_df) > 0 else None
        
        # PMI（最新月份）
        pmi_df = ak.macro_china_pmi()
        pmi_latest = pmi_df.iloc[0] if len(pmi_df) > 0 else None
        
        # M2货币供应量（最新月份）- 降序排列，最新在前
        m2_df = ak.macro_china_supply_of_money()
        m2_latest = m2_df.iloc[0] if len(m2_df) > 0 else None
        
        # 社会融资规模（最新月份）- 升序排列，最新在后
        sf_df = ak.macro_china_shrzgm()
        sf_latest = sf_df.iloc[-1] if len(sf_df) > 0 else None
        
        # 工业增加值（最新月份）- 升序排列，最新在后
        ind_df = ak.macro_china_industrial_production_yoy()
        # 过滤掉今值为NaN的数据
        ind_df_valid = ind_df[pd.notna(ind_df['今值'])] if len(ind_df) > 0 else None
        ind_latest = ind_df_valid.iloc[-1] if ind_df_valid is not None and len(ind_df_valid) > 0 else None
        
        # 失业率（最新月份）- 升序排列，最新在后
        unemp_df = ak.macro_china_urban_unemployment()
        # 筛选全国城镇调查失业率（注意：item字段有尾随空格）
        unemp_df_filtered = unemp_df[unemp_df['item'].str.strip() == '全国城镇调查失业率'] if len(unemp_df) > 0 else None
        unemp_latest = unemp_df_filtered.iloc[-1] if unemp_df_filtered is not None and len(unemp_df_filtered) > 0 else None
        
        overview = {
            "gdp": {
                "period": gdp_latest["季度"] if gdp_latest is not None else None,
                "value": float(gdp_latest["国内生产总值-绝对值"]) if gdp_latest is not None and pd.notna(gdp_latest["国内生产总值-绝对值"]) else None,
                "yoy": float(gdp_latest["国内生产总值-同比增长"]) if gdp_latest is not None and pd.notna(gdp_latest["国内生产总值-同比增长"]) else None,
                "unit": "亿元"
            },
            "cpi": {
                "period": cpi_latest["月份"] if cpi_latest is not None else None,
                "value": float(cpi_latest["全国-当月"]) if cpi_latest is not None and pd.notna(cpi_latest["全国-当月"]) else None,
                "yoy": float(cpi_latest["全国-同比增长"]) if cpi_latest is not None and pd.notna(cpi_latest["全国-同比增长"]) else None,
                "mom": float(cpi_latest["全国-环比增长"]) if cpi_latest is not None and pd.notna(cpi_latest["全国-环比增长"]) else None,
            },
            "ppi": {
                "period": ppi_latest["月份"] if ppi_latest is not None else None,
                "value": float(ppi_latest["当月"]) if ppi_latest is not None and pd.notna(ppi_latest["当月"]) else None,
                "yoy": float(ppi_latest["当月同比增长"]) if ppi_latest is not None and pd.notna(ppi_latest["当月同比增长"]) else None,
            },
            "pmi": {
                "period": pmi_latest["月份"] if pmi_latest is not None else None,
                "manufacturing": float(pmi_latest["制造业-指数"]) if pmi_latest is not None and pd.notna(pmi_latest["制造业-指数"]) else None,
                "non_manufacturing": float(pmi_latest["非制造业-指数"]) if pmi_latest is not None and pd.notna(pmi_latest["非制造业-指数"]) else None,
            },
            "m2": {
                "period": m2_latest["统计时间"] if m2_latest is not None else None,
                "value": float(m2_latest["货币和准货币（广义货币M2）"]) if m2_latest is not None and pd.notna(m2_latest["货币和准货币（广义货币M2）"]) else None,
                "yoy": float(m2_latest["货币和准货币（广义货币M2）同比增长"]) if m2_latest is not None and pd.notna(m2_latest["货币和准货币（广义货币M2）同比增长"]) else None,
                "unit": "亿元"
            },
            "social_financing": {
                "period": sf_latest["月份"] if sf_latest is not None else None,
                "total": float(sf_latest["社会融资规模增量"]) if sf_latest is not None and pd.notna(sf_latest["社会融资规模增量"]) else None,
                "yoy": None,  # akshare数据中没有同比增长
                "unit": "亿元"
            },
            "industrial_production": {
                "period": ind_latest["日期"].strftime('%Y年%m月份') if ind_latest is not None and pd.notna(ind_latest["日期"]) else None,
                "yoy": float(ind_latest["今值"]) if ind_latest is not None and pd.notna(ind_latest["今值"]) else None,
                "unit": "%"
            },
            "unemployment": {
                "period": unemp_latest["date"] if unemp_latest is not None else None,
                "rate": float(unemp_latest["value"]) if unemp_latest is not None and pd.notna(unemp_latest["value"]) else None,
                "unit": "%"
            }
        }
        
        result = success_response({
            "overview": overview,
            "last_update": datetime.now().isoformat()
        })
        
        # 缓存结果
        set_cached("macro_overview", result)
        return result
    except Exception as e:
        logger.error(f"[Macro] Overview fetch error: {e}")
        return error_response(f"宏观概览获取失败: {str(e)}")

# ── 经济日历 ────────────────────────────────────────────────────────
@router.get("/calendar")
async def get_economic_calendar():
    """
    获取中国宏观经济数据发布日历（近期重要数据预告）
    """
    try:
        # 使用akshare的宏观数据获取近期发布日程
        # 注：akshare没有专门的经济日历接口，我们用各指标的最新发布时间推算
        calendar_items = []
        
        # GDP（每季度发布）
        gdp_df = ak.macro_china_gdp()
        if len(gdp_df) > 0:
            latest = gdp_df.iloc[0]
            calendar_items.append({
                "date": latest["季度"],
                "indicator": "GDP",
                "name": "国内生产总值",
                "status": "released",
                "value": float(latest["国内生产总值-同比增长"]) if pd.notna(latest["国内生产总值-同比增长"]) else None,
                "unit": "%"
            })
        
        # CPI（每月发布）
        cpi_df = ak.macro_china_cpi()
        if len(cpi_df) > 0:
            latest = cpi_df.iloc[0]
            calendar_items.append({
                "date": latest["月份"],
                "indicator": "CPI",
                "name": "居民消费价格指数",
                "status": "released",
                "value": float(latest["全国-同比增长"]) if pd.notna(latest["全国-同比增长"]) else None,
                "unit": "%"
            })
        
        # PMI（每月发布）
        pmi_df = ak.macro_china_pmi()
        if len(pmi_df) > 0:
            latest = pmi_df.iloc[0]
            calendar_items.append({
                "date": latest["月份"],
                "indicator": "PMI",
                "name": "采购经理指数",
                "status": "released",
                "value": float(latest["制造业-指数"]) if pd.notna(latest["制造业-指数"]) else None,
                "unit": ""
            })
        
        return success_response({
            "calendar": calendar_items,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] Calendar fetch error: {e}")
        return error_response(f"经济日历获取失败: {str(e)}")

# ── M2货币供应量 ───────────────────────────────────────────────────
@router.get("/m2")
async def get_m2_data(limit: int = 24):
    """
    获取中国M2货币供应量数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_m2_{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        df = ak.macro_china_supply_of_money()
        df = df.head(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["统计时间"],
                "m2_yoy": float(row["货币和准货币（广义货币M2）同比增长"]) if pd.notna(row["货币和准货币（广义货币M2）同比增长"]) else None,
                "m2_amount": float(row["货币和准货币（广义货币M2）"]) if pd.notna(row["货币和准货币（广义货币M2）"]) else None,
            })
        
        result = success_response({
            "indicator": "M2",
            "name": "广义货币供应量",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"[Macro] M2 fetch error: {e}")
        return error_response(f"M2数据获取失败: {str(e)}")

# ── 社会融资规模 ───────────────────────────────────────────────────
@router.get("/social_financing")
async def get_social_financing_data(limit: int = 24):
    """
    获取中国社会融资规模数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_social_financing_{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        df = ak.macro_china_shrzgm()
        # 数据升序排列，取最后N条
        df = df.tail(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["月份"],
                "total": float(row["社会融资规模增量"]) if pd.notna(row["社会融资规模增量"]) else None,
                "rmb_loan": float(row["其中-人民币贷款"]) if pd.notna(row["其中-人民币贷款"]) else None,
            })
        
        result = success_response({
            "indicator": "SocialFinancing",
            "name": "社会融资规模",
            "unit": "亿元",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"[Macro] Social financing fetch error: {e}")
        return error_response(f"社融数据获取失败: {str(e)}")

# ── 工业增加值 ─────────────────────────────────────────────────────
@router.get("/industrial_production")
async def get_industrial_production_data(limit: int = 24):
    """
    获取中国工业增加值数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_industrial_production_{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        df = ak.macro_china_industrial_production_yoy()
        # 过滤掉今值为NaN的数据
        df = df[pd.notna(df['今值'])]
        # 数据升序排列，取最后N条
        df = df.tail(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["日期"].strftime('%Y-%m') if pd.notna(row["日期"]) else None,
                "yoy": float(row["今值"]) if pd.notna(row["今值"]) else None,
                "previous": float(row["前值"]) if pd.notna(row["前值"]) else None,
            })
        
        result = success_response({
            "indicator": "IndustrialProduction",
            "name": "工业增加值",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"[Macro] Industrial production fetch error: {e}")
        return error_response(f"工业增加值数据获取失败: {str(e)}")

# ── 失业率 ─────────────────────────────────────────────────────────
@router.get("/unemployment")
async def get_unemployment_data(limit: int = 24):
    """
    获取中国城镇调查失业率数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_unemployment_{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        df = ak.macro_china_urban_unemployment()
        # 筛选全国城镇调查失业率（注意：item字段有尾随空格）
        df = df[df['item'].str.strip() == '全国城镇调查失业率']
        # 数据升序排列，取最后N条
        df = df.tail(limit) if len(df) > limit else df
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "month": row["date"],
                "rate": float(row["value"]) if pd.notna(row["value"]) else None,
            })
        
        result = success_response({
            "indicator": "Unemployment",
            "name": "城镇调查失业率",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"[Macro] Unemployment fetch error: {e}")
        return error_response(f"失业率数据获取失败: {str(e)}")

# ── 批量获取 ────────────────────────────────────────────────────────
@router.get("/batch")
async def get_macro_batch(
    indicators: str = "gdp,cpi,ppi,pmi",
    limit: int = 12
):
    """
    批量获取宏观经济指标
    
    - **indicators**: 逗号分隔的指标代码（gdp,cpi,ppi,pmi,m2,social_financing,industrial_production,unemployment）
    - **limit**: 每个指标返回最近N期数据
    """
    try:
        indicator_list = [i.strip().lower() for i in indicators.split(",")]
        result = {}
        
        if "gdp" in indicator_list:
            df = ak.macro_china_gdp().tail(limit)
            result["gdp"] = {
                "data": [{"quarter": r["季度"], "yoy": float(r["国内生产总值-同比增长"]) if pd.notna(r["国内生产总值-同比增长"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "季度"
            }
        
        if "cpi" in indicator_list:
            df = ak.macro_china_cpi().tail(limit)
            result["cpi"] = {
                "data": [{"month": r["月份"], "yoy": float(r["全国-同比增长"]) if pd.notna(r["全国-同比增长"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "月度"
            }
        
        if "ppi" in indicator_list:
            df = ak.macro_china_ppi().tail(limit)
            result["ppi"] = {
                "data": [{"month": r["月份"], "yoy": float(r["当月同比增长"]) if pd.notna(r["当月同比增长"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "月度"
            }
        
        if "pmi" in indicator_list:
            df = ak.macro_china_pmi().tail(limit)
            result["pmi"] = {
                "data": [{"month": r["月份"], "index": float(r["制造业-指数"]) if pd.notna(r["制造业-指数"]) else None} for _, r in df.iterrows()],
                "unit": "",
                "frequency": "月度"
            }
        
        if "m2" in indicator_list:
            df = ak.macro_china_m2_yearly().tail(limit)
            result["m2"] = {
                "data": [{"month": r["月份"], "yoy": float(r["M2-同比增长"]) if pd.notna(r["M2-同比增长"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "月度"
            }
        
        if "social_financing" in indicator_list:
            df = ak.macro_china_bank_financing().tail(limit)
            result["social_financing"] = {
                "data": [{"month": r["月份"], "total": float(r["社会融资规模增量"]) if pd.notna(r["社会融资规模增量"]) else None} for _, r in df.iterrows()],
                "unit": "亿元",
                "frequency": "月度"
            }
        
        if "industrial_production" in indicator_list:
            df = ak.macro_china_gyzjz().tail(limit)
            result["industrial_production"] = {
                "data": [{"month": r["月份"], "yoy": float(r["同比增长"]) if pd.notna(r["同比增长"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "月度"
            }
        
        if "unemployment" in indicator_list:
            df = ak.macro_china_urban_unemployment().tail(limit)
            result["unemployment"] = {
                "data": [{"month": r["月份"], "rate": float(r["失业率"]) if pd.notna(r["失业率"]) else None} for _, r in df.iterrows()],
                "unit": "%",
                "frequency": "月度"
            }
        
        return success_response({
            "indicators": result,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] Batch fetch error: {e}")
        return error_response(f"批量获取失败: {str(e)}")

"""
行业板块全局缓存 - Task 1: 路由绝对不允许同步调用 akshare
所有板块数据由后台 Job 填充，API 只读此缓存
"""
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_SECTORS_CACHE: list[dict] = []
_CACHE_READY: bool = False
_LOCK = threading.Lock()

# 静态兜底数据（板块API全挂时使用）
_FALLBACK_SECTORS = [
    {"name": "酿酒行业",    "symbol": "BK0442", "change_pct": 1.23,  "price": 0, "volume": 0,
     "top_stock": {"name": "贵州茅台", "code": "600519"}, "status": "交易中"},
    {"name": "医疗器械",    "symbol": "BK0531", "change_pct": 0.87,  "price": 0, "volume": 0,
     "top_stock": {"name": "迈瑞医疗", "code": "300760"}, "status": "交易中"},
    {"name": "半导体",      "symbol": "BK0361", "change_pct": 0.54,  "price": 0, "volume": 0,
     "top_stock": {"name": "中芯国际", "code": "688981"}, "status": "交易中"},
    {"name": "电池",        "symbol": "BK0988", "change_pct": 0.32,  "price": 0, "volume": 0,
     "top_stock": {"name": "宁德时代", "code": "300750"}, "status": "交易中"},
    {"name": "银行",        "symbol": "BK0401", "change_pct": -0.21, "price": 0, "volume": 0,
     "top_stock": {"name": "招商银行", "code": "600036"}, "status": "交易中"},
    {"name": "证券",        "symbol": "BK0728", "change_pct": -0.45, "price": 0, "volume": 0,
     "top_stock": {"name": "中信证券", "code": "600030"}, "status": "交易中"},
    {"name": "房地产",       "symbol": "BK0451", "change_pct": -0.67, "price": 0, "volume": 0,
     "top_stock": {"name": "万科A",    "code": "000002"}, "status": "交易中"},
    {"name": "煤炭开采",     "symbol": "BK0014", "change_pct": -0.88, "price": 0, "volume": 0,
     "top_stock": {"name": "中国神华", "code": "601088"}, "status": "交易中"},
]


def update_sectors(sectors: list[dict]):
    """后台 Job 调用此函数更新板块缓存"""
    global _SECTORS_CACHE, _CACHE_READY
    with _LOCK:
        _SECTORS_CACHE = sectors
        _CACHE_READY = True
    logger.info(f"[SectorsCache] {len(sectors)} 个板块已缓存")


def get_sectors() -> list[dict]:
    """
    API 路由调用：立即返回缓存（毫秒级，绝不阻塞）
    缓存为空时返回静态兜底数据
    """
    with _LOCK:
        if _SECTORS_CACHE:
            return list(_SECTORS_CACHE)
    return list(_FALLBACK_SECTORS)


def is_ready() -> bool:
    return _CACHE_READY


def fetch_and_cache_sectors():
    """
    后台 Job — 主动抓取真实行业+概念板块并更新缓存
    主用 akshare stock_board_industry_name_em()
    备选 akshare stock_board_concept_name_em()
    绝不在 API 路由线程中调用！
    """
    import akshare as ak

    # 专业关键词加权列表
    WEIGHT_KEYWORDS = ["算力", "人工智能", "AI", "中特估", "半导体设备", "高股息", "芯片", "机器人", "量子", "氢能"]
    WEIGHT_BOOST = 5.0  # 关键词命中的排序权重加成

    rows = []

    # ── 行业板块 ────────────────────────────────────────────────
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                try:
                    name = str(r.get("板块名称", "") or "")
                    rows.append({
                        "name":       name,
                        "symbol":     str(r.get("板块代码", "") or ""),
                        "change_pct": round(float(r.get("涨跌幅", 0) or 0), 2),
                        "price":      float(r.get("总市值", 0) or 0),
                        "volume":     float(r.get("成交额", 0) or 0),
                        "top_stock":  {"name": str(r.get("领涨股票", "") or ""), "code": ""},
                        "status":     "交易中",
                        "_src":       "industry",
                    })
                except (ValueError, TypeError):
                    continue
            logger.info(f"[SectorsCache] 行业板块抓取: {len(rows)} 个")
    except Exception as e:
        logger.warning(f"[SectorsCache] industry 接口失败: {e}")

    # ── 概念板块（融合）────────────────────────────────────────
    try:
        df2 = ak.stock_board_concept_name_em()
        if df2 is not None and not df2.empty:
            seen_names = {r["name"] for r in rows}
            for _, r in df2.iterrows():
                try:
                    name = str(r.get("板块名称", "") or "")
                    # 去重：已存在于行业板的同名板块跳过
                    if name in seen_names:
                        continue
                    rows.append({
                        "name":       name,
                        "symbol":     str(r.get("板块代码", "") or ""),
                        "change_pct": round(float(r.get("涨跌幅", 0) or 0), 2),
                        "price":      float(r.get("总市值", 0) or 0),
                        "volume":     float(r.get("成交额", 0) or 0),
                        "top_stock":  {"name": str(r.get("领涨股票", "") or ""), "code": ""},
                        "status":     "交易中",
                        "_src":       "concept",
                    })
                except (ValueError, TypeError):
                    continue
            logger.info(f"[SectorsCache] 概念板块抓取: {len(rows)} 个（去重后）")
    except Exception as e2:
        logger.warning(f"[SectorsCache] concept 接口失败: {e2}")

    # ── 关键词加权排序 ─────────────────────────────────────────
    def sort_key(x):
        boost = 0.0
        for kw in WEIGHT_KEYWORDS:
            if kw.lower() in x["name"].lower():
                boost += WEIGHT_BOOST
                logger.info(f"[SectorsCache] 关键词命中: {x['name']} (+{WEIGHT_BOOST} 加权)")
        return x["change_pct"] + boost

    if rows:
        rows.sort(key=sort_key, reverse=True)
        update_sectors(rows[:20])  # 扩展到 Top 20（行业+概念融合）
        logger.info(f"[SectorsCache] 综合排序完成，Top 20: {[r['name'] for r in rows[:10]]}")
        return

    # 全挂：使用静态兜底
    update_sectors(_FALLBACK_SECTORS)
    logger.warning("[SectorsCache] 所有接口失败，使用静态兜底数据")

"""
行业板块全局缓存 - Task 1: 路由绝对不允许同步调用 akshare
所有板块数据由后台 Job 填充，API 只读此缓存

数据源：新浪财经行业板块 + 概念板块（vip.stock.finance.sina.com.cn）
稳定性：直连国内 CDN（不走代理），失败重试 3 次
"""
import json
import logging
import re
import threading

import httpx

logger = logging.getLogger(__name__)

_SECTORS_CACHE: list[dict] = []
_CACHE_READY: bool = False
_LOCK = threading.Lock()

# 静态兜底数据（所有 API 全挂时使用）
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

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Connection": "close",
}


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


def _fetch_sina_boards(param: str) -> list[dict]:
    """
    从新浪财经抓取行业/概念板块数据（直连，不走代理）
    param: "industry"（行业板块，约84个）或 "class"（概念板块，约175个）

    Sina JSON 格式示例：
      "hangye_ZA01": "hangye_ZA01,农业,16,10.9825,-0.179375,...,sz300970,8.557,30.700,2.420,华绿生物"
      "gn_hwqc":     "gn_hwqc,华为汽车,97,27.93,-0.136,...,sz002792,9.995,45.340,4.120,通宇通讯"

    字段（逗号分隔，共13个）：
      [0] board_code, [1] board_name, [2] stock_count, [3] avg_price,
      [4] change_pct(%), [5] unknown, [6] volume, [7] amount(元),
      [8] top_stock_code, [9] top_stock_price, [10] top_stock_high, [11] top_stock_low, [12] top_stock_name
    """
    url = "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"
    rows = []

    for attempt in range(3):
        try:
            with httpx.Client(timeout=12.0, http1=True, http2=False,
                              limits=httpx.Limits(max_keepalive_connections=1, max_connections=1)) as client:
                resp = client.get(url, params={"param": param}, headers=SINA_HEADERS)
                text = resp.text

            # 提取 var S_Finance_bankuai_xxx = {...} 中的 JSON 对象
            m = re.search(r"=\s*(\{.*\})\s*$", text, re.DOTALL)
            if not m:
                raise ValueError(f"无法解析 Sina 响应，param={param}")

            data: dict = json.loads(m.group(1))
            if not data:
                raise ValueError("Sina 返回空数据")

            for raw_key, raw_val in data.items():
                try:
                    parts = raw_val.split(",")
                    if len(parts) < 10:
                        continue

                    name = parts[1].strip()
                    change_pct = round(float(parts[4]), 2) if parts[4] not in ("-", "") else 0.0
                    amount = float(parts[7]) if parts[7] not in ("-", "") else 0.0  # 成交额（元）
                    top_code = parts[8].strip()
                    top_name = parts[12].strip() if len(parts) > 12 else ""

                    # 标准化 top_stock.code（去掉 sz/sh 前缀以便前端匹配）
                    norm_code = top_code
                    for p in ("sz", "sh", "bj", "hk", "us", "jp"):
                        if norm_code.lower().startswith(p):
                            norm_code = norm_code[len(p):]
                            break

                    rows.append({
                        "name":       name,
                        "symbol":     raw_key,          # Sina 的原始 board_code，如 "hangye_ZA01"、"gn_hwqc"
                        "change_pct": change_pct,
                        "price":      amount,            # Sina 无总市值，用成交额代替（>0 即有交易）
                        "volume":     float(parts[6]) if parts[6] not in ("-", "") else 0.0,
                        "top_stock":  {"name": top_name, "code": norm_code},
                        "status":     "交易中",
                    })
                except (ValueError, IndexError, TypeError) as exc:
                    logger.debug(f"[SectorsCache] 跳过异常行 {raw_key}: {exc}")
                    continue

            logger.info(f"[SectorsCache] Sina {param} 抓取成功: {len(rows)} 个板块")
            return rows

        except Exception as e:
            logger.warning(f"[SectorsCache] Sina {param} 第{attempt+1}/3次失败: {e}")
            if attempt == 2:
                raise

    return []


def fetch_and_cache_sectors():
    """
    后台 Job — 抓取行业+概念板块，合并去重，关键词加权排序，缓存 Top 20。
    绝不在 API 路由线程中调用！
    """
    WEIGHT_KEYWORDS = ["算力", "人工智能", "AI", "中特估", "半导体设备",
                        "高股息", "芯片", "机器人", "量子", "氢能", "固态电池",
                        "算力", "大模型", "RISC", "光刻", "自主可控"]
    WEIGHT_BOOST = 5.0

    all_rows: list[dict] = []

    # ── 行业板块（约84个）──────────────────────────────────────
    try:
        industry_rows = _fetch_sina_boards("industry")
        for r in industry_rows:
            r["_src"] = "industry"
        all_rows.extend(industry_rows)
    except Exception as e:
        logger.warning(f"[SectorsCache] 行业板块抓取失败: {e}")

    # ── 概念板块（约175个）────────────────────────────────────
    try:
        concept_rows = _fetch_sina_boards("class")
        # 去重：已存在于行业板的同名板块跳过
        seen_names = {r["name"] for r in all_rows}
        for r in concept_rows:
            if r["name"] not in seen_names:
                r["_src"] = "concept"
                all_rows.append(r)
    except Exception as e:
        logger.warning(f"[SectorsCache] 概念板块抓取失败: {e}")

    # ── 关键词加权排序 ─────────────────────────────────────────
    def sort_key(x: dict) -> float:
        boost = 0.0
        name_lower = x["name"].lower()
        for kw in WEIGHT_KEYWORDS:
            if kw.lower() in name_lower:
                boost += WEIGHT_BOOST
                logger.info(f"[SectorsCache] 关键词命中: {x['name']} (+{WEIGHT_BOOST})")
        return x["change_pct"] + boost

    if all_rows:
        all_rows.sort(key=sort_key, reverse=True)
        top20 = all_rows[:20]
        update_sectors(top20)
        top_names = [r["name"] for r in top20]
        logger.info(f"[SectorsCache] 综合排序完成，Top 20: {top_names}")
        return

    # 全挂：使用静态兜底
    update_sectors(_FALLBACK_SECTORS)
    logger.warning("[SectorsCache] 所有接口失败，使用静态兜底数据")

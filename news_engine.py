"""
AlphaTerminal 实时新闻引擎 - Phase 5
全局缓存 + 后台异步刷新（API 只读缓存，<50ms 响应）
"""
import hashlib
import logging
import os
import threading
import time
from datetime import datetime

# ── 确保代理环境变量生效（外网请求必须走代理）────────────────────────
os.environ.setdefault("HTTP_PROXY",  "http://192.168.1.50:7897")
os.environ.setdefault("HTTPS_PROXY", "http://192.168.1.50:7897")
os.environ.setdefault("http_proxy",  "http://192.168.1.50:7897")
os.environ.setdefault("https_proxy", "http://192.168.1.50:7897")

import akshare as ak

logger = logging.getLogger(__name__)

# ── 全局新闻缓存（进程内存，uvicorn 常驻）──────────────────────────────
# 结构: list[dict]，由后台刷新线程维护，API 只读不写
_NEWS_CACHE: list[dict] = []
_NEWS_CACHE_READY: bool = False
_CACHE_LOCK = threading.Lock()

# ── 轮询标的（20 只 A 股核心，覆盖主要行业）─────────────────────────
NEWS_SYMBOLS = [
    "000001", "399001", "399006", "000300",              # 核心指数
    "600036", "601318", "600030", "600016",              # 银行/券商
    "600519", "002594", "300750", "688981",              # 消费/新能源/半导体
    "601628", "000776",                                  # 保险
    "002230", "300059", "688111",                        # 科技
    "600028", "601899", "600050",                        # 周期
    "600887", "603288", "000858",                        # 消费
    "600009", "601888",                                  # 旅游/免税
]

# ── 全局去重哈希集合 ────────────────────────────────────────────────
_SEEN_URL_HASHES: set[str] = set()
_MAX_CACHE_SIZE  = 500


# ─────────────────────────────────────────────────────────────────
def _tag_news(title: str, source: str) -> str:
    t = title + source
    if any(k in t for k in ["突发", "紧急", "暴跌", "大涨", "重磅", "制裁", "黑天鹅"]):
        return "🔴 突发"
    if any(k in t for k in ["央行", "美联储", "降息", "降准", "CPI", "PPI", "GDP", "LPR"]):
        return "💎 宏观"
    if any(k in t for k in ["A股", "沪指", "深指", "创业板", "科创", "涨跌"]):
        return "📈 A股"
    if any(k in t for k in ["港股", "恒生", "南向"]):
        return "🌏 港股"
    if any(k in t for k in ["美股", "纳斯达克", "道琼斯", "标普"]):
        return "🇺🇸 美股"
    if any(k in t for k in ["AI", "ChatGPT", "大模型", "特朗普", "科技"]):
        return "🖥️ AI"
    if any(k in t for k in ["黄金", "原油", "大宗", "能源"]):
        return "🛢️ 商品"
    if any(k in t for k in ["房地产", "楼市", "房价", "限购"]):
        return "🏠 地产"
    return "📰 其他"


def _url_md5(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _fetch_news_for_symbol(symbol: str) -> list[dict]:
    """针对单个标的拉取新闻"""
    try:
        df = ak.stock_news_em(symbol=symbol)
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            try:
                raw_url = str(row.get("新闻链接", "")) or ""
                title   = str(row.get("新闻标题", "")) or ""
                if not title or not raw_url or raw_url == "nan":
                    continue
                rows.append({
                    "title":  title.strip(),
                    "time":   str(row.get("发布时间", ""))[:16],
                    "source": str(row.get("文章来源", "")) or "未知",
                    "url":    raw_url,   # ← 绝对路径，例: http://finance.eastmoney.com/a/202603313690418549.html
                })
            except Exception:
                continue
        return rows
    except Exception as e:
        logger.warning(f"[NewsEngine] stock_news_em({symbol}) 失败: {type(e).__name__}: {e}")
        return []


def _fetch_7x24_news() -> list[dict]:
    """
    东方财富 7×24 实时全球资讯（AkShare 宏观接口，一次性拉取 150+ 条）
    这是兜底数据源，不受个股新闻数量限制
    """
    try:
        df = ak.news_economic_baidu()
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            try:
                raw_url = str(row.get("新闻链接", "")) or ""
                title   = str(row.get("新闻标题", "")) or ""
                time_   = str(row.get("发布时间", ""))[:16]
                source  = str(row.get("来源", "")) or "百度财经"
                if not title or not raw_url or raw_url == "nan":
                    continue
                rows.append({
                    "title":  title.strip(),
                    "time":   time_,
                    "source": source,
                    "url":    raw_url,
                })
            except Exception:
                continue
        logger.info(f"[NewsEngine] 7x24 快讯: {len(rows)} 条")
        return rows
    except Exception as e:
        logger.warning(f"[NewsEngine] 7x24 拉取失败: {type(e).__name__}: {e}")
        return []


def refresh_news_cache(background: bool = True):
    """
    刷新全局新闻缓存池（后台线程调用）
    策略：
      1. 宏观快讯：stock_news_main_cx（财新，100条，走代理，稳定可靠）
      2. 个股新闻：akshare stock_news_em（东方财富，20只）
      所有来源均包含真实发布时间（发布时间 字段），无时间戳造假
    """
    global _NEWS_CACHE, _NEWS_CACHE_READY

    # ── 宏观快讯专用标的（从 stock_news_em 拉，真实时间戳）──────────────
    _MACRO_SYMBOLS = [
        "000001", "399001", "399006", "000300",   # 主要指数
        "600036", "601318", "600000",              # 金融
        "600519", "000858", "600028",              # 消费/能源
        "002230", "300750", "688981",              # 科技
    ]

    def _do_fetch():
        global _NEWS_CACHE, _NEWS_CACHE_READY
        all_news: list[dict] = []
        sources_used = []

        try:
            # ① 宏观快讯：ak.stock_news_em（东方财富，真实发布时间）
            for sym in _MACRO_SYMBOLS:
                try:
                    df = ak.stock_news_em(symbol=sym)
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            try:
                                title  = str(row.get("新闻标题", "") or "")
                                time_  = str(row.get("发布时间", "") or "")[:16]
                                source = str(row.get("文章来源", "东财") or "东财")
                                url    = str(row.get("新闻链接", "") or "")
                                if title and len(title) > 5:
                                    all_news.append({
                                        "title":  title.strip(),
                                        "time":   time_,
                                        "source": source,
                                        "url":    url,
                                    })
                            except Exception:
                                continue
                        sources_used.append(f"em:{sym}")
                except Exception as e:
                    logger.warning(f"[SCHEDULER] stock_news_em({sym}) failed: {type(e).__name__}: {e}")
                time.sleep(0.05)

            logger.info(f"[SCHEDULER] stock_news_em 宏观: fetched {len(all_news)} raw items.")

            # ② 个股新闻（东方财富，20只标的）
            for sym in NEWS_SYMBOLS:
                try:
                    items = _fetch_news_for_symbol(sym)
                    if items:
                        all_news.extend(items)
                except Exception as e:
                    logger.warning(f"[SCHEDULER] {sym} failed: {type(e).__name__}: {e}")
                time.sleep(0.05)  # 快速轮询

        except Exception as e:
            logger.error(f"[SCHEDULER] Overall news fetch failed: {e}", exc_info=True)
            # 即使失败也打印心跳，不让日志沉默
            logger.info(f"[HEARTBEAT] News fetch failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {e}")
            return

        if not all_news:
            logger.warning("[SCHEDULER] All sources returned empty, skipping cache update.")
            return

        # 合并去重（MD5 URL）
        seen = set()
        unique_news = []
        for item in all_news:
            h = _url_md5(item["url"])
            if h not in seen:
                seen.add(h)
                item["tag"] = _tag_news(item["title"], item["source"])
                item["id"]  = h[:12]
                unique_news.append(item)

        # 全量覆盖缓存（去重后最新 200 条）
        unique_news.sort(key=lambda x: x.get("time", ""), reverse=True)
        final = unique_news[:200]

        with _CACHE_LOCK:
            _NEWS_CACHE.clear()
            _NEWS_CACHE.extend(final)
            _NEWS_CACHE_READY = True

        # ── 审计日志：打印最新一条新闻 ────────────────────────────────
        if final:
            latest = final[0]
            print(
                f"[News Fetch] 抓取完成，共 {len(final)} 条。"
                f"最新新闻时间：{latest['time']}，标题：{latest['title'][:40]}",
                flush=True
            )
        else:
            print("[News Fetch] 抓取完成，缓存为空。", flush=True)

        logger.info(
            f"[SCHEDULER] Successfully pushed {len(final)} items to cache. "
            f"(sources: {sources_used}, total_raw={len(all_news)}, total_unique={len(unique_news)})"
        )
        logger.info(
            f"[HEARTBEAT] News refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, "
            f"total={len(final)} items (sources: {sources_used})"
        )

    if background:
        t = threading.Thread(target=_do_fetch, daemon=True, name="news-cache-refresh")
        t.start()
        logger.info("[NewsEngine] 后台刷新线程已启动")
    else:
        _do_fetch()


# ── 外部调用：返回缓存数据（<50ms）─────────────────────────────────
def get_cached_news(limit: int = 150) -> list[dict]:
    """API 调用专用：直接读缓存，毫秒级返回"""
    with _CACHE_LOCK:
        return list(_NEWS_CACHE[:limit])


def is_cache_ready() -> bool:
    return _NEWS_CACHE_READY


def get_mock_news() -> list[dict]:
    """本地兜底快讯（50条，覆盖宏观/A股/港股/美股/商品/AI/能源）"""
    import random
    now = datetime.now()
    hour = now.hour

    base_news = [
        {"id": "m001", "tag": "🔴 突发", "title": "央行宣布定向降准 0.25 个百分点，释放长期资金约 5000 亿元", "source": "央行官网"},
        {"id": "m002", "tag": "📈 A股",  "title": "上证指数重返 3900 点，券商板块掀起涨停潮", "source": "东方财富"},
        {"id": "m003", "tag": "🌏 港股", "title": "恒生科技指数大涨 3.8%，南向资金净买入超 100 亿港元", "source": "经济通"},
        {"id": "m004", "tag": "💎 宏观", "title": "美国 2 月 CPI 超预期回落，市场押注美联储 6 月降息概率突破 70%", "source": "Bloomberg"},
        {"id": "m005", "tag": "🖥️ AI",  "title": "OpenAI 发布 GPT-5 Turbo，上下文窗口扩展至 100 万 token", "source": "The Verge"},
        {"id": "m006", "tag": "📈 A股",  "title": "创业板指涨超 2%，新能源赛道集体反弹，宁德时代涨逾 4%", "source": "东方财富"},
        {"id": "m007", "tag": "🛢️ 大宗", "title": "WTI 原油跌破 70 美元/桶，供应过剩预期施压油价", "source": "路透社"},
        {"id": "m008", "tag": "💎 黄金", "title": "国际金价突破 3300 美元/盎司，再创历史新高", "source": "COMEX"},
        {"id": "m009", "tag": "📈 美股", "title": "纳斯达克指数再创历史新高，科技七巨头总市值突破 15 万亿美元", "source": "WSJ"},
        {"id": "m010", "tag": "💻 AI",  "title": "英伟达发布新一代 AI 芯片 B300，推理性能提升 3.5 倍", "source": "AnandTech"},
        {"id": "m011", "tag": "🏦 金融", "title": "中国平安业绩超预期：新业务价值同比增长 18%，股价大涨 5%", "source": "证券时报"},
        {"id": "m012", "tag": "🛢️ 能源", "title": "欧佩克+维持减产协议至 Q2，WTI 原油短线拉升突破 75 美元", "source": "路透社"},
        {"id": "m013", "tag": "📈 A股",  "title": "半导体板块全线爆发，中芯国际涨停封板，机构资金净流入 20 亿", "source": "东方财富"},
        {"id": "m014", "tag": "🌐 宏观", "title": "中国 2 月 PMI 重返扩张区间，制造业PMI录得 50.2", "source": "国家统计局"},
        {"id": "m015", "tag": "💎 宏观", "title": "欧洲央行宣布维持利率不变，拉加德重申通胀回落目标", "source": "欧央行"},
        {"id": "m016", "tag": "📊 A股",  "title": "沪深两市成交额突破 1.5 万亿元，券商板块净流入居首", "source": "Wind"},
        {"id": "m017", "tag": "🖥️ AI",  "title": "微软 Copilot 接入 ChatGPT-5，企业用户突破 1000 万", "source": "Microsoft"},
        {"id": "m018", "tag": "🏥 医药", "title": "创新药板块迎政策利好，CXO 概念股集体涨停", "source": "医药魔方"},
        {"id": "m019", "tag": "📈 港股", "title": "腾讯控股涨超 4%，游戏业务复苏获机构上调目标价", "source": "港交所"},
        {"id": "m020", "tag": "🚗 新能源", "title": "比亚迪 2 月销量突破 20 万辆，蝉联全球新能源销量冠军", "source": "比亚迪官方"},
        {"id": "m021", "tag": "📈 A股",  "title": "银行板块估值修复行情启动，国有大行股价创年内新高", "source": "Wind"},
        {"id": "m022", "tag": "🌏 亚太", "title": "日经225指数突破 40000 点，创 34 年来新高", "source": "日经中文网"},
        {"id": "m023", "tag": "💎 商品", "title": "LME 铜价突破 9000 美元/吨，铜金比创历史新高", "source": "LME"},
        {"id": "m024", "tag": "📈 美股", "title": "特斯拉 Robotaxi 获监管批准，2026 年将在加州商业化运营", "source": "Reuters"},
        {"id": "m025", "tag": "🏦 宏观", "title": "人民币汇率升破 7.20 关口，外资连续 3 个月净买入 A 股", "source": "外汇交易中心"},
        {"id": "m026", "tag": "🛢️ 原油", "title": "EIA 上调 2026 年全球原油需求增速预期，WTI 原油应声上涨", "source": "EIA"},
        {"id": "m027", "tag": "📈 A股",  "title": "中字头板块持续走强，中国中车、中国建筑创阶段新高", "source": "东方财富"},
        {"id": "m028", "tag": "🖥️ AI",  "title": "谷歌 DeepMind 发布 AlphaCode 4，编程能力超越 99% 人类开发者", "source": "DeepMind"},
        {"id": "m029", "tag": "💡 能源", "title": "光伏组件价格企稳回升，阳光电源、隆基绿能联袂涨停", "source": "Solarzoom"},
        {"id": "m030", "tag": "📈 美股", "title": "苹果 Vision Pro 2 开始预售，产业链供应商集体拉升", "source": "MacRumors"},
        {"id": "m031", "tag": "🏠 地产", "title": "一线城市二手房成交回暖，北京、上海单周成交环比增 30%", "source": "贝壳研究院"},
        {"id": "m032", "tag": "🌏 港股", "title": "阿里巴巴宣布史上最大规模回购 300 亿美元，股价大涨 8%", "source": "港交所"},
        {"id": "m033", "tag": "📊 宏观", "title": "央行副行长：2026 年货币政策保持稳健，支持科技创新是重点", "source": "央行官网"},
        {"id": "m034", "tag": "🛢️ 化工", "title": "化工品价格指数触底反弹，万华化学上调 MDI 出厂价", "source": "卓创资讯"},
        {"id": "m035", "tag": "📈 A股",  "title": "教育板块受政策提振，中公教育、学大教育联袂涨停", "source": "东方财富"},
        {"id": "m036", "tag": "💎 商品", "title": "白银价格创 12 年新高，银价单周涨幅达 15%", "source": "COMEX"},
        {"id": "m037", "tag": "🖥️ AI",  "title": "Meta 发布 Llama 4 开源大模型，性能全面对标 GPT-5", "source": "Meta AI"},
        {"id": "m038", "tag": "📈 期货", "title": "螺纹钢期货主力合约涨停，基建需求预期提振钢价", "source": "上期所"},
        {"id": "m039", "tag": "🏦 金融", "title": "沪深 300ETF 规模突破 2000 亿元，机构配置需求旺盛", "source": "上交所"},
        {"id": "m040", "tag": "🌏 亚太", "title": "韩国综合指数突破 2700 点，半导体板块贡献逾 40% 涨幅", "source": "韩交所"},
        {"id": "m041", "tag": "📈 A股",  "title": "白酒板块止跌反弹，贵州茅台重返 1700 元整数关口", "source": "Wind"},
        {"id": "m042", "tag": "🛢️ 能源", "title": "天然气期货暴跌 20%，欧洲暖冬导致库存超预期", "source": "ICE"},
        {"id": "m043", "tag": "📈 美股", "title": "英伟达纳入道琼斯指数，权重 4.5%，股价创历史新高", "source": "WSJ"},
        {"id": "m044", "tag": "💡 科技", "title": "华为鸿蒙 NEXT 正式商用，生态设备突破 10 亿台", "source": "华为官网"},
        {"id": "m045", "tag": "📈 A股",  "title": "军工板块持续活跃，歼-20 订单催化，中航沈飞涨停", "source": "东方财富"},
        {"id": "m046", "tag": "🌐 宏观", "title": "G20 峰会联合声明：反对贸易保护主义，维护多边贸易体系", "source": "新华社"},
        {"id": "m047", "tag": "🏥 医药", "title": "创新药出海提速：恒瑞医药 License-out 总金额超 50 亿美元", "source": "医药魔方"},
        {"id": "m048", "tag": "📈 A股",  "title": "锂电池板块午后爆发，宁德时代、比亚迪市值重回万亿之上", "source": "Wind"},
        {"id": "m049", "tag": "💎 外汇", "title": "VIX 恐慌指数跌破 15，创 2024 年以来新低", "source": "CBOE"},
        {"id": "m050", "tag": "📈 港股", "title": "美团外卖单量创历史新高，股价连续 5 个交易日上涨", "source": "港交所"},
    ]

    # 时间打散（模拟不同时刻发布的快讯）
    for i, item in enumerate(base_news):
        item["time"] = f"{hour:02d}:{((i * 7) % 60):02d}"
        item["url"] = "#"
    return base_news

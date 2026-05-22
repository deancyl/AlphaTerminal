"""
Symbol-related endpoints extracted from market.py
"""
import logging
import threading
from datetime import datetime
from fastapi import APIRouter, Request, Query

from app.utils.errors import success_response, error_response, ErrorCode
from app.utils.error_decorator import handle_errors
from app.routers.market.dependencies import _normalize_symbol

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Phase 10: 符号注册表（供前端搜索索引）───────────────────────────────
# 规范化 Symbol 前缀规则：sh=上证 sz=深证 us=美股 hk=港股 JP=日股
_MARKET_PREFIX = {
    '000001': 'sh', '000300': 'sh', '000688': 'sh',  # 上证体系
    '399001': 'sz', '399006': 'sz',                   # 深证体系
}
_SYMBOL_REGISTRY = [
    # A股指数
    { 'symbol': 'sh000001', 'code': '000001', 'name': '上证指数',   'pinyin': 'SCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000300', 'code': '000300', 'name': '沪深300',   'pinyin': 'HS300',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399001', 'code': '399001', 'name': '深证成指',   'pinyin': 'SZCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399006', 'code': '399006', 'name': '创业板指',   'pinyin': 'CYBZZ',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000688', 'code': '000688', 'name': '科创50',     'pinyin': 'KC50',   'market': 'AShare', 'type': 'index' },
    # 全球指数
    { 'symbol': 'usNDX',    'code': 'NDX',    'name': '纳斯达克100', 'pinyin': 'NDX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usSPX',    'code': 'SPX',    'name': '标普500',     'pinyin': 'SPX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usDJI',    'code': 'DJI',    'name': '道琼斯',      'pinyin': 'DJS',   'market': 'US',     'type': 'index' },
    { 'symbol': 'hkHSI',    'code': 'HSI',    'name': '恒生指数',    'pinyin': 'HSZS',  'market': 'HK',     'type': 'index' },
    { 'symbol': 'jpN225',   'code': 'N225',   'name': '日经225',     'pinyin': 'RJB',   'market': 'JP',     'type': 'index' },
    # A股个股（示例，实际可扩展到全市场）
    { 'symbol': 'sh600519', 'code': '600519', 'name': '贵州茅台',    'pinyin': 'GZMJ',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh601318', 'code': '601318', 'name': '中国平安',    'pinyin': 'ZGPA',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz000858', 'code': '000858', 'name': '五粮液',      'pinyin': 'WLY',   'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh600036', 'code': '600036', 'name': '招商银行',    'pinyin': 'ZSYH',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz002594', 'code': '002594', 'name': '比亚迪',      'pinyin': 'BYD',   'market': 'AShare', 'type': 'stock' },
    # 宏观
    { 'symbol': 'GOLD',     'code': 'GOLD',   'name': '黄金(USD)',   'pinyin': 'JH',    'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'WTI',      'code': 'WTI',    'name': 'WTI原油',     'pinyin': 'YSCY',  'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'CNHUSD',   'code': 'CNHUSD', 'name': '美元/人民币',  'pinyin': 'MYRMB', 'market': 'Macro',   'type': 'forex' },
    { 'symbol': 'VIX',      'code': 'VIX',    'name': 'VIX恐慌指数',  'pinyin': 'VIX',  'market': 'Macro',   'type': 'index' },
]

# ── 全市场A股名称懒加载（不阻塞后端启动）───────────────────────────────
_ALL_STOCK_NAMES: list[dict] = []      # 全量个股注册表
_STOCK_NAMES_LOADED: bool = False
_STOCK_LOAD_LOCK = threading.Lock()      # 防止并发多次加载

# 快速 lookup 表（动态 + 静态分开，market_lookup 合并查询）
_SYMBOL_LOOKUP_STATIC = { item['symbol']: item for item in _SYMBOL_REGISTRY }


def _get_combined_lookup() -> dict:
    """返回完整 lookup：静态注册表 + 已加载的动态全市场A股（线程安全）"""
    base = dict(_SYMBOL_LOOKUP_STATIC)
    if _STOCK_NAMES_LOADED:
        for s in _ALL_STOCK_NAMES:
            base[s['symbol']] = s
    return base


def _pinyin_fallback(name: str) -> str:
    """获取名称首字拼音（无 pypinyin 时回退到名称前4字）"""
    try:
        from pypinyin import lazy_pinyin
        py = lazy_pinyin(name)
        return ''.join(py) if py else name[:4]
    except (ImportError, ValueError, TypeError):
        return name[:4]  # 无 pypinyin 时用名称前4字做近似


def _load_all_stock_names() -> list[dict]:
    """
    调用 akshare stock_info_a_code_name() 获取全市场A股代码+名称，
    懒加载一次，线程安全，结果缓存于 _ALL_STOCK_NAMES。
    """
    global _ALL_STOCK_NAMES, _STOCK_NAMES_LOADED
    if _STOCK_NAMES_LOADED:
        return _ALL_STOCK_NAMES

    with _STOCK_LOAD_LOCK:
        if _STOCK_NAMES_LOADED:   # double-check（其他线程已加载）
            return _ALL_STOCK_NAMES

        try:
            import akshare as ak
            logger.info("[SymbolRegistry] 开始加载全市场A股名称...")
            df = ak.stock_info_a_code_name()
            # 向量化处理
            df_work = df.copy()
            df_work['code'] = df_work['code'].astype(str).str.strip()
            df_work['name'] = df_work['name'].astype(str).str.strip()
            df_work = df_work[(df_work['code'].str.len() == 6) & (df_work['code'] != '') & (df_work['name'] != '')]
            df_work['prefix'] = df_work['code'].apply(lambda x: 'sh' if x[0] in ('6', '9') else ('bj' if x[0] == '8' else 'sz'))
            df_work['symbol'] = df_work['prefix'] + df_work['code']
            df_work['pinyin'] = df_work['name'].apply(_pinyin_fallback)
            df_work['market'] = 'AShare'
            df_work['type'] = 'stock'
            _ALL_STOCK_NAMES = df_work[['symbol', 'code', 'name', 'pinyin', 'market', 'type']].to_dict('records')
            _STOCK_NAMES_LOADED = True
            logger.info(f"[SymbolRegistry] 全市场A股加载完成: {len(_ALL_STOCK_NAMES)} 只")
        except Exception as e:
            logger.warning(f"[SymbolRegistry] 加载全市场A股失败，使用兜底数据: {e}", exc_info=True)
            _ALL_STOCK_NAMES = []
            _STOCK_NAMES_LOADED = True   # 标记"已尝试"，避免重复拉取

    return _ALL_STOCK_NAMES


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/market/symbols")
@handle_errors(module="market_symbols")
async def market_symbols():
    """返回全量符号注册表（含全市场A股），供前端搜索索引构建"""
    # 懒加载全市场A股名称（首次调用时从 akshare 拉取，之后走缓存）
    all_stocks = _load_all_stock_names()
    # 合并：静态注册表（指数+示例股）+ 全市场A股
    static_symbols = {s['symbol'] for s in _SYMBOL_REGISTRY}
    merged = list(_SYMBOL_REGISTRY) + [
        s for s in all_stocks if s['symbol'] not in static_symbols
    ]
    return success_response({
        'symbols': merged,
        'count': len(merged),
        'loaded': _STOCK_NAMES_LOADED,
        'timestamp': datetime.now().isoformat(),
    })


@router.get("/market/lookup/{symbol}")
@handle_errors(module="market_symbols")
async def market_lookup(symbol: str):
    """单个 symbol 的元信息查询（大小写折叠兜底）"""
    norm = _normalize_symbol(symbol)
    lookup = _get_combined_lookup()
    item = lookup.get(norm)
    if item:
        return success_response(item)
    # 大小写折叠兜底（如 'hsi' → 'hkHSI'，'ndx' → 'usNDX'）
    norm_lower = norm.lower()
    for key, val in lookup.items():
        if key.lower() == norm_lower:
            return success_response(val)
    return success_response(None, 'symbol not found')


@router.get("/market/all_stocks")
@handle_errors(module="market_symbols")
def market_all_stocks(request: Request):
    """
    全市场A股列表（来自 market_all_stocks 缓存表）
    支持搜索: ?search=茅台
    分页: ?page=1&page_size=50
    """
    try:
        from app.db.database import get_all_stocks

        # 获取参数 (从 Request 中提取)
        params = dict(request.query_params)
        search = params.get('search', '').strip()
        page = max(1, int(params.get('page', 1)))
        page_size = min(200, max(1, int(params.get('page_size', 50))))
        offset = (page - 1) * page_size

        total, rows = get_all_stocks(limit=page_size, offset=offset, search=search if search else None)

        return success_response({
            "stocks": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        })
    except Exception as e:
        logger.error(f"[market_all_stocks] 错误: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取全市场个股失败: {str(e)}")


@router.get("/market/all_stocks_lite")
@handle_errors(module="market_symbols")
async def market_all_stocks_lite():
    """全市场A股轻量列表（一次性返回，无分页，StockScreener专用）"""
    try:
        from app.db.database import get_all_stocks_lite
        rows = get_all_stocks_lite()
        return success_response({
            "stocks": rows,
            "total": len(rows),
        })
    except Exception as e:
        logger.error(f"[market_all_stocks_lite] 错误: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取全市场个股失败: {str(e)}")


@router.get("/market/stocks/search")
@handle_errors(module="market_symbols")
def search_stocks_api(
    keyword: str = None,
    min_pct_chg: float = None, max_pct_chg: float = None,
    min_turnover: float = None, max_turnover: float = None,
    min_price: float = None, max_price: float = None,
    min_pe: float = None, max_pe: float = None,
    min_pb: float = None, max_pb: float = None,
    min_mktcap: float = None, max_mktcap: float = None,
    sort_by: str = Query('change_pct', description="排序字段: change_pct|turnover|volume|per|pb|mktcap|code|name|price"),
    sort_dir: str = Query('desc', description="排序方向: asc|desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数(1-200)"),
):
    """
    全市场个股服务端搜索+过滤+排序+分页
    支持的过滤字段:
      keyword: 模糊搜索代码/名称
      min_pct_chg / max_pct_chg: 涨跌幅区间 (%)
      min_turnover / max_turnover: 换手率区间 (%)
      min_price / max_price: 价格区间（元）
      min_pe / max_pe: PE区间
      min_pb / max_pb: PB区间
      min_mktcap / max_mktcap: 市值区间（亿元）
    排序: sort_by=change_pct|turnover|volume|pe|pb|mktcap|code|name
    分页: page + page_size（每页最多200）
    """
    try:
        from app.db.database import search_stocks as _search
        total, rows, page, page_size = _search(
            keyword=keyword,
            min_pct_chg=min_pct_chg, max_pct_chg=max_pct_chg,
            min_turnover=min_turnover, max_turnover=max_turnover,
            min_price=min_price, max_price=max_price,
            min_pe=min_pe, max_pe=max_pe,
            min_pb=min_pb, max_pb=max_pb,
            min_mktcap=min_mktcap, max_mktcap=max_mktcap,
            sort_by=sort_by, sort_dir=sort_dir,
            page=page, page_size=page_size,
        )
        return success_response({
            "stocks": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        })
    except Exception as e:
        logger.exception("[search_stocks] 服务端搜索失败")
        return error_response(ErrorCode.INTERNAL_ERROR, f"搜索失败: {str(e)}")

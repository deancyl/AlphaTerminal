"""
P3 多账户模拟组合 - 路由层
CRUD: 账户 / 持仓 / 净值历史
"""
import time
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# ── Pydantic 模型 ──────────────────────────────────────────────

class PortfolioIn(BaseModel):
    name: str
    type: str = "portfolio"   # portfolio | account | strategy | group
    parent_id: Optional[int] = None
    currency: str = "CNY"  # CNY | USD | HKD
    asset_class: str = "mixed"  # stock | bond | fund | futures | options | mixed
    strategy: Optional[str] = None  # value | growth | balanced | index | quant
    benchmark: Optional[str] = None  # 000001 | 000300 | 399001 | 399006
    status: str = "active"  # active | frozen | closed
    initial_capital: float = 0.0
    description: Optional[str] = None

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None
    currency: Optional[str] = None
    asset_class: Optional[str] = None
    strategy: Optional[str] = None
    benchmark: Optional[str] = None
    status: Optional[str] = None
    initial_capital: Optional[float] = None
    description: Optional[str] = None

class PositionIn(BaseModel):
    portfolio_id: int
    symbol: str
    shares: int
    avg_cost: float

class PositionUpdate(BaseModel):
    shares: Optional[int] = None
    avg_cost: Optional[float] = None

# ── 响应格式标准化（可选使用）─────────────────────────────
def _ok(data, msg="success"):
    return {"code": 0, "message": msg, "data": data, "timestamp": int(time.time() * 1000)}

# ── 数据库工具 ────────────────────────────────────────────────

from app.db.database import _get_conn, _lock

def _row2dict(rows, cols):
    return [dict(zip(cols, r)) for r in rows]

# ── 账户 CRUD ─────────────────────────────────────────────────

@router.get("/")
async def list_portfolios():
    """所有账户列表（WAL 模式并发读，无需应用层锁）"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, name, type, parent_id, created_at, total_cost,
                      currency, asset_class, strategy, benchmark, status, initial_capital, description
               FROM portfolios ORDER BY id"""
        ).fetchall()
    finally:
        conn.close()
    return {"portfolios": _row2dict(rows, ["id", "name", "type", "parent_id", "created_at", "total_cost",
                                            "currency", "asset_class", "strategy", "benchmark", "status",
                                            "initial_capital", "description"])}

@router.post("/")
async def create_portfolio(body: PortfolioIn):
    """新建账户"""
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        try:
            # ── 环形嵌套防御 ─────────────────────────────────────
            if body.parent_id is not None:
                # 自身不能作为自己的 parent
                if body.parent_id == 0:
                    raise HTTPException(400, "parent_id 不能为 0（自身）")
                # parent_id 不能是自身的子孙节点：查出自身所有后代并校验
                descendants = _get_all_descendants(conn, body.parent_id)
                if body.parent_id in descendants:
                    raise HTTPException(400, f"parent_id ({body.parent_id}) 不能指向自身的后代节点，检测到环形嵌套")
            # ── 写入 ─────────────────────────────────────────────
            cur = conn.execute(
                """INSERT INTO portfolios (name, type, parent_id, created_at, total_cost,
                        currency, asset_class, strategy, benchmark, status, initial_capital, description)
                 VALUES (?,?,?,?,0,?,?,?,?,?,?,?)""",
                (body.name, body.type, body.parent_id, now,
                 body.currency, body.asset_class, body.strategy, body.benchmark,
                 body.status, body.initial_capital, body.description)
            )
            conn.commit()
            pid = cur.lastrowid
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"创建账户失败: {e}")
        conn.close()
    return {"id": pid, "name": body.name, "type": body.type, "parent_id": body.parent_id,
            "created_at": now, "total_cost": 0.0, "currency": body.currency,
            "asset_class": body.asset_class, "strategy": body.strategy,
            "benchmark": body.benchmark, "status": body.status,
            "initial_capital": body.initial_capital, "description": body.description}

@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: int):
    """删除账户（连带持仓和快照）"""
    with _lock:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
        conn.commit()
        deleted = cur.rowcount
        conn.close()
    if not deleted:
        raise HTTPException(404, "账户不存在")
    return {"ok": True}

# ── 持仓 CRUD ─────────────────────────────────────────────────

def _get_all_descendants(conn, portfolio_id: int, visited: set = None) -> list:
    """递归获取所有后代账户ID（包括子账户、孙账户等）。使用 visited set 阻断环形嵌套。"""
    if visited is None:
        visited = set()
    if portfolio_id in visited:
        return []
    visited.add(portfolio_id)
    result = [portfolio_id]
    cursor = conn.execute("SELECT id FROM portfolios WHERE parent_id=?", (portfolio_id,))
    children = [row[0] for row in cursor.fetchall()]
    for child_id in children:
        result.extend(_get_all_descendants(conn, child_id, visited))
    return result

@router.get("/{portfolio_id}/positions")
async def list_positions(portfolio_id: int, include_children: bool = Query(False, description="是否包含子账户持仓")):
    """账户当前持仓，可选包含所有子账户持仓"""
    # WAL 模式支持并发读
    conn = _get_conn()
    try:
        if include_children:
            # 获取所有后代账户ID
            all_ids = _get_all_descendants(conn, portfolio_id)
            placeholders = ','.join(['?' for _ in all_ids])
            rows = conn.execute(
                f"""SELECT p.id, p.symbol, p.shares, p.avg_cost, p.updated_at,
                           po.name as portfolio_name, po.id as portfolio_id
                    FROM positions p
                    JOIN portfolios po ON p.portfolio_id = po.id
                    WHERE p.portfolio_id IN ({placeholders})""",
                tuple(all_ids)
            ).fetchall()
            return {"positions": [{"id": r[0], "symbol": r[1], "shares": r[2],
                                    "avg_cost": r[3], "updated_at": r[4],
                                    "portfolio_name": r[5], "portfolio_id": r[6]} for r in rows],
                    "includes_children": True,
                    "portfolio_ids": all_ids}
        else:
            rows = conn.execute(
                "SELECT id, symbol, shares, avg_cost, updated_at FROM positions WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()
            return {"positions": [{"id": r[0], "symbol": r[1], "shares": r[2],
                                    "avg_cost": r[3], "updated_at": r[4]} for r in rows]}
    finally:
        conn.close()

@router.post("/positions")
async def upsert_position(body: PositionIn):
    """
    建仓或调仓：INSERT OR REPLACE
    shares=0 表示清仓（删除持仓）
    """
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        if body.shares == 0:
            conn.execute(
                "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
                (body.portfolio_id, body.symbol)
            )
            conn.commit()
            conn.close()
            return {"ok": True, "action": "cleared"}
        conn.execute(
            "INSERT OR REPLACE INTO positions (portfolio_id, symbol, shares, avg_cost, updated_at) "
            "VALUES (?,?,?,?,?)",
            (body.portfolio_id, body.symbol, body.shares, body.avg_cost, now)
        )
        conn.commit()
        conn.close()
    return {"ok": True, "action": "upserted"}

@router.delete("/{portfolio_id}/positions/{symbol}")
async def delete_position(portfolio_id: int, symbol: str):
    """清仓指定标的"""
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
            (portfolio_id, symbol)
        )
        conn.commit()
        conn.close()
    return {"ok": True}

# ── 实时浮动盈亏（依赖 SpotCache） ─────────────────────────────

@router.get("/{portfolio_id}/pnl")
async def portfolio_pnl(portfolio_id: int, include_children: bool = Query(False, description="是否包含子账户盈亏")):
    """
    实时浮动盈亏计算（专业增强版）
    增加: 名称、权重%、今日涨跌幅、市场、PE/PB、换手率
    支持: 包含所有子账户的聚合视图
    依赖 SpotCache（后台每3分钟刷新的全市场实时行情）
    """
    from app.services.sentiment_engine import SpotCache

    # WAL 模式支持并发读，但 SpotCache 读取和 DB 读取之间保持原子视图
    conn = _get_conn()
    try:
        if include_children:
            # 获取所有后代账户ID
            all_ids = _get_all_descendants(conn, portfolio_id)
            placeholders = ','.join(['?' for _ in all_ids])
            rows = conn.execute(
                f"""SELECT p.symbol, p.shares, p.avg_cost, po.name as portfolio_name, po.id as portfolio_id
                    FROM positions p
                    JOIN portfolios po ON p.portfolio_id = po.id
                    WHERE p.portfolio_id IN ({placeholders})""",
                tuple(all_ids)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()

        # 获取持仓股票的基本面数据（PE/PB等）
        stock_meta = {}
        try:
            meta_rows = conn.execute(
                "SELECT symbol, name, per, pb, mktcap, turnover FROM market_all_stocks"
            ).fetchall()
            for r in meta_rows:
                stock_key = r[0].lower().replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
                stock_meta[stock_key] = {"name": r[1], "per": r[2], "pb": r[3], "mktcap": r[4], "turnover": r[5]}
        except:
            pass
    finally:
        conn.close()

    if not rows:
        return {"positions": [], "total_pnl": 0.0, "total_cost": 0.0, "total_value": 0.0, "includes_children": include_children}

    spot = SpotCache.get_stocks()
    # 构建价格映射表，同时支持带前缀和不带前缀的代码
    price_map = {}
    for s in spot:
        code = s.get("code", "")
        price_map[code] = s  # 带前缀格式: sz300391
        # 同时添加不带前缀格式: 300391
        if len(code) > 2:
            price_map[code[2:]] = s  # 去掉前2位前缀
            price_map[code.lower()] = s
            price_map[code.upper()] = s
    
    # 如果 SpotCache 为空，从数据库兜底获取实时价格
    db_price_loaded = False
    if not spot or len(spot) < 10:
        logger.info("[Portfolio PnL] SpotCache 为空，从数据库兜底获取价格")
        try:
            conn = _get_conn()
            db_rows = conn.execute(
                "SELECT symbol, name, price, change_pct FROM market_all_stocks WHERE price > 0"
            ).fetchall()
            conn.close()
            for r in db_rows:
                sym = r[0]
                name = r[1] or ""
                price = float(r[2] or 0)
                chg_pct = float(r[3] or 0) if r[3] else 0.0
                # 归一化代码格式：同时支持 sh600519 和 600519
                price_map[sym] = {"code": sym, "name": name, "price": price, "chg_pct": chg_pct}
                if len(sym) > 2:
                    # 去掉前缀的版本
                    price_map[sym[2:]] = price_map[sym]
                    price_map[sym.lower()] = price_map[sym]
                    price_map[sym.upper()] = price_map[sym]
            db_price_loaded = True
            logger.info(f"[Portfolio PnL] 从数据库加载 {len(db_rows)} 只股票价格")
        except Exception as e:
            logger.warning(f"[Portfolio PnL] 数据库兜底失败: {e}")
    
    result = []
    total_cost = 0.0
    total_value = 0.0
    missing_prices = []  # 记录未找到价格的股票
    
    # 处理不同结构的rows
    for row in rows:
        if include_children:
            # row: (symbol, shares, avg_cost, portfolio_name, portfolio_id)
            symbol, shares, avg_cost, portfolio_name, portfolio_id_from_row = row
        else:
            # row: (symbol, shares, avg_cost)
            symbol, shares, avg_cost = row
            portfolio_name = None
            portfolio_id_from_row = None
            
        # 尝试多种格式的代码匹配
        info = price_map.get(symbol, {})
        if not info and len(symbol) == 6:
            # 尝试添加前缀
            if symbol.startswith("6"):
                info = price_map.get(f"sh{symbol}", {})
            elif symbol.startswith("0") or symbol.startswith("3"):
                info = price_map.get(f"sz{symbol}", {})
            elif symbol.startswith("4") or symbol.startswith("8"):
                info = price_map.get(f"bj{symbol}", {})
        
        if not info:
            missing_prices.append(symbol)
        current_price = info.get("price", avg_cost)
        change_pct   = info.get("change_pct", 0.0)
        market_value = shares * current_price
        cost_total   = shares * avg_cost
        pnl         = market_value - cost_total
        pnl_pct    = (pnl / cost_total * 100) if cost_total > 0 else 0.0

        sym_upper = symbol.upper().replace("SH", "").replace("SZ", "").replace("HK", "").replace("US", "")
        if sym_upper.startswith("6") or sym_upper.startswith("0") or sym_upper.startswith("3"):
            market = "A股"
        elif "hk" in symbol.lower():
            market = "港股"
        elif "us" in symbol.lower():
            market = "美股"
        else:
            market = "其他"

        meta = stock_meta.get(symbol, {})
        # 判断价格来源：如果找到实时数据，使用实时价格；否则使用成本价
        has_realtime_price = bool(info and info.get("price"))
        pos_data = {
            "symbol":       symbol,
            "name":         meta.get("name", symbol) if meta else (info.get("name") if info else symbol),
            "shares":       shares,
            "avg_cost":     round(avg_cost, 3),
            "price":        round(current_price, 3),
            "price_source": "realtime" if has_realtime_price else "fallback",
            "change_pct":   round(change_pct, 2),
            "market_value": round(market_value, 2),
            "cost_total":   round(cost_total, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":    round(pnl_pct, 2),
            "weight":       0.0,
            "market":       market,
            "pe":          round(meta.get("per"), 2) if meta and meta.get("per") else (round(info.get("pe"), 2) if info and info.get("pe") else None),
            "pb":          round(meta.get("pb"), 2) if meta and meta.get("pb") else (round(info.get("pb"), 2) if info and info.get("pb") else None),
            "turnover":    round(meta.get("turnover"), 2) if meta and meta.get("turnover") else (round(info.get("turnover"), 2) if info and info.get("turnover") else None),
        }

        if include_children:
            pos_data["portfolio_name"] = portfolio_name
            pos_data["portfolio_id"] = portfolio_id_from_row

        result.append(pos_data)
        total_cost  += cost_total
        total_value += market_value

    # 第二遍：计算权重
    for pos in result:
        pos["weight"] = round(pos["market_value"] / total_value * 100, 2) if total_value > 0 else 0.0

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    response = {
        "positions":    result,
        "total_cost":  round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl":   round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }

    if include_children:
        response["includes_children"] = True
        response["portfolio_count"] = len(set(r.get("portfolio_id") for r in result if r.get("portfolio_id")))
    
    # 添加调试信息
    if missing_prices:
        response["missing_price_count"] = len(missing_prices)
        response["missing_price_symbols"] = missing_prices[:10]  # 最多显示10个
    
    # 添加价格数据源信息
    if db_price_loaded:
        response["price_data_source"] = "DatabaseFallback"
    elif spot:
        response["price_data_source"] = "SpotCache"
    response["price_data_count"] = len(spot) if spot else 0

    return response




@router.get("/{portfolio_id}/snapshots")
async def get_snapshots(
    portfolio_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """净值历史快照"""
    # WAL 模式支持并发读
    conn = _get_conn()
    try:
        if start_date and end_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date BETWEEN ? AND ? ORDER BY date ASC",
                (portfolio_id, start_date, end_date)
            ).fetchall()
        elif start_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date>=? ORDER BY date ASC",
                (portfolio_id, start_date)
            ).fetchall()
        elif end_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date<=? ORDER BY date ASC",
                (portfolio_id, end_date)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? ORDER BY date ASC LIMIT 365"
                , (portfolio_id,)
            ).fetchall()
    finally:
        conn.close()
    return {
        "snapshots": [
            {"date": r[0], "total_asset": r[1], "total_cost": r[2],
             "pnl_pct": round((r[1]-r[2])/r[2]*100, 2) if r[2] else 0.0}
            for r in rows
        ]
    }

@router.post("/{portfolio_id}/snapshots")
async def save_snapshot(portfolio_id: int):
    """手动保存当日快照（供路由调用）"""
    return _save_snapshot_impl(portfolio_id)


def _save_snapshot_impl(portfolio_id: int):
    """
    保存当日净值快照（同步函数，供 scheduler 直接调用）
    计算: total_asset = Σ(shares * latest_close)，total_cost = Σ(shares * avg_cost)
    """
    today = date.today().isoformat()
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
            (portfolio_id,)
        ).fetchall()
        conn.close()

    if not rows:
        return {"ok": False, "message": "无持仓，无须保存"}

    # 从 market_data_realtime（SpotCache 刷新的实时表）取最新价格
    from app.db.database import get_latest_prices
    symbols = [r[0] for r in rows]
    prices  = {s["symbol"]: s["price"] for s in get_latest_prices(symbols)}

    total_asset = 0.0
    total_cost  = 0.0
    for symbol, shares, avg_cost in rows:
        price = prices.get(symbol, avg_cost)
        total_asset += shares * price
        total_cost  += shares * avg_cost

    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_snapshots (portfolio_id, date, total_asset, total_cost) "
            "VALUES (?,?,?,?)",
            (portfolio_id, today, round(total_asset, 2), round(total_cost, 2))
        )
        conn.commit()
        conn.close()

    return {
        "ok": True, "date": today,
        "total_asset": round(total_asset, 2),
        "total_cost": round(total_cost, 2),
        "pnl_pct": round((total_asset-total_cost)/total_cost*100, 2) if total_cost else 0.0
    }


# ═══════════════════════════════════════════════════════════════
# Task 9: 底层资产归因与风险分析
# ═══════════════════════════════════════════════════════════════

def _classify_asset(symbol: str, name: str = "") -> dict:
    """
    根据 symbol + name 推断底层资产类型与细分板块。
    返回: { category, sub_category, is_index }
    """
    sym = symbol.strip().lower()
    name_lower = name.lower()
    raw_code = sym.removeprefix("sh").removeprefix("sz").removeprefix("hk").removeprefix("us").removeprefix("jp").removeprefix("bj")

    # ── 固收：国债/国开债/地方债 ────────────────────────────────
    if any(kw in name_lower for kw in ["国债", "国开", "地方债", "政金债", "债券", "债"]):
        return {"category": "bond", "sub_category": "利率债", "is_index": False}

    # ── 商品期货 ────────────────────────────────────────────────
    if raw_code.upper() in ("AU", "AG", "CU", "AL", "ZN", "PB", "NI", "SN",
                             "RU", "RB", "HC", "I", "J", "JM", "焦煤",
                             "原油", "燃油", "沥青", "棕榈", "豆油", "菜油",
                             "棉花", "白糖", "苹果", "红枣"):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}
    if any(kw in name_lower for kw in ["黄金", "白银", "铜", "铝", "锌", "镍", "螺纹", "铁矿石", "焦炭", "原油"]):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}

    # ── 货币基金 / 现金管理 ────────────────────────────────────
    if raw_code.startswith("51") and len(raw_code) == 6:
        return {"category": "money_fund", "sub_category": "货币基金", "is_index": False}

    # ── 宽基指数 ETF（代码特征）─────────────────────────────────
    if raw_code.startswith("51") or raw_code.startswith("15") or raw_code.startswith("56"):
        return {"category": "etf", "sub_category": "宽基ETF", "is_index": True}
    if raw_code in ("000001", "000300", "000016", "000688", "000905", "000852",
                    "399001", "399006", "399100", "399005", "399673"):
        return {"category": "index", "sub_category": "A股指数", "is_index": True}

    # ── 港股 ────────────────────────────────────────────────────
    if sym.startswith("hk"):
        return {"category": "hk_stock", "sub_category": "港股", "is_index": False}

    # ── A股（sh6 / sz0,3 开头个股）───────────────────────────────
    if raw_code.startswith("6") or raw_code.startswith("0") or raw_code.startswith("3"):
        return {"category": "a_stock", "sub_category": "A股个股", "is_index": False}

    return {"category": "other", "sub_category": "其他", "is_index": False}


@router.get("/{portfolio_id}/attribution")
async def get_attribution(portfolio_id: int, include_children: bool = Query(False)):
    """
    底层资产归因 + 组合风险（VaR / 波动率估算）。

    分类规则：
      - sh510xxx / sz159xxx → 宽基ETF
      - sh000xxx / sz399xxx → A股指数
      - 国债/国开/债券关键词 → 利率债
      - AU/AG/黄金/白银 等 → 商品期货
      - sh6xxxxx / sz0/3xxxx → A股个股
      - hkxxxxx → 港股

    返回:
      - attribution[]   各底层资产组的权重、收益贡献
      - risk_metrics     日VaR(95%)、年化波动率、夏普比率
      - total_exposure   各 category 的总仓位占比
    """
    from app.db.database import _get_conn
    from app.services.sentiment_engine import SpotCache

    # ── 1. 获取持仓（WAL 模式并发读）────────────────────────────
    conn = _get_conn()
    try:
        if include_children:
            all_ids = [portfolio_id]
            cur = conn.execute("SELECT id FROM portfolios WHERE parent_id=?", (portfolio_id,)).fetchall()
            all_ids += [r[0] for r in cur]
            ph = ','.join(['?'] * len(all_ids))
            rows = conn.execute(
                f"SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id IN ({ph})",
                tuple(all_ids)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return _ok({"attribution": [], "risk_metrics": None, "total_exposure": []})

    # ── 2. 获取最新价格 ────────────────────────────────────────

    # ── 2. 获取最新价格 ────────────────────────────────────────
    spot = SpotCache.get_stocks()
    price_map = {}
    for s in spot:
        code = s.get("code", "")
        price_map[code] = s
        if len(code) > 2:
            price_map[code[2:]] = s
            price_map[code.lower()] = s
            price_map[code.upper()] = s

    if len(price_map) < 10:
        conn2 = _get_conn()
        try:
            db_rows = conn2.execute(
                "SELECT symbol, name, price, change_pct FROM market_all_stocks WHERE price > 0"
            ).fetchall()
            for r in db_rows:
                sym, name, price, chg_pct = r
                price_map[sym] = {"code": sym, "name": name, "price": float(price or 0), "chg_pct": float(chg_pct or 0)}
                if len(sym) > 2:
                    price_map[sym[2:]] = price_map[sym]
        finally:
            conn2.close()

    # ── 3. 逐条计算持仓盈亏并分类 ──────────────────────────────
    groups = {}

    for symbol, shares, avg_cost in rows:
        info = price_map.get(symbol, {})
        if not info and len(symbol) == 6:
            info = price_map.get(f"sh{symbol}", {})
            if not info:
                info = price_map.get(f"sz{symbol}", {})
        if not info:
            info = price_map.get(symbol[2:]) if len(symbol) > 2 else {}

        price        = info.get("price", avg_cost)
        name         = info.get("name", symbol)
        market_value = shares * price
        cost         = shares * avg_cost
        pnl          = market_value - cost
        pnl_pct      = (pnl / cost * 100) if cost > 0 else 0.0

        cls = _classify_asset(symbol, name)
        cat = cls["category"]

        if cat not in groups:
            groups[cat] = {
                "category":     cat,
                "sub_category": cls["sub_category"],
                "is_index":     cls["is_index"],
                "market_value": 0.0,
                "cost":         0.0,
                "pnl":          0.0,
                "positions":    [],
            }
        groups[cat]["market_value"] += market_value
        groups[cat]["cost"]         += cost
        groups[cat]["pnl"]          += pnl
        groups[cat]["positions"].append({
            "symbol":       symbol,
            "name":         name,
            "shares":       shares,
            "avg_cost":     avg_cost,
            "price":        price,
            "market_value": round(market_value, 2),
            "cost":         round(cost, 2),
            "pnl":          round(pnl, 2),
            "pnl_pct":      round(pnl_pct, 2),
        })

    # ── 4. 汇总计算（防御性容错）──────────────────────────────
    try:
        total_mv    = sum(g["market_value"] for g in groups.values())
        total_cost  = sum(g["cost"]        for g in groups.values())
        total_pnl   = sum(g["pnl"]         for g in groups.values())

        # 极端边界：所有持仓市值和盈亏均为 0（价格全失效），返回空数据避免后续除零
        if total_mv <= 0 and total_pnl == 0:
            return _ok({"attribution": [], "risk_metrics": None, "total_exposure": [],
                        "summary": {"total_market_value": 0, "total_cost": 0, "total_pnl": 0, "total_pnl_pct": 0}})

        attribution = []
        for g in groups.values():
            w  = g["market_value"] / total_mv if total_mv > 0 else 0
            pc = g["pnl"] / total_pnl * 100   if total_pnl != 0 else 0
            attribution.append({
                "category":        g["category"],
                "sub_category":    g["sub_category"],
                "is_index":        g["is_index"],
                "market_value":    round(g["market_value"], 2),
                "cost":            round(g["cost"], 2),
                "pnl":             round(g["pnl"], 2),
                "weight":          round(w * 100, 2),
                "pnl_contrib_pct": round(pc, 2),
                "position_count":  len(g["positions"]),
                "positions":       g["positions"][:5],
            })

        attribution.sort(key=lambda x: x["market_value"], reverse=True)

        # ── 5. 底层资产配置 ─────────────────────────────────────
        total_exposure = [
            {"name": g["sub_category"], "category": g["category"],
             "value": round(g["market_value"], 2), "weight": round(g["market_value"] / total_mv * 100, 2)}
            for g in sorted(groups.values(), key=lambda x: x["market_value"], reverse=True)
        ]

        # ── 6. 风险指标 ─────────────────────────────────────────
        risk_metrics = None
        try:
            conn3 = _get_conn()
            try:
                snap_rows = conn3.execute(
                    "SELECT date, total_asset FROM portfolio_snapshots WHERE portfolio_id=? ORDER BY date ASC LIMIT 60",
                    (portfolio_id,)
                ).fetchall()
            finally:
                conn3.close()

            if snap_rows and len(snap_rows) >= 5:
                assets  = [float(r[1]) for r in snap_rows]
                returns = [(assets[i] - assets[i-1]) / assets[i-1]
                           for i in range(1, len(assets)) if assets[i-1] > 0]

                if returns:
                    import math
                    mean_ret  = sum(returns) / len(returns)
                    variance  = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                    daily_vol = math.sqrt(variance)
                    ann_vol   = daily_vol * math.sqrt(252)

                    try:
                        from statistics import NormalDist
                        z_95 = NormalDist().inv_cdf(0.95)
                    except Exception:
                        z_95 = 1.645

                    latest_asset = assets[-1]
                    var_daily_95 = latest_asset * z_95 * daily_vol

                    risk_free     = 0.03
                    years         = max(len(assets) / 252, 0.01)
                    total_ret     = (assets[-1] - assets[0]) / assets[0]
                    ann_ret       = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
                    sharpe        = (ann_ret - risk_free) / ann_vol if ann_vol > 0 else 0

                    risk_metrics = {
                        "var_daily_95":      round(var_daily_95, 2),
                        "var_daily_95_pct": round(var_daily_95 / latest_asset * 100, 2),
                        "annual_volatility": round(ann_vol * 100, 2),
                        "sharpe_ratio":      round(sharpe, 2),
                        "total_return_pct":  round(total_ret * 100, 2),
                        "annual_return_pct": round(ann_ret * 100, 2),
                        "days":              len(assets),
                    }
        except Exception as e:
            logger.warning(f"[Attribution] risk_metrics error: {e}")

        return _ok({
            "attribution":    attribution,
            "total_exposure":  total_exposure,
            "risk_metrics":    risk_metrics,
            "summary": {
                "total_market_value": round(total_mv, 2),
                "total_cost":        round(total_cost, 2),
                "total_pnl":         round(total_pnl, 2),
                "total_pnl_pct":     round((total_pnl / total_cost * 100) if total_cost else 0, 2),
            },
        })

    except Exception as e:
        logger.error(f"[Attribution] 计算异常: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="归因计算时发生错误，请检查是否有异常交易数据")

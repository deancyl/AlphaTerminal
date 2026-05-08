"""
Strategy Database Service - Strategy CRUD operations with SQLite persistence

Tables:
- strategies: id, name, description, code, market, parameters, stop_loss_pct, take_profit_pct, created_at, updated_at, deleted_at
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Use the same database path as the main application
from app.db.database import _get_conn, _lock


def init_strategy_table():
    """Initialize strategies table (called from database.py init_tables)"""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    code TEXT NOT NULL,
                    market TEXT DEFAULT 'AStock',
                    parameters TEXT DEFAULT '{}',
                    stop_loss_pct REAL DEFAULT 2.0,
                    take_profit_pct REAL DEFAULT 6.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT DEFAULT NULL
                )
            """)
            # Indexes for frequently queried columns
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategies_market ON strategies(market)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategies_deleted ON strategies(deleted_at)")
            conn.commit()
        finally:
            conn.close()


def create_strategy(
    strategy_id: str,
    name: str,
    code: str,
    description: str = "",
    market: str = "AStock",
    parameters: Dict[str, Any] = None,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 6.0,
) -> Dict[str, Any]:
    """
    Create a new strategy
    
    Args:
        strategy_id: Unique strategy identifier
        name: Strategy name
        code: Strategy code
        description: Strategy description
        market: Target market (AStock, HKStock, USStock, etc.)
        parameters: Strategy parameters dict
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
    
    Returns:
        Created strategy dict
    """
    now = datetime.now().isoformat()
    params_json = json.dumps(parameters or {}, ensure_ascii=False)
    
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO strategies 
                (id, name, description, code, market, parameters, stop_loss_pct, take_profit_pct, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id,
                name,
                description,
                code,
                market,
                params_json,
                stop_loss_pct,
                take_profit_pct,
                now,
                now,
            ))
            conn.commit()
            
            return {
                "id": strategy_id,
                "name": name,
                "description": description,
                "code": code,
                "market": market,
                "parameters": parameters or {},
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
                "created_at": now,
                "updated_at": now,
            }
        except sqlite3.IntegrityError as e:
            logger.error(f"[StrategyDB] Create failed - duplicate id: {strategy_id}")
            raise ValueError(f"Strategy with id {strategy_id} already exists")
        except Exception as e:
            logger.error(f"[StrategyDB] Create failed: {e}")
            raise
        finally:
            conn.close()


def get_strategy(strategy_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a strategy by ID (excludes soft-deleted)
    
    Args:
        strategy_id: Strategy ID
    
    Returns:
        Strategy dict or None if not found
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM strategies WHERE id = ? AND deleted_at IS NULL",
            (strategy_id,)
        ).fetchone()
        
        if row is None:
            return None
        
        return _row_to_dict(row)
    except Exception as e:
        logger.error(f"[StrategyDB] Get failed: {e}")
        return None
    finally:
        conn.close()


def list_strategies(
    market: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List strategies with optional filters
    
    Args:
        market: Filter by market (optional)
        include_deleted: Include soft-deleted strategies
        limit: Max results
        offset: Offset for pagination
    
    Returns:
        List of strategy dicts
    """
    conn = _get_conn()
    try:
        conditions = []
        params = []
        
        if not include_deleted:
            conditions.append("deleted_at IS NULL")
        
        if market:
            conditions.append("market = ?")
            params.append(market)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM strategies 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[StrategyDB] List failed: {e}")
        return []
    finally:
        conn.close()


def update_strategy(
    strategy_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    code: Optional[str] = None,
    market: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a strategy (partial update)
    
    Args:
        strategy_id: Strategy ID
        name: New name (optional)
        description: New description (optional)
        code: New code (optional)
        market: New market (optional)
        parameters: New parameters (optional)
        stop_loss_pct: New stop loss (optional)
        take_profit_pct: New take profit (optional)
    
    Returns:
        Updated strategy dict or None if not found
    """
    # Check if exists and not deleted
    existing = get_strategy(strategy_id)
    if existing is None:
        return None
    
    # Build update query
    updates = []
    params = []
    
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if code is not None:
        updates.append("code = ?")
        params.append(code)
    if market is not None:
        updates.append("market = ?")
        params.append(market)
    if parameters is not None:
        updates.append("parameters = ?")
        params.append(json.dumps(parameters, ensure_ascii=False))
    if stop_loss_pct is not None:
        updates.append("stop_loss_pct = ?")
        params.append(stop_loss_pct)
    if take_profit_pct is not None:
        updates.append("take_profit_pct = ?")
        params.append(take_profit_pct)
    
    if not updates:
        return existing  # Nothing to update
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(strategy_id)
    
    with _lock:
        conn = _get_conn()
        try:
            query = f"UPDATE strategies SET {', '.join(updates)} WHERE id = ? AND deleted_at IS NULL"
            conn.execute(query, params)
            conn.commit()
            
            return get_strategy(strategy_id)
        except Exception as e:
            logger.error(f"[StrategyDB] Update failed: {e}")
            raise
        finally:
            conn.close()


def delete_strategy(strategy_id: str, soft_delete: bool = True) -> bool:
    """
    Delete a strategy
    
    Args:
        strategy_id: Strategy ID
        soft_delete: If True, set deleted_at timestamp; if False, hard delete
    
    Returns:
        True if deleted, False if not found
    """
    with _lock:
        conn = _get_conn()
        try:
            if soft_delete:
                # Soft delete
                cursor = conn.execute(
                    "UPDATE strategies SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                    (datetime.now().isoformat(), strategy_id)
                )
            else:
                # Hard delete
                cursor = conn.execute(
                    "DELETE FROM strategies WHERE id = ?",
                    (strategy_id,)
                )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[StrategyDB] Delete failed: {e}")
            return False
        finally:
            conn.close()


def restore_strategy(strategy_id: str) -> bool:
    """
    Restore a soft-deleted strategy
    
    Args:
        strategy_id: Strategy ID
    
    Returns:
        True if restored, False if not found
    """
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "UPDATE strategies SET deleted_at = NULL, updated_at = ? WHERE id = ? AND deleted_at IS NOT NULL",
                (datetime.now().isoformat(), strategy_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[StrategyDB] Restore failed: {e}")
            return False
        finally:
            conn.close()


def count_strategies(market: Optional[str] = None, include_deleted: bool = False) -> int:
    """
    Count strategies with optional filters
    
    Args:
        market: Filter by market (optional)
        include_deleted: Include soft-deleted strategies
    
    Returns:
        Count of strategies
    """
    conn = _get_conn()
    try:
        conditions = []
        params = []
        
        if not include_deleted:
            conditions.append("deleted_at IS NULL")
        
        if market:
            conditions.append("market = ?")
            params.append(market)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"SELECT COUNT(*) as cnt FROM strategies WHERE {where_clause}"
        row = conn.execute(query, params).fetchone()
        
        return row["cnt"] if row else 0
    except Exception as e:
        logger.error(f"[StrategyDB] Count failed: {e}")
        return 0
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert sqlite3.Row to dict with JSON parsing"""
    result = dict(row)
    
    # Parse JSON fields
    if result.get("parameters"):
        try:
            result["parameters"] = json.loads(result["parameters"])
        except (json.JSONDecodeError, TypeError):
            result["parameters"] = {}
    else:
        result["parameters"] = {}
    
    return result

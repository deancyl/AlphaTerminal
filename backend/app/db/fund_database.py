"""
Fund Database Schema

This module provides the database schema for fund-related tables including:
- Fund indicators and metadata
- Fund issuance pipeline
- Fund company profiles and distribution history
- Market sentiment and style history
- Bond yield curves and credit spreads
- Backtest statistics

All tables follow the same WAL mode and connection patterns as the main database.
"""

import sqlite3
import threading
import logging
import os
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_fund_db_path() -> str:
    """
    Get fund database path in user config directory.

    Priority:
    1. APP_DATA environment variable (Tauri/EXE packaging)
    2. ~/.config/alphaterminal/ (standard user config)

    Returns:
        str: Full path to fund_database.db
    """
    # Check for Tauri/EXE environment variable
    app_data = os.environ.get("APP_DATA")

    if app_data:
        db_dir = Path(app_data)
    else:
        # Standard user config directory
        db_dir = Path.home() / ".config" / "alphaterminal"

    # Ensure directory exists
    db_dir.mkdir(parents=True, exist_ok=True)

    return str(db_dir / "fund_database.db")


# Database path (user config directory for Tauri compatibility)
_fund_db_path = get_fund_db_path()
_fund_lock = threading.RLock()

# Environment variable force WAL mode
_FORCE_WAL = os.environ.get("ALPHATERMINAL_FORCE_WAL", "").lower() in (
    "1",
    "true",
    "yes",
)

# Thread-local connection pool
_fund_thread_local = threading.local()
_FUND_WAL_MODE_CHECKED = False
_FUND_USE_WAL = True


def _get_fund_thread_conn():
    """Get current thread's connection (reuse, avoid frequent create/close)"""
    global _FUND_WAL_MODE_CHECKED, _FUND_USE_WAL

    if not hasattr(_fund_thread_local, "conn") or _fund_thread_local.conn is None:
        conn = sqlite3.connect(_fund_db_path, timeout=45.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # WAL mode detection (only first time)
        if not _FUND_WAL_MODE_CHECKED:
            # Force WAL mode via environment variable (highest priority)
            if _FORCE_WAL:
                _FUND_USE_WAL = True
                logger.info("[FundDB] WAL mode forced via ALPHATERMINAL_FORCE_WAL=1")
            else:
                # Default enable WAL (v0.6.49 fix for concurrent lock)
                _FUND_USE_WAL = True
                logger.info(f"[FundDB] WAL mode enabled (default) for: {_fund_db_path}")
            _FUND_WAL_MODE_CHECKED = True

        if _FUND_USE_WAL:
            conn.execute("PRAGMA journal_mode=WAL")
        else:
            conn.execute("PRAGMA journal_mode=DELETE")

        # v0.6.67: Increase lock wait timeout to 45 seconds
        conn.execute("PRAGMA busy_timeout=45000")

        # v0.6.62: SQLite performance optimization PRAGMA
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance performance and safety
        conn.execute("PRAGMA cache_size=-64000")  # 64MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")  # Temp tables in memory
        _fund_thread_local.conn = conn
        logger.debug(
            f"[FundDB] Created new connection for thread {threading.current_thread().name}"
        )

    return _fund_thread_local.conn


def _close_fund_thread_conn():
    """Close current thread's connection (for cleanup)"""
    if hasattr(_fund_thread_local, "conn") and _fund_thread_local.conn:
        _fund_thread_local.conn.close()
        _fund_thread_local.conn = None


@contextmanager
def get_fund_conn():
    """Context manager: Get thread-level connection (reuse, not frequent close)"""
    conn = _get_fund_thread_conn()
    try:
        yield conn
    except sqlite3.Error as e:
        logger.error(f"[FundDB_CTX] Database error: {type(e).__name__}: {e}", exc_info=True)
        try:
            conn.rollback()
        except sqlite3.Error as rollback_err:
            logger.error(
                f"[FundDB_CTX] Rollback failed: {type(rollback_err).__name__}: {rollback_err}",
                exc_info=True,
            )
        raise
    except Exception as e:
        logger.error(
            f"[FundDB_CTX] Unexpected error: {type(e).__name__}: {e}", exc_info=True
        )
        try:
            conn.rollback()
        except sqlite3.Error as rollback_err:
            logger.error(
                f"[FundDB_CTX] Rollback failed: {type(rollback_err).__name__}: {rollback_err}",
                exc_info=True,
            )
        raise


def _get_fund_conn():
    """Get new connection (for scenarios requiring independent connection)"""
    conn = sqlite3.connect(_fund_db_path, timeout=45.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _FUND_USE_WAL:
        conn.execute("PRAGMA journal_mode=WAL")
    else:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=45000")

    # v0.6.62: SQLite performance optimization PRAGMA
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")

    return conn


def init_fund_database():
    """
    Initialize all fund-related tables.
    
    Creates the following tables:
    - fund_indicators: Core filtering table with fund metrics
    - fund_issue_pipeline: Fund issuance tracking
    - fund_company_metadata: Company profiles
    - fund_company_distribution_history: Holdings history
    - market_fear_greed_sentiment_history: FGI time series
    - market_style_strength_history: Style rotation
    - bond_equity_yield_spread_history: ERP calculation
    - index_valuation_history: PE/PB percentiles
    - market_crowding_valuation_history: Crowding scores
    - bond_yield_curve_structure: Yield curves
    - bond_credit_spread_history: Credit spreads
    - backtest_stats_macro_strategies: Strategy backtest results
    """
    with _fund_lock:
        conn = _get_fund_conn()
        
        # ═══════════════════════════════════════════════════════════════
        # 1. FUND TABLES
        # ═══════════════════════════════════════════════════════════════
        
        # 1.1 Fund Indicators - Core filtering table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_indicators (
                fund_code TEXT PRIMARY KEY,
                fund_name TEXT,
                fund_type TEXT,
                manager TEXT,
                setup_date TEXT,
                setup_year INTEGER,
                scale REAL,
                company_name TEXT,
                return_1y REAL,
                return_3y REAL,
                return_5y REAL,
                volatility_1y REAL,
                max_drawdown_1y REAL,
                sharpe_1y REAL,
                sortino_1y REAL,
                heavy_sector TEXT,
                heavy_stock_top1 TEXT,
                heavy_stock_top2 TEXT,
                heavy_stock_top3 TEXT,
                purchase_fee REAL,
                redemption_fee REAL,
                subscription_status TEXT,
                rating_morningstar REAL,
                rating_3y REAL,
                rating_5y REAL,
                manager_experience_years REAL,
                manager_total_scale REAL,
                institutional_holding_pct REAL,
                retail_holding_pct REAL,
                update_time TEXT,
                data_source TEXT
            )
        """)
        
        # Indexes for fund_indicators
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_indicators_type_scale_return "
            "ON fund_indicators(fund_type, scale, return_1y)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_indicators_manager "
            "ON fund_indicators(manager)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_indicators_company "
            "ON fund_indicators(company_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_indicators_return_1y "
            "ON fund_indicators(return_1y DESC)"
        )
        
        # 1.2 Fund Issue Pipeline - Fund issuance tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_issue_pipeline (
                fund_code TEXT PRIMARY KEY,
                fund_name TEXT,
                company TEXT,
                fund_type TEXT,
                subscribe_start_date TEXT,
                subscribe_end_date TEXT,
                status TEXT,
                initial_scale REAL,
                delist_scale REAL,
                delist_date TEXT,
                issue_fee_rate REAL,
                management_fee_rate REAL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_issue_status "
            "ON fund_issue_pipeline(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_issue_subscribe_end "
            "ON fund_issue_pipeline(subscribe_end_date)"
        )
        
        # 1.3 Fund Company Metadata - Company profiles
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_company_metadata (
                company_id TEXT PRIMARY KEY,
                company_name TEXT,
                establish_date TEXT,
                total_scale REAL,
                non_money_scale REAL,
                fund_count INTEGER,
                manager_count INTEGER,
                avg_manager_experience REAL,
                award_count INTEGER,
                equity_fund_scale REAL,
                bond_fund_scale REAL,
                mixed_fund_scale REAL,
                updated_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_company_total_scale "
            "ON fund_company_metadata(total_scale DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_company_fund_count "
            "ON fund_company_metadata(fund_count DESC)"
        )
        
        # 1.4 Fund Company Distribution History - Holdings history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_company_distribution_history (
                company_id TEXT NOT NULL,
                dist_type TEXT NOT NULL,
                stat_quarter TEXT NOT NULL,
                item_name TEXT NOT NULL,
                weight REAL,
                PRIMARY KEY (company_id, dist_type, stat_quarter, item_name)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_dist_company "
            "ON fund_company_distribution_history(company_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_dist_quarter "
            "ON fund_company_distribution_history(stat_quarter)"
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 2. MARKET HISTORY TABLES
        # ═══════════════════════════════════════════════════════════════
        
        # 2.1 Market Fear & Greed Sentiment History - FGI time series
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_fear_greed_sentiment_history (
                trade_date TEXT PRIMARY KEY,
                composite_score REAL,
                sentiment_status TEXT,
                factor_volatility REAL,
                factor_safe_haven REAL,
                factor_margin_ratio REAL,
                factor_volume_deviation REAL,
                factor_futures_basis REAL,
                factor_stock_strength REAL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fgi_date "
            "ON market_fear_greed_sentiment_history(trade_date DESC)"
        )
        
        # 2.2 Market Style Strength History - Style rotation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_style_strength_history (
                trade_date TEXT NOT NULL,
                index_code_num TEXT NOT NULL,
                index_code_den TEXT NOT NULL,
                ratio_value REAL,
                percentile_rank_3y REAL,
                PRIMARY KEY (trade_date, index_code_num, index_code_den)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_style_date "
            "ON market_style_strength_history(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_style_num_den "
            "ON market_style_strength_history(index_code_num, index_code_den)"
        )
        
        # 2.3 Bond Equity Yield Spread History - ERP calculation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bond_equity_yield_spread_history (
                index_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                pe_ttm REAL,
                treasury_yield_10y REAL,
                erp_spread REAL,
                moving_mean_10y REAL,
                std_dev_1y_10y REAL,
                std_dev_2y_10y REAL,
                percentile_rank_10y REAL,
                index_close_price REAL,
                PRIMARY KEY (index_code, trade_date)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_erp_date "
            "ON bond_equity_yield_spread_history(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_erp_index "
            "ON bond_equity_yield_spread_history(index_code)"
        )
        
        # 2.4 Index Valuation History - PE/PB percentiles
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_valuation_history (
                index_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                pe_ttm REAL,
                pb REAL,
                percentile_rank_10y REAL,
                moving_mean_10y REAL,
                index_close_price REAL,
                PRIMARY KEY (index_code, trade_date)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_val_date "
            "ON index_valuation_history(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_val_index "
            "ON index_valuation_history(index_code)"
        )
        
        # 2.5 Market Crowding Valuation History - Crowding scores
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_crowding_valuation_history (
                asset_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                category TEXT NOT NULL,
                crowding_score REAL,
                pe_percentile REAL,
                close_price REAL,
                PRIMARY KEY (asset_code, trade_date, category)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crowd_date "
            "ON market_crowding_valuation_history(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crowd_asset "
            "ON market_crowding_valuation_history(asset_code)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crowd_category "
            "ON market_crowding_valuation_history(category)"
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 3. BOND TABLES
        # ═══════════════════════════════════════════════════════════════
        
        # 3.1 Bond Yield Curve Structure - Yield curves
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bond_yield_curve_structure (
                bond_type TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                tenor TEXT NOT NULL,
                yield_ytm REAL,
                yield_change_bp REAL,
                PRIMARY KEY (bond_type, trade_date, tenor)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_yield_date "
            "ON bond_yield_curve_structure(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_yield_type "
            "ON bond_yield_curve_structure(bond_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_yield_tenor "
            "ON bond_yield_curve_structure(tenor)"
        )
        
        # 3.2 Bond Credit Spread History - Credit spreads
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bond_credit_spread_history (
                bond_category TEXT NOT NULL,
                rating TEXT NOT NULL,
                tenor TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                benchmark_type TEXT NOT NULL,
                yield_ytm REAL,
                credit_spread REAL,
                percentile_rank REAL,
                PRIMARY KEY (bond_category, rating, tenor, trade_date, benchmark_type)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_credit_date "
            "ON bond_credit_spread_history(trade_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_credit_rating "
            "ON bond_credit_spread_history(rating)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_credit_tenor "
            "ON bond_credit_spread_history(tenor)"
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 4. BACKTEST TABLES
        # ═══════════════════════════════════════════════════════════════
        
        # 4.1 Backtest Stats Macro Strategies - Strategy backtest results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_stats_macro_strategies (
                index_code TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                range_min REAL NOT NULL,
                range_max REAL NOT NULL,
                holding_period TEXT NOT NULL,
                win_probability REAL,
                avg_return REAL,
                sample_count INTEGER,
                PRIMARY KEY (index_code, metric_type, range_min, range_max, holding_period)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_backtest_index "
            "ON backtest_stats_macro_strategies(index_code)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_backtest_metric "
            "ON backtest_stats_macro_strategies(metric_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_backtest_holding "
            "ON backtest_stats_macro_strategies(holding_period)"
        )
        
        conn.commit()
        conn.close()
    
    logger.info(f"FundDB Ready: {_fund_db_path}")


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════


def get_table_list() -> list:
    """Get list of all tables in fund database."""
    conn = _get_fund_conn()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_index_list() -> list:
    """Get list of all indexes in fund database."""
    conn = _get_fund_conn()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_table_info(table_name: str) -> list:
    """Get column info for a specific table."""
    conn = _get_fund_conn()
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def verify_schema() -> dict:
    """
    Verify that all required tables exist.
    
    Returns:
        dict: {
            'success': bool,
            'tables': list of existing tables,
            'missing': list of missing tables,
            'indexes': list of indexes
        }
    """
    required_tables = [
        'fund_indicators',
        'fund_issue_pipeline',
        'fund_company_metadata',
        'fund_company_distribution_history',
        'market_fear_greed_sentiment_history',
        'market_style_strength_history',
        'bond_equity_yield_spread_history',
        'index_valuation_history',
        'market_crowding_valuation_history',
        'bond_yield_curve_structure',
        'bond_credit_spread_history',
        'backtest_stats_macro_strategies',
    ]
    
    existing_tables = get_table_list()
    missing_tables = [t for t in required_tables if t not in existing_tables]
    indexes = get_index_list()
    
    return {
        'success': len(missing_tables) == 0,
        'tables': existing_tables,
        'missing': missing_tables,
        'indexes': indexes,
        'total_tables': len(existing_tables),
        'total_indexes': len(indexes),
    }

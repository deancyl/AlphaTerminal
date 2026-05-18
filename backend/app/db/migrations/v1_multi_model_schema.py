"""
Multi-Model Schema Migration (v1)

Creates the database schema for multi-model management and token tracking.

Tables:
    - model_pricing_catalog: Built-in + admin model pricing overrides
    - token_usage_logs: Token usage time-series per request
    - copilot_sessions: Session management with model bindings
    - model_config_versions: Model configuration versioning
    - usage_aggregates: Aggregated usage statistics

CRITICAL: This migration is idempotent and safe to run multiple times.
All tables use IF NOT EXISTS to prevent data loss.
"""
import sqlite3
import logging
import threading
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Thread lock for schema operations
_schema_lock = threading.RLock()


def _get_conn():
    import os
    _db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
        'database.db'
    )
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    # Use DELETE journal mode for network-safe operation
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def get_schema_conn():
    """Context manager for schema operations with proper cleanup."""
    conn = _get_conn()
    try:
        yield conn
    except Exception as e:
        logger.error(f"[Schema] Error during schema operation: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def create_model_pricing_catalog_table(conn):
    """
    Create model_pricing_catalog table.
    
    Stores pricing information for all supported models.
    Built-in models have is_builtin=1, admin overrides have is_builtin=0.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_pricing_catalog (
            model_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            display_name TEXT NOT NULL,
            input_cost_per_token REAL NOT NULL,
            output_cost_per_token REAL NOT NULL,
            context_length INTEGER NOT NULL,
            is_builtin INTEGER DEFAULT 0,
            metadata TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Indexes for common queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pricing_provider ON model_pricing_catalog(provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pricing_builtin ON model_pricing_catalog(is_builtin)")
    logger.debug("[Schema] Created model_pricing_catalog table")


def create_token_usage_logs_table(conn):
    """
    Create token_usage_logs table.
    
    Time-series log of every LLM API call for cost tracking.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            session_id TEXT,
            model_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            duration_ms INTEGER,
            user_id TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # Indexes for time-series queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_session ON token_usage_logs(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_model ON token_usage_logs(model_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_provider ON token_usage_logs(provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user ON token_usage_logs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_created ON token_usage_logs(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_session_created ON token_usage_logs(session_id, created_at)")
    logger.debug("[Schema] Created token_usage_logs table")


def create_copilot_sessions_table(conn):
    """
    Create copilot_sessions table.
    
    Session management with model bindings and usage aggregation.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS copilot_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            config_version INTEGER DEFAULT 1,
            bound_models TEXT,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL,
            expires_at TEXT,
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0
        )
    """)
    
    # Indexes for session queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON copilot_sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_active ON copilot_sessions(last_active_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_expires ON copilot_sessions(expires_at)")
    logger.debug("[Schema] Created copilot_sessions table")


def create_model_config_versions_table(conn):
    """
    Create model_config_versions table.
    
    Version history for model configurations (audit trail).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_config_versions (
            version INTEGER PRIMARY KEY,
            config_snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT,
            change_summary TEXT
        )
    """)
    
    # Index for version queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_config_version_created ON model_config_versions(created_at)")
    logger.debug("[Schema] Created model_config_versions table")


def create_usage_aggregates_table(conn):
    """
    Create usage_aggregates table.
    
    Pre-computed aggregates for dashboard queries.
    aggregate_type: 'daily', 'weekly', 'monthly', 'model', 'user', 'session'
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_aggregates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aggregate_type TEXT NOT NULL,
            aggregate_key TEXT NOT NULL,
            model_id TEXT,
            provider TEXT,
            user_id TEXT,
            total_requests INTEGER NOT NULL,
            total_prompt_tokens INTEGER NOT NULL,
            total_completion_tokens INTEGER NOT NULL,
            total_cost_usd REAL NOT NULL,
            avg_duration_ms REAL,
            created_at TEXT NOT NULL,
            UNIQUE(aggregate_type, aggregate_key, model_id, provider, user_id)
        )
    """)
    
    # Indexes for aggregate queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agg_type ON usage_aggregates(aggregate_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agg_key ON usage_aggregates(aggregate_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agg_model ON usage_aggregates(model_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agg_created ON usage_aggregates(created_at)")
    logger.debug("[Schema] Created usage_aggregates table")


def init_multi_model_schema():
    """
    Initialize all multi-model schema tables.
    
    This function is idempotent - safe to call multiple times.
    All tables use IF NOT EXISTS to prevent data loss.
    
    CRITICAL: This function acquires a lock to prevent concurrent schema changes.
    """
    with _schema_lock:
        conn = _get_conn()
        try:
            # Create all tables
            create_model_pricing_catalog_table(conn)
            create_token_usage_logs_table(conn)
            create_copilot_sessions_table(conn)
            create_model_config_versions_table(conn)
            create_usage_aggregates_table(conn)
            
            # Commit all changes
            conn.commit()
            
            # Verify tables exist
            tables = ['model_pricing_catalog', 'token_usage_logs', 'copilot_sessions', 
                      'model_config_versions', 'usage_aggregates']
            for table in tables:
                result = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()
                if not result:
                    raise RuntimeError(f"Failed to create table: {table}")
            
            logger.info(f"[Schema] Multi-model schema initialized successfully")
            
        except Exception as e:
            logger.error(f"[Schema] Failed to initialize schema: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


def verify_schema():
    """
    Verify that all required tables exist.
    
    Returns:
        dict: Table name -> exists (bool)
    """
    tables = ['model_pricing_catalog', 'token_usage_logs', 'copilot_sessions', 
              'model_config_versions', 'usage_aggregates']
    
    conn = _get_conn()
    try:
        result = {}
        for table in tables:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            result[table] = bool(row)
        return result
    finally:
        conn.close()


def get_table_stats():
    """
    Get row counts for all multi-model tables.
    
    Returns:
        dict: Table name -> row count
    """
    tables = ['model_pricing_catalog', 'token_usage_logs', 'copilot_sessions', 
              'model_config_versions', 'usage_aggregates']
    
    conn = _get_conn()
    try:
        stats = {}
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            stats[table] = row['cnt'] if row else 0
        return stats
    finally:
        conn.close()


if __name__ == "__main__":
    # Run schema initialization
    logging.basicConfig(level=logging.INFO)
    init_multi_model_schema()
    
    # Verify and print stats
    verification = verify_schema()
    stats = get_table_stats()
    
    print("\n=== Multi-Model Schema Verification ===")
    for table, exists in verification.items():
        status = "✅" if exists else "❌"
        count = stats.get(table, 0)
        print(f"{status} {table}: {count} rows")

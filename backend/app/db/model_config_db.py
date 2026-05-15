"""
Model Configuration DB Helpers

CRUD operations for model configuration management.
"""
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def _get_conn():
    """Get database connection with WAL mode for concurrent access."""
    import os
    _db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'database.db'
    )
    conn = sqlite3.connect(_db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Use WAL mode for better concurrency (matches main database.py)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def get_model_config(provider_key: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT value FROM admin_config WHERE key = ?", (provider_key,)
        ).fetchone()
        if not row:
            return None
        return json.loads(row['value'])
    except json.JSONDecodeError:
        return None
    finally:
        conn.close()


def set_model_config(provider_key: str, config: Dict[str, Any]) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO admin_config (key, value, updated_at) VALUES (?, ?, ?)",
            (provider_key, json.dumps(config), datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_all_model_configs() -> Dict[str, Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT key, value FROM admin_config WHERE key LIKE 'llm_%'"
        ).fetchall()
        
        result = {}
        for row in rows:
            try:
                result[row['key']] = json.loads(row['value'])
            except json.JSONDecodeError:
                continue
        return result
    finally:
        conn.close()


def get_model_by_id(provider_key: str, model_id: str) -> Optional[Dict[str, Any]]:
    config = get_model_config(provider_key)
    if not config or 'models' not in config:
        return None
    return config['models'].get(model_id)


def add_model_to_config(provider_key: str, model_id: str, model_config: Dict[str, Any]) -> bool:
    config = get_model_config(provider_key)
    if not config:
        config = {"models": {}, "default_model": None, "migration_version": 1}
    
    if 'models' not in config:
        config['models'] = {}
    
    config['models'][model_id] = model_config
    
    if not config.get('default_model'):
        config['default_model'] = model_id
    
    set_model_config(provider_key, config)
    return True


def update_model_in_config(provider_key: str, model_id: str, updates: Dict[str, Any]) -> bool:
    config = get_model_config(provider_key)
    if not config or 'models' not in config or model_id not in config['models']:
        return False
    
    config['models'][model_id].update(updates)
    set_model_config(provider_key, config)
    return True


def remove_model_from_config(provider_key: str, model_id: str) -> bool:
    config = get_model_config(provider_key)
    if not config or 'models' not in config or model_id not in config['models']:
        return False
    
    del config['models'][model_id]
    
    if config.get('default_model') == model_id:
        remaining = list(config['models'].keys())
        config['default_model'] = remaining[0] if remaining else None
    
    set_model_config(provider_key, config)
    return True


def set_default_model(provider_key: str, model_id: str) -> bool:
    config = get_model_config(provider_key)
    if not config or 'models' not in config or model_id not in config['models']:
        return False
    
    config['default_model'] = model_id
    set_model_config(provider_key, config)
    return True


def get_default_model(provider_key: str) -> Optional[str]:
    config = get_model_config(provider_key)
    if not config:
        return None
    return config.get('default_model')


def get_enabled_models(provider_key: str) -> List[str]:
    config = get_model_config(provider_key)
    if not config or 'models' not in config:
        return []
    
    return [
        model_id for model_id, model_config in config['models'].items()
        if model_config.get('enabled', True)
    ]


def save_config_version(config_snapshot: Dict[str, Any], created_by: str = None, change_summary: str = None) -> int:
    conn = _get_conn()
    try:
        cursor = conn.execute("""
            INSERT INTO model_config_versions (config_snapshot, created_at, created_by, change_summary)
            VALUES (?, ?, ?, ?)
        """, (json.dumps(config_snapshot), datetime.now().isoformat(), created_by, change_summary))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_config_version(version: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM model_config_versions WHERE version = ?", (version,)
        ).fetchone()
        if not row:
            return None
        return {
            "version": row['version'],
            "config_snapshot": json.loads(row['config_snapshot']),
            "created_at": row['created_at'],
            "created_by": row['created_by'],
            "change_summary": row['change_summary']
        }
    finally:
        conn.close()


def get_latest_config_version() -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM model_config_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {
            "version": row['version'],
            "config_snapshot": json.loads(row['config_snapshot']),
            "created_at": row['created_at'],
            "created_by": row['created_by'],
            "change_summary": row['change_summary']
        }
    finally:
        conn.close()


def list_config_versions(limit: int = 10) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT version, created_at, created_by, change_summary FROM model_config_versions ORDER BY version DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def init_model_config_table():
    pass

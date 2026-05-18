"""
LLM Config Migration: Single-Model -> Multi-Model

Migrates existing single-model LLM configs to the new nested multi-model schema.

Old format (admin_config key: "llm_openai"):
    {"api_key": "...", "base_url": "...", "model": "gpt-3.5-turbo"}

New format:
    {
        "models": {
            "gpt-3.5-turbo": {
                "api_key": "...",
                "base_url": "...",
                "context_length": 16385,
                "concurrency_limit": 10,
                "enabled": true
            }
        },
        "default_model": "gpt-3.5-turbo",
        "migration_version": 1
    }

CRITICAL: This migration is safe and preserves all existing data.
- Creates backup before migration
- Idempotent (safe to run multiple times)
- Preserves original configs
"""
import json
import logging
import sqlite3
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import shutil

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 1

DEFAULT_MODEL_CONFIGS = {
    "gpt-4o": {"context_length": 128000, "concurrency_limit": 10},
    "gpt-4o-mini": {"context_length": 128000, "concurrency_limit": 10},
    "gpt-4-turbo": {"context_length": 128000, "concurrency_limit": 10},
    "gpt-3.5-turbo": {"context_length": 16385, "concurrency_limit": 10},
    "claude-3-5-sonnet-20241022": {"context_length": 200000, "concurrency_limit": 5},
    "claude-3-opus-20240229": {"context_length": 200000, "concurrency_limit": 5},
    "claude-3-haiku-20240307": {"context_length": 200000, "concurrency_limit": 10},
    "deepseek-chat": {"context_length": 64000, "concurrency_limit": 10},
    "deepseek-reasoner": {"context_length": 64000, "concurrency_limit": 5},
    "qwen-plus": {"context_length": 128000, "concurrency_limit": 10},
    "qwen-turbo": {"context_length": 128000, "concurrency_limit": 10},
    "qwen-max": {"context_length": 32000, "concurrency_limit": 5},
    "moonshot-v1-8k": {"context_length": 8192, "concurrency_limit": 10},
    "moonshot-v1-32k": {"context_length": 32768, "concurrency_limit": 5},
    "moonshot-v1-128k": {"context_length": 131072, "concurrency_limit": 3},
    "abab6.5s-chat": {"context_length": 245000, "concurrency_limit": 5},
}


def _get_db_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
        'database.db'
    )


def _get_conn():
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def create_backup() -> Optional[str]:
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return None
    
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"[Migration] Created backup: {backup_path}")
    return backup_path


def get_old_config(conn, key: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT value FROM admin_config WHERE key = ?", (key,)
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row['value'])
    except json.JSONDecodeError:
        return None


def set_new_config(conn, key: str, value: Dict[str, Any]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO admin_config (key, value, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(value), datetime.now().isoformat())
    )
    conn.commit()


def migrate_single_to_multi(old_config: Dict[str, Any], provider_key: str) -> Dict[str, Any]:
    model_id = old_config.get('model', 'gpt-3.5-turbo')
    
    default_config = DEFAULT_MODEL_CONFIGS.get(model_id, {
        "context_length": 16385,
        "concurrency_limit": 10
    })
    
    model_config = {
        "api_key": old_config.get('api_key', ''),
        "base_url": old_config.get('base_url', ''),
        "context_length": default_config["context_length"],
        "concurrency_limit": default_config["concurrency_limit"],
        "enabled": True
    }
    
    if 'temperature' in old_config:
        model_config['temperature'] = old_config['temperature']
    if 'max_tokens' in old_config:
        model_config['max_tokens'] = old_config['max_tokens']
    
    new_config = {
        "models": {
            model_id: model_config
        },
        "default_model": model_id,
        "migration_version": MIGRATION_VERSION,
        "migrated_from": provider_key,
        "migrated_at": datetime.now().isoformat()
    }
    
    return new_config


def needs_migration(config: Dict[str, Any]) -> bool:
    if 'models' in config and isinstance(config.get('models'), dict):
        return False
    
    if 'migration_version' in config:
        return False
    
    return True


def migrate_llm_configs(dry_run: bool = False) -> Dict[str, Any]:
    result = {
        "success": True,
        "migrated": [],
        "skipped": [],
        "errors": [],
        "backup_path": None
    }
    
    provider_keys = [
        "llm_openai",
        "llm_anthropic",
        "llm_deepseek",
        "llm_qianwen",
        "llm_kimi",
        "llm_minimax",
        "llm_siliconflow",
        "llm_opencode"
    ]
    
    conn = _get_conn()
    try:
        if not dry_run:
            result["backup_path"] = create_backup()
        
        for key in provider_keys:
            old_config = get_old_config(conn, key)
            
            if not old_config:
                result["skipped"].append({"key": key, "reason": "not_found"})
                continue
            
            if not needs_migration(old_config):
                result["skipped"].append({"key": key, "reason": "already_migrated"})
                continue
            
            try:
                new_config = migrate_single_to_multi(old_config, key)
                
                if dry_run:
                    result["migrated"].append({
                        "key": key,
                        "old": old_config,
                        "new": new_config,
                        "dry_run": True
                    })
                else:
                    set_new_config(conn, key, new_config)
                    result["migrated"].append({
                        "key": key,
                        "model": new_config.get('default_model'),
                        "dry_run": False
                    })
                    
            except Exception as e:
                result["errors"].append({"key": key, "error": str(e)})
                result["success"] = False
        
        return result
        
    finally:
        conn.close()


def verify_migration() -> Dict[str, Any]:
    conn = _get_conn()
    try:
        provider_keys = [
            "llm_openai", "llm_anthropic", "llm_deepseek",
            "llm_qianwen", "llm_kimi", "llm_minimax",
            "llm_siliconflow", "llm_opencode"
        ]
        
        verification = {
            "all_migrated": True,
            "configs": {}
        }
        
        for key in provider_keys:
            config = get_old_config(conn, key)
            if not config:
                verification["configs"][key] = {"status": "not_found"}
                continue
            
            is_migrated = not needs_migration(config)
            verification["configs"][key] = {
                "status": "migrated" if is_migrated else "needs_migration",
                "model_count": len(config.get('models', {})),
                "default_model": config.get('default_model'),
                "migration_version": config.get('migration_version')
            }
            
            if not is_migrated:
                verification["all_migrated"] = False
        
        return verification
        
    finally:
        conn.close()


def run_migration_with_backup() -> Tuple[bool, str]:
    backup_path = create_backup()
    
    try:
        result = migrate_llm_configs(dry_run=False)
        
        if result["success"]:
            verification = verify_migration()
            if verification["all_migrated"]:
                return True, f"Migration successful. Backup: {backup_path}"
            else:
                return False, f"Migration incomplete. Backup: {backup_path}"
        else:
            return False, f"Migration failed with errors: {result['errors']}"
            
    except Exception as e:
        return False, f"Migration error: {str(e)}. Backup: {backup_path}"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate LLM configs to multi-model schema")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without changes")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.verify:
        verification = verify_migration()
        print("\n=== Migration Verification ===")
        for key, info in verification["configs"].items():
            status = "✅" if info["status"] == "migrated" else "❌"
            print(f"{status} {key}: {info['status']}")
            if info["status"] == "migrated":
                print(f"   Models: {info['model_count']}, Default: {info['default_model']}")
        print(f"\nAll migrated: {'✅' if verification['all_migrated'] else '❌'}")
        
    elif args.dry_run:
        result = migrate_llm_configs(dry_run=True)
        print("\n=== Dry Run Preview ===")
        for item in result["migrated"]:
            print(f"\n{item['key']}:")
            print(f"  Old: {json.dumps(item['old'], indent=2)}")
            print(f"  New: {json.dumps(item['new'], indent=2)}")
            
    else:
        success, message = run_migration_with_backup()
        print(f"\n{'✅' if success else '❌'} {message}")

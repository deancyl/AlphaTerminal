"""
Seed Model Pricing Catalog

Populates the model_pricing_catalog table with built-in pricing data for 20+ models.

Pricing sources (as of 2024-01):
- OpenAI: https://openai.com/api/pricing
- Anthropic: https://www.anthropic.com/pricing
- DeepSeek: https://platform.deepseek.com/api-docs/pricing
- Qianwen: https://help.aliyun.com/zh/dashscope/developer-reference/billing
- Kimi: https://platform.moonshot.cn/docs/pricing
- MiniMax: https://www.minimaxi.com/document/pricing
- SiliconFlow: https://siliconflow.cn/pricing

CRITICAL: Pricing data is approximate and should be updated regularly.
Admin can override these values through the admin interface.
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BUILTIN_MODELS = [
    # OpenAI Models
    {
        "model_id": "gpt-4o",
        "provider": "openai",
        "display_name": "GPT-4o",
        "input_cost_per_token": 2.5e-6,  # $2.50/1M tokens
        "output_cost_per_token": 1.0e-5,  # $10.00/1M tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "gpt-4", "multimodal": True})
    },
    {
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "display_name": "GPT-4o Mini",
        "input_cost_per_token": 1.5e-7,  # $0.15/1M tokens
        "output_cost_per_token": 6.0e-7,  # $0.60/1M tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "gpt-4", "multimodal": True})
    },
    {
        "model_id": "gpt-4-turbo",
        "provider": "openai",
        "display_name": "GPT-4 Turbo",
        "input_cost_per_token": 1.0e-5,  # $10.00/1M tokens
        "output_cost_per_token": 3.0e-5,  # $30.00/1M tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "gpt-4", "multimodal": True})
    },
    {
        "model_id": "gpt-3.5-turbo",
        "provider": "openai",
        "display_name": "GPT-3.5 Turbo",
        "input_cost_per_token": 5.0e-7,  # $0.50/1M tokens
        "output_cost_per_token": 1.5e-6,  # $1.50/1M tokens
        "context_length": 16385,
        "metadata": json.dumps({"family": "gpt-3.5"})
    },
    # Anthropic Models
    {
        "model_id": "claude-3-5-sonnet-20241022",
        "provider": "anthropic",
        "display_name": "Claude 3.5 Sonnet",
        "input_cost_per_token": 3.0e-6,  # $3.00/1M tokens
        "output_cost_per_token": 1.5e-5,  # $15.00/1M tokens
        "context_length": 200000,
        "metadata": json.dumps({"family": "claude-3.5", "multimodal": True})
    },
    {
        "model_id": "claude-3-opus-20240229",
        "provider": "anthropic",
        "display_name": "Claude 3 Opus",
        "input_cost_per_token": 1.5e-5,  # $15.00/1M tokens
        "output_cost_per_token": 7.5e-5,  # $75.00/1M tokens
        "context_length": 200000,
        "metadata": json.dumps({"family": "claude-3", "multimodal": True})
    },
    {
        "model_id": "claude-3-haiku-20240307",
        "provider": "anthropic",
        "display_name": "Claude 3 Haiku",
        "input_cost_per_token": 2.5e-7,  # $0.25/1M tokens
        "output_cost_per_token": 1.25e-6,  # $1.25/1M tokens
        "context_length": 200000,
        "metadata": json.dumps({"family": "claude-3", "multimodal": True})
    },
    # DeepSeek Models
    {
        "model_id": "deepseek-chat",
        "provider": "deepseek",
        "display_name": "DeepSeek Chat",
        "input_cost_per_token": 1.0e-7,  # $0.1/1M tokens (cache miss)
        "output_cost_per_token": 2.0e-7,  # $0.2/1M tokens
        "context_length": 64000,
        "metadata": json.dumps({"family": "deepseek", "cache_hit_discount": 0.1})
    },
    {
        "model_id": "deepseek-reasoner",
        "provider": "deepseek",
        "display_name": "DeepSeek Reasoner (R1)",
        "input_cost_per_token": 5.5e-7,  # $0.55/1M tokens (cache miss)
        "output_cost_per_token": 2.19e-6,  # $2.19/1M tokens
        "context_length": 64000,
        "metadata": json.dumps({"family": "deepseek", "reasoning": True, "cache_hit_discount": 0.1})
    },
    # Qianwen Models
    {
        "model_id": "qwen-plus",
        "provider": "qianwen",
        "display_name": "通义千问 Plus",
        "input_cost_per_token": 8.0e-7,  # ¥0.004/1K tokens ≈ $0.0008/1M
        "output_cost_per_token": 2.0e-6,  # ¥0.012/1K tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "qwen", "currency": "CNY"})
    },
    {
        "model_id": "qwen-turbo",
        "provider": "qianwen",
        "display_name": "通义千问 Turbo",
        "input_cost_per_token": 3.0e-7,  # ¥0.002/1K tokens
        "output_cost_per_token": 6.0e-7,  # ¥0.006/1K tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "qwen", "currency": "CNY"})
    },
    {
        "model_id": "qwen-max",
        "provider": "qianwen",
        "display_name": "通义千问 Max",
        "input_cost_per_token": 4.0e-5,  # ¥0.2/1K tokens
        "output_cost_per_token": 1.2e-4,  # ¥0.6/1K tokens
        "context_length": 32000,
        "metadata": json.dumps({"family": "qwen", "currency": "CNY"})
    },
    # Kimi (Moonshot) Models
    {
        "model_id": "moonshot-v1-8k",
        "provider": "kimi",
        "display_name": "Kimi V1 8K",
        "input_cost_per_token": 1.2e-5,  # ¥0.012/1K tokens
        "output_cost_per_token": 1.2e-5,  # ¥0.012/1K tokens
        "context_length": 8192,
        "metadata": json.dumps({"family": "moonshot", "currency": "CNY"})
    },
    {
        "model_id": "moonshot-v1-32k",
        "provider": "kimi",
        "display_name": "Kimi V1 32K",
        "input_cost_per_token": 2.4e-5,  # ¥0.024/1K tokens
        "output_cost_per_token": 2.4e-5,  # ¥0.024/1K tokens
        "context_length": 32768,
        "metadata": json.dumps({"family": "moonshot", "currency": "CNY"})
    },
    {
        "model_id": "moonshot-v1-128k",
        "provider": "kimi",
        "display_name": "Kimi V1 128K",
        "input_cost_per_token": 1.4e-4,  # ¥0.14/1K tokens
        "output_cost_per_token": 1.4e-4,  # ¥0.14/1K tokens
        "context_length": 131072,
        "metadata": json.dumps({"family": "moonshot", "currency": "CNY"})
    },
    # MiniMax Models
    {
        "model_id": "abab6.5s-chat",
        "provider": "minimax",
        "display_name": "ABAB 6.5S Chat",
        "input_cost_per_token": 1.0e-6,  # $1.00/1M tokens (approx)
        "output_cost_per_token": 1.0e-6,  # $1.00/1M tokens
        "context_length": 245000,
        "metadata": json.dumps({"family": "abab"})
    },
    # SiliconFlow Models
    {
        "model_id": "Qwen/Qwen2.5-72B-Instruct",
        "provider": "siliconflow",
        "display_name": "Qwen2.5 72B Instruct",
        "input_cost_per_token": 4.0e-7,  # ¥0.4/1M tokens
        "output_cost_per_token": 4.0e-7,  # ¥0.4/1M tokens
        "context_length": 32768,
        "metadata": json.dumps({"family": "qwen2.5", "hosted_by": "siliconflow"})
    },
    {
        "model_id": "deepseek-ai/DeepSeek-V2.5",
        "provider": "siliconflow",
        "display_name": "DeepSeek V2.5",
        "input_cost_per_token": 1.4e-6,  # ¥1.4/1M tokens
        "output_cost_per_token": 2.8e-6,  # ¥2.8/1M tokens
        "context_length": 32768,
        "metadata": json.dumps({"family": "deepseek", "hosted_by": "siliconflow"})
    },
    # OpenCode Models
    {
        "model_id": "opencode-7b",
        "provider": "opencode",
        "display_name": "OpenCode 7B",
        "input_cost_per_token": 0.0,  # Free / Local
        "output_cost_per_token": 0.0,
        "context_length": 32768,
        "metadata": json.dumps({"family": "opencode", "local": True})
    },
    {
        "model_id": "opencode-13b",
        "provider": "opencode",
        "display_name": "OpenCode 13B",
        "input_cost_per_token": 0.0,  # Free / Local
        "output_cost_per_token": 0.0,
        "context_length": 32768,
        "metadata": json.dumps({"family": "opencode", "local": True})
    },
    # Additional Models
    {
        "model_id": "glm-4",
        "provider": "zhipu",
        "display_name": "GLM-4",
        "input_cost_per_token": 1.0e-4,  # ¥0.1/1K tokens
        "output_cost_per_token": 1.0e-4,  # ¥0.1/1K tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "glm", "currency": "CNY"})
    },
    {
        "model_id": "glm-4-flash",
        "provider": "zhipu",
        "display_name": "GLM-4 Flash",
        "input_cost_per_token": 1.0e-7,  # ¥0.0001/1K tokens
        "output_cost_per_token": 1.0e-7,  # ¥0.0001/1K tokens
        "context_length": 128000,
        "metadata": json.dumps({"family": "glm", "currency": "CNY"})
    },
    {
        "model_id": "yi-lightning",
        "provider": "yi",
        "display_name": "Yi Lightning",
        "input_cost_per_token": 5.0e-7,  # $0.5/1M tokens
        "output_cost_per_token": 5.0e-7,  # $0.5/1M tokens
        "context_length": 16384,
        "metadata": json.dumps({"family": "yi"})
    },
]


def _get_conn():
    import os
    _db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'database.db'
    )
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def seed_pricing_catalog(models: List[Dict[str, Any]] = None, force: bool = False) -> Dict[str, int]:
    if models is None:
        models = BUILTIN_MODELS
    
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()
        inserted = 0
        updated = 0
        skipped = 0
        
        for model in models:
            existing = conn.execute(
                "SELECT model_id FROM model_pricing_catalog WHERE model_id = ?",
                (model["model_id"],)
            ).fetchone()
            
            if existing and not force:
                skipped += 1
                continue
            
            if existing and force:
                conn.execute("""
                    UPDATE model_pricing_catalog 
                    SET provider = ?, display_name = ?, input_cost_per_token = ?,
                        output_cost_per_token = ?, context_length = ?, metadata = ?,
                        updated_at = ?
                    WHERE model_id = ?
                """, (
                    model["provider"], model["display_name"], model["input_cost_per_token"],
                    model["output_cost_per_token"], model["context_length"], model.get("metadata"),
                    now, model["model_id"]
                ))
                updated += 1
            else:
                conn.execute("""
                    INSERT INTO model_pricing_catalog 
                    (model_id, provider, display_name, input_cost_per_token, output_cost_per_token,
                     context_length, is_builtin, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    model["model_id"], model["provider"], model["display_name"],
                    model["input_cost_per_token"], model["output_cost_per_token"],
                    model["context_length"], model.get("metadata"), now, now
                ))
                inserted += 1
        
        conn.commit()
        
        logger.info(f"[Seed] Pricing catalog: {inserted} inserted, {updated} updated, {skipped} skipped")
        
        return {"inserted": inserted, "updated": updated, "skipped": skipped}
        
    finally:
        conn.close()


def get_all_pricing() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT model_id, provider, display_name, input_cost_per_token, 
                   output_cost_per_token, context_length, is_builtin, metadata
            FROM model_pricing_catalog
            ORDER BY provider, model_id
        """).fetchall()
        
        result = []
        for row in rows:
            result.append({
                "model_id": row["model_id"],
                "provider": row["provider"],
                "display_name": row["display_name"],
                "input_cost_per_token": row["input_cost_per_token"],
                "output_cost_per_token": row["output_cost_per_token"],
                "context_length": row["context_length"],
                "is_builtin": bool(row["is_builtin"]),
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None
            })
        return result
    finally:
        conn.close()


def get_pricing_by_model(model_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM model_pricing_catalog WHERE model_id = ?",
            (model_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return {
            "model_id": row["model_id"],
            "provider": row["provider"],
            "display_name": row["display_name"],
            "input_cost_per_token": row["input_cost_per_token"],
            "output_cost_per_token": row["output_cost_per_token"],
            "context_length": row["context_length"],
            "is_builtin": bool(row["is_builtin"]),
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None
        }
    finally:
        conn.close()


def calculate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    pricing = get_pricing_by_model(model_id)
    if not pricing:
        return None
    
    input_cost = prompt_tokens * pricing["input_cost_per_token"]
    output_cost = completion_tokens * pricing["output_cost_per_token"]
    return input_cost + output_cost


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed model pricing catalog")
    parser.add_argument("--force", action="store_true", help="Force update existing entries")
    parser.add_argument("--list", action="store_true", help="List all pricing entries")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.list:
        pricing = get_all_pricing()
        print(f"\n=== Pricing Catalog ({len(pricing)} models) ===")
        for p in pricing:
            builtin = "📦" if p["is_builtin"] else "⚙️"
            print(f"{builtin} {p['model_id']}: ${p['input_cost_per_token']*1e6:.2f}/1M in, ${p['output_cost_per_token']*1e6:.2f}/1M out")
    else:
        result = seed_pricing_catalog(force=args.force)
        print(f"\n✅ Seeded pricing catalog: {result['inserted']} inserted, {result['updated']} updated, {result['skipped']} skipped")

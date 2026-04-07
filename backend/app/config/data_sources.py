"""
数据源统一注册表 (Data Source Registry) - Phase 8
────────────────────────────────────────────────────────────────────────────
用途：集中管理所有外部数据源，支持一键切换故障接口。
结构：domestic / foreign → 资产板块 → 具体标的 → (接口函数名, 参数, 数据路径, 超时秒数)
────────────────────────────────────────────────────────────────────────────
"""

# ── 国内 ─────────────────────────────────────────────────────────────────────
DOMESTIC = {
    "stock": {
        # A股实时指数（上证/沪深300/深证/创业板）→ Sina s_ 前缀格式
        "china_indices": {
            "source":    "sina_hq",
            "symbols":   ["s_sh000001", "s_sh000300", "s_sz399001", "s_sz399006"],
            "fields":    ["name", "current", "prev_close", "open", "high", "low"],
            "parse_fn":  "_parse_sina_index",   # 内部函数
            "parser_key":"change_pct = (current - prev_close) / prev_close * 100",
            "timeout":   10,
            "cache_ttl": 60,    # 1 分钟
        },
        # 个股实时 → Sina 标准格式（name,price,change,change_pct,volume,turnover）
        "stocks": {
            "source":    "sina_hq",
            "parse_fn":  "_parse_sina_hq",
            "timeout":   10,
            "cache_ttl": 30,
        },
        # 板块情绪 → EastMoney
        "sectors": {
            "source":    "ak.macro_china_industry_price_chg",
            "ak_fn":     "ak.macro_china_industry_price_chg",
            "timeout":   8,
            "cache_ttl": 300,
            "fallback":  "MOCK_STATIC_SECTORS",
        },
        # 全球指数（恒生/道琼斯/纳斯达克/标普）→ 腾讯 qt
        "global_indices": {
            "source":    "tencent_qt",
            "symbols":   ["hkHSI", "usDJI", "usIXIC", "usSPX"],
            "timeout":   8,
            "cache_ttl": 60,
        },
    },
    "bond": {
        # 国债收益率曲线 → 中债（akshare）
        "yield_curve": {
            "source":    "ak.bond_china_yield",
            "ak_fn":     "ak.bond_china_yield",
            "timeout":   10,
            "cache_ttl": 300,
            "fallback":  "MOCK_2021_YIELD_CURVE",
        },
        # 活跃债券列表 → Mock（无可靠免费接口）
        "active_bonds": {
            "source":    "mock",
            "data":      "INLINE_MOCK_BONDS",
            "cache_ttl": 300,
        },
    },
    "futures": {
        # 股指期货主力（IF/IC/IM）→ Mock（国内期货实名接口不稳定）
        "index_futures": {
            "source":    "mock",
            "data":      "INLINE_MOCK_INDEX_FUTURES",
            "cache_ttl": 180,
        },
        # 大宗商品期货实时 → 腾讯 qt
        "commodities": {
            "source":    "tencent_qt",
            "symbols":   ["RB0","HC0","SA0","LC0","I0","JM0","J0","SC0","FU0","TA0","MA0","V0","UR0","EG0","PP0"],
            "timeout":   8,
            "cache_ttl": 180,
        },
    },
}

# ── 海外 ─────────────────────────────────────────────────────────────────────
FOREIGN = {
    "macro": {
        # WTI 原油 → Sina hf_CL
        "wti_oil": {
            "source":    "sina_hq_hf",
            "symbol":    "hf_CL",
            "price_fld": 0,    # f[0] = 当前价 USD/桶
            "chg_fld":   32,   # f[32] = 涨跌幅%
            "timeout":   8,
            "cache_ttl": 600,
        },
        # 黄金 → Sina hf_GC（SGE 上海金，RMB/oz）
        "gold": {
            "source":    "sina_hq_hf",
            "symbol":    "hf_GC",
            "price_fld": 0,
            "chg_fld":   32,
            "timeout":   8,
            "cache_ttl": 600,
        },
        # 美元/离岸人民币 → Sina CNYUSD
        "usd_cny": {
            "source":    "sina_hq_cnyusd",
            "symbol":    "CNYUSD",
            "price_fld": 1,    # f[1] = 中行汇买价 USD per CNY
            "parse_fn":  "1 / price",
            "timeout":   8,
            "cache_ttl": 600,
        },
        # 恒指波幅 VHSI → 腾讯 qt（~分隔符）
        "vhsi": {
            "source":    "tencent_qt_tilde",
            "symbol":    "hkVHSI",
            "price_fld": 3,    # f[3] = 当前 VHSI
            "chg_fld":   32,  # f[32] = 涨跌幅%
            "timeout":   8,
            "cache_ttl": 600,
        },
    },
    "indexes": {
        # 美股期指 / VIX → 待接入
        "sp500":  {"source": "ak.stock_us_spot_em", "timeout": 8,  "cache_ttl": 60},
        "vix":    {"source": "tencent_qt_hkVHSI",   "timeout": 8,  "cache_ttl": 600},
    },
}

# ── 统一注册表 ────────────────────────────────────────────────────────────────
DATA_SOURCES = {
    "domestic": DOMESTIC,
    "foreign":  FOREIGN,
}

# ── Mock 静态数据（降级兜底用）───────────────────────────────────────────────
MOCK_SECTORS = [
    {"name": "银行",    "change_pct": -0.21},
    {"name": "证券",    "change_pct": +1.34},
    {"name": "白酒",    "change_pct": -0.58},
    {"name": "新能源",  "change_pct": +2.17},
    {"name": "医药",    "change_pct": +0.83},
    {"name": "半导体",  "change_pct": +1.92},
    {"name": "房地产",  "change_pct": -1.05},
    {"name": "军工",    "change_pct": +0.44},
]

MOCK_2021_YIELD_CURVE = {
    "3月": 2.0316, "6月": 2.1355, "1年": 2.4525,
    "3年": 2.7645, "5年": 2.9373, "7年": 3.1112,
    "10年": 3.1185, "30年": 3.7156,
}

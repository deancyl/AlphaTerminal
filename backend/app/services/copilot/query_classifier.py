"""
Query Classifier Service for AlphaTerminal Copilot

Classifies user queries into predefined types and extracts relevant entities
(stock symbols, sectors, macro indicators) using regex patterns.

Key Features:
- Singleton pattern with thread-safe access
- Pure regex-based classification (no HTTP calls)
- Symbol extraction from Chinese names and stock codes
- Confidence scoring based on pattern matches
"""
import logging
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Query classification types"""
    COMPANY_DEEP_DIVE = "company_deep_dive"      # "分析茅台"
    EVENT_DRIVEN = "event_driven"                 # "茅台涨价影响"
    PORTFOLIO_RISK = "portfolio_risk"             # "检查我的持仓风险"
    MACRO_IMPACT = "macro_impact"                 # "CPI对消费板块影响"
    SECTOR_COMPARISON = "sector_comparison"       # "茅台 vs 五粮液"
    QUICK_QA = "quick_qa"                         # "茅台市盈率是多少"


@dataclass
class ClassificationResult:
    """Result of query classification"""
    query_type: QueryType
    symbols: List[str] = field(default_factory=list)
    sector: Optional[str] = None
    macro_indicators: List[str] = field(default_factory=list)
    confidence: float = 0.0
    original_query: str = ""


# Classification patterns
COMPANY_PATTERNS = [
    r"分析(.+)",
    r"(.+)深度",
    r"(.+)研报",
    r"(.+)基本面",
    r"(.+)财务",
    r"(.+)估值",
]

COMPARISON_PATTERNS = [
    r"(.+?)\s*vs\.?\s*(.+)",
    r"(.+?)对比(.+)",
    r"(.+?)和(.+?)比较",
    r"(.+?)与(.+?)对比",
]

MACRO_PATTERNS = [
    r"(GDP|CPI|PPI|PMI|M2).*(影响|对)",
    r"宏观.*分析",
    r"经济.*影响",
    r"政策.*影响",
]

PORTFOLIO_PATTERNS = [
    r"我的持仓",
    r"组合.*风险",
    r"检查.*仓位",
    r"持仓.*分析",
    r"账户.*风险",
]

EVENT_PATTERNS = [
    r"(.+?)(涨价|降价|并购|重组|业绩|分红|回购|增持|减持)",
    r"(.+?)影响",
    r"(.+?)事件",
]

# Stock name to symbol mapping (common stocks)
STOCK_NAME_MAP = {
    "茅台": "600519",
    "贵州茅台": "600519",
    "平安": "601318",
    "中国平安": "601318",
    "招商银行": "600036",
    "招行": "600036",
    "五粮液": "000858",
    "宁德时代": "300750",
    "宁德": "300750",
    "比亚迪": "002594",
    "比亚迪a": "002594",
    "腾讯": "00700",
    "腾讯控股": "00700",
    "阿里巴巴": "09988",
    "阿里": "09988",
    "美团": "03690",
    "京东": "09618",
    "小米": "01810",
    "百度": "09888",
    "网易": "09999",
    "海康威视": "002415",
    "海康": "002415",
    "隆基绿能": "601012",
    "隆基": "601012",
    "通威股份": "600438",
    "通威": "600438",
    "阳光电源": "300274",
    "阳光": "300274",
    "中芯国际": "688981",
    "中芯": "688981",
    "药明康德": "603259",
    "药明": "603259",
    "恒瑞医药": "600276",
    "恒瑞": "600276",
    "迈瑞医疗": "300760",
    "迈瑞": "300760",
    "爱尔眼科": "300015",
    "爱尔": "300015",
    "智飞生物": "300122",
    "智飞": "300122",
    "万华化学": "600309",
    "万华": "600309",
    "中国中免": "601888",
    "中免": "601888",
    "格力电器": "000651",
    "格力": "000651",
    "美的集团": "000333",
    "美的": "000333",
    "海尔智家": "600690",
    "海尔": "600690",
    "伊利股份": "600887",
    "伊利": "600887",
    "泸州老窖": "000568",
    "泸州老窖": "000568",
    "洋河股份": "002304",
    "洋河": "002304",
    "山西汾酒": "600809",
    "汾酒": "600809",
    "中信证券": "600030",
    "中信": "600030",
    "东方财富": "300059",
    "东财": "300059",
    "平安银行": "000001",
    "平银": "000001",
}

# Sector name mapping
SECTOR_MAP = {
    "白酒": "白酒",
    "银行": "银行",
    "科技": "科技",
    "半导体": "半导体",
    "芯片": "半导体",
    "新能源": "新能源",
    "光伏": "光伏",
    "锂电": "锂电",
    "医药": "医药",
    "医疗": "医药",
    "消费": "消费",
    "食品饮料": "食品饮料",
    "家电": "家电",
    "汽车": "汽车",
    "地产": "地产",
    "房地产": "地产",
    "保险": "保险",
    "券商": "券商",
    "证券": "券商",
    "军工": "军工",
    "化工": "化工",
    "有色": "有色金属",
    "有色金属": "有色金属",
    "煤炭": "煤炭",
    "钢铁": "钢铁",
    "电力": "电力",
    "公用事业": "公用事业",
    "通信": "通信",
    "传媒": "传媒",
    "教育": "教育",
    "旅游": "旅游",
    "酒店": "酒店",
    "零售": "零售",
}

# Macro indicator keywords
MACRO_KEYWORDS = ["GDP", "CPI", "PPI", "PMI", "M2", "M1", "M0", "社融", "信贷", "利率", "汇率", "通胀", "通缩"]

# Quick QA patterns (questions about specific metrics)
QUICK_QA_PATTERNS = [
    r"(.+?)(市盈率|市净率|估值|股价|市值|营收|利润|ROE|ROA|PE|PB)是?(多少|几多)",
    r"(什么是|解释|说明).{0,5}(市盈率|市净率|估值|股价)",
    r"(.+?)(分红|股息|派息).*(多少|几多|什么时候)",
]


class QueryClassifier:
    """
    Query classifier using regex patterns.
    
    Classifies user queries into predefined types and extracts
    stock symbols, sectors, and macro indicators.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        logger.info("[QueryClassifier] Initialized")
    
    def classify(self, query: str) -> ClassificationResult:
        """
        Classify a user query.
        
        Args:
            query: User's natural language query
            
        Returns:
            ClassificationResult with query type and extracted entities
        """
        if not query or not query.strip():
            return ClassificationResult(
                query_type=QueryType.QUICK_QA,
                confidence=0.0,
                original_query=query or ""
            )
        
        query = query.strip()
        
        # Extract entities first
        symbols = self._extract_symbols(query)
        sector = self._extract_sector(query)
        macro_indicators = self._extract_macro_indicators(query)
        
        # Classify query type
        query_type, confidence = self._classify_type(query, symbols, sector, macro_indicators)
        
        result = ClassificationResult(
            query_type=query_type,
            symbols=symbols,
            sector=sector,
            macro_indicators=macro_indicators,
            confidence=confidence,
            original_query=query
        )
        
        logger.debug(f"[QueryClassifier] Classified '{query}' as {query_type.value} (confidence: {confidence:.2f})")
        
        return result
    
    def _classify_type(
        self, 
        query: str, 
        symbols: List[str], 
        sector: Optional[str],
        macro_indicators: List[str]
    ) -> Tuple[QueryType, float]:
        """
        Determine query type based on patterns and extracted entities.
        
        Returns:
            Tuple of (QueryType, confidence)
        """
        scores = {
            QueryType.COMPANY_DEEP_DIVE: 0.0,
            QueryType.EVENT_DRIVEN: 0.0,
            QueryType.PORTFOLIO_RISK: 0.0,
            QueryType.MACRO_IMPACT: 0.0,
            QueryType.SECTOR_COMPARISON: 0.0,
            QueryType.QUICK_QA: 0.1,  # Base score for default
        }
        
        # Check portfolio patterns (highest priority)
        for pattern in PORTFOLIO_PATTERNS:
            if re.search(pattern, query):
                scores[QueryType.PORTFOLIO_RISK] += 0.8
                break
        
        # Check comparison patterns
        for pattern in COMPARISON_PATTERNS:
            match = re.search(pattern, query)
            if match:
                scores[QueryType.SECTOR_COMPARISON] += 0.9
                break
        
        # Check quick QA patterns (specific metric questions)
        for pattern in QUICK_QA_PATTERNS:
            if re.search(pattern, query):
                scores[QueryType.QUICK_QA] += 0.85
                break
        
        # Check macro patterns
        for pattern in MACRO_PATTERNS:
            if re.search(pattern, query):
                scores[QueryType.MACRO_IMPACT] += 0.7
                break
        
        # Check if macro indicators mentioned
        if macro_indicators:
            scores[QueryType.MACRO_IMPACT] += 0.3
        
        # Check event patterns
        for pattern in EVENT_PATTERNS:
            match = re.search(pattern, query)
            if match:
                scores[QueryType.EVENT_DRIVEN] += 0.7
                break
        
        # Check company deep dive patterns
        for pattern in COMPANY_PATTERNS:
            match = re.search(pattern, query)
            if match:
                scores[QueryType.COMPANY_DEEP_DIVE] += 0.6
                break
        
        # Boost company deep dive if symbols found
        if symbols and len(symbols) == 1:
            scores[QueryType.COMPANY_DEEP_DIVE] += 0.2
        
        # Boost comparison if multiple symbols found
        if symbols and len(symbols) >= 2:
            scores[QueryType.SECTOR_COMPARISON] += 0.3
        
        # Determine best match
        best_type = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_type]
        
        # Cap confidence at 1.0
        confidence = min(best_score, 1.0)
        
        return best_type, confidence
    
    def _extract_symbols(self, query: str) -> List[str]:
        """
        Extract stock symbols from query.
        
        Matches:
        - Chinese stock names (茅台, 平安, etc.)
        - Stock codes (600519, 000001, etc.)
        - Prefixed codes (sh600519, sz000001)
        
        Returns:
            List of normalized symbols (6-digit codes)
        """
        symbols = []
        
        # Check Chinese stock names
        for name, code in STOCK_NAME_MAP.items():
            if name in query:
                if code not in symbols:
                    symbols.append(code)
        
        # Check prefixed codes (sh600519, sz000001)
        prefixed_pattern = r"[sS][hHzZ](\d{6})"
        for match in re.finditer(prefixed_pattern, query):
            code = match.group(1)
            if code not in symbols:
                symbols.append(code)
        
        # Check plain stock codes (6 digits)
        # Must be preceded/followed by non-digit to avoid false matches
        code_pattern = r"(?<![0-9])(\d{6})(?![0-9])"
        for match in re.finditer(code_pattern, query):
            code = match.group(1)
            # Validate: A-share codes start with 0, 3, 6
            if code[0] in "036" and code not in symbols:
                symbols.append(code)
        
        return symbols
    
    def _extract_sector(self, query: str) -> Optional[str]:
        """
        Extract sector name from query.
        
        Returns:
            Sector name or None
        """
        for keyword, sector in SECTOR_MAP.items():
            if keyword in query:
                return sector
        return None
    
    def _extract_macro_indicators(self, query: str) -> List[str]:
        """
        Extract macro economic indicators from query.
        
        Returns:
            List of indicator names
        """
        indicators = []
        for keyword in MACRO_KEYWORDS:
            if keyword in query.upper() or keyword in query:
                if keyword not in indicators:
                    indicators.append(keyword)
        return indicators


# Singleton instance
_classifier_instance: Optional[QueryClassifier] = None
_classifier_lock = threading.Lock()


def get_query_classifier() -> QueryClassifier:
    """Get singleton QueryClassifier instance"""
    global _classifier_instance
    if _classifier_instance is None:
        with _classifier_lock:
            if _classifier_instance is None:
                _classifier_instance = QueryClassifier()
    return _classifier_instance

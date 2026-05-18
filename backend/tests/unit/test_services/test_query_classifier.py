"""
Tests for QueryClassifier service
"""
import pytest
from app.services.copilot.query_classifier import (
    get_query_classifier,
    QueryType,
    ClassificationResult,
)


class TestQueryClassifier:
    """Tests for QueryClassifier"""
    
    @pytest.fixture
    def classifier(self):
        return get_query_classifier()
    
    def test_singleton_pattern(self, classifier):
        """Test that get_query_classifier returns singleton"""
        classifier2 = get_query_classifier()
        assert classifier is classifier2
    
    def test_company_deep_dive(self, classifier):
        """Test company deep dive classification"""
        result = classifier.classify("分析茅台")
        assert result.query_type == QueryType.COMPANY_DEEP_DIVE
        assert "600519" in result.symbols
        assert result.confidence > 0
    
    def test_company_deep_dive_with_code(self, classifier):
        """Test company deep dive with stock code"""
        result = classifier.classify("分析600519")
        assert result.query_type == QueryType.COMPANY_DEEP_DIVE
        assert "600519" in result.symbols
    
    def test_sector_comparison(self, classifier):
        """Test sector comparison classification"""
        result = classifier.classify("茅台 vs 五粮液")
        assert result.query_type == QueryType.SECTOR_COMPARISON
        assert len(result.symbols) >= 2
    
    def test_sector_comparison_chinese(self, classifier):
        """Test sector comparison with Chinese separator"""
        result = classifier.classify("茅台对比五粮液")
        assert result.query_type == QueryType.SECTOR_COMPARISON
    
    def test_macro_impact(self, classifier):
        """Test macro impact classification"""
        result = classifier.classify("CPI对消费板块影响")
        assert result.query_type == QueryType.MACRO_IMPACT
        assert "CPI" in result.macro_indicators
    
    def test_portfolio_risk(self, classifier):
        """Test portfolio risk classification"""
        result = classifier.classify("检查我的持仓风险")
        assert result.query_type == QueryType.PORTFOLIO_RISK
    
    def test_event_driven(self, classifier):
        """Test event driven classification"""
        result = classifier.classify("茅台涨价影响")
        assert result.query_type == QueryType.EVENT_DRIVEN
        assert "600519" in result.symbols
    
    def test_quick_qa(self, classifier):
        """Test quick QA classification"""
        result = classifier.classify("茅台市盈率是多少")
        assert result.query_type == QueryType.QUICK_QA
    
    def test_symbol_extraction_chinese(self, classifier):
        """Test symbol extraction from Chinese name"""
        result = classifier.classify("分析平安银行")
        assert "000001" in result.symbols or "平安银行" in str(result.symbols)
    
    def test_symbol_extraction_prefixed(self, classifier):
        """Test symbol extraction from prefixed code"""
        result = classifier.classify("分析sh600519")
        assert "600519" in result.symbols
    
    def test_sector_extraction(self, classifier):
        """Test sector extraction"""
        result = classifier.classify("白酒板块怎么样")
        assert result.sector is not None or len(result.symbols) > 0
    
    def test_confidence_score(self, classifier):
        """Test confidence score calculation"""
        result = classifier.classify("分析茅台的基本面")
        assert 0 <= result.confidence <= 1
    
    def test_empty_query(self, classifier):
        """Test empty query handling"""
        result = classifier.classify("")
        assert result.query_type == QueryType.QUICK_QA
        assert result.confidence >= 0
    
    def test_unknown_query(self, classifier):
        """Test unknown query defaults to quick_qa"""
        result = classifier.classify("今天天气怎么样")
        assert result.query_type == QueryType.QUICK_QA

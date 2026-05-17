"""
Tests for ContextAssembler service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.copilot.context_assembler import (
    get_context_assembler,
    ContextAssembler,
    ContextConfig,
    AssemblyResult,
    CONTEXT_CONFIGS,
)
from app.services.copilot.query_classifier import QueryType, ClassificationResult


class TestContextAssembler:
    """Tests for ContextAssembler"""
    
    @pytest.fixture
    def assembler(self):
        """Get ContextAssembler instance"""
        return get_context_assembler()
    
    def test_singleton_pattern(self, assembler):
        """Test that get_context_assembler returns singleton"""
        assembler2 = get_context_assembler()
        assert assembler is assembler2
    
    def test_context_configs_exist(self):
        """Test that all query types have context configs"""
        for query_type in QueryType:
            assert query_type in CONTEXT_CONFIGS
            config = CONTEXT_CONFIGS[query_type]
            assert isinstance(config, ContextConfig)
    
    def test_company_deep_dive_config(self):
        """Test company deep dive has comprehensive config"""
        config = CONTEXT_CONFIGS[QueryType.COMPANY_DEEP_DIVE]
        assert len(config.f9_tabs) >= 5
        assert "financial" in config.f9_tabs
        assert config.news_days > 0
        assert config.peers is True
    
    def test_event_driven_config(self):
        """Test event driven has news focus"""
        config = CONTEXT_CONFIGS[QueryType.EVENT_DRIVEN]
        assert config.news_days >= 30  # More news for events
    
    def test_portfolio_risk_config(self):
        """Test portfolio risk includes portfolio data"""
        config = CONTEXT_CONFIGS[QueryType.PORTFOLIO_RISK]
        assert config.portfolio is True
        assert len(config.macro_indicators) > 0
    
    def test_macro_impact_config(self):
        """Test macro impact has macro indicators"""
        config = CONTEXT_CONFIGS[QueryType.MACRO_IMPACT]
        assert len(config.macro_indicators) >= 3
        assert "gdp" in config.macro_indicators
    
    def test_sector_comparison_config(self):
        """Test sector comparison has financial data"""
        config = CONTEXT_CONFIGS[QueryType.SECTOR_COMPARISON]
        assert "financial" in config.f9_tabs
        assert "forecast" in config.f9_tabs
    
    def test_quick_qa_config(self):
        """Test quick QA has minimal config"""
        config = CONTEXT_CONFIGS[QueryType.QUICK_QA]
        assert len(config.f9_tabs) <= 2
        assert config.news_days <= 7
    
    def test_estimate_tokens_empty(self, assembler):
        """Test token estimation for empty text"""
        assert assembler._estimate_tokens("") == 0
    
    def test_estimate_tokens_chinese(self, assembler):
        """Test token estimation for Chinese text"""
        text = "分析茅台的基本面"
        tokens = assembler._estimate_tokens(text)
        # 7 Chinese chars ≈ 7 tokens
        assert tokens >= 7
    
    def test_estimate_tokens_mixed(self, assembler):
        """Test token estimation for mixed text"""
        text = "茅台 PE: 35.5"
        tokens = assembler._estimate_tokens(text)
        assert tokens > 0
    
    def test_format_symbol_section_empty(self, assembler):
        """Test symbol section with no symbols"""
        result = assembler._format_symbol_section([])
        assert result == ""
    
    def test_format_symbol_section_with_symbols(self, assembler):
        """Test symbol section with symbols"""
        result = assembler._format_symbol_section(["600519", "000858"])
        assert "600519" in result
        assert "茅台" in result  # Should find name from map
    
    def test_format_financial_section_empty(self, assembler):
        """Test financial section with no data"""
        result = assembler._format_financial_section(None)
        assert result == ""
    
    def test_format_financial_section_with_data(self, assembler):
        """Test financial section with data"""
        data = {
            'indicators': [
                {'indicator_name': 'ROE', 'value': '25%', 'change': '+2%'}
            ]
        }
        result = assembler._format_financial_section(data)
        assert "ROE" in result
        assert "25%" in result
    
    def test_format_news_section_empty(self, assembler):
        """Test news section with no items"""
        result = assembler._format_news_section([])
        assert result == ""
    
    def test_format_news_section_with_items(self, assembler):
        """Test news section with items"""
        items = [
            {'title': '茅台发布业绩预告', 'time': '2024-01-15', 'type': 'bullish'}
        ]
        result = assembler._format_news_section(items)
        assert "茅台发布业绩预告" in result
        assert "📈" in result  # Bullish emoji
    
    def test_format_news_section_bearish(self, assembler):
        """Test news section with bearish news"""
        items = [
            {'title': '白酒板块下跌', 'type': 'bearish'}
        ]
        result = assembler._format_news_section(items)
        assert "📉" in result  # Bearish emoji
    
    @pytest.mark.asyncio
    async def test_assemble_empty_query(self, assembler):
        """Test assembly with empty query"""
        result = await assembler.assemble("")
        assert result.query_type == QueryType.QUICK_QA
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_assemble_with_symbol(self, assembler):
        """Test assembly with explicit symbol"""
        # Mock the fetchers to avoid actual API calls
        with patch.object(assembler._f9_fetcher, 'fetch', new_callable=AsyncMock) as mock_f9:
            mock_f9.return_value = None
            
            result = await assembler.assemble("分析", symbol="600519")
            
            assert "600519" in result.symbols
            mock_f9.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_assemble_timeout(self, assembler):
        """Test assembly timeout handling"""
        # Mock a slow fetch
        async def slow_fetch(*args, **kwargs):
            import asyncio
            await asyncio.sleep(10)
            return {}
        
        with patch.object(assembler._f9_fetcher, 'fetch', side_effect=slow_fetch):
            result = await assembler.assemble("分析茅台", timeout=0.1)
            
            assert result.error is not None
            assert "超时" in result.error
    
    @pytest.mark.asyncio
    async def test_assemble_company_deep_dive(self, assembler):
        """Test assembly for company deep dive query"""
        # Mock all fetchers
        with patch.object(assembler._f9_fetcher, 'fetch', new_callable=AsyncMock) as mock_f9, \
             patch.object(assembler._macro_fetcher, 'fetch', new_callable=AsyncMock) as mock_macro, \
             patch.object(assembler._news_fetcher, 'fetch', new_callable=AsyncMock) as mock_news:
            
            mock_f9.return_value = None
            mock_macro.return_value = None
            mock_news.return_value = None
            
            result = await assembler.assemble("分析茅台的基本面")
            
            assert result.query_type == QueryType.COMPANY_DEEP_DIVE
            assert "600519" in result.symbols
            assert result.tokens_used >= 0
    
    @pytest.mark.asyncio
    async def test_assemble_portfolio_risk(self, assembler):
        """Test assembly for portfolio risk query"""
        with patch.object(assembler._f9_fetcher, 'fetch', new_callable=AsyncMock) as mock_f9, \
             patch.object(assembler._macro_fetcher, 'fetch', new_callable=AsyncMock) as mock_macro, \
             patch.object(assembler._news_fetcher, 'fetch', new_callable=AsyncMock) as mock_news:
            
            mock_f9.return_value = None
            mock_macro.return_value = None
            mock_news.return_value = None
            
            result = await assembler.assemble("检查我的持仓风险")
            
            assert result.query_type == QueryType.PORTFOLIO_RISK
    
    @pytest.mark.asyncio
    async def test_assemble_sector_comparison(self, assembler):
        """Test assembly for sector comparison query"""
        with patch.object(assembler._f9_fetcher, 'fetch', new_callable=AsyncMock) as mock_f9:
            mock_f9.return_value = None
            
            result = await assembler.assemble("茅台 vs 五粮液")
            
            assert result.query_type == QueryType.SECTOR_COMPARISON
            assert len(result.symbols) >= 2
    
    @pytest.mark.asyncio
    async def test_assemble_macro_impact(self, assembler):
        """Test assembly for macro impact query"""
        with patch.object(assembler._macro_fetcher, 'fetch', new_callable=AsyncMock) as mock_macro:
            mock_macro.return_value = None
            
            result = await assembler.assemble("CPI对消费板块影响")
            
            assert result.query_type == QueryType.MACRO_IMPACT
            assert "CPI" in result.classification.macro_indicators


class TestAssemblyResult:
    """Tests for AssemblyResult dataclass"""
    
    def test_default_values(self):
        """Test default values"""
        result = AssemblyResult(
            query_type=QueryType.QUICK_QA,
            context_text="",
            tokens_used=0,
            symbols=[],
            classification=ClassificationResult(
                query_type=QueryType.QUICK_QA,
                symbols=[],
                confidence=0.0,
                original_query=""
            )
        )
        
        assert result.f9_data is None
        assert result.macro_data is None
        assert result.news_data is None
        assert result.portfolio_data is None
        assert result.error is None
    
    def test_with_data(self):
        """Test with data"""
        result = AssemblyResult(
            query_type=QueryType.COMPANY_DEEP_DIVE,
            context_text="测试上下文",
            tokens_used=10,
            symbols=["600519"],
            classification=ClassificationResult(
                query_type=QueryType.COMPANY_DEEP_DIVE,
                symbols=["600519"],
                confidence=0.8,
                original_query="分析茅台"
            ),
            f9_data={"financial": {}},
            error=None
        )
        
        assert result.query_type == QueryType.COMPANY_DEEP_DIVE
        assert result.f9_data is not None

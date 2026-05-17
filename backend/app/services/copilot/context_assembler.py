"""
ContextAssembler - Copilot 上下文组装器

功能特性:
- 根据查询类型智能组装上下文
- 使用 QueryClassifier 分类查询
- 使用 F9Fetcher、MacroFetcher、NewsFetcher 获取数据
- 构建结构化上下文文本供 LLM 注入
- Token 估算（中文: 1 字符 ≈ 1 token）
- 单例模式（线程安全）

设计原则:
- 根据查询类型选择合适的上下文配置
- 并行获取多个数据源
- 格式化为结构化文本
- 超时保护
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.copilot.query_classifier import (
    QueryClassifier,
    QueryType,
    ClassificationResult,
    get_query_classifier,
)
from app.services.copilot.data_fetchers.f9_fetcher import F9Fetcher, get_f9_fetcher
from app.services.copilot.data_fetchers.macro_fetcher import MacroFetcher, get_macro_fetcher
from app.services.copilot.data_fetchers.news_fetcher import NewsFetcher, get_news_fetcher

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构定义
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContextConfig:
    """上下文配置"""
    f9_tabs: List[str] = field(default_factory=list)  # 要获取的 F9 tabs
    macro_indicators: List[str] = field(default_factory=list)  # 宏观指标
    news_days: int = 7  # 新闻天数
    portfolio: bool = False  # 是否包含投资组合数据
    peers: bool = False  # 是否包含同业比较


@dataclass
class AssemblyResult:
    """上下文组装结果"""
    query_type: QueryType
    context_text: str  # 格式化的上下文文本（供 LLM 注入）
    tokens_used: int  # 估算的 token 数量
    symbols: List[str]  # 提取的股票代码
    classification: ClassificationResult  # 原始分类结果
    f9_data: Optional[Dict[str, Any]] = None
    macro_data: Optional[Dict[str, Any]] = None
    news_data: Optional[Dict[str, Any]] = None
    portfolio_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# 查询类型到上下文配置的映射
# ─────────────────────────────────────────────────────────────────────────────

CONTEXT_CONFIGS: Dict[QueryType, ContextConfig] = {
    QueryType.COMPANY_DEEP_DIVE: ContextConfig(
        f9_tabs=["financial", "institution", "forecast", "shareholder", "margin", "peers", "announcements"],
        macro_indicators=["gdp"],
        news_days=30,
        portfolio=False,
        peers=True
    ),
    QueryType.EVENT_DRIVEN: ContextConfig(
        f9_tabs=["financial", "peers"],
        macro_indicators=[],
        news_days=90,
        portfolio=False,
        peers=True
    ),
    QueryType.PORTFOLIO_RISK: ContextConfig(
        f9_tabs=["financial", "shareholder"],
        macro_indicators=["gdp", "cpi", "ppi"],
        news_days=7,
        portfolio=True,
        peers=False
    ),
    QueryType.MACRO_IMPACT: ContextConfig(
        f9_tabs=["peers"],
        macro_indicators=["gdp", "cpi", "ppi", "pmi", "m2"],
        news_days=30,
        portfolio=False,
        peers=True
    ),
    QueryType.SECTOR_COMPARISON: ContextConfig(
        f9_tabs=["financial", "institution", "forecast"],
        macro_indicators=[],
        news_days=0,
        portfolio=False,
        peers=False
    ),
    QueryType.QUICK_QA: ContextConfig(
        f9_tabs=["financial"],
        macro_indicators=[],
        news_days=7,
        portfolio=False,
        peers=False
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# ContextAssembler 类
# ─────────────────────────────────────────────────────────────────────────────

class ContextAssembler:
    """
    上下文组装器
    
    特性:
    - 根据查询类型智能选择上下文配置
    - 并行获取多个数据源
    - 格式化为结构化文本
    - Token 估算
    """
    
    DEFAULT_TIMEOUT = 30.0  # 默认超时时间
    
    def __init__(self):
        """初始化组装器"""
        self._classifier = get_query_classifier()
        self._f9_fetcher = get_f9_fetcher()
        self._macro_fetcher = get_macro_fetcher()
        self._news_fetcher = get_news_fetcher()
        logger.info("[ContextAssembler] 初始化完成")
    
    async def assemble(
        self,
        query: str,
        symbol: Optional[str] = None,
        portfolio_id: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> AssemblyResult:
        """
        组装上下文
        
        Args:
            query: 用户查询
            symbol: 股票代码（可选，如果提供则优先使用）
            portfolio_id: 投资组合 ID（可选）
            timeout: 超时时间（秒）
            
        Returns:
            AssemblyResult 对象
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        # 1. 分类查询
        classification = self._classifier.classify(query)
        query_type = classification.query_type
        symbols = classification.symbols.copy()
        
        # 如果提供了 symbol，添加到 symbols 列表
        if symbol and symbol not in symbols:
            symbols.insert(0, symbol)
        
        logger.info(f"[ContextAssembler] 查询分类: {query_type.value}, symbols: {symbols}")
        
        # 2. 获取上下文配置
        config = CONTEXT_CONFIGS.get(query_type, CONTEXT_CONFIGS[QueryType.QUICK_QA])
        
        # 3. 并行获取数据
        try:
            result = await asyncio.wait_for(
                self._fetch_all_data(config, symbols, portfolio_id),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"[ContextAssembler] 数据获取超时 ({timeout}s)")
            return AssemblyResult(
                query_type=query_type,
                context_text="",
                tokens_used=0,
                symbols=symbols,
                classification=classification,
                error=f"数据获取超时 ({timeout}秒)"
            )
        except Exception as e:
            logger.error(f"[ContextAssembler] 数据获取失败: {e}")
            return AssemblyResult(
                query_type=query_type,
                context_text="",
                tokens_used=0,
                symbols=symbols,
                classification=classification,
                error=f"数据获取失败: {str(e)}"
            )
        
        # 4. 构建上下文文本
        context_text = self._build_context_text(
            query=query,
            symbols=symbols,
            config=config,
            f9_data=result.get("f9"),
            macro_data=result.get("macro"),
            news_data=result.get("news"),
            portfolio_data=result.get("portfolio")
        )
        
        # 5. 估算 token 数量
        tokens_used = self._estimate_tokens(context_text)
        
        logger.info(f"[ContextAssembler] 上下文组装完成: {tokens_used} tokens")
        
        return AssemblyResult(
            query_type=query_type,
            context_text=context_text,
            tokens_used=tokens_used,
            symbols=symbols,
            classification=classification,
            f9_data=result.get("f9"),
            macro_data=result.get("macro"),
            news_data=result.get("news"),
            portfolio_data=result.get("portfolio")
        )
    
    async def _fetch_all_data(
        self,
        config: ContextConfig,
        symbols: List[str],
        portfolio_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        并行获取所有数据
        
        Args:
            config: 上下文配置
            symbols: 股票代码列表
            portfolio_id: 投资组合 ID
            
        Returns:
            数据字典
        """
        result = {}
        tasks = []
        task_names = []
        
        # F9 数据（如果有股票代码）
        if symbols and config.f9_tabs:
            primary_symbol = symbols[0]
            tasks.append(self._f9_fetcher.fetch(primary_symbol, tabs=config.f9_tabs))
            task_names.append("f9")
        
        # 宏观数据
        if config.macro_indicators:
            tasks.append(self._macro_fetcher.fetch(indicators=config.macro_indicators))
            task_names.append("macro")
        
        # 新闻数据
        if config.news_days > 0 and symbols:
            tasks.append(self._news_fetcher.fetch(symbol=symbols[0], days=config.news_days))
            task_names.append("news")
        elif config.news_days > 0:
            tasks.append(self._news_fetcher.fetch(days=config.news_days))
            task_names.append("news")
        
        # 投资组合数据
        if config.portfolio and portfolio_id:
            tasks.append(self._fetch_portfolio_data(portfolio_id))
            task_names.append("portfolio")
        
        # 并行执行
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for name, res in zip(task_names, results):
                if isinstance(res, Exception):
                    logger.warning(f"[ContextAssembler] {name} 获取失败: {res}")
                    result[name] = None
                else:
                    result[name] = res
        
        return result
    
    async def _fetch_portfolio_data(self, portfolio_id: int) -> Optional[Dict[str, Any]]:
        """
        获取投资组合数据
        
        Args:
            portfolio_id: 投资组合 ID
            
        Returns:
            投资组合数据字典
        """
        try:
            from app.routers.portfolio.positions import list_positions
            
            # 调用路由函数获取持仓
            response = await list_positions(portfolio_id)
            
            # 解析响应
            if hasattr(response, 'body'):
                import json
                data = json.loads(response.body.decode())
                data = data.get('data', data)
            elif isinstance(response, dict):
                data = response.get('data', response)
            else:
                data = response
            
            return data if isinstance(data, dict) else None
            
        except Exception as e:
            logger.warning(f"[ContextAssembler] 投资组合数据获取失败: {e}")
            return None
    
    def _build_context_text(
        self,
        query: str,
        symbols: List[str],
        config: ContextConfig,
        f9_data: Optional[Any],
        macro_data: Optional[Any],
        news_data: Optional[Any],
        portfolio_data: Optional[Any]
    ) -> str:
        """
        构建上下文文本
        
        Args:
            query: 用户查询
            symbols: 股票代码列表
            config: 上下文配置
            f9_data: F9 数据
            macro_data: 宏观数据
            news_data: 新闻数据
            portfolio_data: 投资组合数据
            
        Returns:
            格式化的上下文文本
        """
        sections = []
        
        # 1. 当前标的
        if symbols:
            symbol_section = self._format_symbol_section(symbols)
            if symbol_section:
                sections.append(symbol_section)
        
        # 2. 财务摘要
        if f9_data and hasattr(f9_data, 'financial') and f9_data.financial:
            financial_section = self._format_financial_section(f9_data.financial)
            if financial_section:
                sections.append(financial_section)
        
        # 3. 机构持股
        if f9_data and hasattr(f9_data, 'institution') and f9_data.institution:
            institution_section = self._format_institution_section(f9_data.institution)
            if institution_section:
                sections.append(institution_section)
        
        # 4. 盈利预测
        if f9_data and hasattr(f9_data, 'forecast') and f9_data.forecast:
            forecast_section = self._format_forecast_section(f9_data.forecast)
            if forecast_section:
                sections.append(forecast_section)
        
        # 5. 股东研究
        if f9_data and hasattr(f9_data, 'shareholder') and f9_data.shareholder:
            shareholder_section = self._format_shareholder_section(f9_data.shareholder)
            if shareholder_section:
                sections.append(shareholder_section)
        
        # 6. 融资融券
        if f9_data and hasattr(f9_data, 'margin') and f9_data.margin:
            margin_section = self._format_margin_section(f9_data.margin)
            if margin_section:
                sections.append(margin_section)
        
        # 7. 同业比较
        if f9_data and hasattr(f9_data, 'peers') and f9_data.peers:
            peers_section = self._format_peers_section(f9_data.peers)
            if peers_section:
                sections.append(peers_section)
        
        # 8. 宏观背景
        if macro_data and hasattr(macro_data, 'indicators') and macro_data.indicators:
            macro_section = self._format_macro_section(macro_data.indicators)
            if macro_section:
                sections.append(macro_section)
        
        # 9. 相关新闻
        if news_data and hasattr(news_data, 'news_items') and news_data.news_items:
            news_section = self._format_news_section(news_data.news_items)
            if news_section:
                sections.append(news_section)
        
        # 10. 投资组合
        if portfolio_data:
            portfolio_section = self._format_portfolio_section(portfolio_data)
            if portfolio_section:
                sections.append(portfolio_section)
        
        return "\n\n".join(sections)
    
    def _format_symbol_section(self, symbols: List[str]) -> str:
        """格式化股票代码部分"""
        if not symbols:
            return ""
        
        # 获取股票名称（如果有）
        from app.services.copilot.query_classifier import STOCK_NAME_MAP
        
        lines = ["【当前标的】"]
        for symbol in symbols[:3]:  # 最多显示 3 个
            # 查找股票名称
            name = None
            for n, s in STOCK_NAME_MAP.items():
                if s == symbol:
                    name = n
                    break
            
            if name:
                lines.append(f"{symbol} {name}")
            else:
                lines.append(f"{symbol}")
        
        return "\n".join(lines)
    
    def _format_financial_section(self, data: Dict[str, Any]) -> str:
        """格式化财务摘要部分"""
        if not data:
            return ""
        
        lines = ["【财务摘要】"]
        
        # 提取关键财务指标
        indicators = data.get('indicators', [])
        if isinstance(indicators, list) and indicators:
            # 只显示最新的 5 个指标
            for ind in indicators[:5]:
                name = ind.get('indicator_name', ind.get('name', ''))
                value = ind.get('value', ind.get('latest_value', ''))
                change = ind.get('change', ind.get('yoy_change', ''))
                
                if name and value:
                    line = f"- {name}: {value}"
                    if change:
                        line += f" (同比{change})"
                    lines.append(line)
        
        # 提取趋势数据
        trend = data.get('trend', [])
        if isinstance(trend, list) and trend:
            lines.append("\n【财务趋势】")
            for t in trend[:4]:  # 最近 4 个季度
                period = t.get('period', t.get('date', ''))
                revenue = t.get('revenue', t.get('营业收入', ''))
                profit = t.get('net_profit', t.get('净利润', ''))
                
                if period:
                    line = f"- {period}"
                    if revenue:
                        line += f" 营收: {revenue}"
                    if profit:
                        line += f" 净利润: {profit}"
                    lines.append(line)
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_institution_section(self, data: Dict[str, Any]) -> str:
        """格式化机构持股部分"""
        if not data:
            return ""
        
        lines = ["【机构持股】"]
        
        # 持股比例
        holdings = data.get('holdings', [])
        if isinstance(holdings, list) and holdings:
            for h in holdings[:5]:
                institution = h.get('institution_name', h.get('name', ''))
                shares = h.get('shares', h.get('持股数量', ''))
                ratio = h.get('ratio', h.get('持股比例', ''))
                
                if institution:
                    line = f"- {institution}"
                    if ratio:
                        line += f": {ratio}"
                    lines.append(line)
        
        # 持股变化趋势
        trend = data.get('trend', [])
        if isinstance(trend, list) and trend:
            lines.append("\n【持股趋势】")
            for t in trend[:4]:
                period = t.get('period', t.get('date', ''))
                total_ratio = t.get('total_ratio', t.get('机构持股比例', ''))
                
                if period and total_ratio:
                    lines.append(f"- {period}: {total_ratio}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_forecast_section(self, data: Dict[str, Any]) -> str:
        """格式化盈利预测部分"""
        if not data:
            return ""
        
        lines = ["【盈利预测】"]
        
        # EPS 预测
        eps_forecast = data.get('eps_forecast', [])
        if isinstance(eps_forecast, list) and eps_forecast:
            lines.append("\n【EPS 预测】")
            for f in eps_forecast[:3]:
                year = f.get('year', f.get('fiscal_year', ''))
                eps = f.get('eps', f.get('预测EPS', ''))
                
                if year and eps:
                    lines.append(f"- {year}: {eps}")
        
        # 机构评级
        ratings = data.get('ratings', [])
        if isinstance(ratings, list) and ratings:
            lines.append("\n【机构评级】")
            for r in ratings[:3]:
                institution = r.get('institution', r.get('机构名称', ''))
                rating = r.get('rating', r.get('评级', ''))
                target_price = r.get('target_price', r.get('目标价', ''))
                
                if institution:
                    line = f"- {institution}: {rating}"
                    if target_price:
                        line += f" (目标价: {target_price})"
                    lines.append(line)
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_shareholder_section(self, data: Dict[str, Any]) -> str:
        """格式化股东研究部分"""
        if not data:
            return ""
        
        lines = ["【股东研究】"]
        
        # Top10 股东
        holders = data.get('holders', [])
        if isinstance(holders, list) and holders:
            lines.append("\n【Top10 股东】")
            for h in holders[:5]:
                name = h.get('holder_name', h.get('股东名称', ''))
                shares = h.get('shares', h.get('持股数量', ''))
                ratio = h.get('ratio', h.get('持股比例', ''))
                
                if name:
                    line = f"- {name}"
                    if ratio:
                        line += f": {ratio}"
                    lines.append(line)
        
        # 股本变动
        changes = data.get('changes', [])
        if isinstance(changes, list) and changes:
            lines.append("\n【股本变动】")
            for c in changes[:3]:
                date = c.get('date', c.get('变动日期', ''))
                change_type = c.get('type', c.get('变动类型', ''))
                
                if date and change_type:
                    lines.append(f"- {date}: {change_type}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_margin_section(self, data: Dict[str, Any]) -> str:
        """格式化融资融券部分"""
        if not data:
            return ""
        
        lines = ["【融资融券】"]
        
        # 最新数据
        latest = data.get('latest', {})
        if latest:
            financing_balance = latest.get('financing_balance', latest.get('融资余额', ''))
            margin_balance = latest.get('margin_balance', latest.get('融券余额', ''))
            
            if financing_balance:
                lines.append(f"- 融资余额: {financing_balance}")
            if margin_balance:
                lines.append(f"- 融券余额: {margin_balance}")
        
        # 趋势
        trend = data.get('trend', [])
        if isinstance(trend, list) and trend:
            lines.append("\n【30日趋势】")
            for t in trend[-5:]:  # 最近 5 天
                date = t.get('date', '')
                financing = t.get('financing_balance', t.get('融资余额', ''))
                
                if date and financing:
                    lines.append(f"- {date}: {financing}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_peers_section(self, data: Dict[str, Any]) -> str:
        """格式化同业比较部分"""
        if not data:
            return ""
        
        lines = ["【同业比较】"]
        
        # 同业公司
        peers = data.get('peers', [])
        if isinstance(peers, list) and peers:
            for p in peers[:5]:
                name = p.get('name', p.get('公司名称', ''))
                pe = p.get('pe', p.get('市盈率', ''))
                pb = p.get('pb', p.get('市净率', ''))
                
                if name:
                    line = f"- {name}"
                    if pe:
                        line += f" PE: {pe}"
                    if pb:
                        line += f" PB: {pb}"
                    lines.append(line)
        
        # 行业均值
        industry_avg = data.get('industry_avg', {})
        if industry_avg:
            avg_pe = industry_avg.get('pe', industry_avg.get('平均市盈率', ''))
            avg_pb = industry_avg.get('pb', industry_avg.get('平均市净率', ''))
            
            lines.append("\n【行业均值】")
            if avg_pe:
                lines.append(f"- 平均市盈率: {avg_pe}")
            if avg_pb:
                lines.append(f"- 平均市净率: {avg_pb}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_macro_section(self, indicators: Dict[str, Any]) -> str:
        """格式化宏观背景部分"""
        if not indicators:
            return ""
        
        lines = ["【宏观背景】"]
        
        # GDP
        gdp = indicators.get('gdp', {})
        if gdp and isinstance(gdp, dict):
            data = gdp.get('data', [])
            if isinstance(data, list) and data:
                latest = data[0] if data else {}
                period = latest.get('date', latest.get('季度', ''))
                value = latest.get('value', latest.get('GDP增速', ''))
                
                if period and value:
                    lines.append(f"- GDP: {value} ({period})")
        
        # CPI
        cpi = indicators.get('cpi', {})
        if cpi and isinstance(cpi, dict):
            data = cpi.get('data', [])
            if isinstance(data, list) and data:
                latest = data[0] if data else {}
                period = latest.get('date', latest.get('月份', ''))
                value = latest.get('value', latest.get('CPI同比', ''))
                
                if period and value:
                    lines.append(f"- CPI: {value} ({period})")
        
        # PPI
        ppi = indicators.get('ppi', {})
        if ppi and isinstance(ppi, dict):
            data = ppi.get('data', [])
            if isinstance(data, list) and data:
                latest = data[0] if data else {}
                period = latest.get('date', latest.get('月份', ''))
                value = latest.get('value', latest.get('PPI同比', ''))
                
                if period and value:
                    lines.append(f"- PPI: {value} ({period})")
        
        # PMI
        pmi = indicators.get('pmi', {})
        if pmi and isinstance(pmi, dict):
            data = pmi.get('data', [])
            if isinstance(data, list) and data:
                latest = data[0] if data else {}
                period = latest.get('date', latest.get('月份', ''))
                value = latest.get('value', latest.get('PMI', ''))
                
                if period and value:
                    lines.append(f"- PMI: {value} ({period})")
        
        # M2
        m2 = indicators.get('m2', {})
        if m2 and isinstance(m2, dict):
            data = m2.get('data', [])
            if isinstance(data, list) and data:
                latest = data[0] if data else {}
                period = latest.get('date', latest.get('月份', ''))
                value = latest.get('value', latest.get('M2同比', ''))
                
                if period and value:
                    lines.append(f"- M2: {value} ({period})")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_news_section(self, news_items: List[Dict[str, Any]]) -> str:
        """格式化相关新闻部分"""
        if not news_items:
            return ""
        
        lines = ["【相关新闻】"]
        
        for i, item in enumerate(news_items[:10], 1):
            title = item.get('title', item.get('headline', ''))
            time = item.get('time', item.get('date', ''))
            news_type = item.get('type', 'neutral')
            
            # 情感标签
            if news_type == 'bullish':
                tag = '📈'
            elif news_type == 'bearish':
                tag = '📉'
            else:
                tag = '📰'
            
            if title:
                if time:
                    lines.append(f"{i}. [{time}] {tag} {title}")
                else:
                    lines.append(f"{i}. {tag} {title}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_portfolio_section(self, data: Dict[str, Any]) -> str:
        """格式化投资组合部分"""
        if not data:
            return ""
        
        lines = ["【投资组合】"]
        
        # 持仓列表
        positions = data.get('positions', [])
        if isinstance(positions, list) and positions:
            lines.append("\n【当前持仓】")
            for p in positions[:10]:
                symbol = p.get('symbol', p.get('股票代码', ''))
                name = p.get('name', p.get('股票名称', ''))
                shares = p.get('shares', p.get('持仓数量', ''))
                cost = p.get('cost', p.get('成本价', ''))
                market_value = p.get('market_value', p.get('市值', ''))
                
                if symbol:
                    line = f"- {symbol}"
                    if name:
                        line += f" {name}"
                    if shares:
                        line += f": {shares}股"
                    if market_value:
                        line += f" (市值: {market_value})"
                    lines.append(line)
        
        # 汇总信息
        summary = data.get('summary', {})
        if summary:
            total_value = summary.get('total_value', summary.get('总市值', ''))
            total_cost = summary.get('total_cost', summary.get('总成本', ''))
            pnl = summary.get('pnl', summary.get('盈亏', ''))
            pnl_ratio = summary.get('pnl_ratio', summary.get('收益率', ''))
            
            lines.append("\n【组合汇总】")
            if total_value:
                lines.append(f"- 总市值: {total_value}")
            if total_cost:
                lines.append(f"- 总成本: {total_cost}")
            if pnl:
                lines.append(f"- 盈亏: {pnl}")
            if pnl_ratio:
                lines.append(f"- 收益率: {pnl_ratio}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量
        
        简单估算规则:
        - 中文字符: 1 字符 ≈ 1 token
        - 英文单词: 1 单词 ≈ 1 token
        - 数字/标点: 1 字符 ≈ 0.5 token
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0
        
        # 统计中文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        
        # 统计英文单词（粗略估算）
        english_words = len([w for w in text.split() if w.isascii()])
        
        # 统计其他字符
        other_chars = len(text) - chinese_chars - sum(len(w) for w in text.split() if w.isascii())
        
        # 估算 token
        tokens = chinese_chars + english_words + int(other_chars * 0.5)
        
        return tokens


# ─────────────────────────────────────────────────────────────────────────────
# 单例模式（双重检查锁定）
# ─────────────────────────────────────────────────────────────────────────────

_assembler_instance: Optional[ContextAssembler] = None
_assembler_lock = threading.Lock()


def get_context_assembler() -> ContextAssembler:
    """
    获取 ContextAssembler 单例实例
    
    使用双重检查锁定模式确保线程安全
    """
    global _assembler_instance
    
    if _assembler_instance is None:
        with _assembler_lock:
            if _assembler_instance is None:
                _assembler_instance = ContextAssembler()
    
    return _assembler_instance

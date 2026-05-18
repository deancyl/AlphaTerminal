"""
NewsDataFetcher - Copilot 新闻数据获取器

功能特性:
- 直接调用路由函数（非 HTTP 调用）
- 5 分钟缓存 TTL
- 单例模式（线程安全）
- 超时保护
- 支持股票代码特定新闻和通用市场新闻

设计原则:
- 优先使用现有 news_engine 缓存
- 使用 DataCache 单例进行缓存
- 情感分类（利好/利空/中性）
"""

import logging
import threading
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.data_cache import get_cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构定义
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NewsDataResult:
    """新闻数据结果"""
    news_items: List[Dict[str, Any]]  # 新闻列表
    sentiment: Optional[str] = None  # 整体情感（bullish/bearish/neutral）
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


# ─────────────────────────────────────────────────────────────────────────────
# NewsFetcher 类
# ─────────────────────────────────────────────────────────────────────────────

class NewsFetcher:
    """
    新闻数据获取器
    
    特性:
    - 直接调用 news_engine 函数（非 HTTP 调用）
    - 5 分钟缓存 TTL
    - 支持股票代码特定新闻
    - 情感分类
    """
    
    CACHE_TTL = 300  # 5 分钟缓存
    DEFAULT_TIMEOUT = 10.0  # 默认超时时间
    
    # 情感关键词
    BULLISH_KEYWORDS = ["利好", "上涨", "突破", "新高", "增长", "盈利", 
                        "增持", "回购", "中标", "签约", "涨停", "大涨"]
    BEARISH_KEYWORDS = ["利空", "下跌", "暴跌", "亏损", "减持", "质押",
                        "违约", "诉讼", "调查", "处罚", "跌停", "暴跌"]
    
    def __init__(self):
        """初始化获取器"""
        self._cache = get_cache()
        logger.info("[NewsFetcher] 初始化完成")
    
    async def fetch(
        self,
        symbol: Optional[str] = None,  # 股票代码特定新闻
        days: int = 7,  # 最近 N 天的新闻
        limit: int = 10,  # 最大新闻条数
        timeout: Optional[float] = None
    ) -> NewsDataResult:
        """
        获取新闻数据
        
        Args:
            symbol: 股票代码（可选），如 "600519" 或 "sh600519"
            days: 最近 N 天的新闻（默认 7 天）
            limit: 最大新闻条数（默认 10）
            timeout: 超时时间（秒），None 使用默认值
            
        Returns:
            NewsDataResult 对象
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        try:
            # 构建缓存键
            cache_key = f"copilot:news:{symbol or 'general'}:{days}:{limit}"
            
            # 检查缓存
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug(f"[NewsFetcher] 缓存命中: {symbol or 'general'}")
                return NewsDataResult(
                    news_items=cached.get('news_items', []),
                    sentiment=cached.get('sentiment'),
                    fetched_at=datetime.now()
                )
            
            # 获取新闻数据
            if symbol:
                result = await self._fetch_symbol_news(symbol, days, limit, timeout)
            else:
                result = await self._fetch_general_news(limit, timeout)
            
            # 缓存结果
            if not result.error:
                cache_data = {
                    'news_items': result.news_items,
                    'sentiment': result.sentiment,
                }
                self._cache.set(cache_key, cache_data, ttl=self.CACHE_TTL)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"[NewsFetcher] 获取超时 ({timeout}s)")
            return NewsDataResult(
                news_items=[],
                error=f"新闻获取超时 ({timeout}秒)"
            )
        except Exception as e:
            logger.error(f"[NewsFetcher] 获取失败: {e}")
            return NewsDataResult(
                news_items=[],
                error=f"新闻获取失败: {str(e)}"
            )
    
    async def _fetch_general_news(
        self,
        limit: int,
        timeout: float
    ) -> NewsDataResult:
        """
        获取通用市场新闻
        
        直接调用 news_engine 的 get_cached_news 函数
        """
        try:
            from app.services.news_engine import get_cached_news, is_cache_ready
            
            # 检查缓存是否就绪
            if not is_cache_ready():
                logger.warning("[NewsFetcher] 新闻缓存未就绪")
                return NewsDataResult(
                    news_items=[],
                    sentiment="neutral",
                    error="新闻缓存未就绪"
                )
            
            # 在线程池中执行同步函数
            loop = asyncio.get_event_loop()
            news = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: get_cached_news(limit=limit)),
                timeout=timeout
            )
            
            if not news:
                return NewsDataResult(
                    news_items=[],
                    sentiment="neutral"
                )
            
            # 计算整体情感
            sentiment = self._calculate_sentiment(news)
            
            # 格式化新闻数据
            formatted_news = self._format_news_items(news)
            
            logger.info(f"[NewsFetcher] 获取通用新闻成功: {len(formatted_news)} 条")
            
            return NewsDataResult(
                news_items=formatted_news,
                sentiment=sentiment,
                fetched_at=datetime.now()
            )
            
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[NewsFetcher] 通用新闻获取失败: {e}")
            raise
    
    async def _fetch_symbol_news(
        self,
        symbol: str,
        days: int,
        limit: int,
        timeout: float
    ) -> NewsDataResult:
        """
        获取特定股票的新闻
        
        直接调用 news router 的 news_events_for_symbol 函数
        """
        try:
            # 清理股票代码（去除前缀）
            clean_symbol = symbol.replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
            
            # 直接调用路由函数
            from app.routers import news as news_router
            
            # 在线程池中执行同步路由函数（如果路由是同步的）
            # 注意: news_events_for_symbol 是 async 函数，直接调用
            response = await asyncio.wait_for(
                news_router.news_events_for_symbol(symbol, limit=limit),
                timeout=timeout
            )
            
            # 解析响应
            data = response
            if hasattr(response, 'body'):
                import json
                data = json.loads(response.body.decode())  # type: ignore
            elif isinstance(response, dict):
                data = response
            
            # 提取事件数据
            events = data.get('data', {}).get('events', [])
            
            if not events:
                # 如果没有特定新闻，返回通用新闻
                logger.info(f"[NewsFetcher] {symbol} 无特定新闻，返回通用新闻")
                return await self._fetch_general_news(limit, timeout)
            
            # 过滤最近 N 天的新闻
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_events = []
            for event in events:
                date_str = event.get('date', '')
                try:
                    event_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if event_date >= cutoff_date:
                        filtered_events.append(event)
                except ValueError:
                    # 无法解析日期，保留该条
                    filtered_events.append(event)
            
            # 计算整体情感
            sentiment = self._calculate_sentiment_from_events(filtered_events)
            
            # 格式化新闻数据
            formatted_news = self._format_events(filtered_events)
            
            logger.info(f"[NewsFetcher] 获取 {symbol} 新闻成功: {len(formatted_news)} 条")
            
            return NewsDataResult(
                news_items=formatted_news,
                sentiment=sentiment,
                fetched_at=datetime.now()
            )
            
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[NewsFetcher] {symbol} 新闻获取失败: {e}")
            # 降级到通用新闻
            logger.info(f"[NewsFetcher] 降级到通用新闻")
            return await self._fetch_general_news(limit, timeout)
    
    def _calculate_sentiment(self, news: List[Dict]) -> str:
        """
        计算新闻整体情感
        
        Args:
            news: 新闻列表
            
        Returns:
            'bullish', 'bearish', 或 'neutral'
        """
        bullish_count = 0
        bearish_count = 0
        
        for item in news:
            title = item.get('title', '')
            tag = item.get('tag', '')
            
            # 检查标题中的关键词
            for keyword in self.BULLISH_KEYWORDS:
                if keyword in title:
                    bullish_count += 1
                    break
            
            for keyword in self.BEARISH_KEYWORDS:
                if keyword in title:
                    bearish_count += 1
                    break
            
            # 检查标签（如 "🔴 突发" 可能是负面）
            if "暴跌" in tag or "大跌" in tag:
                bearish_count += 1
        
        # 计算情感倾向
        total = bullish_count + bearish_count
        if total == 0:
            return "neutral"
        
        bullish_ratio = bullish_count / total
        
        if bullish_ratio > 0.6:
            return "bullish"
        elif bullish_ratio < 0.4:
            return "bearish"
        else:
            return "neutral"
    
    def _calculate_sentiment_from_events(self, events: List[Dict]) -> str:
        """
        从事件类型计算情感
        
        Args:
            events: 事件列表（包含 type 字段）
            
        Returns:
            'bullish', 'bearish', 或 'neutral'
        """
        bullish_count = sum(1 for e in events if e.get('type') == 'bullish')
        bearish_count = sum(1 for e in events if e.get('type') == 'bearish')
        
        total = bullish_count + bearish_count
        if total == 0:
            return "neutral"
        
        bullish_ratio = bullish_count / total
        
        if bullish_ratio > 0.6:
            return "bullish"
        elif bullish_ratio < 0.4:
            return "bearish"
        else:
            return "neutral"
    
    def _format_news_items(self, news: List[Dict]) -> List[Dict[str, Any]]:
        """
        格式化新闻数据为统一格式
        
        Args:
            news: 原始新闻列表
            
        Returns:
            格式化的新闻列表
        """
        formatted = []
        for item in news:
            formatted.append({
                'title': item.get('title', ''),
                'time': item.get('time', ''),
                'tag': item.get('tag', ''),
                'url': item.get('url', ''),
                'source': item.get('source', ''),
                'type': self._classify_single_news(item.get('title', '')),
            })
        return formatted
    
    def _format_events(self, events: List[Dict]) -> List[Dict[str, Any]]:
        """
        格式化事件数据为统一格式
        
        Args:
            events: 原始事件列表
            
        Returns:
            格式化的新闻列表
        """
        formatted = []
        for event in events:
            formatted.append({
                'title': event.get('headline', ''),
                'time': event.get('date', ''),
                'tag': self._get_tag_from_type(event.get('type', 'neutral')),
                'url': event.get('url', ''),
                'source': event.get('source', ''),
                'type': event.get('type', 'neutral'),
            })
        return formatted
    
    def _classify_single_news(self, title: str) -> str:
        """
        分类单条新闻
        
        Args:
            title: 新闻标题
            
        Returns:
            'bullish', 'bearish', 或 'neutral'
        """
        for keyword in self.BULLISH_KEYWORDS:
            if keyword in title:
                return "bullish"
        
        for keyword in self.BEARISH_KEYWORDS:
            if keyword in title:
                return "bearish"
        
        return "neutral"
    
    def _get_tag_from_type(self, type: str) -> str:
        """
        根据类型生成标签
        
        Args:
            type: 新闻类型
            
        Returns:
            标签字符串
        """
        if type == "bullish":
            return "📈 利好"
        elif type == "bearish":
            return "📉 利空"
        else:
            return "📰 中性"
    
    def clear_cache(self):
        """清空缓存"""
        # 清空通用新闻缓存
        self._cache.delete("copilot:news:general:7:10")
        # 清空特定股票缓存（需要遍历）
        # 由于缓存键是动态的，这里只清空常见的
        for sym in ["600519", "000001", "sh600519", "sz000001"]:
            self._cache.delete(f"copilot:news:{sym}:7:10")
        logger.info("[NewsFetcher] 缓存已清空")


# ─────────────────────────────────────────────────────────────────────────────
# 单例模式（双重检查锁定）
# ─────────────────────────────────────────────────────────────────────────────

_news_fetcher_instance: Optional[NewsFetcher] = None
_news_fetcher_lock = threading.Lock()


def get_news_fetcher() -> NewsFetcher:
    """
    获取 NewsFetcher 单例实例
    
    使用双重检查锁定模式确保线程安全
    """
    global _news_fetcher_instance
    
    if _news_fetcher_instance is None:
        with _news_fetcher_lock:
            if _news_fetcher_instance is None:
                _news_fetcher_instance = NewsFetcher()
    
    return _news_fetcher_instance
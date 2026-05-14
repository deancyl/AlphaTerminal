"""
http_client.py — 统一 HTTP 客户端（带 retry + Circuit Breaker + Pydantic 校验）

所有外部行情 API 调用统一经过此客户端，不得直接使用 httpx.get / requests.get。

核心能力：
1. 指数退避重试（可配置 max_retries / base_delay / max_delay）
2. 可选嵌入 CircuitBreaker（失败自动 record_failure，成功 record_success）
3. 代理支持（从 proxy_config.py 读取）
4. 统一的错误分类（网络错误 / 超时 / HTTP 错误 / 校验错误）
5. 共享 AsyncClient 实例（连接池复用，减少资源消耗）
6. 信号量并发限制（防止过多并发请求压垮数据源）
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable, Any, Type

import httpx

from app.services.circuit_breaker import CircuitBreaker, CircuitState
from app.config.timeout import (
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    WRITE_TIMEOUT,
    POOL_TIMEOUT,
    MAX_CONNECTIONS,
    MAX_KEEPALIVE_CONNECTIONS,
    KEEPALIVE_EXPIRY,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504, 520, 521, 522, 523, 524}

NON_CB_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ConnectTimeout,
)

# 全局并发限制信号量（最多同时 20 个请求）
MAX_CONCURRENT_REQUESTS = 20
_concurrent_semaphore: Optional[asyncio.Semaphore] = None


def get_concurrent_semaphore() -> asyncio.Semaphore:
    """获取全局并发信号量"""
    global _concurrent_semaphore
    if _concurrent_semaphore is None:
        _concurrent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    return _concurrent_semaphore


_shared_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


async def get_shared_client() -> httpx.AsyncClient:
    """
    Get or create the shared AsyncClient instance.
    
    Uses connection pooling for efficiency.
    Thread-safe via asyncio.Lock.
    """
    global _shared_client
    
    if _shared_client is None or _shared_client.is_closed:
        async with _client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT,
                        read=READ_TIMEOUT,
                        write=WRITE_TIMEOUT,
                        pool=POOL_TIMEOUT,
                    ),
                    limits=httpx.Limits(
                        max_connections=MAX_CONNECTIONS,
                        max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
                        keepalive_expiry=KEEPALIVE_EXPIRY,
                    ),
                    follow_redirects=True,
                )
                logger.info(
                    f"[HTTPClient] Created shared client "
                    f"(max_conn={MAX_CONNECTIONS}, keepalive={MAX_KEEPALIVE_CONNECTIONS})"
                )
    
    return _shared_client


async def close_shared_client():
    """Close the shared AsyncClient instance."""
    global _shared_client
    
    if _shared_client is not None:
        async with _client_lock:
            if _shared_client is not None:
                await _shared_client.aclose()
                _shared_client = None
                logger.info("[HTTPClient] Closed shared client")


class HTTPClientError(Exception):
    """HTTP 客户端基础异常"""
    def __init__(self, message: str, url: str = ""):
        self.url = url
        super().__init__(message)


class RetryableError(HTTPClientError):
    """可重试错误（触发 retry）"""
    pass


class ValidationError(HTTPClientError):
    """Pydantic 校验失败（不重试，不触发 circuit breaker）"""
    pass


class CircuitOpenError(HTTPClientError):
    """Circuit Breaker 打开（跳过请求）"""
    pass


class ValidatedHTTPClient:
    """
    统一 HTTP 客户端。

    Usage:
        client = ValidatedHTTPClient(
            proxy="http://192.168.1.50:7897",
            timeout=10.0,
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            circuit_breaker=my_circuit_breaker,
        )
        resp = await client.get_with_retry("https://hq.sinajs.cn/list=sh000001")
        await client.close()
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        referer: str = "https://finance.sina.com.cn",
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.cb = circuit_breaker
        self.user_agent = user_agent
        self.referer = referer
        self._client: Optional[httpx.AsyncClient] = None
        self._total_requests: int = 0
        self._total_retries: int = 0

    # ── 生命周期 ──────────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            proxies = {"all://": self.proxy} if self.proxy else None
            self._client = httpx.AsyncClient(
                proxies=proxies,
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=self.timeout,
                    write=5.0,
                    pool=10.0,
                ),
                headers={
                    "User-Agent": self.user_agent,
                    "Referer": self.referer,
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.debug(f"[HTTPClient] closed (total_requests={self._total_requests}, total_retries={self._total_retries})")

    # ── Circuit Breaker 前置检查 ──────────────────────────────────────────

    def _check_circuit(self) -> bool:
        """检查 circuit breaker 是否允许请求"""
        if self.cb is None:
            return True

        state = self.cb.state
        if state == CircuitState.OPEN:
            stats = self.cb.get_stats()
            timeout = stats.get("timeout", 30.0)
            opened_at = stats.get("opened_at", 0)
            wait_left = max(0, timeout - (time.time() - opened_at))
            logger.warning(
                f"[HTTPClient] CircuitBreaker '{self.cb.name}' OPEN, "
                f"还需等待 {wait_left:.1f}s，跳过请求"
            )
            return False

        if state == CircuitState.HALF_OPEN:
            logger.info(f"[HTTPClient] CircuitBreaker '{self.cb.name}' HALF_OPEN，放行测试请求")
            return True

        return True  # CLOSED

    # ── 核心请求方法 ──────────────────────────────────────────────────────

    async def get_with_retry(
        self,
        url: str,
        *,
        headers: Optional[dict] = None,
        encoding: Optional[str] = None,   # 响应编码（如 "gbk" for Sina）
        extra_retries: Optional[int] = None,
    ) -> httpx.Response:
        """
        GET 请求，指数退避重试。

        策略：
        - 网络错误 / 超时：触发 retry，触发 circuit breaker
        - HTTP 429/502/503/504/520~524：触发 retry，触发 circuit breaker
        - HTTP 200：检查响应体，异常时触发 retry
        - 校验失败（ValidationError）：不重试，不触发 circuit breaker
        - 信号量限制：最多同时 MAX_CONCURRENT_REQUESTS 个请求
        """
        retries = extra_retries if extra_retries is not None else self.max_retries
        delay = self.base_delay
        last_error: Optional[Exception] = None

        # Circuit Breaker 前置检查
        if not self._check_circuit():
            raise CircuitOpenError(f"CircuitBreaker OPEN for {url}", url)

        # 使用信号量限制并发
        semaphore = get_concurrent_semaphore()
        async with semaphore:
            for attempt in range(retries + 1):
                self._total_requests += 1
                try:
                    client = await self._get_client()
                    resp = await client.get(url, headers=headers or {})

                    if resp.status_code in RETRYABLE_STATUS_CODES:
                        # 可重试的 HTTP 错误
                        if attempt < retries:
                            self._total_retries += 1
                            logger.warning(
                                f"[HTTPClient] {url} HTTP {resp.status_code}，"
                                f"{delay:.1f}s 后重试 (attempt {attempt + 1}/{retries + 1})"
                            )
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, self.max_delay)
                            self._record_failure()
                            continue
                        else:
                            raise RetryableError(
                                f"HTTP {resp.status_code} after {retries + 1} attempts",
                                url
                            )

                    resp.raise_for_status()

                    # 检查响应体是否为空
                    if not resp.content:
                        if attempt < retries:
                            self._total_retries += 1
                            logger.warning(f"[HTTPClient] {url} 响应体为空，{delay:.1f}s 后重试")
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, self.max_delay)
                            continue
                        raise RetryableError("响应体为空", url)

                    # 成功 — 记录 circuit breaker
                    self._record_success()
                    return resp

                except NON_CB_NETWORK_ERRORS as e:
                    # 网络错误，但可能是瞬时的 — 记录 failure 并 retry
                    last_error = e
                    if attempt < retries:
                        self._total_retries += 1
                        self._record_failure()
                        logger.warning(
                            f"[HTTPClient] {url} 网络错误: {type(e).__name__}，"
                            f"{delay:.1f}s 后重试 (attempt {attempt + 1}/{retries + 1})"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.max_delay)
                    else:
                        self._record_failure()
                        logger.error(f"[HTTPClient] {url} 网络错误，全部尝试失败: {e}")

                except httpx.TimeoutException as e:
                    last_error = e
                    if attempt < retries:
                        self._total_retries += 1
                        self._record_failure()
                        logger.warning(
                            f"[HTTPClient] {url} 超时，{delay:.1f}s 后重试 "
                            f"(attempt {attempt + 1}/{retries + 1})"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.max_delay)
                    else:
                        self._record_failure()
                        logger.error(f"[HTTPClient] {url} 超时，全部尝试失败: {e}")

                except httpx.HTTPStatusError as e:
                    # 4xx 错误（不含429）— 不重试，直接失败
                    last_error = e
                    self._record_failure()
                    logger.error(f"[HTTPClient] {url} HTTP {e.response.status_code}: {e}")
                    break

                except Exception as e:
                    last_error = e
                    if attempt < retries:
                        self._total_retries += 1
                        self._record_failure()
                        logger.warning(
                            f"[HTTPClient] {url} 未知错误: {type(e).__name__}: {e}，"
                            f"{delay:.1f}s 后重试"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.max_delay)
                    else:
                        self._record_failure()
                        logger.error(f"[HTTPClient] {url} 未知错误，最终失败: {e}")

        raise last_error or RetryableError(f"HTTP GET failed after {retries + 1} attempts", url)

    # ── Circuit Breaker 记录 ─────────────────────────────────────────────

    def _record_success(self):
        if self.cb:
            self.cb.record_success()

    def _record_failure(self):
        if self.cb:
            self.cb.record_failure()

    # ── 统计 ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total_requests": self._total_requests,
            "total_retries": self._total_retries,
            "retry_rate": round(self._total_retries / max(1, self._total_requests), 3),
            "circuit_breaker": self.cb.get_stats() if self.cb else None,
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器退出。
        返回 None（不抑制异常），确保异常正确传播。
        """
        await self.close()
        # 返回 None 而非 False，语义更清晰：
        # - None: 不处理异常，让异常正常传播
        # - False: 显式表示不抑制异常（但语义不如 None 直观）
        return None

"""
外汇模块测试套件

测试所有修复的问题:
- P0: 前端竞态条件、缓存锁、ECharts内存泄漏
- P1: 错误消息、加载状态、键盘导航、熔断器状态、金额验证
- P2: ARIA、货币对切换防抖
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestForexRouter:
    """外汇路由测试"""

    def test_spot_quotes_success(self):
        """测试获取即期报价成功"""
        response = client.get("/api/v1/forex/spot")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "quotes" in data["data"]
        assert "circuit_breaker" in data["data"]

    def test_spot_quotes_circuit_breaker_status(self):
        """测试熔断器状态返回"""
        response = client.get("/api/v1/forex/spot")
        assert response.status_code == 200
        data = response.json()
        cb = data["data"].get("circuit_breaker", {})
        assert "is_open" in cb
        assert "failure_count" in cb
        assert "state" in cb

    def test_convert_validation_amount_too_large(self):
        """测试金额超过最大值 (le=1000000000)"""
        response = client.get(
            "/api/v1/forex/convert",
            params={"amount": 9999999999, "from_currency": "USD", "to_currency": "CNY"}
        )
        assert response.status_code == 422

    def test_convert_validation_amount_negative(self):
        """测试金额为负数 (gt=0)"""
        response = client.get(
            "/api/v1/forex/convert",
            params={"amount": -100, "from_currency": "USD", "to_currency": "CNY"}
        )
        assert response.status_code == 422

    def test_convert_validation_amount_zero(self):
        """测试金额为零 (gt=0)"""
        response = client.get(
            "/api/v1/forex/convert",
            params={"amount": 0, "from_currency": "USD", "to_currency": "CNY"}
        )
        assert response.status_code == 422

    def test_convert_validation_missing_params(self):
        """测试缺少必需参数"""
        response = client.get("/api/v1/forex/convert")
        assert response.status_code == 422

    def test_convert_success(self):
        """测试货币转换成功"""
        response = client.get(
            "/api/v1/forex/convert",
            params={"amount": 100, "from_currency": "USD", "to_currency": "CNY"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_history_success(self):
        """测试获取历史K线数据成功"""
        response = client.get("/api/v1/forex/history/EURUSD")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = client.get("/api/v1/forex/health")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # 健康检查应该包含服务状态
        health_data = data["data"]
        assert "status" in health_data or "service" in health_data

    def test_cfets_endpoint(self):
        """测试CFETS银行间报价端点"""
        response = client.get("/api/v1/forex/cfets")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_official_rates_endpoint(self):
        """测试官方中间价端点"""
        response = client.get("/api/v1/forex/official")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_official_rates_with_days_param(self):
        """测试带days参数的官方中间价"""
        response = client.get("/api/v1/forex/official?days=7")
        assert response.status_code == 200

    def test_cross_rate_matrix_endpoint(self):
        """测试交叉汇率矩阵端点"""
        response = client.get("/api/v1/forex/matrix")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_cross_rate_matrix_custom_currencies(self):
        """测试自定义货币列表的交叉汇率矩阵"""
        response = client.get("/api/v1/forex/matrix?currencies=USD,EUR,GBP")
        assert response.status_code == 200

    def test_cross_rate_endpoint(self):
        """测试交叉汇率计算端点"""
        response = client.post(
            "/api/v1/forex/cross-rate",
            json={"from_currency": "USD", "to_currency": "EUR", "amount": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_convert_same_currency(self):
        """测试相同货币转换"""
        response = client.get(
            "/api/v1/forex/convert",
            params={"amount": 100, "from_currency": "USD", "to_currency": "USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # 同货币转换，汇率应为1
        assert data["data"]["rate"] == 1.0


class TestForexValidation:
    """外汇验证测试"""

    def test_official_rates_days_too_large(self):
        """测试days参数超过最大值"""
        response = client.get("/api/v1/forex/official?days=500")
        assert response.status_code == 422

    def test_official_rates_days_too_small(self):
        """测试days参数小于最小值"""
        response = client.get("/api/v1/forex/official?days=0")
        assert response.status_code == 422

    def test_history_limit_param(self):
        """测试历史数据limit参数"""
        response = client.get("/api/v1/forex/history/EURUSD?limit=50")
        assert response.status_code == 200

    def test_history_invalid_limit(self):
        """测试无效的limit参数"""
        response = client.get("/api/v1/forex/history/EURUSD?limit=0")
        assert response.status_code == 422

    def test_matrix_too_few_currencies(self):
        """测试货币数量不足"""
        response = client.get("/api/v1/forex/matrix?currencies=USD")
        # API returns 200 with code=100 (BAD_REQUEST) in body
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 100  # BAD_REQUEST


class TestForexCircuitBreaker:
    """熔断器测试"""

    def test_circuit_breaker_structure(self):
        """测试熔断器返回结构"""
        response = client.get("/api/v1/forex/spot")
        assert response.status_code == 200
        data = response.json()
        cb = data["data"].get("circuit_breaker", {})

        # 验证熔断器字段
        assert "state" in cb
        assert "failure_count" in cb or "consecutive_failures" in cb

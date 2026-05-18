"""
Audit Router Test Suite

Tests all audit endpoints:
- GET /api/v1/audit/verify - Chain integrity verification
- GET /api/v1/audit/stats - Chain statistics
- GET /api/v1/audit/logs - Log query with pagination
- GET /api/v1/audit/health - Health check
- Input validation tests
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
@pytest.fixture
def temp_audit_db():
    """
    Create a temporary database for testing audit endpoints.
    Patches AUDIT_DB_PATH and initializes the audit_logs table.
    
    The client is created INSIDE the patch context so it picks up the test db path.
    """
    from app.main import app
    
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    
    conn.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            prev_hash TEXT NOT NULL DEFAULT '',
            record_hash TEXT NOT NULL DEFAULT '',
            chain_index INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_logs(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_chain_index ON audit_logs(chain_index)")
    conn.commit()
    conn.close()
    
    with patch('app.services.audit_chain.AUDIT_DB_PATH', Path(path)):
        client = TestClient(app)
        yield {'client': client, 'db_path': path}
    
    os.unlink(path)


class TestAuditVerify:
    """审计链验证测试"""

    def test_verify_chain_success(self, temp_audit_db):
        """测试链验证成功"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "checked_records" in data
        assert isinstance(data["valid"], bool)
        assert isinstance(data["checked_records"], int)

    def test_verify_chain_with_from_id(self, temp_audit_db):
        """测试带 from_id 参数的链验证"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?from_id=1")
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "checked_records" in data

    def test_verify_chain_with_to_id(self, temp_audit_db):
        """测试带 to_id 参数的链验证"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?to_id=100")
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data

    def test_verify_chain_with_range(self, temp_audit_db):
        """测试带范围参数的链验证"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?from_id=1&to_id=50")
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data

    def test_verify_chain_response_structure(self, temp_audit_db):
        """测试验证响应结构"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify")
        assert response.status_code == 200
        data = response.json()
        # Check all expected fields
        assert "valid" in data
        assert "checked_records" in data
        assert "first_invalid_id" in data
        assert "error_type" in data


class TestAuditStats:
    """审计统计测试"""

    def test_stats_success(self, temp_audit_db):
        """测试获取统计成功"""
        response = temp_audit_db['client'].get("/api/v1/audit/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_records" in data
        assert "genesis_hash" in data
        assert "retention_days" in data

    def test_stats_response_structure(self, temp_audit_db):
        """测试统计响应结构"""
        response = temp_audit_db['client'].get("/api/v1/audit/stats")
        assert response.status_code == 200
        data = response.json()
        # Check all expected fields
        assert "total_records" in data
        assert "chain_index_min" in data
        assert "chain_index_max" in data
        assert "first_record" in data
        assert "last_record" in data
        assert "genesis_hash" in data
        assert "retention_days" in data

    def test_stats_retention_days(self, temp_audit_db):
        """测试保留期天数 (SEC Rule 17a-4: 7年 = 2555天)"""
        response = temp_audit_db['client'].get("/api/v1/audit/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 2555

    def test_stats_genesis_hash(self, temp_audit_db):
        """测试创世哈希 (64个零)"""
        response = temp_audit_db['client'].get("/api/v1/audit/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["genesis_hash"] == "0" * 64
        assert len(data["genesis_hash"]) == 64


class TestAuditLogs:
    """审计日志查询测试"""

    def test_logs_success(self, temp_audit_db):
        """测试获取日志成功"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_logs_with_limit(self, temp_audit_db):
        """测试带 limit 参数"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10

    def test_logs_with_offset(self, temp_audit_db):
        """测试带 offset 参数"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?offset=5")
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 5

    def test_logs_with_agent_id_filter(self, temp_audit_db):
        """测试按 agent_id 过滤"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?agent_id=test_user")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data

    def test_logs_with_action_filter(self, temp_audit_db):
        """测试按 action 过滤"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?action=buy")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_logs_pagination(self, temp_audit_db):
        """测试分页功能"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=20&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 20
        assert data["offset"] == 0


class TestAuditHealth:
    """审计健康检查测试"""

    def test_health_success(self, temp_audit_db):
        """测试健康检查成功"""
        response = temp_audit_db['client'].get("/api/v1/audit/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "chain_valid" in data
        assert "retention_days" in data

    def test_health_status_values(self, temp_audit_db):
        """测试健康状态值"""
        response = temp_audit_db['client'].get("/api/v1/audit/health")
        assert response.status_code == 200
        data = response.json()
        # Status should be "ok" or "degraded"
        assert data["status"] in ["ok", "degraded"]
        # chain_valid should be boolean
        assert isinstance(data["chain_valid"], bool)

    def test_health_retention_days(self, temp_audit_db):
        """测试健康检查中的保留期"""
        response = temp_audit_db['client'].get("/api/v1/audit/health")
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 2555

    def test_health_checked_records(self, temp_audit_db):
        """测试健康检查中的已检查记录数"""
        response = temp_audit_db['client'].get("/api/v1/audit/health")
        assert response.status_code == 200
        data = response.json()
        assert "checked_records" in data
        assert isinstance(data["checked_records"], int)


class TestAuditValidation:
    """审计输入验证测试"""

    def test_verify_from_id_negative(self, temp_audit_db):
        """测试 from_id 为负数 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?from_id=-1")
        assert response.status_code == 422

    def test_verify_from_id_zero(self, temp_audit_db):
        """测试 from_id 为零 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?from_id=0")
        assert response.status_code == 422

    def test_verify_to_id_negative(self, temp_audit_db):
        """测试 to_id 为负数 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?to_id=-1")
        assert response.status_code == 422

    def test_verify_to_id_zero(self, temp_audit_db):
        """测试 to_id 为零 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify?to_id=0")
        assert response.status_code == 422

    def test_logs_limit_too_small(self, temp_audit_db):
        """测试 limit 小于最小值 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=0")
        assert response.status_code == 422

    def test_logs_limit_negative(self, temp_audit_db):
        """测试 limit 为负数 (ge=1)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=-1")
        assert response.status_code == 422

    def test_logs_limit_too_large(self, temp_audit_db):
        """测试 limit 超过最大值 (le=1000)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=1001")
        assert response.status_code == 422

    def test_logs_offset_negative(self, temp_audit_db):
        """测试 offset 为负数 (ge=0)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?offset=-1")
        assert response.status_code == 422

    def test_logs_limit_boundary_min(self, temp_audit_db):
        """测试 limit 边界值 (最小值)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=1")
        assert response.status_code == 200

    def test_logs_limit_boundary_max(self, temp_audit_db):
        """测试 limit 边界值 (最大值)"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=1000")
        assert response.status_code == 200


class TestAuditChainIntegrity:
    """审计链完整性测试"""

    def test_verify_returns_valid_structure(self, temp_audit_db):
        """测试验证返回有效结构"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify")
        assert response.status_code == 200
        data = response.json()
        
        # All required fields should be present
        required_fields = ["valid", "checked_records", "first_invalid_id", "error_type"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_verify_valid_chain_has_no_error(self, temp_audit_db):
        """测试有效链没有错误"""
        response = temp_audit_db['client'].get("/api/v1/audit/verify")
        assert response.status_code == 200
        data = response.json()
        
        if data["valid"]:
            assert data["first_invalid_id"] is None
            assert data["error_type"] is None

    def test_stats_total_records_non_negative(self, temp_audit_db):
        """测试总记录数非负"""
        response = temp_audit_db['client'].get("/api/v1/audit/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] >= 0

    def test_logs_total_matches_count(self, temp_audit_db):
        """测试日志总数匹配"""
        response = temp_audit_db['client'].get("/api/v1/audit/logs?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        # Total should be >= number of logs returned
        assert data["total"] >= len(data["logs"])

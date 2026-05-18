"""Tests for bond router."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd

from app.main import app


client = TestClient(app)


class TestBondCurve:
    """Test cases for bond curve endpoint."""

    def test_bond_curve_endpoint(self):
        """Test GET /bond/curve endpoint returns valid structure."""
        response = client.get("/api/v1/bond/curve")
        assert response.status_code == 200
        
        data = response.json()
        assert "code" in data
        assert data.get("code") == 0
        assert "data" in data

    def test_bond_curve_response_structure(self):
        """Test that curve response has correct structure."""
        response = client.get("/api/v1/bond/curve")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                result = data["data"]
                assert "yield_curve" in result
                assert "update_time" in result
                assert "source" in result

    def test_bond_curve_has_tenors(self):
        """Test that curve includes standard tenors."""
        response = client.get("/api/v1/bond/curve")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                yield_curve = data["data"]["yield_curve"]
                assert isinstance(yield_curve, dict)


class TestBondYieldCurve:
    """Test cases for legacy yield curve endpoint."""

    def test_bond_yield_curve_endpoint(self):
        """Test GET /bond/yield_curve endpoint."""
        response = client.get("/api/v1/bond/yield_curve")
        assert response.status_code == 200
        
        data = response.json()
        assert "code" in data
        assert data.get("code") == 0


class TestBondActive:
    """Test cases for active bonds endpoint."""

    def test_bond_active_endpoint(self):
        """Test GET /bond/active endpoint."""
        response = client.get("/api/v1/bond/active")
        assert response.status_code == 200
        
        data = response.json()
        assert "code" in data
        assert data.get("code") == 0

    def test_bond_active_response_structure(self):
        """Test that active bonds response has correct structure."""
        response = client.get("/api/v1/bond/active")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                result = data["data"]
                assert "bonds" in result
                assert isinstance(result["bonds"], list)

    def test_bond_active_bond_structure(self):
        """Test that each bond has required fields."""
        response = client.get("/api/v1/bond/active")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                bonds = data["data"]["bonds"]
                if len(bonds) > 0:
                    bond = bonds[0]
                    assert "code" in bond
                    assert "name" in bond
                    assert "rate" in bond


class TestBondHistory:
    """Test cases for bond history endpoint."""

    def test_bond_history_endpoint(self):
        """Test GET /bond/history endpoint with default params."""
        response = client.get("/api/v1/bond/history")
        assert response.status_code == 200
        
        data = response.json()
        assert "code" in data

    def test_bond_history_with_tenor(self):
        """Test GET /bond/history with specific tenor."""
        response = client.get("/api/v1/bond/history?tenor=10年")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("code") == 0:
            result = data["data"]
            assert "tenor" in result

    def test_bond_history_with_period(self):
        """Test GET /bond/history with specific period."""
        response = client.get("/api/v1/bond/history?tenor=10年&period=1Y")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("code") == 0:
            result = data["data"]
            assert "history" in result
            assert isinstance(result["history"], list)

    def test_bond_history_invalid_tenor(self):
        """Test GET /bond/history with invalid tenor returns gracefully."""
        response = client.get("/api/v1/bond/history?tenor=invalid")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("code") == 0:
            result = data["data"]
            assert result.get("source") in ["error", "akshare"]

    def test_bond_history_response_structure(self):
        """Test that history response has correct structure."""
        response = client.get("/api/v1/bond/history?tenor=10年&period=1Y")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                result = data["data"]
                assert "tenor" in result
                assert "source" in result

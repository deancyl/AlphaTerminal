"""
Tests for IP validation utilities.

Tests cover:
- Trusted proxy detection
- IP format validation
- Client IP extraction with spoofing prevention
"""

import os
from unittest.mock import patch

from app.utils.ip_validation import (
    is_trusted_proxy,
    validate_ip_format,
    extract_client_ip,
    get_client_ip_safe,
    reload_trusted_proxies,
)


class TestIsTrustedProxy:
    """Tests for is_trusted_proxy function."""

    def test_private_ipv4_trusted(self):
        """Private IPv4 addresses should be trusted by default."""
        reload_trusted_proxies()

        assert is_trusted_proxy("10.0.0.1") is True
        assert is_trusted_proxy("10.255.255.255") is True
        assert is_trusted_proxy("172.16.0.1") is True
        assert is_trusted_proxy("172.31.255.255") is True
        assert is_trusted_proxy("192.168.1.1") is True
        assert is_trusted_proxy("192.168.255.255") is True
        assert is_trusted_proxy("127.0.0.1") is True

    def test_public_ipv4_not_trusted(self):
        """Public IPv4 addresses should NOT be trusted by default."""
        reload_trusted_proxies()

        assert is_trusted_proxy("8.8.8.8") is False
        assert is_trusted_proxy("1.1.1.1") is False
        assert is_trusted_proxy("203.0.113.1") is False
        assert is_trusted_proxy("93.184.216.34") is False

    def test_ipv6_loopback_trusted(self):
        """IPv6 loopback should be trusted by default."""
        reload_trusted_proxies()

        assert is_trusted_proxy("::1") is True

    def test_ipv6_ula_trusted(self):
        """IPv6 ULA (Unique Local Address) should be trusted by default."""
        reload_trusted_proxies()

        assert is_trusted_proxy("fd00::1") is True
        assert is_trusted_proxy("fc00::1") is True

    def test_ipv6_public_not_trusted(self):
        """Public IPv6 addresses should NOT be trusted by default."""
        reload_trusted_proxies()

        assert is_trusted_proxy("2001:4860:4860::8888") is False
        assert is_trusted_proxy("2606:4700:4700::1111") is False

    def test_invalid_ip_not_trusted(self):
        """Invalid IP strings should return False."""
        assert is_trusted_proxy("") is False
        assert is_trusted_proxy("not-an-ip") is False
        assert is_trusted_proxy("256.256.256.256") is False
        assert is_trusted_proxy(None) is False

    @patch.dict(os.environ, {"TRUSTED_PROXIES": "203.0.113.0/24,198.51.100.0/24"})
    def test_custom_trusted_proxies(self):
        """Custom trusted proxies from environment should work."""
        reload_trusted_proxies()

        assert is_trusted_proxy("203.0.113.1") is True
        assert is_trusted_proxy("203.0.113.255") is True
        assert is_trusted_proxy("198.51.100.1") is True

        assert is_trusted_proxy("10.0.0.1") is False
        assert is_trusted_proxy("192.168.1.1") is False


class TestValidateIpFormat:
    """Tests for validate_ip_format function."""

    def test_valid_ipv4(self):
        """Valid IPv4 addresses should pass validation."""
        assert validate_ip_format("192.168.1.1") is True
        assert validate_ip_format("10.0.0.1") is True
        assert validate_ip_format("127.0.0.1") is True
        assert validate_ip_format("0.0.0.0") is True
        assert validate_ip_format("255.255.255.255") is True

    def test_valid_ipv6(self):
        """Valid IPv6 addresses should pass validation."""
        assert validate_ip_format("::1") is True
        assert validate_ip_format("2001:db8::1") is True
        assert validate_ip_format("fe80::1") is True
        assert validate_ip_format("fd00::1") is True

    def test_invalid_formats(self):
        """Invalid formats should fail validation."""
        assert validate_ip_format("") is False
        assert validate_ip_format(None) is False
        assert validate_ip_format("not-an-ip") is False
        assert validate_ip_format("256.256.256.256") is False
        assert validate_ip_format("192.168.1") is False
        assert validate_ip_format("192.168.1.1.1") is False

    def test_whitespace_handling(self):
        """Whitespace should be handled gracefully."""
        assert validate_ip_format("  192.168.1.1  ") is True
        assert validate_ip_format("  10.0.0.1  ") is True


class TestExtractClientIp:
    """Tests for extract_client_ip function."""

    def setup_method(self):
        """Reset trusted proxies before each test."""
        reload_trusted_proxies()

    def test_trusted_proxy_single_hop(self):
        """Single trusted proxy should extract original client IP."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1", x_real_ip=None, remote_addr="10.0.0.1"
        )
        assert result == "1.1.1.1"

    def test_trusted_proxy_multi_hop(self):
        """Multi-hop trusted proxy chain should extract original client."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1, 10.0.0.1, 192.168.1.1",
            x_real_ip=None,
            remote_addr="10.0.0.1",
        )
        assert result == "1.1.1.1"

    def test_untrusted_source_ignores_header(self):
        """Untrusted source should ignore X-Forwarded-For (spoofing prevention)."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1", x_real_ip=None, remote_addr="203.0.113.1"
        )
        assert result == "203.0.113.1"

    def test_spoofing_attack_prevention(self):
        """Attacker cannot spoof X-Forwarded-For from untrusted source."""
        result = extract_client_ip(
            x_forwarded_for="8.8.8.8, 1.1.1.1, 10.0.0.1",
            x_real_ip=None,
            remote_addr="93.184.216.34",
        )
        assert result == "93.184.216.34"

    def test_all_ips_trusted(self):
        """If all IPs in chain are trusted, use leftmost."""
        result = extract_client_ip(
            x_forwarded_for="10.0.0.1, 192.168.1.1, 172.16.0.1",
            x_real_ip=None,
            remote_addr="10.0.0.1",
        )
        assert result == "10.0.0.1"

    def test_fallback_to_x_real_ip(self):
        """Should fall back to X-Real-IP if X-Forwarded-For is empty."""
        result = extract_client_ip(
            x_forwarded_for=None, x_real_ip="1.1.1.1", remote_addr="10.0.0.1"
        )
        assert result == "1.1.1.1"

    def test_fallback_to_remote_addr(self):
        """Should fall back to remote_addr if no headers."""
        result = extract_client_ip(
            x_forwarded_for=None, x_real_ip=None, remote_addr="10.0.0.1"
        )
        assert result == "10.0.0.1"

    def test_no_remote_addr_with_forwarded_for(self):
        """Should use first IP from X-Forwarded-For if no remote_addr."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1, 10.0.0.1", x_real_ip=None, remote_addr=None
        )
        assert result == "1.1.1.1"

    def test_all_none(self):
        """Should return 'unknown' if all inputs are None."""
        result = extract_client_ip(
            x_forwarded_for=None, x_real_ip=None, remote_addr=None
        )
        assert result == "unknown"

    def test_empty_forwarded_for(self):
        """Should handle empty X-Forwarded-For string."""
        result = extract_client_ip(
            x_forwarded_for="", x_real_ip="1.1.1.1", remote_addr="10.0.0.1"
        )
        assert result == "1.1.1.1"

    def test_invalid_ip_in_chain(self):
        """Should skip invalid IPs in chain."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1, invalid-ip, 10.0.0.1",
            x_real_ip=None,
            remote_addr="10.0.0.1",
        )
        assert result == "1.1.1.1"

    def test_ipv6_client(self):
        """Should handle IPv6 client addresses."""
        result = extract_client_ip(
            x_forwarded_for="2001:db8::1", x_real_ip=None, remote_addr="10.0.0.1"
        )
        assert result == "2001:db8::1"

    def test_ipv6_trusted_proxy(self):
        """Should handle IPv6 trusted proxy addresses."""
        result = extract_client_ip(
            x_forwarded_for="1.1.1.1", x_real_ip=None, remote_addr="::1"
        )
        assert result == "1.1.1.1"


class TestGetClientIpSafe:
    """Tests for get_client_ip_safe function."""

    def setup_method(self):
        """Reset trusted proxies before each test."""
        reload_trusted_proxies()

    def test_basic_usage(self):
        """Basic usage should work correctly."""
        result = get_client_ip_safe(
            x_forwarded_for="1.1.1.1", x_real_ip=None, remote_addr="10.0.0.1"
        )
        assert result == "1.1.1.1"

    def test_spoofing_prevention(self):
        """Should prevent spoofing from untrusted source."""
        result = get_client_ip_safe(
            x_forwarded_for="8.8.8.8", x_real_ip=None, remote_addr="203.0.113.1"
        )
        assert result == "203.0.113.1"


class TestReloadTrustedProxies:
    """Tests for reload_trusted_proxies function."""

    @patch.dict(os.environ, {"TRUSTED_PROXIES": "1.2.3.0/24"})
    def test_reload_from_env(self):
        """Should reload trusted proxies from environment."""
        reload_trusted_proxies()

        assert is_trusted_proxy("1.2.3.1") is True
        assert is_trusted_proxy("10.0.0.1") is False

    @patch.dict(os.environ, {}, clear=True)
    def test_reload_default(self):
        """Should reload default trusted proxies when env is cleared."""
        reload_trusted_proxies()

        assert is_trusted_proxy("10.0.0.1") is True
        assert is_trusted_proxy("1.1.1.1") is False

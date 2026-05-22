"""
IP Validation Utilities for Trusted Proxy Verification

Prevents IP spoofing attacks by validating X-Forwarded-For headers
against a list of trusted proxy CIDR ranges.
"""

import os
import logging
from typing import Optional, Set
from ipaddress import ip_address, ip_network, IPv4Network, IPv6Network

logger = logging.getLogger(__name__)

# Global cache for trusted proxy networks
_trusted_proxies: Optional[Set[IPv4Network | IPv6Network]] = None


def _load_trusted_proxies() -> Set[IPv4Network | IPv6Network]:
    """
    Load trusted proxy CIDR ranges from environment variable.
    
    Environment variable format:
        TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
    
    Default (if not configured):
        - 10.0.0.0/8 (Class A private)
        - 172.16.0.0/12 (Class B private)
        - 192.168.0.0/16 (Class C private)
        - 127.0.0.0/8 (Loopback)
        - ::1/128 (IPv6 loopback)
        - fc00::/7 (IPv6 ULA)
    
    Returns:
        Set of ip_network objects representing trusted proxy ranges
    """
    global _trusted_proxies

    if _trusted_proxies is not None:
        return _trusted_proxies

    proxies_str = os.environ.get("TRUSTED_PROXIES", "")

    if proxies_str:
        # Parse from environment variable
        cidr_list = [cidr.strip() for cidr in proxies_str.split(",") if cidr.strip()]
        logger.info(f"[IPValidation] Loading trusted proxies from env: {cidr_list}")
    else:
        # Default: trust private networks
        cidr_list = [
            "10.0.0.0/8",      # Class A private
            "172.16.0.0/12",   # Class B private
            "192.168.0.0/16",  # Class C private
            "127.0.0.0/8",     # Loopback
            "::1/128",         # IPv6 loopback
            "fc00::/7",        # IPv6 ULA
        ]
        logger.info("[IPValidation] Using default trusted proxies (private networks)")

    networks: Set[IPv4Network | IPv6Network] = set()

    for cidr in cidr_list:
        try:
            network = ip_network(cidr, strict=False)
            networks.add(network)
        except ValueError as e:
            logger.warning(f"[IPValidation] Invalid CIDR '{cidr}': {e}", exc_info=True)

    _trusted_proxies = networks
    logger.info(f"[IPValidation] Loaded {len(networks)} trusted proxy ranges")

    return _trusted_proxies


def is_trusted_proxy(ip_str: str) -> bool:
    """
    Check if an IP address is in the trusted proxy list.
    
    Args:
        ip_str: IP address string (IPv4 or IPv6)
    
    Returns:
        True if IP is in a trusted proxy CIDR range, False otherwise
    """
    if not ip_str:
        return False

    try:
        ip = ip_address(ip_str.strip())
    except ValueError:
        return False

    trusted_networks = _load_trusted_proxies()

    for network in trusted_networks:
        try:
            if ip in network:
                return True
        except TypeError:
            # IPv4 address cannot be in IPv6 network and vice versa
            continue

    return False


def validate_ip_format(ip_str: str) -> bool:
    """
    Validate that a string is a valid IP address format.
    
    Args:
        ip_str: String to validate
    
    Returns:
        True if valid IPv4 or IPv6 address, False otherwise
    """
    if not ip_str:
        return False

    try:
        ip_address(ip_str.strip())
        return True
    except ValueError:
        return False


def extract_client_ip(
    x_forwarded_for: Optional[str],
    x_real_ip: Optional[str],
    remote_addr: Optional[str]
) -> str:
    """
    Extract the real client IP from request headers.
    
    Security Logic:
        1. If remote_addr is NOT from a trusted proxy, use remote_addr directly
           (untrusted source, ignore X-Forwarded-For to prevent spoofing)
        2. If remote_addr IS from a trusted proxy, parse X-Forwarded-For
           and find the rightmost non-trusted IP (the original client)
        3. If X-Forwarded-For is empty or all IPs are trusted, fall back to
           X-Real-IP or remote_addr
    
    Args:
        x_forwarded_for: Value of X-Forwarded-For header (comma-separated IPs)
        x_real_ip: Value of X-Real-IP header
        remote_addr: Direct connection IP (from request.client.host)
    
    Returns:
        The real client IP address
    
    Example:
        # Trusted proxy scenario (remote_addr = 10.0.0.1, trusted)
        # X-Forwarded-For: 1.1.1.1, 10.0.0.1
        # Returns: 1.1.1.1 (the original client)
        
        # Untrusted source scenario (remote_addr = 203.0.113.1, not trusted)
        # X-Forwarded-For: 1.1.1.1 (spoofed)
        # Returns: 203.0.113.1 (ignore spoofed header)
    """
    # Step 1: Check if remote_addr is from a trusted proxy
    if not remote_addr:
        # No direct connection IP, fall back to headers
        if x_forwarded_for:
            # Take the first IP (leftmost) as a best guess
            first_ip = x_forwarded_for.split(",")[0].strip()
            if validate_ip_format(first_ip):
                return first_ip
        if x_real_ip:
            real_ip = x_real_ip.strip()
            if validate_ip_format(real_ip):
                return real_ip
        return "unknown"

    # Step 2: If remote_addr is NOT trusted, ignore X-Forwarded-For
    # (prevents spoofing from untrusted sources)
    if not is_trusted_proxy(remote_addr):
        logger.debug(f"[IPValidation] Untrusted source {remote_addr}, ignoring X-Forwarded-For")
        return remote_addr

    # Step 3: remote_addr IS trusted, parse X-Forwarded-For
    if x_forwarded_for:
        # Parse IPs from right to left
        # Format: client, proxy1, proxy2, ...
        # The rightmost non-trusted IP is the original client
        ips = [ip.strip() for ip in x_forwarded_for.split(",")]

        # Iterate from right to left
        for ip in reversed(ips):
            if validate_ip_format(ip) and not is_trusted_proxy(ip):
                logger.debug(f"[IPValidation] Extracted client IP {ip} from trusted proxy chain")
                return ip

        # All IPs in chain are trusted, use the leftmost
        if ips and validate_ip_format(ips[0]):
            logger.debug(f"[IPValidation] All IPs trusted, using leftmost: {ips[0]}")
            return ips[0]

    # Step 4: Fall back to X-Real-IP
    if x_real_ip:
        real_ip = x_real_ip.strip()
        if validate_ip_format(real_ip):
            return real_ip

    # Step 5: Use remote_addr as last resort
    return remote_addr


def get_client_ip_safe(
    x_forwarded_for: Optional[str],
    x_real_ip: Optional[str],
    remote_addr: Optional[str]
) -> str:
    """
    Simplified version of extract_client_ip for use in middleware.
    
    Args:
        x_forwarded_for: Value of X-Forwarded-For header
        x_real_ip: Value of X-Real-IP header
        remote_addr: Direct connection IP
    
    Returns:
        The real client IP address (or "unknown" if all fail)
    """
    return extract_client_ip(x_forwarded_for, x_real_ip, remote_addr)


def reload_trusted_proxies():
    """
    Force reload of trusted proxies from environment.
    Useful for testing or dynamic configuration updates.
    """
    global _trusted_proxies
    _trusted_proxies = None
    _load_trusted_proxies()

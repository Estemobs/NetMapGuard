"""Tests for netmapguard.capture module."""

import pytest
from unittest.mock import MagicMock, patch

from netmapguard.capture import is_public_ip, get_connections, Connection


# ── is_public_ip ──────────────────────────────────────────────────────────

class TestIsPublicIp:
    def test_public_ipv4(self):
        assert is_public_ip("8.8.8.8") is True

    def test_public_ipv4_cloudflare(self):
        assert is_public_ip("1.1.1.1") is True

    def test_private_10(self):
        assert is_public_ip("10.0.0.1") is False

    def test_private_192_168(self):
        assert is_public_ip("192.168.1.1") is False

    def test_private_172_16(self):
        assert is_public_ip("172.20.0.1") is False

    def test_loopback(self):
        assert is_public_ip("127.0.0.1") is False

    def test_link_local(self):
        assert is_public_ip("169.254.0.1") is False

    def test_ipv6_loopback(self):
        assert is_public_ip("::1") is False

    def test_ipv6_link_local(self):
        assert is_public_ip("fe80::1") is False

    def test_public_ipv6(self):
        assert is_public_ip("2606:4700:4700::1111") is True

    def test_invalid_ip(self):
        assert is_public_ip("not-an-ip") is False

    def test_cgnat(self):
        assert is_public_ip("100.64.0.1") is False


# ── get_connections ───────────────────────────────────────────────────────

def _make_sconn(raddr_ip, raddr_port, laddr_ip="192.168.1.5", laddr_port=54321,
                status="ESTABLISHED", pid=1234, sock_type=1):  # 1 = SOCK_STREAM
    """Build a minimal psutil-style sconn namedtuple mock."""
    m = MagicMock()
    m.raddr = MagicMock()
    m.raddr.ip = raddr_ip
    m.raddr.port = raddr_port
    m.laddr = MagicMock()
    m.laddr.ip = laddr_ip
    m.laddr.port = laddr_port
    m.status = status
    m.pid = pid
    m.type = MagicMock()
    m.type.name = "SOCK_STREAM" if sock_type == 1 else "SOCK_DGRAM"
    return m


class TestGetConnections:
    def test_returns_public_established(self):
        conn = _make_sconn("8.8.8.8", 443)
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn]):
            with patch("netmapguard.capture.psutil.Process") as mock_proc:
                mock_proc.return_value.name.return_value = "chrome"
                result = get_connections()
        assert len(result) == 1
        c = result[0]
        assert c.remote_ip == "8.8.8.8"
        assert c.remote_port == 443
        assert c.proto == "TCP"
        assert c.process == "chrome"

    def test_skips_private_remote(self):
        conn = _make_sconn("192.168.1.100", 8080)
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn]):
            result = get_connections()
        assert result == []

    def test_skips_listen_status(self):
        conn = _make_sconn("8.8.8.8", 443, status="LISTEN")
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn]):
            result = get_connections()
        assert result == []

    def test_no_remote_addr_skipped(self):
        m = MagicMock()
        m.raddr = None
        with patch("netmapguard.capture.psutil.net_connections", return_value=[m]):
            result = get_connections()
        assert result == []

    def test_deduplication(self):
        """Two identical connections should appear only once."""
        conn = _make_sconn("8.8.8.8", 443)
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn, conn]):
            result = get_connections()
        assert len(result) == 1

    def test_access_denied_returns_empty(self):
        import psutil as _psutil
        with patch("netmapguard.capture.psutil.net_connections",
                   side_effect=_psutil.AccessDenied(0)):
            result = get_connections()
        assert result == []

    def test_udp_proto_label(self):
        conn = _make_sconn("8.8.8.8", 53, sock_type=2)
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn]):
            with patch("netmapguard.capture.psutil.Process") as mock_proc:
                mock_proc.return_value.name.return_value = "systemd-resolve"
                result = get_connections()
        if result:
            assert result[0].proto == "UDP"

    def test_connection_id_format(self):
        conn = _make_sconn("8.8.8.8", 443, laddr_ip="10.0.0.5", laddr_port=60000)
        with patch("netmapguard.capture.psutil.net_connections", return_value=[conn]):
            with patch("netmapguard.capture.psutil.Process") as mock_proc:
                mock_proc.return_value.name.return_value = "test"
                result = get_connections()
        assert len(result) == 1
        assert result[0].id == "10.0.0.5:60000-8.8.8.8:443-TCP"

    def test_to_dict_keys(self):
        c = Connection(
            id="a:1-b:2-TCP",
            local_ip="a", local_port=1,
            remote_ip="b", remote_port=2,
            proto="TCP", pid=42,
            process="test", status="ESTABLISHED",
        )
        d = c.to_dict()
        for key in ("id", "local_ip", "local_port", "remote_ip", "remote_port",
                    "proto", "pid", "process", "status"):
            assert key in d

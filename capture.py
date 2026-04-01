"""capture.py – poll live network connections via psutil (no root required)."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

# Private / link-local ranges we do NOT want to geolocate
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
]
_PRIVATE_NETS_V6 = [
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]


def is_public_ip(ip_str: str) -> bool:
    """Return True if *ip_str* is a routable public address."""
    try:
        addr = ipaddress.ip_address(ip_str)
        if addr.version == 6:
            return not any(addr in net for net in _PRIVATE_NETS_V6)
        return not any(addr in net for net in _PRIVATE_NETS)
    except ValueError:
        return False


@dataclass
class Connection:
    id: str
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    proto: str
    pid: Optional[int]
    process: Optional[str]
    status: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "local_ip": self.local_ip,
            "local_port": self.local_port,
            "remote_ip": self.remote_ip,
            "remote_port": self.remote_port,
            "proto": self.proto,
            "pid": self.pid,
            "process": self.process,
            "status": self.status,
        }


def get_connections() -> List[Connection]:
    """Return active TCP/UDP connections to public remote IPs."""
    results: List[Connection] = []
    seen_ids: set = set()

    try:
        raw = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        return results

    for conn in raw:
        # We only care about connections that have a remote address
        if not conn.raddr:
            continue
        remote_ip = conn.raddr.ip
        remote_port = conn.raddr.port

        if not is_public_ip(remote_ip):
            continue

        if conn.status not in ("ESTABLISHED", "SYN_SENT", "SYN_RECV", "CLOSE_WAIT"):
            continue

        local_ip = conn.laddr.ip if conn.laddr else ""
        local_port = conn.laddr.port if conn.laddr else 0

        # socket type: SOCK_STREAM=TCP, SOCK_DGRAM=UDP
        try:
            proto = conn.type.name  # e.g. "SOCK_STREAM"
        except AttributeError:
            proto = str(conn.type)
        proto = "TCP" if "STREAM" in proto else "UDP"

        conn_id = f"{local_ip}:{local_port}-{remote_ip}:{remote_port}-{proto}"
        if conn_id in seen_ids:
            continue
        seen_ids.add(conn_id)

        # Try to resolve process name
        proc_name: Optional[str] = None
        if conn.pid:
            try:
                proc_name = psutil.Process(conn.pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        results.append(
            Connection(
                id=conn_id,
                local_ip=local_ip,
                local_port=local_port,
                remote_ip=remote_ip,
                remote_port=remote_port,
                proto=proto,
                pid=conn.pid,
                process=proc_name,
                status=conn.status or "UNKNOWN",
            )
        )

    return results

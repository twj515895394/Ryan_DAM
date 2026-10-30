from __future__ import annotations

import socket


def detect_lan_ips() -> list[str]:
    """探测本机局域网 IPv4 地址集合（排除回环），供外部接口地址展示与发现文件写入。"""
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    # UDP connect 技巧仅用于让内核选出默认路由网卡，不会真正发包
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            ip = probe.getsockname()[0]
            if not ip.startswith("127."):
                ips.add(ip)
        finally:
            probe.close()
    except OSError:
        pass
    return sorted(ips)

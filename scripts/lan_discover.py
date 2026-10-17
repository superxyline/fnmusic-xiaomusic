#!/usr/bin/env python3
"""小爱音箱局域网探测工具 v3

小爱音箱是纯云端管控设备，局域网通常没有任何可探测服务（无 mDNS / 无 miIO /
无开放端口）。本工具用尽常规手段寻找并识别局域网设备，用于：
  1. 排查音箱是否在线、在哪台主机（结合 OUI 厂商库 + 反向 DNS）
  2. 摸清局域网小米生态设备分布
  3. 部署 xiaomusic 并绑定小米账号后，设备型号会自动出现在其设备列表中（最终以那个为准）

探测手段：
  A. mDNS（绑定 5353 组播口，按来源 IP 归因）：_miio / _airplay / _raop / 服务枚举
  B. SSDP M-SEARCH
  C. miIO UDP 54321 握手（全网段并发）
  D. 常见 TCP 端口扫描
  E. ARP 表 + Wireshark OUI 厂商库识别全部设备（库文件缓存 30 天）
  F. 反向 DNS（PTR）

用法：
  python lan_discover.py [--subnet 192.168.31] [--timeout 5] [--no-scan]
"""
import argparse
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request

MDNS_GROUP = ("224.0.0.251", 5353)
SSDP_GROUP = ("239.255.255.250", 1900)
MIIO_PORT = 54321
TCP_PORTS = [80, 443, 8080, 8009, 8443, 6095, 22, 7000, 49152]
MANUF_URL = "https://www.wireshark.org/download/automated/data/manuf"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".oui_cache.txt")
CACHE_TTL_DAYS = 30


# ---------- mDNS ----------
def build_mdns_query(name, qtype):
    header = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return header + qname + struct.pack(">HH", qtype, 1)


def read_name(data, offset):
    labels, pos, jumped, end = [], offset, False, offset
    while pos < len(data):
        length = data[pos]
        if length == 0:
            pos += 1
            if not jumped:
                end = pos
            break
        if length & 0xC0 == 0xC0:
            ptr = struct.unpack(">H", data[pos:pos + 2])[0] & 0x3FFF
            if not jumped:
                end = pos + 2
            pos = ptr
            jumped = True
            continue
        labels.append(data[pos + 1:pos + 1 + length].decode("utf-8", "replace"))
        pos += 1 + length
    return ".".join(labels), end


def parse_dns(data):
    out = []
    try:
        _, _, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
        pos = 12
        for _ in range(qd):
            _, pos = read_name(data, pos)
            pos += 4
        for _ in range(an + ns + ar):
            name, pos = read_name(data, pos)
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
            pos += 10
            rdata = data[pos:pos + rdlen]
            pos += rdlen
            if rtype == 12:
                target, _ = read_name(data, pos - rdlen)
                out.append(("PTR", name, target))
            elif rtype == 33:
                target, _ = read_name(data, pos - rdlen + 6)
                out.append(("SRV", name, f"{target}:{struct.unpack('>H', rdata[4:6])[0]}"))
            elif rtype == 16:
                txts, p = [], 0
                while p < len(rdata):
                    ln = rdata[p]
                    txts.append(rdata[p + 1:p + 1 + ln].decode("utf-8", "replace"))
                    p += 1 + ln
                out.append(("TXT", name, txts))
            elif rtype == 1:
                out.append(("A", name, socket.inet_ntoa(rdata)))
    except Exception:
        pass
    return out


def mdns_discover(timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", 5353))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                        struct.pack("4sl", socket.inet_aton(MDNS_GROUP[0]), socket.INADDR_ANY))
    except OSError:
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.bind(("", 0))
    for name in ("_miio._udp.local", "_services._dns-sd._udp.local",
                 "_airplay._tcp.local", "_raop._tcp.local"):
        try:
            sock.sendto(build_mdns_query(name, 12), MDNS_GROUP)
        except OSError:
            pass
        time.sleep(0.15)
    sock.settimeout(0.4)
    by_ip, deadline = {}, time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(8192)
        except (socket.timeout, ConnectionResetError, OSError):
            continue
        recs = parse_dns(data)
        if recs:
            bucket = by_ip.setdefault(addr[0], [])
            for rec in recs:
                if rec not in bucket:
                    bucket.append(rec)
    sock.close()
    return by_ip


# ---------- SSDP ----------
def ssdp_discover(timeout):
    msg = "\r\n".join([
        "M-SEARCH * HTTP/1.1", "HOST: 239.255.255.250:1900",
        'MAN: "ssdp:discover"', "MX: 2", "ST: ssdp:all", "", "",
    ]).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.bind(("", 0))
    sock.sendto(msg, SSDP_GROUP)
    sock.settimeout(0.5)
    responses, deadline = {}, time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except (socket.timeout, ConnectionResetError, OSError):
            continue
        if addr[0] not in responses:
            responses[addr[0]] = data.decode("utf-8", "replace")
    sock.close()
    return responses


# ---------- 端口探测 ----------
def udp_miio_probe(ip, timeout=0.5):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(b"\x21\x31\x00\x20" + b"\x00" * 32, (ip, MIIO_PORT))
        data, _ = s.recvfrom(1024)
        s.close()
        if len(data) >= 36 and data[:4] == b"\x21\x31\x00\x20":
            return data[4:36].hex()
    except Exception:
        pass
    return None


def tcp_probe(ip, port, timeout=0.6):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        ok = s.connect_ex((ip, port)) == 0
        s.close()
        return ok
    except Exception:
        return False


def threaded_scan(subnet, fn, workers=60):
    results, lock = {}, threading.Lock()
    threads = []

    def work(i):
        ip = f"{subnet}.{i}"
        r = fn(ip)
        if r:
            with lock:
                results[ip] = r

    for i in range(1, 255):
        t = threading.Thread(target=work, args=(i,), daemon=True)
        t.start()
        threads.append(t)
        if len(threads) >= workers:
            for t in threads:
                t.join(3)
            threads = []
    for t in threads:
        t.join(3)
    return results


# ---------- ARP + OUI 库 ----------
def load_oui_db():
    need_download = True
    if os.path.exists(CACHE_FILE):
        age_days = (time.time() - os.path.getmtime(CACHE_FILE)) / 86400
        need_download = age_days > CACHE_TTL_DAYS
    if need_download:
        print(f"    下载 OUI 厂商库（{MANUF_URL}）...")
        try:
            urllib.request.urlretrieve(MANUF_URL, CACHE_FILE)
        except Exception as e:
            print(f"    下载失败（{e}），使用本地缓存或跳过厂商识别")
    db = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) >= 2 and ":" in parts[0]:
                    db[parts[0].strip().upper()] = parts[1].strip()
    return db


def arp_table():
    entries = []
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True).stdout.decode("gbk", "replace")
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].count(".") == 3 and parts[1].count("-") == 5:
                entries.append((parts[0], parts[1].upper().replace("-", ":")))
    except Exception as e:
        print(f"    ARP 读取失败: {e}")
    return entries


def reverse_dns(ip):
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="小爱音箱局域网探测")
    parser.add_argument("--subnet", default="192.168.31")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--no-scan", action="store_true", help="跳过全网段扫描")
    args = parser.parse_args()

    print(f"探测网段: {args.subnet}.0/24")
    print("[1/6] mDNS（_miio / _airplay / _raop / 服务枚举，按来源归因）...")
    mdns = mdns_discover(args.timeout)
    for ip in sorted(mdns):
        ptrs = [v for t, _, v in mdns[ip] if t == "PTR"]
        if ptrs:
            print(f"  {ip}: {', '.join(ptrs[:8])}")
    if not mdns:
        print("  （无响应）")

    print("[2/6] SSDP...")
    ssdp = ssdp_discover(args.timeout)
    for ip, text in sorted(ssdp.items()):
        st = next((l.split(":", 1)[1].strip() for l in text.splitlines()
                   if l.upper().startswith("ST:")), "")
        print(f"  {ip}  ST: {st}")
    if not ssdp:
        print("  （无响应）")

    if not args.no_scan:
        print(f"[3/6] miIO UDP {MIIO_PORT} 全网段握手...")
        miio = threaded_scan(args.subnet, lambda ip: udp_miio_probe(ip, 0.5))
        for ip, did in sorted(miio.items()):
            print(f"  * {ip}  设备ID: {did}")
        if not miio:
            print("  （无 miIO 设备）")

        print("[4/6] 常见 TCP 端口扫描...")
        tcp_found = {}
        for port in TCP_PORTS:
            res = threaded_scan(args.subnet, lambda ip, p=port: tcp_probe(ip, p) and p or None)
            for ip in res:
                tcp_found.setdefault(ip, []).append(port)
        for ip, ports in sorted(tcp_found.items()):
            print(f"  {ip}  open: {ports}")
        if not tcp_found:
            print("  （无开放端口）")
    else:
        miio, tcp_found = {}, {}

    print("[5/6] ARP 表 + OUI 厂商库识别...")
    db = load_oui_db()
    arp = arp_table()
    xiaomi_ips = []
    for ip, mac in arp:
        oui = ":".join(mac.split(":")[:3])
        vendor = db.get(oui, "")
        if "xiaomi" in vendor.lower() or "lumi" in vendor.lower() or "yeelink" in vendor.lower():
            xiaomi_ips.append((ip, mac, vendor))
    print(f"  ARP 共 {len(arp)} 台；小米生态设备 {len(xiaomi_ips)} 台：")
    for ip, mac, vendor in xiaomi_ips:
        print(f"    {ip:16} {mac}  {vendor}")

    print("[6/6] 反向 DNS...")
    all_ips = sorted({ip for ip, _ in arp} | set(mdns) | set(miio) | set(tcp_found))
    for ip in all_ips:
        name = reverse_dns(ip)
        if name and name != ip:
            print(f"  {ip} -> {name}")

    print()
    print("===== 结论 =====")
    if miio:
        print("发现 miIO 设备:", ", ".join(sorted(miio)))
    print("小爱音箱为云端管控设备，若上面未出现明确的小爱设备，属正常现象。")
    print("音箱型号将在 xiaomusic 绑定小米账号后自动获取（Web 界面设备列表可见硬件型号）。")


if __name__ == "__main__":
    main()

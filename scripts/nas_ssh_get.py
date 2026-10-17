#!/usr/bin/env python3
"""通过 SSH exec 通道把 NAS 上的大文件下载回本地（fnOS 无 SFTP）。

用法: python nas_ssh_get.py <远程路径> <本地路径> [--md5 <期望值>]
"""
import sys
import time
import re
import hashlib
import os
import paramiko

HOST = os.getenv("NAS_HOST", "")
PORT = 22
USER = os.getenv("NAS_USER", "")
PASSWORD = os.getenv("NAS_PASS", "")
CHUNK = 256 * 1024


def _fix_msys_path(arg: str) -> str:
    """还原 Git Bash 改写过的 Unix 路径（同 nas_ssh.py 逻辑）。"""
    m = re.match(r"^[A-Za-z]:[\\/].*?[\\/]git[\\/](.*)$", arg, re.IGNORECASE)
    if m:
        return "/" + m.group(1).replace("\\", "/")
    return arg


def get_file(remote: str, local: str, expect_md5: str | None = None) -> bool:
    print(f"连接 {HOST} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)

    # 先拿文件大小
    stdin, stdout, stderr = client.exec_command(f"stat -c%s {remote}")
    size = int(stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print(f"错误: {err}")
        client.close()
        return False
    print(f"远程文件: {remote}  {size/1048576:.1f} MB")

    transport = client.get_transport()
    channel = transport.open_session()
    channel.exec_command(f"cat {remote}")
    channel.settimeout(None)

    md5 = hashlib.md5()
    received = 0
    start = time.time()
    last_print = 0.0
    with open(local, "wb") as f:
        while True:
            data = channel.recv(CHUNK)
            if not data:
                break
            f.write(data)
            md5.update(data)
            received += len(data)
            now = time.time()
            if now - last_print >= 2.0:
                last_print = now
                pct = received * 100 // size if size else 0
                speed = received / 1048576 / (now - start) if now > start else 0
                eta = (size - received) / 1048576 / speed if speed > 0 else 0
                print(f"  {pct:3d}%  {received/1048576:8.1f} MB  {speed:6.1f} MB/s  剩余约 {eta:.0f}s", flush=True)

    channel.close()
    client.close()
    elapsed = time.time() - start
    print(f"下载完成: {received} 字节, 耗时 {elapsed:.1f}s, 平均 {received/1048576/max(elapsed,0.1):.1f} MB/s")

    if received != size:
        print(f"!! 大小不匹配: 期望 {size}, 实际 {received}")
        return False
    got = md5.hexdigest()
    if expect_md5 and got != expect_md5:
        print(f"!! MD5 不匹配: 期望 {expect_md5}, 实际 {got}")
        return False
    print(f"MD5: {got}  ✓")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    remote, local = _fix_msys_path(sys.argv[1]), _fix_msys_path(sys.argv[2])
    expect = None
    if "--md5" in sys.argv:
        expect = sys.argv[sys.argv.index("--md5") + 1]
    ok = get_file(remote, local, expect)
    sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""分块上传工具：nas_ssh_put.py <local> <remote>

nas_ssh.py 的 put 一次性 sendall 大文件时通道可能被服务端关闭
（实测 206KB FPK 报 Socket is closed）。本工具分 32KB 小块发送，
每块之间稍作等待，上传后 md5 校验。

凭据复用 E:\\codex\\tools\\nas_ssh.py 的 HOST/USER/PWD。
"""
import hashlib
import os
import re
import sys
import time

import paramiko

HOST = os.getenv("NAS_HOST", "192.168.x.x")  # 你的 NAS 地址
USER = os.getenv("NAS_USER", "")
PWD = os.getenv("NAS_PASS", "")
CHUNK = 256 * 1024


def _fix_msys_path(arg: str) -> str:
    m = re.match(r"^[A-Za-z]:[\\/].*?[\\/]git[\\/](.*)$", arg, re.IGNORECASE)
    if m:
        return "/" + m.group(1).replace("\\", "/")
    return arg


def put(local: str, remote: str) -> None:
    data = open(local, "rb").read()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    try:
        ch = c.get_transport().open_session()
        ch.exec_command(f"cat > {remote}")
        sent = 0
        total = len(data)
        # 大块发送；sendall 自带流控（对端消费慢时自动阻塞），无需 sleep
        # 仅在流控阻塞超过阈值时打印心跳，避免长时间静默
        last_report = time.time()
        for i in range(0, total, CHUNK):
            ch.sendall(data[i : i + CHUNK])
            sent = i + len(data[i : i + CHUNK])
            if time.time() - last_report > 5:
                print(f"上传中 {sent}/{total} ({sent*100//total}%)", flush=True)
                last_report = time.time()
        print(f"发送完成 {sent}/{total}")
        ch.shutdown_write()
        rc = ch.recv_exit_status()
        if rc != 0:
            raise RuntimeError(f"upload failed, rc={rc}")
    finally:
        c.close()
    local_md5 = hashlib.md5(data).hexdigest()
    c2 = paramiko.SSHClient()
    c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c2.connect(HOST, username=USER, password=PWD, timeout=20)
    try:
        _, out, _ = c2.exec_command(f"md5sum {remote}", timeout=60)
        text = out.read().decode("utf-8", "replace")
    finally:
        c2.close()
    remote_md5 = text.split()[0] if text.strip() else ""
    if local_md5 != remote_md5:
        raise RuntimeError(f"md5 mismatch: local={local_md5} remote={remote_md5}")
    print(f"PUT OK ({len(data)} bytes, md5 {local_md5})")


if __name__ == "__main__":
    put(_fix_msys_path(sys.argv[1]), _fix_msys_path(sys.argv[2]))

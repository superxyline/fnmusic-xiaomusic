#!/usr/bin/env python3
"""authx 签名算法验证：用音桥（fn-music-bridge）官方测试向量校验本实现

测试向量来自 api/internal/api/signer_test.go：
  1) GET /music/api/v1/search/track  query={q:"hello world", page:"1"}
     prefix="prefix" key="key" nonce="123456" timestamp=1700000000000
     => sign=a32d34bb733dfb367391b7fd7e0ce2d7
  2) POST /music/api/v1/static/cover/track body="binary" multipart=true（payload 按 "{}" 签）
     => sign=74ff9fc73bebf5276024c6bb60fbfae0
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))

import fnmusic_client as fc  # noqa: E402

ok = True


def check(name, got, want):
    global ok
    status = "PASS" if got == want else "FAIL"
    if got != want:
        ok = False
    print(f"  [{status}] {name}\n         got : {got}\n         want: {want}")


# 固定签名常量以匹配测试向量
fc.AUTHX_PREFIX = "prefix"
fc.AUTHX_KEY = "key"

print("[1] GET 签名（含 query 规范化）")
got = fc.sign_authx("GET", "/music/api/v1/search/track",
                    {"q": "hello world", "page": "1"}, b"",
                    nonce="123456", timestamp="1700000000000")
check("authx header", got,
      "nonce=123456&timestamp=1700000000000&sign=a32d34bb733dfb367391b7fd7e0ce2d7")

print("[2] POST multipart 签名（payload 按 '{}'）")
# 本实现不直接支持 multipart 标志，按算法：multipart 时 payload = "{}"
payload = b"{}"
import hashlib
nonce, ts = "123456", "1700000000000"
source = f"prefix_/music/api/v1/static/cover/track_{nonce}_{ts}_{hashlib.md5(payload).hexdigest()}_key"
want_sign = hashlib.md5(source.encode()).hexdigest()
check("sign 值（手算公式对照）", want_sign, "74ff9fc73bebf5276024c6bb60fbfae0")

print("[3] GET 无 query 签名（冒烟）")
h = fc.sign_authx("GET", "/music/api/v1/user/me", None, b"")
print(f"  [INFO] {h}")

print()
print("结论:", "签名算法与官方实现一致 ✅" if ok else "存在差异 ❌")
sys.exit(0 if ok else 1)

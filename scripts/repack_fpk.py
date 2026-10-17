#!/usr/bin/env python3
"""修复 FPK 中 cmd 脚本的可执行权限位 + 还原 UTF-8 manifest

1. fnpack 在 Windows 上无法保留 Unix 权限位（打出来都是 0o666），
   而 fnOS 安装后要执行 cmd/ 下的脚本。本工具重打包 FPK，把 cmd/* 置为 0o755。
2. fnpack（Windows 版）会重写 manifest 并把 UTF-8 中文全部丢掉
   （display_name/desc 变空壳）。本工具用仓库里 fpk-v2-src/manifest
   的原始 UTF-8 内容替换 FPK 内损坏的 manifest。

用法：python repack_fpk.py <in.fpk> [out.fpk]
"""
import io
import os
import sys
import tarfile


def repack(src: str, dst: str) -> None:
    # 读取仓库中的原始 UTF-8 manifest（脚本位于 scripts/ 下，仓库根是上一级）
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_fix = None
    cand = os.path.join(here, "fpk-v2-src", "manifest")
    if os.path.isfile(cand):
        manifest_fix = open(cand, "rb").read()
        print(f"已加载 UTF-8 manifest（{len(manifest_fix)} 字节）用于替换")

    with tarfile.open(src, "r:gz") as tin, tarfile.open(
        dst, "w:gz", format=tarfile.GNU_FORMAT
    ) as tout:
        for m in tin.getmembers():
            if m.name.startswith("cmd/") and m.isfile():
                m.mode = 0o755
                m.uid = m.gid = 0
                m.uname = m.gname = ""
            if m.isfile():
                data = tin.extractfile(m).read()
                if m.name == "manifest" and manifest_fix:
                    data = manifest_fix
                    print("已替换损坏的 manifest 为 UTF-8 原文")
                m.size = len(data)
                tout.addfile(m, io.BytesIO(data))
            else:
                tout.addfile(m)
    print(f"已修复权限位: {src} -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    repack(src, dst)

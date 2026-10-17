#!/usr/bin/env python3
"""修复 FPK 中 cmd 脚本的可执行权限位

fnpack 在 Windows 上无法保留 Unix 权限位（打出来都是 0o666），
而 fnOS 安装后要执行 cmd/ 下的脚本。本工具重打包 FPK，把 cmd/* 置为 0o755。

用法：python repack_fpk.py <in.fpk> [out.fpk]
"""
import io
import sys
import tarfile


def repack(src: str, dst: str) -> None:
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

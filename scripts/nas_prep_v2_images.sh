#!/bin/bash
# NAS 上构建 v2 单容器镜像并保存
set -e

BASE=/home/Aadmin/xiaomusic-fnmusic-v2-base.fpk
WORK=/home/Aadmin/xm-v2-prep
OUT=/home/Aadmin/xm-v2-images.tar

echo "=== 1. 解包 base FPK ==="
rm -rf "$WORK" && mkdir -p "$WORK/target"
cd "$WORK"
tar xzf "$BASE"
cd target && tar xzf ../app.tgz && cd "$WORK"
echo "源码文件:"
ls -la target/docker/fnmusic-app/

echo "=== 2. 构建 fnmusic-xiaomusic 镜像（pip 安装 xiaomusic，约3-5分钟）==="
cd "$WORK/target/docker/fnmusic-app"
docker build -t fnmusic-xiaomusic:local . 2>&1 | tail -8

echo "=== 3. 保存镜像 ==="
rm -f "$OUT"
docker save fnmusic-xiaomusic:local -o "$OUT"
ls -la "$OUT"
echo "镜像 tar 大小: $(du -h "$OUT" | cut -f1)"
md5sum "$OUT"
echo "=== 全部完成 ==="

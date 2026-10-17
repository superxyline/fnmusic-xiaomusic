#!/bin/bash
# v2 一键重建：解包最新 base -> 放入静态 ffmpeg -> 构建镜像 -> save -> 合成最终 FPK
set -e
BASE=/home/Aadmin/xiaomusic-fnmusic-v2-base.fpk
WORK=/home/Aadmin/xm-v2-prep
OUT=/home/Aadmin/xm-v2-images.tar

echo "=== 1. 解包最新 base FPK ==="
rm -rf "$WORK" && mkdir -p "$WORK/target"
cd "$WORK"
tar xzf "$BASE"
cd target && tar xzf ../app.tgz && cd "$WORK"
md5sum target/docker/fnmusic-app/app.py

echo "=== 2. 放入静态 ffmpeg ==="
mkdir -p target/docker/fnmusic-app/ffmpeg-static
cp /home/Aadmin/ffbin/ffmpeg target/docker/fnmusic-app/ffmpeg-static/ffmpeg
ls -la target/docker/fnmusic-app/ffmpeg-static/

echo "=== 3. 构建镜像 ==="
cd "$WORK/target/docker/fnmusic-app"
docker build --progress plain -t fnmusic-xiaomusic:local . 2>&1 | tail -3

echo "=== 4. 保存镜像 ==="
rm -f "$OUT"
docker save fnmusic-xiaomusic:local -o "$OUT"
ls -la "$OUT" | awk '{print $5, $9}'

echo "=== 5. 合成最终 FPK ==="
bash /home/Aadmin/nas_build_final_v2.sh 2>&1 | tail -3
echo "=== 全部完成 ==="

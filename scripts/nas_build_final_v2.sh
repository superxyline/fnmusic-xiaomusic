#!/bin/bash
# NAS 本地合成 v2 最终 FPK：骨架 + 预置镜像 tar
set -e

BASE=/home/Aadmin/xiaomusic-fnmusic-v2-base.fpk
IMAGES=/home/Aadmin/xm-v2-images.tar
WORK=/home/Aadmin/xm-v2-final
OUT=/home/Aadmin/xiaomusic-fnmusic-2.0.0.fpk

echo "=== 1. 解包骨架 FPK ==="
rm -rf "$WORK" && mkdir -p "$WORK/target"
cd "$WORK"
tar xzf "$BASE"
cd target && tar xzf ../app.tgz && cd ..

echo "=== 2. 注入镜像 tar ==="
mkdir -p target/images
cp "$IMAGES" target/images/fnmusic-images.tar
ls -la target/images/

echo "=== 3. 重打 app.tgz ==="
cd target
tar czf ../app.tgz docker ui images
cd ..

echo "=== 4. 重打外层 FPK ==="
rm -f "$OUT"
tar czf "$OUT" manifest config cmd wizard app.tgz ICON.PNG ICON_256.PNG

echo "=== 5. 校验 ==="
ls -la "$OUT"
echo "--- cmd 权限位（应全为 755）---"
tar tvzf "$OUT" | grep 'cmd/' | awk '{print $1, $NF}'
echo "md5: $(md5sum "$OUT" | cut -d' ' -f1)"
echo "=== 合成完成 ==="

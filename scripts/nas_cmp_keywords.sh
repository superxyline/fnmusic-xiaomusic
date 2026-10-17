#!/bin/bash
# 对比宿主与容器内的 keywords 值
HOST_CONF=/var/apps/xiaomusic-fnmusic/shares/xiaomusic-fnmusic/data/conf/setting.json

echo "=== 宿主文件 ==="
ls -la "$HOST_CONF"
python3 - << 'PYEOF'
import json
s = json.load(open("/var/apps/xiaomusic-fnmusic/shares/xiaomusic-fnmusic/data/conf/setting.json", encoding="utf-8"))
print("host playlist :", repr(s.get("keywords_playlist", ""))[:110])
print("host playlocal:", repr(s.get("keywords_playlocal", "")))
PYEOF

echo "=== 容器内文件 ==="
docker exec fnmusic-xiaomusic python3 - << 'PYEOF'
import json
s = json.load(open("/data/conf/setting.json", encoding="utf-8"))
print("ctr playlist :", repr(s.get("keywords_playlist", ""))[:110])
print("ctr playlocal:", repr(s.get("keywords_playlocal", "")))
PYEOF

echo "=== xiaomusic 内存中的生效值（via API）==="
curl -s -m 10 "http://127.0.0.1:58091/xm/getsetting" | python3 -c "
import json, sys
s = json.load(sys.stdin)
print('api playlist :', repr(str(s.get('keywords_playlist', '')))[:110])
print('api playlocal:', repr(str(s.get('keywords_playlocal', ''))))"
echo "=== done ==="

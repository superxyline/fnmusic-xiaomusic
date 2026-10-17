#!/bin/bash
# 正确解码查看最近日志中的中文
docker logs --since 6m fnmusic-xiaomusic > /tmp/xmlog_raw.txt 2>&1
python3 - << 'PYEOF'
import re
data = open('/tmp/xmlog_raw.txt', 'rb').read().decode('utf-8', errors='replace')
keys = ['docmd', '收到消息', '匹配', 'play_internal', 'play]', '没有找到', 'tts', '搜索', '收藏']
for line in data.splitlines():
    if any(k in line for k in keys) and '[proxy' not in line:
        # 压缩超长行
        print(line[:200])
PYEOF

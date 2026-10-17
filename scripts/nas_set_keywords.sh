#!/bin/bash
# 修改 xiaomusic 口令关键词：多变体触发收藏乱序播放
CONF=/var/apps/xiaomusic-fnmusic/shares/xiaomusic-fnmusic/data/conf/setting.json

echo "=== 当前 keywords 配置 ==="
python3 - "$CONF" << 'PYEOF'
import json, sys
s = json.load(open(sys.argv[1]))
for k in sorted(s):
    if "keyword" in k:
        print(k, "=", repr(s[k]))
PYEOF

echo "=== 通过 modifiysetting 推送新关键词 ==="
# 播放歌单（收藏）：纳入全部口语变体
# playlocal（播放本地下载歌曲）：本方案无下载目录，改用不常用词避免与变体冲突
#   （xiaomusic 默认 playlocal 含「播放本地歌曲,播放本地音乐」，会抢先匹配）
NEW_PLAYLIST="播放列表,播放歌单,播放本地收藏歌曲,播放本地收藏,播放本地歌曲,播放本地音乐,放几首本地歌,放几首本地歌曲,放首本地歌,放首本地歌曲,随便放几首歌,随便放首歌,来几首本地歌,来几首本地音乐"
NEW_PLAYLOCAL="播放下载歌曲"
curl -s -m 20 -X POST http://127.0.0.1:58091/xm/api/system/modifiysetting \
  -H "Content-Type: application/json" \
  -d "{\"keywords_playlist\": \"$NEW_PLAYLIST\", \"keywords_playlocal\": \"$NEW_PLAYLOCAL\"}"
echo
sleep 6

echo "=== 验证落盘 ==="
python3 - "$CONF" << 'PYEOF'
import json, sys
s = json.load(open(sys.argv[1]))
print("keywords_playlist =", s.get("keywords_playlist", "")[:80], "...")
print("keywords_playlocal =", repr(s.get("keywords_playlocal", "")))
PYEOF
echo "=== done ==="

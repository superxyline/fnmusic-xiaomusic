#!/bin/bash
# 修复被 SSH 传输损坏的关键词（中文经命令行传输丢失，改用文件内嵌 + 宿主直改 + 重启容器）
CONF=/var/apps/xiaomusic-fnmusic/shares/xiaomusic-fnmusic/data/conf/setting.json

echo "=== 先停容器（防止退出钩子把旧内存配置写回覆盖）==="

echo "=== 写入正确关键词（脚本文件内嵌中文，二进制安全）==="
docker stop -t 1 fnmusic-xiaomusic
sleep 15
echo 容器已完全停止，开始修改配置
python3 - "$CONF" << 'PYEOF'
import json, sys
p = sys.argv[1]
s = json.load(open(p, encoding="utf-8"))
s["keywords_playlist"] = ",".join([
    "播放列表", "播放歌单",
    "播放本地收藏歌曲", "播放本地收藏", "播放本地歌曲", "播放本地音乐",
    "放几首本地歌", "放几首本地歌曲", "放首本地歌", "放首本地歌曲",
    "随便放几首歌", "随便放首歌", "来几首本地歌", "来几首本地音乐",
])
s["keywords_playlocal"] = "播放下载歌曲"
json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("keywords_playlist =", s["keywords_playlist"])
print("keywords_playlocal =", s["keywords_playlocal"])
PYEOF

echo "=== 停容器 -> 改文件 -> 再启动（避免退出钩子写回覆盖）==="
docker start fnmusic-xiaomusic
sleep 12
docker ps --format "{{.Names}} {{.Status}}" | grep fnmusic
echo "=== 验证容器内生效值 ==="
docker exec fnmusic-xiaomusic python3 -c "
import json
s = json.load(open('/data/conf/setting.json', encoding='utf-8'))
pl = s.get('keywords_playlist', '')
print('playlist 词数:', len([w for w in pl.split(',') if w.strip()]))
print('playlocal:', s.get('keywords_playlocal'))
assert '播放本地歌曲' in pl and '播放本地音乐' in pl, '中文校验失败!'
print('中文关键词校验 OK')
"
echo "=== done ==="

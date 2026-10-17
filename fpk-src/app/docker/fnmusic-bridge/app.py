"""
fnmusic-xiaomusic 桥接服务

连接「飞牛音乐」与「xiaomusic（小爱音箱）」：
  1. 定时登录飞牛音乐拉取收藏列表，乱序生成 xiaomusic 网络歌单 JSON
  2. 通过 xiaomusic HTTP API 推送歌单与口令配置并热生效（无需重启）
  3. 提供带认证的音频流代理 /play?guid=（Cookie + authx 签名，跟随 302，透传 Range）
  4. 对不支持 FLAC 的音箱型号（L05B/L05C/LX06/L16A）自动转码 MP3（可用 xiaomusic 设备列表自动判断）

语音口令（在 xiaomusic 配置 keywords_playlist 中追加）：
  - "播放本地收藏歌曲"      -> 播放收藏歌单（空参数匹配第一个歌单）
  - "播放列表本地收藏"      -> 同上（显式歌单名）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import secrets
import shutil
import time
import urllib.parse

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from fnmusic_client import FnMusicClient, FnMusicError

# ---------------- 配置 ----------------
def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


class Config:
    fnmusic_base_url: str = _env("FNMUSIC_BASE_URL", "http://192.168.31.26:5666")
    fnmusic_username: str = _env("FNMUSIC_USERNAME")
    fnmusic_password: str = _env("FNMUSIC_PASSWORD")
    device_id_file: str = _env("FNMUSIC_DEVICE_ID_FILE", "/data/device_id")

    xiaomusic_base_url: str = _env("XIAOMUSIC_BASE_URL", "http://xiaomusic:8090")
    xiaomusic_username: str = _env("XIAOMUSIC_USERNAME")
    xiaomusic_password: str = _env("XIAOMUSIC_PASSWORD")

    bridge_port: int = _env_int("BRIDGE_PORT", 58091)
    # 歌单里嵌入的流地址：必须能被 xiaomusic 容器访问（默认同 compose 网络服务名）
    bridge_url: str = _env("BRIDGE_URL", f"http://fnmusic-bridge:{_env_int('BRIDGE_PORT', 58091)}")

    playlist_name: str = _env("PLAYLIST_NAME", "本地收藏")
    playlist_keyword: str = _env("PLAYLIST_KEYWORD", "播放本地收藏歌曲")
    sync_interval: int = _env_int("SYNC_INTERVAL", 300)

    # 转码：auto=根据 xiaomusic 设备型号自动判断；always=总是转码；never=从不
    transcode_mode: str = _env("TRANSCODE_MODE", "auto").lower()
    transcode_formats: str = _env("TRANSCODE_FORMATS", "flac,wav,ape,dsf,dff,aiff")
    transcode_bitrate: str = _env("TRANSCODE_BITRATE", "192k")

    log_level: str = _env("LOG_LEVEL", "INFO").upper()


CFG = Config()

logging.basicConfig(
    level=getattr(logging, CFG.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bridge")

# 不支持 FLAC 等无损格式的小爱型号（见 xiaomusic 文档 #153）
FLAC_INCOMPATIBLE_MODELS = {"L05B", "L05C", "LX06", "L16A"}

# ---------------- 全局状态 ----------------
class State:
    fn: FnMusicClient | None = None
    favorites: list[dict] = []
    playlist_json: str = "[]"
    last_sync_at: float = 0
    last_push_at: float = 0
    last_error: str = ""
    push_ok: bool = False
    transcode_enabled: bool = False
    transcode_reason: str = "未判断"
    transcode_warned: bool = False


STATE = State()


def load_or_create_device_id() -> str:
    try:
        with open(CFG.device_id_file, "r", encoding="utf-8") as f:
            did = f.read().strip()
            if did:
                return did
    except OSError:
        pass
    did = secrets.token_hex(16)
    try:
        os.makedirs(os.path.dirname(CFG.device_id_file), exist_ok=True)
        with open(CFG.device_id_file, "w", encoding="utf-8") as f:
            f.write(did)
    except OSError as e:
        log.warning("无法持久化 device_id: %s", e)
    return did


# ---------------- xiaomusic API ----------------
def _xm_client() -> httpx.AsyncClient:
    auth = None
    if CFG.xiaomusic_username:
        auth = httpx.BasicAuth(CFG.xiaomusic_username, CFG.xiaomusic_password)
    return httpx.AsyncClient(base_url=CFG.xiaomusic_base_url, timeout=15.0, auth=auth)


async def xm_get_setting() -> dict:
    async with _xm_client() as c:
        resp = await c.get("/getsetting")
        resp.raise_for_status()
        return resp.json()


async def xm_modify_setting(updates: dict) -> None:
    async with _xm_client() as c:
        resp = await c.post("/api/system/modifiysetting", json=updates)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", True):
            raise FnMusicError(f"xiaomusic 配置更新失败: {data}")


async def xm_refresh_list() -> None:
    async with _xm_client() as c:
        resp = await c.post("/api/music/refreshlist")
        resp.raise_for_status()


async def xm_play_playlist(list_name: str) -> None:
    """（可选）直接让 xiaomusic 播放指定歌单，需要设备已绑定"""
    setting = await xm_get_setting()
    devices = setting.get("devices") or {}
    for did in devices:
        async with _xm_client() as c:
            await c.post("/playmusiclist", json={"did": did, "listname": list_name, "musicname": ""})
        break


# ---------------- 歌单生成 ----------------
def build_playlist(favorites: list[dict]) -> list[dict]:
    """把收藏列表转成 xiaomusic 网络歌单（乱序 + 同名去重）"""
    items, seen = [], {}
    for t in favorites:
        guid = t.get("guid") or ""
        if not guid:
            continue
        title = (t.get("title") or "未知歌曲").strip()
        artists = " / ".join(
            (a.get("name") or "").strip() for a in (t.get("artists") or []) if a.get("name")
        )
        name = f"{artists} - {title}" if artists else title
        if name in seen:  # 同名去重：追加专辑名，再退化为 guid 前缀
            album = ((t.get("album") or {}).get("name") or "").strip()
            name = f"{name}（{album}）" if album else f"{name}#{guid[:6]}"
            if name in seen:
                name = f"{name}#{guid[:6]}"
        seen[name] = True
        items.append({"name": name, "url": f"{CFG.bridge_url}/play?guid={guid}"})
    random.shuffle(items)
    return [{"name": CFG.playlist_name, "musics": items}]


# ---------------- 同步与推送 ----------------
async def push_to_xiaomusic(force: bool = False) -> dict:
    """把歌单 JSON 和口令配置推送到 xiaomusic 并刷新歌单"""
    result = {"updated": False, "refreshed": False}
    setting = await xm_get_setting()

    updates: dict = {}
    # 1. 歌单 URL（供 xiaomusic 服务端拉取，Web 界面也可手动"获取"）
    playlist_url = f"{CFG.bridge_url}/playlist.json"
    if setting.get("music_list_url") != playlist_url:
        updates["music_list_url"] = playlist_url
    # 2. 口令：在用户现有 keywords_playlist 后追加我们的口令
    kw = (setting.get("keywords_playlist") or "").strip()
    if CFG.playlist_keyword and CFG.playlist_keyword not in kw:
        base = kw if kw else "播放列表,播放歌单"
        updates["keywords_playlist"] = base.rstrip(",") + "," + CFG.playlist_keyword
    # 3. hostname：仍是出厂默认值时，用 NAS 地址修正（小爱要靠它访问 xiaomusic 代理）
    hostname = (setting.get("hostname") or "").strip()
    parsed = urllib.parse.urlparse(CFG.fnmusic_base_url)
    nas_url = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
    if nas_url and hostname in ("", "http://192.168.2.5"):
        updates["hostname"] = nas_url
    # 4. 歌单 JSON（有变化才推）
    if force or setting.get("music_list_json") != STATE.playlist_json:
        updates["music_list_json"] = STATE.playlist_json

    if updates:
        await xm_modify_setting(updates)
        result["updated"] = True
        log.info("已更新 xiaomusic 配置: %s", list(updates.keys()))
    if force or "music_list_json" in updates:
        await xm_refresh_list()
        result["refreshed"] = True
        log.info("已通知 xiaomusic 刷新歌单")
    STATE.push_ok = True
    STATE.last_push_at = time.time()
    return result


async def update_transcode_decision() -> None:
    """根据 xiaomusic 已绑定设备的型号，决定是否转码"""
    if CFG.transcode_mode == "never":
        STATE.transcode_enabled = False
        STATE.transcode_reason = "配置为从不转码"
        return
    if CFG.transcode_mode == "always":
        STATE.transcode_enabled = True
        STATE.transcode_reason = "配置为总是转码"
        return
    try:
        setting = await xm_get_setting()
        models = []
        for dev in (setting.get("devices") or {}).values():
            hw = (dev.get("hardware") or "").upper()
            if hw:
                models.append(hw)
        bad = [m for m in models if m in FLAC_INCOMPATIBLE_MODELS]
        if bad:
            STATE.transcode_enabled = True
            STATE.transcode_reason = f"设备不支持无损: {', '.join(sorted(set(bad)))}"
        else:
            STATE.transcode_enabled = False
            STATE.transcode_reason = f"设备支持无损: {', '.join(sorted(set(models))) or '未绑定'}"
    except Exception as e:
        STATE.transcode_reason = f"型号获取失败: {e}"


async def do_sync(force: bool = False) -> dict:
    """拉收藏 -> 有变化则重建歌单 -> 推送 xiaomusic"""
    favorites = await STATE.fn.get_favorites()
    STATE.favorites = favorites
    STATE.last_sync_at = time.time()
    guids = sorted(t.get("guid") or "" for t in favorites)
    changed = force or guids != getattr(do_sync, "_last_guids", None)
    result = {"count": len(favorites), "changed": changed}
    if changed:
        do_sync._last_guids = guids
        STATE.playlist_json = json.dumps(build_playlist(favorites), ensure_ascii=False)
        log.info("收藏列表变化，已重建歌单（%d 首，乱序）", len(favorites))
    try:
        push_result = await push_to_xiaomusic(force=changed)
        result.update(push_result)
    except Exception as e:
        STATE.push_ok = False
        STATE.last_error = f"推送 xiaomusic 失败: {e}"
        log.warning("%s（xiaomusic 可能尚未启动完成，下个周期重试）", STATE.last_error)
    await update_transcode_decision()
    return result


async def sync_loop() -> None:
    # 启动初期等待 xiaomusic 就绪（compose 同时启动时 xiaomusic 需要几十秒）
    for i in range(24):
        try:
            await xm_get_setting()
            log.info("xiaomusic 已就绪")
            break
        except Exception as e:
            log.info("等待 xiaomusic 就绪... (%d/24) %s", i + 1, type(e).__name__)
            await asyncio.sleep(5)
    while True:
        try:
            await do_sync()
            STATE.last_error = ""
        except FnMusicError as e:
            STATE.last_error = str(e)
            log.error("同步失败: %s", e)
        except Exception as e:
            STATE.last_error = f"{type(e).__name__}: {e}"
            log.exception("同步异常")
        await asyncio.sleep(CFG.sync_interval)


# ---------------- 音频流 ----------------
def _need_transcode(content_type: str) -> bool:
    if not STATE.transcode_enabled:
        return False
    if not shutil.which("ffmpeg"):
        if not STATE.transcode_warned:
            STATE.transcode_warned = True
            log.warning("需要转码但容器内没有 ffmpeg，已跳过转码（直推原始格式）")
        return False
    ct = (content_type or "").lower()
    return any(fmt in ct for fmt in CFG.transcode_formats.split(","))


async def _transcode_pipe(resp) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", "pipe:0", "-vn",
        "-acodec", "libmp3lame", "-b:a", CFG.transcode_bitrate,
        "-f", "mp3", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )


async def transcode_generator(resp, proc):
    async def feed():
        try:
            async for chunk in resp.aiter_bytes():
                proc.stdin.write(chunk)
                await proc.stdin.drain()
        except Exception:
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    feeder = asyncio.create_task(feed())
    try:
        while True:
            chunk = await proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        await feeder
        if proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                proc.kill()


async def passthrough_generator(resp):
    try:
        async for chunk in resp.aiter_bytes():
            yield chunk
    finally:
        await resp.aclose()


# ---------------- FastAPI ----------------
app = FastAPI(title="fnmusic-xiaomusic 桥接服务")


@app.on_event("startup")
async def startup():
    device_id = load_or_create_device_id()
    STATE.fn = FnMusicClient(
        CFG.fnmusic_base_url, CFG.fnmusic_username, CFG.fnmusic_password,
        device_id=device_id,
    )
    log.info("桥接服务启动：fnmusic=%s xiaomusic=%s", CFG.fnmusic_base_url, CFG.xiaomusic_base_url)
    asyncio.create_task(sync_loop())


@app.on_event("shutdown")
async def shutdown():
    if STATE.fn:
        await STATE.fn.aclose()


@app.get("/health")
async def health():
    return {
        "ok": True,
        "token": bool(STATE.fn and STATE.fn.token),
        "auth_mode": "authx+cookie" if (STATE.fn and STATE.fn.use_authx) else "cookie",
        "favorites": len(STATE.favorites),
        "playlist": CFG.playlist_name,
        "playlist_songs": len(json.loads(STATE.playlist_json)[0]["musics"]) if STATE.playlist_json != "[]" else 0,
        "last_sync_at": STATE.last_sync_at,
        "last_push_at": STATE.last_push_at,
        "push_ok": STATE.push_ok,
        "transcode": STATE.transcode_enabled,
        "transcode_reason": STATE.transcode_reason,
        "last_error": STATE.last_error,
    }


@app.get("/playlist.json")
async def playlist_json():
    return JSONResponse(content=json.loads(STATE.playlist_json),
                        media_type="application/json; charset=utf-8")


@app.get("/favorites")
async def favorites_debug():
    return {"count": len(STATE.favorites),
            "tracks": [{"guid": t.get("guid"), "title": t.get("title"),
                        "artists": [a.get("name") for a in t.get("artists", [])]}
                       for t in STATE.favorites[:100]]}


@app.post("/sync")
async def sync_now():
    try:
        result = await do_sync(force=True)
        return {"ret": "OK", **result}
    except FnMusicError as e:
        STATE.last_error = str(e)
        return JSONResponse({"ret": "FAIL", "error": str(e)}, status_code=502)
    except Exception as e:
        STATE.last_error = f"{type(e).__name__}: {e}"
        log.exception("手动同步异常")
        return JSONResponse({"ret": "FAIL", "error": str(e)}, status_code=500)


@app.api_route("/play", methods=["GET", "HEAD"])
async def play(request: Request, guid: str):
    """音频流代理：带认证请求飞牛音乐，跟随 302，流式回传"""
    if not STATE.fn:
        return JSONResponse({"error": "服务未初始化"}, status_code=503)
    range_header = request.headers.get("range")
    try:
        resp = await STATE.fn.open_stream(guid, range_header=range_header)
    except FnMusicError as e:
        log.warning("取流失败 guid=%s: %s", guid, e)
        return JSONResponse({"error": str(e)}, status_code=502)
    try:
        if resp.status_code >= 400:
            body = await resp.aread()
            log.warning("取流失败 guid=%s HTTP %s %s", guid, resp.status_code, body[:200])
            return JSONResponse(
                {"error": f"飞牛音乐取流失败 HTTP {resp.status_code}", "detail": body[:200]},
                status_code=resp.status_code,
            )
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        headers = {}
        for h in ("Content-Length", "Content-Range", "Accept-Ranges"):
            v = resp.headers.get(h)
            if v:
                headers[h] = v
        if request.method == "HEAD":
            await resp.aclose()
            return Response(status_code=resp.status_code, media_type=content_type, headers=headers)
        transcode = _need_transcode(content_type)
        if transcode:
            log.info("转码播放 guid=%s (%s -> mp3 %s)", guid, content_type, CFG.transcode_bitrate)
            proc = await _transcode_pipe(resp)
            return StreamingResponse(
                transcode_generator(resp, proc),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline"},
            )
        return StreamingResponse(
            passthrough_generator(resp),
            status_code=resp.status_code,
            media_type=content_type,
            headers=headers,
        )
    except Exception as e:
        await resp.aclose()
        log.exception("播放异常")
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.get("/", response_class=HTMLResponse)
async def index():
    h = await health()
    songs = h["playlist_songs"]
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>飞牛音乐 → 小爱音箱 桥接服务</title>
<style>
 body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
        max-width: 720px; margin: 24px auto; padding: 0 16px; color: #222; line-height: 1.7; }}
 h1 {{ font-size: 20px; }} code {{ background: #f2f2f2; padding: 1px 6px; border-radius: 4px; }}
 table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
 td, th {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 14px; text-align: left; }}
 .ok {{ color: #0a7; }} .warn {{ color: #c60; }} .err {{ color: #c00; }}
</style></head><body>
<h1>飞牛音乐 → 小爱音箱 桥接服务</h1>
<p>对小米小爱音箱说 <code>播放本地收藏歌曲</code> 或 <code>播放列表{CFG.playlist_name}</code>，即可随机播放飞牛音乐收藏。</p>
<table>
 <tr><th>项目</th><th>状态</th></tr>
 <tr><td>飞牛登录</td><td class="{'ok' if h['token'] else 'err'}">{('已登录（' + h['auth_mode'] + '）') if h['token'] else '未登录'}</td></tr>
 <tr><td>收藏歌曲</td><td>{h['favorites']} 首</td></tr>
 <tr><td>歌单「{CFG.playlist_name}」</td><td>{songs} 首（乱序）</td></tr>
 <tr><td>xiaomusic 配置推送</td><td class="{'ok' if h['push_ok'] else 'warn'}">{'正常' if h['push_ok'] else '等待中/失败'}</td></tr>
 <tr><td>无损转码</td><td>{'开启' if h['transcode'] else '关闭'}（{h['transcode_reason']}）</td></tr>
 <tr><td>最近同步</td><td>{time.strftime('%H:%M:%S', time.localtime(h['last_sync_at'])) if h['last_sync_at'] else '未同步'}</td></tr>
 <tr><td>最近错误</td><td class="{'err' if h['last_error'] else 'ok'}">{h['last_error'] or '无'}</td></tr>
</table>
<p>接口：<code>/health</code> 状态 · <code>/playlist.json</code> 歌单 · <code>/favorites</code> 收藏明细 ·
<code>/play?guid=</code> 音频流 · <code>POST /sync</code> 立即同步</p>
</body></html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=CFG.bridge_port)

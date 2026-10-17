#!/usr/bin/env python3
"""飞牛音乐 API 连通性测试脚本

在部署桥接服务之前，先验证：
  1. 网关可达（/initialization/state）
  2. 登录（自动适配 authx / 纯 Cookie 两种认证模式）
  3. 会话校验（/user/me）
  4. 收藏列表（/favorite-track/list）
  5. 音频流（/track/stream，Range 请求 + 302 跟随）

用法：
  python test_fnmusic_api.py --host http://192.168.31.26:5666 --username 账号 --password 密码
  python test_fnmusic_api.py --host ... --username ... --password ... --guid <歌曲GUID>
  python test_fnmusic_api.py --host ... --username ... --password ... --no-authx   # 强制纯 Cookie

可以在任意能访问 NAS 的机器上运行（部署本机的电脑、NAS SSH 均可）。
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))

from fnmusic_client import FnMusicClient, FnMusicError  # noqa: E402

PASS, FAIL = "  [PASS]", "  [FAIL]"


async def main():
    parser = argparse.ArgumentParser(description="飞牛音乐 API 连通性测试")
    parser.add_argument("--host", required=True, help="如 http://192.168.31.26:5666")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--guid", default="", help="测试流的歌曲 GUID（默认取收藏第一首）")
    parser.add_argument("--no-authx", action="store_true", help="强制纯 Cookie 模式")
    parser.add_argument("--authx-only", action="store_true", help="强制 authx 模式")
    args = parser.parse_args()

    print(f"目标: {args.host}")
    print(f"账号: {args.username}")
    print("=" * 56)

    use_authx = not args.no_authx
    client = FnMusicClient(args.host, args.username, args.password, use_authx=use_authx)
    ok_count = 0

    # 1. 网关
    print("[1] 网关连通性 /initialization/state")
    try:
        state = await client.get_initialization_state()
        data = state.get("data", {})
        print(f"{PASS} {state}  initialized={data.get('initialized')}")
        ok_count += 1
    except Exception as e:
        print(f"{FAIL} {e}")
        print("    -> NAS 地址或端口不对，或飞牛音乐未运行")
        await client.aclose()
        return 1

    # 2. 登录
    print("[2] 登录 /user/password-login")
    try:
        token = await client.login()
        print(f"{PASS} 登录成功，token: {token[:12]}...（认证模式: authx={client.use_authx}）")
        ok_count += 1
    except FnMusicError as e:
        print(f"{FAIL} {e}")
        print("    -> 检查账号密码；若音乐库用 NAS 账号一键登录，请用 NAS 账号")
        print("    -> 可加 --no-authx 或 --authx-only 强制某种认证模式重试")
        await client.aclose()
        return 1

    # 3. 会话校验
    print("[3] 会话校验 /user/me")
    try:
        me = await client.get_user_info()
        name = me.get("username") or me.get("name") or me
        print(f"{PASS} 当前用户: {name}")
        ok_count += 1
    except FnMusicError as e:
        print(f"{FAIL} {e}")

    # 4. 收藏列表
    print("[4] 收藏列表 /favorite-track/list")
    favorites = []
    try:
        favorites = await client.get_favorites()
        print(f"{PASS} 共 {len(favorites)} 首收藏")
        for t in favorites[:5]:
            artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
            album = (t.get("album") or {}).get("name", "")
            print(f"      - {t.get('title')} / {artists} / {album}  guid={t.get('guid')}")
        if len(favorites) > 5:
            print(f"      ... 等共 {len(favorites)} 首")
        ok_count += 1
    except FnMusicError as e:
        print(f"{FAIL} {e}")
        print("    -> 收藏接口异常；可先去飞牛音乐收藏几首歌再试")

    # 5. 音频流
    guid = args.guid or (favorites[0].get("guid") if favorites else "")
    print(f"[5] 音频流 /track/stream?guid={guid or '(无，跳过)'}")
    if not guid:
        print("  [SKIP] 没有可测试的歌曲")
    else:
        try:
            resp = await client.open_stream(guid, range_header="bytes=0-2047")
            ctype = resp.headers.get("Content-Type", "")
            crange = resp.headers.get("Content-Range", "")
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total >= 4096:
                    break
            await resp.aclose()
            if resp.status_code in (200, 206) and total > 0:
                print(f"{PASS} HTTP {resp.status_code}  Content-Type: {ctype}")
                print(f"      Content-Range: {crange}  已读取 {total} 字节")
                ok_count += 1
            else:
                print(f"{FAIL} HTTP {resp.status_code} 读取 {total} 字节  Content-Type: {ctype}")
        except FnMusicError as e:
            print(f"{FAIL} {e}")
        except Exception as e:
            print(f"{FAIL} {type(e).__name__}: {e}")

    await client.aclose()
    print("=" * 56)
    print(f"结果: {ok_count}/5 项通过")
    if ok_count == 5:
        print("全部通过！可以部署桥接服务了。")
        return 0
    print("存在问题，请根据上面的提示排查后重试。")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

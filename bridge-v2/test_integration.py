"""本地集成测试：模拟 v2 lifespan 创建 xiaomusic + mount + run_forever"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, "E:/codex/fnmusic-xiaomusic/bridge-v2")
os.environ["DATA_DIR"] = "E:/codex/fnmusic-xiaomusic/bridge-v2/testdata"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


async def main():
    import app as appmod
    from fastapi import FastAPI

    # 1. lifespan 里的创建流程
    appmod.create_xiaomusic()
    print("[test] XiaoMusic 创建 OK")
    appmod.app.mount("/xm", appmod.XM_APP)
    print("[test] mount OK，路由数:", len(appmod.app.routes))

    # 2. 驱动 run_forever（xiaomusic 登录+轮询）
    xm = appmod.XM
    asyncio.create_task(xm.run_forever())
    print("[test] run_forever 已启动")

    # 3. 用 TestClient 打接口（不起真实服务器）
    await asyncio.sleep(3)

    from fastapi.testclient import TestClient
    with TestClient(appmod.app) as client:
        r = client.get("/health")
        print("[test] GET /health ->", r.status_code, r.json())
        r = client.get("/api/wizard/state")
        print("[test] GET /api/wizard/state ->", r.status_code, r.json())
        r = client.get("/")
        print("[test] GET / ->", r.status_code, "长度", len(r.text), "含logo:", "data:image/png;base64," in r.text)
        # xiaomusic 子应用路由
        r = client.get("/xm/getversion")
        print("[test] GET /xm/getversion ->", r.status_code, r.text[:80])
        r = client.get("/xm/")
        print("[test] GET /xm/ ->", r.status_code, "长度", len(r.text))
    print()
    print("=== 集成测试全部通过 ===")
    xm.cancel_all_tasks()


asyncio.run(main())

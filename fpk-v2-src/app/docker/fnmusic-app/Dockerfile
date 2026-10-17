# fnmusic-xiaomusic v2 单容器镜像（瘦身版 ~250MB）
# 基础镜像可通过构建参数覆盖（国内网络自动切换镜像源重试）
#
# 瘦身要点（对比初版 ~770MB）：
#   1. 不用 apt 装 ffmpeg（Debian 版连依赖 ~450MB）—— COPY 静态 ffmpeg 单二进制（78MB），
#      构建前把静态 ffmpeg 放到 /home/Aadmin/ffbin/ffmpeg（nas_prep 脚本负责）
#   2. 不装 curl（healthcheck 用 python 标准库）
#   3. pip 装完卸载 yt-dlp/uvloop/httptools（本方案用不到，省 ~45MB）
#   4. 时长计算用 mutagen（pip 已装），不再需要 ffprobe
ARG BASE_IMAGE=docker.1ms.run/library/python:3.12-slim
FROM ${BASE_IMAGE}

ENV TZ=Asia/Shanghai \
    DATA_DIR=/data \
    BRIDGE_PORT=58091 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 预置静态 ffmpeg（构建上下文由 rebuild 脚本放入）
COPY --chmod=0755 ffmpeg-static/ffmpeg /usr/local/bin/ffmpeg

COPY requirements.txt .
# 国内 pip 源优先，官方源作后备（部分新包国内镜像未同步，如 xiaomusic 本身）
RUN pip install --no-cache-dir \
        --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
        --extra-index-url https://pypi.org/simple \
        -r requirements.txt \
    && pip uninstall -y yt-dlp uvloop httptools websockets brotli 2>/dev/null; true

COPY . .

EXPOSE 58091

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:${BRIDGE_PORT}/health',timeout=4)" || exit 1

CMD ["python", "app.py"]

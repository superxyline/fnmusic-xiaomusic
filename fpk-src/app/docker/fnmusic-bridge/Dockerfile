# fnmusic-xiaomusic 桥接服务镜像
# 基础镜像默认走 docker.1ms.run（国内可达）；构建参数可覆盖：
#   --build-arg BASE_IMAGE=python:3.12-slim
#   --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
#   --build-arg APT_MIRROR=mirrors.aliyun.com
ARG BASE_IMAGE=docker.1ms.run/library/python:3.12-slim
FROM ${BASE_IMAGE}

# ffmpeg：对不支持 FLAC 的小爱型号（L05B/L05C/LX06/L16A）转码 MP3 用
# 安装失败不阻断构建（转码功能不可用，其余功能正常）
ARG APT_MIRROR=
RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s|deb.debian.org|$APT_MIRROR|g; s|security.debian.org|$APT_MIRROR|g" \
            /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    || echo "WARN: ffmpeg 安装失败，无损转码功能将不可用"

WORKDIR /app
COPY requirements.txt ./
ARG PIP_INDEX_URL=
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

COPY fnmusic_client.py app.py ./

ENV FNMUSIC_DEVICE_ID_FILE=/data/device_id
VOLUME ["/data"]
EXPOSE 58091

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${BRIDGE_PORT:-58091}"]

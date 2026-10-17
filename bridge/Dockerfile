# fnmusic-xiaomusic 桥接服务镜像
# 国内构建加速：docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t fnmusic-bridge ./bridge
FROM python:3.12-slim

# ffmpeg：对不支持 FLAC 的小爱型号（L05B/L05C/LX06/L16A）转码 MP3 用
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
ARG PIP_INDEX_URL=
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

COPY fnmusic_client.py app.py ./

ENV FNMUSIC_DEVICE_ID_FILE=/data/device_id
VOLUME ["/data"]
EXPOSE 58091

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${BRIDGE_PORT:-58091}"]

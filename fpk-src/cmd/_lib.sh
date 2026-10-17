#!/bin/bash
# 共享函数库：环境配置生成 / 桌面图标端口同步
# 被 install_callback / upgrade_callback / config_callback 引用

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

# 探测 shares 根目录（兼容不同安装位置）
detect_shares_root() {
    local cand
    for cand in "/var/apps/${TRIM_APPNAME}/shares" "${TRIM_APPDEST%/target}/shares" "${TRIM_APPDEST}/../shares"; do
        if [ -d "$cand" ]; then
            echo "$cand"
            return 0
        fi
    done
    echo "/var/apps/${TRIM_APPNAME}/shares"
}

# 从持久化 env 文件读单个值
env_get() {
    local key="$1"
    grep -m1 "^${key}=" "${TRIM_PKGVAR}/fnmusic.env" 2>/dev/null | cut -d= -f2-
}

# 全量写入环境配置（持久化 + 同步到 compose 目录）
# 用法: env_write_full <nas_ip> <fm_port> <fm_user> <fm_pass> <xm_port> <br_port>
env_write_full() {
    local nas_ip="$1" fm_port="$2" fm_user="$3" fm_pass="$4" xm_port="$5" br_port="$6"
    local env_file="${TRIM_PKGVAR}/fnmusic.env"
    mkdir -p "${TRIM_PKGVAR}"
    {
        printf 'NAS_IP=%s\n' "$nas_ip"
        printf 'FM_PORT=%s\n' "$fm_port"
        printf 'FNMUSIC_BASE_URL=http://%s:%s\n' "$nas_ip" "$fm_port"
        printf 'FNMUSIC_USERNAME=%s\n' "$fm_user"
        printf 'FNMUSIC_PASSWORD=%s\n' "$fm_pass"
        printf 'XIAOMUSIC_BASE_URL=http://xiaomusic:8090\n'
        printf 'XIAOMUSIC_HOSTNAME=http://%s\n' "$nas_ip"
        printf 'BRIDGE_URL=http://fnmusic-bridge:%s\n' "$br_port"
        printf 'BRIDGE_PORT=%s\n' "$br_port"
        printf 'XIAOMUSIC_PORT=%s\n' "$xm_port"
        printf 'SHARES_ROOT=%s\n' "$(detect_shares_root)"
        printf 'PLAYLIST_NAME=%s\n' "本地收藏"
        printf 'PLAYLIST_KEYWORD=%s\n' "播放本地收藏歌曲"
        printf 'SYNC_INTERVAL=%s\n' "300"
        printf 'TRANSCODE_MODE=%s\n' "auto"
    } > "${env_file}"
    chmod 600 "${env_file}"
    cp "${env_file}" "${TRIM_APPDEST}/docker/.env"
}

# 同步桌面图标端口到 ui/config
sync_ui_ports() {
    local xm_port="$1" br_port="$2"
    local cfg="${TRIM_APPDEST}/ui/config"
    [ -f "$cfg" ] || return 0
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$cfg" "$xm_port" "$br_port" <<'PYEOF' 2>/dev/null || true
import json, sys
path, xm, br = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)
for key, entry in cfg.get(".url", {}).items():
    if key.endswith(".main"):
        entry["port"] = xm
    elif key.endswith(".bridge"):
        entry["port"] = br
with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=4)
PYEOF
    fi
}

# 从包内 images 目录加载预置镜像（安装时零构建零拉取）
# FPK 打包前已把 fnmusic-xiaomusic:local 和 fnmusic-bridge:local
# 两个镜像 docker save 成 app/images/fnmusic-images.tar 随包分发
load_local_images() {
    local tar_file="${TRIM_APPDEST}/images/fnmusic-images.tar"
    if [ ! -f "$tar_file" ]; then
        echo "[images] 未找到预置镜像包: $tar_file" >&2
        return 1
    fi
    local size_mb=$(( $(stat -c%s "$tar_file" 2>/dev/null || echo 0) / 1048576 ))
    echo "[images] 加载预置镜像（约 ${size_mb}MB，需要1-2分钟）..."
    docker load -i "$tar_file"
}

# 把 .env 的值硬替换进 docker-compose.yaml
# 原因：appcenter 运行 docker compose 时不读取 .env（变量插值全落默认值，
# 实测 FNMUSIC_USERNAME/PASSWORD 为空导致登录失败），
# 因此从模板重新生成 compose，把实际配置写死，保证容器拿到正确的环境变量。
harden_compose_env() {
    local dir="${TRIM_APPDEST}/docker"
    [ -f "${dir}/docker-compose.yaml.template" ] || return 0
    [ -f "${TRIM_PKGVAR}/fnmusic.env" ] || return 0
    cp "${dir}/docker-compose.yaml.template" "${dir}/docker-compose.yaml"
    python3 - "${dir}" "${TRIM_PKGVAR}/fnmusic.env" <<'PYEOF' || return 1
import re, sys
d, env_file = sys.argv[1], sys.argv[2]
env = {}
with open(env_file, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k] = v
path = f"{d}/docker-compose.yaml"
with open(path, encoding="utf-8") as f:
    text = f.read()
text = re.sub(r"\$\{(\w+):-([^}]*)\}", lambda m: env.get(m.group(1), m.group(2)), text)
text = re.sub(r"\$\{(\w+)\}", lambda m: env.get(m.group(1), ""), text)
with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("[harden] compose 环境变量已硬替换")
PYEOF
    chmod 600 "${dir}/docker-compose.yaml"
}

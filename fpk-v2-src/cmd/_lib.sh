#!/bin/bash
# 共享函数库：环境配置生成 / 端口同步 / 镜像加载
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
# v2 安装向导只收集 NAS IP 和端口；飞牛音乐账号在应用内三步向导里填写
env_write_full() {
    local nas_ip="$1" br_port="$2"
    local env_file="${TRIM_PKGVAR}/fnmusic.env"
    mkdir -p "${TRIM_PKGVAR}"
    {
        printf 'NAS_IP=%s\n' "$nas_ip"
        printf 'BRIDGE_PORT=%s\n' "$br_port"
        printf 'SHARES_ROOT=%s\n' "$(detect_shares_root)"
    } > "${env_file}"
    chmod 600 "${env_file}"
    cp "${env_file}" "${TRIM_APPDEST}/docker/.env"
}

# 同步桌面图标端口到 ui/config
sync_ui_ports() {
    local br_port="$1"
    local cfg="${TRIM_APPDEST}/ui/config"
    [ -f "$cfg" ] || return 0
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$cfg" "$br_port" <<'PYEOF' 2>/dev/null || true
import json, sys
path, br = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)
for key, entry in cfg.get(".url", {}).items():
    entry["port"] = br
with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=4)
PYEOF
    fi
}

# 从包内 images 目录加载预置镜像（安装时零构建零拉取）
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

# 定位 appcenter 实际使用的 compose 目录并重建容器
# （appcenter 先起容器后跑回调，且工作目录在 /vol3/@appcenter/<app>/docker，
#  裸跑 compose 项目名会推断成 "docker" 导致容器名冲突，必须 -p）
recreate_containers() {
    local compose_dir=""
    for d in "/vol3/@appcenter/${TRIM_APPNAME}/docker" "${TRIM_APPDEST}/docker"; do
        if [ -f "$d/docker-compose.yaml" ]; then compose_dir="$d"; break; fi
    done
    [ -n "$compose_dir" ] || return 0
    cd "$compose_dir" && docker compose -p "${TRIM_APPNAME}" up -d 2>&1 | tail -5 || true
}

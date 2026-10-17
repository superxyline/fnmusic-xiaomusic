# 小爱音箱·飞牛音乐（fnmusic-xiaomusic）

对家里的小爱音箱说 **「播放本地收藏歌曲」**，音箱即随机播放 NAS 上**飞牛音乐（fnOS trim.music）**的收藏列表。收藏有增减时自动同步（默认 5 分钟），全程语音控制，小爱侧零改动。

已封装为飞牛 FPK 应用：**一个安装包、一个端口（58091）、一个三步向导界面**。安装包内置全部镜像，安装过程不需要访问外网。

## 功能特性

- 🎵 **语音播放收藏**：「播放本地收藏歌曲」「播放收藏」「播放本地」等口令随机播放飞牛音乐收藏，每次口令都重新打乱顺序
- 🎤 **语音点歌**：「播放晴天」「播放周杰伦的晴天」——先搜收藏，没有则经 [fnmusic-ext](https://gitee.com/superxyline/fnos_music_ext) 增强搜索（本地曲库 + 在线源）；在线歌自动**下载**进本地音乐库（**不污染收藏**），点播的歌放完没人管会自动接播收藏随机歌单
- 🔄 **自动同步**：飞牛音乐收藏增减约 5 分钟自动同步到歌单（也可语音说「刷新列表」立即同步）
- 🗣️ **完整语音控制**：下一首 / 上一首 / 暂停 / 随机播放 / 全部循环 / 单曲循环 / 顺序播放
- 📱 **三步安装向导**：小米账号登录（支持密码 / 米家 App 扫码）→ 勾选小爱音箱 → 自动扫描连接飞牛音乐
- 📦 **安装零联网**：FPK 内置全部 Docker 镜像（约 184MB），无需拉取镜像或构建源码
- 🔁 **升级保数据**：重装/升级自动保留小米账号绑定状态

## 项目结构

```
fnmusic-xiaomusic/
├── fpk-v2-src/                   # FPK 打包源码
│   ├── manifest / config / cmd / wizard   # 生命周期脚本与安装向导
│   └── app/
│       ├── docker/fnmusic-app/   # 应用源码（桥接服务 + 向导 UI）
│       └── docker/docker-compose.yaml
├── bridge-v2/                    # 桥接服务源码（开发主目录，与 FPK 内同步）
├── docker-compose.yml            # 手动 Docker 部署（非飞牛 NAS / 不走 App 中心时用）
│   ├── app.py                    # 主应用：三步向导 + 飞牛音乐桥接 + xiaomusic 集成
│   ├── fnmusic_client.py         # 飞牛音乐 API 客户端（登录/收藏/音频流/authx 签名）
│   ├── static/wizard.html        # 三步向导 + 状态页（单文件，无外部依赖）
│   └── Dockerfile / requirements.txt
├── scripts/                      # 打包与部署脚本
└── docs/部署指南.md               # 详细部署文档
```

## 部署方法（适用于飞牛 NAS）

> 前置要求：飞牛 fnOS（已安装并正常运行**飞牛音乐**）、小爱音箱、小米账号、飞牛音乐账号。
> 安装包下载地址见 [Releases](../../releases) 页面。

### 方式一：App 中心手动安装（推荐）

1. 在 [Releases](../../releases) 页面下载 `xiaomusic-fnmusic-0.2.fpk`
2. 飞牛桌面 → **App 中心** → 右上角「手动安装」→ 选择下载的 FPK
3. 安装向导只需填两项：**NAS 局域网 IP**（如 192.168.31.26）、**应用端口**（默认 58091）
4. 等待安装完成（约 1-2 分钟，主要是加载内置镜像），应用状态变为「运行中」

### 方式二：SSH 命令行安装

```bash
# 将 FPK 上传到 NAS 后（如 /tmp/xiaomusic-fnmusic-0.2.fpk），SSH 到 NAS 执行：
cat > /tmp/xm-install.env <<'EOF'
nas_ip=192.168.31.26      # 改成你的 NAS 局域网 IP
bridge_port=58091         # 应用端口（被占用就换）
EOF
sudo appcenter-cli install-fpk /tmp/xiaomusic-fnmusic-0.2.fpk -e /tmp/xm-install.env -v 3
```

> `-v 3` 是存储卷索引，请按你 NAS 的实际卷调整（App 中心图形安装则无需关心）。

### 安装后：三步向导

浏览器打开 `http://NAS_IP:58091`（或点桌面「小爱音箱」图标）：

1. **登录小米账号** —— 账号密码，或用「米家 App」扫二维码
2. **勾选小爱音箱** —— 自动列出账号下的设备，勾选要接管的音箱（可多选）
3. **连接飞牛音乐** —— 自动扫描 NAS 上的飞牛音乐服务，填写飞牛音乐账号密码，完成

完成后即可语音使用。升级版本时直接卸载重装，小米账号绑定会自动迁移。

## 使用方式

### 语音口令（对小爱音箱说）

| 口令 | 效果 |
| --- | --- |
| **播放收藏 / 播放本地 / 播放本地收藏歌曲** | 随机播放飞牛音乐收藏（每次都重新打乱顺序） |
| **播放晴天 / 播放周杰伦的晴天** | 点歌：搜收藏 → 没有 → 在线搜并自动下载（不进收藏）→ 播放 |
| 下一首 / 上一首 | 切换歌曲（顺序不打乱） |
| 停止播放 / 关机 | 停止 |
| 随机播放 / 全部循环 / 单曲循环 / 顺序播放 | 切换播放模式 |
| 刷新列表 | 重新加载歌单（改了收藏不想等同步时用） |

> 点播的歌自然放完且没有后续指令时，自动接播收藏随机歌单；期间任何新指令（停止 / 下一首 / 新点歌）都不会被打断式接管。

### Web 界面

- **`http://NAS_IP:58091/`**：状态页（收藏数 / 歌单数 / 推送状态 / 最近错误）+「立即同步」+ 重新配置入口
- **`http://NAS_IP:58091/xm/`**：xiaomusic 原版高级设置（设备管理、播放控制等）

### 日常维护

- **改配置**（NAS IP / 端口）：飞牛 App 中心 → 应用设置 → 配置，保存后自动重启生效
- **看日志**：飞牛 Docker → 容器 `fnmusic-xiaomusic` → 日志（桥接与 xiaomusic 日志都在这）
- **小米登录失效**：小米服务端会吊销长期不活跃的 token——重新走向导第 1 步（扫码最快），数据不丢

## 重新打包 FPK（开发用）

```bash
# 1. 本地打骨架（不含镜像）
fnpack build --directory fpk-v2-src
python scripts/repack_fpk.py xiaomusic-fnmusic.fpk xiaomusic-fnmusic-base.fpk   # 修复 cmd 脚本权限位

# 2. 上传骨架到 NAS 构建（需先在 NAS 的 ~/ffbin/ 放置静态 ffmpeg，
#    下载自 https://registry.npmmirror.com/-/binary/ffmpeg-static/b6.0/ffmpeg-linux-x64）
python scripts/nas_ssh_put.py xiaomusic-fnmusic-base.fpk /home/<user>/
# NAS 上执行：bash nas_v2_rebuild_all.sh（解包 → docker build → save → 注入 → 合成）

# 3. 下载最终 FPK
python scripts/nas_ssh_get.py /home/<user>/xiaomusic-fnmusic-0.2.fpk ./
```

## 已知限制

- **飞牛 API 非公开**：接口来自社区逆向，fnOS 大版本升级可能导致变动——桥接层已隔离风险，变动时只需更新 `fnmusic_client.py` 重新出包
- **小米 token 会过期**：小米服务端策略，过期后重新走向导第 1 步即可
- **小米账号安全**：xiaomusic 通过轮询对话记录工作，官方建议该账号不要同时绑定摄像头
- **进度拖动**：网络歌曲经 xiaomusic 代理播放，拖动进度会从头开始
- **容器内无 Node.js**：xiaomusic 的 JS 插件功能不可用（不影响核心功能）

## 致谢

本项目的核心能力建立在以下优秀开源项目之上，特别感谢：

- **[xiaomusic](https://github.com/hanxi/xiaomusic)**（涵曦）—— 本项目直接内嵌了 xiaomusic（pip 安装，作为子应用挂载于 `/xm/`），小米账号登录（含扫码）、小爱音箱设备管理、对话口令轮询、播放控制全部来自它。没有 xiaomusic 就没有这个项目，其扫码登录模块（`qrcode_login.py`）也被完整复用。
- [MiService / miservice-fork](https://github.com/yihong0618/MiService) —— xiaomusic 的小米服务接口层
- [xiaogpt](https://github.com/yihong0618/xiaogpt) —— 项目灵感来源
- [kuilei0926/FeiNiuMusic](https://github.com/kuilei0926/FeiNiuMusic) —— 飞牛音乐 Flutter 客户端（API 逆向：登录 / Cookie 认证）
- [Raduap/FN-Music-Apple](https://github.com/Raduap/FN-Music-Apple) —— 飞牛音乐 Windows 客户端（API 逆向）
- [qianlipp/fn-music-bridge](https://github.com/qianlipp/fn-music-bridge) —— 「音桥」（authx 签名算法与常量出处）
- [fmusic](https://blog.zwbcc.cn/archives/f966c451-281c-4d3a-a8dc-838b109e13df) —— authx 逆向详解

## License

本项目代码 MIT。所依赖与参考的第三方项目版权归原作者所有（见上文链接）。

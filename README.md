# 小爱音箱·飞牛音乐（fnmusic-xiaomusic）

> ## ⚠️ 本项目已归档：功能已完整并入 fnmusic-ext，不再更新
>
> **本仓库停止维护。** 从 2026-10-18 起，本项目的全部能力已移植进
> **[fnmusic-ext](https://github.com/superxyline/fnos_music_ext)（`fnos_music_ext` 二次开发版）v3.3.0**，
> 作为 `fnmusic-sources` 容器内第 5 个进程运行，与本扩展的音源、收藏、在线搜索共用同一套部署。
>
> | | 本项目（独立 FPK） | 现在：fnmusic-ext v3.3.0+ |
> | :--- | :--- | :--- |
> | 部署形态 | 独立应用 + 独立容器 | 内置为 `fnmusic-sources` 容器第 5 进程 |
> | 端口 | 58091 | 8775（容器内 8005） |
> | 配置入口 | 本项目自带向导页 | 管理台左侧菜单「**小爱音箱**」页（`http://<NAS_IP>:8774`） |
> | 升级 | 单独重装 FPK | 随 fnmusic-ext 一起升级，小米登录态与数据不丢 |
> | 口令能力 | 全部 | 完全一致（同一套桥接代码） |
>
> **新用户**：不要安装本项目。请直接安装
> [fnmusic-ext v3.3.0 及以上](https://github.com/superxyline/fnos_music_ext/releases)，
> 在管理台「小爱音箱」页完成三步配置（小米账号 → 勾选音箱 → 飞牛账号）即可。
>
> **老用户迁移**：应用中心卸载「小爱音箱·飞牛音乐」→ 安装 fnmusic-ext 3.3.0+ →
> 管理台开启「小爱音箱」并重新走三步配置（小米账号需重新扫码，飞牛音乐账号需重填；
> 两个应用的数据目录不同，无法自动搬移）。历史 FPK 仍保留在 [Releases](../../releases)，
> 可继续使用但**不再获得更新与修复**。
>
> **本项目版本缺失的重要修复**（仅在 fnmusic-ext v3.3.0+ 提供）：
> ① 口令轮询开关（`enable_pull_ask`）默认关闭导致「所有口令失效、音箱只播自己的在线试听」；
> ② 设备标识被存成 UUID 导致口令只对勾选的第一台音箱生效；
> ③ 「重新配置」无法重选设备/更换小米账号；
> ④ 「音箱访问地址」被预填成容器网关导致口令能收到但拉不到音频流。
> 若你在本项目上遇到以上问题，请迁移到 fnmusic-ext 后再试。

对家里的小爱音箱说 **「播放本地收藏歌曲」**，音箱即随机播放 NAS 上**飞牛音乐（fnOS trim.music）**的收藏列表。收藏有增减时自动同步（默认 5 分钟），全程语音控制，小爱侧零改动。

已封装为飞牛 FPK 应用：**一个安装包、一个端口（58091）、一个三步向导界面**。安装包内置全部镜像，安装过程不需要访问外网。

> 📦 以下文档保留为 **v0.2.1 历史版本** 的说明，仅供仍在用旧 FPK 的用户参考。

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

> 🚫 **本章为 v0.2.1 历史版本的部署方式，新用户请勿使用。**
> 请改用 [fnmusic-ext v3.3.0+](https://github.com/superxyline/fnos_music_ext/releases)，
> 其「小爱音箱」功能与本项目等价且包含后续修复（见文首归档说明）。

> 前置要求：飞牛 fnOS（已安装并正常运行**飞牛音乐**）、小爱音箱、小米账号、飞牛音乐账号。
> 安装包下载地址见 [Releases](../../releases) 页面。

### 方式一：App 中心手动安装（推荐）

1. 在 [Releases](../../releases) 页面下载 `xiaomusic-fnmusic-0.2.1.fpk`
2. 飞牛桌面 → **App 中心** → 右上角「手动安装」→ 选择下载的 FPK
3. 安装向导只需填两项：**NAS 局域网 IP**（如 192.168.31.26）、**应用端口**（默认 58091）
4. 等待安装完成（约 1-2 分钟，主要是加载内置镜像），应用状态变为「运行中」

### 方式二：SSH 命令行安装

```bash
# 将 FPK 上传到 NAS 后（如 /tmp/xiaomusic-fnmusic-0.2.1.fpk），SSH 到 NAS 执行：
cat > /tmp/xm-install.env <<'EOF'
nas_ip=192.168.31.26      # 改成你的 NAS 局域网 IP
bridge_port=58091         # 应用端口（被占用就换）
EOF
sudo appcenter-cli install-fpk /tmp/xiaomusic-fnmusic-0.2.1.fpk -e /tmp/xm-install.env -v 3
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
python scripts/nas_ssh_get.py /home/<user>/xiaomusic-fnmusic-0.2.1.fpk ./
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

## 归档说明

- **归档日期**：2026-10-18（最后版本 v0.2.1）
- **归档原因**：功能已完整并入 [fnmusic-ext](https://github.com/superxyline/fnos_music_ext) v3.3.0——独立 FPK 需要单独维护一套容器/端口/升级链路，合并后用户只需装一个应用、开一个开关，且能直接复用 fnmusic-ext 的在线搜索、收藏同步与代理取流能力。合并也便于集中修复问题（本轮口令失效等修复只在合并后的版本里）。
- **代码去向**：桥接主程序 `bridge-v2/app.py` + `fnmusic_client.py` + 向导页，已移植为 fnmusic-ext 仓库的 `xiaomusic-service/` 目录（含适配改动：数据目录 `/data/xiaomusic/`、内外端口分离 8005/8775、飞牛地址改用容器网关探测、ffmpeg 用镜像 apt 版）。
- **后续反馈**：本仓库不再接受 issue / PR。使用问题请提到 [fnmusic-ext issues](https://github.com/superxyline/fnos_music_ext/issues)。
- **历史版本**：v0.2.1 及更早的 FPK 仍保留在 [Releases](../../releases)，可继续安装使用，但不再修复问题、不跟进小米/飞牛接口变化。


## License

本项目代码 MIT。所依赖与参考的第三方项目版权归原作者所有（见上文链接）。

# Claude 网络住宅 IP 配置规则

给 Codex 使用的 **macOS / Windows + Clash Verge Rev / Mihomo** 本地配置工具与实施说明。把两份订阅合并进一个运行配置，分别使用各自节点，不需要手动切换订阅卡片，也不是把两份订阅串联中转。

**此仓库不提供住宅 IP 或订阅，也不保证防封号。** 复用的是分流策略，不是作者的账号、IP、节点、订阅密钥或电脑路径。你需要自己拥有普通订阅和固定住宅订阅。

## 流量如何分配

| 请求 | 路线 | 故障行为 |
|---|---|---|
| Claude 已识别客户端/Claude Code、Claude 域名 | 单个指定住宅节点 | 不换节点、不直连 |
| 发往专用 `127.0.0.1:17897` 的请求，包括下载 | 同一个指定住宅节点 | 代理失败则请求失败 |
| ChatGPT、Codex、Twitter、YouTube、普通外网 | 普通订阅：美国优先 → 其他地区 | 不占住宅额度；普通线路全故障时拒绝 |
| 国内网站、微信常见国内连接、私网 | DIRECT | 不消耗代理套餐；按请求目标识别，并非微信进程一律直连 |

实际联网路径：`Claude → 本机专用代理 → 固定住宅节点 → 目标网站`；`普通外网 → 本机 Clash → 普通订阅节点 → 目标网站`。在规则模式下同时生效，不需要前台“切换代理组”。美国优先按节点名称匹配，必须校对 `usPattern`；标签不是物理位置证明。健康检查有周期，切换不是零延迟。

## 直接交给 Codex

在目标 Mac 或 Windows 电脑克隆仓库后，把下面这段发给 Codex：

> 请读取本仓库 AGENTS.md、docs/SETUP.md；Windows 另读 docs/WINDOWS.md。在我的电脑上配置 Clash Verge，读取真实版本、订阅、脚本、节点和应用路径，使用我自己的两份订阅。只有 Claude 固定住宅，失败不换节点不直连；其他外网优先普通美国节点，失效可用其他普通地区，国内直连。配置 DNS 接管和浏览器 WebRTC 防泄露，不把整个浏览器改走住宅。先备份、生成候选并隔离测试，再应用、验证实际客户端和浏览器。不要启用 LuLu、改变时区或终止工作。缺少订阅身份或固定出口信息时再问，不能猜测。不上传私有配置；未通过的验收明确列出。

Codex 可以自动读取和配置，但**首次仍需明确哪份是住宅订阅、固定哪个节点、预期出口 IP**。操作系统权限提示需用户自己批准。未知 Claude Desktop 版本不能冒充已完成适配。

## DNS / WebRTC 防泄露与平台限制

**浏览器的 WebRTC 防护必须单独配置，分流规则本身不足以阻止 STUN 暴露直连地址。** 无需把整个浏览器或检测网站改走住宅。Chrome 运行 `python3 scripts/browser_privacy.py apply` 后，在 `chrome://policy` 重新加载并实际复测。Windows 已提供双订阅、命名管道热加载、Desktop 官方注册表、原生 Code、Chrome/Edge 和 DNS 检查流程，见 [Windows 完整入口](docs/WINDOWS.md)。Edge 使用不同的正式政策键。CI 不代替目标机浏览器、客户端及系统服务验收。

2026-10-29 起默认 **只有 Claude 走住宅**，ChatGPT 改走普通订阅。旧用户若确实需要保留 ChatGPT 住宅，可在私有设置显式添加 `"chatgptResidential": true`；更新代码不会自动修改正在运行的电脑，需要重新 prepare、审阅、apply。

## Windows 入口

先读 [docs/WINDOWS.md](docs/WINDOWS.md)。`scripts/windows_setup.py` 统一执行 prepare / apply / check / rollback；先用 `manage.py init` 从本机生成私有设置。原生 Windows Python 需要安装 `requirements.txt` 中的 PyYAML，不能套用 WSL 网络。系统权限批准、真实节点身份和有效浏览器政策检查不能跳过。

## macOS 快速命令

要求 Python 3.9+、Node.js 18+、curl、已安装的 Clash Verge Rev；YAML 读取使用 macOS Ruby，或你自己的 Python 环境中的 PyYAML。运行测试不需要账号。

```bash
python3 scripts/manage.py inspect
# UID 和节点名从 inspect 获得；预期公网出口先用隔离代理核验。
python3 scripts/manage.py init --residential-uid RES_UID --ordinary-uid NORMAL_UID \
  --node '你的固定住宅节点' --expected-ip '你的住宅公网IP'
# 仅在本地审阅 .private/settings.json，核对普通订阅身份、路径、DNS。
python3 scripts/manage.py prepare
# 先按 docs/SETUP.md 完成隔离验证，再执行下面的应用命令。
python3 scripts/manage.py apply
python3 scripts/clients.py plan
# Claude 正常退出后，才配置客户端；不会自动杀进程。
python3 scripts/clients.py apply
python3 scripts/manage.py check
# Claude Code 从此入口启动，包含启动出口校验：
python3 scripts/clients.py code -- --help
```

`prepare` 只生成候选与本地备份，不改运行配置；`apply` 才修改当前住宅订阅的扩展脚本和运行配置并热加载。仅语法通过不代表网络验收通过。**本工具会重建所选配置的 rules、proxy-groups 和 DNS 路由策略**，有企业内网/自定义规则时必须先合并审阅，不能盲目覆盖。TUN 启用时补齐 UDP/TCP 53 接管；不自动启用 TUN，系统代理、其他监听器保持现状，由 Codex 核实是否捕获到目标进程；本工具不自动开启系统网络扩展。

## 限制必须知道

- 这是代理分流与客户端代理设置，**不是独立系统防火墙**。代理遵从客户端在本机代理不可用时请求失败，但任意忽略代理的子进程、外部浏览器、远程容器/服务器不在完整保障范围。若要求全部进程在 Clash 完全退出后也无法直连，需要额外系统隔离，不能仅靠本仓库承诺。
- 已知 Claude 进程的 UDP 被拒绝；私网 TCP 保留。通过专用端口的所有请求（即使下载自通用 CDN）都走住宅。共享 Node/Python 进程不粗暴归类，需验证启动环境和实际连接。
- 启动检查是时间点检查，不是持续 IP 锁。运营商在同一入口后更换出口时，已运行连接不一定立即停止。脚本固定的是入口，独享、住宅和长期静态属性要由服务商保证。
- 公共域名规则不能识别所有“间接相关”请求；Claude 服务端代发的请求不经过你的 Mac。当前方案不会假装能够控制它们。
- DNS 对 Claude 走住宅解析，对 ChatGPT/Codex/普通外网走普通解析，国内和节点引导 DNS 独立。代理端的远端解析取决于服务商，不能承诺 DNS 检测一定显示同一个出口 IP。
- 没有广告过滤、解密 HTTPS、安装证书、LuLu、系统时区修改或后台监控。

## 验证、恢复和维护

见 [实施流程](docs/SETUP.md)、[客户端边界](docs/CLIENTS.md)、[测试记录](docs/VALIDATION.md)、[来源与许可](docs/SOURCES.md)。

```bash
node --test tests/routing.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py'
# 停止客户端后回退客户端设置（如本次配置过）：
python3 scripts/clients.py rollback
python3 scripts/manage.py rollback
```

所有订阅凭据、备份、生成脚本和本地报告在 `.private/`，默认忽略且权限收紧。不要把整份 Clash 配置、日志或 `.private` 上传到 Issue。订阅更新会重新执行持久扩展脚本；住宅入口身份不匹配会变成 REJECT，不自动挑其他住宅节点。普通 provider 按自身周期更新；订阅 URL 变更需重新生成计划。运行计划不能重复使用：后续修订用 `--plan .private/plan-2`，保留旧备份。

MIT 许可适用于本仓库原创工具与文档。Mihomo、Clash Verge 及其数据规则库保持各自许可；此仓库不捆绑它们。

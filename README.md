# Claude 网络住宅 IP 配置规则

**让本地 Codex 先识别环境，再按流量用途配置代理。** 支持一个或多个节点来源，不要求恰好两份订阅，也不要求一定购买住宅套餐。仓库名称保留；住宅只是用户可以选择的一种 Claude 出口，不是节点质量证明。

入口：[完整通用提示词](docs/UNIVERSAL-PROMPT.md) · [通用实施流程](docs/UNIVERSAL.md) · [DNS / WebRTC](docs/LEAK-PROTECTION.md)。这里只发布策略与工具，不提供节点、凭据，不保证账号不被停用。

## 分流原则

| 用途 | 路线 | 失败处理 |
|---|---|---|
| 已识别的 Claude 请求、受支持客户端及专用代理入口 | 用户明确选定的一个固定节点 | 请求失败，不切其他节点、不直连 |
| ChatGPT、Codex、Twitter、YouTube、普通外网 | 用户选定的普通节点池，可来自多份订阅 | 默认美国优先，再尝试其他普通节点；不借 Claude 专线 |
| 国内及内网请求 | 按用户所在地区、现有本地规则与企业网络确定 DIRECT | 不粗暴把整个微信或整个浏览器归类 |

一份订阅里的多个节点也可以分别承担角色。专线专用的来源不进入普通池；混合套餐需要明确标记 `mixed` 并选定节点。节点名称不是住宅/地理/计费身份的证明。仅有一个节点又要求“专线不供普通外网使用”时，普通外网无法同时获得代理服务；工具不会偷偷直连或共用，而会要求明确接受普通流量拒绝，或补充普通节点。

## 当前能自动到哪一步

| 实际客户端/设备 | 生成与配置路径 | 实机边界 |
|---|---|---|
| Windows / Mac，Clash Verge Rev + Mihomo | 自动发现本地 profile，通用清单生成，多来源候选；接现有备份、校验、热加载、客户端与回滚工具 | 必须核验目标版本、浏览器与真实连接链 |
| 其他真实 Mihomo 客户端，例如桌面或 Android 的兼容客户端 | 从该客户端原生导出生成 Mihomo JSON（YAML 兼容）候选 | 先用其实际内核编译，再走该 App 正式导入；不猜写内部配置库 |
| iPhone，Shadowrocket | 原生导出 → 多来源 `.conf`；可复用 Windows/Mac USB Documents 传输 | 实验适配，原生导入、VPN、DNS/STUN 尚需接机验收 |
| Mac / iPhone，Surge | 原生导出 → 独立 Surge `.conf`，含原生 STUN 拒绝规则 | 新增实验适配；目前限 HTTP/HTTPS/SOCKS5/SS/Trojan 的已支持参数；未实机 |
| sing-box、Quantumult X、Loon、其他未知引擎/格式 | 先盘点官方导出/导入、格式和能力，保存本地计划 | 没有通用写入器；不把别的语法硬塞进去，不擅自换客户端 |

**通用的是角色模型、检测顺序和验收要求，不是“所有 App 共用一种文件、所有手机权限都可自动批准”。** 有可用本地工具时 Codex 继续执行受支持的配置步骤；没有真实设备或原生接口的步骤明确待验证，不能伪造成功。不能把 Android、iOS、桌面 Chrome 的 WebRTC 设置互相替代。

## 先检查，再配置

在目标机使用 [通用提示词](docs/UNIVERSAL-PROMPT.md)。Codex 先检查现有网络、客户端、浏览器、版本、节点与权限，复用已装软件；只补齐必要且已授权的依赖。未知角色、实际权限提示、付费和工作中应用退出等实质门槛才请求用户。

```sh
# Python 可执行名以目标机为准；discover只读本机，报告写入私有目录。
python scripts/universal.py capabilities
python scripts/universal.py discover --output .private/discovery-1
# 已确认是本机 Clash Verge 后，自动读取所有可解析的本地节点来源。
python scripts/universal.py draft --adapter clash-verge --manifest .private/universal.json
# Codex 根据私有盘点补全角色、实际版本、出口、地区及DNS/WebRTC方案。
python scripts/universal.py prepare --manifest .private/universal.json --output .private/candidate-1
python scripts/universal.py check --manifest .private/universal.json --output .private/candidate-1
```

`draft` 不猜哪个套餐属于专线。`prepare` 只生成新候选，不改变系统代理/TUN/DNS/客户端。通用候选与实际安装计划是两个目录，不能互相覆盖。后续部署命令和各客户端恢复步骤见 [实施流程](docs/UNIVERSAL.md)。

当前通用模式把获准节点生成**私有快照**：不依赖 GUI 当前选中了哪张订阅卡，也不串联两个套餐。普通池不会在订阅更新时悄悄扩大范围。供应商更改节点后，要重新读取、校对出口及角色、生成新计划；旧参数失效不会自动换节点。原双订阅 HTTP/file provider 的动态更新模式作为兼容入口保留，新用户优先通用模式。

## DNS 和 WebRTC 分开处理

- Mihomo 对 Claude、普通外网、直连目标分别配置解析路径；独立节点引导 DNS 避免循环。只有真的进入内核的请求才受它控制。
- 桌面 Chrome/Edge 用正式浏览器政策，检查有效政策再测 STUN，不为检测绿勾把整个浏览器或检测站改走专线。
- Shadowrocket 使用原生 Disable STUN 选项并实际验证；Surge 使用 `PROTOCOL,STUN,REJECT`。Mihomo 手机客户端没有浏览器政策写入器，可在用户了解音视频影响后选择拒绝进入该 VPN 的 UDP；这不是全系统防火墙。
- 手机原生适配使用用户明确选择的 IP 字面量 DoH，避免解析服务引导依赖系统 DNS；它不保证递归 DNS IP 等于 Claude 出口。手机应用自身 DoH、IPv6、Wi-Fi/蜂窝与 VPN 关闭均须另验。
- 不为了安装先开 TUN，不自动关闭浏览器 DoH；已有健康网络保留。Windows TUN 可选试验先启动独立本地恢复进程，不依赖在线 Codex 才能回退。

[完整隐私边界与测试方法](docs/LEAK-PROTECTION.md)。住宅/独享/静态属性由服务商和实际观测确定；固定代理入口不是持续公网 IP 锁，不能防止服务商在入口之后改变出口。

## 手机与 USB

手机每台独立生成清单，使用手机自己的订阅/导出，不复制电脑路径、端口或账号。iPhone 系统信任、VPN 批准、商店登录或购买必须由本人完成。Shadowrocket 的 USB 工具只访问获准的 Documents 文件共享，不读取完整容器/备份。其他 App 走自己的正式文件导入；Android 也使用原生导出/导入，不自动开启 USB 调试、root 或安装不明 APK。

手机未连接时可完成主机准备和离线候选，但不能称手机已配置。已授权且有设备工具时继续导入、验证；没有 UI 工具时提示用户完成具体界面动作并续接。

[手机流程](docs/MOBILE.md) · [USB](docs/MOBILE-USB.md) · [Windows+iPhone准备](docs/WINDOWS-IPHONE-PREPARATION.md) · [Windows+iPhone顺序执行](docs/WINDOWS-IPHONE.md)

## 兼容、验收与恢复

原 `manage.py init` 双来源入口、Mac/Windows 客户端设置、浏览器政策、USB 工具和冲突保护仍保留，详见 [SETUP](docs/SETUP.md)、[Windows](docs/WINDOWS.md)、[客户端](docs/CLIENTS.md)。内部旧字段/组名中的“住宅”保留以兼容既有部署，不表示程序鉴定了住宅属性。

这不是独立系统防火墙。Clash/VPN 退出后，忽略代理的进程、任意工具子进程或手机原生应用不能仅凭分流规则保证不直连。要求这一层时必须另做系统/设备隔离，不以改配置文案冒充实现。共享 CDN 的第三方请求也不能仅凭域名自动全部归属 Claude。

```sh
node --test tests/routing.test.cjs tests/controller.test.cjs tests/watchdog.test.cjs
python -m unittest discover -s tests -p 'test_*.py'
# 可选：真实内核、全本机假上游，既不停止主代理也不消耗套餐。
python tests/integration.py --mihomo /path/to/mihomo --snapshots
```

[验证记录](docs/VALIDATION.md) · [能力变更](docs/CAPABILITY_MAP.md) · [来源和许可](docs/SOURCES.md)。所有私有清单、节点、备份和回执留在 `.private/`，不要提交到 GitHub。MIT 只覆盖本仓库原创实现；不捆绑第三方客户端或规则库。

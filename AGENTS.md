# 给 Codex / 本地配置代理

## 通用候选与兼容入口

- 新安装使用schema2多来源角色模型，不要求两份订阅或住宅节点。universal候选目录与manage/windows_setup安装计划目录分开；Verge绑定当前baseUid，无需切订阅卡。候选通过后继续获准部署，不只输出计划。其他App用正式导入，不猜内部库。
- 快照不自动拉新节点；变化须重新核对角色/出口/来源哈希。旧动态HTTP/file provider保留兼容，不把两种刷新方式混为一谈。
- browser-policy仅支持桌面Chrome/Edge；手机client-stun仅有原生实现的App；reject-udp须说明音视频/游戏影响并取得选择。不得用少数STUN端口黑名单冒充全部覆盖，不把普通浏览器整体改走专线。
- 手机原生DNS不等于Mihomo逐域名解析；DNS、STUN、IPv6、Wi-Fi/蜂窝、实际Claude入口分别验收，VPN退出全进程阻断未实现。Surge和Android新适配标注未实机。
- 以下具体Windows+iPhone、Verge、Shadowrocket流程仅在检测匹配后使用。未知App不擅自替换；继续独立已授权步骤。

## 目标与真实边界

先读 README.md、docs/UNIVERSAL.md、docs/UNIVERSAL-PROMPT.md 和 docs/LEAK-PROTECTION.md。只操作用户授权的目标设备。先检测 OS、客户端/真实内核、浏览器及任意数量来源，再选择适配器；不能预设两订阅、住宅套餐、Verge或小火箭。Claude 固定单个获准代理，普通流量只用获准普通池，两种角色不能互为备用。共享同一来源时明确 mixed 并选不同节点；同一入口不得加入普通池。不要承诺住宅纯净、独享或不封号。旧 chatgptResidential 仅兼容显式 opt-in，不是新用户默认。

Windows + iPhone 请求先执行 docs/WINDOWS-IPHONE-PREPARATION.md，软件/依赖缺失时不能直接运行依赖它们的Python工具。先盘点当前联网与权限；已获配置授权时自动复用/安装缺少的必要组件到适当独立环境，核实来源和结果，不只输出待安装清单。已有软件不一律升级或重装，不擅自重启/切网络/占住宅下载流量。UAC、信任、VPN、登录、付费或无界面能力等真实外部门槛才提示本人，记录.private进度，确认后重新检查并继续后续配置，不重跑已成功步骤。安装/准备成功不等于设备网络已验收。

## 必须遵循的实施顺序

1. 先用 `universal.py discover` 做本地有界盘点，报告不等于运行态/手机检测。识别为Verge后再用 `manage.py inspect` 读取当前 profile 与真实路径。不打印 URL、UUID、密码、完整配置或用户聊天。确认 OS、Verge、Mihomo 版本、进程路径和节点角色。macOS 和原生 Windows 已有部署实现；Windows 先读 docs/WINDOWS.md 并用 windows_setup.py，WSL/Linux/未知平台需另做网络适配。
2. 读现有 profile/global merge/script，确认执行顺序。保留当前工作；记录哈希。不得把作者电脑的历史 IP、UID、路径写进目标电脑。
3. 用schema2私有清单选定一个固定Claude节点、零到多个普通节点和来源用途；普通池为空默认阻止生成，不能应用让当前Codex失联的候选。来源/基线哈希变化重新审阅；名称不能证明住宅或计费身份。预期公网IP经隔离代理验证或用户明确提供；不要自动批准新的出口。
4. 新安装用 universal.py draft/prepare/check；旧双来源init保留兼容，不是通用前提。校对私有设置，检查普通 provider 只来自获准节点、优先地区匹配、供应商特殊 bootstrap DNS、真实 bundle ID（不能仅凭名为 ChatGPT.app 就归为 Codex）。
5. prepare，审阅变更。候选替换现有规则/组，不能丢掉其他已知自定义能力。隔离测试使用备用端口、TUN 关闭、无系统代理变更；控制流量，不能跑大测速。必要时 `--interface`/本机物理接口防止测试连接再次被主 TUN 捕获。不要暂停生产节点来测试。
6. 用户已授权配置且候选验收通过后 apply。应用不会重启内核，但旧连接可能保持原路径，不能据此宣称全部迁移。不能删除所有连接或重启客户端打断用户开发。若 live 规则被其他脚本重新覆盖，应修持久来源而非循环重写 runtime。
7. 客户端设置只适配已识别格式。用户正常退出后再写，未知版本查其官方文档与本地配置。不要创建猜测的文件，不用浏览器伪装、关闭证书校验、改系统时区解决问题。
8. 验证真实客户端页面/连接链、专用端口公网 IP、普通订阅美国故障/全故障、住宅失败、代理监听消失；后两项在隔离环境验证。区分配置检查、模拟测试、真实客户端测试和未验证部分。测试消息/付费调用不是默认必要动作。
9. 交付改动、证据、回退路径及剩余边界。只读诊断无法证明客户端已修复；代理设置无法证明全进程树强制隔离。

## 发布与维护

手机先读 docs/UNIVERSAL.md；iOS和Android分别识别实际App/原生格式，不从主机推断。Shadowrocket分支再读 docs/MOBILE.md 和 docs/MOBILE-USB.md。Surge走其原生配置，真实Mihomo移动端走原生内核编译/导入，未知引擎先做官方能力适配与测试；不得把Shadowrocket USB工具写入其他App。USB使用原生Windows或Mac与受信任Documents文件共享，先读实际iOS/App版本和导出；不要执行电脑manage.py配置手机。仅当App声明文件共享且实际VendDocuments成功才传输，拒绝后不改用VendContainer、全机备份、越狱或猜内部数据库。仅手机Codex阅读仓库不等于获得App读写权限。首次系统信任/VPN批准由用户完成。

Windows + iPhone 连续配置先读 docs/WINDOWS-IPHONE.md：先修本机未完成项，check 必须包括所选 Desktop/Code/Chrome，之后用 windows_phone.py 连接手机。doctor 先检查 Apple 服务，现有 USB 可用就不换驱动；不打开热点/开发者隧道。每次真实手机动作复查电脑状态，手机失败不能重跑已完成电脑 apply。使用手机自身订阅，不能直接复制电脑配置。

手机暂无订阅/未连接时，继续开发和离线测试；不要伪造版本、手机证据或 fullyVerified。用户要求先实机验收再发布时，保留本地候选，不能绕过发布顺序。Shadowrocket 原生编译、分组故障、DNS/STUN、Wi-Fi/蜂窝切换要分别验证。手机普通订阅默认含 ChatGPT；共享下载域名需连接证据，不能将整浏览器或全部 CDN 归住宅。手机实验适配不修改当前 Mac 网络。

仅提交公开源文件，不提交 .private、源订阅、真实节点参数、账户、个人路径、截图或日志。对改动跑 Node 和 Python 测试；涉及内核语义跑隔离 Mihomo 集成测试。不要自动更新生产内核或恢复旧后台任务。未知版本停止受影响步骤，继续独立准备工作。

## 防泄露验收新增要求

读取 docs/LEAK-PROTECTION.md。不能只改 Clash 就宣称 Chrome WebRTC 已保护：必须核验浏览器生效策略及真实 STUN 测试。不要为了让检测 IP 相同把整个 Chrome 或 IP 检测域名改走住宅。浏览器策略影响网页音视频，需告知；其他应用不受该策略控制。Windows 按本机 APPDATA、实际进程及命名管道配置，Desktop 用官方 HKCU 政策；存在 HKLM 冲突就停。账号暂停与网络错误分开记录，不能保证反封禁。

Windows 默认阶段交付包含：版本与签名、联网基线、阶段回执、Chrome 有效政策与 STUN、Claude 与普通连接链、隔离故障及回退。TUN/全面DNS是后续可选阶段：未选择时明确未验收；选择后要求 strict-route 与 UDP/TCP DNS 查询。不得为了补齐清单擅自启用TUN，不得把CI当目标机实测或修改fullyVerified字段伪造完成。

通用化与联网优先：个人字段从目标机init生成，端口自动选；不得复制作者地址或将本机回环入口当住宅IP。Windows先运行bootstrap确认系统代理可用，不要求TUN。不要修改另一台正常设备。TUN只在后续授权试验中启用，先启动独立本地恢复进程，成功也恢复基线；不依赖Codex在线才能回退。默认不改Chrome DoH；全面DNS必须独立验收。明确套餐身份/固定出口，不能从节点名称猜付费归属。未安装Codex允许空路径；无Claude客户端时需显式domains-only范围，不能生成空进程正则。

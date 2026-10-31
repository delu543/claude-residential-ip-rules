# 功能与变更边界

## 当前通用架构（2026-10-31）

- active：schema2来源ID/节点角色模型、一个或多个来源、同来源mixed分节点、专线排除、同入口别名/重复防护、哈希漂移拒绝、全私有候选和回执。
- active：有界主机盘点与草稿，真实信息不齐保留未选择；不推断套餐属性或手机权限。
- changed：新主入口universal.py + 通用提示词取代强制“两份订阅/小火箭”的默认假设。原manage/mobile双来源入口保持兼容。
- changed：通用模式使用已审阅节点快照；普通池跨来源，固定节点独立于当前GUI订阅；Verge部署复用原备份/热加载/回滚，保留工作网络。
- active：Mihomo生成、Node/Python回归与本机假上游集成测试。实际目标版本/浏览器/服务仍须验收。
- experimental：其他Mihomo客户端原生导入（包括Android）、多来源Shadowrocket、原生Surge适配；没有真实移动设备/Surge验收。
- changed：隐私按设备/引擎分派，新增Claude域名UDP拒绝覆盖domain-only。浏览器政策、原生STUN、可选UDP拒绝分别说明影响和验证。
- retained：Windows阶段配置、Mac客户端、Chrome/Edge回退、USB Documents和Windows每步主机复查；不移除已有稳定能力。
- 未实现：任意客户端全自动写入、自动获取手机权限、VPN退出全进程隔离、住宅质量/防封号保证。旧表里的“active”均指工具实现，不等于任意设备验收。

| 能力 | 状态 | 验收 |
|---|---|---|
| 双订阅同一内核分流 | active | provider来源、配置和连接链 |
| Claude固定住宅、无自动备用 | active | selector单节点、listener绑定、隔离故障 |
| Claude住宅与其他普通线路区分 | active | 已识别路径优先级、真实进程 |
| 普通线路美国优先、跨地区fallback | active | 隔离内核健康/失效场景 |
| 国内/本地直连 | active | 规则顺序与受控请求 |
| 参数化安装、私有备份与冲突回滚 | active | Python测试、候选语法检查 |
| 已识别Desktop配置和Code启动器 | active | 保留已有键；真实UI验收另做 |
| 任意子进程/Clash退出的强制隔离 | experimental | 未实现，不作保证 |
| Chrome WebRTC 隐私策略及可回退设置 | active | 生效策略 + 真实 STUN 测试（macOS 实测；Windows 未实机） |
| DNS 分流及 UDP/TCP 接管 | active | 配置、系统查询、浏览器 DNS 观测分层验收 |
| LuLu / 广告过滤 / 系统时区修改 | removed | 本仓库不包含 |

相对源配置的变化：普通外网从部分亚洲地区优先统一到美国优先及其他普通地区备用；不再发布源机器硬编码路径、固定IP和供应商节点DNS；缺失住宅入口改成可编译的拒绝节点；提供生成/备份/回滚工具。发布本身不会修改运行配置；目标电脑需单独实施与验收。

## Windows 新增能力

- active：APPDATA/实际进程盘点、named pipe控制、跨平台规则生成与回退。
- active：Windows TUN严格路由、DNS四查询审计、Chrome/Edge分开写官方政策。
- active：支持版本Desktop的HKCU代理、原生Code设置、阶段式配置和回执。
- experimental：目标Windows完整浏览器/客户端/服务联调（需现场验收）；WSL/容器未覆盖。
- changed：Mac-only入口改为平台分派；原Mac工作流、单住宅无备用及数据保留不变。

## 通用化及联网优先（取代前一版TUN前置要求）

- active：空个人字段模板、本机自动端口/冲突检测、协议/入口本地读取、普通remote/file来源。
- active：地区/DNS可配置；缺少Codex不阻断；domain-only显式范围，空路径不生成全匹配正则。
- replaced：Windows强制TUN安装前提 → 系统代理基线优先；默认不改Chrome DoH。
- active：可选TUN临时试验与独立本地恢复进程，成功也恢复基线；这是恢复尝试，不是OS故障下的绝对保证。
- active：真实机器状态不因文档截图而修改；更新仓库不等于更新正在运行的网络。

## 手机/USB 新增（实验阶段，未实机）

- changed：Claude/OpenAI 域名集中到 src/policy.json；Verge生成脚本内嵌，不增加运行时文件读取。电脑路由语义保持。
- experimental：Shadowrocket 原生节点快照与本地规则基线 → 私有候选/哈希回执；未知协议、混合源、住宅消失停止生成。
- experimental：Windows/macOS 通过 pymobiledevice3 的受信任 USB Documents 共享探测、指定文档导出、新文件传输和读回。没有 App 数据共享就停止，不升级为完整容器访问。
- experimental：手机 fallback/DNS/STUN/故障回归；当前只有离线与模拟测试，未实机。
- 未实现且不承诺：自动授权、手机任意进程归属、无设备接口的全自动安装、VPN退出强制断网。
- 无能力移除：Mac/Windows、普通订阅与住宅隔离、回滚及联网优先流程保留。依赖只装在可选私有venv。

## Windows + iPhone 顺序扩展（2026-10-30）

- active：Windows check 补齐所选 Desktop/Code/Chrome 设置回读；未完成步骤、过期成功或政策漂移不再通过。
- active：保留已健康的 TUN 路径，系统代理未打开不自动触发切换；默认仍联网优先。
- experimental：Windows Apple 服务/USB 只读前检、原生 Windows USB 后端与每步复查桌面的 windows_phone 入口。真实 Windows+iPhone 仍待接机验证。
- active：UTF-8 子进程、独立依赖环境、保留备份及新建传输文件。
- 无能力移除：桌面规则、Mac USB、数据保留和恢复流程不变；没有新增系统权限绕过或手机界面自动化保证。

## 准备清单与提示词同步（2026-10-30）

- changed：执行入口增加软件/依赖/权限盘点，授权内自动补齐必要缺项、安装后验证并续接电脑/手机配置。
- active：现有网络/软件复用、单项系统确认、私有进度记录、接机后续接；不自动升级内核、切网、重启或付费。
- 无代码或能力移除：本次仅说明/提示词更新，安装动作由目标本地 Codex 按实际工具与授权执行；doctor 继续只读，手机实机限制不变。

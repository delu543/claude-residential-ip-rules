# 功能与变更边界

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

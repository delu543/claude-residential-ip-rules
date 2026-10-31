# iPhone + Shadowrocket

> New installations: start with [Universal setup](UNIVERSAL.md) and the [single maintained prompt](UNIVERSAL-PROMPT.md). Detect the actual device/client and any number of sources first. This page documents a specific adapter or the legacy two-source workflow; it is not a universal client/subscription requirement.


状态：**原生配置候选生成已实现；iPhone 实机验收未完成**。目标版本来自用户：2.2.93（3488）。iOS 版本由接线后的设备读取，不以“最新版”替代真实版本。操作入口是 Windows 或 Mac 上的 Codex + USB，见 [USB流程](MOBILE-USB.md)；Windows 先完成 [电脑再手机流程](WINDOWS-IPHONE.md)。手机分支不运行电脑的 `manage.py apply`，不修改电脑的工作网络。

## 能力与边界

| 目标 | 生成行为 | 必须实机确认 |
|---|---|---|
| Claude 已知域名 | 一个内嵌固定住宅节点，select 只有一个成员；无 DIRECT/其他节点 | 手机代理日志与住宅出口；住宅失败不外溢 |
| Claude 新的下载地址 | 经记录确认后加入 `extraClaudeDomains`，不把共享 CDN 整体住宅化 | 域名范围和实际请求归属 |
| 普通外网/ChatGPT/Codex | 只引用普通源的节点；优先地区排序后的单层 fallback | 2.2.93 的优先顺序、故障切换与全失效行为 |
| 国内/本地 | 从该手机审阅后的本地规则基线保留 DIRECT 分类 | 微信、国内 CDN、局域网业务 |
| DNS | 已知代理域名优先匹配；IP规则 no-resolve；显式加密 DNS、无系统备用 | 实际远端解析、明文 DNS、IPv6、应用自带 DoH |
| WebRTC | 不生成伪 IP，也不复制桌面 Chrome 政策；要求小火箭“禁用 STUN”并复测 | Safari/Chrome 实际 STUN；音视频兼容性 |
| VPN 关闭 | **没有系统强制隔离** | 不得宣传为 VPN-off kill switch |

手机不能用 `PROCESS-PATH` 区分 Claude 的任意请求。未识别的共享服务、IP-only、工具代发或远程服务请求，不会因为它“间接来自 Claude”就自动走住宅。只有在确认域名映射后才纳入固定规则。若必须所有请求连 VPN 关闭都阻断，应评估受管理设备/独立网络隔离，本工具不具备此能力。按需连接不是这种强制隔离的证明。

## 输入从目标用户取得

1. 将用户自己的一个或多个来源导入实际使用的小火箭，明确固定Claude及普通角色；订阅名称不能证明线路属性。确认固定节点和允许的实际出口IP。多来源走universal，下面旧init命令仅为双来源兼容示例。
2. 保留原配置名称、原节点和原开关状态，导出可恢复副本。先验证普通线路能用，不在配置第一步全局代理或大范围改 DNS/TUN。
3. 使用客户端真实导出的原生节点参数。生成器接受含 `[Proxy]` 的Shadowrocket `.conf`快照；universal支持任意数量文件及同来源mixed分节点。**小火箭“导出配置”可能只有规则，“导出节点”可能是JSON；缺少 `[Proxy]`、未知JSON/URI/Clash YAML不会被当作已适配。** 按真实格式另做经过验证的适配，不猜字段或发送在线转换网站。
4. 规则基线用该用户小火箭内置 `default.conf` 或其明确审阅的无广告分流配置，导出到本地。只接受明确 DIRECT/PROXY 的域名、IP/Country 规则；脚本、自定义 Host（默认 localhost 映射可保留）、重写、远程 RULE-SET 或自定义组先独立审阅，不能悄悄丢掉。

这条输入边界意味着当前版本不是“任意订阅格式一键转换器”。相同源/同 endpoint 混入普通线路会拒绝生成；这是防止误用套餐，不能证明供应商后台无共享或出口不变。

## 离线生成

在电脑仓库工作目录执行。Windows 使用对应 venv 的 python.exe；下面反斜线换行是 shell 示例，PowerShell 请将参数放同一行或使用反引号换行。以下路径只是本地输入示例；所有真实参数保留在 `.private/`。

```sh
python3 scripts/mobile.py capabilities
python3 scripts/mobile.py inspect --file .private/phone-residential.conf
python3 scripts/mobile.py inspect --file .private/phone-ordinary.conf
python3 scripts/mobile.py init \
  --residential-file .private/phone-residential.conf \
  --ordinary-file .private/phone-ordinary.conf \
  --baseline-file .private/phone-baseline.conf \
  --node '用户确认的固定节点名' --expected-ip '用户确认的出口IP' --country US \
  --ios-version 'USB probe 返回的实际版本' \
  --shadowrocket-version '2.2.93 (3488)' \
  --dns 'https://1.1.1.1/dns-query'
# 上面 DNS 仅示例；需选本网络可用、TLS有效且支持 IP URL 的 DoH。
# 本地审阅 mobile-settings.json；ordinaryNodes 只保留普通订阅有效节点。
python3 scripts/mobile.py prepare
python3 scripts/mobile.py check
```

输出 `.private/mobile-plan/shadowrocket.conf`（含节点密钥）和 `receipt.json`。它们不可发布到 GitHub、Issue、公共链接或第三方短链。生成器不下载订阅、不读取电脑当前网络、不改变手机设置。原有文件从不覆盖；后续计划用 `--output .private/mobile-plan-2`。配置和源哈希发生变化，旧验证不能复用。

原生协议支持是保守白名单：SS、VMess、VLESS、Trojan、Hysteria2 的已审阅参数。Reality/传输层扩展只原样保留已识别字段，不猜测映射；未知参数立即停止。不得为了生成成功移除参数或关闭 TLS 验证。来源节点内嵌为快照，因此手机自动更新原订阅不会更新本文件；更新后重新生成、核对固定身份并验证。住宅节点更名/缺失会停止生成，保留之前文件，不自动选新节点。

普通组默认按名称匹配美国优先，支持本地 `preferredPattern`；排序标签不是地域证据。使用单层组避免照搬桌面嵌套策略，周期测试仍可能有切换延迟。普通组不含住宅、DIRECT 或默认 PROXY。`expectedIp` 只是验收预期值，生成器不会持续观测或锁定供应商出口；入口不变而出口变化时，这份配置不能自动发现或拦截。

## 导入与隐私开关

走 USB 工具传输或小火箭受支持的“从文件导入”，作为**新的配置**导入，保留原配置可切回。原生编译成功前不能启用；不删除旧订阅/配置。仅传输成功不算启用成功。

- 全局路由选“配置”。核对全局回退、简单模式和场景覆盖；不让默认 PROXY 决定住宅路线。关闭全局回退，普通组自身保留 fallback。
- 在目标版本界面核对“设置 → UDP → 禁用 STUN”，然后测试；此项可能影响网页/应用音视频。未知界面不猜按钮或写内部数据库。禁止用 `stun-response-ip` 伪造检测通过。
- DNS 示例只覆盖受小火箭处理的请求。已知 Claude 域名需由住宅代理处理，国内用指定加密解析，节点引导也需验证。应用自带 DoH、硬编码 IP、系统豁免和 IPv6 路径不能仅从配置文本推断。
- 不将桌面 `WebRtcIPHandling` 注册表/偏好设置搬到 iOS Chrome。`ipv6=false` 只是客户端选项，不是整机 IPv6 禁用证据。

## 手机验收和恢复

每个项目保存对应配置哈希、时间、实际 iOS/App 版本、结果与最少的连接证据到本地。不要上传私有节点或完整日志。

1. 基线：普通代理、国内网站和原配置恢复路径可用；电脑 Codex 仍可访问网络。
2. 原生编译/应用：两组的实际成员正确，住宅只有固定节点，普通无住宅；新配置实际启用。
3. 正常流量：Claude 请求进入住宅；ChatGPT/普通外网进入普通；国内请求 DIRECT。不能用普通 IP 检测页面的 IP 代替 Claude 连接链证据。
4. 住宅故障：先退出手机 Claude，在独立测试副本中使住宅端点不可用，用不含账号凭据的测试请求检查失败与日志；不得改/暂停真实住宅服务或影响电脑。确认没有普通/DIRECT 尝试后恢复副本，重新验证住宅出口再使用 Claude。
5. 普通故障：用独立副本验证美国失效改走其他普通节点，普通全失效不借住宅；记录测试周期和恢复时间。
6. DNS/STUN：用实际手机浏览器、Wi-Fi与蜂窝分别测试；观察请求的实际出口、解析和 IPv6。只见“未检出”不能证明所有流量都被阻断。
7. VPN 关闭：已知不提供全系统 kill switch。不要用已登录 Claude 做直连试验；若必须验证隔离，先设计独立系统方案。
8. 回滚：停止手机 Claude，选择之前保留的原配置/路由模式，恢复原开关并验证普通网络。若原配置不保护 Claude，在重新验收前保持 Claude 关闭。无需 Codex 在线，不需删除新文件。USB工具不会自动重启任何 VPN。

当前 `receipt.json` 的手机项全部初始为 pending；`check` 只检查离线完整性，不能将其输出改成现场通过。开发/模拟完成与手机全链路验收分开交付。

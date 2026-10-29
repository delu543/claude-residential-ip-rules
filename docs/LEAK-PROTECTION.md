# DNS、WebRTC 与故障诊断

## 两个独立层面

分流选择请求出口；WebRTC 策略决定网页能否自行建立直连 STUN/ICE 连接。国内网站 DIRECT + 普通外网代理时，如果浏览器未限制 WebRTC，同一网页可向国内 STUN 发请求并拿到国内公网地址，即使网页 HTTP 出口在国外。这是覆盖缺口，不能靠把检测网站改成住宅来修复。

默认只有 Claude 域名、已识别 Claude 进程和专用 HTTP 入口走住宅。ChatGPT、Codex、普通外网和检测网站走普通订阅；国内保持直连。浏览器不是整体绑定住宅，网页中的任意第三方请求也不能仅靠域名表自动认定属于 Claude。需要全部第三方请求固定住宅时使用独立浏览器实例/显式专用代理，并另做实际验证，不要全局修改普通 Chrome。

## Chrome WebRTC（macOS / Windows）

使用 Chrome 官方 `WebRtcIPHandling=disable_non_proxied_udp`。不安装证书，不解密流量，不需要下载扩展，不关闭全部软件 UDP。该策略限制未经过代理的 UDP；支持代理的 TCP/TURN 仍可能工作，不能把它称为完全关闭 WebRTC。

```sh
python3 scripts/browser_privacy.py check
python3 scripts/browser_privacy.py apply
```

工具仅修改 macOS 当前用户 `com.google.Chrome` 中一个键，或 Windows HKCU `Software\Policies\Google\Chrome` 中同名 REG_SZ。保存旧值在 `.private/browser-policy.json`，不改用户代理、语言、时区、DNS 或其他策略。已配置则不覆盖备份。

在 Chrome 的 `chrome://policy` 点重新加载政策，确认键名、值及状态 OK；若受企业管理策略覆盖，停止并由管理员处理，不能绕过。**写入本地值不等于浏览器已采纳**。重新加载 STUN 检测页，核验国内和海外服务器，记录时间、浏览器版本与结果。测试页显示“未检测到 WebRTC IP 泄露”只说明这批测试没有取得地址，不证明所有网站、原生客户端、任意子进程都无泄露。

网页音视频可能变慢或连接失败；微信等独立应用不由 Chrome 策略控制。Chrome、Edge、Firefox 和 Electron 客户端是不同入口，不可拿一个浏览器的结果代替其他入口。Mac 原生已识别 Claude 进程另有 UDP 拒绝规则；Windows 实际进程路径必须重新适配。

恢复（会恢复原有 WebRTC 行为，只在用户明确需要回退时执行）：

```sh
python3 scripts/browser_privacy.py rollback
```

随后重新加载政策。回退只恢复该键，有后续改动则拒绝覆盖。若原来无该键，只移除本次新增的设置值，不删除浏览器文件或其他策略。

## DNS 路径与验证

- Claude 四类域名（claude.ai / claude.com / anthropic.com / claudeusercontent.com）的 `nameserver-policy` 显式指定 `https://1.1.1.1/dns-query#Claude 固定出口`。
- 普通海外域名经普通代理 DoH；国内域名走国内 DoH；节点引导解析独立，避免 DNS 依赖代理、代理又依赖 DNS 的循环。引导 DNS 可能直连，这是必要例外，不是“系统所有 DNS 都不出本地网络”的保证。
- 当前生成器对已启用 TUN 补齐 `any:53` 和 `tcp://any:53`。不要盲目启用 TUN、覆盖原网关或企业内网。仅有规则并不能证明系统 DNS 被捕获。
- macOS/Windows 的 LAN DNS 有接管边界；必须核对实际系统解析器。Windows `strict-route` 有助于防多宿主 DNS 泄露，但可能影响虚拟网络；需按内核版本单独验证。不要把新版本文档字段强加给旧内核。
- 浏览器 Secure DNS/应用内 DoH 是 HTTPS 流量，不受端口 53 接管约束。若检测结果异常，应确认解析服务连接实际走向；不要直接认定“开 DoH 就安全”或粗暴全局关闭加密 DNS。
- IPv4、IPv6 都要验证。关闭 DNS AAAA 返回不等于系统 IPv6 已被隔离。

验收分层：

1. 核对运行态 rule、TUN、系统解析器、DNS 策略与 Claude 单节点组；记录版本，不发布原配置或凭据。
2. 对实际系统解析器分别做 UDP/TCP DNS 查询，例如 `dig @<系统DNS> claude.ai A +short` 与 `+tcp`；fake-IP 回答证明这次查询被接管，**不证明上游路径一定无泄露**。
3. 从浏览器运行 DNS 检测，记录递归解析器。普通线路可能显示普通节点供应商的解析器；递归 DNS IP 本来就不必等于网页出口。国内主动 DIRECT 的 DNS 不构成全机防泄露承诺。
4. 检查 Claude 真实连接链与专用端口出口。HTTP 代理可将目标域名交给远端节点解析，因此服务商解析路径也须纳入边界；本地无法仅靠规则保证远端 DNS 的实现。
5. 代理/节点故障测试放在隔离内核，不关闭生产 Clash 或打断开发。DNS 报告未完成时写“未验证”，不能用 WebRTC 绿勾代替 DNS 验收。

## 订阅入口或端口更新

固定线路与服务商订阅更新是两件事。服务商可能保留公网出口但更换入站服务器或端口；旧四元组钉选会停止连接，这是拒绝回退的预期行为，不能靠加入 DIRECT 或普通节点备用修复。读取最新订阅到本地私有候选，隔离测试新入口的公网出口与既定 IP 相同，再经已授权的修复更新私有设置、重新 prepare / apply。未经核验不自动接受新的公网 IP。旧配置与客户端设置保留用于回退；失效旧端口的回退只恢复配置，不保证恢复网络。

## Chrome 登录错误与账号暂停分开处理

`Can't reach Claude`、连接超时和页面资源失败属于连接/前端症状；HTTP 403 也可能来自未登录探测或防机器人验证，不能据此宣布账号被封。保留已有登录会话，使用新的普通 `/login` 页面验证，不复用或上传带 nonce/token 的登录链接。主文档 200 不代表脚本、初始化 API 或 OAuth 回调都成功。

`account suspended/on hold` 是账号状态，修代理不会解除。住宅、独享、新邮箱均不保证账号可用。不同电脑、系统、出口和账号必须独立取证，不能将 Mac 测试当作 Windows 成功。按 [Anthropic 官方申诉说明](https://support.claude.com/en/articles/8241253-safeguards-warnings-and-appeals) 请求审核；仓库不用于规避账号停用。

Windows 已增加自动配置入口，见 [WINDOWS.md](WINDOWS.md)。先读取实际版本、路径、模式、TUN/DNS 和连接链，再用 windows_setup.py 准备、应用和验证。不要提供订阅 URL、UUID、密码、登录 nonce 或账号 Cookie；账号停用需单独官方审核。

## Windows 浏览器与 DNS

Chrome 使用 WebRtcIPHandling；Edge 使用 WebRtcLocalhostIpHandling，后者需正常重启，个人微软账号配置可能不适用，必须实测。不能只写注册表就宣称生效。Windows TUN 使用 auto-route、strict-route、UDP/TCP 53 和 fake-IP；局域网 DNS、加密 DNS、IPv6 仍须按目标机验收。

默认 WebRTC 命令不改 DNS。独立 `browser_privacy.py --policy dns` 在固定出口和 TUN 预检通过后设置 DnsOverHttpsMode=off，将浏览器解析交给系统/TUN，再做 DNS 查询测试。关闭 DoH 本身不是防泄露措施，Clash/TUN 退出后也不具备全系统 DNS 强制隔离。Windows 统一流程包含该阶段，回退先恢复浏览器 DNS 政策再恢复路由。

## 官方依据

- [Chrome WebRtcIPHandling](https://chromeenterprise.google/policies/#WebRtcIPHandling)
- [Chromium 策略定义](https://chromium.googlesource.com/chromium/src/+/main/components/policy/resources/templates/policy_definitions/WebRtc/WebRtcIPHandling.yaml)
- [Mihomo TUN 与 DNS 接管限制](https://wiki.metacubex.one/en/config/inbound/tun/)
- [Mihomo DNS](https://wiki.metacubex.one/en/config/dns/)

以上借鉴公开接口说明，没有复制第三方软件或整套规则库。以目标机实际版本和测试为准。

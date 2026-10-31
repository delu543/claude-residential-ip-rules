# Windows + Chrome：先保持联网，再分阶段配置

> New installations: start with [Universal setup](UNIVERSAL.md) and the [single maintained prompt](UNIVERSAL-PROMPT.md). Detect the actual device/client and any number of sources first. This page documents a specific adapter or the legacy two-source workflow; it is not a universal client/subscription requirement.


目标电脑由本机Codex执行。**不要先开TUN来安装本仓库。** 系统代理和TUN是不同接管方式；系统代理可用、TUN不可用时，先保留能联网的系统代理。无需改动另一台正常电脑。只有目标电脑的诊断能确认其故障原因。

先读 [通用化与个人参数](PORTABILITY.md) 和 [客户端边界](CLIENTS.md)。本仓库不提供订阅、住宅IP或账号，不复制作者的地址和路径。默认Chrome，不改Edge。

还要接 iPhone 时，先执行 [软件/依赖/权限准备清单](WINDOWS-IPHONE-PREPARATION.md)，完成本页电脑步骤后进入 [Windows → USB iPhone](WINDOWS-IPHONE.md)；可直接使用其中的 Codex 提示词。依赖缺失由已获授权的本机 Codex 核实并补齐，不要求用户逐条手工安装。

## 0. 前置网络检查，任何写入之前

使用原生Windows PowerShell/Python，不在WSL。要求已安装Clash Verge Rev、Node.js 18+、Python 3.9+和curl.exe。内核参考语义基线v1.19.15，实际版本仍要语法验收；本仓库不自动更新内核/安装驱动/禁用安全功能。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/bootstrap.py --verge-dir "实际Verge配置目录"
.\.venv\Scripts\python.exe scripts/manage.py inspect --verge-dir "实际Verge配置目录"
```

默认目录从APPDATA确定；便携版用Verge“打开配置目录”确认后传参数。bootstrap只读记录网卡、默认路由、DNS、Verge服务与系统代理设置；通过普通HTTP/mixed本机端口做一个小型连通性请求。结果只存`.private/bootstrap.json`，不要上传访问/设备信息。

- 系统代理可用且TUN关闭：按下文继续。
- 当前TUN已开启且一切正常：保留现状，不为“标准化”反复开关，也不要运行要求TUN关闭的trial。
- 开TUN整机不通、关TUN系统代理正常：在目标机恢复已知可用模式后继续。此时TUN不是必需步骤，先完成客户端显式代理和Chrome WebRTC。
- 系统代理本身也不通：先查节点、套餐、监听端口、控制接口和服务。不能用打开TUN来掩盖未完成的基线检查。

只有注册表系统代理开关还不够，真实HTTP必须可达。Codex的实际连接仍需观察；检查不表示所有应用已联网。bootstrap失败不写配置、不关闭DoH、不启用TUN。

## 1. 从个人配置生成参数

明确两份订阅身份、固定住宅节点和已测量的住宅公网IP。国家默认US，可`--country`改为已批准的实际国家；不能凭节点名认定。专用端口自动选，所有后续工具引用私有设置中的同一端口。

```powershell
.\.venv\Scripts\python.exe scripts/manage.py init --residential-uid RES_UID --ordinary-uid NORMAL_UID --node "你的固定住宅节点名" --expected-ip "已验证公网IP" --country US
```

自定义配置目录时init也传`--verge-dir`。应用未运行/路径未发现时补真实`--claude-path`；Codex不是必装依赖。只用网页选`--scope domains-only`，不得称全客户端保护。不同地区/本地订阅/DNS参数见PORTABILITY.md。

## 2. 自动配置系统代理阶段

```powershell
.\.venv\Scripts\python.exe scripts/windows_setup.py prepare --exe "实际Claude.exe路径" --mihomo "实际verge-mihomo.exe路径"
.\.venv\Scripts\python.exe tests/integration.py --mihomo "实际verge-mihomo.exe路径"
# 审阅候选。到写客户端设置时才保存工作、正常退出Claude，不退出Clash。
.\.venv\Scripts\python.exe scripts/windows_setup.py apply
.\.venv\Scripts\python.exe scripts/windows_setup.py check
```

仅原生Code用`prepare --clients code`；只配置路由和浏览器用空`--clients`；Desktop需要实际exe。默认Chrome，可选其他浏览器需明确指定。自定义plan每次命令传同一`--plan`。

`check` 会重新检查所选 Desktop、Code、Chrome 设置，拒绝未完成/中断工作流，并在 `verification.json` 区分设置检查与实际界面验证；旧的成功报告不能掩盖新失败。

阶段内容：

1. 再次确认现有系统代理联网，生成并用实际内核检查候选。
2. 写持久分流和运行配置，用本地named pipe热加载；住宅/普通连通性失败则恢复旧配置。保留当前TUN状态，不强制打开。
3. 受支持Claude Desktop通过官方HKCU固定HTTP代理，清除覆盖它的PAC；核验版本至少1.44121.1和签名，机器HKLM政策冲突时停止。原生Code写代理环境，保留其他设置。
4. Chrome写WebRtcIPHandling=disable_non_proxied_udp。用户在chrome://policy重新加载，实际跑STUN IPv4/IPv6测试。
5. 保留Chrome原来的DoH和系统DNS设置。此阶段只声明系统代理/显式代理和已实测WebRTC，不声明全系统DNS强接管。

没有强制杀进程、修改时区、安装证书、启用LuLu或把全部Chrome走住宅。代码脚本不强制TUN=true，避免用户关掉后又被脚本自动开启。

Code检查启动器：`scripts/clients.py code --binary "实际原生claude.exe" -- --help`。WSL、共享Node、远程容器需要单独适配，不把全部Node/Python流量归住宅。

## 3. TUN仅作为后续可选验收，有本地恢复进程

只有用户需要TUN全面接管、系统代理基线稳定且允许短时测试时，在目标Windows执行：

```powershell
.\.venv\Scripts\python.exe scripts/tun_trial.py run --mihomo "实际verge-mihomo.exe路径" --seconds 60
```

该命令拒绝在Mac或当前TUN已经开启时运行。使用独立临时目录保存基线和候选，不改浏览器、系统代理或持久profile脚本。先启动并确认本地恢复进程，再临时加载TUN候选。恢复进程不依赖Codex连接或互联网，收到请求或达到期限后通过本机控制接口恢复基线；主测试进程退出后它仍可运行。**成功也会恢复，最终TUN保持关闭，不会把试验默认为长期启用。**

测试检查固定住宅、普通线路、非显式代理HTTP、系统/显式DNS的UDP/TCP请求。检查失败保留诊断，不自动换住宅/扩大直连。每次新试验用新的`--plan`目录。正常网络上的开发仍可能受短暂TUN切换影响，所以不能在未获目标用户允许时运行。

恢复不是对故障OS/死亡内核的绝对保证：若服务崩溃、管道消失或权限拒绝，本地恢复也可能失败；`restore-error.json`会记录，用户用Verge切回系统代理。手动恢复命令为`tun_trial.py restore --plan 对应试验目录`，不需要联网。

诊断方向：服务/UAC权限、其他VPN/网络扩展、虚拟交换机、物理接口选路、多网卡DNS、LAN DNS不可被普通劫持、特定协议栈兼容性。只根据报告修根因，不同时换节点/DNS/MTU/协议栈猜测，不自动关闭系统防火墙。

## 4. 需要长期TUN及DNS防泄露时的收尾

trial通过后，目标Codex先审阅其结果，再按用户选择在Verge正常开启TUN并配置已验证的auto-route、strict-route、UDP/TCP53接管及fake-IP。私有`windowsDnsProtection=true`可让持久脚本在TUN**已经开启时**补齐这些参数；它不会主动开启TUN。重新prepare时用新plan，保持变更证据和回退。Verge服务批准/UAC仍由用户完成。

```powershell
.\.venv\Scripts\python.exe scripts/windows_setup.py check --full
.\.venv\Scripts\python.exe scripts/browser_privacy.py apply --policy dns
```

`--full`才要求DNS全面检查；浏览器DNS命令在真实UDP/TCP查询已通过后才设置DnsOverHttpsMode=off，将解析交给系统/TUN。不满足时原设置不变。关闭DoH本身不是防泄露；Clash退出后也不具备独立系统隔离。

实际Chrome测试：WebRTC不出现本地公网IPv4/IPv6，DNS观察无意外本地解析，HTTP出口仍按普通订阅。Claude域名DNS经住宅DoH，普通外网经普通DoH，国内和节点引导独立。服务商远端解析不能仅靠本机配置保证。LAN DNS、第三方DoH、IPv6和企业网须单独检查。

## 5. 恢复与最终交付

`windows_setup.py rollback`按已记录步骤逆序恢复Chrome WebRTC、Code、Desktop、路由。可选DNS步骤独立执行过时，**先**`browser_privacy.py rollback --policy dns`，再恢复路由；TUN trial无长期变更，使用其独立恢复证据。

若workflow.json有pending，先检查该步回执和实际状态，确认未写/已恢复/已成功后再修正状态，不盲目重跑或覆盖备份。所有备份保留在用户目录，Windows依赖用户目录ACL，不声称Unix0600就是Windows权限。

交付分开记录：基线联网、分流连接链、Chrome有效政策/WebRTC、可选TUN和DNS、客户端/工具下载、隔离故障。未做TUN不伪称全系统DNS验收通过，CI不等于目标机实测，网络设置不保证不封号或解除停用。

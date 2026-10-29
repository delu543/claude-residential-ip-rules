# Windows 10/11：完整实施入口

本流程给在**目标 Windows 本机**运行的 Codex 使用。不是下载仓库就自动获得作者的订阅/IP，也不能自动批准 UAC、绕过企业政策、解除账号暂停。仓库提供自动配置、验证脚本和回退；最终需要目标机浏览器/客户端验收。原生 Windows 与 WSL、远程 SSH、Docker 是不同网络环境，不能把本机通过算成它们通过。

## 自动执行的范围

- 两份订阅合并：住宅 profile 为基础，普通订阅以 provider 注入；只有 Claude/专用端口住宅，其他外网普通美国优先再其他地区，国内直连。
- Windows 路径按实际进程读取；不把所有 node.exe、python.exe 或 chrome.exe 归住宅。版本更新导致路径变化后重新盘点。
- 本机 Mihomo named pipe 热加载，不新增 LAN 控制端口、不打印订阅/secret。
- Windows TUN 已开启时补齐 auto-route、strict-route 和 UDP/TCP 53 接管、fake-ip。TUN 原本关闭时，仅在明确使用 `--enable-tun` 后纳入候选；服务/UAC仍须系统批准。
- Claude Desktop 官方 `egressProxyUrl` 用户政策固定17897，清除优先级更高的PAC键；版本和数字签名检查，遇机器策略冲突停止。
- Claude Code 用户 settings 的代理变量，专用启动器先做固定出口检查。保留其他键，不修改全系统代理环境变量。
- Chrome WebRTC 政策；可选 Edge 使用不同的正式键。浏览器 DoH 可交给已验证工作的 TUN DNS，不把整个浏览器改成住宅。
- 每阶段私有备份、回读、冲突检测、可恢复记录。不会杀进程或删除会话。

## 1. 环境与身份盘点

使用原生 PowerShell、Python 3.9+、Node.js 18+、Windows curl.exe。Clash Verge Rev及其服务需已安装；本仓库不自动下载安装程序或升级内核。参考语义基线 Mihomo v1.19.15，目标版本必须再跑语法测试。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/manage.py inspect
```

默认配置目录来自 `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev`；便携或自定义目录用 `--verge-dir` 指定**在 Verge 中打开配置目录后确认的路径**。`inspect`读取当前订阅与正在运行的 Claude/Codex 绝对路径；未运行/无权限读取时，不猜测，先确认实际安装文件，再补私有设置。不要把 `.private` 存在共享目录或上传到云端；Windows权限继承用户目录ACL，Unix的0600并非Windows ACL保证。

记录实际 Verge、Mihomo、Claude、Chrome/Edge 版本和签名；核对当前 profile 的全局及局部脚本执行顺序和重要自定义规则。候选会重建规则/组/DNS策略，不能覆盖未审阅的企业内网规则。

确定两份套餐身份和固定住宅入口后，用独立 Mihomo（TUN关闭、备用端口）验证预期公网IP。不能从节点名称/浏览器普通出口猜固定住宅IP。正常运行的 Claude 要保留；**客户端写入阶段才需要保存工作并正常退出**。

```powershell
.\.venv\Scripts\python.exe scripts/manage.py init --residential-uid RES_UID --ordinary-uid NORMAL_UID --node "固定住宅节点的真实名称" --expected-ip "已验证的住宅出口IP"
```

如果TUN原本未开启而用户同意启用，加`--enable-tun`；这会影响系统路由，必须将影响纳入候选审阅。切勿以全局代理模式代替规则模式。

## 2. 准备、隔离验收、应用

在 `.private/settings.json` 确认 `platform=win32`、实际 `apiPipe`、两个真实进程路径列表、固定四元组和出口。普通provider不得含住宅。不要手工将`apiPipe`设成远程管道，不暴露无认证的TCP API。`windowsTun=true`仅表示已明确选择启用TUN；服务尚未授权时不能报就绪。

```powershell
.\.venv\Scripts\python.exe scripts/windows_setup.py prepare --exe "C:\实际安装路径\Claude.exe" --mihomo "C:\实际安装路径\verge-mihomo.exe"
# 本机假代理回归，不使用住宅订阅、不关闭主Clash：
.\.venv\Scripts\python.exe tests/integration.py --mihomo "C:\实际安装路径\verge-mihomo.exe"
# 审阅 .private/windows-plan 后，保存工作并正常退出Claude；不退出Clash。
.\.venv\Scripts\python.exe scripts/windows_setup.py apply
.\.venv\Scripts\python.exe scripts/windows_setup.py check
```

`prepare`默认Chrome；若实际使用Edge，在prepare时加`--browsers chrome edge`（仅选实际使用者）。自定义`--plan`路径后每条命令都传同一plan。apply按准备时保存的步骤执行，依次配置路由、Desktop、Code、浏览器政策；失败立即停在该步骤，成功步骤保留在workflow.json，不假称所有阶段成功。不会自动切换住宅节点或改变公网IP。

Claude策略仅写`HKCU\SOFTWARE\Policies\Claude`两个网络键，不改账户、推理提供方、证书或时区。存在HKLM机器政策时先停，由管理员审阅有效源；不覆盖管理政策。受支持版本至少1.44121.1，但版本/签名检查也不能替代客户端日志和实际连接验收。官方说明主要在Desktop网络配置文档中，未知发行版应停在适配边界。

原生Code可以从检查启动器启动：

```powershell
.\.venv\Scripts\python.exe scripts/clients.py code --binary "C:\实际安装路径\claude.exe" -- --help
```

不要把`.cmd`/`.ps1`包装器或WSL路径冒充本机原生exe。npm安装共享Node的情况需逐项适配，不能给所有Node放住宅。项目级/托管Code设置可能覆盖用户代理，必须在实际项目验证。

## 3. DNS与WebRTC必须分层验收

`windows_setup.py check`检查真实内核运行模式、TUN/auto-route/strict-route、固定出口，并对claude.ai执行系统/显式外部DNS的UDP/TCP四种查询；预期fake-IP。保存`.private/windows-plan/audit.json`，只写本地，不上传访问记录。失败不能跳过并称全部完成。

浏览器：

1. Chrome在`chrome://policy`重新加载，`WebRtcIPHandling=disable_non_proxied_udp`状态正常。Edge使用`WebRtcLocalhostIpHandling`同值，需要正常重启浏览器；个人微软账号配置可能不适用，必须看策略状态和STUN，必要时选Chrome。已有企业策略、URL覆盖规则/扩展冲突先查清，不能仅看注册表。
2. DNS阶段设置`DnsOverHttpsMode=off`，**只有固定出口检查和TUN自动/严格路由通过后才执行**，让浏览器使用系统/TUN分域解析。关闭浏览器DoH本身不是防泄露；Clash/TUN退出后仍可能回到系统DNS，所以不能把它说成独立防火墙。回退时先恢复浏览器DNS政策，再恢复路由。
3. 用实际浏览器运行国内/海外STUN测试，确认无本地公网IPv4/IPv6暴露；再用DNS测试页检查解析器。浏览器普通HTTP出口仍为普通订阅，不要求与住宅相同。全绿仅证明本次检测样本，不证明未来所有请求。
4. 物理网卡DNS指向局域网路由器时，TUN的普通劫持可能覆盖不到；先看Get-DnsClientServerAddress和四项查询结果。脚本不盲目更改企业DNS、禁IPv6或全系统阻断53。发现LAN DNS/加密DNS旁路，需要根据目标机适配再验收，不能忽略。
5. Windows多网卡解析由strict-route补强；虚拟机、企业VPN、虚拟交换机有兼容性风险。检查其网络，出现异常先按回退流程恢复，不叠加多个过滤器。

DNS策略：Claude域名→住宅DoH；普通外网→普通DoH；国内/节点引导DNS按需直连。远端节点可能自行解析目标，取决于服务商；递归解析器IP不必等于出口IP。

## 4. 最终验收清单

Codex应保存配置层、系统层、浏览器层、客户端层四份结果：

- Claude页面、Code请求、下载和工具分别观察真实进程/链；只有已观察或显式代理遵从的请求可算通过。
- 普通外网/Codex/ChatGPT走普通provider，国内DIRECT；住宅计费只覆盖Claude相关捕获请求。
- 住宅失败不换节点不直连、普通US失效用其他普通地区、全部普通失效拒绝、监听消失请求失败，用隔离测试验收。
- 桌面主进程、更新器、沙箱、共享Node/MCP、IPv6、WSL分别列已测/未测；不把浏览器全绿当作全部客户端强隔离。
- 登录验证和账号停用分别处理。不要反复注册、更换地区来代替官方申诉；本配置不保证账号不被停用。

## 5. 恢复与中断

```powershell
.\.venv\Scripts\python.exe scripts/windows_setup.py rollback
```

按逆序恢复本次写过的浏览器策略、Code、Desktop、路由；检测后续修改则拒绝覆盖。备份保留。若workflow.json有pending，说明某步失败或被中断：先读取该步私有回执和实际状态（manage应用失败自带回退），确认未写/已恢复/成功后再由Codex只修该步状态，不能重复重跑或删除备份。每个子工具都有独立rollback，可依据其回执恢复。策略写入前若没有改动的必要则不生成备份，不应回退用户原有保护。

测试层级：Linux/macOS单元与集成、Windows CI的真实命名管道/隔离注册表测试，**均不能替代目标Windows的Clash、管理员服务、浏览器、Claude实机验收**。安装收尾不得把`fullyVerified:false`改成true来跳过未完成检查。

# Windows 电脑 → USB iPhone：按顺序执行

适用于在 **目标 Windows 电脑的 Codex** 中执行：先修复和核验 Windows + Clash Verge Rev + Chrome，再处理数据线连接的 iPhone + Shadowrocket。没有连接手机也能先完成电脑步骤。不能用本仓库作者的 Mac、另一台 Windows 或 CI 代替这两台目标设备的验收。

执行提示词见 [WINDOWS-IPHONE-PROMPT.md](WINDOWS-IPHONE-PROMPT.md)。本流程不需要重新设计路由：复用现有 Windows 安装器、手机生成器和 Documents 传输，只补齐阶段衔接。下载仓库本身不会修改任何网络设置。

## 零、先检查并补齐准备项

先执行 [准备清单与自动补齐流程](WINDOWS-IPHONE-PREPARATION.md)，再运行下文依赖 Python/Node 的工具。由 Codex 检查并复用现有软件，在已授权范围自动安装必要缺项、建立独立环境、回读验证。只有确实需要本人确认的系统弹窗/操作或缺失输入才提示；完成后继续本页，不止于准备报告。已经联网的系统代理/TUN、生产内核及其他项目环境保持，安装要求重启/切网时先说明影响并保存进度。手机未连接时仍可完成电脑阶段。

## 一、先让 Windows 完成配置

1. 读取 AGENTS、[WINDOWS](WINDOWS.md)、[PORTABILITY](PORTABILITY.md)、[LEAK-PROTECTION](LEAK-PROTECTION.md)。在原生 PowerShell 操作，不用 WSL。先检查本机已安装的 Python、Node、curl、Verge/Mihomo/Claude/Chrome 版本和真实路径。
2. 读取旧 `.private/windows-plan/workflow.json`、备份和实际配置。不要凭“昨天没完成”重置所有设置。状态为 pending 时逐步对照回执修复；旧配置与备份保留，新候选用新 plan 目录。
3. 用 `bootstrap.py` 确认当前联网。TUN 故障时优先恢复已有系统代理；当前 TUN 健康时保持原状。普通本机监听和现用路径都要可用，不能只看开关。不得为部署脚本先开 TUN、关安全软件或更换住宅节点。
4. 明确本机两份订阅角色与固定住宅入口/公网出口，按 WINDOWS.md 执行 init/prepare、实际内核语法检查及隔离故障测试，然后 apply。只在需要写客户端设置时让用户保存并正常退出 Claude；不退出 Clash，不中止 Codex。
5. `windows_setup.py check` 现在同时复查：固定住宅出口、普通/现用路径、所选 Desktop 政策、Code 的六个代理环境键、Chrome 的 WebRTC 持久政策。缺项、机器政策覆盖、步骤中断均不能通过。新结果写入 plan 的 `verification.json`，失败会撤销旧报告中的成功状态。
6. 浏览器有效政策/STUN、Claude 和普通流量连接链、项目级环境覆盖、工具子进程另做实际验证。默认只检查选定的范围；仅选 Code 或网页不能报告 Desktop 已完成。报告中的 `fullyVerified=false` 不可手改为 true。
7. 全面 DNS 接管按 WINDOWS.md 的后续 TUN 流程实施：先试验与独立恢复，再实际 UDP/TCP、浏览器 DNS、IPv6 验收。不能在 TUN 未验证前关闭 Chrome DoH。若用户未允许可能影响网络的试验，或试验失败，保留工作网络并明确这一项未验收。规则配置不等于任何程序都无法直连。

```powershell
# 这里的解释器/plan 用刚才实际检查过的路径；下文仅示例默认目录。
.\.venv\Scripts\python.exe scripts/windows_setup.py check --plan .private/windows-plan
```

## 二、准备 Windows 的 USB 工具

独立可选 USB 依赖需要 Python **3.11+ / OpenSSL**。已存在环境先核对，不覆盖旧环境。Windows 桌面工具和 USB 工具可以是不同的 Python；用 `--usb-python` 明确传入，避免安装到了另一套环境。

```powershell
# 先用 py -0p 找到已安装的 3.11+ 解释器，以下示例为 3.12。
py -3.12 -m venv .private/mobile-tools
.\.private\mobile-tools\Scripts\python.exe -m pip install -r requirements-mobile.txt
.\.venv\Scripts\python.exe scripts/windows_phone.py doctor
```

`doctor` 只读检查：Python/依赖、Apple Devices 是否存在、Apple 设备服务、USB Apple 设备状态及实际 usbmux 通信；不记录设备序列号，不改服务、驱动、网卡、代理或 VPN。`readyForUSB=true` 只表示主机通信接口可用，不表示已连接或信任 iPhone。

| 状态 | 下一步 |
|---|---|
| host-prerequisite-missing | 按提示修正独立 Python/固定依赖，重新 doctor |
| backend-import-failed | 核对依赖安装日志和系统架构；不盲目升级依赖 |
| usbmux-unreachable | 检查官方 Apple Devices/iTunes 设备服务和数据线；仅充电线不够 |
| no-usb-device | 电脑配置保留，连接并解锁手机后继续；不重跑电脑 apply |
| usb-detected | 选择该设备指纹，首次按正常信任流程 pair |

Apple 官方提供 [Windows 文件共享](https://support.apple.com/en-ie/120402)。上游 [pymobiledevice3 Windows 安装说明](https://github.com/doronz88/pymobiledevice3/blob/master/docs/installation.md)要求 Apple 设备服务。已有 Apple Devices/iTunes 且 USB 工作就复用，不为了 Wi-Fi 发现而换软件。本工具 **USB-only**。缺少服务时从 Apple/Microsoft 官方渠道安装合适组件，系统安装/UAC由用户确认；不从不明镜像安装驱动、不同时堆叠多个驱动、不重置手机信任或卸载其他软件。不需要个人热点、开发者隧道、越狱或全机备份。

## 三、电脑检查通过后识别手机

```powershell
.\.venv\Scripts\python.exe scripts/windows_phone.py devices
.\.venv\Scripts\python.exe scripts/windows_phone.py pair --device "上一步设备指纹"
.\.venv\Scripts\python.exe scripts/windows_phone.py probe --device "同一指纹"
```

除 doctor 外，每次操作前都重新执行 Windows check，不信任缓存成功记录；失败就停止该次手机操作。真实 USB 操作在独立解释器中执行，UTF-8 处理中文，参数不经 shell 拼接。所有事件保存到 plan 同级的 `phone-events/计划名/`，默认 `.private/phone-events/windows-plan/`；doctor 不会提前创建电脑 plan 导致 prepare 冲突。若 plan/USB venv 自定义，每次传相同 `--desktop-plan` / `--usb-python`。

首次信任提示在 iPhone/Apple Devices 中由用户确认。`probe` 读取真实 iOS、Shadowrocket 版本/build，并验证 App 声明文件共享且 Documents 可读取。只能操作明确选择的文档，不能读取其他 App 或完整容器。若文件共享不可用，Windows 的 Apple Devices 也不会自动获得更高权限；改用小火箭正式导出/导入界面，当前工具不能越过这个限制。

## 四、读取手机自己的配置并生成、传输

先备份手机原配置、当前节点和模式；确认**手机**两份订阅身份（不假定与电脑相同），住宅固定节点和已批准出口。只读规则导出可能没有节点，必须另外通过正式导出拿到节点。当前接受审阅的原生 `.conf` `[Proxy]` 格式；未知 JSON/URI 格式先核对真实样本与协议后适配，不能猜字段、漏参数或上传在线转换器。

```powershell
.\.venv\Scripts\python.exe scripts/windows_phone.py pull --device "设备指纹" --document "已看到的原配置.conf" --destination .private/phone-original.conf
# 对明确选择的普通、住宅节点导出分别 pull；保留所有原件。
# 依 MOBILE.md 用手机实际文件/版本/出口/DNS执行 mobile.py init。
.\.venv\Scripts\python.exe scripts/mobile.py prepare
.\.venv\Scripts\python.exe scripts/mobile.py check
.\.venv\Scripts\python.exe scripts/windows_phone.py stage --device "同一指纹"
```

`stage` 只写新的随机 `.conf`，不覆盖现用配置；读回逐字节校验。中断时保留意图回执和可能的部分文件，先检查再恢复，不自动重复传输。完整命令及源字段见 [MOBILE](MOBILE.md) 和 [MOBILE-USB](MOBILE-USB.md)。配置不是永久订阅同步器；源节点变化需重新生成、传输并验证。

## 五、手机导入与验收不能省略

使用小火箭正式界面导入、编译并选择新配置，使用配置模式，核对单住宅组、普通 fallback、无全局回退/场景覆盖；打开其真实版本提供的 Disable STUN，不能伪造 STUN IP。iOS Chrome 也不使用 Windows Chrome 注册表政策。VPN 系统批准由用户完成。

通过实际已授权可用的手机界面工具协助；没有这种工具时明确让用户完成所需手机点击，不能把 USB 当作屏幕遥控或自动批准权限。**传输成功≠导入生效≠网络验收。**

验收至少包括：Claude实际住宅出口、普通外网不借住宅、国内直连、住宅不可用不回退、普通节点失效切换及全失效拒绝、DNS/STUN、Wi-Fi/蜂窝与IPv6、恢复原配置。故障验收应在测试配置/隔离条件下做，不停止正在工作的电脑 Clash。记录版本、时间、候选哈希和手机日志证据，未完成逐项写明。

电脑回退：先处理独立 DNS 政策，再执行该 plan 的 `windows_setup.py rollback`，后续修改冲突时停止覆盖。手机回退：正式界面选回备份的原配置、原模式及节点，验证联网；新增文档与证据保留，不删除历史数据。手机失败不回滚或重跑已验收的电脑配置。

当前能力：代码和模拟测试支持 Windows/macOS USB；Windows 主机实机配对、Shadowrocket 文件共享/导出格式、导入/VPN和网络验收尚未完成。用户接机后继续，不能承诺一段提示词能取消这些系统要求。

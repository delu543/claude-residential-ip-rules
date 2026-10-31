# Windows / Mac Codex + USB iPhone 工作流

> New installations: start with [Universal setup](UNIVERSAL.md) and the [single maintained prompt](UNIVERSAL-PROMPT.md). Detect the actual device/client and any number of sources first. This page documents a specific adapter or the legacy two-source workflow; it is not a universal client/subscription requirement.


这比仅在手机上阅读仓库更适合本项目：代码、测试、备份放在电脑；手机只承载真实 Shadowrocket 路由。**USB 不是读取任意 App 数据的授权，也不自动给予界面控制。** Apple 文件共享仅对支持该能力的 App 开放；信任配对、文件共享、VPN 批准是不同权限。

Windows 电脑先使用 [Windows → iPhone 顺序入口](WINDOWS-IPHONE.md)，含 PowerShell 命令、Apple 服务检查和电脑优先检查。本文下面的 shell 命令保留给 Mac；USB 协议和 Documents 安全边界两端相同。

## 首次连接前

工具仅依赖普通受信任 USB 连接，无越狱、Developer Mode、FUSE 扩展、远程后台服务器、全机备份或全容器访问。电脑与手机是否同 Apple ID 不用于识别，按 USB 设备指纹与 App 身份确认。

安装可选依赖到私有虚拟环境（不修改系统 Python、Clash 或代理设置）：

先选择已安装的 **Python 3.11+ / OpenSSL**。Mac 自带旧 Python/LibreSSL 不作为USB工具运行环境；Codex可检查已有运行时，不能直接覆盖系统Python。以下 python3 指这个经过检查的解释器；若旧venv存在，换一个新目录保留它。

```sh
python3 -m venv .private/mobile-tools
.private/mobile-tools/bin/python -m pip install -r requirements-mobile.txt
.private/mobile-tools/bin/python scripts/mobile_usb.py --help
```

当前固定 `pymobiledevice3==11.48.0`。它是独立上游 GPL-3.0 项目，体积和依赖多于纯规则生成器；不是本仓库原创实现或 Apple 官方软件。这里只用 USB pairing、指定 App 元数据与 VendDocuments/AFC 文件传输，不使用其其他能力。安装版本变动时先审接口，不自动升级生产环境。

## 连接与能力检测

1. USB 接 iPhone，解锁；在 iPhone 和 Finder/Apple Devices 出现信任提示时由用户确认。不通过脚本假定或绕过信任。
2. 以下命令默认 USB-only；两台手机时必须选明确指纹，不随机挑选。不输出序列号、设备名称或其他 App 清单。

```sh
.private/mobile-tools/bin/python scripts/mobile_usb.py devices
# 首次需要正常配对时才执行，会触发设备的正常授权流程：
.private/mobile-tools/bin/python scripts/mobile_usb.py pair --device 'devices返回的指纹'
.private/mobile-tools/bin/python scripts/mobile_usb.py probe --device 'devices返回的指纹'
```

`probe` 读取 iOS 版本、Shadowrocket 版本/build 和文件共享声明，并尝试读取 Documents 根目录中的 `.conf/.json` 文件名，不读取文件内容。若 App 不开放文件共享，返回 `file-sharing-unavailable`，停止 USB 传输分支；使用 App 自己的导出/导入界面。不能退回 VendContainer、读取 SQLite/钥匙串、提取全机备份或猜测内部路径。**是否开放只能由真实手机确定；当前尚未实机测试。**

## 导出、生成、传输

先在手机正常导出原配置/所选节点，或者在 `probe` 已见的文档里选择明确文件。只有下列显式操作才读内容：

```sh
.private/mobile-tools/bin/python scripts/mobile_usb.py pull \
  --device '目标指纹' --document '实际导出的配置.conf' \
  --destination .private/phone-baseline.conf
```

导出只允许 Documents 下 `.conf/.json`、最多8 MiB的普通文件，拒绝路径穿越和符号链接；写入新的私有本地文件。不自动把所有手机数据传给云端 Codex。普通/住宅两个源按 [手机流程](MOBILE.md) 生成设置与候选，缺少/未知格式先停止该步。

```sh
python3 scripts/mobile.py prepare
python3 scripts/mobile.py check
.private/mobile-tools/bin/python scripts/mobile_usb.py stage \
  --device '目标指纹' --settings .private/mobile-settings.json \
  --output .private/mobile-plan
```

`stage` 重新验证输入与候选哈希、实际设备版本，只写一个新的随机名称 `.conf`，从手机读回比较原始字节。写入前保存本地意图回执；中途拔线/失败不生成成功回执、不删除文件或自动重试。检查 `usb-transfer.json` 和 `usb-readback.json` 后决定恢复。原配置与节点不覆盖。

**stage 不启用配置或 VPN。** 需要通过小火箭正式导入/选择/编译界面完成。若电脑上有用户授权且实际可用的手机界面操作工具，可用它协助；不存在这种工具时不假装已点击。URL Scheme 与快捷指令只能调用 App 暴露的动作，不能读回完整设置或自行获得系统权限，本版本没有未经验证的一键快捷指令。

## 给 Mac Codex 的执行提示

> 读取 AGENTS.md、docs/MOBILE.md、docs/MOBILE-USB.md。我要为 USB 连接的 iPhone 上 Shadowrocket 配置双订阅分流。先检测设备、真实版本和 Documents 共享，不动 Mac 网络。用手机自己的两份订阅，确认住宅单节点和预期出口，复用手机审阅后的国内规则，生成私有候选。普通美国优先，失败可换其他普通节点；Claude只固定住宅，无备用/直连。备份后传入新文件并读回校验，通过正式界面导入、编译、核对模式和 STUN 设置，再实测正常/故障、DNS/WebRTC与回滚。系统信任和VPN批准由我确认。若接口不存在或输入格式未知，说明具体原因，不绕过权限、不扩大导出、不把文件传输等同网络验收。

## 当前验证范围

- 已实现：保守原生配置生成、离线校验、USB 设备选择/配对/能力探测、限定文档导出、新文件传输及读回回执。
- 本机可验证：工具依赖 API、代码回归、模拟传输/损坏/版本不符/路径越界。
- 尚未验证：实机配对、该版本 App 的共享接口、原生配置编译、实际路由/STUN/DNS及故障效果。无手机/订阅时无法提前消除这些外部验收。
- 不支持：自动批准系统信任、任意沙盒读写、无接口时无人值守导入、关闭 VPN 后的系统阻断。

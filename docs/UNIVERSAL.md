# 通用实施：先发现，再选择角色，最后部署

这是新安装的主入口。旧 `manage.py init` 和 `mobile.py init` 为双来源兼容接口保留；不再把它们的参数数量当作所有人的要求。`universal.py` 是离线盘点/规划工具，实际部署复用对应客户端原生能力，不自动激活 VPN。

## 1. 确认目标、保持联网

记录目标设备、OS/客户端/内核/浏览器的真实版本、安装路径、现有系统代理/TUN/VPN、路由/DNS与可用网络。使用该平台正式查询接口，命令输出保留在 `.private`，不要打印订阅密钥。`universal.py discover` 只做有界文件/应用盘点，不探测手机、不扫描局域网、不读取所有进程命令行，不把安装目录当作运行状态。

```sh
python scripts/universal.py discover --output .private/discovery-1
python scripts/universal.py capabilities
```

工具能发现已知位置的 Verge profiles、部分代理/浏览器安装线索、实际 Mac bundle 版本和 Claude/Codex 路径。Windows 安装版本、便携目录、活动客户端、浏览器有效政策及网络基线由目标 Codex 继续通过正式本地查询补齐；未知目录由 App 的“打开配置目录/导出”定位。不要因发现多个客户端就同时启用它们。手机只能通过获准设备接口或本人提供的导出读取，不凭这台电脑的结果推断。

依赖：先找到可用 Python（桌面工具3.9+，USB3.11+及OpenSSL）、Node（兼容版本，缺失才装官方支持版本）、curl；YAML 可用独立环境 `requirements.txt`。USB需要时才安装 `requirements-mobile.txt`。Mac 已有兼容Ruby YAML路径保留。安装不重装正常驱动/内核、不停现网，不擅自用专线流量下载大文件。Windows具体检查见 [准备清单](WINDOWS-IPHONE-PREPARATION.md)。不能自动完成系统信任、付费或受管理政策批准。

## 2. 输入数量和套餐用途分开

从已有本地 profile、原生导出或获准 provider 缓存读取节点。不抓取未经许可的订阅，不使用在线转换器。只有 provider URL/加密导出没有实际节点时，先用原 App 正常导出，不猜协议。

```sh
# 已确认本机是Verge，自动列入本地可解析profile；不用切订阅卡。
python scripts/universal.py draft --adapter clash-verge --manifest .private/universal.json
# 其他真实Mihomo客户端，来源可重复任意次数；目标平台明确指定。
python scripts/universal.py draft --adapter mihomo --target android \
  --source .private/source-a.yaml --source .private/source-b.yaml \
  --baseline .private/current.yaml --manifest .private/phone.json
# iPhone原生配置：把adapter改为shadowrocket或surge，source/baseline均为对应App原生文件。
```

`.conf` 扩展名不说明语法；Shadowrocket 与 Surge 要明确区分，不能互相套用。通用生成器不转换协议。`inspect --source ... --format mihomo|shadowrocket|surge --output .private/inventory-2` 把节点名/类型清单保存本地，终端只打印数量。

清单关键字段（完整空模板见 [示例](../examples/universal.example.json)）：

| 字段 | 用途 |
|---|---|
| `target` | 实际平台、适配器、客户端/OS版本、`clients`或`domains-only`范围 |
| `sources[]` | 任意数量本地来源；稳定ID、原生格式、实际路径及内容哈希 |
| `sources[].usage` | `claude-only`专用来源、`ordinary`普通来源、`mixed`同套餐分节点、`unused`不选用；初始`unassigned`不能生成 |
| `roles.claude` | 唯一`source`+`node`，已批准的公网`expectedIp`、`country`；不是服务器入口IP |
| `roles.ordinary[]` | 明确获准的`source`+`node`列表，可以跨多个来源；不从名字或所有来源自动全选 |
| `baseline` | 当前原生配置或已审阅规则基线及哈希；不凭作者规则猜企业内网 |
| `policy` | 普通优先标签正则、直连国家/域名、适用引擎的geosite、经连接证据确认的Claude附加域名 |
| `privacy` | WebRTC方法、浏览器及DNS；需要影响UDP时显式记录选择 |
| `reviewedPolicyReplacement` | 审阅了规则/组/DNS/原生General替换范围后才设true；不是“全部验收完成” |

不能可靠推断用途时集中确认：固定哪个节点、普通池可用哪些来源、地区直连范围、真实出口。用户已有同范围明确授权不重复问。`mixed`只是用途选择，不证明不同节点计费独立。主机名不同可能仍是同一服务商出口，生成器不能证明物理隔离；测试及服务商条款要分别核对。

同名节点用`来源ID+节点名`区分。普通池禁止固定节点的同入口别名，也禁止专用来源内任何入口；重复普通入口会报错。不去重后悄悄挑凭据。仅有一个节点且无普通池时，默认停止；`ordinaryUnavailableAccepted=true`仅生成普通流量REJECT候选，**不能应用到依赖它联网的Codex主机**，需先提供可行普通路径。绝不自动添加DIRECT备用。

## 3. 隐私方案须匹配平台

Mihomo：`directResolvers`、`proxiedResolvers`、`bootstrapResolvers`是经过实际可达性核验的IP字面量HTTPS DoH列表。生成器给Claude DNS绑定固定组，普通DNS绑定普通组，引导DNS独立。不预填作者DNS；内网专用解析需求要单独适配，不能为了通过校验硬替换。

Shadowrocket/Surge：填写原生 `directResolvers`。目前采用独立加密解析与远端代理域名解析边界，**不是Mihomo逐域名DNS路由的同等级实现**。Surge保留明确的解析器IP作为连通性测试DNS；普通域名用加密DNS，其网络侧仍可看见解析器连接。不要承诺DNS服务器与网页出口同IP。未知原生参数、模块、规则组或Host覆写停止生成，保留原文件供审阅。

WebRTC选项：

- `browser-policy`：仅受支持的桌面Chrome/Edge，显式`browser`；生成规则后继续调用浏览器工具并验证有效政策/STUN。不是“已经写过”即成功。
- `client-stun`：Shadowrocket导入后启用原生Disable STUN并实测；Surge候选写入`PROTOCOL,STUN,REJECT`。STUN阻断可能影响P2P语音，先说明。
- `reject-udp`：在进入所选代理/VPN的流量上拒绝UDP，需要`udpImpactAccepted=true`；可能影响所有相关音视频/游戏，而非只影响Claude。不控制VPN外的流量，也不是完整禁用WebRTC。Mihomo手机暂用此可审阅方案，用户不接受时不能宣称已完成同等WebRTC防护，应继续适配原App能力。

手机不得用电脑Chrome政策冒充保护。仅禁止3478/19302端口不能覆盖任意STUN端口，不能当通用防护。浏览器/原生App内DoH、IPv6、VPN绕过需分层核验；系统代理阶段未捕获的DNS明确待验，不能为了补齐先开TUN。

## 4. 生成、核验、接原生部署

```sh
python scripts/universal.py prepare --manifest .private/universal.json --output .private/candidate-1
python scripts/universal.py check --manifest .private/universal.json --output .private/candidate-1
```

候选只写新的 `.private` 目录，包含原生配置、适用时的部署 `settings.json`、哈希与待验收回执。来源/基线/清单/候选变化会使完整性检查失败；准备不下载订阅、不改变现网。`check`不重新分配端口，也不把设备验收设为成功。

**Verge/Mihomo桌面**：通用生成器的快照可与任意当前活动profile组合，`baseUid`绑定的是当前profile，不必切到固定节点所在订阅。`settings.json`内旧`residential`字段仅为兼容。专用端口在目标主机自动选/复用；为手机或另一台主机离线生成时须提供该目标已核实的空闲端口，不能拿主机空闲端口当手机事实。

在目标机检查候选、真实节点的小流量出口和正常网络基线。重新运行通用`check`后，使用**另一个**实际安装计划目录：

```sh
# Mac，仅prepare；Mihomo路径和Verge目录用本机实际值，需要时通过参数传入。
python scripts/manage.py prepare --settings .private/candidate-1/settings.json --plan .private/install-1
# Windows同类准备（Desktop/Code/浏览器范围按本机实际选择，不盲目复制）：
python scripts/windows_setup.py prepare --settings .private/candidate-1/settings.json --plan .private/install-1 --clients code --browsers chrome
```

完成原生编译、隔离测试及变更审阅后，Mac用`manage.py apply --plan .private/install-1`、客户端工具；Windows用`windows_setup.py apply --plan .private/install-1`。不要停在生成候选，已授权且通过门槛就继续。回退对应`manage.py rollback`或`windows_setup.py rollback`，同一个安装计划；客户端/浏览器回退用各自真实备份。后续编辑冲突时不能覆盖。实际客户端、浏览器与DNS验收见对应说明。

**其他Mihomo客户端**：对`mihomo.json`使用目标实际内核的语法检查；JSON是YAML兼容格式，但仍需App确实支持原生Mihomo配置及所用功能。用新配置正式导入，保留旧配置。不要把它写成FlClash、Android等App内部数据库；不因“名字包含Clash”就认定兼容。原生编译/导入不能自动完成时，明确唯一待本人动作后继续核验。

**Shadowrocket**：`shadowrocket.conf`可供正式导入，新的schema2清单也可传给 `mobile_usb.py stage --settings <manifest> --output <candidate>`。USB传输前仍重建候选校验、核对真实iOS/Shadowrocket版本。已有Windows Verge顺序流程继续使用`windows_phone.py`复查主机。若主机不是Verge，不运行这个Verge专用协调器：先保存该主机原生网络验证，再用USB只读doctor及后续手机步骤。USB没有自动激活VPN功能。

**Surge**：`surge.conf`通过Surge正式文件导入，先编译后选择规则模式，再启用/验证。当前USB写入器绑定Shadowrocket，不能拿它给Surge写文件；使用该App实际开放的正式文件共享或用户导入。新适配器仅接受已支持原生协议/参数，不转换VLESS等未知格式。保留旧profile，恢复时重新选择旧profile；不删除用户旧文件。

**未知引擎**：保存本地环境与能力缺口，查官方原生规则、导出/导入、代理失败/UDP/DNS行为，在明确客户端及版本后新增适配器和测试。当前没有实现时明确告知，继续不依赖该适配的准备。不能把通用提示词当任意引擎写入能力，更不能自作主张换App。

## 5. 各设备独立验收

按回执逐项保存时间、实际版本及脱敏观测：固定出口/普通/国内连接链、请求计费路线、浏览器有效政策、国内与海外STUN、系统UDP/TCP DNS、应用DoH、IPv4/IPv6、手机Wi-Fi/蜂窝、固定节点失效、普通池切换、代理退出、回退。每一项区分离线静态、隔离内核、真实设备。

节点失效和代理监听器消失可在本机假上游隔离内核测，不关闭生产代理。不能从这些测试推导“任何手机App或任意子进程在VPN退出时都不会直连”；那是独立隔离需求，本仓库未实现。

新多来源模式使用已选择节点快照，供应商更新后重新检查/生成，不自动更换固定出口或扩大普通池。原HTTP/file provider兼容模式仍在，但不把其自动更新机制说成新快照模式也具备。保留所有旧备份与验收记录，不重复安装或重跑已完成设备。

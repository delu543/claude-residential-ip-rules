# 通用规则与个人配置的边界

> New installations: start with [Universal setup](UNIVERSAL.md) and the [single maintained prompt](UNIVERSAL-PROMPT.md). Detect the actual device/client and any number of sources first. This page documents a specific adapter or the legacy two-source workflow; it is not a universal client/subscription requirement.


本仓库发布的是策略和配置工具，不是某人的整份代理配置。模板中的个人字段为空，不能直接应用。运行 `manage.py init` 后才在目标机生成 `.private/settings.json`，所有客户端和预检都从该文件读取同一套参数。

## 本机入口不是住宅节点

`127.0.0.1`是“当前这台电脑”，不属于作者、运营商或住宅出口。专用HTTP入口的端口现在自动选择：优先复用已识别的本工具监听器，否则向系统申请空闲端口；初始化、准备和应用前检查冲突。也可`--port`指定。端口选定后写入私有设置并保持稳定，不会每次启动随机变化；桌面、Code和测试从同一参数引用。

旧版文档中的17897只是早期默认值，已不作为新安装要求。旧电脑继续使用自己的既有端口；仅更新仓库代码不会迁移运行中的网络。改端口必须同步客户端设置，不能在开发期间静默换端口。

## 哪些自动读，哪些需要明确选择

| 项目 | 来源/行为 |
|---|---|
| 操作系统、配置目录 | 按OS默认目录发现；便携/自定义目录通过Verge“打开配置目录”确认后传`--verge-dir` |
| 订阅UID、节点名、协议、入口、端口及凭据 | 读取目标机profiles；支持实际节点协议，不固定VLESS/某供应商地址 |
| 任意数量来源及用途 | schema2用来源ID+节点选择角色；用户或目标Codex根据授权信息确认，不从名字猜计费身份 |
| 普通订阅 | 远程URL用HTTP provider；本地含节点文件用file provider，不要求URL |
| 固定住宅节点 | 显式选中后从本地读取四元组；失效/变化拒绝，不自动选择其他节点 |
| 预期住宅公网IP/国家 | 用隔离代理测量并确认；不是入口server，也不从“美国”等名字推断 |
| 专用本机端口 | 自动选择/复用并检查冲突，不固定一个数字 |
| 控制接口 | 读取实际运行配置的Unix socket或本机Windows named pipe |
| Claude/Codex路径 | 已安装/运行进程发现；可用`--claude-path`/`--codex-path`补充真实路径，不复制作者用户名 |
| 没安装Codex | 允许空列表，普通OpenAI规则仍有效，不生成空进程正则 |
| 只用网页 | `--scope domains-only`允许空Claude路径，明确只覆盖域名，不冒充客户端隔离 |
| 客户端配置范围 | Windows `--clients desktop code`或`--clients code`；空`--clients`仅路由与浏览器 |
| 国内直连范围 | 默认CN；`--direct-country`可重复指定；`NONE`取消国家直连；地理规则不是全部内网需求 |
| 普通优先地区 | 默认美国，可用`--preferred-pattern`设置节点标签正则；不是出口位置证明 |
| DNS | 从当前配置保留节点引导/基础/直连解析器；私有参数可修改，不绑作者DNS或供应商 |
| 浏览器 | 默认Chrome，Edge仅明确选择；其他浏览器需要其正式配置方式和实测 |
| TUN | 不作为安装前提、不由规则脚本强制打开；先验证可用系统代理 |

`--country`设置批准的固定出口国家，未指定时以US作为本项目默认策略，**不能据此声称已测到美国**。住宅出口预检会比对IP与国家，不符就拒绝。CN直连/US优先是公开策略默认值，不是作者个人凭据；不适合目标用户时应在初始化阶段更改。

私有DNS参数：`defaultNameservers`用于引导，`proxyServerNameservers`保持独立，`directResolvers`仅直连，`proxiedResolvers`由生成器分别绑定住宅/普通策略。不得预先夹带另一个策略组形成循环。`directGeosites`须是目标规则库实际存在的标签，`directDomains`用于已审阅的直连域名；不要把Claude域名改直连。

## 输入边界与未知格式

通用入口支持任意数量原生节点快照；固定节点与普通池分别指定，不依赖当前GUI选中哪份订阅。旧manage.py init保留两份不同profile的动态HTTP/file provider兼容模式。只有proxy-providers而没有节点时，先取获准的原生缓存或正式导出；加密格式、链式中转和未知协议需独立适配，不换供应商、复制作者节点或把固定专线作通用备用。新快照不会自动更新；旧file provider需重新加载/验收，HTTP provider按自身周期刷新。

已有自定义企业规则、GeoSite库、客户端格式可能不同。工具不是“任意环境一键兼容”的承诺；自动读取可靠信息，把无法推断的选择清楚列出，并保留本地备份、语法及实际连接验收。

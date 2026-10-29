# 客户端设置与保障范围

## Claude Desktop

本例源机器使用 `Claude-3p/configLibrary/_meta.json` 的 appliedId 指向本地配置，支持 `egressProxyUrl` 与 `egressProxyPacUrl`。`clients.py` 仅对**已存在且可解析**的这一结构进行适配：固定 `egressProxyUrl` 到本机17897，移除覆盖它的PAC，保留其余键。需用户正常退出，写入后正常打开并看实际代理日志/连接；不复制作者的配置、会话或凭据。

不是所有官方 Claude Desktop 构建都使用这套结构。找不到时工具停止而非创建猜测文件。让 Codex 根据已安装客户端的官方说明查找支持的企业代理设置；仅 Electron `--proxy-server` 不能保证主进程/更新器也受控。未知构建在完成验证前不得标为兼容。本仓库的主配置能通过已知进程规则兜住 Clash 运行时捕获到的连接，但不等于退出 Clash 后的独立防火墙。

## Claude Code

`clients.py apply` 合并 `.claude/settings.json` 的 HTTP_PROXY/HTTPS_PROXY（大小写）和空 NO_PROXY，保留其他 env、permissions 等。`clients.py code -- ...` 先检查固定组和公网出口，再带固定代理环境启动本地 CLI。新的 shell 环境不会改变已经运行的任务；不要强制退出正在开发的会话。

共享 Node/Python、MCP、自定义下载器可能不遵从代理环境。启动工具继承 env 不等于这些工具使用代理。请用真实连接元数据、socket归属和受控请求核验；不要将全部 Node/Python 进程归住宅，避免 Codex、其他项目消耗住宅流量。

## 下载和远程服务

只要请求由专用17897发出，就不受目标域名分类影响，下载也走住宅。已知Claude进程路径的公网请求同样走住宅。外部浏览器接管的链接、子进程自行直连、容器/SSH远端运行的任务需要分别配置；Claude服务端抓取网页不从你的Mac出站。

## “失败不直连”究竟覆盖什么

1. **固定节点失败而 Clash 在运行**：固定selector和专用listener没有备用，访问失败；不借普通节点或DIRECT。
2. **Clash退出**：遵从显式本机代理的客户端无法连接本机端口。此工具不控制绕过代理的进程。
3. **供应商同一入口背后更换公网出口**：启动检查会在下一次运行时拒绝不匹配IP；现有会话没有持续IP拦截保证。
4. **系统休眠/客户端更新/新增进程**：需要重新验收，不能因为曾经通过就永久视为安全。

若需求包括任意子进程、更新器、UDP以及Clash退出的所有情况，需另行设计独立系统防火墙、隔离虚拟机或受控网关。这不在本仓库已完成范围。

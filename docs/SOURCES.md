# 来源、兼容性与许可

核对日期：2026-10-29。

- [Clash Verge Rev 扩展脚本](https://www.clashverge.dev/guide/script.html)：复用现有 `main(config, profileName)` 接口，配置在订阅更新后重新生成，不只修改临时 runtime。此仓库没有复制该文档或应用源码。
- [Mihomo fallback](https://wiki.metacubex.one/en/config/proxy-groups/fallback/) 与 [v1.19.15 fallback源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.15/adapter/outboundgroup/fallback.go)：核对按顺序找健康节点及全故障处理。采用内核现有功能，不自研网络过滤扩展。内核版本变化需复验。
- [Mihomo监听器](https://wiki.metacubex.one/en/config/inbound/listeners/)：使用专用listener直接绑定固定代理。使用接口，不捆绑或派生内核源代码。
- [Claude Code网络配置](https://code.claude.com/docs/en/network-config)：使用正式支持的代理环境变量。环境变量不是强制隔离。
- [Johnshall/Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever)：仅参考分流思路，没有复制其规则文件、订阅、广告列表或代码。Shadowrocket语法不直接等于Mihomo配置，此仓库不实现广告过滤。因此没有将其代码按本仓库许可重新发布。

本仓库原创代码与文档以MIT许可公开。Clash Verge Rev与Mihomo分别适用其上游许可；仓库不重新分发这两个二进制、GeoSite/GeoIP数据、订阅内容。用户自行安装的依赖仍受各自许可与供应商条款约束。

已在源环境读取Mihomo v1.19.15。仅对通过测试的接口作兼容声明；不宣称所有操作系统、Claude构建或未来版本可无人值守安装。Node用于本地渲染测试，Python标准库+Ruby/Psych用于本地配置，不额外上传订阅给第三方转换服务。

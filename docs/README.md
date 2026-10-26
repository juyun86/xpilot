# xpilot 文档

本目录保留上游资料和 xpilot 扩展说明。先读 [Xpilot 最高开发规范](../DEVELOPMENT_RULES.md)，再按 [XPILOT.md](../XPILOT.md) 查阅相关接口；设计稿不自动等于已实现 API，验证记录不自动等于发布或设备验收通过。

## 插件 API 与设计

- [宿主 IPv4 VPN API](design/xpilot-network-api.md)：固定网络能力、归属、停车复查、生命周期和时效消息。
- [UI 语言包插件 API](design/xpilot-ui-language-api.md)：语言角色、返回格式、字体和词条校验、启停与错误回退。
- [可替换核心接口](design/xpilot-replaceable-core.md)：核心角色和宿主边界。
- [运行时 Panda 规则](design/xpilot-panda-rules.md)：规则表、ABI 与加载流程。
- [协作转向插件](design/xpilot-mixed-control-plugin.md)：协作转向的接口和验证范围。

## 验证记录

[validation](validation/) 中的记录只适用于各自注明的设备、提交和输入。静态检查、界面渲染、设备启动和驾驶验证分别记录。

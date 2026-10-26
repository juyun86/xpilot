# xpilot 文档

本目录保留上游资料和 xpilot 扩展说明。当前插件接口、仓库分工及开发规则以 [XPILOT.md](../XPILOT.md) 为入口。

## 插件 API 与设计

- [UI 语言包插件 API](design/xpilot-ui-language-api.md)：语言角色、返回格式、字体和词条校验、启停与错误回退。
- [可替换核心接口](design/xpilot-replaceable-core.md)：核心角色和宿主边界。
- [运行时 Panda 规则](design/xpilot-panda-rules.md)：规则表、ABI 与加载流程。
- [协作转向插件](design/xpilot-mixed-control-plugin.md)：协作转向的接口和验证范围。

## 验证记录

[validation](validation/) 中的记录只适用于各自注明的设备、提交和输入。静态检查、界面渲染、设备启动和驾驶验证分别记录。

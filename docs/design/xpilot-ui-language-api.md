# UI 语言包插件 API

本页描述当前实现的接口。插件 API 版本仍为 1；新增能力通过
requires.hooks 中的 ui_language 探测，不通过分支名或版本字符串猜测。

实现入口：

- [Plugin.ui_language](../../openpilot/tesla/plugin.py)：插件扩展方法。
- [语言包宿主](../../openpilot/tesla/ui/localization.py)：选择、校验与应用。
- [清单及能力检查](../../openpilot/tesla/manifest.py)：资源冲突及 requires。
- [界面与字体加载](../../openpilot/system/ui/lib/application.py)：启动顺序。
- [翻译函数](../../openpilot/system/ui/lib/multilang.py)：原文查找与回退。

## 1. 声明和文件

语言插件声明独占资源 role:ui.language，并声明 requires.hooks。
只做语言替换时不需要 CAN、进程、模型或原生平台声明；建议归入 tools 类别。

~~~json
{
  "id": "sample_locale",
  "name": "Example Language Pack",
  "version": "1.0.0",
  "api": 1,
  "use": "both",
  "category": "tools",
  "entry": "plugin:ExampleLocale",
  "author": "example",
  "priority": 100,
  "enable_param": "ExtExampleLocale",
  "claims": ["role:ui.language"],
  "requires": {"hooks": ["ui_language"]},
  "params": {"ExtExampleLocale": {"type": "BOOL", "default": "0"}}
}
~~~

最小目录：

~~~text
plugins/sample_locale/
  __init__.py
  plugin.json
  plugin.py
  translations.json
  font.otf
  OFL.txt
~~~

下载插件使用 ParamsView 保存自有参数，不需要将这些键编进系统 Params。
开关默认关闭。实际中文插件使用 XpilotChineseUI，保留其已有键名。

## 2. 方法及返回格式

~~~python
import json
from pathlib import Path
from openpilot.tesla.plugin import Plugin

class ExampleLocale(Plugin):
  @classmethod
  def ui_language(cls) -> dict:
    root = Path(__file__).resolve().parent
    return {
      "code": "zh-CHS",
      "font": str(root / "font.otf"),
      "translations": json.loads(
        (root / "translations.json").read_text(encoding="utf-8")
      ),
    }
~~~

| 返回字段 | 类型 | 当前约束 |
| --- | --- | --- |
| code | str | 仅支持 zh-CHS、zh-CHT、ja、ko、th |
| font | str / Path | 应返回绝对路径；解析后必须位于插件类源码文件所在目录或其子目录 |
| translations | dict[str, str] | 不超过 10,000 项，译文必须为非空字符串 |

三项均必需；额外字段目前不会被使用。基类方法默认返回 None，
但声明并获得该角色的插件必须返回有效字典，None 会作为无效语言包处理。
本接口没有提供英语覆盖包；恢复基础语言应关闭插件并重启软件。

### 字体

路径会 resolve 后再检查，因此不能利用父目录或符号链接引用插件外的字体。
只接受小写后缀 .otf、.ttf，文件头须为 OTTO 或 00 01 00 00。
字体及许可证应随包提供，界面启动时不下载字体。

当前宿主只检查路径、存在性、后缀和文件头，不验证完整字体结构或字形覆盖。
发布前必须另查所有译文字形及实际渲染。商店另有限制：压缩包最大 20 MiB；
这不等于解压后总大小限制，也不等于语言接口单独限制了字体字节数。

### 词条

键为界面英文原文，查找区分大小写且完全匹配；宿主不自动生成大小写变体。
字典只扩展普通 tr 查找，不提供复数规则或新的 trn 翻译结构。
缺少词条时沿用基础译文；基础语言也没有对应翻译时显示原文。

~~~json
{
  "Following distance": "跟车距离",
  "Update: {status}": "更新：{status}",
  "Install {version}": "安装 {version}"
}
~~~

宿主使用 string.Formatter 比较原文、译文的字段名、重复次数、格式和转换标记。
允许调整字段出现的顺序，但不能把 {name} 改成 {NAME}，
也不能丢失 :d、:.1f 或 !r 等标记。字面花括号使用双花括号。
百分号格式符不在这项检查范围内；新词条优先使用花括号格式。

## 3. 生效时机和角色裁决

正式 UI 调用 GuiApplication.init_window("UI") 时，在字体和页面构造前读取一次语言包。
其他标题的 setup/updater 窗口没有此接入点。运行期间不轮询词典文件，
开关和文件更新也不会让已有页面、字体或缓存自动重建。

只有当前启用、经过资源裁决并拥有 role:ui.language 的插件会被调用。
同一角色按宿主通用规则裁决：priority 较小者优先，相同则按插件 ID。
不会依次叠加多个语言包。

首次安装、新插件发现、升级和卸载后应完整重启软件或设备，让 manager 重新发现插件。
已发现的语言插件改变开关后也建议完整重启软件；仅设置参数并不能立即刷新界面。
configure 是启动入口，不是热切换 API；不要在同一 UI 实例上反复调用它模拟切换。

应用语言包仅修改当前 UI 进程的语言、译文字典及字体路径；
不会写入 LanguageSetting，不改动其他进程的控制逻辑。
关闭后，新 UI 从原 LanguageSetting 及已支持的基础语言重新初始化。
当前系统基础语言列表只有英语，因此关闭中文插件后实际恢复英语。

旧宿主若未公布 ui_language 能力，会在包清单兼容性检查中拒绝该插件。
索引条目不一定携带 requires；不能仅凭商店列表的初始安装按钮判定能力兼容。

## 4. 在界面中使用

仅加入词典不会自动翻译界面。宿主需对显示文字调用 tr，并在布局、测量和截断前翻译。

~~~python
from openpilot.system.ui.lib.multilang import tr

title = tr("Update: {status}").format(status=tr(raw_state))
button = tr("DOWNLOAD") if raw_state == "download update" else tr("CHECK")
~~~

不要翻译后再比较机器状态；回调仍应接收 raw_state。
避免先构造动态英文再调用 tr，例如 tr(f"Install {version}") 无法匹配固定模板。
选项应分开保存值与显示名称：颜色键 Cobalt、跟车模式索引、分支名、模型 ID 等保持原值。
路名、网络名、用户输入和原始标识不要经过无差别的底层绘图翻译。

文字测量应使用 measure_text_cached 或 font_fallback 后的字体，
不能用 Inter 测量中文、再用另一字体绘制。
生成翻译标记时保留模块文档字符串和 __future__ 导入顺序。

## 5. 错误处理与边界

资源、方法调用、字体和词条校验发生异常时：

1. 宿主尝试以 ui_language 标记记录 XpilotPluginFaults 并输出日志。
2. 该次启动不应用该语言包，保留基础语言和界面启动。
3. 不自动修改插件开关，也不尝试改用输掉独占裁决的另一插件。

以上保护只覆盖语言包加载过程。界面模块自身的语法或导入错误、
字体底层渲染错误和页面布局缺陷仍须单独验证。
曾出现的 __future__ 导入顺序错误属于界面导入失败，不能称为语言包的自动回退。

## 6. 验证及发布

在匹配的 xpilot 环境运行：

~~~bash
python3 tools/sp_tesla_e2e/localization_check.py
python3 tools/sp_tesla_e2e/tile_layout_check.py
python3 tools/sp_tesla_e2e/offroad_pages_check.py
python3 -c "import openpilot.selfdrive.ui.ui"
~~~

语言接口检查会编译 UI 页面，实际 import 检查导入依赖；两者都不等于界面渲染通过。
发布前还需验证：关闭/启用/再关闭、原 LanguageSetting 不变、
无缺字、长标题与选项布局、更新状态与按钮动作保持原语义。
静态资源、原生构建、实际渲染和驾驶验证应分别报告。

宿主接口及通用 UI 标记提交 xpilot；词条、字体、插件源码、dist 和 index 提交 xpilot-plugins。
插件源文件中包括 README 时，修改 README 也需要重建对应归档和索引。
先发布宿主能力，再发布需要它的语言插件；没有用户授权时不自动推送仓库。

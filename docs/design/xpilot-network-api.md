# 宿主 IPv4 VPN 接口 v1

这是受审核网络插件的固定能力合同，不是任意系统命令接口。最高开发规范优先。
Plugin.network_vpn() 返回 NetworkVPN，要求 role:network.vpn；requires.hooks 包含 network_vpn。
只支持现有 mihomo IPv4 配置档，不替换驾驶角色、CAN 或 Panda；后续配置档需独立审查。

## 调用与权限

宿主 API 为 NetworkVPN(provider_id).request(action)，worker 可直接导入该宿主客户端。
只接受 prepare/startcore/stopcore/enable/disable，不接受命令文本、可执行路径或路由参数。
提权入口固定为宿主 network_gateway.py，绝不导入下载插件的 Python 代码。
prepare/startcore/enable 在调用前及取得宿主操作锁后复查停车和未接管，核对安装清单、总开关、角色优胜者及运行服务 lease。
stopcore/disable 允许故障或卸载后清理，但只处理 root 所存 owner 的资源；没有 owner 不删除任何同名资源，其他 provider 无权清理。
claims 不是防恶意代码的 OS 沙箱；AGNOS 已有 sudo 权限不由此 API 扩大。

## 固定资源及归属

- 私有数据与历史迁移目录 /data/mihomo；可执行核心固定为该目录 mihomo，配置为 config.yaml。
- root 归属记录 /data/xpilot_network/vpn-owner.json，目录 0700、记录 0600。记录 provider、daemon PID/启动时间及原 ip_forward。
- 独立 UID/GID 61400，接口 c3mh0 / 198.18.0.1/30，表和 mark 17890，规则优先级 17880/17890。
- 回环控制/代理端口 17891/17890，DNS 17893；17894 是插件自有的临时私有 Wi-Fi 配对 HTTP 端口，令牌不写日志。
- C3MH_MARK、C3MH_OUTDNS、C3MH_INPUT、C3MH_DNS 链。预留前检查接口、表、规则、链、UID 和端口，存在其他占用即拒绝，不接管或清空已有资源。
- 公共 IPv4 经 TUN，回环、RFC1918、链路本地和组播直连；不全局接管 IPv6，不改默认主路由和 DNS 配置文件。热点规则仅在 192.168.43.1 存在时添加。

## 生命周期与失败

后台进程启动前写 network-lease.json（自身 PID、proc 启动 ticks）。root 独立看守核对该代服务与核心；退出后清理该代 owner，恢复普通网络及原转发状态，不误清理下一代。
故障时先停止核心再删除 TUN。停用/卸载仍可调用宿主清理，不依赖被移走的插件提权脚本。
从旧 Starlink 升级前，必须先停止旧进程并由旧版本清理旧资源；新宿主不会把无 owner 的历史资源当作自己所有。
宿主命令超时、冲突及错误只返回短错误，不回显配置、订阅、节点凭据、内核 stderr 或令牌。

## 状态消息

Starlink 声明 msg:network.vpn 和 source:plugin_msg。当前传输仅支持单发布者，独占 source 声明避免与其他声明该 source 的插件同时启用；不宣称提供多发布者 broker。
每 3 秒用 plugins.send_msg 发布 running/gateway/configured/nodes/message，有效期 6000 ms，不含凭据或节点身份。
磁贴用 PluginMsgs.fresh('network.vpn') 读取；无新鲜消息显示停止。长操作或退避期间过期也显示停止，不保留过期的“已连接”。

## 验证

先运行 network_contract_check 与 Starlink tests/contract_e2e.py，覆盖无 API、任意动作、外部资源清理、排队后停车结束和状态过期。
再在停车设备验证实际 TUN、故障恢复、停用/卸载/升级清理、配对成功导入与回滚。检查不代表道路驾驶或全协议流量验证。

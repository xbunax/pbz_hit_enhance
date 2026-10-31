# 架构说明

## 自动加载

`dwmapi.dll` 为 x64 系统代理。导出表来自已检查的 dwmapi 导出清单，MASM 桩直接跳转到系统 DLL 的真实地址。转发在 DllMain 中准备；版本校验、加载 UE4SS 和启动面板由后台线程执行。

后台只处理文件名为 PBZ.exe 且 SHA256 匹配的进程。默认从 DLL 旁的 PBZHitEnhance 查找数据；可由 PBZHitEnhance.ini 的 Paths/DataDirectory 覆盖。运行库校验通过后加载 ue4ss/UE4SS.dll，再启动独立面板程序并传入 --mod-dir。不会注册服务或系统开机启动项。

`PBZHitEnhanceStatus` 为测试导出：2 表示非游戏进程被跳过；发布检查在 Python 测试宿主中验证不会加载 UE4SS。

## 统一反馈入口

`/PBZCombatAsset/Prototypes/Hitreact/BP_HitEffectPlayer_Chooser.BP_HitEffectPlayer_Chooser_C:GetEffectData`

使用蓝图函数后置回调，游戏选择完反馈数据后，仅修改当次输出 SlomoData.Frames。不改武器表，不用“上次攻击者”推断归属。StartSlomoData Hook 只记录下游消费，避免给双方重复加帧。

policy.lua 负责配置解析、作用范围与帧数计算。仅处理 Hitreact.Strength.Income.Normal.*、原值 >0 且 UseSlomoDuration=false 的反馈。写后读回校验失败时尝试恢复原值，随后停止修改直到配置内容变化。

## 面板

Python/Tk 源码由 PyInstaller 生成包含解释器和 Tk 的独立目录包；用户不需要安装 Python。全局快捷键由 RegisterHotKey 工作线程处理，Tk 主线程负责显示和原子保存配置。已设置快捷键时，自动启动模式默认隐藏。

配置不作为 Lua 执行，只接受白名单键与合法数值。后台按约一秒周期在游戏线程应用新配置。UI 与脚本通过配置和状态文件通信，不进行外部进程内存写入。

## 构建与验证

CMake 构建代理 DLL，Python 工具生成完整发行包。依赖归档与 UE4SS DLL 均锁定 SHA256。发行包还包含每个文件的校验清单及压缩包 SHA256。

测试覆盖原始 Lua 回调执行、配置热更新、无效配置停用、写入失败回滚；Windows 检查验证所有导出可解析、两个真实系统调用、非游戏宿主保护及冻结后的面板自检。构建不包含游戏文件、存档、用户快捷键或实战日志。

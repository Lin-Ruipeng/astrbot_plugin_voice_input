# astrbot_plugin_voice_input

一个 AstrBot 插件，把"这条用户消息是语音还是打字发来的"这件事从管线里捞出来，交给别人用。
它的存在价值是**提供一个稳定的判断**，而不是替使用者决定回复长什么样。

## Language

**输入模态（Input modality）**：
用户这条消息到达时是 `voice` 还是 `text`。
_Avoid_: 消息类型, 语音类型, 消息来源

**语音输入判定（Voice input detection）**：
把输入模态判成 `voice` 这件事本身，以及它依赖的三条信号。
_Avoid_: 语音识别（那是 STT，指把音频转成文字）

**`voice_input`**：
本插件写在事件上的布尔标志，每次事件都会被写入（`True` / `False`），是唯一对外的产物。
_Avoid_: `is_voice_input`（旧名字，已废弃，只读兼容）

**检测信号（Detection signal）**：
支持判定的一条证据：残留 `Record` 组件、平台原始消息段里的 `record`、事件登记的临时音频文件。
_Avoid_: 判定条件, 特征

**回复策略（Reply modality policy）**：
"要不要用语音回、用哪个 TTS、用什么音色"这类决定，属于使用者，不属于本插件。
_Avoid_: 语音回复（那只是策略的一个结果）

**示例（Example）**：
仓库 `examples/` 下可直接运行的小插件，用来演示某种回复策略，不发布到插件市场。
_Avoid_: 内置功能, 子插件

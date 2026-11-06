# astrbot_plugin_voice_input

一个 AstrBot 插件，把"这条用户消息是语音还是打字发来的"这件事从管线里捞出来，交给别人用。
默认它只提供判断；打开 `voice_reply_probability` 后，它会把语音消息的文字回复换成语音。

## Language

**输入模态（Input modality）**：
用户这条消息到达时是 `voice` 还是 `text`。
_Avoid_: 消息类型, 语音类型, 消息来源

**语音输入判定（Voice input detection）**：
把输入模态判成 `voice` 这件事本身，以及它依赖的三条信号。
_Avoid_: 语音识别（那是 STT，指把音频转成文字）

**`voice_input`**：
本插件写在事件上的布尔标志，每次事件都会被写入（`True` / `False`），是唯一对外暴露的判断结果。
_Avoid_: `is_voice_input`（旧名字，已废弃，只读兼容）

**检测信号（Detection signal）**：
支持判定的一条证据：残留 `Record` 组件、平台原始消息段里的 `record`、事件登记的临时音频文件。
_Avoid_: 判定条件, 特征

**强制语音回复（Forced voice reply）**：
在回复投递前，把纯文本回复整体换成一条 `Record` 的确定性转换；是否发生由 `voice_reply_probability` 抽签决定。
_Avoid_: 语音回复（太泛，可能指模型的回复策略，也可能指合成动作）

**抽签（Roll）**：
每个事件只做一次的 `voice_reply_probability` 判定，结果缓存在事件上，事件内多次钩子不会重抽。
_Avoid_: 随机数（那是实现细节）

**独占（Exclusive claim）**：
检测到带概率的 TTS 插件时，语音消息的回复模态只由本插件决定，其它插件不得再把这轮回复转成语音。
_Avoid_: 抢占（那是实现手段，不是概念）

**TTS 回退（TTS fallback）**：
框架没有配置 TTS 提供商时，复用 `astrbot_plugin_clonetts` 的凭据直连火山引擎合成语音。
_Avoid_: 内置 TTS（那个指 AstrBot 自己的 TTS 提供商）

**回复策略（Reply modality policy）**：
"要不要用语音回、用哪个 TTS、用什么音色"这类决定。本插件现在提供一个可选策略（强制语音回复），
音色与合成实现仍属于使用者的 TTS 配置。
_Avoid_: 语音回复（那只是策略的一个结果）

**示例（Example）**：
仓库 `examples/` 下可直接运行的小插件，用来演示某种回复策略，不发布到插件市场。
_Avoid_: 内置功能, 子插件

**`inject_prompt` / 语音回复指令**：
已移除（1.0.x 及更早）。当时靠往系统提示词里追加"请用语音回复"，由模型自己调用 TTS 工具，遵循率不稳定。
现在改用强制语音回复。
_Avoid_: 提示词注入（容易和别的内容注入混）

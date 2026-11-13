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

**STT（语音识别）**：
把用户语音转成文字，让模型读懂内容；与「语音输入判定」是两件事，后者不依赖它。
_Avoid_: 语音输入（那是输入模态，不是识别）

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

**框架 TTS（Framework TTS）**：
AstrBot 自带、在「模型提供商 → 文字转语音」配置的 TTS 提供商；需要在「配置文件 → AI → 语音回复」里开启并选中默认模型才能被解析。
_Avoid_: 内置 TTS（容易和 TTS 回退混）

**TTS 回退（TTS fallback）**：
框架 TTS 不可用时，复用 `astrbot_plugin_clonetts` 的凭据直连火山引擎合成语音。
_Avoid_: 内置 TTS（那是框架 TTS，不是回退）

**回复策略（Reply modality policy）**：
"要不要用语音回、用哪个 TTS、用什么音色"这类决定。本插件现在提供一个可选策略（强制语音回复），
音色与合成实现仍属于使用者的 TTS 配置。
_Avoid_: 语音回复（那只是策略的一个结果）

**示例（Example）**：
仓库 `examples/` 下的教学文档与可运行示例，用来演示某种回复策略或配置方式，不发布到插件市场。
_Avoid_: 内置功能, 子插件

**版本号（Version number）**：
本插件同时有两份元数据，`version` 必须字面相等；哪一处漏改，`tests/test_metadata.py` 会让 CI 红。
_Avoid_: 版本号（不指明是哪一份）

**项目元数据（Project metadata）**：
`pyproject.toml` 的 `[project]` 段，描述“这个 Python 包是什么”：包名、版本、依赖、pytest / ruff 配置。
面向 pip 与构建工具，与 AstrBot 无关。
_Avoid_: 发布元数据（那是 metadata.yaml）

**发布元数据（Publishing metadata）**：
`metadata.yaml`：插件市场展示与自动更新读的那份，包含插件名、显示名、版本、作者、`repo`、`astrbot_version` 范围。
_Avoid_: 插件配置（那是 `_conf_schema.json`）

**`inject_prompt` / 语音回复指令**：
已移除（1.0.x 及更早）。当时靠往系统提示词里追加"请用语音回复"，由模型自己调用 TTS 工具，遵循率不稳定。
现在改用强制语音回复。
_Avoid_: 提示词注入（容易和别的内容注入混）

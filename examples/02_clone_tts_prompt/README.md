# 示例 2：发语音，就用克隆音色回语音

> 这是 [`astrbot_plugin_voice_input`](../../) 的示例，**不发布到插件市场**。
> 用法：把本目录拷到 `data/plugins/` 下，并把目录名改成 `astrbot_plugin_voice_input_demo_clone_tts`（与 `metadata.yaml` 的 `name` 一致），然后在 WebUI 启用。

> **2.0.0 起建议直接用主插件的 `voice_reply_probability`**：本示例靠提示词让模型自己调
> `clone_tts`，实测遵循率不稳定（模型可能不调、调了失败、长上下文下照做率下降）。
> 主插件是确定性转换：回复已生成、尚未投递时直接换成语音，见
> [`reply_policy.py`](../../reply_policy.py) 与 [ADR 0002](../../docs/adr/0002-forced-voice-reply-hook.md)。
> 本示例保留下来作为对照，也方便你想继续走"模型自己决定"路线时参考。

## 效果

| 你发的内容 | 机器人回的内容 |
| --- | --- |
| 一条语音 | 用**克隆音色**生成的语音（模型自己调 `clone_tts` 工具） |
| 一条文字 | 普通文字回复，不调 TTS |

这就是"发语音就回语音"最常见的做法：**检测交给主插件，回复交给提示词 + TTS 工具。**

## 前置 1：装音色克隆插件

`clone_tts` 工具来自第三方插件 **CloneTTS（音色克隆）**：

- 仓库：<https://github.com/Radiant303/astrbot_plugin_clonetts>
- 插件市场里搜「克隆语音」也能找到

### 路线 A：自己手动装（5 分钟）

1. 装好插件并在 WebUI 启用；
2. 按它 README 的"凭证获取教程"去火山引擎开通 **语音合成** + **声音复刻**，
   拿到 `api_key`（API Key 管理页）与 `voice_type`（音色库里的克隆音色 ID，通常 `S_` 开头）；
3. 在「插件配置 → 克隆语音」里填这两个值；
4. 确认 `enable_llm_tool` 是开着的（默认开）——它才提供 `clone_tts` 工具。

> 这个插件**不依赖** AstrBot 自带 TTS，所以不需要配 `provider_tts_settings`。

### 路线 B：让机器人自己装

WebUI 首页把 Agent / 沙箱权限打开后，直接把这段发给机器人：

> 帮我安装 AstrBot 插件「克隆语音」（astrbot_plugin_clonetts），装好后把配置项
> api_key 设为 xxx、voice_type 设为 xxx，然后确认 enable_llm_tool 已开启。

它自己会去市场拉插件、改配置、重载。装完你在插件页复查一眼即可。

## 前置 2：启用本示例

把本目录拷过去、改名、启用。默认文案已经是：

> 用户这条消息是语音发来的，请必须调用 clone_tts 工具用语音回复，不要只发文字。语气按人格设定来。

想换语气、换工具名，在插件配置的 `prompt_text` 里改。

## 为什么用提示词而不是写死代码

- 模型自己判断"这轮是不是语音"，比你写死逻辑更灵活（比如群里刷屏时它可以不吭声）；
- 换 TTS 插件时只改一行文案，不用改代码；
- 代价是模型可能不听话 —— 真遇到就换示例 1 的做法：直接用代码把回复换成语音，绕过模型的决定。

## 注意

- **不要同时开主插件的 `voice_reply_probability` 和本示例**：本示例会让模型调 `clone_tts` 工具，
  工具自己就发了一条语音；主插件随后又会把文字回复转成语音，可能收到两条。
- 克隆插件自己也有 `tts_probability`（默认 80），它会在 `on_decorating_result` 里把回复再转一次。
  只开主插件的 `voice_reply_probability` 时，主插件会独占语音消息、而且主插件的
  `Record.text` 是空串，克隆插件会自己跳过，所以一句话只合成一次（实测于 v3.0.4）。
- 文案里写死了 `clone_tts` 这个工具名。换用别的 TTS 插件（Minimax、IndexTTS、voice_hub……）时，
  把工具名改成它提供的那一个，否则模型会一直调用一个不存在的工具。
- 检测本身由主插件负责；本示例不发音频、不拦截消息，只改系统提示词。

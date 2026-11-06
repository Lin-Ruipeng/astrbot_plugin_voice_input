# 示例 1：发语音，就用 AstrBot 自带 TTS 回语音

> 这是 [`astrbot_plugin_voice_input`](../../) 的示例，**不发布到插件市场**。
> 用法：把本目录拷到 `data/plugins/` 下，并把目录名改成 `astrbot_plugin_voice_input_demo_tts`（与 `metadata.yaml` 的 `name` 一致），然后在 WebUI 启用。

## 效果

| 你发的内容 | 机器人回的内容 |
| --- | --- |
| 一条语音 | 一条**语音**：「我看得出你这条是语音发的。」+ 它原本想说的话 |
| 一条文字 | **文字**：「我看得出你这条是文字发的。」+ 它原本想说的话 |

发不出来语音时（没配 TTS / 合成失败），会自动退回文字，不会卡死。

## 它怎么做到的

1. 主插件在 `on_llm_request` / `on_decorating_result` 里写 `event.set_extra("voice_input", bool)`；
2. 本示例在 `on_decorating_result`（priority=90，晚于主插件）里读这个标志；
3. 是语音 → `context.get_using_tts_provider_async()` 拿到 TTS provider，
   `provider.get_audio(text)` 合成出一个本地音频文件，把消息链换成一个 `Record`。

```python
provider = await self.context.get_using_tts_provider_async(event.unified_msg_origin)
audio_path = await provider.get_audio(text)
event.track_temporary_local_file(audio_path)  # 交给 AstrBot 事后清理
event.get_result().chain = [Record.fromFileSystem(audio_path)]
```

> 官方文档里 `on_decorating_result` 就是拿来做"转语音 / 转图片 / 加前缀"的钩子。

## 前置：配一个 TTS 提供商

本示例**自己调用** TTS provider，所以不需要打开全局的
`provider_tts_settings.enable`（那是"所有回复都转语音"，和示例想要的效果不一样）。

### 推荐：小米 MiMo TTS（便宜，够用）

1. 打开 <https://platform.xiaomimimo.com> 注册并完成实名认证；
2. 在控制台创建 **API Key** 并复制：
   - `sk-` 开头 = 按量计费（有限时免费额度）
   - `tp-` 开头 = Token Plan 套餐
3. AstrBot 管理面板 →「模型提供商」→「文字转语音」→「新增」→ 选 **MiMo TTS API**，填：

   | 字段 | 值 |
   | --- | --- |
   | API Key | 上一步复制的 Key |
   | API Base | `https://api.xiaomimimo.com/v1`（用 `tp-` Key 时填 `https://token-plan-cn.xiaomimimo.com/v1`） |
   | 模型 | `mimo-v2.5-tts` |
   | 音色 | `mimo_default`（想换风格可改 `mimo-tts-voice` / `mimo-tts-style-prompt`） |

4. 「保存并获取模型」→ 点模型右侧测试一下。

其它可选：OpenAI TTS、Fish Audio、MiniMax、火山引擎等，AstrBot 内置适配器都可以用，
本示例不关心具体是哪家。

### 顺便把 STT 开起来（可选但强烈建议）

检测本身**不依赖** STT，但不开 STT 的话 AI 读不懂你说了什么。
「模型提供商」→「语音转文字」→ 新增一个（MiMo 的 `mimo-v2.5-asr` 也可以），然后在
「配置文件 → AI → 语音转文字」里启用。

### 官方文档

- 配置文件里的 TTS 相关字段（`provider_tts_settings`）：<https://docs.astrbot.app/dev/astrbot-config.html>
- 会话级 TTS 开关（自定义规则）：<https://docs.astrbot.app/use/custom-rules.html>
- 成篇的 TTS 使用说明目前只有 v3 文档（概念仍适用）：<https://docs-v3.astrbot.app/use/tts.html>
- 小米 MiMo 控制台 / 文档：<https://platform.xiaomimimo.com> 、<https://mimo.mi.com/docs>

## 注意

- **不要同时打开全局 TTS**（`provider_tts_settings.enable`）：全局转换会把所有回复都变语音，
  再叠加本示例会发两遍。示例代码里已经检测"链里是否已有 `Record`"并跳过，但两个都开属于重复配置。
- 本示例会把回复链缩成一条语音，链里的图片 / @ 之类会被丢掉 —— 示例图省事，正式插件请自己取舍。
- 会话级关掉了 TTS（自定义规则里的「启用 TTS」）不影响本示例，因为本示例直接调 provider。

## 关掉"我看得出…"那句话

插件配置里的 `verdict_prefix` 设为 `false`，就只做"语音进 → 语音出"，不再加提示语。

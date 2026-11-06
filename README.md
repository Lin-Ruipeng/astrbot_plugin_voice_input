# 语音输入门控（astrbot_plugin_voice_gate）

判断用户这条消息是不是语音发来的。如果是，就往系统提示词里追加一条指令，
让 AI 用语音回复。

## 为什么需要它

AstrBot 的预处理阶段会先做语音转文字（STT），然后把消息链里的 `Record`
组件**原地替换**成 `Plain`。

等插件拿到消息时，语音痕迹已经没了，`isinstance(comp, Record)` 永远是
`False`。所以 AI 无法判断"用户刚才是发语音还是打字"。

结果就是：你发语音，它可能只回文字。

## 原理

预处理阶段在转文字之前，会先把语音转成 wav，并把文件登记到事件对象的
临时媒体列表上，用于事后清理。

本插件在 `on_llm_request` 钩子里检查这个列表：

- 列表里出现 `.wav` / `.mp3` / `.amr` 等音频后缀 → 判定为语音输入
- 命中后，把一条指令追加到 `req.system_prompt`
- AI 看到指令后，按人格设定用语音回复

同时兼容两种兜底：

- 消息链里若仍存在 `Record` 组件（某些时序下）
- 其他插件写入的 `is_voice_input` 标记

## 安装

把本目录放到 AstrBot 的插件目录：

```
/AstrBot/data/plugins/astrbot_plugin_voice_gate/
```

重启 AstrBot，或在 WebUI 插件页重载。

## 配置

| 项 | 说明 |
| --- | --- |
| `enable` | 总开关 |
| `prompt_text` | 命中语音时追加到系统提示词的内容，可自定义 |
| `debug_log` | 把命中记录写到 `/tmp/voice_gate.log` |

## 已知限制

1. 依赖 `on_llm_request` 钩子，只能影响走 LLM 的回复，插件指令类回复管不到。
2. 判定依据是临时媒体文件后缀。如果上游改了预处理行为，这个依据可能失效。
3. 只能告诉 AI "用语音回"，真正能不能发出语音，还得看 TTS 插件是否正常。
4. 图片消息同样会被登记为临时媒体，所以这里只认音频后缀。

## 排查

```bash
tail -f /tmp/voice_gate.log
```

有 `detected voice input` 说明判定成功。

## 许可

MIT

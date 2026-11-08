<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# Voice Input Detection (astrbot_plugin_voice_input)

**Detects whether a user message arrived as voice. If it did, your bot can reply with voice too.**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-2.0.1-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[简体中文](README.md) ｜ **English** ｜ [Changelog](CHANGELOG.md)

</div>

---

## What it does

After installing, you usually only change one value: `voice_reply_probability` from `0.0` to `1.0`.
There are two features.

### Feature 1: detect whether the user's message is voice

It works out of the box, no configuration needed. AstrBot's preprocessing turns voice into text and
replaces the `Record` component in place; this plugin recovers that information and exposes it:

```python
event.get_extra("voice_input")  # True = voice, False = text
```

| Related setting | Description |
| --- | --- |
| `verbose_log` | Log the detection signals and roll result at debug level; default `false` |

> Detection does not need STT. But the model still needs STT to **understand** what you said (see step 2 below).

### Feature 2: when the message is voice, control the probability of a voice reply

| Setting | Default | Effect |
| --- | --- | --- |
| `voice_reply_probability` | `0.0` | `0.0` = off; `1.0` = every voice message gets a voice reply; `0.5` = half. **Voice messages only** — text messages are never converted |
| `voice_reply_max_chars` | `300` | Skip conversion when the reply is longer than this; `0` = unlimited. Long replies are slow and expensive to synthesize |

**Three global switches gate this feature** (they are not in this plugin's config page):

| Global switch | Where | Required value |
| --- | --- | --- |
| **Voice Replies** + **Default Text-to-Speech Model** | Config → AI → Voice Replies | **On**, with a TTS model selected. Without it the plugin cannot get a framework TTS provider (with clonetts installed it falls back to Volcano) |
| **TTS Trigger Probability** | Config → AI → TTS Trigger Probability | **`0`**. Otherwise AstrBot's built-in TTS converts **text** messages too |
| **Streaming Output** | Config → AI → Streaming Output (under "Others") | **Off**. Both the built-in TTS and this plugin skip streaming results |

### Why it's designed this way

When it is convenient to send voice, it is usually convenient to listen to voice too — people who send
voice messages are likely happy to receive voice replies. So the plugin makes that call: if the input was
voice, convert the reply with a probability, instead of hoping the model remembers to call a TTS tool.

---

## Quick start

About 10 minutes. Pick one route: **Route A, send a prompt to your bot**, or **Route B, click it yourself**.

### Route A (lazy): send this to your bot

Prerequisite: the Agent sandbox / plugin-install permission is enabled in the WebUI.

```text
帮我安装并配置 AstrBot 插件「语音输入识别」（astrbot_plugin_voice_input），
目标是：我发语音时你用语音回复，我发文字时你用文字回复。

1. 安装并启用插件，然后读一下插件目录里的 AGENTS.md。
2. 检查 STT（语音识别）能不能用：不能用就告诉我怎么配（推荐 MiMo ASR）。
3. 检查 TTS 能不能用：没有就先用免费的 Edge TTS（缺 edge-tts 库要先装）。
4. 确认这三个全局开关：配置文件 → AI → 语音回复 = 开且选了默认模型；
   TTS 触发概率 = 0；流式输出 = 关。
5. 把插件配置 voice_reply_probability 设为 1.0，voice_reply_max_chars 保持 300。
6. 用一段话告诉我：你改了什么、还有哪一步需要我手动做、我发语音后应该看到什么日志。
```

The prompt is in Chinese because this plugin's docs and most WebUI deployments use Chinese labels;
translate the menu names if your WebUI is in English. The bot reads [`AGENTS.md`](AGENTS.md) and explains
each setting in plain language; if it cannot change something, it will tell you which step is left.

### Route B (manual): a four-step prerequisite chain

> Keep the order: Agent permission → STT → TTS → this plugin. Steps 1–3 have skip conditions.

#### Step 1: give the bot Agent permission

Enable the Agent / sandbox / plugin-install permission in the WebUI.

- Already enabled → **skip**.

#### Step 2: let STT hear voice

1. Providers → **Speech-to-Text** → add **MiMo STT(API)**:

   | Field | Value |
   | --- | --- |
   | API Key | `sk-…` (pay-as-you-go) or `tp-…` (Token Plan) |
   | API Base | `https://api.xiaomimimo.com/v1` (`tp-` keys: `https://token-plan-cn.xiaomimimo.com/v1`) |
   | Model | `mimo-v2.5-asr` |

2. Config → AI → **Speech Recognition**: on → **Default Speech-to-Text Model**: pick it.

- Already configured, or ask the bot "can you understand my voice messages?" and it says yes → **skip**.
- MiMo also offers TTS (`mimo-v2.5-tts`, voice `mimo_default`); this step only uses its ASR.

#### Step 3: let TTS send voice

1. Providers → **Text-to-Speech** → add **Edge TTS**.
   - Free, no API key; default voice `zh-CN-XiaoxiaoNeural`.
   - If the `edge-tts` library is missing: Console (Data & Logs → Logs) → **Install pip Package** → `edge-tts`;
     or `pip install edge-tts` inside the container and restart.
2. Config → AI → **Voice Replies**: on → **Default Text-to-Speech Model**: pick Edge TTS.
3. On the same page: set **TTS Trigger Probability to `0`** and turn **Streaming Output off**.

- Already configured, or ask the bot "can you send voice messages?" and it says yes → **skip**;
  still verify **trigger probability = 0** and **streaming = off**.
- Want a nicer voice: use **Alibaba Cloud Bailian TTS(API)** with a **Cosy-series** model (e.g. `cosyvoice-v1`).
  **Qwen-series TTS does not work on AstrBot at all (no official support)**.

#### Step 4: turn on this plugin

WebUI → Plugins → `Voice Input Detection` → plugin config:

| Setting | Value |
| --- | --- |
| `voice_reply_probability` | `1.0` |
| `voice_reply_max_chars` | `300` (default) |

Save and reload the plugin.

#### Verify

- Send a **voice** message → get a voice reply; send a **text** message → get a text reply.
- The startup log should contain:

  ```
  [voice_reply] 强制语音回复：概率 1.00；文本上限：300 字
  ```

---

## Four typical configurations

| What I want | Voice Replies | TTS Trigger Probability | `voice_reply_probability` |
| --- | --- | --- | --- |
| Detect only, never change replies | Off (or on with trigger `0`) | `0` | `0.0` (default) |
| **Only voice messages get voice replies** (recommended) | on + default model | `0` | `1.0` |
| All replies are voice | on + default model | `1.0` | any |
| Cloned voice | on / off | — | `1.0` + install `astrbot_plugin_clonetts` |

The fourth one reuses the cloning plugin's voice; when both are installed, voice messages are claimed by
this plugin so the same sentence is not synthesized twice. See
[Configuration and coexistence](docs/configuration.md#和-astrbot_plugin_clonetts-一起用) (Chinese).

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No `[voice_input]` log line | AstrBot >= 4.27.3, plugin enabled |
| Always detected as text | Turn on `verbose_log`; if all three signals are empty, the platform likely did not hand voice to AstrBot |
| Voice in, text out, log says `没有可用的 TTS` | Voice Replies is off or no default model is selected; or clonetts is not installed. See step 3 |
| Log says `流式输出下不会转换语音` | Config → AI → Streaming Output: turn it off |
| **Text** messages become voice | TTS Trigger Probability is not `0` |
| Long replies stay text | Over `voice_reply_max_chars` (default 300); raise it or set `0` |
| Two voice messages / synthesized twice | `astrbot_plugin_clonetts` v3.0.4, and this plugin's priority is still 100 |
| Bailian TTS produces nothing | A Qwen-series model was selected (it does not work on AstrBot); use a **Cosy-series** model |
| Want each detection signal | `verbose_log` on, log level DEBUG |

More on configuration: [Configuration and coexistence](docs/configuration.md). Implementation details:
[Internals](docs/internals.md) (both in Chinese).

---

## How it works (short version)

AstrBot's preprocessing transcribes voice and replaces the `Record` component in place, so by the time a
plugin sees the event the voice trace is gone. This plugin recovers it from three signals: a leftover
`Record` component, a voice segment in the platform's raw message, and temporary audio files registered
during preprocessing. When the raw platform message is available it wins — so a text message quoting a
voice message is not misdetected.

With the switch on, the plugin converts a text-only reply into a single voice message in
`on_decorating_result` (reply generated, not yet delivered). One roll per event, so multi-round agent runs
cannot produce "first half voice, second half text". Synthesis prefers your framework TTS provider, falls
back to `astrbot_plugin_clonetts`' Volcano credentials, and keeps text if both fail.

Long version: [Internals](docs/internals.md) (Chinese) · Decision record:
[ADR 0002](docs/adr/0002-forced-voice-reply-hook.md).

---

## Compatibility

| Item | Notes |
| --- | --- |
| AstrBot | **>= 4.27.3** (detection relies on `_temporary_local_files`, introduced there) |
| Platforms | **Only `qq_official` has been verified end to end.** `aiocqhttp` (OneBot v11 / NapCat / LLOneBot) keeps its code path but is **untested**; other platforms fall back to the temp-audio-suffix signal and are untested too |
| STT | **Not required** for detection; still required for the model to understand the voice content |

See [Development](docs/development.md#实测环境复现基线) for the verified environment and real-bot test log.

### Known limitations

1. Streaming output is never converted (AstrBot's built-in TTS skips it too).
2. Command / `yield` results and chains with non-text components (images, etc.) stay text.
3. Replies longer than `voice_reply_max_chars` are not converted.
4. After conversion `Record.text` is an empty string so probabilistic TTS plugins skip cleanly. Some
   platforms use it as a text fallback when voice sending fails; that fallback text is then empty.
5. The Volcano fallback needs `api_key` / `voice_type` in `astrbot_plugin_clonetts`; without them the reply
   stays text.
6. The plugin produces no audio itself. Whether voice can actually be sent depends on the framework TTS
   provider or clonetts' Volcano config.

---

## Upgrading from 1.0.x to 2.0.0

2.0.0 **removes** `inject_prompt` / `prompt_text`: "let the model decide whether to call a TTS tool" did not
survive real-world testing.

| 1.0.x setting | What to do in 2.0.0 |
| --- | --- |
| `inject_prompt: true` | Use `voice_reply_probability: 1.0`; it changes from "hope the model complies" to a deterministic conversion |
| `inject_prompt: false` (default) | Nothing — the default is `0.0` |
| `prompt_text: ...` | Removed. The soft-prompt path is gone |
| Relying on `examples/02_clone_tts_prompt` | Use the built-in switch instead; the example stays as a comparison |

Leftover `inject_prompt` / `prompt_text` keys in an old config file are ignored, not an error.

---

## Full configuration

This plugin has exactly three settings in the WebUI plugin config:

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `voice_reply_probability` | float | `0.0` | Probability that a voice message gets a voice reply. `0.0` off; `1.0` always; intermediate values roll per message. Voice input only |
| `voice_reply_max_chars` | int | `300` | Skip conversion when the reply is longer than this; `0` = unlimited |
| `verbose_log` | bool | `false` | Log detection signals and roll results at debug level |

Values are sanitized: the probability is clamped to `0.0–1.0` (a value like `80` logs a warning and is
treated as `1.0`), and a negative character limit is treated as `0` (unlimited).

AstrBot global settings that affect it (not part of this plugin; see "Feature 2" and "Four typical
configurations" above):

| Where | Setting | Suggested |
| --- | --- | --- |
| Config → AI | `provider_tts_settings.enable` (Voice Replies) | on |
| Config → AI | `provider_tts_settings.provider_id` (Default Text-to-Speech Model) | pick one |
| Config → AI | `provider_tts_settings.trigger_probability` (TTS Trigger Probability) | `0` |
| Config → AI | `provider_settings.streaming_response` (Streaming Output) | off |
| Config → AI | `provider_stt_settings.enable` / `provider_id` (Speech Recognition) | on + pick one (otherwise the model cannot read voice content) |

---

## More docs

- [Docs index](docs/README.md)
- [Configuration and coexistence](docs/configuration.md) — TTS choices, the four combinations, clonetts matrix
- [Internals](docs/internals.md) — three signals, hook order, exclusive claim, Volcano fallback
- [Custom reply policy](docs/custom-policy.md) — when you want to write your own
- [Development](docs/development.md)
- [AGENTS.md](AGENTS.md) — setup notes and a reporting template for AI assistants
- [Glossary](GLOSSARY.md) ｜ [ADR](docs/adr/) ｜ [Changelog](CHANGELOG.md)

Examples: [`examples/01_builtin_tts`](examples/01_builtin_tts/) (setup tutorial),
[`examples/02_clone_tts_prompt`](examples/02_clone_tts_prompt/) (runnable example).

---

## License

[MIT](LICENSE) © 2026 Lin-Ruipeng

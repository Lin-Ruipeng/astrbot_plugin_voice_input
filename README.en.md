<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# Voice Input Detection (astrbot_plugin_voice_input)

**Tells you whether a message arrived as voice. Nothing more.**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-1.0.1-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[简体中文](README.md) ｜ **English**

</div>

---

## What it does

AstrBot's preprocessing stage runs speech-to-text (STT) and **replaces** the `Record` component in the
message chain with a `Plain` component in place. By the time a plugin sees the event, every trace of
"this was a voice message" is gone.

This plugin brings that bit of information back and puts it on the event:

```python
event.get_extra("voice_input")  # True = voice, False = text
```

## What it does not do

| | |
| --- | --- |
| ❌ Does not decide *whether to reply with voice* | That is **your reply policy**. Copy one of the [`examples/`](examples/) if you want it |
| ❌ Does not modify, block, or reroute messages | Read-only detection plus one `extra` key |
| ❌ Does not ship a TTS engine | Use AstrBot's built-in TTS or a third-party plugin |

**Installed with default settings it changes nothing** — until another plugin (or you, via `inject_prompt`)
reads the flag.

## Install

**Plugin market**: AstrBot dashboard → *Plugins* → *Market*, search for `voice input`.

**Manual**: drop this folder into `data/plugins/astrbot_plugin_voice_input/`, then restart or reload.

**Archive**: upload the zip on the *Plugins* page (a single wrapper directory inside the zip is fine).

## Compatibility

| | |
| --- | --- |
| AstrBot | **>= 4.27.3** (detection relies on `_temporary_local_files`, introduced there) |
| Platforms | `aiocqhttp` (OneBot v11: NapCat, LLOneBot, …) and `qq_official` are both tested and accurate; other platforms fall back to the temp-audio-suffix signal and are untested |
| STT | **Not required** for detection. It is still required for the model to understand what was said |

## Quick check

Send one voice message and one text message. The log should contain:

```
[voice_input] 本轮消息判定为语音输入
[voice_input] 本轮消息判定为文字输入
```

Turn on `verbose_log` and set the log level to `DEBUG` to see each signal's value.

## Consuming the flag from another plugin

`voice_input` is a plain `extra`, readable from any event. **Your handler's `priority` must be lower than
100** — higher numbers run first in AstrBot, and this plugin registers at 100.

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star


class MyVoicePolicy(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    @filter.on_llm_request(priority=50)  # < 100: voice_input is already set
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        if not event.get_extra("voice_input"):
            return
        req.system_prompt += "The user sent this message as voice; reply with voice."
```

Command-style plugins (no LLM involved) can read the same flag inside `on_decorating_result` — this plugin
writes it in both hooks.

Two **runnable** examples live in [`examples/`](examples/):

| Example | Effect | Prerequisite |
| --- | --- | --- |
| [`01_builtin_tts`](examples/01_builtin_tts/) | Voice in → voice out via **AstrBot's built-in TTS** ("I can tell you sent voice"); text in → text out | A TTS provider (Xiaomi MiMo recommended, has free quota) |
| [`02_clone_tts_prompt`](examples/02_clone_tts_prompt/) | Voice in → voice out with a **cloned voice** | The `astrbot_plugin_clonetts` plugin |

## Configuration

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `inject_prompt` | bool | `false` | Append `prompt_text` to the system prompt when voice is detected. **An optional policy, not the plugin's job** |
| `prompt_text` | text | see below | Only used when `inject_prompt` is on. The default names no specific TTS plugin |
| `verbose_log` | bool | `false` | Log the three signals (has_record / temp files / raw_signal) at debug level |

Default text:

> 【语音输入】用户这条消息是语音发来的，请用语音回复。如果当前没有可用的语音合成能力，就用文字回复并说明原因。

## How detection works

Three signals; any hit means voice. When the platform's raw message segments are available, they win:

| Signal | Source | Notes |
| --- | --- | --- |
| A leftover `Record` | `event.get_messages()` | Only when STT is off or failed |
| B raw message | OneBot: `raw_message.message` containing `type == "record"`; QQ official: `raw_message.attachments` with a `content_type` starting with `voice` (or an audio filename) | Only the message itself counts; quoted audio does not |
| C temp audio suffix | `event._temporary_local_files` | Fallback populated by preprocessing (images are tracked too, hence the suffix filter) |

The logic lives in [`detection.py`](detection.py) as pure functions with no `astrbot` import.

## Known limitations

1. Depends on `_temporary_local_files` (AstrBot >= 4.27.3). When the attribute is missing the plugin logs a
   single warning instead of failing silently.
2. On platforms whose raw message shape is unknown (**neither** OneBot v11 nor QQ official), with STT enabled, a
   *text* message that quotes a *voice* message is reported as voice — the quoted audio really is in the temp list.
   Add a branch to `raw_voice_signal()` in `detection.py` to make that platform precise.
3. Only affects the LLM request and pre-send hooks; nothing about the message content changes.
4. The plugin produces no audio. Whether a voice reply is actually sent depends on your TTS setup.

## Troubleshooting

- No `[voice_input]` log line at all → check AstrBot version (>= 4.27.3) and that the plugin is enabled.
- Always `False` → enable `verbose_log` and see which signal is empty. If all three are empty, the platform
  never handed the audio to AstrBot.
- Voice in but text out → check `inject_prompt` and your TTS plugin/provider (see the example READMEs).

## Development

```bash
pip install pytest pyyaml packaging ruff
ruff check . && ruff format --check .
pytest
```

Tests cover the pure detection logic plus release-metadata consistency (semver, `repo` field, config/schema
alignment, no deprecated `@register`). **AstrBot is not required.**

## License

[MIT](LICENSE) © 2026 Lin-Ruipeng

<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# Voice Input Detection (astrbot_plugin_voice_input)

**Tells you whether a message arrived as voice. By default it hands that flag over; flip the switch and
voice messages get voice replies.**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-2.0.0-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[简体中文](README.md) ｜ **English**

</div>

---

## What it does

AstrBot's preprocessing stage runs speech-to-text (STT) and **replaces** the `Record` component in the
message chain with a `Plain` component in place. By the time a plugin sees the event, every trace of
"this was a voice message" is gone.

This plugin does two things:

1. **Detection**: brings that bit of information back and puts it on the event:

   ```python
   event.get_extra("voice_input")  # True = voice, False = text
   ```

2. **Optional deterministic conversion**: with `voice_reply_probability` turned on, the reply to a voice
   message is replaced by a voice message before it is sent. `1.0` = every voice message gets a voice reply,
   `0.0` = off (default).

## What it does not do

| | |
| --- | --- |
| ❌ Does not change replies by default | With default settings it behaves exactly like "detection only" |
| ❌ Does not touch text messages | Only `voice_input=True` messages are rolled; typed messages are never converted |
| ❌ Does not ship a TTS vendor | Uses **your framework TTS provider**; if there is none, it reuses `astrbot_plugin_clonetts`' Volcano credentials as a fallback |
| ❌ Does not pick a voice | The voice belongs to your TTS provider / cloning plugin |

## Compatibility

| | |
| --- | --- |
| AstrBot | **>= 4.27.3** (detection relies on `_temporary_local_files`, introduced there) |
| **Platforms** | **Only `qq_official` (QQ official bot) has been verified end to end.** `aiocqhttp` (OneBot v11 / NapCat / LLOneBot) keeps its code path but is **untested**; other platforms fall back to the temp-audio-suffix signal and are untested too |
| STT | **Not required** for detection. It is still required for the model to understand what was said |

### Verified environment (reproduction baseline)

| Item | Value |
| --- | --- |
| Platform | `qq_official` |
| AstrBot | 4.29.4 (repo pyproject; install metadata 4.28.2) |
| Voice cloning | `astrbot_plugin_clonetts` **v3.0.4** |
| STT | `mimo_stt_api` (`mimo-v2.5-asr`) |
| System | Debian 13 / Python 3.12 / Docker container |
| This plugin | 2.0.0 |

## Quick check

Send one voice message and one text message. The log should contain:

```
[voice_input] 本轮消息判定为语音输入
[voice_input] 本轮消息判定为文字输入
```

With `voice_reply_probability` enabled, startup also logs:

```
[voice_reply] 强制语音回复：概率 1.00；文本上限：300 字
```

Turn on `verbose_log` and set the log level to `DEBUG` to see each signal's value and every roll.

## Configuration

Both numeric keys can be edited in the WebUI plugin config; save and reload the plugin.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `voice_reply_probability` | float | `0.0` | `0.0` = off; `1.0` = every voice message gets a voice reply; `0.5` = half. Voice input only |
| `voice_reply_max_chars` | int | `300` | Skip conversion when the reply is longer than this; `0` = unlimited. Long replies are slow and expensive to synthesize, hence the default cap |
| `verbose_log` | bool | `false` | Log the three signals and the roll at debug level |

Both values are sanitized: the probability is clamped to `0.0–1.0` (a value like `80` logs a warning and is
treated as `1.0`), and a negative character limit is treated as `0` (unlimited).

### Upgrading from 1.0.x to 2.0.0

2.0.0 **removes** `inject_prompt` / `prompt_text`: "let the model decide whether to call a TTS tool" did not
survive real-world testing.

| 1.0.x setting | What to do in 2.0.0 |
| --- | --- |
| `inject_prompt: true` | Use `voice_reply_probability: 1.0`. It changes from "hope the model complies" to a deterministic conversion |
| `inject_prompt: false` (default) | Nothing — the default is `0.0` |
| `prompt_text: ...` | Removed. The soft-prompt path is gone; your own plugin can still add a prompt if you want |
| Relying on `examples/02_clone_tts_prompt` | Use the built-in switch instead; the example stays as a comparison |

Leftover `inject_prompt` / `prompt_text` keys in an old config file are ignored, not an error.

## How "voice in → voice out" works

Conversion happens in `on_decorating_result`: the reply exists but has not been sent yet.

1. Only `voice_input=True` messages are rolled. **One roll per event**, cached on the event, so agent
   multi-round runs cannot produce "first half voice, second half text".
2. These are skipped: an existing `Record` (someone already converted), command / `yield` results, streaming
   output, chains containing non-text components, empty text, and replies longer than `voice_reply_max_chars`.
3. Audio is produced by the **session's framework TTS provider**; if there is none (or it fails), the plugin
   falls back to **reusing `astrbot_plugin_clonetts`' `api_key` / `voice_type` against Volcano Engine v3**.
4. The whole chain becomes one `Record`. Any failure keeps the text.

Why not "append 'please reply with voice' to the system prompt": the model is still the executor — it may skip
the tool, call it with bad parameters, or stop following instructions in long contexts. Replacing the reply
after it has been generated is what makes it deterministic.

## Running alongside astrbot_plugin_clonetts

`astrbot_plugin_clonetts` also converts replies in `on_decorating_result`, using its own
`tts_probability` (default 80) — but it **does not look at the input modality**. Without isolation, the same
sentence can be **synthesized twice**: two TTS calls, two bills, one message sent, the first call wasted.

This plugin handles it by **claiming voice messages exclusively when clonetts is detected**, while text
messages still go through clonetts' probability. Three pieces, all required:

| Piece | Effect |
| --- | --- |
| This plugin's `on_decorating_result` has priority 100; clonetts uses the default 0 | This plugin runs first and decides the modality of voice messages |
| `Record.text` is left as an empty string after conversion | clonetts collects text via `hasattr(component, "text")`; an empty string sends it down its "no text, skip" branch |
| When no conversion happened, the result type is downgraded to a general result | Both clonetts' and AstrBot's built-in TTS `is_llm_result()` checks fail, so neither synthesizes again |

Scenario matrix (**voice messages only**):

| `voice_reply_probability` | clonetts installed | Result |
| --- | --- | --- |
| `0.0` (default) | any | This plugin stays out entirely; voice messages follow clonetts' probability |
| `0 < p < 1`, hit | any | This plugin synthesizes; clonetts finds no text and skips |
| `0 < p < 1`, miss | yes | This plugin claims the message; clonetts and built-in TTS both skip; text is kept |
| `0 < p < 1`, miss | no | Text is kept (no downgrade; other plugins are not a concern) |
| `1.0` | any | Every voice message becomes voice here; clonetts' probability only applies to text messages |

**Cost**: the claimed message no longer goes through AstrBot's built-in TTS, nor through "LLM results only"
segmented replies. Content safety already ran before the hook; reply prefix / mentions / quotes / text-to-image
are unaffected.

This relies on clonetts' implementation detail (`hasattr(c, "text")`). The verified version is **v3.0.4**;
re-verify "one sentence is never synthesized twice" after upgrading it.

## Writing your own policy

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
        req.system_prompt += "The user sent this as voice; keep the answer short."
```

Command-style plugins (no LLM involved) can read the same flag inside `on_decorating_result` — this plugin
writes it in both hooks.

Two **runnable** examples live in [`examples/`](examples/):

| Example | Effect | Prerequisite |
| --- | --- | --- |
| [`01_builtin_tts`](examples/01_builtin_tts/) | Voice in → voice out via **AstrBot's built-in TTS**; text in → text out | A TTS provider (Xiaomi MiMo recommended) |
| [`02_clone_tts_prompt`](examples/02_clone_tts_prompt/) | Voice in → voice out with a **cloned voice** (prompt-based, unreliable) | The `astrbot_plugin_clonetts` plugin |

Since 2.0.0 the main plugin ships the same capability; the examples are best read as "how to write your own
policy".

## How detection works

Three signals; any hit means voice. When the platform's raw message segments are available, they win:

| Signal | Source | Notes |
| --- | --- | --- |
| A leftover `Record` | `event.get_messages()` | Only when STT is off or failed |
| B raw message | OneBot: `raw_message.message` containing `type == "record"`; QQ official: top-level `raw_message.attachments` whose `content_type` starts with `voice` (or an audio filename) | Only the message itself counts; quoted audio does not |
| C temp audio suffix | `event._temporary_local_files` | Fallback populated by preprocessing (images are tracked too, hence the suffix filter) |

Detection lives in [`detection.py`](detection.py) as pure functions with no `astrbot` import. The reply policy's
roll and skip rules live in [`reply_policy.py`](reply_policy.py), also testable offline.

## Known issue and limitations

**Known issue (not fixed yet): on `qq_official`, a *text* message that quotes a *voice* message can still be
detected as voice input.**

The message itself is text, but the quoted audio is also transcoded and tracked on the event. 2.0.0 prefers the
QQ official message's **top-level** `attachments` (quoted audio lives in `msg_elements` and is not counted), but
in practice that signal is not always available, so detection falls back to the temp-audio signal. There is no
reliable fix yet (issue #1), so it is documented as a known issue. Consequence: with
`voice_reply_probability` enabled, that text message may get a voice reply.

Other limitations:

1. Depends on `_temporary_local_files` (AstrBot >= 4.27.3). When missing, the plugin logs a single warning
   instead of failing silently.
2. Only `qq_official` is verified; `aiocqhttp` keeps its code path but is untested, and other platforms are
   untested too.
3. **Streaming output is never converted** (AstrBot's built-in TTS skips streaming as well). Disable streaming
   if you need guaranteed voice replies.
4. Command / `yield` results and chains containing images or other non-text components stay text.
5. `Record.text` is deliberately empty so probability-based TTS plugins skip cleanly. On platforms that use it
   as a text fallback when audio delivery fails, that fallback will be empty.
6. The Volcano fallback needs `api_key` / `voice_type` in clonetts' config; otherwise the plugin logs a warning
   and keeps text.
7. The plugin produces no audio itself. Whether voice is actually sent depends on your framework TTS provider
   or clonetts' Volcano config.

## Troubleshooting

- No `[voice_input]` log line at all → check AstrBot version (>= 4.27.3) and that the plugin is enabled.
- Always `False` → enable `verbose_log` and see which signal is empty. If all three are empty, the platform
  never handed the audio to AstrBot.
- Voice in but text out → read the `[voice_reply]` lines: probability `0`? roll missed? text too long? no TTS
  available? streaming enabled?
- Two voice messages / synthesized twice → confirm `astrbot_plugin_clonetts` is v3.0.4 and this plugin still
  runs at priority 100.
- Need exact ratios → with clonetts installed, intermediate probabilities still hold (misses are claimed and
  downgraded), and text messages keep following clonetts' probability.

## Development

```bash
pip install pytest pyyaml packaging ruff
ruff check . && ruff format --check .
pytest
```

Tests cover the pure logic (detection signals, probability clamping, rolls, skip rules, Volcano stream parsing)
plus release-metadata consistency (semver, `repo` field, config/schema alignment, no deprecated `@register`).
**AstrBot is not required.**

## License

[MIT](LICENSE) © 2026 Lin-Ruipeng

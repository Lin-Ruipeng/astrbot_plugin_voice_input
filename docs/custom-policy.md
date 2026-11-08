# 自己写回复策略

主插件已经内置「检测到语音 → 把回复换成语音」的确定性转换，绝大多数人只要把
`voice_reply_probability` 设成 `1.0` 就够了（见 [README](../README.md)）。

这篇文档给需要**自己控制**的人：想加自己的跳过规则、想换判断逻辑、想先做别的装饰再转语音，
或者只是想知道主插件内部是怎么调的。

## 何时值得自己写

| 场景 | 建议 |
| --- | --- |
| 只在特定群 / 特定人格下回语音 | 自己写：读 `voice_input`，再叠加你的条件 |
| 想要"语音进 → 语音出"，但音色和长度规则用主插件的 | 不用写，改配置即可 |
| 想在转语音前加前缀、改写文案、加水印 | 自己写一个 `on_decorating_result`（priority < 100） |
| 想完全替换主插件的转换（比如改用别的 TTS 服务） | 自己写，并把主插件 `voice_reply_probability` 设 `0.0` |

## 前置

主插件会把结论写到事件上（两个钩子都会写）：

```python
event.get_extra("voice_input")  # True = 语音，False = 文字
```

读取方的 `priority` 要 **小于 100**（AstrBot 里数值大的 handler 先执行，主插件是 100）。

## 完整示例（可拷成插件）

下面是一份最小实现：读 `voice_input`，是语音就用框架 TTS provider 合成，
把消息链换成一条 `Record`；失败就保留文字。

> 目录名要符合 `astrbot_plugin_` 前缀，且与 `metadata.yaml` 的 `name` 一致。

```python
"""示例：读 voice_input，发语音就用 AstrBot 自带 TTS 回语音。

依赖 ``astrbot_plugin_voice_input`` 先把 ``voice_input`` 写到事件上。
本示例自己调 TTS provider，但仍需要框架里「语音回复」处于开启状态并选好默认模型，
否则 ``get_using_tts_provider_async()`` 会返回 None。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.star import Context, Star

VERDICT_VOICE = "我看得出你这条是语音发的。"
VERDICT_TEXT = "我看得出你这条是文字发的。"


class VoiceReplyPolicy(Star):
    """把"是语音"变成"回语音"。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    @filter.on_decorating_result(priority=90)
    async def on_decorating_result(self, event: AstrMessageEvent) -> None:
        """发送前装饰：语音进来的消息，把文本回复换成语音。"""
        result = event.get_result()
        if result is None or not result.chain:
            return

        is_voice = bool(event.get_extra("voice_input"))

        if is_voice and self._has_record(result.chain):
            # 已经有别的组件（或主插件 / 全局 TTS）把回复转成语音了，不重复处理
            return

        self._prepend(result.chain, VERDICT_VOICE if is_voice else VERDICT_TEXT)

        if not is_voice:
            return  # 文字消息保持文字回复

        await self._to_voice(event, result.chain)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _has_record(chain: list) -> bool:
        return any(isinstance(component, Record) for component in chain)

    @staticmethod
    def _prepend(chain: list, text: str) -> None:
        """把提示语放在消息链最前面（尽量复用第一个 Plain）。"""
        for index, component in enumerate(chain):
            if isinstance(component, Plain):
                chain[index] = Plain(f"{text}\n{component.text}")
                return
        chain.insert(0, Plain(text))

    async def _to_voice(self, event: AstrMessageEvent, chain: list) -> None:
        text = "".join(
            component.text for component in chain if isinstance(component, Plain)
        ).strip()
        if not text:
            return

        provider = await self.context.get_using_tts_provider_async(
            event.unified_msg_origin
        )
        if provider is None:
            self.logger.warning(
                "[voice_policy] 没有可用的 TTS 提供商，继续发送文字。"
                "请先到「模型提供商 → 文字转语音」新增一个（免费可先用 Edge TTS），"
                "再到「配置文件 → AI → 语音回复」打开并选默认模型。"
            )
            return

        try:
            audio_path = await provider.get_audio(text)
        except Exception:  # noqa: BLE001 - 示例：失败就退回文字
            self.logger.exception("[voice_policy] TTS 合成失败，退回文字回复")
            return

        if not audio_path:
            self.logger.warning("[voice_policy] TTS 没有返回音频文件，退回文字回复")
            return

        event.track_temporary_local_file(audio_path)
        event.get_result().chain = [Record.fromFileSystem(audio_path)]
        self.logger.info("[voice_policy] 已把回复转成语音：%s", audio_path)
```

配套的 `metadata.yaml`：

```yaml
name: astrbot_plugin_my_voice_reply
display_name: 语音输入·自定义回复策略
short_desc: 读 voice_input，用 AstrBot 自带 TTS 回语音（示例）
version: 1.0.0
author: your-name
repo: https://github.com/your-name/your-repo
astrbot_version: ">=4.27.3,<5"
```

## 几个容易踩的点

| 点 | 说明 |
| --- | --- |
| **provider 从哪来** | `context.get_using_tts_provider_async(umo)` 走 `ProviderManager._resolve_using_provider()`；`语音回复` 没开或没选默认模型时返回 `None`。所以"自己调 provider"也躲不开这个前置 |
| **别重复合成** | 先检查链里是否已有 `Record`；主插件（priority 100）先跑，如果它已经转换，这里要直接跳过 |
| **链里有图片 / @** | 上面的示例会把链缩成一条语音，图片会丢。正式插件请自己决定是保留图片还是只转文本部分 |
| **失败回退** | `get_audio` 失败 / 返回空路径时保留原文字，不要抛异常让消息发不出去 |
| **临时文件** | 合成出的音频用 `event.track_temporary_local_file(path)` 登记，交给 AstrBot 事后清理 |
| **流式输出** | `on_decorating_result` 在流式下仍会被调用，但内置 TTS 与本插件都跳过；自己写时也建议跳过 `STREAMING_RESULT` |
| **命令 / `yield` 类结果** | 这些不是 LLM 结果，通常不该转语音 |

## 和主插件同开时的行为

| 主插件 `voice_reply_probability` | 你的 priority | 结果 |
| --- | --- | --- |
| `0.0` | 任意 | 主插件只写 `voice_input`，不碰回复；你的策略生效 |
| `> 0` | `< 100` | 主插件先跑；它转换后链里已有 `Record`，你应当跳过 |
| `> 0` | `> 100` | 你先跑；主插件随后可能再转换一次（它只看纯文本链），**避免这种组合** |

想完全接管，请把主插件的开关设成 `0.0`，只把它当检测器用。

## 相关

- [配置与共存](configuration.md) —— 与 `astrbot_plugin_clonetts` 的场景矩阵、TTS 选型
- [实现细节](internals.md) —— 主插件的三信号、hook 时序、独占机制
- [AGENTS.md](../AGENTS.md) —— 给 AI 的配置说明与回报模板

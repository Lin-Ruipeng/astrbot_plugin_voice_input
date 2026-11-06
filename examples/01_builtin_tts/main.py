"""示例：读 voice_input，发语音就用 AstrBot 自带 TTS 回语音。

依赖 ``astrbot_plugin_voice_input`` 先把 ``voice_input`` 写到事件上。
本示例自己调 TTS provider，因此**不需要**打开全局的 ``provider_tts_settings.enable``。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.star import Context, Star

VERDICT_VOICE = "我看得出你这条是语音发的。"
VERDICT_TEXT = "我看得出你这条是文字发的。"


class VoiceInputDemoTTS(Star):
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
            # 已经有别的组件（或全局 TTS）把回复转成语音了，不重复处理
            return

        if self._verdict_prefix_enabled:
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
                "[demo_tts] 没有可用的 TTS 提供商，继续发送文字。"
                "请先到「模型提供商 → 文字转语音」新增一个（推荐 MiMo TTS API）。"
            )
            return

        try:
            audio_path = await provider.get_audio(text)
        except Exception:  # noqa: BLE001 - 示例：失败就退回文字
            self.logger.exception("[demo_tts] TTS 合成失败，退回文字回复")
            return

        if not audio_path:
            self.logger.warning("[demo_tts] TTS 没有返回音频文件，退回文字回复")
            return

        event.track_temporary_local_file(audio_path)
        event.get_result().chain = [Record.fromFileSystem(audio_path)]
        self.logger.info("[demo_tts] 已把回复转成语音：%s", audio_path)

    @property
    def _verdict_prefix_enabled(self) -> bool:
        return bool(self.config.get("verdict_prefix", True))

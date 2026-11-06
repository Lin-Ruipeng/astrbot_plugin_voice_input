"""语音输入识别插件。

默认只做一件事：判断本轮用户消息是不是**语音发来的**，并把结论写到事件上。

    from astrbot.api.event import AstrMessageEvent

    if event.get_extra("voice_input"):
        ...

打开 ``voice_reply_probability`` 后，再额外做一件事：语音消息的回复在投递前
被换成一条语音。为什么反转了「只检测」的定位、怎么和概率型 TTS 插件共存，
见 ``docs/adr/0002-forced-voice-reply-hook.md``。
"""

from __future__ import annotations

import random

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import ResultContentType
from astrbot.core.utils.astrbot_path import (
    get_astrbot_config_path,
    get_astrbot_temp_path,
)

from .clonetts_tts import config_path, load_config, synthesize
from .detection import detect_voice_input, raw_voice_signal
from .reply_policy import (
    DEFAULT_MAX_CHARS,
    clamp_max_chars,
    clamp_probability,
    should_block_other_tts,
    should_convert,
)

VOICE_INPUT_KEY = "voice_input"
"""对外暴露的键名：``event.get_extra("voice_input")``，恒为 ``bool``。"""

CLONETTS_PLUGIN_NAME = "astrbot_plugin_clonetts"
"""会按自己的概率转语音的插件；检测到它时本插件要独占语音消息。"""

_TEMP_FILES_ATTR = "_temporary_local_files"
"""AstrBot 预处理阶段登记的临时媒体文件列表（>= v4.27.3）。"""

_ANNOUNCED_KEY = "_voice_input_announced"
"""内部标记：保证每个事件只打一条 info 日志。"""

_ROLL_KEY = "_voice_reply_roll"
"""内部标记：本事件的抽签值，事件内多次钩子不重抽。"""

_UNSET = object()
"""区分「还没抽过签」和「抽到 0.0」。"""


class VoiceInputPlugin(Star):
    """识别语音输入，并按配置把语音消息的回复换成语音。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        self._warned_missing_temp_files = False
        self._warned_missing_tts = False
        self._warned_streaming = False
        self._clonetts_announced = False
        self._announce_config()

    # ------------------------------------------------------------------ hooks

    @filter.on_llm_request(priority=100)
    async def on_llm_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """把判定写进事件，供 priority < 100 的其它插件读取。"""
        self._mark(event)

    @filter.on_decorating_result(priority=100)
    async def on_decorating_result(self, event: AstrMessageEvent) -> None:
        """回复已生成、尚未投递：按概率把语音消息的回复换成语音。"""
        if not self._mark(event):
            return
        await self._force_voice_reply(event)

    # -------------------------------------------------------------- detection

    def _mark(self, event: AstrMessageEvent) -> bool:
        """计算并写入 ``voice_input``，返回本轮判定结果。"""
        has_record = self._has_record_component(event)
        local_files = self._temporary_local_files(event)
        raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)

        is_voice = detect_voice_input(
            has_record=has_record,
            local_files=local_files,
            raw_message=raw_message,
        )
        event.set_extra(VOICE_INPUT_KEY, is_voice)

        if self._verbose_log:
            self.logger.debug(
                "[voice_input] has_record=%s temp_files=%s raw_signal=%s "
                "-> voice_input=%s",
                has_record,
                [str(path) for path in local_files],
                raw_voice_signal(raw_message),
                is_voice,
            )

        if not event.get_extra(_ANNOUNCED_KEY):
            event.set_extra(_ANNOUNCED_KEY, True)
            self.logger.info(
                "[voice_input] 本轮消息判定为%s",
                "语音输入" if is_voice else "文字输入",
            )
        return is_voice

    def _has_record_component(self, event: AstrMessageEvent) -> bool:
        """信号 A：消息链里是否还有 ``Record``。"""
        get_messages = getattr(event, "get_messages", None)
        if get_messages is None:
            return False
        try:
            messages = get_messages()
        except Exception:  # noqa: BLE001 - 取不到消息链就当作没有
            self.logger.debug("[voice_input] 读取消息链失败", exc_info=True)
            return False
        return any(isinstance(component, Record) for component in messages or [])

    def _temporary_local_files(self, event: AstrMessageEvent) -> list[str]:
        """信号 C：预处理阶段登记的临时媒体文件。"""
        files = getattr(event, _TEMP_FILES_ATTR, None)
        if files is None:
            if not self._warned_missing_temp_files:
                self._warned_missing_temp_files = True
                self.logger.warning(
                    "[voice_input] 当前 AstrBot 没有 %s，语音判定只能依赖 "
                    "Record 组件与原始消息段（请确认 AstrBot >= 4.27.3）。",
                    _TEMP_FILES_ATTR,
                )
            return []
        try:
            return [str(path) for path in files]
        except TypeError:
            self.logger.debug("[voice_input] %s 不是可迭代对象", _TEMP_FILES_ATTR)
            return []

    # ------------------------------------------------------- voice reply hook

    async def _force_voice_reply(self, event: AstrMessageEvent) -> None:
        """按抽签结果决定：转语音，或者独占语音消息后保持文字。"""
        probability = self._probability
        if probability <= 0:
            return  # 完全不介入：不转换，也不降级

        result = event.get_result()
        if result is None or not result.chain:
            return

        if self._is_streaming(result):
            self._warn_streaming_once()
            return

        chain = result.chain
        already_record = any(isinstance(component, Record) for component in chain)
        text_only = all(isinstance(component, Plain) for component in chain)
        text = "".join(
            component.text for component in chain if isinstance(component, Plain)
        ).strip()
        is_llm_result = bool(result.is_llm_result())
        max_chars = self._max_chars
        roll = 0.0 if probability >= 1.0 else self._roll(event)

        convert = should_convert(
            probability=probability,
            roll=roll,
            voice_input=True,
            already_record=already_record,
            is_llm_result=is_llm_result,
            text_only=text_only,
            text=text,
            max_chars=max_chars,
        )

        clonetts_present = self._clonetts_star() is not None

        if self._verbose_log:
            self.logger.debug(
                "[voice_reply] p=%.2f roll=%.3f clonetts=%s llm=%s text_only=%s "
                "len=%d max_chars=%d -> convert=%s",
                probability,
                roll,
                clonetts_present,
                is_llm_result,
                text_only,
                len(text),
                max_chars,
                convert,
            )

        if not convert:
            self._claim_if_needed(
                result,
                probability=probability,
                clonetts_present=clonetts_present,
                is_llm_result=is_llm_result,
            )
            return

        audio_path = await self._synthesize_voice(event, text)
        if not audio_path:
            return  # 合成失败：保留文字，也不降级（让别的插件还有机会）

        tracker = getattr(event, "track_temporary_local_file", None)
        if tracker is not None:
            tracker(audio_path)

        # text="" 是故意的：概率型 TTS 插件（clonetts v3.0.4）用
        # ``hasattr(component, "text")`` 收集文本，空串会让它干净地跳过，
        # 避免同一句话被合成两次。见 ADR 0002。
        result.chain = [Record.fromFileSystem(audio_path, text="")]
        self.logger.info("[voice_reply] 已把回复转成语音：%s", audio_path)

    def _claim_if_needed(
        self,
        result,
        *,
        probability: float,
        clonetts_present: bool,
        is_llm_result: bool,
    ) -> None:
        """没转成语音时，独占本轮语音消息，避免别的插件再合成一次。"""
        if not should_block_other_tts(
            probability=probability,
            voice_input=True,
            clonetts_present=clonetts_present,
            converted=False,
            is_llm_result=is_llm_result,
        ):
            return
        result.result_content_type = ResultContentType.GENERAL_RESULT
        self.logger.debug(
            "[voice_reply] 本轮未转语音，已降级结果类型以阻止其它 TTS 插件接手",
        )

    @staticmethod
    def _is_streaming(result) -> bool:
        """流式结果不转换（与 AstrBot 内置 TTS 的行为一致）。"""
        content_type = getattr(result, "result_content_type", None)
        return content_type in (
            ResultContentType.STREAMING_RESULT,
            ResultContentType.STREAMING_FINISH,
        )

    def _roll(self, event: AstrMessageEvent) -> float:
        """本事件的抽签值：同一个事件只抽一次，避免多轮之间抖动。"""
        value = event.get_extra(_ROLL_KEY, _UNSET)
        if value is _UNSET:
            value = random.random()
            event.set_extra(_ROLL_KEY, value)
        return float(value)

    # ------------------------------------------------------------------- tts

    async def _synthesize_voice(
        self,
        event: AstrMessageEvent,
        text: str,
    ) -> str | None:
        """优先用框架 TTS 提供商，没有时回退到 clonetts 的火山 v3 配置。"""
        path = await self._provider_audio(event, text)
        if path:
            return path
        return await self._clonetts_audio(text)

    async def _provider_audio(
        self,
        event: AstrMessageEvent,
        text: str,
    ) -> str | None:
        """当前会话的框架 TTS 提供商。"""
        try:
            provider = await self.context.get_using_tts_provider_async(
                event.unified_msg_origin
            )
        except Exception:  # noqa: BLE001 - 取不到就当没有
            self.logger.debug("[voice_reply] 获取 TTS 提供商失败", exc_info=True)
            return None
        if provider is None:
            return None
        try:
            audio_path = await provider.get_audio(text)
        except Exception:  # noqa: BLE001 - 合成失败继续尝试回退
            self.logger.exception("[voice_reply] 框架 TTS 合成失败，尝试火山回退")
            return None
        if not audio_path:
            self.logger.debug("[voice_reply] 框架 TTS 没有返回音频，尝试火山回退")
            return None
        self.logger.debug("[voice_reply] 已用框架 TTS 合成：%s", audio_path)
        return str(audio_path)

    async def _clonetts_audio(self, text: str) -> str | None:
        """复用 clonetts 的 api_key / voice_type 直连火山 v3。"""
        star = self._clonetts_star()
        if star is None:
            self._warn_no_tts()
            return None

        root_dir_name = getattr(star, "root_dir_name", None)
        conf_path = config_path(get_astrbot_config_path(), root_dir_name)
        conf = load_config(conf_path)
        if conf is None:
            self._warn_no_tts(f"读不到 {conf_path}")
            return None

        audio_path, error = await synthesize(
            text,
            conf,
            temp_dir=get_astrbot_temp_path(),
            verbose=self._verbose_log,
        )
        if error or not audio_path:
            self.logger.warning("[voice_reply] 火山回退失败：%s", error or "未知原因")
            return None
        self.logger.debug("[voice_reply] 已用火山回退合成：%s", audio_path)
        return audio_path

    def _clonetts_star(self):
        """检测 clonetts 是否已加载（用于独占与火山回退）。"""
        getter = getattr(self.context, "get_registered_star", None)
        if getter is None:
            return None
        try:
            star = getter(CLONETTS_PLUGIN_NAME)
        except Exception:  # noqa: BLE001 - 注册表读不到就当没装
            self.logger.debug("[voice_reply] 读取插件注册表失败", exc_info=True)
            return None
        if star is None or not getattr(star, "activated", True):
            return None
        if not self._clonetts_announced:
            self._clonetts_announced = True
            self.logger.info(
                "[voice_reply] 检测到 %s %s：语音消息将由本插件独占",
                CLONETTS_PLUGIN_NAME,
                getattr(star, "version", None) or "(未知版本)",
            )
        return star

    def _warn_no_tts(self, detail: str | None = None) -> None:
        """没有任何可用 TTS 时只 warning 一次。"""
        if self._warned_missing_tts:
            return
        self._warned_missing_tts = True
        self.logger.warning(
            "[voice_reply] 没有可用的 TTS：请到「模型提供商 → 文字转语音」新增一个，"
            "或安装 astrbot_plugin_clonetts（本插件会复用它的音色配置）%s",
            f"（{detail}）" if detail else "",
        )

    def _warn_streaming_once(self) -> None:
        if self._warned_streaming:
            return
        self._warned_streaming = True
        self.logger.warning(
            "[voice_reply] 流式输出下不会转换语音；要强制语音回复请先关闭流式输出。",
        )

    # ----------------------------------------------------------------- config

    def _announce_config(self) -> None:
        """把生效配置与钳值结果打进日志，方便复现时确认。"""
        raw_probability = self.config.get("voice_reply_probability", 0.0)
        probability = clamp_probability(raw_probability)
        numeric = self._as_float(raw_probability)
        if numeric is None:
            self.logger.warning(
                "[voice_reply] voice_reply_probability=%r 不是数字，按 0.0 处理",
                raw_probability,
            )
        elif numeric != probability:
            self.logger.warning(
                "[voice_reply] voice_reply_probability=%r 超出 0.0-1.0，按 %.1f 处理",
                raw_probability,
                probability,
            )

        raw_max_chars = self.config.get("voice_reply_max_chars", DEFAULT_MAX_CHARS)
        max_chars = clamp_max_chars(raw_max_chars)
        numeric_max = self._as_int(raw_max_chars)
        if numeric_max is None:
            self.logger.warning(
                "[voice_reply] voice_reply_max_chars=%r 不是整数，按 %d 处理",
                raw_max_chars,
                DEFAULT_MAX_CHARS,
            )
        elif numeric_max < 0:
            self.logger.warning(
                "[voice_reply] voice_reply_max_chars=%r 是负数，按 0（不限制）处理",
                raw_max_chars,
            )

        self.logger.info(
            "[voice_reply] 强制语音回复：%s；文本上限：%s",
            "关闭（voice_reply_probability=0）"
            if probability <= 0
            else f"概率 {probability:.2f}",
            "不限制" if max_chars == 0 else f"{max_chars} 字",
        )

    @staticmethod
    def _as_float(raw: object) -> float | None:
        try:
            return float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(raw: object) -> int | None:
        try:
            return int(raw)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None

    @property
    def _probability(self) -> float:
        return clamp_probability(self.config.get("voice_reply_probability", 0.0))

    @property
    def _max_chars(self) -> int:
        return clamp_max_chars(
            self.config.get("voice_reply_max_chars", DEFAULT_MAX_CHARS)
        )

    @property
    def _verbose_log(self) -> bool:
        return bool(self.config.get("verbose_log", False))

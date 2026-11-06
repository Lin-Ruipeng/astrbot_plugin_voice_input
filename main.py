"""语音输入识别插件。

只做一件事：判断本轮用户消息是不是**语音发来的**，并把结论写到事件上。

    from astrbot.api.event import AstrMessageEvent

    if event.get_extra("voice_input"):
        ...

"要不要用语音回复"、"用哪个 TTS"属于使用者的回复策略，本插件不参与。
需要现成策略时参考仓库里的 ``examples/``。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Record
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star

from .detection import detect_voice_input

VOICE_INPUT_KEY = "voice_input"
"""对外暴露的键名：``event.get_extra("voice_input")``，恒为 ``bool``。"""

DEFAULT_PROMPT = (
    "【语音输入】用户这条消息是语音发来的，请用语音回复。"
    "如果当前没有可用的语音合成能力，就用文字回复并说明原因。"
)

_TEMP_FILES_ATTR = "_temporary_local_files"
"""AstrBot 预处理阶段登记的临时媒体文件列表（>= v4.27.3）。"""

_ANNOUNCED_KEY = "_voice_input_announced"
"""内部标记：保证每个事件只打一条 info 日志。"""


class VoiceInputPlugin(Star):
    """识别语音输入，并把结果写入 ``event.set_extra("voice_input", bool)``。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        self._warned_missing_temp_files = False

    # ------------------------------------------------------------------ hooks

    @filter.on_llm_request(priority=100)
    async def on_llm_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """写标志；可选地把"用语音回复"追加进系统提示词。"""
        is_voice = self._mark(event)
        if is_voice:
            self._inject_prompt(req)

    @filter.on_decorating_result(priority=100)
    async def on_decorating_result(self, event: AstrMessageEvent) -> None:
        """让命令类等非 LLM 回复也能读到标志。"""
        self._mark(event)

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
                "[voice_input] has_record=%s temp_files=%s raw=%s -> voice_input=%s",
                has_record,
                [str(path) for path in local_files],
                raw_message is not None,
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

    # ---------------------------------------------------------------- inject

    def _inject_prompt(self, req: ProviderRequest) -> None:
        """可选策略：把 ``prompt_text`` 追加到系统提示词（默认关闭）。"""
        if not self._inject_prompt_enabled:
            return

        prompt = (self.config.get("prompt_text") or DEFAULT_PROMPT).strip()
        if not prompt:
            return

        base = getattr(req, "system_prompt", "") or ""
        if prompt in base:
            return

        req.system_prompt = f"{base}\n{prompt}" if base else prompt
        self.logger.debug("[voice_input] 已向系统提示词追加语音回复指令")

    # ----------------------------------------------------------------- config

    @property
    def _inject_prompt_enabled(self) -> bool:
        return bool(self.config.get("inject_prompt", False))

    @property
    def _verbose_log(self) -> bool:
        return bool(self.config.get("verbose_log", False))

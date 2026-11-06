"""语音输入门控插件。

作用：在 LLM 请求之前判断这条用户消息是不是语音发来的。
如果是，就往系统提示词里追加一条指令，要求 AI 也用语音回复。

原理：
AstrBot 的预处理阶段会把语音消息转成文字（STT），并把 Record 组件
原地替换成 Plain，插件层面已经看不到语音了。
但预处理同时会把转码后的 wav 临时文件登记到事件对象上，
所以这里通过检查事件挂着的临时媒体文件后缀来判断。
"""

import os

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

AUDIO_EXTS = (
    ".wav",
    ".mp3",
    ".ogg",
    ".amr",
    ".silk",
    ".m4a",
    ".flac",
    ".aac",
    ".opus",
    ".wma",
)

DEFAULT_PROMPT = (
    "【语音输入】用户这条消息是用语音发来的，请必须使用语音（调用 clone_tts 工具）回复，"
    "不要只发文字。语气按人格设定来。"
)

DEBUG_LOG = "/tmp/voice_gate.log"


def _debug(msg: str) -> None:
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            from datetime import datetime

            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


@register(
    "astrbot_plugin_voice_gate",
    "self",
    "语音输入门控",
    "v1.0.0",
    "识别语音输入并要求 AI 用语音回复",
)
class VoiceGatePlugin(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    def _is_voice_input(self, event: AstrMessageEvent) -> bool:
        """判断这条消息是不是语音发来的。"""
        # 1) 消息链里还有 Record（某些时序下预处理尚未替换）
        try:
            for comp in event.get_messages():
                if type(comp).__name__ == "Record":
                    return True
        except Exception:
            pass

        # 2) 事件上登记的临时媒体文件，语音会被转成 wav
        try:
            files = getattr(event, "_temporary_local_files", None) or []
        except Exception:
            files = []
        for f in files:
            if str(f).lower().endswith(AUDIO_EXTS):
                return True

        # 3) 其他插件/流程打的标记
        try:
            if event.get_extra("is_voice_input"):
                return True
        except Exception:
            pass

        return False

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在请求模型前注入语音标记。"""
        if not self._is_voice_input(event):
            return

        try:
            event.set_extra("is_voice_input", True)
        except Exception:
            pass

        prompt = self.config.get("prompt_text") or DEFAULT_PROMPT
        if not prompt.strip():
            return

        base = getattr(req, "system_prompt", "") or ""
        if prompt.strip() in base:
            return

        req.system_prompt = f"{base}\n{prompt}" if base else prompt
        logger.info("[voice_gate] 检测到语音输入，已注入语音回复指令")
        _debug("detected voice input, prompt injected")

"""示例：读 voice_input，让模型用克隆音色回语音。

依赖：
- ``astrbot_plugin_voice_input``（写 ``voice_input`` 标志）
- ``astrbot_plugin_clonetts``（提供 ``clone_tts`` 工具）

策略本身只有一行：是语音输入，就往系统提示词里要求模型调用 ``clone_tts``。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star

DEFAULT_PROMPT = (
    "用户这条消息是语音发来的，请必须调用 clone_tts 工具用语音回复，不要只发文字。"
    "语气按人格设定来。"
)


class VoiceInputDemoCloneTTS(Star):
    """语音进 → 克隆音色出。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    @filter.on_llm_request(priority=90)
    async def on_llm_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """只在语音输入时追加指令，文字消息一律不动。"""
        if not event.get_extra("voice_input"):
            return

        prompt = (self.config.get("prompt_text") or DEFAULT_PROMPT).strip()
        if not prompt:
            return

        base = getattr(req, "system_prompt", "") or ""
        if prompt in base:
            return

        req.system_prompt = f"{base}\n{prompt}" if base else prompt
        self.logger.debug("[demo_clone_tts] 已追加语音回复指令")

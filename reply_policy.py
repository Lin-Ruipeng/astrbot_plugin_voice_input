"""强制语音回复的纯函数判定层。

和 ``detection.py`` 一样，这一层刻意不导入 ``astrbot``：只吃原始类型，
因此能脱离 AstrBot 单测（见 ``tests/test_reply_policy.py``）。

三个概念：

- **概率**：``voice_reply_probability`` 的取值，钳在 ``[0.0, 1.0]``。
- **抽签**：每个事件只做一次的 ``roll``，落在 ``[0.0, 1.0)``。
- **独占**：检测到概率型 TTS 插件时，语音消息的回复模态只由本插件决定。
"""

from __future__ import annotations

DEFAULT_MAX_CHARS = 300
"""``voice_reply_max_chars`` 的默认值：超过这个字数就不转语音。"""


def clamp_probability(raw: object) -> float:
    """把配置值钳成 ``[0.0, 1.0]`` 的概率。

    Args:
        raw: 配置文件里的原始值（可能是字符串、``None`` 或 ``80`` 这种误填的百分数）。

    Returns:
        合法的概率；无法转成数值或为 ``nan`` 时返回 ``0.0``（等同于关闭）。
    """

    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if value != value or value in (float("inf"), float("-inf")):
        return 0.0
    return max(0.0, min(1.0, value))


def clamp_max_chars(raw: object) -> int:
    """把 ``voice_reply_max_chars`` 钳成非负整数。

    Returns:
        合法的字数上限；无法转换时用 :data:`DEFAULT_MAX_CHARS`，
        负数按 ``0``（不限制）处理。
    """

    try:
        value = int(raw)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return DEFAULT_MAX_CHARS
    return 0 if value < 0 else value


def should_convert(
    *,
    probability: float,
    roll: float,
    voice_input: bool,
    already_record: bool,
    is_llm_result: bool,
    text_only: bool,
    text: str,
    max_chars: int,
) -> bool:
    """本轮是否把文字回复换成语音。

    Args:
        probability: 已钳过的 ``voice_reply_probability``。
        roll: 本事件的抽签值，落在 ``[0.0, 1.0)``。
        voice_input: 本轮用户消息是否来自语音（``event.get_extra("voice_input")``）。
        already_record: 回复链里是否已经有 ``Record``（别的插件已经转过了）。
        is_llm_result: 结果是否来自 LLM；命令类与流式输出都是 ``False``。
        text_only: 回复链是否全是 ``Plain``；带图片等组件时不转换，避免丢内容。
        text: 可朗读的纯文本。
        max_chars: 字数上限，``0`` 表示不限制。

    Returns:
        可以转换时为 ``True``。
    """

    if probability <= 0:
        return False
    if not voice_input:
        return False
    if roll > probability:
        return False
    if already_record:
        return False
    if not is_llm_result:
        return False
    if not text_only:
        return False
    if not text:
        return False
    return not (max_chars > 0 and len(text) > max_chars)


def should_claim(
    *, probability: float, voice_input: bool, clonetts_present: bool
) -> bool:
    """本轮语音消息是否已被本插件「认领」，因而不允许别的 TTS 插件接手。

    只关心权限归属，不关心这次抽签有没有命中：只要开了概率、消息是语音、
    且检测到了概率型 TTS 插件，回复模态就归本插件决定。

    Args:
        probability: 已钳过的 ``voice_reply_probability``。
        voice_input: 本轮用户消息是否来自语音。
        clonetts_present: 是否检测到 ``astrbot_plugin_clonetts``。

    Returns:
        需要独占时为 ``True``。``probability <= 0`` 表示完全不介入，返回 ``False``。
    """

    return bool(voice_input and clonetts_present and probability > 0)


def should_block_other_tts(
    *,
    probability: float,
    voice_input: bool,
    clonetts_present: bool,
    converted: bool,
    is_llm_result: bool,
) -> bool:
    """没转成语音时，是否要把结果类型降级以阻止其它插件合成。

    「没转成」既包括抽签没命中，也包括超长、混合链、没有可读文本等跳过情况。
    命令类 / 流式结果本来就不是 LLM 结果，不需要再降级。

    Args:
        probability: 已钳过的 ``voice_reply_probability``。
        voice_input: 本轮用户消息是否来自语音。
        clonetts_present: 是否检测到 ``astrbot_plugin_clonetts``。
        converted: 本轮是否已经把回复换成了语音。
        is_llm_result: 结果是否来自 LLM。

    Returns:
        需要降级时为 ``True``。
    """

    if converted:
        return False
    if not is_llm_result:
        return False
    return should_claim(
        probability=probability,
        voice_input=voice_input,
        clonetts_present=clonetts_present,
    )

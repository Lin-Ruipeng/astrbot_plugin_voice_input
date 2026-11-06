"""语音输入的纯函数判定层。

这一层刻意不导入 ``astrbot``：任何能提供信号的地方都能复用，
也让它能脱离 AstrBot 单测（见 ``tests/test_detection.py``）。

三条检测信号：

A. 消息链里还有 ``Record`` —— 只在 STT 关闭或失败时成立。
B. 平台原始消息里"本条消息自己"含语音 —— 能拿到就最准，不受引用影响。
   支持 OneBot v11（``message`` 段列表）与 QQ 官方机器人（botpy 的 ``attachments``）。
C. 事件登记的临时媒体文件有音频后缀 —— 兜底；会把"引用的语音"也算进来。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

AUDIO_SUFFIXES: frozenset[str] = frozenset(
    {
        ".wav",
        ".mp3",
        ".ogg",
        ".oga",
        ".amr",
        ".silk",
        ".m4a",
        ".flac",
        ".aac",
        ".opus",
        ".wma",
        ".webm",
    }
)

RECORD_SEGMENT_TYPE = "record"
"""OneBot v11 里语音消息段的 type 值。"""

VOICE_CONTENT_TYPE_PREFIXES: tuple[str, ...] = ("voice", "audio", "silk")
"""QQ 官方机器人（botpy）附件里语音的 content_type 前缀。"""

_MESSAGE_POST_TYPE = "message"
"""OneBot 上报里"普通消息"的 post_type；notice / request 事件不会有语音段。"""

_MISSING = object()


def is_audio_path(path: Any) -> bool:
    """判断一个文件路径是否是音频。

    Args:
        path: 文件路径、``file://`` URI 或任何可字符串化的对象。

    Returns:
        后缀命中 :data:`AUDIO_SUFFIXES` 时为 ``True``。
    """

    if path is None:
        return False
    text = str(path).split("?", 1)[0].split("#", 1)[0].strip().lower()
    if not text:
        return False
    return text.endswith(tuple(AUDIO_SUFFIXES))


# ---------------------------------------------------------------- 信号 B：OneBot


def _segment_type(segment: Any) -> str | None:
    """从 OneBot 消息段里取出 type（兼容 dict、对象、枚举）。"""

    raw_type: Any = None
    if isinstance(segment, dict):
        raw_type = segment.get("type")
    else:
        raw_type = getattr(segment, "type", None)
    if raw_type is None:
        return None
    # 某些实现把 type 放进枚举，``str(enum)`` 形如 "SegmentType.record"
    value = getattr(raw_type, "value", raw_type)
    return str(value).strip().lower() or None


def _onebot_segments(raw_message: Any) -> list[Any] | None:
    """取出 OneBot 原始消息段列表；结构不认识时返回 ``None``。"""

    if isinstance(raw_message, list):
        return raw_message

    message = (
        raw_message.get("message")
        if isinstance(raw_message, dict)
        else getattr(raw_message, "message", _MISSING)
    )
    if message is _MISSING or message is None:
        return None
    if isinstance(message, str):
        # CQ 码字符串形式："[CQ:record,file=...]"
        return [{"type": RECORD_SEGMENT_TYPE}] if "[CQ:record" in message else []
    if isinstance(message, Iterable):
        return list(message)
    return None


# ------------------------------------------------------------ 信号 B：QQ 官方


def _attachment_field(attachment: Any, *names: str) -> Any:
    """按若干候选字段名读取附件属性（dict 与对象都支持）。"""

    for name in names:
        if isinstance(attachment, dict):
            if name in attachment:
                return attachment[name]
            continue
        value = getattr(attachment, name, _MISSING)
        if value is not _MISSING:
            return value
    return None


def _attachment_is_voice(attachment: Any) -> bool:
    """QQ 官方附件是否为语音（AstrBot 自己也是这么判断的）。"""

    content_type = str(
        _attachment_field(attachment, "content_type", "contentType") or ""
    )
    content_type = content_type.strip().lower()
    if content_type.startswith(VOICE_CONTENT_TYPE_PREFIXES):
        return True
    filename = _attachment_field(attachment, "filename", "name")
    return is_audio_path(filename)


def _qq_attachments(raw_message: Any) -> list[Any] | None:
    """取出 QQ 官方机器人消息的**顶层** ``attachments``。

    只读顶层：被引用的语音在 ``msg_elements`` 里，不能算成本条消息的语音。
    结构不认识（没有该字段）时返回 ``None``。
    """

    if isinstance(raw_message, dict):
        attachments = raw_message.get("attachments", _MISSING)
    else:
        attachments = getattr(raw_message, "attachments", _MISSING)
    if attachments is _MISSING or attachments is None:
        return None
    try:
        return list(attachments)
    except TypeError:
        return None


# ------------------------------------------------------------------ 对外接口


def _is_message_event(raw_message: Any) -> bool:
    """通知/请求类上报不可能是语音消息。"""

    post_type = raw_message.get("post_type") if isinstance(raw_message, dict) else None
    if post_type is None:
        post_type = getattr(raw_message, "post_type", None)
    return post_type is None or str(post_type) == _MESSAGE_POST_TYPE


def raw_voice_signal(raw_message: Any) -> bool | None:
    """平台原始消息里"本条消息自己"是否含语音。

    Returns:
        ``True`` / ``False`` 表示这个平台的结构可以判断；
        ``None`` 表示拿不到（例如平台未提供原始消息，或结构不认识），
        调用方应退回到其它信号。
    """

    if raw_message is None or not _is_message_event(raw_message):
        return None

    segments = _onebot_segments(raw_message)
    if segments is not None:
        return any(
            _segment_type(segment) == RECORD_SEGMENT_TYPE for segment in segments
        )

    attachments = _qq_attachments(raw_message)
    if attachments is not None:
        return any(_attachment_is_voice(attachment) for attachment in attachments)

    return None


def raw_has_record(raw_message: Any) -> bool:
    """原始消息里是否含语音；无法判断时返回 ``False``。

    需要区分"无法判断"请用 :func:`raw_voice_signal`。
    """

    return raw_voice_signal(raw_message) is True


def detect_voice_input(
    *,
    has_record: bool,
    local_files: Iterable[Any] | None,
    raw_message: Any = None,
) -> bool:
    """唯一对外的判定入口：三条信号合并成一个布尔值。

    Args:
        has_record: 消息链里是否仍有 ``Record`` 组件（信号 A）。
        local_files: 事件登记的临时媒体文件路径（信号 C）。
        raw_message: 平台原始消息（信号 B）。能判断时以它为准：被引用的语音
            在原始消息里不属于"本条消息"，因此不会被误判成语音输入。

    Returns:
        这条消息是否来自语音输入。
    """

    raw_signal = raw_voice_signal(raw_message)
    if raw_signal is not None:
        # 能拿到原始消息时以它为准（信号 A 作为补充，两者不会互相矛盾）
        return raw_signal or bool(has_record)

    if has_record:
        return True
    if not local_files:
        return False
    return any(is_audio_path(path) for path in local_files)

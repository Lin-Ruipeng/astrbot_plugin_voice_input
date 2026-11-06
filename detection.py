"""语音输入的纯函数判定层。

这一层刻意不导入 ``astrbot``：任何能提供信号的地方都能复用，
也让它能脱离 AstrBot 单测（见 ``tests/test_detection.py``）。

三条检测信号：

A. 消息链里还有 ``Record`` —— 只在 STT 关闭或失败时成立。
B. 平台原始消息段里有 ``record`` —— OneBot v11 最准，只反映"用户本条消息"。
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

_MESSAGE_POST_TYPE = "message"
"""OneBot 上报里"普通消息"的 post_type；notice / request 事件不会有语音段。"""


def is_audio_path(path: Any) -> bool:
    """判断一个临时文件路径是否是音频。

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


def _raw_segments(raw_message: Any) -> list[Any] | None:
    """取出原始消息段列表；取不到时返回 ``None``（表示"无法判断"）。"""

    if raw_message is None:
        return None

    # 平台上报的是通知/请求事件，不存在消息段
    if isinstance(raw_message, dict) and raw_message.get("post_type") not in (
        None,
        _MESSAGE_POST_TYPE,
    ):
        return None
    post_type = getattr(raw_message, "post_type", None)
    if post_type is not None and str(post_type) != _MESSAGE_POST_TYPE:
        return None

    if isinstance(raw_message, list):
        return raw_message

    message = (
        raw_message.get("message")
        if isinstance(raw_message, dict)
        else getattr(raw_message, "message", None)
    )
    if message is None:
        return None
    if isinstance(message, str):
        # CQ 码字符串形式："[CQ:record,file=...]"
        return [{"type": RECORD_SEGMENT_TYPE}] if "[CQ:record" in message else []
    if isinstance(message, Iterable):
        return list(message)
    return None


def raw_has_record(raw_message: Any) -> bool:
    """原始消息段里是否有语音段。

    Args:
        raw_message: 平台原始消息对象（aiocqhttp 的 OneBot 事件对象、
            ``{"message": [...]}`` 字典、或消息段列表均可）。

    Returns:
        命中 ``record`` 段时为 ``True``；无法判断时返回 ``False``
        （需要区分"无法判断"请用 :func:`_raw_record_signal`）。
    """

    return _raw_record_signal(raw_message) is True


def _raw_record_signal(raw_message: Any) -> bool | None:
    """原始消息段的语音信号；``None`` 表示这个平台拿不到原始消息。"""

    segments = _raw_segments(raw_message)
    if segments is None:
        return None
    return any(_segment_type(segment) == RECORD_SEGMENT_TYPE for segment in segments)


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
        raw_message: 平台原始消息（信号 B）。能拿到时以它为准，
            这样"文字消息引用了一条语音"不会被误判成语音输入。

    Returns:
        这条消息是否来自语音输入。
    """

    raw_signal = _raw_record_signal(raw_message)
    if raw_signal is not None:
        # 能拿到原始消息段时以它为准（信号 A 作为补充，两者不会互相矛盾）
        return raw_signal or bool(has_record)

    if has_record:
        return True
    if not local_files:
        return False
    return any(is_audio_path(path) for path in local_files)

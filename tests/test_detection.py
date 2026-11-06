"""detection.py 的纯函数测试（不需要安装 AstrBot）。"""

from __future__ import annotations

import enum

import pytest

from detection import (
    AUDIO_SUFFIXES,
    detect_voice_input,
    is_audio_path,
    raw_has_record,
)


class SegmentType(enum.Enum):
    TEXT = "text"
    RECORD = "record"


class Segment:
    """假的 OneBot 消息段对象。"""

    def __init__(self, type_: object) -> None:
        self.type = type_


class RawEvent:
    """假的 aiocqhttp 原始事件对象。"""

    def __init__(self, message: object, post_type: str = "message") -> None:
        self.message = message
        self.post_type = post_type


# ------------------------------------------------------------------ 信号 C


@pytest.mark.parametrize(
    "path",
    [
        "/AstrBot/data/temp/media_audio_1.wav",
        "/tmp/voice.amr",
        "/tmp/voice.mp3",
        "/tmp/voice.silk",
        "/tmp/voice.ogg",
        "/tmp/voice.m4a",
        "/tmp/voice.flac",
        "file:///tmp/voice.opus",
    ],
)
def test_is_audio_path_accepts_audio(path: str) -> None:
    assert is_audio_path(path)


@pytest.mark.parametrize(
    "path",
    ["/tmp/media_image_1.png", "/tmp/pic.JPEG", "/tmp/noext", "", None],
)
def test_is_audio_path_rejects_others(path: str | None) -> None:
    assert not is_audio_path(path)


def test_is_audio_path_ignores_url_query_and_fragment() -> None:
    assert is_audio_path("https://example.com/a.wav?token=1")
    assert not is_audio_path("https://example.com/a.png#x.wav")


def test_audio_suffixes_are_normalized() -> None:
    assert AUDIO_SUFFIXES
    for suffix in AUDIO_SUFFIXES:
        assert suffix.startswith(".")
        assert suffix == suffix.lower()


# ------------------------------------------------------------------ 信号 B


def test_raw_message_none() -> None:
    assert raw_has_record(None) is False


def test_raw_message_dict_with_record() -> None:
    assert raw_has_record({"message": [{"type": "record", "data": {}}]})


def test_raw_message_dict_text_only() -> None:
    assert not raw_has_record({"message": [{"type": "text", "data": {"text": "hi"}}]})


def test_raw_message_object_with_record() -> None:
    assert raw_has_record(RawEvent([Segment("record")]))


def test_raw_message_enum_segment_type() -> None:
    assert raw_has_record(RawEvent([Segment(SegmentType.RECORD)]))
    assert not raw_has_record(RawEvent([Segment(SegmentType.TEXT)]))


def test_raw_message_cq_code_string() -> None:
    assert raw_has_record(RawEvent("[CQ:record,file=abc.amr]"))
    assert not raw_has_record(RawEvent("你好"))


def test_raw_message_bare_segment_list() -> None:
    assert raw_has_record([{"type": "record"}])


def test_raw_message_non_message_post_type_is_ignored() -> None:
    assert not raw_has_record(RawEvent([Segment("record")], post_type="notice"))


# ------------------------------------------------------------------ 合并判定


def test_record_component_is_voice() -> None:
    assert detect_voice_input(has_record=True, local_files=None)


def test_no_signal_is_not_voice() -> None:
    assert not detect_voice_input(has_record=False, local_files=None)
    assert not detect_voice_input(has_record=False, local_files=[])


def test_temp_audio_is_voice() -> None:
    assert detect_voice_input(
        has_record=False,
        local_files=["/tmp/media_audio_1.wav"],
        raw_message=None,
    )


def test_temp_image_is_not_voice() -> None:
    assert not detect_voice_input(
        has_record=False,
        local_files=["/tmp/media_image_1.png"],
        raw_message=None,
    )


def test_quoted_voice_does_not_leak_into_text_message() -> None:
    """文字消息引用了一条语音时，临时文件里有音频，但原始消息段说没有。"""

    assert not detect_voice_input(
        has_record=False,
        local_files=["/tmp/media_audio_quoted.wav"],
        raw_message={"message": [{"type": "reply"}, {"type": "text"}]},
    )


def test_raw_record_wins_without_temp_files() -> None:
    assert detect_voice_input(
        has_record=False,
        local_files=[],
        raw_message={"message": [{"type": "record"}]},
    )


def test_falls_back_to_temp_files_when_platform_unknown() -> None:
    """通知事件（拿不到消息段）不应阻断信号 C。"""

    assert detect_voice_input(
        has_record=False,
        local_files=["/tmp/media_audio_1.wav"],
        raw_message=RawEvent([Segment("record")], post_type="notice"),
    )

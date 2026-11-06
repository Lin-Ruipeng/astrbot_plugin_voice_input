"""reply_policy.py 的纯函数测试（不需要安装 AstrBot）。"""

from __future__ import annotations

import pytest

from reply_policy import (
    DEFAULT_MAX_CHARS,
    clamp_max_chars,
    clamp_probability,
    should_block_other_tts,
    should_claim,
    should_convert,
)

BASE = {
    "probability": 1.0,
    "roll": 0.5,
    "voice_input": True,
    "already_record": False,
    "is_llm_result": True,
    "text_only": True,
    "text": "这是一条回复",
    "max_chars": 300,
}


def convert(**overrides: object) -> bool:
    return should_convert(**{**BASE, **overrides})  # type: ignore[arg-type]


# ------------------------------------------------------------------ 概率


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0.0),
        (0.0, 0.0),
        (0.5, 0.5),
        (1, 1.0),
        ("0.25", 0.25),
        (" 1.0 ", 1.0),
        (80, 1.0),  # 误填百分数：钳到 1.0
        (-3, 0.0),
        (None, 0.0),
        ("abc", 0.0),
        (float("nan"), 0.0),
        (float("inf"), 0.0),
    ],
)
def test_clamp_probability(raw: object, expected: float) -> None:
    assert clamp_probability(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (300, 300),
        ("120", 120),
        (0, 0),
        (-1, 0),
        (None, DEFAULT_MAX_CHARS),
        ("abc", DEFAULT_MAX_CHARS),
        (12.9, 12),
    ],
)
def test_clamp_max_chars(raw: object, expected: int) -> None:
    assert clamp_max_chars(raw) == expected


# ------------------------------------------------------------------ 转换判定


def test_converts_when_everything_matches() -> None:
    assert convert()


def test_probability_zero_never_converts() -> None:
    assert not convert(probability=0.0)


def test_probability_one_always_converts_regardless_of_roll() -> None:
    assert convert(probability=1.0, roll=0.999999)


def test_roll_above_probability_skips() -> None:
    assert not convert(probability=0.5, roll=0.5001)


def test_roll_equal_to_probability_converts() -> None:
    assert convert(probability=0.5, roll=0.5)


@pytest.mark.parametrize("roll", [0.0, 0.25, 0.5, 0.75, 0.999])
def test_half_probability_hits_roughly_half(roll: float) -> None:
    assert convert(probability=0.5, roll=roll) is (roll <= 0.5)


def test_text_input_never_converts() -> None:
    assert not convert(voice_input=False)


def test_existing_record_skips() -> None:
    assert not convert(already_record=True)


@pytest.mark.parametrize("is_llm_result", [False])
def test_command_or_streaming_result_skips(is_llm_result: bool) -> None:
    assert not convert(is_llm_result=is_llm_result)


def test_mixed_chain_skips() -> None:
    assert not convert(text_only=False)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_skips(text: str) -> None:
    assert not convert(text=text.strip())


def test_too_long_text_skips() -> None:
    assert not convert(text="字" * 301, max_chars=300)


def test_text_at_limit_converts() -> None:
    assert convert(text="字" * 300, max_chars=300)


def test_zero_max_chars_means_unlimited() -> None:
    assert convert(text="字" * 10_000, max_chars=0)


# ------------------------------------------------------------------ 独占


def test_claim_requires_probability_voice_and_clonetts() -> None:
    assert should_claim(probability=0.5, voice_input=True, clonetts_present=True)


@pytest.mark.parametrize(
    ("probability", "voice_input", "clonetts_present"),
    [
        (0.0, True, True),  # 关闭：完全不介入
        (1.0, False, True),  # 文字消息不归我们管
        (1.0, True, False),  # 没有竞争对手就不需要独占
    ],
)
def test_claim_is_false(
    probability: float, voice_input: bool, clonetts_present: bool
) -> None:
    assert not should_claim(
        probability=probability,
        voice_input=voice_input,
        clonetts_present=clonetts_present,
    )


def test_block_other_tts_when_conversion_skipped_on_voice_input() -> None:
    assert should_block_other_tts(
        probability=1.0,
        voice_input=True,
        clonetts_present=True,
        converted=False,
        is_llm_result=True,
    )


@pytest.mark.parametrize(
    ("converted", "is_llm_result"),
    [(True, True), (False, False)],
)
def test_block_other_tts_is_false_when_converted_or_not_llm(
    converted: bool, is_llm_result: bool
) -> None:
    assert not should_block_other_tts(
        probability=1.0,
        voice_input=True,
        clonetts_present=True,
        converted=converted,
        is_llm_result=is_llm_result,
    )


def test_block_other_tts_is_false_without_clonetts() -> None:
    assert not should_block_other_tts(
        probability=1.0,
        voice_input=True,
        clonetts_present=False,
        converted=False,
        is_llm_result=True,
    )

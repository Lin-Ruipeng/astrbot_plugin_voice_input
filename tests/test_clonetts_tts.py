"""clonetts_tts.py 的纯函数与回退分支测试（不需要安装 AstrBot / aiohttp）。"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from clonetts_tts import (
    CONFIG_SUFFIX,
    DONE_CODE,
    MODEL,
    PLUGIN_NAME,
    RESOURCE_ID_CLONE,
    RESOURCE_ID_TTS,
    build_headers,
    build_payload,
    config_path,
    load_config,
    parse_stream,
    synthesize,
)

CONF = {
    "api_key": "key-123",
    "voice_type": "S_abc",
    "sample_rate": 48000,
    "speed_ratio": 10,
    "loudness_rate": -5,
}


# ------------------------------------------------------------------ 配置发现


def test_config_path_uses_root_dir_name() -> None:
    path = config_path("/data/config", "astrbot_plugin_clonetts_main")
    assert path == Path("/data/config") / f"astrbot_plugin_clonetts_main{CONFIG_SUFFIX}"


@pytest.mark.parametrize("name", [None, "", "   "])
def test_config_path_falls_back_to_plugin_name(name: str | None) -> None:
    assert config_path("/data/config", name).name == f"{PLUGIN_NAME}{CONFIG_SUFFIX}"


def test_load_config_reads_utf8_bom(tmp_path: Path) -> None:
    target = tmp_path / "conf.json"
    target.write_text(json.dumps(CONF), encoding="utf-8-sig")
    assert load_config(target) == CONF


@pytest.mark.parametrize("content", ["", "not json", "[]", '"text"'])
def test_load_config_rejects_bad_content(tmp_path: Path, content: str) -> None:
    target = tmp_path / "conf.json"
    target.write_text(content, encoding="utf-8")
    assert load_config(target) is None


def test_load_config_missing_file(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.json") is None


# ------------------------------------------------------------------ 请求构造


def test_build_headers_uses_clone_resource_for_s_voices() -> None:
    headers = build_headers(CONF, request_id="req-1")
    assert headers["X-Api-Key"] == "key-123"
    assert headers["X-Api-Resource-Id"] == RESOURCE_ID_CLONE
    assert headers["X-Api-Request-Id"] == "req-1"
    assert headers["Content-Type"] == "application/json"


def test_build_headers_uses_tts_resource_for_other_voices() -> None:
    headers = build_headers({**CONF, "voice_type": "zh_female_1"})
    assert headers["X-Api-Resource-Id"] == RESOURCE_ID_TTS
    assert headers["X-Api-Request-Id"]


@pytest.mark.parametrize(
    "conf",
    [
        {},
        {"api_key": "k"},
        {"voice_type": "v"},
        {"api_key": "  ", "voice_type": "v"},
    ],
)
def test_build_headers_requires_credentials(conf: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        build_headers(conf)


def test_build_payload_keeps_clonetts_parameters() -> None:
    payload = build_payload("你好", CONF, uid="user-1")
    assert payload["user"] == {"uid": "user-1"}
    params = payload["req_params"]
    assert params["text"] == "你好"
    assert params["model"] == MODEL
    assert params["speaker"] == "S_abc"
    assert params["audio_params"] == {
        "format": "mp3",
        "sample_rate": 48000,
        "enable_timestamp": True,
        "speech_rate": 10,
        "loudness_rate": -5,
    }
    additions = json.loads(params["additions"])
    assert additions["explicit_language"] == "zh-cn"
    assert additions["disable_markdown_filter"] is True


@pytest.mark.parametrize("field", ["sample_rate", "speed_ratio", "loudness_rate"])
def test_build_payload_falls_back_on_bad_numbers(field: str) -> None:
    payload = build_payload("hi", {**CONF, field: "abc"})
    params = payload["req_params"]["audio_params"]
    key = "speech_rate" if field == "speed_ratio" else field
    assert isinstance(params[key], int)


@pytest.mark.parametrize("conf", [{}, {"api_key": "k"}])
def test_build_payload_requires_credentials(conf: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        build_payload("hi", conf)


# ------------------------------------------------------------------ 流式解析


def chunk(data: bytes) -> str:
    return json.dumps({"data": base64.b64encode(data).decode(), "code": 0})


def test_parse_stream_concatenates_chunks() -> None:
    lines = [chunk(b"abc"), chunk(b"def"), json.dumps({"code": DONE_CODE})]
    assert parse_stream(lines) == b"abcdef"


def test_parse_stream_stops_at_done_code() -> None:
    lines = [
        chunk(b"abc"),
        json.dumps({"code": DONE_CODE}),
        chunk(b"ignored"),
    ]
    assert parse_stream(lines) == b"abc"


def test_parse_stream_accepts_bytes_and_sse_prefix() -> None:
    lines = [
        f"data: {chunk(b'abc')}".encode(),
        b"",
        b"   ",
    ]
    assert parse_stream(lines) == b"abc"


@pytest.mark.parametrize(
    "lines",
    [
        [],
        ["not json", "[]", '"x"', json.dumps({"data": None})],
        [json.dumps({"data": "!!!not-base64!!!"})],
    ],
)
def test_parse_stream_ignores_garbage(lines: list[str]) -> None:
    assert parse_stream(lines) == b""


# ------------------------------------------------------------------ 合成入口


def test_synthesize_reports_missing_credentials(tmp_path: Path) -> None:
    path, error = asyncio.run(synthesize("hi", {}, temp_dir=tmp_path))
    assert path is None
    assert error is not None and "api_key" in error

"""TTS 回退：复用 ``astrbot_plugin_clonetts`` 的配置直连火山引擎 v3。

为什么需要这一层：``astrbot_plugin_clonetts`` 注册的是 LLM 工具，不是框架级
``TTSProvider``。只装它时 ``context.get_using_tts_provider_async()`` 拿不到任何
TTS 能力，强制语音回复会退化成纯文字。这里读它的配置文件（``api_key`` /
``voice_type`` / 采样率 / 语速 / 音量），按它同样的参数调火山 v3 接口，
把流式返回的 base64 音频块拼成 mp3。

纯函数（``config_path`` / ``load_config`` / ``build_headers`` / ``build_payload``
/ ``parse_stream``）不导入 ``astrbot`` 与 ``aiohttp``，可脱机单测；
``synthesize`` 才惰性导入 ``aiohttp``。
"""

from __future__ import annotations

import base64
import json
import tempfile
import traceback
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

PLUGIN_NAME = "astrbot_plugin_clonetts"
"""回退所依赖的插件名。"""

CONFIG_SUFFIX = "_config.json"
"""AstrBot 插件配置文件的后缀。"""

TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
"""火山引擎 v3 流式 TTS 接口（与 clonetts v3.0.4 一致）。"""

MODEL = "seed-tts-2.0-expressive"
"""与 clonetts v3.0.4 一致的模型名。"""

RESOURCE_ID_CLONE = "seed-icl-2.0"
"""音色克隆（``voice_type`` 以 ``S_`` 开头）用的资源 ID。"""

RESOURCE_ID_TTS = "seed-tts-2.0"
"""普通音色用的资源 ID。"""

DONE_CODE = 20000000
"""火山流式响应的结束码。"""

DEFAULT_SAMPLE_RATE = 24000


def config_path(config_dir: str | Path, root_dir_name: str | None = None) -> Path:
    """插件配置文件的路径。

    AstrBot 用**插件目录名**命名配置文件（``<data>/config/<dir>_config.json``），
    所以优先用 ``StarMetadata.root_dir_name``，拿不到时退回插件名。
    """

    name = (root_dir_name or "").strip() or PLUGIN_NAME
    return Path(config_dir) / f"{name}{CONFIG_SUFFIX}"


def load_config(path: str | Path) -> dict[str, Any] | None:
    """读取 clonetts 的配置。

    Returns:
        配置字典；文件不存在、不是合法 JSON 或顶层不是对象时返回 ``None``。
    """

    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _credentials(conf: Mapping[str, Any]) -> tuple[str, str] | None:
    api_key = str(conf.get("api_key") or "").strip()
    voice_type = str(conf.get("voice_type") or "").strip()
    if not api_key or not voice_type:
        return None
    return api_key, voice_type


def build_headers(
    conf: Mapping[str, Any], request_id: str | None = None
) -> dict[str, str]:
    """构造火山 v3 的请求头。"""

    pair = _credentials(conf)
    if pair is None:
        raise ValueError("clonetts 配置缺少 api_key 或 voice_type")
    api_key, voice_type = pair
    resource_id = RESOURCE_ID_CLONE if voice_type.startswith("S_") else RESOURCE_ID_TTS
    return {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": request_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }


def build_payload(
    text: str,
    conf: Mapping[str, Any],
    uid: str | None = None,
) -> dict[str, Any]:
    """构造火山 v3 的请求体（参数与 clonetts v3.0.4 保持一致）。"""

    pair = _credentials(conf)
    if pair is None:
        raise ValueError("clonetts 配置缺少 api_key 或 voice_type")
    _, voice_type = pair
    sample_rate = _as_int(conf.get("sample_rate"), DEFAULT_SAMPLE_RATE)
    return {
        "user": {"uid": uid or str(uuid.uuid4())},
        "req_params": {
            "text": text,
            "model": MODEL,
            "speaker": voice_type,
            "audio_params": {
                "format": "mp3",
                "sample_rate": sample_rate,
                "enable_timestamp": True,
                "speech_rate": _as_int(conf.get("speed_ratio"), 0),
                "loudness_rate": _as_int(conf.get("loudness_rate"), 0),
            },
            "additions": json.dumps(
                {
                    "explicit_language": "zh-cn",
                    "disable_markdown_filter": True,
                    "enable_latex_tn": True,
                },
                ensure_ascii=False,
            ),
        },
    }


def parse_stream(lines: Iterable[str | bytes]) -> bytes:
    """把火山流式响应拼成完整音频。

    每行是一个 JSON 对象，``data`` 字段是 base64 音频块；``code == 20000000``
    表示结束。兼容带 ``data:`` 前缀的 SSE 写法，坏行直接跳过。

    Args:
        lines: 响应体按行的迭代器（``str`` 或 ``bytes``）。

    Returns:
        拼好的音频字节；没有音频块时返回 ``b""``。
    """

    audio = bytearray()
    for line in lines:
        text = line.decode("utf-8", "ignore") if isinstance(line, bytes) else line
        text = text.strip()
        if text.startswith("data:"):
            text = text[len("data:") :].strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        chunk = payload.get("data")
        if isinstance(chunk, str) and chunk:
            try:
                audio.extend(base64.b64decode(chunk))
            except (ValueError, TypeError):
                continue
        if payload.get("code") == DONE_CODE:
            break
    return bytes(audio)


async def synthesize(
    text: str,
    conf: Mapping[str, Any],
    *,
    temp_dir: str | Path,
    timeout: float = 30.0,
    verbose: bool = False,
) -> tuple[str | None, str | None]:
    """调用火山 v3 合成语音并落盘。

    Args:
        text: 要朗读的文本。
        conf: clonetts 的配置字典。
        temp_dir: 临时音频目录。
        timeout: 整个请求的超时秒数。
        verbose: 失败时是否把 traceback 一并带回（由 ``verbose_log`` 控制）。

    Returns:
        ``(音频路径, 错误信息)``；成功时错误信息为 ``None``，失败时路径为 ``None``。
    """

    if _credentials(conf) is None:
        return None, "clonetts 配置缺少 api_key 或 voice_type"

    try:
        import aiohttp
    except ImportError:
        return None, "当前环境没有 aiohttp，无法走火山回退"

    headers = build_headers(conf)
    payload = build_payload(text, conf)

    try:
        async with (
            aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session,
            session.post(TTS_ENDPOINT, headers=headers, json=payload) as response,
        ):
            if response.status != 200:
                return None, f"火山接口返回 HTTP {response.status}"
            # 注意括号：``await response.read().splitlines()`` 会先取
            # ``.splitlines()`` 再 await，协程没有这个方法，合成永远失败。
            body = await response.read()
            audio = parse_stream(body.splitlines())
    except Exception as exc:  # noqa: BLE001 - 回退失败一律保留文字
        detail = f"{type(exc).__name__}: {exc}"
        if verbose:
            detail = f"{detail}\n{traceback.format_exc()}"
        return None, f"火山回退请求失败：{detail}"

    if not audio:
        return None, "火山接口没有返回音频数据"

    try:
        target_dir = Path(temp_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".mp3",
            prefix="voice_reply_",
            dir=str(target_dir),
            delete=False,
        ) as handle:
            handle.write(audio)
            path = handle.name
    except OSError as exc:
        return None, f"临时音频写入失败：{exc}"

    return path, None

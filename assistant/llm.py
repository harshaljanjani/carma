import json
from typing import List, Optional, Type, TypeVar

import litellm
from pydantic import BaseModel

from .config import HAS_LLM, MODEL

litellm.drop_params = True

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    pass


def _require_key():
    if not HAS_LLM:
        raise LLMUnavailable("GEMINI_API_KEY is not set; export it to enable the assistant.")


def complete(system: str, messages: List[dict], temperature: float = 0.3) -> str:
    _require_key()
    payload = [{"role": "system", "content": system}] + messages
    response = litellm.completion(model=MODEL, messages=payload, temperature=temperature)
    return response.choices[0].message.content or ""


def stream_complete(system: str, messages: List[dict], temperature: float = 0.3):
    _require_key()
    payload = [{"role": "system", "content": system}] + messages
    response = litellm.completion(model=MODEL, messages=payload, temperature=temperature, stream=True)
    for part in response:
        delta = part.choices[0].delta.content
        if delta:
            yield delta


def structured(schema: Type[T], system: str, user: str, temperature: float = 0.0) -> Optional[T]:
    _require_key()
    payload = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response = litellm.completion(
        model=MODEL,
        messages=payload,
        temperature=temperature,
        response_format=schema,
    )
    content = response.choices[0].message.content or ""
    return _parse(schema, content)


def _parse(schema: Type[T], content: str) -> Optional[T]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return schema.model_validate_json(content)
    except Exception:
        pass
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return schema.model_validate(json.loads(content[start : end + 1]))
        except Exception:
            return None
    return None

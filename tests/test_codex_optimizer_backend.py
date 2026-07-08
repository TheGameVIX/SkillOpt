from __future__ import annotations

import importlib.util
import os
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest


class _OpenAIClientStub:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


def _install_openai_stub() -> None:
    if "openai" in sys.modules or importlib.util.find_spec("openai") is not None:
        return
    openai_stub = types.ModuleType("openai")
    openai_stub.AzureOpenAI = _OpenAIClientStub
    openai_stub.OpenAI = _OpenAIClientStub
    sys.modules["openai"] = openai_stub


def _import_model_modules() -> tuple[Any, Any, Any, Any]:
    _install_openai_stub()
    import skillopt.model as model_module
    from skillopt.model import azure_openai, backend_config, codex_backend

    return model_module, backend_config, codex_backend, azure_openai


@pytest.fixture(autouse=True)
def isolate_backend_state() -> Iterator[tuple[Any, Any, Any, Any]]:
    model_module, backend_config, codex_backend, azure_openai = _import_model_modules()
    optimizer_backend = backend_config.get_optimizer_backend()
    target_backend = backend_config.get_target_backend()
    env = {
        key: os.environ.get(key)
        for key in (
            "OPTIMIZER_BACKEND",
            "TARGET_BACKEND",
            "OPTIMIZER_DEPLOYMENT",
            "TARGET_DEPLOYMENT",
        )
    }
    yield model_module, backend_config, codex_backend, azure_openai
    backend_config.set_optimizer_backend(optimizer_backend)
    backend_config.set_target_backend(target_backend)
    for key, value in env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_codex_exec_can_be_optimizer_backend(
    isolate_backend_state: tuple[Any, Any, Any, Any],
) -> None:
    _model_module, backend_config, _codex_backend, _azure_openai = isolate_backend_state

    backend_config.set_optimizer_backend("codex_exec")

    assert backend_config.get_optimizer_backend() == "codex_exec"


def test_set_backend_codex_uses_codex_for_optimizer_and_target(
    isolate_backend_state: tuple[Any, Any, Any, Any],
) -> None:
    model_module, backend_config, _codex_backend, _azure_openai = isolate_backend_state

    assert model_module.set_backend("codex") == "codex"

    assert backend_config.get_optimizer_backend() == "codex_exec"
    assert backend_config.get_target_backend() == "codex_exec"
    assert model_module.get_backend_name() == "codex"


def test_chat_optimizer_routes_to_codex_backend(
    monkeypatch: pytest.MonkeyPatch,
    isolate_backend_state: tuple[Any, Any, Any, Any],
) -> None:
    model_module, backend_config, codex_backend, azure_openai = isolate_backend_state
    codex_calls: list[dict[str, Any]] = []

    def fake_codex_optimizer(**kwargs: Any) -> tuple[str, dict[str, int]]:
        codex_calls.append(kwargs)
        return "codex result", {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }

    def fail_openai_optimizer(**_kwargs: Any) -> tuple[str, dict[str, int]]:
        raise AssertionError("openai optimizer should not be called for codex_exec")

    monkeypatch.setattr(codex_backend, "chat_optimizer", fake_codex_optimizer)
    monkeypatch.setattr(azure_openai, "chat_optimizer", fail_openai_optimizer)
    backend_config.set_optimizer_backend("codex_exec")

    text, usage = model_module.chat_optimizer("system", "user", retries=1, timeout=5)

    assert text == "codex result"
    assert usage["total_tokens"] == 3
    assert codex_calls[0]["system"] == "system"
    assert codex_calls[0]["user"] == "user"
    assert codex_calls[0]["timeout"] == 5

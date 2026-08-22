"""Testa o módulo de observabilidade: sem credenciais, tracing desligado — zero chamada ao SDK."""

from __future__ import annotations

from typing import Any

import pytest

from agent import observability
from app.config import Settings


def test_sem_credenciais_nao_chama_o_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem LANGFUSE_PUBLIC_KEY/SECRET_KEY, devolve [] e não instancia nada do Langfuse."""
    chamadas: list[str] = []
    monkeypatch.setattr(observability, "Langfuse", lambda **_: chamadas.append("Langfuse"))
    monkeypatch.setattr(
        observability, "CallbackHandler", lambda **_: chamadas.append("CallbackHandler")
    )
    settings = Settings(langfuse_public_key=None, langfuse_secret_key=None)

    handlers = observability.callbacks_langfuse(settings)

    assert handlers == []
    assert chamadas == []


def test_com_credenciais_cria_um_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com as duas chaves, instancia o cliente Langfuse e devolve 1 CallbackHandler do par."""
    construidos: dict[str, Any] = {}

    class FakeHandler:
        pass

    def fake_langfuse(*, public_key: str, secret_key: str, host: str) -> None:
        construidos["client"] = (public_key, secret_key, host)

    def fake_handler(*, public_key: str) -> FakeHandler:
        construidos["handler_key"] = public_key
        return FakeHandler()

    monkeypatch.setattr(observability, "Langfuse", fake_langfuse)
    monkeypatch.setattr(observability, "CallbackHandler", fake_handler)
    settings = Settings(
        langfuse_public_key="pk-teste",
        langfuse_secret_key="sk-teste",
        langfuse_host="http://langfuse.teste",
    )

    handlers = observability.callbacks_langfuse(settings)

    assert len(handlers) == 1
    assert isinstance(handlers[0], FakeHandler)
    assert construidos["client"] == ("pk-teste", "sk-teste", "http://langfuse.teste")
    assert construidos["handler_key"] == "pk-teste"


def test_cliente_openai_sem_credenciais_nao_registra_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem chaves, `cliente_openai` nunca chama `Langfuse(...)` (o import de `langfuse.openai`
    monkeypatcha o SDK globalmente ao acontecer — por isso o caminho sem credenciais não pode
    disparar nem o registro do cliente nem esse import; ver docstring do módulo)."""
    monkeypatch.setattr(observability, "Langfuse", lambda **_: pytest.fail("não deveria chamar"))
    settings = Settings(langfuse_public_key=None, langfuse_secret_key=None)

    cliente = observability.cliente_openai(settings, api_key="sk-teste")

    assert cliente.api_key == "sk-teste"


def test_cliente_openai_com_credenciais_registra_o_cliente_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com as duas chaves, `cliente_openai` registra o cliente Langfuse (ativa o tracing) antes
    de devolver o cliente OpenAI instrumentado."""
    registrado: dict[str, Any] = {}
    monkeypatch.setattr(
        observability,
        "Langfuse",
        lambda **kwargs: registrado.setdefault("client", kwargs),
    )
    settings = Settings(langfuse_public_key="pk-teste", langfuse_secret_key="sk-teste")

    cliente = observability.cliente_openai(settings, api_key="sk-abc")

    assert cliente.api_key == "sk-abc"
    assert registrado["client"]["public_key"] == "pk-teste"


def test_flush_sem_credenciais_nao_chama_o_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem chaves, `flush_langfuse` não chama `get_client` — nunca existiu cliente a esvaziar."""
    monkeypatch.setattr(observability, "get_client", lambda **_: pytest.fail("não deveria chamar"))
    settings = Settings(langfuse_public_key=None, langfuse_secret_key=None)

    observability.flush_langfuse(settings)  # não levanta


def test_flush_com_credenciais_chama_shutdown_do_cliente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com as duas chaves, `flush_langfuse` busca o cliente pelo public_key e chama shutdown()."""
    chamadas: list[str] = []

    class FakeClient:
        def shutdown(self) -> None:
            chamadas.append("shutdown")

    def fake_get_client(*, public_key: str) -> FakeClient:
        chamadas.append(f"get_client:{public_key}")
        return FakeClient()

    monkeypatch.setattr(observability, "get_client", fake_get_client)
    settings = Settings(langfuse_public_key="pk-teste", langfuse_secret_key="sk-teste")

    observability.flush_langfuse(settings)

    assert chamadas == ["get_client:pk-teste", "shutdown"]

"""Testa `LLMOpenAI.planejar`: saída malformada do LLM vira PlanoInvalidoError, não crash cru."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent.llm import LLMOpenAI, PlanoInvalidoError


def _cliente_fake(conteudo: str) -> Any:
    """Fake do SDK OpenAI: `chat.completions.create(...)` devolve `conteudo` fixo."""

    def _create(**_kwargs: Any) -> Any:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=conteudo))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))


async def test_json_malformado_vira_plano_invalido() -> None:
    """Saída não é JSON válido — mesma causa raiz de KPI fora do catálogo (LLM não-determinístico),
    tem que virar PlanoInvalidoError (o nó `planejar` do grafo só trata esse tipo)."""
    llm = LLMOpenAI(_cliente_fake("isso não é JSON"), modelo_forte="x", modelo_rapido="y")

    with pytest.raises(PlanoInvalidoError):
        await llm.planejar("qualquer pergunta")


async def test_json_sem_campo_obrigatorio_vira_plano_invalido() -> None:
    """JSON válido mas fora do schema de `Plano` (falta kpi_alvo) também vira PlanoInvalidoError."""
    llm = LLMOpenAI(_cliente_fake('{"dimensao": {}}'), modelo_forte="x", modelo_rapido="y")

    with pytest.raises(PlanoInvalidoError):
        await llm.planejar("qualquer pergunta")

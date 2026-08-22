"""Tracing opcional via Langfuse — 2 peças, ambas best-effort (princípio de produto): sem
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` configuradas, nenhuma chamada ao SDK acontece e o
grafo roda normal, sem tracing.

1. `callbacks_langfuse`: handler passado em `config["callbacks"]` na chamada ao grafo
   (`services/chat.py`) — LangGraph emite um evento de chain por nó, então cada nó
   (`condensar`, `planejar`, `perna_quantitativa`, `enriquecer`, `relatorio`) vira 1 span,
   sem instrumentar `grafo.py` nó a nó.
2. `cliente_openai`: as chamadas de LLM em `agent/llm.py` usam o SDK cru da OpenAI (não um
   `Runnable` do LangChain), então `config["callbacks"]` não as alcança — ficariam invisíveis
   dentro do span do nó (sem prompt/completion/tokens/custo). `langfuse.openai` reexporta a
   MESMA classe `openai.OpenAI`, mas monkeypatcha `chat.completions.create` (via `wrapt`) já
   ao ser IMPORTADO, globalmente no processo — por isso o import é local, só dentro do
   caminho com credenciais, pra não afetar o SDK quando Langfuse não está configurado. Cada
   chamada vira 1 generation, aninhada no span do nó corrente via contextvars (propaga através
   do `asyncio.to_thread` em `llm.py`).
"""

from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
from openai import OpenAI

from app.config import Settings


def _registrar_cliente(settings: Settings) -> bool:
    """Registra o cliente Langfuse (singleton por public_key). False = as chaves não existem."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return False
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return True


def callbacks_langfuse(settings: Settings) -> list[BaseCallbackHandler]:
    """Handler dos spans de nó do grafo. Sem-chave = [] (nenhuma chamada ao SDK)."""
    if not _registrar_cliente(settings):
        return []
    return [CallbackHandler(public_key=settings.langfuse_public_key)]


def cliente_openai(settings: Settings, *, api_key: str) -> OpenAI:
    """Cliente OpenAI do agente. Com Langfuse configurado, cada chamada vira uma generation
    (prompt/completion/tokens/custo); sem chaves, é o `openai.OpenAI` puro — sem monkeypatch."""
    if _registrar_cliente(settings):
        from langfuse.openai import OpenAI as OpenAIComTracing  # import local — ver docstring

        return OpenAIComTracing(api_key=api_key)
    return OpenAI(api_key=api_key)


def flush_langfuse(settings: Settings) -> None:
    """Esvazia o buffer de spans/generations no shutdown do processo (`lifespan` do FastAPI).

    Sem as duas chaves, nunca chegou a existir um cliente registrado — no-op, sem tocar o SDK
    (mesmo princípio best-effort das outras duas funções deste módulo)."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    get_client(public_key=settings.langfuse_public_key).shutdown()

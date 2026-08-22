# ADR 0006 — Langfuse Cloud, tracing via callback (não nó a nó) e import tardio do wrapper OpenAI

- **Status:** aceito
- **Data:** 2026-08-22
- **Issue:** #1 (observabilidade Langfuse: traces do grafo LangGraph)

## Contexto

A dependência `langfuse` estava travada no `pyproject.toml` desde o início do projeto, mas nunca
instrumentada — nem no `docker-compose.yml`, nem em `backend/`. O invariante do `CLAUDE.md` ("cada
run gravado no schema `harness` + Langfuse quando provisionado") ficou pendente. Três decisões não
óbvias tiveram que ser tomadas para fechar essa lacuna.

## Decisão 1 — Langfuse Cloud (SaaS), não self-hosted

Self-hospedar o Langfuse exige ClickHouse + Redis + object storage próprios — peso desproporcional
para um workshop cujos stores "sagrados" já são Postgres/Qdrant/MinIO (regra: nunca
`docker compose down -v`). Optou-se por Langfuse Cloud via `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`/`HOST`
no `.env`, sem novo serviço no `docker-compose.yml`. Sem as chaves, o tracing fica desligado e o
`/chat` funciona normal (best-effort, princípio de produto).

## Decisão 2 — Tracing via callback handler, não instrumentação nó a nó

`backend/agent/grafo.py` é um `StateGraph` de nós assíncronos comuns (não `Runnable`s LangChain
avulsos). Em vez de importar Langfuse dentro de `grafo.py` e abrir um span por nó manualmente
(o que acoplaria o grafo — hoje agnóstico de framework de observabilidade — a um SDK específico),
o `CallbackHandler` do Langfuse é passado em `config["callbacks"]` na chamada a `grafo.astream(...)`
(`app/services/chat.py`). O LangGraph já emite um evento de chain por nó ao executar; o handler
transforma cada um em 1 span automaticamente. `grafo.py` continua sem depender de Langfuse.

`config["metadata"] = {"langfuse_session_id": thread_id}` correlaciona o trace com o registro
equivalente em `harness.runs` (mesma chave usada por `fontes_recomendadas_da_thread`).

## Decisão 3 — `langfuse.openai` importado só quando há credenciais

As chamadas de LLM (`agent/llm.py::LLMOpenAI._chat`) usam o SDK cru da OpenAI
(`openai.OpenAI().chat.completions.create`), não um `Runnable` — `config["callbacks"]` não as
alcança, e ficariam invisíveis dentro do span do nó (sem prompt/completion/tokens/custo). O módulo
`langfuse.openai` resolve isso, mas **reexporta a mesma classe `openai.OpenAI`** e monkeypatcha
`chat.completions.create` (via `wrapt`) **globalmente no processo assim que é importado** — não é
uma subclasse opcional, é um efeito colateral de import.

Por isso `agent/observability.py::cliente_openai` importa `langfuse.openai` **localmente**, só
dentro do ramo em que as credenciais existem (`_registrar_cliente(settings)` retornou `True`). Sem
credenciais, o processo nunca importa `langfuse.openai` e o SDK da OpenAI não é tocado — preserva
"sem chaves, zero envolvimento do SDK" na prática, não só na branch de retorno.

A generation nasce aninhada no span do nó corrente porque o `CallbackHandler` atrela o span ao
contexto OTel ambiente (`contextvars`) durante a execução do nó, e `asyncio.to_thread` (usado em
`_chat` para não bloquear o loop) copia esse contexto para a thread — a cadeia de paternidade
sobrevive à troca de thread sem código extra de propagação.

## Consequências

- Zero serviço novo no `docker-compose.yml`; ativar observabilidade é só preencher 2 variáveis.
- `grafo.py` e `llm.py` mantêm o contrato de dependências (`Dependencias`, `ModeloLLM`) sem
  importar Langfuse — a instrumentação inteira vive em `agent/observability.py` + os pontos de
  wiring (`app/main.py`, `app/routers/chat.py`, `app/services/chat.py`).
- Limitação conhecida, aceita para este escopo: não há flush/shutdown explícito do cliente Langfuse
  no `lifespan` do FastAPI — um `SIGTERM` abrupto pode perder o último lote de spans em buffer
  (o exportador já faz flush por intervalo/tamanho de lote; não há perda em shutdown gracioso).

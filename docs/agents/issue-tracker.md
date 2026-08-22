# Issue tracker

Issues e PRDs vivem como **GitHub Issues** do repo `AndreNonatoFigueiredo/workshop-agent-harness`
(o fork onde este projeto roda), geridas via `gh` CLI. O upstream
`caio-moliveira/workshop-agent-harness` é só referência histórica — não abrimos issue nem PR lá.

## Template de issue

Toda issue gerada pelo `/to-issues` segue o template de `.claude/skills/to-issues/SKILL.md`
(`## What to build` · `## Acceptance criteria` · `## Blocked by`), com a label `ready-for-agent`
quando pronta para um agente AFK.

## Fluxo de implementação: branch + PR por issue

Cada issue vira **uma branch própria**, nunca commit direto em `main`.

1. **Branch:** `feat/<issue>-<slug-curto>` a partir de `main` atualizada (ex.: `feat/1-langfuse`).
2. **Implementa a fatia**, com o gate rodando a cada edição (hook `PostToolUse`/`Stop`).
3. **Gate verde** (`ruff` + `mypy` + `pytest` — `/validar`) antes de abrir a PR.
4. **Abre a PR** contra `main`, corpo referenciando a issue (`Closes #N`) e resumindo o que mudou.
5. **`revisor-codigo`** revisa o diff da PR. Bloqueante → corrige e empurra de novo na mesma
   branch. Sem bloqueante (`aprovado` ou `aprovado com ressalvas`) → segue.
6. **Auto-merge:** com gate verde + revisor sem bloqueante, o próprio agente faz o merge
   (`gh pr merge --merge --delete-branch`) — merge commit, não squash/rebase (mantém o padrão já
   presente no histórico: `Merge pull request #N from ...`). Fecha a issue automaticamente via
   `Closes #N` no corpo da PR.
7. **Delivery record** em `metrics/entregas.jsonl` (schema em `metrics/README.md`), commitado
   depois do merge — direto em `main` (é só o registro de métrica, não uma fatia de produto).

Isso troca o padrão anterior (commit direto em `main`, herdado do histórico pré-existente deste
fork) por um fluxo com PR — dá um artefato de review e um ponto de auto-merge explícito, mantendo
o ciclo 100% AFK quando o gate e o revisor não acham bloqueante. Se o revisor bloquear, a correção
acontece **antes** do merge, na mesma branch — não vira uma segunda PR.

## Triage labels

Vocabulário canônico documentado em `docs/agents/triage-labels.md`.

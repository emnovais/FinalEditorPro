# Propostas de anotação temporal por IA

As anotações complementares ficam separadas das referências humanas. O contrato
`WindowProposal` valida descrição, categorias visuais, incertezas e eventos com
pelo menos dois índices distintos de frames fornecidos. Uma saída válida no schema
não comprova a veracidade da descrição. Modelos não recebem as descrições humanas
nesta rodada, evitando tratá-las como evidência visual independente.

## Protocolo local

Qwen3-VL 8B e Gemma 3 12B já aprovados são executados sequencialmente pelo runtime
local auditado, com hashes verificados e sandbox de rede restrito a loopback.
Nenhum download, instalação, envio remoto ou alteração do exportador é necessário.
Frames derivados de 512 pixels de largura são amostrados a 1 fps, em janelas de
até oito imagens, com uma imagem de sobreposição. Não há análise do sinal de áudio.

Cada evento conserva os índices que o modelo citou. Os campos temporais usam
frações exatas do frame rate original e representam **o intervalo das evidências
amostradas**, não início/fim exatos da ação. A resolução temporal da observação é
aproximadamente um segundo. Eventos curtos podem ser perdidos; discordância entre
modelos não é resolvida automaticamente. Uma pose não comprova uma ação.

`event_interval` usa intervalos semiabertos: `[primeiro_frame, último_frame + 1)`.
Os hashes de entrada/modelo, falhas, respostas brutas privadas, tempo de inferência
e incertezas permanecem no workspace. As fontes recebem verificação de hash,
tamanho e mtime antes e depois da execução.

## Splits e independência

Todos os seis clipes atuais ficam em `development`: pertencem ao mesmo grupo de
origem provisório e o conjunto já participou da preparação e exploração dos modelos.
O agrupamento conservador é mantido. Nenhum dos clipes se torna um holdout por
renomeação ou sorteio. Avaliação independente requer mídia de novos grupos de
origem, reservada antes de ajustar prompts ou modelos.

O dataset derivado continua `frozen=false`, com referências humanas `pending`.
Propostas de modelos avaliados não são convertidas em ground truth nem usadas para
atribuir notas a esses mesmos modelos. Identidade/data do anotador, revisão das
categorias, exaustividade, validação temporal e notas humanas cegas continuam sendo
pendências humanas. Música não deve ser tratada como vídeo para preencher essas
categorias e não fornece evidência sobre os eventos visuais.

## Verificação

`tests/test_proposals.py` cobre rejeição de evidências inexistentes/duplicadas,
conversão temporal racional e atribuição a desenvolvimento sem promover referências
humanas. A suíte anterior é preservada.

## Resultado da execução local — 16/11/2026

Foram processados os seis vídeos em 14 janelas por modelo, 28 inferências reais.
Qwen3-VL 8B: 13 respostas válidas e uma falha de schema por lista de incertezas
vazia. Gemma 3 12B: 14 respostas válidas. Há 33 e 51 propostas de eventos,
respectivamente; essas contagens incluem descrições sobrepostas, poses e hipóteses
divergentes, não representam 84 eventos únicos ou confirmados. Aderência ao schema
não é medida de precisão visual. Não foi feito ranking nem alterada a comparação
anterior dos modelos.

Artefatos locais em `workspace/evaluation/annotation-proposals-v1/`:

- `proposals.json`: resultados completos por janela/modelo e pendências.
- `review.html`: revisão visual com frames, categorias, intervalos e incertezas.
- `dataset-development.json`: cópia derivada com todos os clipes em desenvolvimento.
- `integrity.json`: hashes, tamanho e mtime dos seis originais conferidos na execução.
- `run.py`, `summarize.py`: scripts locais desta rodada; respostas brutas privadas
  e imagens derivadas permanecem ignoradas pelo Git.

A tentativa inicial não iniciou o backend porque o sandbox externo bloqueou
`sandbox_apply`; a execução autorizada usou o sandbox próprio do runtime, sem
remover o bloqueio de rede externa. O contexto encerrou o servidor ao finalizar.
76 testes aprovados; `git diff --check` sem erros. Nenhum commit/push realizado.

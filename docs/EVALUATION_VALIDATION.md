# MVP 0.2.1 — validação do framework e piloto local

Data: 16/11/2026, Australia/Brisbane. Base Git confirmada: 7c4ad63, main limpa ao
início. Nenhum commit/push realizado nesta etapa. **Framework implementado e piloto
operacional executado; seleção final de modelos inconclusiva.**

## Escopo e aprovações

Pesos do usuário preservados: visual 25%, temporal 25%, confiabilidade 20%,
criatividade 15%, velocidade 10%, memória 5%. Não há total quando faltam dados;
não redistribuir os 85% de critérios de qualidade para os 15% de desempenho.

O usuário aprovou baixar Qwen3-VL 8B, Gemma 3 4B e Gemma 3 12B, após inspeção de
manifestos/licenças. Todas as camadas/configs foram verificadas por SHA/tamanho.
Artefatos adicionais publicados: ~17,7 GB. Somente workspace/; sem instalação
ou atualização de dependências. Baseline Qwen3-VL 4B/runtime existente reaproveitado.
Gemma tem termos próprios; Qwen usa Apache-2.0. Auditoria: EVALUATION_CANDIDATES.md.

Todos os quatro modelos carregaram texto/imagens no runtime Apple Silicon
existente (llama-server incluso no Ollama standalone v0.40.16). Ready significa
compatível para medir, não aprovado para produção ou qualidade certificada.
Contexto 8192, um slot, uma instância por vez, mesmos frames por caso. Não houve
API remota, download de dataset ou envio de mídia. O sandbox existente foi mantido.

## Dataset e referência fornecida

Seis MXFs locais foram inventariados e verificados, além do arquivo humano
`workspace/Descricao dos videos`, fornecido pelo usuário. Este descreve os seis
clipes e inclui observações de áudio. Foi preservado integralmente; SHA:
`bd7cc387278d600ed753008b03ee59a93a1b8e54dd0db5a28b1b7f1a89737f8b`.

Importação separada: workspace/evaluation/dataset-human-descriptions.json.
Texto visual e notas de áudio foram separados, sem inventar objetos estruturados,
intervalos de eventos, identidade do anotador ou data de verificação. O material
humano é útil para revisão, mas não é um gabarito temporal exaustivo. Voz/instruções
mencionadas no áudio não são critérios de acerto para modelos que só viram imagens.

São seis clipes de uma mesma sessão aparente; grupos/splits ainda não foram
confirmados pelo usuário. Todos permanecem unassigned, dataset frozen=false.
As oito categorias solicitadas ainda não têm cobertura humana certificada. Isso
não prova ausência física de todas essas categorias, apenas falta de anotação
confirmada. Não presumir casamento a partir da presença de um casal. Faltam
amostras independentes/categorias para um held-out representativo; não dividir
aleatoriamente clipes do mesmo grupo entre desenvolvimento e teste final.

O piloto usou dois casos: clip-01 (3,84 s, interação próxima) e clip-06 (10,08 s,
cuja descrição humana menciona beijo seguido de olhar para câmera). Os outros
quatro foram inventariados/anotados em texto, mas não medidos nesta rodada.
Cada caso usa quatro proxies PNG 320×180, índices/timestamps congelados e hash.
Modalidade: sequência de frames, não entrada de vídeo nativa. Assinaturas de input
e protocolo são únicas por caso e iguais nos quatro modelos.

## Execuções reais e protocolo

Três sessões novas por modelo/caso: **24 sessões, 48 inferências reais**, primeiro
pedido cold e segundo warm em cada sessão. Warm chama o modelo: não usa cache de
relatório. Houve ainda 30 leituras/validações de respostas em cache, medidas à
parte e sem inferência. Tentativas de desenvolvimento/preflight não foram misturadas.
Cold é processo novo; não se purgou cache de arquivos do macOS. Temperatura 0 não
é uma garantia de reprodutibilidade bit a bit de kernels/modelos.

Protocolo comum final: content-only-schema-prompt-envelope-v3. Foi definido após
preflights exploratórios, antes de uma avaliação final (que ainda não existe).
O parser nativo falhou ao inicializar o sampler estruturado Gemma. A alternativa
content-only foi aplicada a TODOS os modelos, com schema também explícito no
prompt. Um envelope Markdown JSON que ocupa a mensagem inteira é desembrulhado
por regra determinística comum, registrado e mostrado ao revisor. Nenhum campo
extra ou conteúdo incorreto é removido para transformar erro em sucesso.

Pydantic e grounding continuam estritos. No clip-01, Qwen3-VL 4B produziu respostas
que não satisfizeram campos mínimos; diagnóstico adicional confirmou descrição/
evidências/incertezas vazias nessa configuração. No clip-06, produziu respostas
válidas. Gemma 3 4B gerou campos extras nos casos observados, recusados pelo schema.
Essas são falhas de contrato, não prova automática de erro visual ou incompatibilidade
de hardware. O baseline 0.2 já havia funcionado no protocolo nativo: os números
abaixo avaliam modelo+configuração v3, não uma capacidade universal do modelo.

## Resultados medidos

Todos os tempos a seguir são observações reais. Latências incluem resposta
validada no cliente. RSS é residente do servidor, amostrado a cada 250 ms; não é
memória GPU/unificada total. Não apresentar pico amostrado como pico exato.

| Modelo | Respostas válidas / tentativas | Mediana cold válida | Mediana warm válida | IQR warm | RSS máximo observado |
|---|---:|---:|---:|---:|---:|
| Qwen3-VL 4B | 6 / 12 | 6,042 s* | 5,292 s* | 0,138 s* | 4,51 GiB |
| Qwen3-VL 8B | 12 / 12 | 10,696 s | 9,376 s | 0,670 s | 7,23 GiB |
| Gemma 3 4B | 0 / 12 | — | — | — | 3,99 GiB |
| Gemma 3 12B | 12 / 12 | 29,548 s | 21,796 s | 0,184 s | 9,53 GiB |

\* Qwen3-VL 4B teve respostas válidas apenas no clip-06. Esses tempos NÃO devem
ser usados para declará-lo mais rápido no conjunto completo. O score de velocidade
e os critérios de qualidade ficam ausentes quando faltam casos válidos; não
beneficiar modelo que só resolveu um subconjunto. A tabela de recursos inclui
medições de tentativas fracassadas, sem certificar sua utilidade editorial.

Mediana de carregamento até health (sem hashing): 4,455 s / 4,835 s / 5,009 s /
5,109 s, na ordem da tabela. Verificação de integridade e setup total são separados
no JSON. Geração de respostas válidas reportou mediana de ~76,93 / 49,38 / — /
23,21 tokens/s. Tokens e encoders não são diretamente equivalentes entre famílias.
Latências de falhas e estatísticas por caso também estão no relatório, não omitidas.

Microbenchmark de cache de resposta: medianas de ~0,106 ms (Qwen4), 0,146 ms
(Qwen8) e 0,137 ms (Gemma12); Gemma4 não tinha resposta válida a reutilizar.
Isso mede leitura/validação do JSON já salvo, não a análise end-to-end do Analyzer
nem revalidação completa de vídeo no período cronometrado. Nunca comparar esses
valores como velocidade de inferência. Sem tokens/inferência adicionais no cache.

Fonte completa: workspace/evaluation/comparison-pilot-v3-final.json. Há n, IQR,
mínimo/máximo, loading, integridade, falhas, TPS, RSS e hash de protocolo por ensaio.
A amostra pequena, dois casos e três sessões são piloto, não prova de significância
ou generalização a vídeos longos/outros projetos. Estado térmico e carga de outros
apps não foram controlados como em laboratório. Parte da preparação local ocorreu
entre medições exploratórias; não classificar este piloto como ensaio final isolado.

## Revisão cega preparada

**30 respostas válidas, cinco saídas únicas**, deduplicadas apenas quando input,
caso, JSON canônico e normalização eram idênticos. A revisão de uma saída pode ser
aplicada às repetições idênticas com hash, mas não vira seis juízos humanos.
Pacote local autocontido, com os mesmos frames e notas humanas visuais:

`workspace/evaluation/blind-review-v3/blind/review.html`

Mapa privado de identidade fica fora de blind/, para revelar só após avaliação.
Notas e contagens de afirmações são preenchidas pelo humano; nenhum LLM foi usado
como juiz. Não foram inventadas notas visuais, temporais ou de utilidade criativa.
Respostas fracassadas constam nas métricas/artefatos privados, não como saídas
certificadas para o futuro Director.

## Conclusão e pendências

**Inconclusivo para seleção final de modelo ou combinação por tarefa.** Não há
weighted_score nem automatic_winner. Operacionalmente, Qwen8 e Gemma12 satisfizeram
o contrato nos dois casos; isso não decide precisão visual/temporal nem criatividade.
A maior parte do peso depende da avaliação humana ainda não realizada. Não
promover configurações de produção nem avançar ao Director com um vencedor presumido.

Para completar: preencher a revisão cega, confirmar grupos/splits e categorias,
acrescentar intervalos temporais/rótulos humanos quando houver métrica objetiva,
e obter amostras independentes para avaliação final. Usar o development para
qualquer otimização de prompt/configuração; depois congelar e reavaliar todos em
held-out. Modelos por tarefa podem ser selecionados após esses trade-offs, sem
acoplamento ao exportador ou promoção automática por score agregado.

## Segurança, regressão e testes

Vídeos originais (seis), arquivo humano e FCPXML validado permaneceram com os
hashes anteriores. Nenhuma biblioteca foi acessada/alterada. Nenhuma mídia,
proxy, peso, cache ou credencial foi adicionado ao Git. Runtime e servidores
continuam somente no workspace, com lifecycle de encerramento gerenciado.
Schemas/relatórios do Analyzer 0.2 preservados; somente o helper de runtime ganhou
instrumentação e opção explícita de parser, mantendo o default anterior.

Suíte atual: **74 testes aprovados** (59 da base + 15 novos). Inclui pesos,
proveniência, separação de grupos, hashes de respostas, revisão cega e deduplicação,
falhas, cache que não substitui inferência, protocolo comum, importação humana
sem timestamps inventados e abstenção com dados faltantes/casos não resolvidos.

```sh
TMPDIR="$PWD/temp/evaluation-audit" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/python -m pytest -q --basetemp=temp/evaluation-audit/pytest-final
```

Documentação operacional: EVALUATION.md. Schemas em docs/evaluation-schemas/.
Pesos em config/evaluation-weights.json. Os resultados reais completos, inputs,
referência humana e pacote cego ficam ignorados em workspace/evaluation/.

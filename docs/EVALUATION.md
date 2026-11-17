# Model Benchmark & Evaluation — MVP 0.2.1

Esta camada compara configurações de IA sem modificar AnalysisReport 0.2,
exportador FCPXML, mídias ou bibliotecas do editor. Os pesos solicitados são:
precisão visual 25%, temporal 25%, confiabilidade 20%, utilidade criativa 15%,
velocidade 10%, eficiência de memória 5% (`config/evaluation-weights.json`).
Pesos devem somar 1. Métricas ausentes ficam null; não redistribuir seus pesos.

## Preparação e compatibilidade

Plano: MVP_0_2_1_PLAN.md. Candidatos/licenças: EVALUATION_CANDIDATES.md.
Nenhum comando desta camada baixa pesos ou instala dependências implicitamente.
O catálogo config/evaluation-models.json diferencia candidato de ready. Modelo
novo só é medido após preflight: hashes, carregamento, modalidade image anunciada
pelo servidor e recepção de um pedido multimodal. Validade da resposta é um
resultado separado: falha de formato/schema conta contra confiabilidade, sem
excluir seletivamente o modelo e criar viés de sobrevivência. ready significa
pronto para medir, não aprovado para produção.
Falhas são registradas e não corrigidas por fallback de nuvem ou outro modelo.

Cada ModelSpec aponta a manifest de runtime com hashes aprovados, digest do
modelo, quantização detectada e licença. Executa-se uma instância por vez com o
mesmo runtime local e sandbox existente. Mudanças de modelo NÃO alteram rotas de
produção: qualquer promoção por tarefa requer decisão humana e configuração
explícita. LOCAL/HYBRID/CLOUD do Analyzer continuam intactos; este runner só usa
backend local e nunca chama APIs de inferência remotas.

## Dataset e referência humana

```sh
.venv/bin/python -m final_editor_pro.evaluation.cli inventory \
  workspace/test_media --output workspace/evaluation/dataset-new.json
.venv/bin/python -m final_editor_pro.evaluation.cli coverage \
  workspace/evaluation/dataset-new.json
```

A ingestão reutiliza ffprobe/metadata. O inventário não classifica automaticamente
as categorias nem cria gabaritos. Cada caso possui hash, fps racional, intervalo
[start_frame,end_frame), source_group, split, categorias e referência humana.
Categorizações e status pending são distintos de ausência de objetos/eventos.
Datasets ficam em workspace/, sem upload e ignorados pelo Git.

O usuário forneceu `workspace/Descricao dos videos`, com seis descrições em
português. O importador preserva texto e SHA, separa notas de áudio e deixa
pendentes identidade do anotador, datas, intervalos de eventos e rótulos exaustivos.
Não transforma descrições gerais em eventos frame-exatos. O arquivo original
permanece intacto; dataset adaptado fica em arquivo separado.
Um formulário opcional também pode ser gerado via `annotate DATASET --output PATH`;
ele começa vazio e não mostra respostas de modelos como referência.

Referência verified exige anotador, data e notas de evidência. Objetos, ações e
eventos têm rótulos/aliases fornecidos pelo humano e intervalos em frames. O
schema recusa intervalos fora do caso. Development e evaluation não podem conter
o mesmo grupo ou mesmo arquivo (hash), mesmo com nomes/grupos renomeados. Não
resolver falta de variedade colocando seis clipes da mesma sessão nos dois splits.
Para `frozen=true`, todos os casos precisam de referências e splits atribuídos.
A avaliação final ainda exige casos evaluation e cobertura do conjunto solicitado.

Categorias: restaurant, wedding, event, travel, people_motion, camera_motion,
low_light, rapid_changes. Marcar categorias só após confirmação humana. Mais
amostras locais poderão ser necessárias; nenhum dataset externo foi autorizado.

## Entradas equivalentes

```sh
.venv/bin/python -m final_editor_pro.evaluation.cli freeze-input \
  DATASET CASE_ID ANALYSIS_REPORT_0_2 --output workspace/evaluation/inputs/CASE_ID.json
```

Congela PNGs base64, ordem, índices e timestamps do Analyzer, verificando hashes
contra a mídia original e cache de frames. Requer pelo menos dois frames por caso.
O pacote contém checksum do input e não pode ser sobrescrito pelo comando.
Mídia original é revalidada antes/depois das sessões. Todos os modelos recebem
exatamente esse pacote. Modalidade da rodada: ordered_timestamped_frames; não é
comparação de vídeo nativo contra imagens.

Prompt/schema/parâmetros partem do adapter temporal 0.2. O protocolo comum v3
acrescenta o schema explicitamente ao texto para TODOS os modelos e usa parser
content-only do backend (content-only-schema-prompt-envelope-v3). Um envelope Markdown JSON que ocupa a mensagem inteira
pode ser desembrulhado deterministicamente para todos; esse fato é registrado
por resposta. Não são removidas chaves extras nem reparado JSON inválido. A
validação Pydantic/grounding continua integral. A assinatura
do payload remove apenas o identificador do modelo e preserva imagens/configuração.
O runner grava metadata do backend: encoder/tokenizador/templates internos e
quantização podem diferir, e essas diferenças são explicitadas. Contexto 8192,
um slot, temperatura 0 e limite 1800 tokens no adapter atual. Não ajustar o prompt
para favorecer um candidato depois de observar o conjunto final; usar development
para alterações e rodar protocolo novo para todos.

## Sessões e medições

```sh
.venv/bin/python -m final_editor_pro.evaluation.cli run \
  DATASET MODEL_SPEC --inputs workspace/evaluation/inputs \
  --output workspace/evaluation/model-run-new --repetitions 3 \
  --cases clip-01 --exploratory
```

Sem --exploratory, recusa dataset não congelado ou casos fora de evaluation.
Modo exploratório é identificado na proveniência, não conta como avaliação final.
Pelo menos três sessões independentes por caso/modelo; cada sessão carrega um
servidor novo, faz primeiro pedido cold_inference e segundo warm_inference real.
Ambos chamam o modelo. Não usam cache de relatório do Analyzer. A leitura/validação
de uma resposta salva é medida à parte como report_cache, com tokens não medidos
(null), sem nova inferência. Cache hit não é usado para classificar velocidade de IA.
Cold não significa limpar caches de arquivos do macOS; o modelo começa em processo
novo, mas arquivos podem estar no cache do sistema. Warm inclui reuso interno de
contexto/prefill do backend; diferenças inevitáveis entre famílias são registradas.

Startup total inclui verificação de hashes, separada de load_ready_seconds (spawn
até endpoint saudável). Inferência mede latência cliente até resposta validada.
Tokens/s só é registrado se o backend reportar geração: não inventar dividindo
tokens por tempo total. RSS do servidor é amostrado a cada 250 ms, não é memória
unificada/GPU total. Quando ps falhar a medição é ausente, nunca zero fictício.
Não somar picos não simultâneos de vários processos. Falhas/timeouts são mantidos;
falta de inferência por falha de startup tem latência null. Não há retries ocultos.

A saída contém trials.json e provenance.json, registros por sessão e metadata do
backend. Há mediana, IQR inclusivo, mínimo, máximo e n por condição. Não misturar
cold, warm e cache numa só latência. Três repetições são um piloto, não estimativa
robusta de significância estatística. Gerenciador encerra o servidor em finally.

## Revisão cega humana

```sh
.venv/bin/python -m final_editor_pro.evaluation.cli blind \
  MODEL_A/trials.json MODEL_B/trials.json --output workspace/evaluation/review-new
```

Abrir manualmente blind/review.html. Página autocontida, sem servidor, fontes ou
scripts externos; não é aberta automaticamente. Ordem aleatória e IDs opacos;
modelos, quantização, latência e IDs internos não aparecem no pacote público.
identity-map.private.json fica fora da pasta blind e deve ser aberto só depois.
A presença de envelope normalizado é mostrada ao revisor.
O texto gerado em si pode revelar estilo/identidade; cegamento de metadata não
garante que o revisor nunca reconheça uma família pelo conteúdo.

Com --dataset e --inputs, o pacote cego inclui os mesmos frames congelados e
notas visuais humanas, sem o áudio. Julgar somente o que é visível nas amostras:
as notas descrevem o clipe completo e podem mencionar eventos não amostrados.
O revisor deve consultar os frames/timestamps originais, atribuir notas 0..4 para
visual, temporal, confiabilidade e criatividade, contar afirmações verificadas e
sem suporte e escrever notas. Rubrica geral: 0 incorreto/inútil; 1 muitos erros;
2 parcial; 3 bom com ressalvas; 4 correto/útil na evidência disponível. Julgar
incerteza, conteúdo ausente e uso editorial, não só fluência do texto.
Confiabilidade humana considera alucinações/calibração; confiança do modelo não
é nota humana. Nenhum LLM é usado como juiz desta camada.

O botão gera JSON em um campo de texto; salvar manualmente dentro de workspace/.
Não há download automático para fora do projeto. Reviews têm identidade do revisor,
data e hash da resposta. Duplicatas/IDs desconhecidos ou resposta alterada são
recusados. Para múltiplos avaliadores será necessária política explícita de
adjudicação; não escolher silenciosamente a nota mais favorável.

## Métricas, pesos e decisão

```sh
.venv/bin/python -m final_editor_pro.evaluation.cli compare DATASET \
  MODEL_A/trials.json MODEL_B/trials.json \
  --reviews workspace/evaluation/reviews.json \
  --identity-map workspace/evaluation/review-new/identity-map.private.json \
  --output workspace/evaluation/comparison-new.json
```

Objetivas: sucesso/falha/timeout, validação de índices/timestamps do contrato,
checagem exata de rótulos/aliases humanos (recall), precisão de rótulos apenas se
anotação de objetos for exaustiva, desempenho e recursos. Um texto não casado por
alias não é automaticamente alucinação. Temporalidade/IoU só faz sentido quando
há intervalos de eventos previstos verificáveis: o output atual do Analyzer tem
índices de evidência, não intervalos completos por ação. Não inventar IoU a partir
de um único frame. A utilidade interval_iou está disponível para futuras previsões
com spans; nesta rodada a qualidade temporal é revisada por humano.

Critérios 0..1: visual/temporal/criatividade = média humana /4; confiabilidade =
(média humana /4) × taxa de sucesso operacional. Speed = 1/(1+mediana warm/10 s);
memory = 1/(1+mediana RSS/36 GB). Referências são explícitas e devem ser fixadas
antes da comparação; não min-max relativo que muda ao adicionar candidatos.
Modelos com notas/revisões/medições ausentes não recebem total. Pesos são os
25/25/20/15/10/5 solicitados, sem normalização oportunista de métricas faltantes.

Mesmo com total completo não há automatic_winner. Relatório expõe seis componentes,
trade-offs, cobertura, n, IQR e falhas. Sem dois modelos, entradas equivalentes,
repetições suficientes, revisão humana ou dataset final, conclusão é inconclusive.
Melhor modelo para cada tarefa e combinação local exigem revisão desses dados,
não promoção automática por score. Nenhuma configuração de produção é sobrescrita.

## Comandos de preparação adicionais

`import-descriptions DATASET SOURCE --output PATH` importa as notas textuais sem
inventar intervalos. `preflight DATASET MODEL_SPEC CASE_ID --input PACKET --output
PATH` verifica runtime/capacidade e preserva falhas de resposta separadamente.
Dados humanos de referência alterados após importação invalidam a comparação pelo
SHA de origem. As referências temporais finas e a revisão cega continuam humanas.

## Protocolo e tentativas de desenvolvimento

As primeiras tentativas exploratórias identificaram uma falha do sampler de
JSON-schema no parser nativo do backend Gemma. O modo content-only resolveu essa
falha de runtime, mas expôs envelopes Markdown. O protocolo comum final do piloto
é content-only-schema-prompt-envelope-v3: schema também no prompt, mesma política
para todos e desembrulho somente de um envelope JSON que ocupa toda a mensagem.
O schema de conteúdo permanece estrito: campos extras, descrições vazias ou
referências inválidas continuam sendo falhas. Não remover campos arbitrários
para melhorar a taxa de sucesso. Tentativas anteriores não são misturadas na
comparação v3; a assinatura de protocolo impede apresentá-las como equivalentes.

O baseline de produção 0.2 não foi alterado. Um modelo pode responder bem ao
protocolo nativo do Analyzer e falhar no protocolo comum desta avaliação. Os
resultados são de configuração+modelo, não uma medida universal de capacidade.
Novas otimizações por modelo devem ser feitas em development, declaradas como
protocolos distintos e reavaliadas com entradas comparáveis, sem ajustar depois
no held-out. Anotações humanas nunca são incluídas no prompt de inferência;
só entram na revisão/avaliação posterior para não vazar o gabarito.

Respostas com JSON canônico idêntico no mesmo caso/input e com a mesma normalização são
deduplicadas na revisão cega. O mapa aplica um juízo humano às observações
idênticas, reportando separadamente avaliações únicas e respostas cobertas.
Isso não é evidência de múltiplos revisores. Casos sem resposta válida impedem
score de qualidade/velocidade agregado no conjunto completo, evitando favorecer
um modelo por resolver só o subconjunto fácil. CPU, energia e memória GPU total
não são medidos nesta rodada.

# AI Creative Director — MVP 0.3

Aprovado manualmente pelo usuário no Final Cut em 17/11/2026 para a montagem
3840×2880/4:3/25 fps, 20 s, com cortes, música e slow motion 50%.
Registro: [CREATIVE_DIRECTOR_VALIDATION.md](CREATIVE_DIRECTOR_VALIDATION.md).

## Contratos e fluxo

`director/schemas.py` contém CreativeBrief, BriefInterpretation, Candidate,
NarrativePlan, EditDecision e EditDecisionList v0.3.0. Relógios de fonte e timeline
são independentes e racionais; intervalos são semiabertos. `duration_frames` é
medido na timeline; `source_in_frame/out_frame` usam o frame rate da fonte.
A identidade de mídia é o SHA-256 e cada decisão referencia o segmento Analyzer.

1. Reutilizar ingestão e AnalysisReport do MVP 0.2. Preservar métricas e evidências.
2. Construir janelas limitadas dentro de cada segmento analisado (3/5/6 s conforme
   ritmo). Importar interpretações multimodais como camada separada, com sua origem.
3. Limitar o contexto a 18 candidatos com cobertura por fonte e diversidade
   temporal; todos os candidatos continuam no JSON. Não descartar um take por um
   único score. Não há embedding de similaridade ou identificação física de pessoas.
4. Modelo textual seleciona IDs, ordem, papéis, velocidade e justificativas.
   Conteúdo, qualidade técnica, componentes, confiança e ações são fornecidos ao
   planejador. Continuidade, redundância e enquadramentos são interpretações do
   modelo, não restrições fisicamente garantidas. Refinamento semântico de ações
   completas ainda exige revisão humana.
5. Motor determinístico completa capacidade insuficiente com candidatos distintos,
   privilegiando fontes ainda não usadas e duração disponível. Cada inclusão é
   explicitamente identificada como decisão do motor; nunca atribuída ao modelo.
   `model-narrative.json` preserva a proposta original e `narrative.json` o plano
   completado. O motor recusa capacidade total insuficiente.
6. Distribuir a duração exata. Ajustar apenas alguns cortes para onsets próximos
   (até 150 ms), sem obrigar sincronização de todos os cortes.
7. Decodificar frames adicionais nas entradas/saídas propostas, incluindo posições
   vizinhas a ±200 ms. Escolher limites por nitidez/extremos de luminância. Isto
   verifica frames exatos, mas não comprova fronteiras de ações ou qualidade estética.
8. Criar EDL validada, gerar XML pelo exportador original e aplicar o adaptador
   explícito de formato/retime/música. Validar DTD e equivalência XML/EDL.

## Briefing em linguagem natural

A tarefa `creative_brief` retorna uma proposta separada, com citações do texto
original para campos essenciais. Se faltarem campos, o resultado deve conter
`brief=null` e `missing_fields`; propostas completas sem citações são recusadas.
Não há execução automática do briefing extraído: revisar e salvar o objeto brief
em arquivo próprio antes de `build`. Citações existentes não comprovam toda a
interpretação; a revisão permanece necessária.

## Modelos e modos

`creative_direction` e `creative_brief` são contratos do ProcessingRouter.
O adapter llama-server implementa planejamento textual para os dois modelos locais
aprovados (Qwen3-VL 8B e Gemma 3 12B), sem escolher um vencedor. O uso real desta
montagem é registrado no relatório de validação; não implica equivalência entre
eles para planejamento. O runtime verifica hashes e exige sandbox local. Respostas
estruturalmente inválidas podem receber até duas correções no mesmo modelo; não
há troca automática de provedor. Respostas/erros privados ficam no workspace.

Configuração global e override por projeto reutilizam `ai/config.py`. LOCAL
bloqueia remoto e fallback; HYBRID/CLOUD podem rotear contratos textuais via API
Python e HTTPS existente, com consentimento de payload/destino. A CLI recusa
provedor remoto por não possuir UI de consentimento. Probe, áudio, refinamento,
preview, XML e validação continuam locais. Credenciais continuam no Keychain.
Nenhuma chamada remota foi feita nesta entrega.

## Música

FFmpeg aprovado decodifica mono PCM 8 kHz em memória, limitado a 15 minutos.
A biblioteca padrão calcula envelope RMS de 20 ms, novidade positiva em log-energia,
onsets, autocorrelação aproximada de tempo (60–180 BPM), janelas de 10 s e intensidade.
Não há librosa, nova instalação, separação de instrumentos ou entendimento musical
por IA. BPM pode ficar ausente; fase e ambiguidades de metade/dobro são possíveis.
`stable_tempo_supported` apenas indica consistência aproximada entre janelas.
Os pontos de corte usam alguns onsets, não uma grade presumida de BPM constante.

## Exportação e áudio

O arquivo `ave/core.py` permanece intacto. `director/export.py` ajusta o XML novo:
sequência de resolução customizada (sem inventar preset Apple), `adjust-conform`
fill central, cadência explícita e `timeMap` linear para velocidade 1/2. O caminho
atual admite fontes uniformes e frame rate igual ou dobro da timeline. Não há
speed ramp, optical flow, máscaras, tracking, efeitos complexos ou grading.

Clipes em velocidade normal mantêm o áudio original e todos os recursos multicanal.
Clipes a 50% recebem `srcEnable=video`: áudio de câmera não é desacelerado. Música
original é recurso conectado editável, com gain provisório -12 dB, sem ducking ou
normalização de loudness. Taxa 44,1 kHz da música é declarada sem converter a fonte;
Final Cut fará o conform de reprodução para o projeto 48 kHz.

Fontes 3840×2160 passam por crop central equivalente a 2880×2160 e upscale a
3840×2880. Há perda de enquadramento e ganho de pixels interpolados, não detalhe
nativo adicional. Não há tracking automático para reposicionar pessoas.

Fontes Apple consultadas:
[timeMap](https://developer.apple.com/documentation/professional-video-applications/timemap),
[frame sampling](https://developer.apple.com/documentation/professional-video-applications/frame-sampling)
e DTD oficial local `audit/FCPXMLv1_10.dtd`. A DTD não garante importação nem aparência.

## CLI

```sh
.venv/bin/python -m final_editor_pro.director.cli build \
  --brief workspace/director-0.3/brief.json \
  --reports workspace/director-0.3/analysis-01/analysis.json \
            workspace/director-0.3/analysis-02/analysis.json \
            workspace/director-0.3/analysis-03/analysis.json \
            workspace/director-0.3/analysis-04/analysis.json \
            workspace/director-0.3/analysis-05/analysis.json \
            workspace/director-0.3/analysis-06/analysis.json \
  --proposals workspace/evaluation/annotation-proposals-v1 \
  --output workspace/director-0.3/new-edit
```

O output deve ser novo. `--global-config` e `--project-config` são opcionais.
Para trocar modelo, alterar model_id no briefing e configurar a rota coerente.
`parse-brief --text-file ... --model ... --output ...` cria somente uma proposta.
Schemas JSON publicados em `docs/director-schemas/`.

Cada artefato de montagem tem hash no journal. `undo_run` (API Python em pipeline)
estaciona apenas artefatos gerados intactos em `undone/`, preservando o journal e
as fontes. Recusa arquivos alterados/desconhecidos. Não é uma transação contra falha
de energia nem apaga dados privados automaticamente.

Preview opcional: `director.preview.preview(edl, nova_pasta)` produz 512×384/25 fps.
É proxy de revisão com música; áudio da câmera é omitido **somente no preview**.
A timeline XML mantém a política original por decisão. O preview não aplica LUT ou
normalização de Log/HDR; não é render final. A pasta de preview possui journal próprio.

# AI Video Analyzer — uso e contratos do MVP 0.2

O Analyzer escreve somente relatórios/caches em pastas novas; não altera fontes,
planos de edição ou FCPXML. Não abre o Final Cut. O exportador do MVP 0.1 permanece
inalterado. Relatório de demonstração real: [ANALYZER_VALIDATION.md](ANALYZER_VALIDATION.md).

## Pipeline e capacidades reais

- Ingestão reutiliza probe/metadata existentes para MP4/MOV/MXF compatíveis.
  Preserva codec, dimensões, fps racional, duração e áudio. Orientação rotacionada,
  relógios ambíguos e formatos não suportados falham em vez de serem normalizados
  sem autorização. Áudio nesta versão é metadata: não há transcrição/análise sonora.
- FFmpeg decodifica a fonte local uma vez por extração e entrega RGB reduzido.
  Seleção usa número de frame, não fps que duplica imagens. PNG é codificado pela
  biblioteca padrão. Não se gera um vídeo proxy: as imagens são proxies de análise.
- Amostragem adapta o stride à frequência pedida, duração e orçamento máximo.
  São escolhidos frames distribuídos dentro de cada segmento para inferência.
  Ainda não há refinamento automático frame-exato em torno de cortes.
- Detector exige diferença de pixels e histograma persistente, com duração mínima.
  Uma oscilação/flash que volta ao histograma anterior não cria automaticamente
  uma cena. Pans bruscos, mudanças persistentes de luz e composições semelhantes
  ainda podem causar falsos positivos/negativos. Reporta incerteza em frames.
- Métricas: luminância, extremos, variância do Laplaciano, diferença de frames e
  variação dessa diferença como proxy de instabilidade. Não há optical flow,
  separação física confiável de movimento de câmera/objeto, tracking ou grading.
- Semântica: múltiplos frames ordenados, descrição/objetos/pessoas/contexto,
  ações aparentes, enquadramento, atmosfera, incertezas e oportunidades hipotéticas.
  Ações precisam citar pelo menos dois frames enviados. Evidência é validação
  de referência, não prova de que toda afirmação do modelo está correta.
- Scores têm seis componentes e motivos. Relevância/ação/narrativa/transição
  vêm de avaliações subjetivas do modelo ou ficam desconhecidas; confiança é
  autodeclarada e não calibrada. Nunca descartar take com base nesses indicadores.

## Execução determinística, sem IA e offline

Da raiz do projeto, com FFmpeg/ffprobe aprovados já disponíveis:

```sh
.venv/bin/python -m final_editor_pro.analysis.cli \
  workspace/test_media/A_0018C480A261031_164803HW_CANON.MXF \
  --output workspace/analysis-new-run \
  --analysis-config config/analysis.example.json
```

Saídas: analysis.json, probe.json quando houve ingestão nova, operations.jsonl.
A pasta de saída não pode existir. Cache padrão: workspace/analysis-cache.
Modelos não são baixados e providers não são construídos quando semantic=false.

Configuração de análise persistente em JSON (defaults em --analysis-config,
overrides em --project-analysis-config; score_weights é mesclado por componente): sample_fps racional (até 10), max_frames,
proxy_width, duração mínima, limiares, max_semantic_frames, perfil e semantic.
score_weights permite overrides por componente; pesos desconhecidos, negativos,
NaN ou todos zero são recusados. Perfis: restaurant, wedding, event, travel, social.

Configuração de processamento reutiliza os arquivos globais e overrides por
projeto existentes (--global-config e --project-config). O novo task ID é
`temporal_visual_analysis`. LOCAL é o padrão, sem fallback de nuvem.

## Modelo local real

O runtime/modelo foram aprovados pelo usuário nesta sessão; o código não instala
ou baixa automaticamente. Exemplos de provider estão desativados por padrão em
config/analysis-local.example.json. Para habilitar uma instância previamente
preparada, use cópia local ignorada dentro de workspace/.

Adapter Ollama nativo existe, mas o comando ollama serve tenta criar uma identidade
em ~/.ollama. Ele NÃO foi iniciado. A execução demonstrada usa llama-server que
vem no arquivo oficial Ollama v0.40.16, com o mesmo modelo/projetor aprovados.
Servidor dedicado em 127.0.0.1:11435, sem GUI, sem cloud, sem autenticação remota,
sem ferramentas, com sandbox negando conexões externas e escrita fora da pasta
runtime em temp/. Comunicação loopback mantém os dados no Mac.

O manifest de runtime contém paths e hashes de binário, modelo, projetor e libs,
sem credenciais. Preparação desta máquina: workspace/approved-local-runtime.json.
O helper local_server verifica esses hashes, recusa porta já usada, inicia o
servidor com ambiente limpo e o encerra em finally, inclusive se houver falha.
Não herda tokens/proxies do shell e não reaproveita outro daemon do usuário.

Benchmark completo com carregamento e encerramento gerenciados:

```sh
.venv/bin/python -m final_editor_pro.analysis.benchmark \
  workspace/test_media/A_0018C480A261031_164803HW_CANON.MXF \
  --output workspace/benchmark-new-run \
  --runtime-manifest workspace/approved-local-runtime.json \
  --global-config workspace/analysis-local-validation.json \
  --analysis-config workspace/analysis-semantic-validation.json
```

As duas últimas configurações são cópias locais habilitadas para a demonstração,
não segredos nem defaults versionados. Um output parcial retorna erro no CLI e
não é certificado/reutilizado como sucesso. Não há retry automático para nuvem.

## HYBRID/CLOUD e privacidade

O roteador e CloudProvider existentes aceitam o novo contrato temporal; o adaptador
HTTPS inclui imagens reais e timestamps no payload aprovado. Nenhuma integração
remota foi executada nesta entrega. O CLI do Analyzer bloqueia providers remotos
até existir uma interface interativa de consentimento; não há flag de autoaprovação.

A API Python permite o fluxo explícito por segmento: primeiro análise determinística,
construir TemporalInput via temporal_request, revisar router.preview_upload,
registrar confirmação humana e passar os grants por segment_id no argumento consent.
Mudança de bytes/modelo/destino invalida o grant. Nada é enviado automaticamente
por escolher HYBRID ou CLOUD. A semântica de consentimento segue AI_PROCESSING.md.

## Cache, integridade e benchmark

Cache de frames: hash completo da fonte + caminho + parâmetros de amostragem +
hashes de ferramentas + versão de pipeline. Scoring/modelo diferentes podem
reutilizar esses frames. Cada PNG é verificado por SHA-256 antes do reuso.
Cache de relatório inclui toda configuração e identidade do provider/modelo;
sidecar SHA detecta corrupção do JSON. Cache corrompido falha explicitamente;
frames inválidos são preservados como .invalid e reextraídos. Não aceitar
relatório parcial como cache completo. Não há lock para execução concorrente:
use um worker por cache nesta versão; falhas de concorrência não são certificadas.

SHA-256 e mtime das fontes são conferidos ao terminar. Relatórios, proxies e
modelos ficam em workspace/, ignorado pelo Git. Journals não registram imagens,
prompts ou descrições; contêm status, tarefa, provider/modelo, hashes e tempos.

Tempos medidos: análise por minuto da amostra, inferência e startup separado.
RSS do processo e filhos é high-water do macOS; RSS do servidor é amostrado a
cada 250 ms. Não representam memória GPU/unificada total. Cache quente registra
zero chamadas de inferência/frames extraídos, não repete os contadores frios.

## Schemas e interface do futuro Director

Schemas JSON exportados em docs/analysis-schemas/ para MediaAsset, SceneSegment,
TechnicalMetrics, VisualAnalysis, ShotScore, TransitionOpportunity e AnalysisReport.
Contrato central: AnalysisReport.schema_version=0.2.0, pipeline_version=analyzer-2.

Intervalos são [start_frame,end_frame), inteiros, com timestamps em segundos
racionais como strings. Relatório valida cobertura contígua da fonte, timestamps,
referências de evidência e intervalos. source_start guarda origem de timecode;
intervalos de análise são relativos ao início do vídeo, sem confundir ambos.
Cada segmento tem asset_id, amostras, métricas, score, semântica opcional,
provider/modelo e status. Resultados insuficientes ficam null/failed ou com
incerteza explícita. O campo metadata mantém o manifesto de ingestão existente.

O Director 0.3 deverá ler AnalysisReport.model_validate_json, escolher intervalos
com justificativas e propor CreativePlan separado. O Analyzer não chama apply_plan
nem o exportador. Nenhuma oportunidade sugerida executa máscara, transição ou VFX.

Exemplo real sanitizado: examples/analysis_report.real-sanitized.json. Ele remove
prefixos absolutos da máquina; não inclui imagens ou modelo e não é fixture para
fingir uma inferência real. Os testes usam fixtures sintéticos separados.

# MVP 0.2 — relatório técnico de validação

Data: 16/11/2026, Australia/Brisbane. Base anterior: a1e457e.
Status: pipeline implementado e demonstrado com análise multimodal local real.
Não é validação de qualidade editorial geral nem garantia de ausência de alucinação.
Sem commit, push, publicação ou alterações em bibliotecas Final Cut.

## Entrega e evidência real

Módulos novos em final_editor_pro/analysis/: schemas, media, metrics, pipeline,
ollama (adapters locais), runtime (sandbox/lifecycle), CLI e benchmark.
Configurações persistentes, contratos e roteamento reaproveitam a base.
FCPXML Exporter e Timeline Engine não foram modificados nesta etapa.

Modelo: Qwen3-VL 4B Instruct Q4_K_M, manifesto aprovado
84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318.
Runtime: llama-server distribuído no Ollama standalone oficial v0.40.16.
Pesos/projetor verificados, servidor em loopback com contexto 8192 e um slot,
sandbox negando egress externo e escrita nas mídias. Preparação e decisões em
[ANALYZER_DEPENDENCY_AUDIT.md](ANALYZER_DEPENDENCY_AUDIT.md).

Amostra: A_0018C480A261031_164803HW_CANON.MXF, **192 frames/3,84 s**, 3840×2160/50 fps,
quatro streams de áudio mono a 48 kHz. Permissões/caminhos foram verificados;
a fonte foi somente lida. Amostragem: oito proxies PNG 320×180, quatro frames
cronológicos submetidos à inferência. O pipeline identificou um segmento nessa amostra.

O modelo descreveu duas pessoas próximas, vestimentas escuras e ambiente externo,
indicou enquadramento/movimento aparente e incerteza sobre gestos/posição das mãos.
As ações foram vinculadas a pelo menos dois frames. O resultado é interpretação
do modelo, não anotação humana certificada. Scores narrativos/emocionais são
hipóteses subjetivas, nunca fatos sobre a relação ou intenção das pessoas.

Relatório real completo: workspace/analyzer-benchmark-001/cold/analysis.json.
Exemplo sanitizado e validável: examples/analysis_report.real-sanitized.json.
Sem vídeos, imagens ou pesos versionados; nenhuma mídia foi enviada a serviço externo.

## Benchmark medido

Fonte: workspace/analyzer-benchmark-001/benchmark.json. Mesmo clipe e processo;
primeira execução com cache do Analyzer vazio e segunda com cache preenchido.
Caches de arquivos do sistema operacional podem estar quentes. Resultados não
são média de várias rodadas nem extrapolação comprovada para vídeos longos.

| Medida | Execução fria do Analyzer | Cache quente |
|---|---:|---:|
| Tempo de análise | 5,963 s | 0,0447 s |
| Tempo de inferência | 3,710 s | 0 s |
| Chamadas de inferência | 1 | 0 |
| Frames extraídos | 8 | 0 |
| Frames enviados ao modelo | 4 | 0 |
| Tempo normalizado por minuto da amostra | 93,17 s/min | 0,698 s/min |

Preparação do runtime: **5,202 s**, incluindo hashes e carregamento, fora do tempo
de análise. O ganho observado com cache foi aproximadamente 133× nessa amostra;
nenhuma nova inferência ocorreu no cache quente. O hashing da fonte ainda é feito.

RSS máximo observado do servidor: **4.787.306.496 bytes (~4,46 GiB)**, amostrado
por ps a cada 250 ms. RSS high-water do processo Python: 50.118.656 bytes na
execução fria; filhos: 951.713.792 bytes. Esses valores são medições por processo,
não somar como se fossem um pico simultâneo; não medem memória GPU/unificada
total nem garantem ausência de picos entre amostras. Hardware é o informado pelo
usuário, sem benchmark comparativo com outras máquinas.

O servidor foi encerrado pelo context manager após as duas rodadas. A prova
local de rede negada está em temp/analyzer-audit/network-deny-proof.json.

## Testes

Suíte preservada: 46 testes do MVP 0.1. Suíte atual: **59 testes aprovados**, sem
chamadas remotas de IA. Novos testes cobrem métricas sintéticas, mudança persistente
versus flash/movimento, orçamento temporal, schemas, grounding, erros/truncamento,
seleção LOCAL sem transporte remoto, cache/invalidação/corrupção e sandbox manifesto.
Um teste de integração gera vídeo sintético de duas cenas com FFmpeg real e valida
extração/segmentação sem depender de footage privado. Nenhum modelo real é invocado
nos testes unitários; a inferência descrita acima é uma execução separada real.

```sh
TMPDIR="$PWD/temp/analyzer-audit" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/python -m pytest -q --basetemp=temp/analyzer-audit/pytest-final
```

Hashes/tamanhos/mtime dos seis originais permanecem iguais ao manifesto inicial.
Artefatos de validação anteriores, bundle de referência e FCPXML corrigido também
preservados. Evidência: temp/analyzer-audit/integrity-final.json.

## Falhas encontradas e tratamento

- Runtime Ollama tentaria criar identidade fora do projeto: evitado por usar o
  servidor embutido, sem iniciar o daemon Ollama.
- Primeiro perfil de sandbox foi recusado por sintaxe: corrigido mantendo deny.
- Primeira inferência repetiu texto e atingiu o limite de tokens. Marcada partial,
  nunca promovida a sucesso nem reutilizada como cache. O prompt foi tornado
  conciso e a resposta truncada é recusada explicitamente.
- Resposta seguinte citou apenas um frame para ações. O contrato foi reforçado
  para exigir duas evidências e restringir índices aos frames submetidos.
- Contadores de cache quente foram separados de frames disponíveis/custos frios;
  relatório quente não reapresenta tempo de inferência como trabalho novo.

## Limitações e riscos remanescentes

Detector é aproximado e dependente da amostragem; flashes persistentes e pans
podem confundir. Não há refinamento frame-exato, optical flow, transcrição,
áudio semântico, estabilização, máscaras, tracking ou execução de VFX.
Nitidez/luminância são medidas no proxy, sem normalização Canon Log/HDR.
Ações sutis ou rápidas podem desaparecer com quatro frames; não há prova de
compreensão de todo o vídeo. Uma referência de evidência válida não valida a
verdade da afirmação. O modelo ainda pode ser impreciso no enquadramento ou nos
movimentos; avaliação humana e um conjunto anotado são próximos gates.

O scoring é explicitamente subjetivo/heurístico e não descarta takes. Narrative
potential não substitui briefing. Semântica remota não foi executada; a API está
preparada para consentimento por segmento, e o CLI remoto continua bloqueado.
Cache é de um worker por diretório, sem transação/lock para concorrência robusta.
A instalação não é distribuída como produto assinado; artefatos grandes ficam
locais e exigem preparação aprovada em outra máquina.

## Próximo MVP 0.3

AI Creative Director deve consumir relatórios, briefing e restrições de duração,
produzir CreativePlan com rastreabilidade para segmentos e solicitar revisão antes
 de gerar nova timeline. Priorizar avaliação humana de seleção/ritmo e limites
 determinísticos. Adicionar áudio/transcrição/batidas somente com auditoria e
 validação específicas. Oportunidades de efeitos seguem como hipóteses até testes
 reais de render e round-trip no editor.

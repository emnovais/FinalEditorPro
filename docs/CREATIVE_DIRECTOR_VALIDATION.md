# MVP 0.3 — validação integrada real

16/11/2026, macOS/Apple Silicon. Estado: montagem real gerada e validada
estruturalmente. **MVP 0.3 aprovado manualmente pelo usuário em 17/11/2026**.
A aprovação confirma as funcionalidades abaixo; não representa uma avaliação
estética quantitativa nem validação universal de outros formatos/mídias.
Nenhum commit/push automático, instalação, upload ou alteração de biblioteca.
Nenhuma nova rodada de benchmark/revisão cega.

## Resultado

Briefing confirmado pelo usuário: 20 segundos, saída 3840×2880/4:3, crop central e
upscale, timeline 25 fps, ritmo equilibrado, música local e slow motion em takes
emocionantes. Objetivo/estilo romântico proposto para essa montagem experimental.

Seis MXFs reais 3840×2160/50 fps foram reanalisados deterministicamente, reutilizando
a ingestão e o Analyzer. As interpretações já geradas por Qwen3-VL 8B e Gemma 3 12B
foram consumidas separadamente das evidências e das descrições humanas. Planejamento
textual real realizado com Qwen3-VL 8B, sem cloud. Gemma permanece selecionável, mas
não foi exercitado como planejador textual nesta execução; não se afirma equivalência.

A montagem final tem oito segmentos e exatamente 500 frames a 25 fps = 20 s.
Um trecho usa velocidade 1/2. O modelo propôs cinco escolhas; o motor determinístico
acrescentou três candidatos distintos para completar capacidade/duração. Essas
inclusões possuem justificativa própria, sem atribuí-las ao modelo. A proposta
original e a completada estão preservadas em JSON.

Música escolhida: Alon Peretz — Peasants Courtyard (WAV estéreo/44,1 kHz), por estar
entre os arquivos autorizados e cobrir a duração com fonte PCM. Não foi declarada
compatibilidade de atmosfera musical por IA. A heurística estimou 66,67 BPM e
`stable_tempo_supported=false`; não é um BPM validado. Um ponto de corte já coincidia
com onset próximo; os demais não foram forçados à grade. Mix provisório a -12 dB.

Os pontos de entrada/saída receberam inspeção adicional de frames e limites locais.
Um alerta do próprio modelo menciona possível desfoque em um candidato; a afirmação
de que isso não prejudica a narrativa **não foi verificada** e precisa de revisão.
Todos os oito segmentos ficaram com confiança combinada ≤0,6 (não calibrada).
Não se declara que a montagem ficou visualmente boa ou que as ações estão completas.

## Artefatos locais para revisão

Pasta `workspace/director-0.3/` (ignorada pelo Git):

- `final/timeline.fcpxml`: arquivo final para importação manual.
- `final/edl.json`: decisões versionadas, racionais, por fonte/timeline/velocidade.
- `final/review.html`: ordem, justificativas, relações com briefing, áudio e alertas.
- `preview-001/preview-music-only.mp4`: proxy 512×384, 25 fps, 500 frames.
  **O preview usa apenas música; o áudio da câmera permanece no XML nos takes normais.**
- `edit-005/`: execução real completa, relatórios musicais, candidatos, modelo,
  narrativa completada, refinamento por frames, journal e validação inicial.
- `final-validation.json`: verificações finais e hash do XML.
- `tests-final.txt`: resultado dos testes.

O XML final foi republicado deterministicamente a partir da EDL existente para
usar a duração racional original do WAV (1187363/11025 s), em vez de arredondar a
duração aos samples do proxy 8 kHz. Nenhum corte foi alterado e nenhuma nova chamada
a modelo foi feita nessa republicação. Relógios do áudio decodificado e original
estão separados. O diretório inicial e seu XML foram preservados.

SHA-256 do XML final:
`34f01d700674e498351f019a53074a7d36293ed2f7ec568f782230dcb4ac6a4d`.

## Verificações executadas

- **93 testes automatizados aprovados**, incluindo os 76 anteriores.
- Testes offline bloqueiam sockets/DNS. Cobertura nova: briefing/ausências,
  geometria, relógios racionais, seleção diversa, duração, onsets, silêncio,
  narrativa, limites de mídia, retime, source timecode, áudio multicanal,
  música conectada, XML/EDL, ausência/alteração de fonte, falha/correção limitada
  de modelo, política LOCAL e consentimento remoto, reversão de artefatos.
- XML final validado com `xmllint --nonet` e DTD oficial Apple 1.10.
- Referências de mídia/recursos, offsets, durações, timeMap e origem do timecode
  comparados com EDL. O XML reexportado pela versão final coincide byte a byte.
- Hashes de todos os vídeos e da música preservados. Verificação de tamanho/mtime
  durante o pipeline dos vídeos e análise musical; hashes rechecados após preview.
- Preview verificado por ffprobe: 512×384, 25 fps, exatamente 500 frames.
- Runtime encerrado; endpoint local de health deixou de responder.
- `ave/core.py` sem alterações; caminho anterior e testes preservados.
- Nenhuma dependência nova; fontes, modelos e derivados permanecem ignorados.

## Falhas e ajustes encontrados

1. Primeira entrada com 32 candidatos recebeu HTTP 400 do runtime. O contexto foi
   limitado a 18 por cobertura de fontes e diversidade temporal, não só score.
2. Planos com capacidade insuficiente e papéis de abertura/encerramento inválidos
   foram rejeitados antes da exportação. Tentativas também omitiram confiança.
3. A aritmética de duração foi separada do ranking criativo: inclusão determinística
   explícita de candidatos, distribuição racional e validação estrita da EDL.
4. Correção limitada de schema/papéis usa o mesmo modelo, no máximo duas tentativas
   adicionais. A execução aceita em `edit-005` usou uma resposta aceita, sem correções.
5. Duração do áudio original foi separada da duração resampleada para análise.

Execuções rejeitadas `edit-001` a `edit-004` preservam diagnósticos e não são a
entrega para importação. Não houve fallback, alteração de origem ou instalação.

## Importação manual

1. Abra/crie uma biblioteca **de testes separada** no Final Cut. Não use produção.
2. Escolha File → Import → XML e selecione `final/timeline.fcpxml`.
3. Prefira manter mídia no local, sem mover os originais.
4. Confirme projeto 3840×2880/25 fps, duração 20 s, oito segmentos e música editável.
5. Confira crop central em cada take, sobretudo pessoas próximas às bordas;
   ajuste manualmente a posição se necessário.
6. Confira o trecho lento: 50%, sequência suave, entrada/saída corretas e áudio de
   câmera desativado somente nesse trecho. Nos demais, confira fontes/canais originais.
7. Escute o mix com música; -12 dB não é uma mixagem final. Revise desfoque,
   continuidade, repetição e se as ações ficaram completas.
8. Registre qualquer aviso de importação e, se possível, exporte um FCPXML de
   round-trip em nova pasta dentro do workspace para comparação.

## Aprovação manual — 17/11/2026 (Australia/Brisbane)

O usuário confirmou no Final Cut Pro:

- Importação bem-sucedida da timeline.
- Cortes funcionando corretamente.
- Slow motion de 50% funcionando.
- Música adicionada corretamente.
- Duração final de 20 segundos.
- Resolução 3840×2880, proporção 4:3 e timeline 25 fps respeitadas.

O MVP 0.3 está aprovado para esta montagem. A validação foi realizada pelo usuário,
sem automação da interface. Não foram declaradas novas verificações de round-trip,
qualidade estética, todos os canais de áudio ou outros modelos/formatos.
O usuário autorizou o commit local de conclusão; push exige autorização separada.
Os artefatos locais originais preservam o estado histórico da geração (pending);
este registro documenta a aprovação posterior sem reescrever esses artefatos.

Verificação de encerramento em 17/11/2026: 93 testes aprovados novamente;
`git diff --check` e revisão do diff preparado sem erros de whitespace.
Índice Git e `.gitignore` conferidos: nenhuma mídia, render, cache, modelo,
credencial ou arquivo temporário identificado entre os arquivos a versionar;
nenhum arquivo ignorado já rastreado. `.gitignore`, `.github/` e `.editorconfig`
continuam permitidos. Não foi necessária remoção de arquivos do índice.

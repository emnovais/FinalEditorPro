# MVP 0.4 — validação local e comparação

17/11/2026 (Australia/Brisbane). Estado: nova montagem real pronta para revisão.
**Importação e round-trip do MVP 0.4 ainda não foram validados no Final Cut Pro.**
A aprovação manual do MVP 0.3 não foi transferida para a versão nova.

Base `165e2cb`, `main` preservada. Branch `develop/mvp-0.4-intelligent-editing`.
Sem commit/push, downloads, instalações, upload de mídias ou alteração de bibliotecas.
Plano: [MVP_0_4_PLAN.md](MVP_0_4_PLAN.md).
Arquitetura/uso: [INTELLIGENT_EDITING.md](INTELLIGENT_EDITING.md).

## Execução real

- Mesmos seis vídeos autorizados; fontes 3840×2160/50 fps e WAV original.
- Gemma 3 12B realizou planejamento narrativo pelo pipeline existente, com uma
  resposta aceita na primeira tentativa. Runtime aprovado e sandbox restrito a
  loopback. Não foi benchmark nem comparação para declarar vencedor. Qwen3-VL 8B
  continua disponível; o MVP 0.3 aprovado é a referência anterior produzida com ele.
- A entrada para refinamento é a nova montagem do Gemma, com EDL executável schema
  0.3. O pacote 0.4 guarda a versão executável e as novas decisões separadamente.
- Frames adicionais a aproximadamente 10 fps para movimento/continuidade;
  inspeção dos frames exatos nas bordas. Hints semânticos anteriores a 1 fps são
  candidatos, não ground truth temporal. A validação final das sementes de eventos
  usou caches reais e confirmou os mesmos cortes, sem nova chamada a modelo.
- Vision nativo, helper Swift próprio revisado, assinatura do compilador Apple
  verificada; nenhuma dependência instalada. Rede negada durante detecção. Foram
  obtidas 159 observações a 2 fps; três caixas fora do frame foram rejeitadas.
- Reframing estático sustentado por detecções em seis segmentos. Três segmentos
  mantêm crop central e alerta, por evidência insuficiente/inconsistente. Não há
  tracking de identidade nem inferência de direção de olhar.

## Timeline e preview

Nova timeline: **500 frames, 20 segundos, nove segmentos, 3840×2880, 4:3, 25 fps**.
Um segmento permanece em 50% de velocidade; áudio de câmera desativado nesse
segmento, preservado nos demais. Música original conectada e editável.

A saída adiciona transformações estáticas de posição e envelopes de ganho/fade.
O bound conservador dos picos levou a ganhos de aproximadamente -14,52 dB para
originais e -24,52 dB para música. Esses valores são mix inicial de segurança, não
loudness final. O bound calculado foi -3 dBFS; o preview completo teve pico de
amostra medido em **-14,626538 dBFS**. Não houve clipping de amostra detectado nesse
preview; não se afirma true peak ou equivalência de pan/roteamento no Final Cut.

Preview: 512×384/25 fps, 500 frames. Desta vez inclui os streams originais declarados,
downmixados para estéreo, e música com os envelopes. O preview antigo do 0.3 contém
apenas música; não usar a diferença de áudio desses proxies como avaliação cega.
Sem LUT/normalização Log-HDR ou afirmação de qualidade estética final.

## Comparação mensurada

Todos os indicadores abaixo usam as mesmas observações/eventos locais. Compatibilidade
é um proxy de fonte antes do crop final, não uma métrica perceptual da renderização.

| Indicador | MVP 0.3 aprovado (Qwen) | Plano Gemma antes do refinamento | MVP 0.4 final |
|---|---:|---:|---:|
| Compatibilidade visual média (0–1, maior melhor) | 0,791661 | 0,782130 | 0,823315 |
| Distância média de corte a evento musical (s, menor melhor) | 0,142857 | 0,027500 | 0,060000 |
| Duração da timeline (s) | 20 | 20 | 20 |
| Segmentos | 8 | 9 | 9 |

A continuidade melhora sob a métrica implementada tanto contra a entrada Gemma
quanto contra a referência 0.3. O alinhamento musical melhora contra o 0.3, mas
piora contra a entrada Gemma: a reordenação priorizou continuidade/narrativa e nem
todas as fronteiras podem ser alinhadas dentro da tolerância. Este trade-off é
explícito; não se afirma melhoria em todos os eixos ou superioridade de modelo.

No refinamento local da entrada, o custo agregado da estratégia de fronteiras
passou de 3,400485 para 0,235025. É a função interna de movimento/qualidade/deslocamento
sobre as mesmas durações e janelas de busca, não erro de timestamp contra referência
humana. A precisão semântica de ações completas continua pendente de revisão.

A primeira política de música ajustava fronteiras alternadas e resultou em 0,08 s
de distância média. A política final prioriza maior benefício, ajusta no máximo
metade das fronteiras e resultou em 0,06 s. Não força todos os cortes às batidas.

## Arquivos de revisão locais

Em `workspace/director-0.4/` (ignorado pelo Git):

- `final/timeline.fcpxml`: nova timeline para importação.
- `final/edl.json`: pacote versionado com evidências/decisões/proveniência.
- `final/review.html`: comparação visual dos previews, decisões, crop e alertas.
- `final/comparison.json`: métricas completas por par e referências da comparação.
- `final/validation.json`: validação estrutural e estado manual pendente.
- `preview-002/preview.mp4`: preview final com mix; journal contém pico medido.
- `gemma-planning/`: planejamento real e montagem anterior ao refinamento.
- `subjects-prepared/`: saída da CLI pública de preparação, verificada com caches
  das inferências Vision reais; `subjects-v2.json` é a evidência usada na montagem.
- `roundtrip-tool-selftest.json`: teste da ferramenta consigo mesma, **não round-trip**.
- `final-validation.json`: evidências adicionais de integridade/execução.

SHA-256 da timeline final:
`68a871a9376d3e4bc27cb293545928d5c9f258de6dd0e373217ee235849c02f4`.

O XML final é idêntico ao de `edit-003`: republicação determinística com diagnóstico
adicional de sementes de eventos e relatório visual. Não houve mudança de corte,
transformação ou mix nessa republicação. O preview corresponde a esse XML.
`edit-001` reteve falha anterior ao XML; `edit-002`/`preview-001` são intermediários.

## Testes e segurança

**120 testes aprovados**, incluindo os 93 anteriores e 27 verificações novas.
Testes bloqueiam sockets/DNS. Cobertura nova: continuidade/componentes/opt-out,
quatro aspectos, segurança de crop, detecções inconsistentes, quatro estratégias
temporais, sementes de eventos, música/pausas/seções, duração e limites de fonte,
headroom, ducking, fades, exportação DTD, curvas/transformações versus pacote,
round-trip canônico e diferenças curtas de fade, falhas/mídia ausente, cache
corrompido e reversão de artefatos. Teste adicional real de FFmpeg com WAV sintético
verificou atenuação e ducking, preservando o arquivo-fonte.

Validação integrada real: DTD oficial Apple 1.10 (`xmllint --nonet`), recursos,
times, timeMap, transformações e envelopes comparados ao pacote; reexportação
idêntica byte a byte. Fontes preservadas por SHA-256; tamanho/mtime verificados
nos pipelines. XML aprovado do MVP 0.3 preservado com hash anterior. Runtime do
modelo encerrado. Exportadores `ave/core.py` e `director/export.py` sem alterações.

Falhas encontradas e tratadas:
- `codesign` não conseguiu avaliar confiança dentro do sandbox; checagem externa
  somente leitura passou. Nenhum download/instalação foi usado para contornar isso.
- Caixas Vision fora do frame foram rejeitadas, sem coordenadas inventadas.
- Primeiros testes pegaram o sufixo `s` em timestamps XML de volume antes da
  conversão racional. Corrigido; testes e XML real passaram depois.
- Música após reordenação tem trade-off mensurado, mantido explícito no relatório.

## Revisão e round-trip manual necessários

1. Importe `final/timeline.fcpxml` em **biblioteca de teste separada**.
2. Confirme 20 s/25 fps, 3840×2880/4:3, nove segmentos, música e slow motion 50%.
3. Compare o preview e a timeline; confira entradas/saídas, gestos completos,
   repetição e deslocamentos estáticos de enquadramento. Revise os três fallbacks.
4. Escute o áudio original/música e os fades. Ajuste o mix se estiver baixo ou se
   houver instruções de set indesejadas. Ducking não foi habilitado sem prioridade
   explícita; não há reconhecimento automático de diálogo.
5. Exporte pelo próprio Final Cut para uma pasta nova, sugerida:
   `workspace/director-0.4/roundtrip/`. Preserve `.fcpxml` ou bundle `.fcpxmld`.
6. Informe o caminho para executar a CLI de comparação descrita na documentação.
   Ela verifica duração, ordem, curvas de fonte/velocidade, transformações, música
   e ganho. Estruturas nativas não suportadas exigem comparação manual adicional.

Sem automação da interface. Aguardar avaliação do usuário e round-trip antes de
considerar o marco aprovado. Nenhum commit ou push sem nova autorização.

## Retorno posterior do usuário

O arquivo reexportado recebido corresponde ao MVP 0.3 (oito segmentos), confirmado
pelo usuário. O MVP 0.4 foi importado com avisos de keyframes de volume; o importador
ignorou os envelopes. Causa e correção, diferenças do round-trip e revisão sem
reutilização de takes: [FCPXML_AUDIO_AND_TAKE_REUSE_FIX.md](FCPXML_AUDIO_AND_TAKE_REUSE_FIX.md).
A versão nova aguarda importação e avaliação; não há aprovação manual do MVP 0.4.

## Validação da revisão de seis takes

O usuário confirmou importação sem erros, melhora visual, cortes musicais e
keyframes de áudio/música perceptíveis. Reportou espera repetida ao iniciar em
zero. O novo round-trip preserva cortes e envelopes dentro das tolerâncias
documentadas; desempenho inicial continua pendente. Investigação e testes
controlados: [FCPXML_STARTUP_INVESTIGATION.md](FCPXML_STARTUP_INVESTIGATION.md).

## Reprodução inicial resolvida

O usuário validou o teste A com várias reproduções desde zero, sem a espera
reportada. A reconciliação BWF foi incorporada ao fluxo e a versão consolidada
coincide com esse teste, exceto pelo nome do projeto. Detalhes e evidências em
[FCPXML_STARTUP_INVESTIGATION.md](FCPXML_STARTUP_INVESTIGATION.md). A importação sem
erros, a melhora visual reportada, os keyframes e a resolução dessa espera têm
validação manual recebida. Commit e push continuam sem autorização.

## Registro e publicação autorizados

Em 17/11/2026, o usuário autorizou commit e push das alterações acumuladas.
Verificação final: 133 testes locais aprovados; índices e ignores conferidos.
Publicação na branch de desenvolvimento, preservando a main. Testes, mídias,
modelos, renders, caches e dados privados do workspace permanecem fora do commit.

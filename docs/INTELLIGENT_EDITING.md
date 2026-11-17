# MVP 0.4 — Intelligent Editing & Continuity

Estado: revisão de seis takes importada sem erros e considerada melhor pelo
usuário. Keyframes preservados; teste A resolveu a espera inicial e foi incorporado.
Detalhes e limites no relatório de validação e na investigação de startup. Base estável preservada em `main` no commit `165e2cb`; branch
`develop/mvp-0.4-intelligent-editing`. Sem commit/push autorizado.

## Arquitetura e contratos

`final_editor_pro/editing/` é uma camada sobre o Director. Recebe uma EDL válida,
observações locais e preferências; mantém fontes e decisões originais intactas.
`EditingPackage` v0.4.0 contém `base_edl` (contrato executável v0.3), configurações,
permutação, refinamentos, reframing, continuidade, música, mix e proveniência.
Não é um arquivo aceito diretamente pela CLI antiga do Director. Usar a CLI nova
para refinar/exportar. Contratos anteriores e o exportador estável não mudaram.

Schemas Pydantic em `editing/schemas.py`, JSON em `docs/editing-schemas/`:
EditingSettings, SubjectBox, SubjectObservation, FrameFeature, ReframeDecision,
AudioEnvelope, MixPlan e EditingPackage. Validações recusam intervalos inválidos,
crops fora da imagem, razão incompatível, transformação divergente, evidências
fora do take, settings incompletos e envelopes fora da duração. O pacote usa
relógios racionais e preserva clocks distintos de fonte/timeline.

As camadas continuam separadas: pixels/caixas/eventos observados → interpretações
semânticas do Analyzer → ranking/narrativa do Director → refinamento determinístico
→ decisões executáveis → XML. Um modelo não confirma o próprio resultado como
referência humana. O modo LOCAL e a ausência de fallback permanecem no roteador.
Não houve chamadas remotas nesta entrega; inferência usa runtimes/modelos aprovados.

## Continuidade

Features locais: luminância, histograma, thumbnail 16×9, nitidez, diferença
interframe e deslocamento global aparente por busca limitada de pixels. Quando há
caixas válidas: centro/área da união de pessoas, como proxies de posição/escala.
Não há separação física de câmera/objeto, optical flow completo, identidade,
direção de olhar, profundidade ou classificação garantida de enquadramentos.

Compatibilidade tem componentes e pesos explícitos: luma, histograma, composição,
direção aparente quando confiável, posição/escala de pessoas quando disponíveis,
repetição de intervalos e preferência suave de cronologia. São proxies de fonte,
não métricas perceptuais da imagem final cropada ou um julgamento estético.
Similaridade não implica que um take deva ser removido. Abertura, highlights e
encerramento mantêm posições; a busca limitada permuta apenas desenvolvimentos.
`continuity_weight` modula a preferência contra deslocar a narrativa; zero ou
`allow_reorder=false` preserva ordem. `intentional_break_after` exclui cortes
estilísticos da pontuação. Não há restrição absoluta contra contrastes intencionais.
Busca de mais de sete posições livres preserva ordem, em vez de fingir ótimo global.

## Reframing inicial

16:9, 9:16, 4:3 e 1:1 usam geometria determinística de fill/crop. Evidência opcional
vem do Vision instalado no macOS, via helper Swift próprio auditado e sandbox sem
rede: [auditoria](MVP_0_4_TOOL_AUDIT.md). Sem instalação ou modelo baixado.
Caixas têm origem/índice de frame/hash da imagem, coordenadas normalizadas com y
para baixo e confiança do detector. Caixas fora do frame são rejeitadas e a resposta
bruta preservada; não se inventam ou ajustam caixas para fazê-las passar.

São necessárias três observações distintas no take, alta disponibilidade,
quantidade consistente de pessoas, centro estável e margem de segurança. A união
conservadora preserva o conjunto detectado; não identifica o sujeito principal.
Se isso falhar ou a união não couber na razão pedida, crop central e alerta manual.
`verified_detector_union` significa proveniência/consistência verificadas, não
verdade humana. O crop é estático; não é tracking. Sem evidência de olhar, não
há promessa de espaço de olhar automático. Movimento pode impedir ajuste estático.

## Action-aware cutting

Frames densos a aproximadamente 10 fps, com índices reais, refinam a vizinhança
dos cortes. Evidências de eventos a 1 fps fornecem sementes para candidatos locais,
mas nunca fronteiras exatas. O conjunto de candidatos inclui toda a grade local;
sementes são projetadas na grade, avaliadas pelas observações adicionais.

Estratégias: `cut_on_action`, `preserve_complete_action`, `cut_before_action`,
`cut_after_action`. A referência é a entrada do segmento; preservação completa
penaliza entrada/saída dentro de intervalos de movimento aparente. Registra
movimentos, mudanças de direção estimadas, intervalos estáveis e incertezas.
O intervalo de busca é limitado, o consumo de fonte considera a velocidade, e
frames exatos na entrada/saída são decodificados para inspeção final.

Movimento aparente pode ser da câmera, luz ou objeto; conter um evento de movimento
não prova uma ação semântica completa. Não se afirma que todos os gestos importantes
foram preservados. Limites completos não detectáveis são pendência de revisão.

## Música e ritmo

Envelopes RMS locais, onsets, cadeias de batidas ancoradas em ataques observados,
pausas e mudanças persistentes de intensidade. Não se extrapola um BPM fixo sobre
pausas e mudanças de tempo. Seções são aproximações de energia, não labels de
verso/refrão. Pontos de corte combinam esses eventos; deslocamentos obedecem à
tolerância, duração mínima dos takes, capacidade da fonte e duração final exata.
No máximo metade das fronteiras recebe ajuste, priorizando o maior benefício.
Reordenação, narrativa e ação podem competir com o alinhamento musical; o relatório
expõe os trade-offs em vez de declarar melhoria em todos os indicadores.

## Mixagem não destrutiva

FFmpeg `astats` mede picos de amostra dos trechos e da música na taxa de reprodução.
O bound soma conservadoramente todos os canais, aplica ganhos e reduz ambos se
necessário para reservar headroom de -3 dBFS. Não é true peak ou LUFS, não substitui
escuta, e o roteamento/pan do editor pode diferir do downmix do preview.

Ganhos e fades são curvas `adjust-volume/param/keyframeAnimation`, editáveis.
Os fades por clip suavizam joins sem sobreposição. **Crossfades reais com handles
não estão implementados**. Slow motion permanece sem áudio original; os demais
mantêm recursos/canais originais. Música tem ganho/envelope separado. Ducking é
opcional e exige `priority_ranges` explícitos: nenhuma voz é classificada como
diálogo automaticamente. Não há normalização destrutiva, limiter ou alteração de
fontes. O preview reproduz os ganhos/envelopes e downmixa todos os streams declarados
para estéreo; não promete equivalência de pan do Final Cut ou grading de Log/HDR.

## FCPXML, preview e round-trip

`editing/export.py` chama o exportador 0.3 e acrescenta somente transformação
estática e volume/envelopes. Mídia, timecodes, fps, duração e timeMap de 50% são
preservados. Posição usa percentuais da altura da fonte, conforme referência Apple.
`validation.py` confere as adições XML contra o pacote, além da DTD oficial 1.10.

`roundtrip.py` compara XMLs simples/Info.fcpxml em bundle `.fcpxmld`, resolvendo IDs
e normalizando durações, ordem, origens, curva de retime, transformações, fontes
áudio, música e curvas completas de ganho. Remove pontos colineares redundantes;
não depende de nomes de recursos nem de apenas poucas amostras de volume. Estruturas
aninhadas, curvas não lineares ou ajustes de canal não suportados falham explicitamente
para revisão manual. Não é um comparador universal de equivalência de FCPXML.
Um self-test comparando o arquivo consigo mesmo **não é um round-trip real**.

Fontes oficiais:
- https://developer.apple.com/documentation/professional-video-applications/adjust-transform
- https://developer.apple.com/documentation/professional-video-applications/adjustment-attributes-and-effect-parameters
- DTD local auditada `audit/FCPXMLv1_10.dtd`.

## Uso

```sh
.venv/bin/python -m final_editor_pro.editing.cli enhance \
  workspace/director-0.4/gemma-planning/edl.json \
  --subjects workspace/director-0.4/subjects-v2.json \
  --proposals workspace/evaluation/annotation-proposals-v1 \
  --reference workspace/director-0.3/final/edl.json \
  --settings config/editing.example.json \
  --output workspace/director-0.4/new-edit

.venv/bin/python -m final_editor_pro.editing.cli preview \
  workspace/director-0.4/new-edit/edl.json \
  --output workspace/director-0.4/new-preview

.venv/bin/python -m final_editor_pro.editing.cli roundtrip \
  workspace/director-0.4/final/timeline.fcpxml \
  workspace/director-0.4/roundtrip/Info.fcpxml \
  --output workspace/director-0.4/roundtrip-comparison.json
```

Outputs devem ser novos. `--subjects` é opcional; sem ele, fallback central.
O arquivo de sujeitos deve ter sidecar `.sha256`; a preparação nativa verifica
hashes do helper, origem das imagens e cache. Detector indisponível não permite
contornar o sandbox; executar sem detecções é um modo explicitamente sinalizado.
`editing.undo.undo(output)` estaciona apenas artefatos gerados intactos após validar
hashes; nunca toca nos originais. Caches são derivados e invalidados por hashes de
fonte/ferramenta/settings; corrupção falha explicitamente.

## Preparação opcional de sujeitos

O helper não é instalado nem compilado automaticamente. Depois de revisar o
fonte e o compilador Apple já instalado, o build usado nesta execução foi:

```sh
mkdir -p workspace/director-0.4/tools workspace/director-0.4/swift-cache temp/mvp04
TMPDIR="$PWD/temp/mvp04" xcrun swiftc \
  -module-cache-path workspace/director-0.4/swift-cache \
  tools/vision_people.swift -o workspace/director-0.4/tools/vision-people
```

O manifesto JSON deve declarar `binary` e `sha256` do executável revisado. A CLI
não cria um hash de aprovação arbitrário para um binário desconhecido. O manifesto
local usado e os hashes de revisão estão no workspace; só o fonte é versionável.

```sh
.venv/bin/python -m final_editor_pro.editing.cli prepare-subjects \
  workspace/director-0.4/gemma-planning/edl.json \
  --helper-manifest workspace/director-0.4/vision-manifest-v2.json \
  --output workspace/director-0.4/new-subjects
```

Essa preparação é opcional/macOS e exige sandbox-exec disponível. Cache contém
proxies e resultados com hashes, sem inferência de identidades. Falha de Vision
é registrada e interrompe a preparação; o usuário pode optar explicitamente pela
execução de edição sem `--subjects`, que sinaliza crop central.

## Relógio BWF da música

A origem `time_reference / sample_rate` é registrada e preservada no asset, no clip
e nos keyframes, mantendo envelopes relativos e posição na timeline. Usar a taxa
da fonte, sem arredondar ao frame de vídeo. Sem BWF, origem zero. A correção foi
validada pelo usuário com repetidas reproduções do início nesta montagem.
Mídias e bibliotecas permanecem intactas; não há mudança de duração ou resampling
destrutivo. Pacotes antigos podem ser reconciliados pelo pass `enhance`.

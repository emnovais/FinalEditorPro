# Feedback de edição e correções de compatibilidade

## Escopo do retorno

O usuário confirmou que a avaliação de vídeo mediano e take repetido refere-se à
montagem **MVP 0.3, oito segmentos**. O bundle reexportado em
`workspace/director-0.4/roundtrip/` corresponde a ela, e não à montagem 0.4 de nove
segmentos. A aprovação anterior de funcionamento do 0.3 não implica aprovação
estética. O MVP 0.4 foi depois importado com avisos nos parâmetros de áudio.
Nenhuma das correções abaixo foi declarada aprovada visualmente pelo usuário.

## Aviso de volume do MVP 0.4

O aplicativo informou que ignorou `adjust-volume/param` por causa do atributo de
interpolação nos keyframes. O exportador emitia `interp="linear"` nos elementos
`keyframe` de volume. A DTD permite esse atributo genericamente; isso não garante
que o parâmetro específico o aceite no importador.

Correção: emitir keyframes de volume somente com `time` e `value`; manter
`interp="linear"` em `timeMap/timept`, que pertence a outro recurso. O validador
semântico agora rejeita atributos explícitos de interpolação em volume, além de
conferir tempos e ganhos contra o plano. A suíte possui regressão específica.
O ganho estático de fallback passa a ser o nominal, em vez do primeiro ponto de
fade (-96 dB), para evitar fallback quase silencioso caso um envelope seja ignorado.

Uma primeira correção isolada, preservando todos os cortes e valores originais,
foi publicada em `workspace/director-0.4/audio-param-fix/timeline.fcpxml`.
Ela removeu apenas `interp` de 36 keyframes. A revisão de seis takes abaixo inclui
também o fallback nominal e uma atenuação explícita de segurança no trecho lento.
A ausência de novos avisos exige nova importação manual; DTD não comprova isso.

Referências: [parâmetros de ajuste da Apple](https://developer.apple.com/documentation/professional-video-applications/adjustment-attributes-and-effect-parameters),
DTD oficial local `audit/FCPXMLv1_10.dtd` e o diagnóstico fornecido pelo usuário.

## Repetição e duração de candidatos

Havia dois problemas distintos:

- A política proibia repetir o ID de candidato, mas permitia diferentes intervalos
  do mesmo arquivo. A continuidade só penalizava sobreposição entre vizinhos,
  deixando reutilização distante passar. Isso explica repetição de takes sem haver
  necessariamente duplicação byte a byte do mesmo intervalo.
- O tamanho da janela de seleção usava o fps da timeline. Com fontes de 50 fps e
  projeto 25 fps, cinco segundos viravam 125 frames de fonte (2,5 s). Agora o cálculo
  usa fps da fonte: cinco segundos = 250 frames. A seleção não exige mais tantos
  fragmentos curtos para preencher o tempo.

`CreativeBrief.max_shots_per_asset` limita uso de cada fonte na sequência inteira.
Novas execuções do Director adotam um uso por arquivo quando o limite não está
explicitado. Arquivos/EDLs antigos continuam legíveis; reutilização intencional
pode ser configurada explicitamente com limite maior. A política é validada no
plano e na EDL, e a complementação determinística de duração não pode burlá-la.

Para limite um, a entrada do planejador já tem um candidato por arquivo. A escolha
considera duração disponível, avisos de blur nos eventos e variedade de evidências;
não se afirma avaliação estética definitiva. Um novo audit global registra fontes
reutilizadas, repetições exatas e intervalos sobrepostos, incluindo pares distantes.

Respostas locais do Gemma que desrespeitaram reutilização/papéis foram preservadas
como rejeitadas. A revisão compilou uma resposta real já salva contendo seis fontes
únicas; não usou provider simulado. O compilador atribuiu rótulos de borda por
posição e moveu explicitamente a fonte descrita pelo usuário como beijo/sorriso
para o fechamento, preservando o intervalo selecionado pelo modelo. Autoria dessa
regra editorial é determinística, não atribuída ao modelo. A ordem não foi novamente
reotimizada por similaridade. O raw original e as alterações são rastreáveis.

## Round-trip real do MVP 0.3

Comparação do arquivo fornecido pelo usuário:

- Geometria, fps, duração de 20 s, ordem e durações dos oito segmentos coincidem.
- Cinco entradas normais foram reexportadas um frame de fonte (20 ms) mais tarde.
  As novas seleções normais são alinhadas ao relógio da timeline, considerando
  origem de timecode e cadência fonte/projeto; não há conversão silenciosa de fps.
- O mapa de 50% foi reparametrizado pelo editor, com diferença racional mínima de
  taxa/posição; não se afirma identidade numérica exata.
- `srcEnable="video"` do trecho lento não reaparece no XML nativo. Isso é uma
  diferença declarativa, não prova de áudio audível. A revisão mantém o flag e
  acrescenta ganho estático -96 dB como defesa explícita; requer escuta/reexportação.
- O offset declarado da âncora musical difere em -20 ms; isso não é uma medição
  perceptual do sync. Ganho constante da música coincide.
- Referências passaram a apontar para mídia na biblioteca do usuário. Não foram
  abertos nem alterados os conteúdos da biblioteca; identidade dos bytes dessas
  cópias não foi certificada apenas por nome e metadados.

`comparison-mvp03.json` e `summary-mvp03.json` no diretório de round-trip guardam
os resultados locais. O retorno não é marcado como equivalente exato e não valida
as novas curvas de áudio ou transforms do 0.4.

## Revisão de seis takes

Arquivos em `workspace/director-0.4/revision-unique/`:

- `final/timeline.fcpxml`: nova revisão com título distinto, seis segmentos de seis
  arquivos diferentes, 500 frames / 20 s, 3840×2880, 4:3, 25 fps e um trecho a 50%.
- `final/edl.json`, `final/comparison.json`: política, decisões e auditoria global.
- `preview/preview.mp4`: proxy 512×384/25 fps com áudio original/música e fades.
- `review.html`: revisão local com preview e links.
- `planned/` e `planned-002/`: respostas locais rejeitadas e seus motivos.
- `unique-plan/`: compilação explícita da resposta real e regras editoriais.

Não há arquivo reutilizado, intervalo sobreposto ou repetição exata nesta revisão.
O preview contém 500 frames; pico de amostra medido -14,509551 dBFS. A melhora
estética e a ausência de avisos de importação continuam sujeitas à revisão humana.

**128 testes aprovados**, incluindo os 120 anteriores e regressões de volume,
reutilização global, janelas em fps de fonte, seleção única, rótulos de narrativa,
fallback nominal e alinhamento de corte. Os testes ficam somente no disco,
ignorados pelo Git conforme solicitado. XML validado pela DTD oficial e pelas
checagens semânticas de mídia/tempos/transformações/ganho. Originais, XMLs anteriores
e arquivo reexportado preservados. Nenhum commit, push ou instalação nesta revisão.

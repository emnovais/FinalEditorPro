# Investigação de demora ao iniciar reprodução em zero

**Estado atual: espera resolvida operacionalmente no teste A pelo usuário e
correção incorporada.** As hipóteses e instruções abaixo preservam a cronologia
da investigação. Encerramento e classificação das diferenças do round-trip:
[MVP_0_4_CLOSEOUT.md](MVP_0_4_CLOSEOUT.md).

## Retorno do usuário

A revisão de seis takes foi importada sem erros. O usuário considerou o vídeo
melhor, percebeu cortes no ritmo musical e os keyframes de áudio/música. A demora
de alguns segundos ocorre **toda vez ao iniciar exatamente do começo**, inclusive
após reproduzir outro trecho. Não ocorre ao iniciar de outras posições.

O bundle nativo recebido é `Final Editor Pro — Revision 0.4 • Six Unique Takes.fcpxmld`,
no diretório `workspace/director-0.4/roundtrip/`. Ele foi somente lido. Não foram
abertas ou alteradas bibliotecas nem mídias dentro delas.

## Comparação do round-trip

- Seis segmentos, ordem, offsets, durações, 20 s, 3840×2880/4:3 e 25 fps coincidem.
- As cinco entradas normais coincidem exatamente; o alinhamento ao relógio do
  projeto evitou os deslocamentos de um frame observados na versão anterior.
- As posições de transform coincidem dentro de 0,0001 unidade.
- Curvas de volume foram preservadas: diferença máxima de 0,000003 dB nos clipes
  e 0,000027 dB na música (arredondamento de serialização).
- O mapa lento foi reparametrizado pelo Final Cut. A diferença máxima nas posições
  amostradas é aproximadamente 0,000012573 s, muito menor que um frame da fonte.
- O flag `srcEnable=video` não reaparece, mas o ganho de segurança -96 dB no trecho
  lento foi preservado. Isso não é uma afirmação de identidade estrutural do XML.
- A âncora da música está exatamente no início da timeline. Não há gap inicial ou
  atraso de vários segundos declarado no XML.
- Os fades iniciais programados são de 0,2 s, não de vários segundos. Sua presença
  não comprova causa de espera do transporte do editor.
- Os arquivos nativos apontam para mídia na biblioteca. Não foram verificados os
  hashes dessas cópias; correspondência de nomes/metadados não prova identidade.

Uma falha do comparador foi corrigida: os pares tempo/ganho eram tuplas, e a
recursão aplicava tolerância apenas a listas. Os arredondamentos acima apareciam
como diferenças exatas. Novo teste cobre essa situação, sem afrouxar tempos.

## Hipótese verificável de relógio da música

O WAV original é Broadcast Wave e contém `time_reference=1117`, com 44.100 Hz.
Isso corresponde a `1117/44100 s`, aproximadamente 25,33 ms. O importador passa a
declarar essa origem no asset nativo; nosso XML original declarava `start=0s`.
A música conectada permanece com início implícito zero no XML nativo.

A discrepância de relógio é real, mas **não prova que cause vários segundos de
espera**. Ela não deve ser confundida com atraso desejado na timeline. Também
podem existir efeitos de preparação/decodificação/renderização do editor que o
XML estático não mede. Nenhum resultado de latência no Final Cut foi inventado.
Não foi alterado o exportador de produção com base apenas nessa hipótese.

## Arquivos controlados para teste

Pasta `workspace/director-0.4/startup-diagnostics/`. Cada arquivo tem projeto com
nome distinto. Todos passaram na DTD oficial 1.10. Vídeos, seis cortes, origem dos
vídeos, resolução, duração, slow motion e transformações são os mesmos.

| Arquivo | Única variável funcional |
|---|---|
| `00-control.fcpxml` | Estrutura original, apenas nome diferente para controle de nova importação |
| `A-music-source-clock.fcpxml` | Origem BWF do asset e da música reconciliadas; keyframes deslocados pelo mesmo delta no relógio da fonte |
| `B-music-disabled.fcpxml` | Música removida da cópia de diagnóstico e seu recurso não utilizado; vídeos e áudio original intactos |
| `C-static-volume.fcpxml` | Automação de volume removida; ganhos nominais, música e ganho -96 dB do slow motion preservados |

O teste A preserva o início físico do áudio e os tempos relativos dos fades:
asset, start do clip e keyframes recebem o mesmo delta. Offset de âncora, duração,
valores de ganho e referências permanecem inalterados. Não se adiciona silêncio,
não se renderiza nem modifica o WAV. B e C são diagnósticos, não versões finais.

### Sequência de avaliação

1. Use a biblioteca de testes separada. Não substitua a revisão aprovada.
2. Teste primeiro A: reproduza de zero, avance, volte a zero e repita com Espaço.
3. Se A melhorar, compare com `00-control` nas mesmas condições, para separar o
   efeito do relógio do efeito de simplesmente importar um projeto novo.
4. Se A mantiver a demora, teste B. Se B melhorar, há evidência para investigar o
   caminho da música, sem provar que seja apenas o relógio BWF.
5. Se B mantiver a demora, teste C. Se só C melhorar, investigar avaliação dos
   envelopes no início. Se nenhum melhorar, isso não elimina causas de mídia,
   renderização, dispositivo de áudio ou estado interno do editor.
6. Registre aproximadamente quantos segundos leva cada teste e se a espera repete.
   Compare com tarefas de fundo concluídas, sem apagar caches/bibliotecas.

Não foram alteradas preferências globais ou executadas ações no Final Cut. A Apple
explica que tarefas em segundo plano e configurações de reprodução influem no
desempenho, mas isso não identifica a causa deste caso.

## Verificações

131 testes aprovados, incluindo deslocamento de relógio com preservação das curvas,
variantes isoladas e tolerância de arredondamento do comparador. Testes continuam
locais/ignorados pelo Git. DTD, igualdade de atributos dos vídeos, sequência,
timeMaps e transforms verificadas em todas as variantes. XML original, bundle
reexportado, vídeos e WAV preservados. Sem instalação, download de modelos,
commit ou push.

Dados: `report.json` e `roundtrip-differences.json` na pasta de diagnóstico.
Naquele estágio, a causa de performance ainda não estava confirmada; o teste A
foi depois validado pelo usuário, conforme a seção de resolução abaixo.

## Fontes oficiais

- [Apple: atributos de tempo](https://developer.apple.com/documentation/professional-video-applications/timing-attributes): relógios e âncoras; filhos ancorados podem ultrapassar a duração do parent.
- [Apple: configurações de reprodução](https://support.apple.com/guide/final-cut-pro/verb8e60ab7/mac).
- [Apple: mídia otimizada/proxy e tarefas em segundo plano](https://support.apple.com/guide/final-cut-pro/verb8e5f6fd/mac).

## Resolução validada pelo usuário

Em 17/11/2026, o usuário informou que importou o teste A e reproduziu o vídeo
várias vezes desde o início; a espera deixou de ocorrer. A reconciliação da origem
BWF foi incorporada ao pipeline de produção para esta montagem e futuras músicas
com `time_reference` disponível. Isso registra validação operacional do usuário,
sem afirmar instrumentação interna do Final Cut ou causalidade universal.

`source_start_seconds`, `source_clock_kind` e `bwf_time_reference_samples` ficam
no relatório musical. A referência em amostras usa a taxa original (44.100 Hz neste
WAV), nunca a taxa reduzida usada na análise. Sem a tag, a origem continua zero.
Metadados negativos/inválidos são recusados. O Director preserva a origem no asset
e no clip; o exportador de envelopes soma essa mesma origem a cada keyframe.
O pass de refinamento também reconcilia a origem ao receber uma EDL anterior.
A posição na timeline e os tempos relativos de áudio não mudam.

Versão consolidada: `workspace/director-0.4/revision-unique/final-bwf/timeline.fcpxml`.
O XML foi comparado integralmente ao teste A validado, desconsiderando somente o
nome do projeto, e coincide. O pacote EDL correspondente inclui a origem correta.
Cortes, fontes, mix, geometria e 500 frames de duração permanecem iguais. Não é
necessário renderizar outro preview, pois o conteúdo audiovisual pretendido é o mesmo.

133 testes aprovados após a incorporação, incluindo taxa de amostragem variável,
origem ausente/inválida, igualdade da exportação de produção com o teste A e
rejeição de divergência entre origem do asset e do clip de música. Testes permanecem
ignorados pelo Git. DTD oficial e integridade dos originais verificadas. Nenhum
commit/push realizado; não há nova autorização para publicação.

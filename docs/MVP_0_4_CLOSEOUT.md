# Encerramento técnico — MVP 0.4

17/11/2026 — Australia/Brisbane.

**Estado: encerrado tecnicamente para a revisão de seis takes aprovada visualmente
pelo usuário no Final Cut Pro. Não há bloqueador técnico identificado nesse escopo.**

Branch confirmada: `develop/mvp-0.4-intelligent-editing`.
Código verificado: `f4dca7cf87b99d7ae5b9cf83555933a85b40807a`.
A conferência de 17/11/2026 alterou somente documentação, sem nova funcionalidade,
alteração do exportador, instalação, execução de modelos, automação do Final Cut,
commit ou push. Em 18/11/2026, o usuário aprovou o encerramento e autorizou somente
o commit documental local nesta branch. Push, merge e alterações na main continuam
fora da autorização atual.

## Aceite manual recebido

O usuário aprovou a revisão de seis takes e confirmou importação sem erros,
melhoria perceptível da montagem, cortes no ritmo musical, preservação dos
keyframes de áudio/música e round-trip com duração, segmentos, geometria, cortes
e transformações preservados. No teste A, repetidas reproduções desde zero deixaram
de apresentar a espera reportada. Trata-se de validação manual desta montagem,
não de benchmark, prova de identidade estrutural ou validação de todos os formatos.

A timeline tem seis fontes distintas, 500 frames/20 segundos, 3840×2880, 4:3,
25 fps e um trecho em 50% de velocidade. O áudio e os arquivos originais não foram
modificados pelo sistema.

## Correção BWF no código de produção

Conferência realizada diretamente no código, sem modificá-lo:

| Etapa | Implementação verificada |
|---|---|
| Leitura do relógio | `director/music.py:source_clock_metadata` interpreta `time_reference / sample_rate` usando a taxa da fonte |
| Ingestão/planejamento | `director/pipeline.py:run_director` incorpora os campos ao relatório musical e à EDL |
| Refinamento de EDL anterior | `editing/pipeline.py:enhance` reconcilia a origem a partir de probe local e registra a operação |
| Recurso e clip musical | `director/export.py:export_edl` usa a mesma origem no asset e no início do clip |
| Automação | `editing/export.py:apply_envelope` soma a origem aos tempos relativos de cada keyframe |
| Validação | `editing/validation.py:validate_package_xml` confere origem do asset/clip e envelopes contra o pacote |

Neste WAV, a origem é `1117/44100 s`. Sem a tag BWF, o fluxo usa zero. A correção
preserva o início físico do áudio, a âncora na timeline, a duração e os tempos
relativos dos fades. Não é adição de 25,33 ms de silêncio ou deslocamento da montagem.

A resolução da espera foi confirmada operacionalmente pelo usuário no teste A.
Não foi instrumentado o mecanismo interno de inicialização do Final Cut, nem
estabelecida causalidade universal para outros projetos.

## Correspondência do consolidado com o teste A

Artefatos locais preservados:

- `workspace/director-0.4/startup-diagnostics/A-music-source-clock.fcpxml` — teste A aprovado.
- `workspace/director-0.4/revision-unique/final-bwf/timeline.fcpxml` — consolidado de produção.
- `workspace/director-0.4/revision-unique/final-bwf/edl.json` — pacote correspondente.

A comparação integral das árvores XML, normalizando **somente o nome do projeto**,
passou. Não foram normalizados tempos, valores de áudio, URLs ou transformações
para obter esse resultado. A reexportação do pacote pelo código de produção também
coincide **byte a byte** com o consolidado. A DTD oficial Apple 1.10 foi validada
com `xmllint --nonet`, além das verificações semânticas XML/EDL/gain/transform.

| Artefato | SHA-256 |
|---|---|
| Teste A | `8b788c31d6684423b970b2764154a7828c21eaf348616355915c17fdb2204102` |
| Consolidado | `4aac8a7283b770c9e4fd2a0b491f230ab8d8479c456fa8d4e6f1898562c58988` |
| XML nativo de seis takes fornecido | `338916480a47e90b16ce365cb52183a6f42a4a4a0264fc0dab7d917b9acbec51` |

Os hashes do teste A e do consolidado diferem porque os nomes dos projetos diferem.

## Round-trip: classificação das diferenças

O round-trip disponível compara o XML de seis takes **anterior à correção BWF**
com o bundle nativo `Final Editor Pro — Revision 0.4 • Six Unique Takes.fcpxmld`.
Não foi fornecido outro XML nativo reexportado especificamente a partir do teste A
ou do consolidado BWF. A reprodução do teste A tem aceite manual; sua equivalência
ao consolidado é comprovada separadamente pela comparação descrita acima.

| Categoria | Observação | Interpretação |
|---|---|---|
| Serialização sem mudança numérica | Frações equivalentes (`20/1s` e `20s`), novos IDs, omissão de atributos com default e transforms identidade | Não representa mudança de duração/ordem; comparar referências resolvidas e valores, não texto bruto |
| Serialização com arredondamento | Ganhos diferem até 0,000003 dB nos clipes e 0,000027 dB na música; posição de transform dentro de 0,0001 unidade | Preservação dentro das tolerâncias documentadas; não identidade numérica perfeita |
| Relocalização de mídia | URLs apontam para cópias gerenciadas dentro da biblioteca e incluem IDs/bookmarks nativos | Não são mudança de corte; também não comprovam identidade dos bytes por nome/metadados |
| Representação de retime com pequena diferença numérica | Final Cut expandiu/reparametrizou o mapa lento; desvio máximo nas posições amostradas de aproximadamente 0,000012573 s | Abaixo de um frame da fonte, mas não igualdade matemática exata de todos os valores/estruturas |
| **Diferença semântica declarativa de áudio** | `srcEnable=video` não reaparece; o comparador passa de `audio_enabled=false` a `true` | Não tratar como mera serialização nem alegar equivalência estrutural perfeita. O ganho constante de **-96 dB foi preservado**, mantendo a atenuação de segurança planejada |
| **Diferença semântica de relógio de origem** | Asset musical reexportado declara `1117/44100s`, em vez de zero do XML anterior | A correção de produção reconcilia asset, clip e keyframes. Esse é o ajuste operacionalmente validado pelo teste A; não deve ser escondido como arredondamento |

Conferências exatas: os seis offsets e as seis durações coincidem; as entradas e
saídas normais coincidem exatamente. A âncora musical continua no início. A pequena
diferença do mapa lento permanece registrada, sem ser convertida em uma afirmação
de equivalência exata. A comparação é específica à estrutura simples desta revisão,
não um comparador universal de todos os recursos FCPXML.

### Identidade das mídias

Os hashes dos seis vídeos originais e da música em `workspace/test_media/` foram
reconferidos contra a EDL e coincidem. **A identidade por hash das cópias dentro da
biblioteca não foi verificada.** Nenhum conteúdo da biblioteca foi aberto, alterado
ou varrido para certificá-la. URLs, nomes, metadados e aprovação visual não substituem
essa verificação; ela permanece uma limitação documentada, não uma identidade presumida.

## Testes, Git e proteção de arquivos

- Suíte completa executada novamente: **133 testes aprovados**, sem falhas ou skips.
- Sockets/DNS bloqueados nos testes; nenhuma inferência remota. O teste local com
  WAV sintético/FFmpeg continua cobrindo curvas de ganho.
- Testes BWF cobrem taxa da fonte, tag ausente/inválida, igualdade com o teste A e
  divergência entre origem do asset e do clip.
- XML consolidado validado pela DTD oficial e pelo validador de pacote existente.
- Branch atual conferida, sem mudar `main` ou referências Git.
- Diff desta tarefa restrito a documentação; código/exportadores inalterados.
- Índice e `.gitignore` conferidos: nenhum vídeo, áudio original, proxy, render,
  cache, modelo, binário, biblioteca, credencial ou arquivo temporário a versionar.
- `/tests/` continua ignorado, com os scripts preservados somente no disco, conforme
  decisão do usuário. A suíte não é incluída em clones novos do repositório.

Evidências locais desta conferência em `workspace/director-0.4/closeout/`:
`verification.json` e `tests.txt`. Esses arquivos não são versionados.

## Bloqueadores e limites do encerramento

**Nenhum bloqueador técnico real identificado para encerrar o MVP 0.4 no escopo
validado pelo usuário.** Importação, revisão visual, curvas e reprodução inicial
têm confirmação manual; as conferências de produção passaram.

Permanecem limites explicitamente aceitos neste relatório: hashes das cópias da
biblioteca não verificados, ausência de equivalência estrutural perfeita no flag
de áudio, pequenas diferenças de serialização/retime e ausência de outro round-trip
nativo do teste A. Não foram convertidos em garantias universais ou ignorados para
produzir um falso resultado de identidade. Outros codecs, tracking, crossfades com
handles e VFX continuam fora deste marco, sem implementação adicional aqui.

Em 18/11/2026, o usuário autorizou o commit local exclusivamente destas atualizações
documentais, com a mensagem `docs: finalize MVP 0.4 validation and closeout`.
Não há autorização de push, merge ou alterações na main. A publicação remota
continua pendente e não constitui bloqueador técnico do resultado validado.

# Final Editor Pro — arquitetura do MVP original

Data: 16/11/2026. Estado: MVP offline implementado e testes locais aprovados;
extração real de metadados e importação no Final Cut ainda não verificadas.

## Viabilidade e escopo

É viável automatizar análise, decisões e montagem e entregar uma timeline
editável por FCPXML. Não há equivalência entre gerar XML e controlar todos os
recursos internos do Final Cut. A qualidade editorial precisa de avaliação humana
e a fidelidade do intercâmbio precisa de testes reais de ida e volta.

O computador Apple Silicon informado favorece inferência e decodificação locais,
mas não fizemos benchmark nem verificamos o hardware. Desempenho de 4K depende do
codec, quantidade de memória e modelos. Não se promete tempo real.

Decisões iniciais:

- Núcleo próprio em Python, sem dependências Python adicionais no MVP.
- FCPXML 1.10 como alvo conservador, ancorado na DTD oficial consultada.
  Não confundir a versão publicada dessa página com a mais recente aceita pelo app.
- Nenhuma instalação, inicialização MCP, chamada de IA, download de modelo ou
  automação do Final Cut nesta entrega.
- Não adotar `fcp-mcp-server` como dependência inicial. Auditoria em [SECURITY_AUDIT.md](../SECURITY_AUDIT.md).
- Arquivos originais somente para leitura; não transcodificar, mover, renomear ou
  sobrescrever. SHA-256 antes/depois do probe e antes/depois da publicação.
- Exportar eventos/projetos novos, sem localização ou UID de biblioteca existente.
  O usuário deve criar e selecionar uma biblioteca de teste separada na importação.

## Módulos e contratos

```text
Vídeo/música/instruções
  → ingestão e catálogo imutável
  → análise multimodal → evidências com intervalos/confiança/proveniência
  → planejamento criativo → projeto JSON versionado
  → verificador determinístico → plano aprovado
  → compilador de efeitos → recursos nativos ou mídia derivada
  → exportador FCPXML → validação DTD/semântica → revisão → importação isolada
```

1. **Ingestão:** caminhos locais canônicos, hash, relógios, codec, resolução,
   áudio, cor e timecode. MVP: `ave.cli.probe` e `ave.core.metadata`.
   `ffprobe` é executado por caminho explícito, sem shell e com protocolo `file`.
   Não está instalado neste ambiente; sua instalação/execução depende de aprovação.
2. **Análise multimodal (planejada):** adapters independentes para cenas,
   movimento, enquadramento, fala e batidas. Produzir evidências; não editar arquivos.
   Priorizar proxies e amostras locais, mantendo mapeamento exato ao original.
3. **Planejamento:** timeline JSON independente do provedor de IA. MVP:
   `plan`, montagem determinística na ordem de entrada. Futuro: interface
   `Planner.plan(brief, evidence, constraints) -> Project`; providers locais ou
   remotos intercambiáveis, versões/modelos registrados. Nenhum provider implementado.
4. **Execução de efeitos (planejada):** consultar matriz de capacidades;
   efeitos nativos viram parâmetros, outros geram jobs de render em diretório
   derivado. Falhar explicitamente quando não suportado. Sem comandos arbitrários
   propostos por modelos. Render externo perde editabilidade interna do efeito.
5. **Exportação:** `export_xml` faz somente compilação. Não abre Final Cut.
   `publish` cria diretório exclusivo; JSON e XML independem de bibliotecas nativas.
6. **Operações:** diário JSONL de publicação, hashes e reversão dos artefatos
   intactos para `undone/`. Falhas durante publicação ficam registradas. Preflight
   e probe anteriores à publicação reportam erro no terminal; ainda não possuem
   diário persistente. Não há reversão de importação no Final Cut.

## JSON intermediário implementado

`version`, `name`, `media[]`, `clips[]`, `decisions`.
Cada mídia contém caminho absoluto, SHA-256, tamanho, fps/duração/start racionais,
dimensões, canais, codec, pixel format e informações de cor disponíveis.
Cada corte usa índice de mídia, `in_frames` e `duration_frames` inteiros.
`start` é a origem do timecode de fonte; `in_frames` é relativo a essa origem.
`decisions` registra estratégia/modelo/efeitos; efeitos não vazios são recusados.
Racionais no JSON são strings (`24000/1001`), nunca floats.
O JSON pode ser ajustado e reexportado para outra pasta sem reprobe.
Uma futura migração deve preservar manifestos antigos e usar schema explícito.

## Matriz de capacidades

| Recurso | Representação e execução | Estado deste MVP |
|---|---|---|
| Cortes, ordem, duração, referências | FCPXML, sem render | Implementado |
| Marcadores, roles, áudio conectado e sincronização musical | Decisões no XML; detecção de batidas externa | Planejado |
| Transform, crop e animação de parâmetros | XML com curvas compatíveis | Planejado |
| Speed ramps | `timeMap`/pontos no XML; interpolação/render pelo editor | Planejado; exige round-trip |
| Transições | XML referencia efeito instalado; exige handles suficientes | Planejado |
| Máscaras de objetos | Segmentar externamente ou recurso nativo/plugin; curva/efeito conforme versão | Pesquisa necessária |
| Tracking | Versões recentes expõem elementos de tracking; calcular/transferir dados exige validação específica | Pesquisa necessária |
| Efeitos cinematográficos | Referências Motion/FxPlug e parâmetros ou render externo | Planejado |
| Correção de cor/LUT | Metadados/efeitos suportados; análise e decisão externas | Não implementado |
| Render final | Final Cut/Motion ou motor externo | Não implementado |

Expressar um parâmetro no XML não executa análise de imagem nem garante que o
efeito/plugin exista. Não se inventarão UIDs ou dados opacos. Templates Motion
devem ser versionados, instalados com aprovação e testados na versão alvo.

## Preservação e limites

- Nenhuma recompressão no MVP: `media-rep` aponta para URLs locais dos originais.
- Fontes precisam ter mesma resolução, fps e metadados de cor. Não há conform
  implícito. Proxies, música separada e timelines com formatos mistos vêm depois.
- Um vídeo progressivo, pixels quadrados, no máximo um stream de áudio mono/estéreo
  48 kHz. Recusa offsets de PTS/áudio, rotação/side data e durações fora da grade.
- Comparar fps nominal e médio e contagem disponível detecta ambiguidades comuns,
  mas não comprova CFR. Varredura de timestamps por frame é uma etapa futura.
- Timecodes SMPTE NDF/DF são convertidos para segundos racionais. Timecode não é
  PTS. Material FX3 com relógios/metadata especiais pode ser recusado, nunca
  corrigido por suposição.
- Cor de fonte fica registrada no JSON; XML não força espaço nem aplica LUT.
  Preservar bytes não garante interpretação correta de S-Log3/HDR pelo Final Cut.
  Validar camera LUT e gerenciamento de cor antes de produção.
- SHA completo de 4K pode ser lento. A comparação não impede outro processo de
  alterar o arquivo depois; montagem de fontes somente leitura é recomendada.
- Publicação não é uma transação resistente a queda de energia. Arquivos parciais
  ficam na pasta de execução; somente o evento `complete` certifica o término.
- Proteções de caminho assumem workspace local confiável, sem adversário trocando
  diretórios concorrentemente. Não equivalem a sandbox do sistema operacional.

## Dependências e aprovação

Atual: Python 3.10+ (testado com 3.15.0), biblioteca padrão; testes DTD usam
`/usr/bin/xmllint` já presente no macOS e DTD oficial baixada como texto.
Nenhum pacote instalado, código upstream importado ou vídeo real processado.

Próxima dependência: FFmpeg/ffprobe, com versão/origem/hash identificados e
aprovação explícita antes de instalar/executar. Depois: avaliar ferramentas de
cenas, áudio, transcrição e inferência Metal/MLX por módulo, com licenças,
lockfile, hashes, caches isolados e auditoria das dependências transitivas.
Serviços remotos só recebem mídia com autorização específica; nomes e transcrições
são dados não confiáveis e não podem instruir ferramentas.

## Plano de implementação e critérios de aceite

1. **Concluído:** auditoria estática inicial, plano, núcleo JSON, compilador e
   CLI com testes unitários e DTD. Limites registrados, sem efeitos simulados.
2. **Próximo, após aprovação:** obter ffprobe auditado e executar com clipes de
   teste 24/25/29.97 fps, áudio, caracteres especiais e timecodes. Verificar hashes,
   metadados e rejeições; incluir fixture real pequena e redistribuível.
3. **Validação no editor:** criar biblioteca descartável; importar manualmente,
   comparar frames de entrada/saída, duração, áudio, cor e links; exportar XML de
   volta e comparar semanticamente. DTD válida não basta para garantir importação.
4. **Análise local:** áudio/batidas/cenas e índice por fonte; evidências reproduzíveis,
   cache por hash, orçamento de memória, cancelamento e diário também do preflight.
5. **Planejamento IA:** schema formal, providers, validação de limites, avaliações
   editoriais e explicação das decisões. Saída do modelo nunca vai direto ao editor.
6. **Efeitos graduais:** áudio conectado/markers → transforms → transições →
   retiming → Motion/cor → máscaras/tracking, cada recurso com fixture e round-trip.
7. **MCP opcional:** somente após aprovação e auditoria transitiva; allowlist mínima,
   rede bloqueada, volumes de fontes somente leitura e importação fora do servidor.

## Referências oficiais

- [Apple: FCPXML Reference](https://developer.apple.com/documentation/professional-video-applications/fcpxml-reference)
- [Apple: criação de documentos](https://developer.apple.com/documentation/professional-video-applications/creating-fcpxml-documents)
- [Apple: DTD 1.10](https://developer.apple.com/documentation/professional-video-applications/document-type-definition)
- [Apple: assets](https://developer.apple.com/documentation/professional-video-applications/asset)
- [OpenAI: MCP no Codex](https://developers.openai.com/codex/mcp/)

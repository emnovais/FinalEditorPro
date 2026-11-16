# Auditoria estática inicial — fcp-mcp-server

16/11/2026. Decisão: **não habilitar no ambiente do usuário nesta etapa**.
Não é certificado de ausência de vulnerabilidades. Não foram executados servidor,
testes upstream, instaladores, hooks ou imports do projeto externo.

## Proveniência e cobertura

Repositório: https://github.com/DareDev256/fcp-mcp-server
Commit fixado: `eece097cc77e2b5882be8b321c0df206f56f85f5`.
Manifesto declara versão `0.34.1`, licença MIT e Python >=3.10.
`audit/commit.json` e `audit/tree.json` preservam consultas ao GitHub.
`audit/upstream/` contém server.py, manifestos e módulos Python de `fcpxml/`
e `tools/`, obtidos como texto por URL com commit fixo; `audit/manifest.json`
registra os hashes dos arquivos baixados. Não usar esses arquivos como executáveis.

Método: leitura dos manifestos e pontos de entrada, busca estática de subprocessos,
rede, escrita/remoção, limites de caminho e variáveis de ambiente; leitura focada
em validação de caminhos, XML, journal, live, geração e transcrição. Não houve
revisão linha a linha de toda a base, análise dinâmica ou auditoria transitiva.
Não foram baixados wheels, dependências nem modelos. README é alegação do autor,
não evidência de testes executados por nós.

## Achados e decisões

| Prioridade | Evidência no snapshot | Implicação e controle necessário |
|---|---|---|
| Alta para este uso | `server.py:115–125,277–293`: raízes de leitura dependem de `FCP_PROJECTS_DIRS`; `FCP_PROJECTS_DIR` legado não as restringe | Configuração comum deixa leitura sem confinamento. Aplicar sandbox de SO e raízes explícitas; não apontar para Home/Movies completos. |
| Alta para este uso | `server.py:254–274`: caminho lexical dentro da raiz basta, mesmo quando symlink resolve fora | Semântica intencional para bibliotecas, inadequada como isolamento forte. Fontes read-only e sandbox; não tratar allowlist interna como barreira suficiente. |
| Alta para este uso | `fcpxml/live.py`, `server.py:4190+` e `4274+`: AppleScript/Open Document e autopush configurável | Pode importar e modificar biblioteca no app. Autopush é desligado por padrão; remover acesso às ferramentas live e não conceder automação na etapa inicial. |
| Alta para este uso | `fcpxml/safe_xml.py:serialize_xml` abre saída com `w`; `server.py:_validate_output_path` valida caminho sem garantir exclusividade | Sufixos e journal não provam ausência universal de sobrescrita. Não disponibilizar escrita em diretórios de originais; exigir criação exclusiva em wrapper próprio. |
| Alta privacidade | `fcpxml/transcribe.py:_transcribe_scribe` envia arquivo para ElevenLabs; `fcpxml/gen.py:_http` faz chamadas HTTP | Há modos remotos e geração paga. Não fornecer chaves, bloquear rede e exigir autorização específica por envio; não confundir opção local com ausência de rede em todo o pacote. |
| Média | `pyproject.toml`: dependências com limites inferiores, sem lock transitivo; build setuptools | Instalar resolução futura executa código não auditado. Fixar versões/hashes e auditar wheels/build antes de aprovação. |
| Média | `fcpxml/transcribe.py:308+`: criação de WhisperModel por nome | Pode precisar baixar modelo. Pré-provisionar pesos aprovados e testar offline, nunca fazer download implícito. |
| Média | `fcpxml/journal.py`: argumentos são registrados; undo move arquivos | Histórico pode conter prompts/caminhos sensíveis; ledger não é backup de biblioteca. Restringir permissões e retenção; validar hashes antes de reversão. |

São riscos observados por leitura estática, sem PoCs executadas. O cenário inclui
agente com acesso a ferramentas e entradas não confiáveis; não afirmamos exploração
remota nem classificações CVE.

## Controles positivos observados

`safe_xml.py` usa defusedxml com entidades e referências externas proibidas;
`live.py` usa argumentos de subprocesso e escape de strings AppleScript; há
timeouts em diversas operações. `journal.py` registra hashes e verifica alterações
antes de mover saídas no undo. Geração exige quote/confirm e limite por chamada;
autopush desligado por padrão. `vlm.py` configura flags offline para o caminho
de captions. Esses controles não anulam os riscos acima e não foram testados aqui.

## Compatibilidade com Codex

O ponto de entrada `server:main_sync` inicia servidor MCP por stdio
(`mcp.server.stdio.stdio_server`). A documentação oficial do Codex descreve suporte
a servidores MCP; portanto existe compatibilidade **de protocolo em princípio**,
sem dependência inerente de Claude nos handlers observados.

Não fizemos handshake, descoberta de ferramentas ou chamada ponta a ponta com
Codex. A UI MCP Apps do upstream não deve ser assumida como disponível no cliente.
Um perfil futuro deve expor somente leitura/inspeção permitida; ativar um servidor
com todos os handlers e depender de instruções em linguagem natural é insuficiente.
Não foi alterada a configuração do Codex e não foi usado `uvx`, que pode instalar
automaticamente uma distribuição diferente do snapshot auditado.

## O que falta para autorizar adoção

Revisar dependências transitivas e artefatos efetivamente instalados, fechar versão
e hashes, testar em sandbox com mídia sintética, negar rede e Apple Events,
verificar escapes de caminhos/symlinks, sobrescrita e journal com testes adversariais.
Reauditar cada atualização. O núcleo desta entrega não depende desse servidor.

Fontes: [snapshot GitHub](https://github.com/DareDev256/fcp-mcp-server/tree/eece097cc77e2b5882be8b321c0df206f56f85f5),
[documentação MCP do Codex](https://developers.openai.com/codex/mcp/).

# Final Editor Pro — arquitetura

## Incremento MVP 0.3 — AI Creative Director

`final_editor_pro/director/` acrescenta briefing, seleção por candidatos,
planejamento narrativo, análise de música, refinamento temporal, EDL v0.3.0 e
adaptador de exportação. Evidências, interpretações, decisões e instruções
executáveis permanecem separadas. `ave/core.py` e o caminho do MVP 0.1 continuam
inalterados. Novas tarefas `creative_brief` e `creative_direction` usam o roteador,
configuração e política de privacidade existentes. Dependências não aumentaram.

A saída nova admite conversão explícita 50→25 fps, crop central 4:3, upscale,
retime linear 50% e música conectada editável. O áudio da câmera é desativado
somente nos trechos lentos, preservando-o nos demais. Não há speed ramp ou VFX.
O caminho novo foi aprovado manualmente pelo usuário no Final Cut em 17/11/2026:
importação, cortes, slow motion 50%, música, 20 s e 3840×2880/4:3/25 fps.
Essa aprovação cobre a montagem validada, sem presumir outros formatos/mídias.
Detalhes: [docs/CREATIVE_DIRECTOR.md](docs/CREATIVE_DIRECTOR.md).

## Incremento MVP 0.2 — AI Video Analyzer

`final_editor_pro/analysis/` acrescenta ingestão reutilizada, extração proxy,
detecção de cenas amostrada, métricas, semântica temporal e scores separados.
Os relatórios não modificam a timeline. Configuração e políticas LOCAL/HYBRID/CLOUD
reutilizam o roteador; `temporal_visual_analysis` é um novo contrato Pydantic.
Runtime/modelo locais foram auditados quanto a proveniência e aprovados, com uma
execução real e benchmark. O servidor é temporário e isolado por sandbox.
Não houve instalação global ou novos pacotes Python. Exportador FCPXML intacto.
Arquitetura operacional e schemas: [docs/ANALYZER.md](docs/ANALYZER.md).
Evidências/limites: [docs/ANALYZER_VALIDATION.md](docs/ANALYZER_VALIDATION.md).

O texto abaixo registra a base inicial e suas decisões; afirmações históricas de
inferência ainda não executada foram superadas pelo relatório do incremento.

Atualizado em 16/11/2026. Estado: MVP de timeline e infraestrutura de IA testados
offline. Integrações reais opcionais implementadas como adapters, sem execução
contra modelo/API nesta etapa. Nenhum processamento de VFX anunciado como pronto.

## Separação de responsabilidades

```text
Fontes imutáveis → metadados/análise local → evidências validadas
  → ProcessingRouter → AIProvider local ou remoto → CreativePlan JSON
  → verificação determinística → adaptador de timeline → Timeline Engine
  → exportação FCPXML → validação → revisão/importação manual isolada
```

| Módulo | Responsabilidade |
|---|---|
| `ave/core.py` | Ingestão/metadados, planejamento sequencial, validação e exportador determinístico já existente |
| `ave/cli.py` | Probe explícito, publicação exclusiva, journal e reversão de artefatos |
| `final_editor_pro/ai/schemas.py` | Contratos Pydantic por tarefa e decisões criativas independentes do provedor |
| `ai/config.py` | Configuração global, overrides por projeto, modos e especificações de providers |
| `ai/providers.py` | AIProvider Protocol, LocalProvider, CloudProvider e resultado/uso/custo |
| `ai/router.py` | Seleção por tarefa/capacidade/modo e ledger de operações |
| `ai/privacy.py` | Consentimento efêmero de uso único por payload/destino |
| `ai/keychain.py` | Leitura/escrita de credenciais via Security.framework, sem arquivos |
| `ai/adapters.py` | Integrações opcionais llama.cpp e HTTPS; factory de providers habilitados |
| `final_editor_pro/timeline.py` | Tradução de CreativePlan para o JSON existente; não acopla fornecedores ao motor |

O pacote `ave` é preservado para compatibilidade com o MVP. Trocar providers exige
somente registro/configuração, sem modificar Timeline Engine ou FCPXML Exporter.
Separação física adicional do core pode ocorrer quando houver alteração funcional;
esta etapa preserva o comportamento testado do motor existente.

## Modos e configuração

LOCAL usa apenas modelos locais; referência explícita a provider remoto falha.
Não há fallback automático após erro. HYBRID permite seleção remota por tarefa e
prefere local quando não há rota explícita. CLOUD prefere remoto para tarefas de IA,
sem transferir operações de mídia/IO para fora do Mac. Probe, transcode e exportação
são reservados aos motores locais, não aceitam rotas de IA.

`ProcessingConfig` é global; `ProjectOverride` mescla rotas e especificações por ID
sem modificar a configuração original. Exemplos versionados não contêm segredos.
Cada tarefa pode ter provider próprio: visual, planning, segmentation e effects.
Os dois últimos possuem contratos, mas nenhum adapter real os implementa ainda;
selecioná-los resulta em erro de capacidade, não em resultado simulado.

## Dados e privacidade

Pydantic valida entradas e saídas, proíbe extras e limita tamanho de payloads.
CreativePlan v1 contém cortes em frames inteiros e rationale, sem IDs de fornecedor.
IDs de assets são mapeados localmente aos originais. Cortes fora dos limites e
observações sobre frames não enviados são recusados. O motor mantém seu JSON v1
com path/hash/tamanho, fps/duração/origem racionais, clips e decisões criativas.

`allow_uploads` apenas habilita a solicitação de consentimento. O grant exige ação
humana explícita e vincula provider/tarefa/destino/hash/tamanho dos bytes exatos
serializados. Dura até cinco minutos, só em memória, e é consumido antes da chamada.
Nenhum retry ou redirecionamento reusa autorização. Texto também exige consentimento.
O Keychain armazena o segredo sob serviço `FinalEditorPro`; projeto guarda apenas
nome da conta. Não há fallback para env, dotenv ou arquivos de credenciais.

O diário de IA registra início/conclusão/falha, modelo/provider/modo/tarefa, hash do
upload, tempo, tokens e estimativa USD quando há preços explícitos. Sem preços/uso
confiáveis, o custo fica desconhecido; não é faturamento reconciliado. Não registrar
prompts, imagens, saídas, chaves ou tokens de consentimento. Journal de IA não pode
desfazer custo remoto; journal de timeline permite estacionar artefatos intactos.

## Integrações e dependências

Runtime Python >=3.11, Pydantic 2.14.1; testes pytest 9.2.0 e xmllint do macOS.
Auditoria inicial e hashes em `docs/DEPENDENCY_AUDIT.md`, `audit/dependencies.json`
e `requirements.lock` (Python 3.15/macOS arm64). Usuário aprovou esses wheels para
instalação/testes na venv. Não houve instalação global nem uso de modelo real.

llama.cpp: subprocesso com binário e GGUF locais de hashes aprovados, flags offline,
ambiente limpo e sandbox-exec obrigatório negando rede/escrita. Sem download ou modo
inseguro alternativo. A interface CLI/saída depende da versão do runtime; validar
binário/modelo reais é o próximo gate, inclusive cache/Metal sob sandbox.

HTTPS: modelo/endpoint configuráveis, JSON mode, schema no prompt e validação local.
Credencial é obtida do Keychain somente depois da autorização. Proíbe redirect e
proxy herdado. Adapters reais não foram exercitados; testes verificam contratos com
mocks, não comprovam qualidade do modelo nem compatibilidade de todo serviço.

ffprobe foi auditado quanto a proveniência/receitas e instalado com aprovação:
Homebrew FFmpeg 9.0.2 revisão 1. A validação com seis MXFs reais e timeline de
cinco clipes está em [docs/REAL_MEDIA_VALIDATION.md](docs/REAL_MEDIA_VALIDATION.md).
O extrator suporta múltiplas fontes mono/estéreo uniformes de 48 kHz, com
relógios/durações compatíveis, declaradas no JSON e no XML. O servidor MCP externo
não é dependência. Seu snapshot foi apenas inspecionado; veja SECURITY_AUDIT.md.

## Preservação audiovisual e capacidades FCPXML

Não renderizamos nem recomprimimos originais. Exportador gera referências locais,
recusa escrita em bibliotecas e exige pasta nova para publicação. Tempos usam
frações exatas, com timecode de fonte distinto de PTS. Fontes precisam ter fps,
resolução e informações de cor compatíveis; versões com relógios ambíguos falham.
Preservar bytes não garante interpretação automática de S-Log3/HDR no editor.

| Recurso | Caminho técnico | Estado |
|---|---|---|
| Cortes, ordem, referências e duração | FCPXML | Implementado |
| Música, marcadores, roles e sincronização | Análise local + decisões XML | Roadmap |
| Transform/keyframes | Parâmetros XML compatíveis | Roadmap |
| Speed ramps | timeMap e render pelo editor | Roadmap com round-trip |
| Transições | Referências a efeitos instalados, handles | Roadmap |
| Cor/LUT | Análise externa + metadados/efeitos compatíveis | Roadmap |
| Máscaras e tracking | Análise/segmentação + efeitos/dados compatíveis por versão | Pesquisa/roadmap |
| VFX complexos | Motion/FxPlug ou derivados externos | Não implementado |

FCPXML descreve decisões; não calcula máscaras nem torna qualquer efeito editável.
Não inventar UIDs/dados opacos. Recursos derivados externos têm editabilidade
interna limitada e precisam de proveniência. DTD oficial 1.10 é o alvo inicial,
sem alegar ser a versão mais recente aceita pelo app.

## Validação e limitações

Testes offline bloqueiam sockets/DNS e usam providers simulados; o subprocesso de
modelo e Keychain real não são executados. DTD valida estrutura; testes também
verificam integridade, referências, limites de cortes e timecodes. Falta round-trip
em biblioteca descartável do Final Cut, benchmark FX3/4K e validação de inferência real.
Leitura de metadados e verificação de pacotes dos MXFs Canon fornecidos já foram
executadas; isso não equivale a validar decodificação integral ou reprodução no editor.

Providers locais são código confiável auditado, não plugins arbitrários: o protocolo
sozinho não cria sandbox para Python de terceiros. O adapter real é quem exige
sandbox do processo local. Hashes não impedem troca concorrente de arquivos após
verificação; não se afirma proteção contra adversário com escrita no workspace.
Diários/publicação ainda não são transações resistentes a toda falha de energia;
preflight de mídia não tem diário persistente completo. Outras limitações do motor
original estão em [docs/ARCHITECTURE_MVP.md](docs/ARCHITECTURE_MVP.md).

Plano verificável: [ROADMAP.md](ROADMAP.md). Uso dos adapters:
[docs/AI_PROCESSING.md](docs/AI_PROCESSING.md).

## Fontes

- [Apple FCPXML](https://developer.apple.com/documentation/professional-video-applications/fcpxml-reference)
- [Apple DTD](https://developer.apple.com/documentation/professional-video-applications/document-type-definition)
- [llama.cpp CLI](https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md)
- [API Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)

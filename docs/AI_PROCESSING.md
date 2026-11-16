# Processamento de IA

## Política de modos

| Modo | Seleção padrão sem rota explícita | Rede de IA |
|---|---|---|
| LOCAL | Primeiro provedor local capaz | Proibida; sem fallback remoto |
| HYBRID | Local capaz; remoto se não existir local ou por rota explícita | Somente com elegibilidade e consentimento por chamada |
| CLOUD | Remoto capaz; local se só ele tiver capacidade | Mesmas exigências de consentimento |

Seleção só escolhe uma vez. Não há retry ou fallback após erro em nenhum modo.
Capacidades não implementadas falham. `media_probe`, `transcode` e `fcpxml_export`
são operações reservadas aos motores locais, recusadas pelo roteador de modelos.
CLOUD não desloca ingestão, montagem, exportação, Keychain ou integração Final Cut.

## Configuração e uso

`config/global.example.json` é um exemplo seguro: LOCAL, uploads negados e adapters
desativados. `load_config(global_path, project_path)` aceita caminhos explícitos;
não escreve no Home nem procura segredos em `.env`. Overrides mesclam `routes`
e `providers` por identificador, substituindo a especificação completa do provider.
Os outros campos substituem o valor global. Mudar modo é uma escolha explícita
de configuração, nunca consequência de falha de inferência.

```python
from final_editor_pro.ai.config import load_config
from final_editor_pro.ai.adapters import build_providers
from final_editor_pro.ai.privacy import PrivacyPolicy
from final_editor_pro.ai.router import ProcessingRouter, OperationJournal

config = load_config('config/global.example.json')
policy = PrivacyPolicy()
providers = build_providers(config, policy)
# O diretório do diário deve existir e deve ficar em logs/ (ignorado).
router = ProcessingRouter(config, providers, OperationJournal('logs/ai.jsonl'))
```

Esse exemplo não executa inferência. Defina modelo e paths/hashes de artefatos
previamente auditados e habilite o provider para usar uma integração real.
Rotas aceitam IDs distintos para `visual_analysis`, `planning`, `segmentation`
e `effect_generation`; os adapters atuais suportam apenas o que anunciam:
llama.cpp = planning; HTTPS = planning/visual_analysis. Os dois últimos contratos
reservam a evolução futura, sem simular execução.

## Consentimento e credenciais

Para uma chamada remota, `allow_uploads=True` permite solicitar consentimento.
`router.preview_upload(task, request)` retorna provider, tarefa, destino,
SHA-256 e tamanho dos bytes serializados. A aplicação deve mostrar também o
conteúdo que o usuário enviará. A confirmação deve vir de uma ação humana;
não de um modelo nem da simples presença de `allow_uploads`.

```python
upload = router.preview_upload(task, request)
# SOMENTE depois da confirmação humana do conteúdo/destino:
consent = policy.approve(upload, confirmed=True)
result = router.run(task, request, consent=consent)
```

O grant dura até cinco minutos, fica só em memória e é consumido antes do envio,
mesmo se a chamada falhar. Mudanças de tarefa, modelo, destino ou conteúdo exigem
nova confirmação. Nenhum retry, redirect HTTP ou proxy herdado do ambiente.
Textos também são uploads; nunca presumir que briefings/evidências são públicos.
Não foi enviado conteúdo real a nenhum serviço nesta entrega.

`MacOSKeychain.set(account, secret)` e `.get(account)` usam Security.framework;
o serviço é `FinalEditorPro`. A configuração armazena somente o nome da conta.
Uma interface deve obter a chave por entrada oculta (por exemplo `getpass`),
nunca por argumento de shell. Não configuramos ou modificamos o Keychain real
durante os testes. O macOS pode solicitar autorização no primeiro acesso real.

## Modelos e dados

Todos os inputs/outputs de tarefas usam schemas Pydantic com campos extras
proibidos. Planejamento recebe IDs/frames, sem caminhos de mídia; o plano criativo
contém cortes/rationale independentes de fornecedor. O adaptador `apply_plan`
traduz esse plano para o JSON do motor existente. Limites de fonte são verificados
antes da exportação; saída de modelo não é código executável.

O endpoint opcional usa Chat Completions, JSON mode e schema no prompt; a validação
local é obrigatória. Compatibilidade do modelo escolhido, limites e qualidade de
visão precisam de teste real. Segmentação e geração/render de efeitos não existem.

## Offline e custos

Funcionam offline: configuração, schemas, seleção, planejamento determinístico,
Timeline Engine, FCPXML e testes. Probe é local após instalação aprovada de ffprobe.
Inferência llama.cpp exige binário/GGUF pré-provisionados: subprocesso com ambiente
limpo, hashes verificados, flags offline e sandbox macOS negando rede e escrita.
O sandbox é obrigatório e pode limitar caches/Metal; erro não permite execução
sem sandbox. Nenhum modelo real foi carregado nesta etapa.

Rede: provider HTTPS após consentimento; obtenção manual de dependências/modelos
fora do processamento LOCAL exige aprovação própria. Testes Python bloqueiam
sockets/DNS e mockam subprocessos de inferência; não comprovam isolamento de todo
plugin arbitrário. Providers locais registrados são código confiável e precisam
de auditoria; não há plugin loader de terceiros.

O journal registra início/conclusão/falha, modo, tarefa, provider, modelo, hash do
upload, tempo e tokens/custo quando disponíveis. Não inclui conteúdo nem chaves.
Taxas explícitas no construtor CloudProvider permitem estimar USD por milhão;
sem taxas o custo é `unknown`, nunca zero inventado. Zero local significa custo
de API zero, sem medir energia/hardware. Erros podem ter custo remoto não apurado;
taxas podem ser configuradas por provider em `input_usd_per_million` e
`output_usd_per_million`; reconciliação de fatura fica no roadmap.

# Final Editor Pro

Edição não destrutiva de vídeo com planejamento por IA e timeline editável no
Final Cut Pro via FCPXML. Repositório: https://github.com/emnovais/FinalEditorPro

O MVP monta sequências simples na ordem de entrada, mantém decisões em JSON,
valida referências e tempos racionais e exporta FCPXML 1.10. A infraestrutura de IA
oferece modos LOCAL, HYBRID e CLOUD, seleção por capacidade, schemas Pydantic,
consentimento por upload e credenciais no macOS Keychain.

O MVP 0.2 acrescenta o [AI Video Analyzer](docs/ANALYZER.md): amostragem temporal,
detecção de cenas aproximada, métricas técnicas, scoring explicável, cache e
análise multimodal local. Uma execução real foi demonstrada com Qwen3-VL 4B;
[resultados e benchmark](docs/ANALYZER_VALIDATION.md). Nenhuma decisão do Analyzer
é aplicada automaticamente ao FCPXML.

O incremento [0.2.1 — Model Benchmark & Evaluation](docs/EVALUATION.md) acrescenta
entradas congeladas, repetições cold/warm, revisão cega e pesos configuráveis
25/25/20/15/10/5. [Resultados do piloto](docs/EVALUATION_VALIDATION.md): a comparação
de qualidade permanece inconclusiva até completar referências/revisão humanas.

O [MVP 0.3 — AI Creative Director](docs/CREATIVE_DIRECTOR.md) acrescenta briefing,
seleção, planejamento local, análise musical inicial, EDL e montagem editável.
[Validação real e aprovação manual](docs/CREATIVE_DIRECTOR_VALIDATION.md).
Por decisão do usuário, não haverá nova rodada de benchmark/revisão cega agora;
Qwen3-VL 8B e Gemma 3 12B permanecem disponíveis sem vencedor declarado.

**Estado:** MVP 0.3 aprovado manualmente no Final Cut Pro em 17/11/2026: cortes,
slow motion 50%, música, 20 segundos e 3840×2880/4:3/25 fps confirmados.
Testes offline e análise multimodal local real aprovados nesta amostra.
Providers são opcionais e desativados por padrão; APIs remotas não foram validadas
em execução real. Não há VFX, segmentação de objetos,
tracking, correção de cor ou importação automática no Final Cut implementados.

## Desenvolvimento com Codex

Leia [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md) e
[ROADMAP.md](ROADMAP.md). Python >=3.11; ambiente validado nesta inicialização:
Python 3.15/macOS Apple Silicon. `requirements.lock` fixa os wheels aprovados
para essa combinação. Outra plataforma exige lock/auditoria próprios.

Após aprovação da auditoria em [docs/DEPENDENCY_AUDIT.md](docs/DEPENDENCY_AUDIT.md):

```sh
python3 -m venv .venv
# Instalação reproduzível de wheels, sem build de código-fonte:
.venv/bin/python -m pip install --only-binary=:all: --require-hashes -r requirements.lock
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Nesta máquina os wheels foram instalados de `audit/wheels/` com `--no-index`.
Essa pasta, a venv e os fontes externos auditados ficam locais e não são enviados
para o GitHub. O projeto pode ser executado da raiz sem instalação editable.

## Uso do motor de timeline

A extração de metadados requer ffprobe previamente auditado/aprovado. Nesta máquina,
FFmpeg/ffprobe 9.0.2 foi instalado com autorização e validado com MXFs reais;
veja [o relatório](docs/REAL_MEDIA_VALIDATION.md). Use clipes de teste e pasta nova:

```sh
.venv/bin/python -m ave.cli build /caminho/testes/clip.mov \
  --ffprobe /caminho/absoluto/ffprobe --output /caminho/workspace/run-001
```

Saídas: `project.json`, `timeline.fcpxml` e `operations.jsonl`. O pai precisa existir;
a pasta de saída não pode existir. Há recusa de formatos/relógios ambíguos, hashes
de integridade e reversão dos artefatos sem apagar originais.
[Guia detalhado do MVP](docs/MVP.md).

## Processamento de IA

[Configuração, consentimento e integrações opcionais](docs/AI_PROCESSING.md).
Exemplos seguros em `config/`; nenhum contém chaves ou modelos baixados.

| Modo | Comportamento |
|---|---|
| LOCAL | Apenas provedores locais; nenhum fallback remoto |
| HYBRID | Mídia local, modelos selecionáveis; uploads exigem consentimento |
| CLOUD | Prefere modelos remotos; IO, timeline e exportação continuam locais |

O protocolo é independente do fornecedor. Planejamento gera `CreativePlan` JSON,
traduzido para a timeline sem alterar o motor/exportador. Testes usam provedores
simulados; adapters opcionais usam llama.cpp/GGUF local ou HTTPS compatível com
Chat Completions. O roteador não instala, baixa modelos nem aprova uploads sozinho.

## Garantias e verificação

- Originais somente leitura; nenhum processamento sobre bibliotecas existentes.
- Importação futura manual em biblioteca de teste separada; nenhum editor é aberto.
- LOCAL impede seleção remota. Adaptador llama.cpp exige sandbox macOS sem rede.
- Credenciais somente no Keychain; diário registra provedores, tokens e custos
  estimados quando disponíveis, sem inventar valores ausentes.
- Testes cobrem XML/DTD oficial, mídia/timecodes/integridade, modos, overrides,
  consentimento, ausência de chamadas de rede e fronteiras de integração.

XML válido pela DTD não comprova importação correta. Não foi feito round-trip no
Final Cut nem benchmark 4K. Leia os limites em ARCHITECTURE.md antes de usar mídia real.

# Final Editor Pro — roadmap

## Etapa 1 — concluída nesta inicialização

- MVP determinístico preservado: metadados, JSON, timeline e exportador FCPXML.
- Modos LOCAL/HYBRID/CLOUD, configuração global e override por projeto.
- AIProvider Protocol, LocalProvider, CloudProvider e ProcessingRouter.
- Contratos Pydantic para visual/planning/segmentation/effects; implementação
  de VFX/segmentação continua ausente e adapters não anunciam essas capacidades.
- Consentimento efêmero por upload, Keychain, journal e custos estimados/desconhecidos.
- Testes com provedores simulados e bloqueio de sockets/DNS.
- Adapters opcionais escritos: llama.cpp local e endpoint HTTPS compatível com
  Chat Completions. Não validados contra modelos/serviços reais.

## Etapa 2 — inferência real e entrada de mídia

Auditar binário llama.cpp e modelo GGUF, identificar versão/licença/hash, obter
aprovação e medir planejamento real no Mac. Sem download automático. Auditar
ffprobe e validar clipes FX3 de teste. Validar o sandbox macOS com inferência real;
se indisponível, falhar sem modo inseguro. Não prometer compatibilidade universal
de CLI/modelo sem essa execução.

Configurar uma conta de API no Keychain e escolher modelo/endpoint. Somente após
consentimento específico executar uma chamada pequena e registrar tokens/custo.
Testar recusas, timeouts, JSON inválido e restrições de privacidade do serviço.

## Etapa 3 — Final Cut e análise audiovisual

Biblioteca descartável e teste de round-trip. Validar timecodes, áudio, cor S-Log3,
fps fracionários e links dos originais. Depois: proxies locais, batidas, cenas,
transcrição, evidências com timestamps e visão local real.

## Etapa 4 — planejamento editorial

Avaliações com briefings e timelines de referência, budgets e tabela de preços
versionada; UI de revisão/consentimento, cancelamento e ledger robusto a falhas.
Configuração de perfis por projeto sem chaves. Não automatizar aprovação por IA.

## Etapa 5 — efeitos graduais (preservada)

Áudio conectado e sincronização musical → transforms/keyframes → transições com
handles → speed ramps → Motion/cor → segmentação/máscaras → tracking.
Cada capacidade exige fixtures e round-trip no editor antes de ser anunciada.
Efeitos externos usam recursos derivados e registram perda de editabilidade interna.

## Etapa 6 — operação e integrações

Persistência transacional, reconciliação de custos/faturas, logs também de
preflight/probe, sandbox de arquivos mais restrito e auditoria de providers.
MCP opcional com allowlist mínima, sem importação automática em bibliotecas reais.

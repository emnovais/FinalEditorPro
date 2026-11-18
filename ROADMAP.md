# Final Editor Pro — roadmap

## Base validada e próximo incremento

MVP de timeline confirmado pelo usuário no Final Cut, incluindo a versão
corrigida do formato de sequência. Base versionada: `a1e457e`.
Preparação do MVP 0.2: [plano e critérios de aceite](docs/MVP_0_2_PLAN.md).
A prioridade foi definida: AI Video Analyzer. Pipeline determinístico e uma
análise multimodal local real foram demonstrados; detalhes e limites em
[docs/ANALYZER_VALIDATION.md](docs/ANALYZER_VALIDATION.md). Sem commit/push automático.

## MVP 0.3 — AI Creative Director (concluído e aprovado manualmente)

[Arquitetura/uso](docs/CREATIVE_DIRECTOR.md) e
[validação real](docs/CREATIVE_DIRECTOR_VALIDATION.md). Briefing, seleção,
planejamento, música local, EDL, retime linear, crop central e FCPXML integrado.
Aprovação manual do usuário em 17/11/2026: importação, cortes, slow motion 50%,
música, 20 s e 3840×2880/4:3/25 fps confirmados. Commit local autorizado;
push depende de autorização separada. Por decisão explícita
do produto, sem novo benchmark ou revisão cega agora; Qwen3-VL 8B e Gemma 3 12B
permanecem disponíveis, sem vencedor. A comparação quantitativa anterior não é
reinterpretada como conclusiva.

Próximo incremento: revisar continuidade/framing, refinar ações completas e cortes
com feedback humano, melhorar onsets/tempo e mix, testar round-trip de retime/música,
validar planejamento Gemma no fluxo real e só então ampliar formatos/efeitos.
Máscaras, tracking, transições automatizadas e VFX permanecem no roadmap.

## MVP 0.4 — Intelligent Editing & Continuity (encerramento técnico)

Continuidade explicável, reframing estático, refinamento de cortes, eventos
musicais e ganho/fades editáveis implementados, com montagem real e preview.
Gemma 3 12B exercitado como planejador; sem novo benchmark ou vencedor.
[Relatório](docs/INTELLIGENT_EDITING_VALIDATION.md). Recebidos round-trip nativo,
importação sem erros e feedback visual positivo para a revisão de seis takes.
A reconciliação BWF eliminou a espera inicial no teste manual e está incorporada.
O usuário aprovou visualmente o marco. [Encerramento técnico](docs/MVP_0_4_CLOSEOUT.md):
BWF em produção, consolidado equivalente ao teste A exceto pelo nome, 133 testes
aprovados e limites do round-trip explícitos. Nenhum bloqueador técnico real
identificado para esta montagem. O commit/push anterior foi executado em `f4dca7c`;
o commit documental local de encerramento foi autorizado em 18/11/2026.
Não há autorização de push, merge ou alterações na main nesta tarefa.

Depois: validar feedback de enquadramento/mix, melhorar ações semânticas e
continuidade, decidir prioridade de tracking e crossfades com handles. Máscaras,
transições automáticas, speed ramps e VFX seguem graduais, com testes de round-trip.

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

### Validação posterior da revisão de seis takes

Recebidos: importação sem erros, melhora visual e keyframes funcionando; o teste A
resolveu a demora inicial, e a correção BWF está incorporada. Consolidado em
`workspace/director-0.4/revision-unique/final-bwf/`. Não executar commit/push sem
nova autorização. Relatório: [investigação de startup](docs/FCPXML_STARTUP_INVESTIGATION.md).

Autorização atual em 17/11/2026: registrar e publicar as alterações acumuladas
na branch `develop/mvp-0.4-intelligent-editing`. As notas anteriores de espera por
autorização são históricas; não impedem este commit/push solicitado.

### Estado do encerramento atual

A autorização de publicação registrada anteriormente já foi executada. Em
18/11/2026, o usuário aprovou o encerramento e autorizou somente o commit local
da documentação na branch de desenvolvimento. Não realizar push, merge ou
alterações na main. Nenhuma funcionalidade adicional implementada.

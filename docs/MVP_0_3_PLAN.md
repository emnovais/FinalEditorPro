# MVP 0.3 — plano e decisões

Preservar `ave/core.py`, contratos e testes anteriores. O novo pacote `director/`
encapsula briefing, seleção, planejamento, refinamento, música, EDL e exportação.
Não repetir benchmark ou revisão cega: decisão de produto do usuário. Qwen3-VL 8B
e Gemma 3 12B permanecem selecionáveis; confirmação do conteúdo pelo usuário não
é convertida em um ranking quantitativo nem em novos eventos humanos exatos.

Etapas verificáveis:

1. Contratos Pydantic e relógios racionais; suites anteriores preservadas.
2. Candidatos por intervalos locais limitados, relatórios Analyzer e interpretações
   multimodais separadas; sem tratar evidências de 1 fps como fronteiras de ação.
3. Planejamento textual com tarefas próprias no ProcessingRouter; sem fallback.
4. Música local com FFmpeg e biblioteca padrão; heurísticas de envelope, onsets,
   autocorrelação, intensidade; nenhuma dependência nova.
5. Distribuição de duração exata, sincronização opcional com alguns onsets,
   refinamento de frames adicionais nas entradas/saídas.
6. Adaptador EDL → exportador original → ajustes explícitos de sequência,
   crop/fill, conform de cadência, timeMap linear e música conectada.
7. Testes, execução real local, DTD oficial, relatório e importação manual.

Briefing autorizado: montagem de casal, 20 s, 3840×2880 (4:3), crop central com
upscale, timeline 25 fps, ritmo equilibrado, música do workspace e slow motion
nos momentos emocionalmente relevantes. Fontes 3840×2160/50 fps preservadas.
Estilo proposto romântico a partir do pedido de momentos emocionantes; não é
uma análise automática do gênero/atmosfera da música. Câmera lenta usa 50% sem
interpolação óptica, áudio de câmera desativado nesses trechos; normais preservam
áudio de fonte. Música a -12 dB como mix provisório editável.

Validação nova no Final Cut é obrigatória: DTD não garante semântica de importação,
framing do crop, retime ou apreciação estética. Não anunciar esse caminho como
validado manualmente antes do usuário importar. Nenhum commit/push automático.

## Encerramento

Plano executado; MVP 0.3 aprovado manualmente pelo usuário em 17/11/2026.
Confirmações e limites em [CREATIVE_DIRECTOR_VALIDATION.md](CREATIVE_DIRECTOR_VALIDATION.md).
Commit local de conclusão autorizado; nenhum push sem autorização separada.

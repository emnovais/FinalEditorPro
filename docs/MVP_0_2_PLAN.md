# MVP 0.2 — AI Video Analyzer

Escopo substitui a proposta anterior de planejamento. Base validada: a1e457e. Runtime/pesos aprovados pelo usuário e análise local
real demonstrada; resultados em [ANALYZER_VALIDATION.md](ANALYZER_VALIDATION.md).
Não modificar o exportador FCPXML, as mídias ou bibliotecas do Final Cut.

## Arquitetura e etapas

1. Ingestão reutiliza ave.cli.probe/ave.core.metadata. JSON MediaAsset conserva
   hash, streams, fps racional e orientação suportada. Arquivos ambíguos falham.
2. Extração local FFmpeg, em resolução reduzida e com índices de frame racionais.
   Frequência e orçamento de frames configuráveis; cache por SHA/config/tool hash.
3. Detecção determinística de mudanças por histogramas + mudança de pixels,
   persistência temporal e duração mínima. Limite de precisão igual ao intervalo
   de amostragem; não anunciar cortes frame-exatos sem varredura complementar.
   PySceneDetect AdaptiveDetector e FFmpeg scdet foram investigados; a primeira
   opção requer dependências adicionais. A abordagem inicial não as instala.
4. Métricas de luminância, extremos, variância do Laplaciano, diferenças e
   movimento aparente. São indicadores, não descarte nem julgamento criativo.
5. Novo contrato semântico temporal, integrado ao roteador existente. Saída inclui
   evidências/limitações e incerteza; múltiplos frames por segmento quando possível.
6. Scoring com componentes separados, pesos por perfil e justificativas. Relevância
   narrativa/ação permanecem desconhecidas sem análise semântica; nunca inventar.
7. Relatório Pydantic versionado, cache separado da fonte, diário sem prompts e
   benchmark com tempos/RSS medidos. Nenhuma decisão de edição aplicada ao XML.
8. Integração real opcional: candidato Ollama + Qwen3-VL 4B Instruct quantizado,
   após auditoria/aprovação. Servidor em loopback, pesos locais, cloud desabilitado,
   sandbox negando conexões não locais. Preparação/download separados da inferência.
9. Validar ao menos um vídeo real com o modelo local. Testes com mocks não encerram
   o MVP. Relatar exatamente o que falhar ou permanecer pendente.

## Decisões e riscos

- Sem NumPy/Pillow/PySceneDetect na primeira etapa: Python padrão + FFmpeg já
  auditado. Conversão RGB/PNG e métricas pequenas não exigem instalação adicional.
- MLX-VLM é alternativa Apple Silicon; a árvore observada inclui MLX, Transformers,
  OpenCV e bibliotecas de áudio/servidor, com compatibilidade Python 3.15 a verificar.
- Ollama permite runtime independente do Python do projeto e formato JSON schema.
  Loopback é comunicação local entre processos, não upload externo.
- Modelos de 4B quantizados são candidatos aos 36 GB informados; memória real,
  contexto e latência serão medidos, não prometidos. Limitar frames/contexto.
- Luminosidade em Log e motion blur intencional podem distorcer heurísticas.
- Pans, flash, mudanças de iluminação e cortes entre composições parecidas podem
  confundir o detector. Reportar método, limiares e resolução temporal.
- O modelo pode alucinar. Cada observação deve indicar frames de evidência e
  confiança autodeclarada (não calibrada); proibir extrapolar áudio/identidades.
- LOCAL não seleciona provider remoto. HYBRID/CLOUD reutilizam grants por payload;
  nenhuma autorização de upload ou instalação é inferida deste plano.

## Gate de aprovação

Instalar runtime e baixar pesos exige autorização específica após auditoria de
receitas, origem, licenças e digests. Sem essa aprovação, continuar somente o
pipeline determinístico e testes; não declarar integração real concluída.
Sem commit/push automático. Versão 0.2.0 apenas após critérios de aceite satisfeitos.

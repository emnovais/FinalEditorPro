# MVP 0.2.1 — Model Benchmark & Evaluation

Base inspecionada: 7c4ad63, main limpa e sincronizada no início. Backend real:
llama-server incluso no Ollama standalone v0.40.16, sandbox local, contexto 8192.
O benchmark 0.2 anterior mede uma execução e cache de relatório; não é comparação
estatística entre modelos nem mede warm inference sem cache de relatório.

## Etapas

1. Auditar candidatos, licenças e manifestos; pedir aprovação antes de pesos novos.
2. Dataset versionado por hash e intervalos em frames, grupos de origem e splits
   development/evaluation disjuntos. Categorias desconhecidas e anotações humanas
   permanecem pendentes. Nunca gerar ground truth a partir da resposta do modelo.
3. Congelar entradas: mesmos PNGs/hashes/ordem/timestamps, prompt e schema de saída.
   Comparar somente sequências de frames equivalentes; não anunciar vídeo nativo.
4. Runner local: pelo menos três sessões por modelo; primeiro pedido cold inference,
   segundo pedido warm inference real. Nenhuma leitura de cache de relatório para
   esses pedidos. Cache hit é uma terceira condição separada, sem inferência.
5. Registrar startup (inclui verificação de hashes), latência, sucesso/falha,
   timeout, tokens quando reportados e RSS amostrado. Mediana, IQR e min/max;
   não tratar RSS como memória GPU/unificada total. Sem retry silencioso.
6. Pacote de revisão cega sem IDs de modelo, revisado por humano. Mapa separado
   para revelar depois. Rubricas visual/temporal/confiabilidade/criatividade,
   afirmações sem evidência e verificações objetivas contra rótulos humanos.
7. Classificação com pesos 25/25/20/15/10/5, sem renormalizar métricas ausentes.
   Preservar seis componentes, cobertura e trade-offs; nenhum vencedor automático.
8. Validação real dos modelos aprovados, documentação e conclusão inconclusiva
   até haver anotações humanas/dataset e revisão final suficientes.

## Gates e limitações

Os vídeos locais atuais são seis clipes da mesma sessão aparente; não representam
as oito categorias pedidas. Não atribuir categorias baseando-se só em nomes ou IA.
Não colocar partes do mesmo grupo em development e evaluation. Enquanto o humano
não definir grupos/splits, os casos são apenas desenvolvimento exploratório.

Qwen3-VL 4B é baseline carregado; 8B compartilha arquitetura, mas precisa de smoke
test neste runtime. Gemma 3 4B/12B suporta imagens e consta no backend upstream;
compatibilidade do artefato quantizado/projetor precisa de teste real. As três
opções novas somam ~17,7 GB de download; isso não estima RAM. Uma instância por vez,
contexto 8192 e quatro frames reduzidos para limitar consumo nos 36 GB informados.
Qwen: Apache-2.0. Gemma 3: termos próprios Google, não Apache-2.0.

Nenhuma nova dependência é necessária. Preserve Analyzer schemas/relatórios 0.2,
exportador e bibliotecas FCP. Sem APIs externas de inferência, commit/push automático
ou promoção automática de modelo à configuração de produção.

O anexo fornecido termina truncado em "Não modificar o exportador F". O plano
preserva integralmente o exportador já validado e não presume requisitos adicionais.

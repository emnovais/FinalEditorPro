# MVP 0.4 — Intelligent Editing & Continuity

Base preservada: `165e2cb`, MVP 0.3 aprovado manualmente, 93 testes. Desenvolvimento
isolado em `develop/mvp-0.4-intelligent-editing`. Nenhum commit/push autorizado.

A camada `editing/` recebe uma EDL validada do Director. Mantém a EDL executável
0.3 dentro de um pacote versionado 0.4 com evidências, decisões e controles novos.
Não modifica `ave/core.py` ou o comportamento padrão do exportador 0.3.

Etapas:
1. Schemas e cache de frames locais com índices exatos/hashes. Features de
   luminância, histograma, composição e movimento aparente; não confundir movimento
   global de imagem com identificação física do movimento da câmera.
2. Continuidade por componentes com pesos explícitos e opt-out para cortes
   intencionais. Otimização limitada preserva abertura, highlight e encerramento.
3. Reframing determinístico para 16:9, 9:16, 4:3 e 1:1 usando apenas caixas
   comprovadamente retornadas por detector local ou anotações identificadas.
   União conservadora de pessoas, margens e estabilidade; fallback central com alerta.
4. Amostragem adicional e estratégias de corte por movimento aparente, com
   candidatos de eventos sem promover evidências amostradas a ações exatas.
5. Música: onsets, batidas ancoradas em ataques observados, intensidade, pausas e
   mudanças de seção aproximadas. Sincronização limitada pelo ritmo/duração.
6. Mixagem não destrutiva: ganhos, fades, envelopes opcionais de ducking por
   prioridade explícita. Headroom conservador e medição de pico do preview.
   Crossfade com sobreposição de handles só será anunciado se implementado/validado.
7. Adaptador XML adicional: transformação estática de crop e volume com envelopes.
   Preview local correspondente; não render final ou garantia estética.
8. Planejamento real Gemma via pipeline existente, sem novo benchmark. Comparação
   com a montagem 0.3, testes novos e preparação de round-trip manual.

Biblioteca padrão, FFmpeg e modelos já aprovados. A opção de detector usa Vision
nativo do macOS por pequeno helper Swift próprio: revisar o código e a assinatura
Apple do compilador instalado antes de compilar. Nenhum pacote/modelo baixado.
Execução do detector com rede negada; indisponibilidade resulta em fallback sinalizado.
Referências Apple serão registradas no documento de auditoria local.

Critérios: nova montagem real, DTD e consistência EDL/XML; ganho mensurável em
continuidade, fronteiras ou alinhamento musical sob a mesma métrica, sem chamar
isso de melhoria estética comprovada. Importação e round-trip aguardam o usuário.

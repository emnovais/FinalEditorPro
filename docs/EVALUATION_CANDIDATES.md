# Auditoria de candidatos — MVP 0.2.1

Data: 16/11/2026. Baseline real: Qwen3-VL 4B Instruct Q4_K_M, runtime
llama-server do Ollama standalone oficial v0.40.16, já aprovado. Não é o daemon
Ollama e não será instalado outro backend nesta etapa.

| Candidato | Origem/licença | Download publicado | Estado inicial |
|---|---|---:|---|
| Qwen3-VL 4B Instruct | Qwen/Apache-2.0 | já disponível | baseline carregado no MVP 0.2 |
| Qwen3-VL 8B Instruct | Qwen/Apache-2.0 | 6.190.971.589 bytes | requer teste real |
| Gemma 3 4B | Google/Gemma Terms of Use | 3.350.272.259 bytes | requer teste real |
| Gemma 3 12B | Google/Gemma Terms of Use | 8.164.039.587 bytes | requer teste real |

Manifestos oficiais do registry Ollama foram consultados e preservados em
`temp/evaluation-audit/`; somente metadados/licenças foram baixados antes da
aprovação. SHA das licenças conferido contra os manifests. O usuário aprovou
baixar e validar os três modelos, incluindo o aviso sobre termos próprios Gemma.
Não houve autorização para dataset externo ou inferência remota.

Digests dos manifests:

- Qwen3-VL 8B: 70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb.
- Gemma 3 4B: 68ceab7e468a31c988b44d5a4984a0e21f58c4f7158c6ce29c1804babac38df7.
- Gemma 3 12B: b92b218582c521ba287f38f1d6057dcd3c6cbff036f13cac97b5d861f5e58ec3.

Cada camada/config é verificada por digest/tamanho antes de carregar. Pesos e
projetores ficam em workspace/ollama-models/; manifests de execução usam o mesmo
binário/bibliotecas aprovados. Nenhum peso ou credencial é versionado.

## Compatibilidade e memória

Qwen3-VL declara imagens/vídeo na família; esta avaliação usa exclusivamente
frames ordenados com timestamps, não o caminho de vídeo nativo. Gemma 3 4B e
12B aceitam texto/imagens; compreensão temporal será avaliada pela mesma sequência,
sem atribuir a eles uma modalidade de vídeo que o adapter não utiliza.
A documentação upstream llama.cpp lista Gemma 3 4B/12B e o runtime existente já
carregou Qwen3-VL 4B. Qwen3-VL 8B compartilha arquitetura, mas cada combinação
GGUF/projetor deve passar no preflight antes de ser incluída em medições.

Os tamanhos acima são de artefatos, NÃO RAM necessária. Os 36 GB informados sugerem
viabilidade para investigação quantizada, sem garantia: encoder, KV cache,
contexto e outros processos também consomem memória. Carregar um modelo por vez,
contexto 8192, um slot e mesmas quatro imagens reduzidas. Registrar RSS observado
em vez de inventar memória GPU/unificada. Diferenças de quantização/encoder são
registradas pelo metadata do runtime, não ocultadas pela tabela de parâmetros.

Não adicionar candidatos extras nesta rodada: o conjunto inicial já contrasta
duas famílias e dois tamanhos por família, sem ampliar downloads sem justificativa.

## Limites da auditoria

Revisão de origem, manifests, licença, suporte publicado e compatibilidade prática.
Não é auditoria integral de pesos ou código nativo. Hash garante integridade
relativa à origem, não ausência de bugs. O sandbox anterior é preservado, sem
fallback de nuvem, ferramentas ou rede externa durante a inferência.

Fontes oficiais:
- https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
- https://ai.google.dev/gemma/docs/core/model_card_3
- https://ai.google.dev/gemma/terms
- https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md
- https://ollama.com/library/gemma3/tags
- https://registry.ollama.ai/v2/library/qwen3-vl/manifests/8b-instruct
- https://registry.ollama.ai/v2/library/gemma3/manifests/4b
- https://registry.ollama.ai/v2/library/gemma3/manifests/12b

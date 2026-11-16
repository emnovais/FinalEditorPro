# Auditoria inicial do runtime multimodal — 16/11/2026

Nenhum runtime ou peso executado nesta auditoria. Metadados/fontes em
`temp/analyzer-audit/`, ignorado pelo Git.

## Opção selecionada para aprovação

Ollama standalone oficial v0.40.16 (MIT), arquivo ollama-darwin.tgz, 186.116.182
bytes. Digest publicado na API de release oficial GitHub:
`a743717494315da7cd352982b805f6b992d4b4452ca117fd5fbf86c4ee46fca0`.
Usar extração local em `workspace/tools/`, sem app GUI, daemon persistente,
Homebrew ou alteração do Python. Inspecionar paths/symlinks e verificar o hash
antes de executar. Binários nativos não são auditáveis integralmente por inspeção
estática; origem e hash não são garantia de ausência de vulnerabilidades.

Foram revisados envconfig/config.go e rotas do servidor no tag oficial, flags
OLLAMA_NO_CLOUD, OLLAMA_MODELS e binding de host. Servidor dedicado em 127.0.0.1,
com sandbox macOS negando conexões externas, sem proxy herdado, sem cloud models
ou ferramentas, sem envio de mídia. Downloads são etapa separada, antes de
qualquer frame ser entregue ao servidor. Processo encerrado após a validação.

A alternativa Homebrew foi inspecionada: dependências MLX e Python poderiam
atualizar o ambiente existente. Não será instalada para esta primeira validação.
MLX-VLM também foi pesquisado; mais dependências e compatibilidade Python 3.15
seriam um gate adicional. Nenhum desses pacotes Python será instalado agora.

## Modelo proposto

Qwen3-VL 4B Instruct Q4_K_M, Apache-2.0. Manifesto oficial registry.ollama.ai:
`84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318`.
Download de camadas: **3.337.225.445 bytes** (~3,34 GB), além do runtime.
Modelo: `3a859c4dca6883593e389a08987f04762f2a374d475cabc1538360473a72b1da`.
Projetor: `70ac570fd36b65a64fbb99883c34d5196368c1cf8f63d8402802a34a0ed2b363`.
Licença e parâmetros pequenos foram baixados como texto e os hashes conferidos.
Pesos ainda não baixados. Validar todas as camadas antes de carregá-las.

36 GB informados tornam esse tamanho um candidato razoável, sem prometer uso
real de memória ou velocidade; contexto/imagens também consomem memória.
Confiança gerada pelo modelo não é calibrada. Registrar amostragem e incerteza.

## FFmpeg e pipeline determinístico

FFmpeg 9.0.2 já foi instalado/autorizado e sua proveniência foi revisada na etapa
anterior (FFPROBE_AUDIT.md). Será usado para leitura local e extração de imagens
reduzidas em cache, nunca reescrita de fontes. Não adicionar dependências Python
para esse caminho. Os schemas/testes usam Pydantic/pytest já aprovados.

Fontes:
- https://github.com/ollama/ollama/releases/tag/v0.40.16
- https://github.com/ollama/ollama/blob/v0.40.16/envconfig/config.go
- https://docs.ollama.com/api/chat
- https://ollama.com/library/qwen3-vl:4b-instruct
- https://www.scenedetect.com/docs/latest/api/detectors.html
- https://github.com/Blaizzy/mlx-vlm/blob/main/requirements.txt

## Resultado após aprovação

O usuário aprovou download e validação local. Artefato oficial conferido pelo
SHA publicado e extraído com filtro de paths/links; todas as camadas do modelo
(incluindo config, licença e parâmetros) conferidas por digest/tamanho.

A revisão de cmd/cmd.go mostrou que `ollama serve` chama initializeKeypair e
escreve ~/.ollama/id_ed25519. Esse servidor não foi iniciado. Foi usado o
`llama-server` incluso no mesmo artefato oficial aprovado, com pesos GGUF e
projetor já conferidos, sem identidade de conta. O manifest local registra hashes
de binário/modelo/projetor e 33 bibliotecas, verificados pelo launcher.

Uma primeira sintaxe de sandbox com IP numérico foi recusada pelo macOS antes de
iniciar o servidor. A forma aceita usa localhost nos filtros, mantendo binding
real em 127.0.0.1. A prova executada sob o mesmo perfil negou connect para endereço
de documentação TEST-NET-1 com PermissionError antes de qualquer transmissão.
O helper de produção não possui fallback sem sandbox e não usa redirecionamentos.

A execução gerenciada confirmou suporte multimodal, produziu relatório real e
encerrou o processo. Nenhum download/pull foi usado durante a inferência.
Os downloads de artefatos foram feitos antes de enviar frames ao processo local.
Não foi alterado o Python do sistema nem armazenada credencial em arquivo.

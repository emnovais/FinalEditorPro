# Auditoria inicial de FFmpeg/ffprobe — 16/11/2026

O usuário autorizou a instalação via Homebrew e a exceção de escrita fora do
projeto necessária para `/opt/homebrew`. Não autorizou alterações em mídia.

Inicialmente ffprobe estava ausente do PATH e dos caminhos usuais verificados.
Homebrew já estava presente em `/opt/homebrew/bin/brew`. A fórmula oficial
`homebrew/core/ffmpeg` inclui ffprobe; consultada nesta data: 9.0.2, revisão 1.

Escopo estático anterior à instalação: metadados e fontes Ruby das 15 fórmulas
FFmpeg + dependências transitivas de runtime; SHA-256 de cada fonte conferido
com o publicado na API oficial. Dados completos e fontes preservados localmente
em `temp/mvp-validation/homebrew-audit/` (ignorado pelo Git). Conferidos URLs,
checksums das bottles, instruções de instalação, serviços e post-install.
Nenhum serviço declarado. FFmpeg não possui post-install; openssl e ca-certificates
possuem etapas de configuração de certificados sob prefixo Homebrew. A última lê
certificados públicos confiáveis dos Keychains do sistema, não senhas de APIs.

A instalação deve usar bottles oficiais e verificação de hash pelo Homebrew,
sem compilação de fontes, auto-update, analytics ou limpeza automática. Caches
principais e logs são direcionados para `temp/` do projeto. Instalações e links
sob `/opt/homebrew` são a exceção autorizada; metadados internos do gerenciador
podem existir fora do projeto. Nenhum servidor MCP ou modelo de IA será executado.

Esta é uma revisão de proveniência/receitas e superfície de instalação, não uma
auditoria completa dos fontes C/C++, do Homebrew inteiro ou dos binários. Hashes
publicados fornecem integridade relativa à origem; não provam ausência de bugs.

Na validação, somente ffprobe será usado: leitura de arquivos locais, protocolo
`file`, sem shell nem upload. Hashes dos seis originais foram registrados antes
em `temp/mvp-validation/originals-before.json`; devem ser conferidos no término.

Fontes oficiais:
- https://formulae.brew.sh/formula/ffmpeg
- https://formulae.brew.sh/api/formula/ffmpeg.json
- Fontes Ruby fixadas por commit e hashes no inventário local.

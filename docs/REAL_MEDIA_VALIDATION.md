# Validação do MVP com mídia real — 16/11/2026

Status: extração real e geração/validação externa do FCPXML concluídas.
Importação, reprodução e round-trip no Final Cut pendentes de validação manual.
Nenhum commit ou push realizado nesta etapa.

## Ambiente e autorização

Revisados AGENTS.md, SECURITY_AUDIT.md, ARCHITECTURE.md, código e testes.
ffprobe inicialmente ausente. O usuário disponibilizou os clipes após a primeira
inspeção e aprovou instalar FFmpeg via Homebrew, incluindo a exceção de escrita
fora do projeto necessária ao gerenciador. Auditoria: [FFPROBE_AUDIT.md](FFPROBE_AUDIT.md).

Instalada bottle oficial homebrew/core/ffmpeg 9.0.2 revisão 1. Sem compilação de
fontes, auto-update, analytics, limpeza automática ou checagem de dependentes
instalados nessa operação. Caches principais e logs foram direcionados para temp/;
instalações e links em /opt/homebrew conforme autorização.

- Executável: `/opt/homebrew/Cellar/ffmpeg/9.0.2_1/bin/ffprobe`.
- Link: `/opt/homebrew/bin/ffprobe`.
- Versão executada: 9.0.2, Apple clang 21.0.0.
- SHA-256: `bfe676bfc3a889bebe63af07c71a926a6167f568c7a932a79c2f1fe51ae6d5a1`.
- Recibo/configuração: `temp/mvp-validation/ffprobe-provenance.json` e `ffprobe-version.txt`.

## Mídia e timeline

Seis arquivos MXF, 2.432.937.760 bytes. Os nomes indicam Canon; não é uma validação
comprovada de Sony FX3. Todos foram sondados: H.264, 3840×2160, 50 fps,
yuv422p10le (4:2:2 de 10 bits), quatro streams PCM pcm_s24le mono a 48 kHz,
com durações iguais às do vídeo. Há ainda um stream auxiliar smpte_436m_anc;
os bytes permanecem no original, mas seu conteúdo não é interpretado pelo sistema.

Os cinco primeiros em ordem lexicográfica compõem a sequência, sem trims,
reordenação criativa, efeitos, retiming, LUT ou recompressão.

| Nome sem extensão .MXF | Frames | Duração (s) | Offset (s) | Timecode de origem |
|---|---:|---:|---:|---|
| A_0018C480A261031_164803HW_CANON | 192 | 3,84 | 0 | 00:15:29:38 |
| A_0018C484A261031_16535367_CANON | 504 | 10,08 | 3,84 | 00:15:58:04 |
| A_0018C488A261031_170322GD_CANON | 1488 | 29,76 | 13,92 | 00:16:48:00 |
| A_0018C490A261031_170723WU_CANON | 576 | 11,52 | 43,68 | 00:17:23:02 |
| A_0018C493A261031_1711371V_CANON | 624 | 12,48 | 55,20 | 00:17:46:28 |

O sexto, A_0018C495A261031_17124149_CANON.MXF, tem 504 frames/10,08 s e também
foi aceito na extração final; ficou fora para respeitar o limite de cinco clipes.
Timecodes vieram dos metadados, não dos nomes. PTS começa em zero e é distinto
da origem de timecode do asset. O JSON/XML mantêm tempos racionais exatos.

Sequência: **3384 frames / 67,68 s / 00:01:07:34 a 50 fps**, início em zero.

## Problema e correção local

O MVP recusou inicialmente os seis arquivos por limitar áudio a um stream.
Não foi descartado áudio para contornar o problema. O extrator agora aceita até
32 fontes mono/estéreo uniformes de 48 kHz, verificando origem zero e duração
racional explícita igual à do vídeo para múltiplas fontes. Layouts ambíguos falham.

JSON registra fontes, índices e streams auxiliares. Para estes MXFs, o XML declara
`audioSources="4"`, `audioChannels="1"`, `audioRate="48000"`: canais são por fonte.
JSON antigo de uma fonte continua suportado. Oito testes novos cobrem esse caso e
recusas, sem depender dos vídeos privados. Mapeamento e reprodução dos quatro
canais ainda precisam de confirmação no Final Cut.

## Artefatos e verificações

Saídas em `workspace/validation-2026-11-16/`:
`timeline.fcpxml`, `project.json` e `operations.jsonl`.
SHA-256 do XML: `a3aee2ec65a2fd7d6ccffa5a6673cdcbd9ac3e6a70b516a68747cfce9f367c09`.

Evidências locais em `temp/mvp-validation/`: manifestos antes/depois, saídas
ffprobe, resultados iniciais/finais, inventário Homebrew, comando de geração,
validações DTD/semântica/timestamps. Ambas as pastas são ignoradas pelo Git.

Verificado:

1. DTD oficial Apple 1.10 por xmllint com `--nonet`: saída 0, sem erros.
2. Cinco clipes, IDs únicos, referências de mídia/formatos resolvidas, URLs locais
   existentes dentro de workspace/test_media e hashes correspondentes ao JSON.
3. Timecodes de origem, durações, offsets consecutivos, soma de 1692/25 segundos,
   frameDuration de 1/50 segundo e declaração de quatro fontes de áudio por asset.
4. Pacotes dos cinco vídeos: 192/504/1488/576/624; PTS ordenados de 0 a N−1,
   duração de um tick (1/50 s) por pacote. Não houve decodificação integral.
5. Os seis originais mantêm SHA-256, tamanho e mtime_ns iguais ao manifesto inicial.
   Nenhum original foi renomeado, transcodificado ou alterado pelo sistema.
6. Journal termina com complete; hashes dos artefatos publicados conferidos.
7. workspace/ já está no .gitignore, linha 45; temp/ também é ignorado.
   `git ls-files workspace` e rastreados ignorados retornam vazio. Não foi
   necessário executar git rm --cached.

Suíte inicial: **33 aprovados**. Suíte após correção: **41 aprovados**.
A primeira execução usou temporários padrão do sistema; a suíte foi repetida
com temporários explicitamente dentro do projeto. Comando de referência:

```sh
TMPDIR="$PWD/temp/mvp-validation" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/python -m pytest -q --basetemp=temp/mvp-validation/pytest-final
```

## Limitações e próximos passos

ffprobe informa matriz bt709, mas primárias e transferência estão ausentes.
Isso não permite inferir Rec.709 completo ou Canon Log. Não foi aplicada LUT.
Não houve inspeção visual/sonora, importação, criação de biblioteca, reprodução,
round-trip ou automação da interface. A rede foi usada apenas para documentação
e instalação autorizada de software; nenhuma mídia foi enviada.

Próximo gate: [FCP_IMPORT_TEST.md](FCP_IMPORT_TEST.md). Registrar versão do editor,
avisos, frames de corte, quatro fontes de áudio e interpretação de cor, depois
exportar o projeto de volta para comparação. Não ampliar para VFX/produção antes.

Alterações para revisão: ave/core.py, tests/test_multistream_audio.py,
documentos desta validação e atualização pontual de arquitetura/guia.

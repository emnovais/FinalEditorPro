# Final Editor Pro — guia do motor offline

Monta cortes simples em FCPXML 1.10 e mantém decisões em JSON. Não executa IA,
efeitos, render, instalação automática ou importação no Final Cut Pro.

Leia [ARCHITECTURE.md](../ARCHITECTURE.md) e [SECURITY_AUDIT.md](../SECURITY_AUDIT.md).

## Verificação já executada

```sh
python3 -m unittest discover -s tests -v
```

Nove testes passaram no macOS com Python 3.15.0 e `/usr/bin/xmllint`.
Os bytes de mídia e metadados dos testes são controlados, **não vídeos reais**.
O teste do adaptador de probe usa mock; o validador DTD real do macOS foi executado
com rede desabilitada. O XML usa DTD extraída da documentação oficial Apple,
cujo copyright está preservado em `audit/FCPXMLv1_10.dtd`.
Não houve teste de importação no editor, codec FX3 ou desempenho 4K.

## Uso após aprovação de ffprobe

Execute a partir desta pasta. Não execute estes exemplos antes de aprovar a origem
e versão de ffprobe. Nenhuma instalação é feita pelo programa.

```sh
python3 -m ave.cli build /caminho/testes/clip1.mov /caminho/testes/clip2.mov \
  --ffprobe /caminho/absoluto/ffprobe --output /caminho/workspace/run-001
```

O diretório pai deve existir e `run-001` não pode existir. Saídas:
`project.json`, `timeline.fcpxml`, `operations.jsonl`. Antes de importar, exigir
evento `complete` no diário e validar a DTD:

```sh
/usr/bin/xmllint --nonet --noout --dtdvalid audit/FCPXMLv1_10.dtd \
  /caminho/workspace/run-001/timeline.fcpxml
```

Para mudar cortes, ajuste `in_frames`/`duration_frames` no JSON e publique uma nova
versão. Não altere metadados nem hashes para contornar verificações.

```sh
python3 -m ave.cli export /caminho/workspace/run-001/project.json \
  --output /caminho/workspace/run-002
python3 -m ave.cli undo /caminho/workspace/run-002
```

Undo guarda os dois artefatos em `undone/`, preservando o diário. Recusa artefatos
modificados. Não desfaz ações no Final Cut. A biblioteca de teste deve ser criada
manualmente e separada das bibliotecas de produção. Importação também é manual;
escolha manter mídia no local. Nenhuma biblioteca é aberta ou alterada pelo código.

## Limites práticos

Montagem na ordem de entrada, mesmo fps/resolução/cor, vídeo progressivo com pixels
quadrados, áudio opcional em até 32 fontes mono/estéreo uniformes a 48 kHz,
com origem zero e durações compatíveis com vídeo. Arquivos ambíguos são recusados;
isso inclui relógios com PTS não zero, rotação e certos metadados de câmera.
Não há música separada, transcrição, IA, speed ramp, máscara, tracking, grading
ou integração Motion implementados. FCPXML válido pela DTD precisa ainda de
validação semântica e visual no Final Cut.

`audit/upstream/` é material de auditoria externo, não parte do aplicativo.
Não o execute nem adicione ao PYTHONPATH. Somente `ave/` é implementação própria.

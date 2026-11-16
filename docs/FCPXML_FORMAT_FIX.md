# Correção do formato de sequência — 16/11/2026

## Resultado

Novo arquivo, separado da entrada:
`workspace/validation-2026-11-16/format-fix-v2/timeline.fcpxml`.
Projeto JSON e journal próprios na mesma pasta. **46 testes aprovados** e
validação DTD oficial Apple 1.10 aprovada. Sem instalação, commit, push,
automação da interface ou acesso a bibliotecas nativas nesta etapa.

O usuário confirmou que a versão anterior importou cinco clipes e áudio,
mas apresentou aviso em `/fcpxml/event/project/sequence/@format`.
Ausência do aviso na versão nova ainda precisa de reimportação manual.

## Diagnóstico: o que foi confirmado

No XML anterior `sequence/@format` aponta para `r1`, existente e único.
Não há referência quebrada ou ID duplicado. O recurso contém:

```xml
<format id="r1" frameDuration="1/50s" width="3840" height="2160"/>
```

O bundle fornecido pelo usuário contém `Info.fcpxml` versão 1.14. Seu formato
de sequência é:

```xml
<format id="r1" name="FFVideoFormat3840x2160p50"
        frameDuration="100/5000s" width="3840" height="2160"
        colorSpace="1-1-1 (Rec. 709)"/>
```

Nesse mesmo bundle, os asset-clips usam outro recurso, `r3`, com nome,
resolução e frameDuration iguais, mas **sem colorSpace**. Portanto, o Final Cut
normalizou separadamente o formato de saída da sequência e o formato dos clipes.

Resolução e cadência não diferem: `100/5000s == 1/50s` exatamente.
Os tempos dos cinco clipes no round-trip são frações equivalentes aos originais;
a duração da sequência continua 3384 frames/67,68 s/00:01:07:34.
O ID literal `r1` é somente uma referência local, não um nome de preset.

O problema identificado no exportador é reutilizar uma descrição customizada
incompleta em relação ao formato de projeto normalizado pelo Final Cut, sem
separar saída da sequência e mídia. A diferença inclui **nome e espaço de cor**;
não foi tratada como simples renomeação de ID ou mudança de frame rate.

## Limite da conclusão causal

A DTD aceita o XML anterior, e a documentação Apple permite formatos customizados
sem nome. Logo, ausência de `name` isoladamente não prova a causa do aviso.
O retorno do editor mostra o formato que ele adotou após importar, mas não revela
qual condição interna disparou o alerta. Não foi executado teste A/B no parser
proprietário para isolar nome versus colorSpace.

A conclusão comprovada é a divergência semântica da descrição de sequência;
a correção reproduz o conjunto de atributos de formato aceito/exportado pelo
editor. **Não afirmamos causa interna exata nem desaparecimento do aviso antes
da nova importação.** Isso exigiria observação no editor e, se necessário,
comparação controlada de variantes com apenas um atributo alterado.

## Correção na origem

`ave/core.py` agora mantém:

- `r1` para assets/asset-clips, sem atribuir Rec.709 às fontes.
- `r_sequence` para a sequência, com `name="FFVideoFormat3840x2160p50"`,
  `frameDuration="1/50s"`, dimensões 3840×2160 e `colorSpace="1-1-1 (Rec. 709)"`.
- Nome de preset somente para combinações mapeadas da lista oficial Apple.
  Formatos customizados não recebem nomes inventados e tempos fracionários
  mantêm sua precisão.
- Perfil de saída explícito: Rec.709 por padrão, correspondente ao projeto
  exportado pelo usuário; `sequence_color_space` no JSON permite selecionar
  um dos perfis de saída conhecidos. Isso não é LUT nem perfil de câmera.

Não copiamos `library/location`, UIDs, bookmarks, caminhos de mídia externos ao
workspace ou ajustes de cor do bundle nativo. As referências externas presentes
no bundle foram apenas lidas como texto; não foram seguidas ou modificadas.
O perfil Canon Log 2/Cinema Gamut encontrado na metadata do bundle não foi
convertido automaticamente em perfil de saída nem imposto às mídias.

## Testes e preservação

Novo `tests/test_sequence_format.py`: cinco casos, incluindo correspondência do
formato nativo, separação de formato de fonte/saída, DTD, fps fracionários e
recusa de inventar preset para dimensões customizadas. São verificações do
contrato exportado, não uma simulação do importador Final Cut.

```text
TMPDIR="$PWD/temp/format-validation" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
.venv/bin/python -m pytest -q --basetemp=temp/format-validation/pytest
46 passed
```

Os XMLs anterior e novo passaram na DTD 1.10 com xmllint e `--nonet`.
O bundle nativo 1.14 foi usado como referência sem tentar validá-lo na DTD 1.10.

Comparação automatizada da nova versão com a anterior:

- Subárvore de sequence idêntica após excluir somente o atributo format.
- Elementos asset idênticos, incluindo quatro fontes mono/48 kHz e URLs.
- JSON de decisões idêntico; nenhum corte, timecode, fps ou duração alterado.
- Formato de sequência equivalente ao nativo para nome, dimensões, espaço de
  saída e duração racional de frame.
- Seis vídeos, XML anterior, JSON anterior e Info.fcpxml de referência:
  SHA-256, tamanho e mtime_ns preservados (nove arquivos no total).

Evidências locais: `temp/format-validation/results.json`, `tests.txt` e
`preserved-before.json`; workspace/ e temp/ continuam ignorados pelo Git.
SHA-256 do XML novo:
`7ea05ffab4a79007e0caff38fc449256cc40b11003aaf63b234b93ba8cd6db63`.

## Verificação manual seguinte

Importar **format-fix-v2/timeline.fcpxml** na biblioteca de teste escolhida pelo
usuário e registrar presença/ausência do aviso. Não reutilizar biblioteca de
produção. Confirmar cinco clipes, quatro fontes de áudio e duração 00:01:07:34.
Nenhuma ação no Final Cut foi automatizada nesta correção.

## Fontes oficiais

- [Apple: format e espaço de cor](https://developer.apple.com/documentation/professional-video-applications/format)
- [Apple: nomes de presets](https://developer.apple.com/documentation/professional-video-applications/predefined-video-formats)
- DTD oficial já disponível em `audit/FCPXMLv1_10.dtd`.

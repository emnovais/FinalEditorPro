# Importação manual — biblioteca de testes

Este roteiro ainda não foi executado. Não automatizar a interface nesta etapa.
Arquivo pronto para importação:

`/Users/evandronovais/Projetos/FinalEditorPro/workspace/validation-2026-11-16/timeline.fcpxml`

1. No Final Cut Pro, use **File > New > Library** e crie
   `FinalEditorPro-MVP-Test-2026-11-16.fcpbundle` dentro de `workspace/`.
   Não reutilize uma biblioteca existente de produção.
2. Configure o armazenamento dessa biblioteca para manter mídia derivada,
   cache e backups em pastas de teste dentro de workspace/. Registre a versão
   do editor. Não mova ou consolide os originais.
3. Use **File > Import > XML** e selecione o arquivo acima. Confirme como destino
   exclusivamente a nova biblioteca. Se houver seletor de biblioteca, escolha
   a de testes; cancele se o destino não estiver claro.
4. Se for solicitada opção de organização da mídia, escolha **Leave files in place**.
   Não gere proxies/optimized media nem aplique correções automáticas nesta etapa.
5. Abra `Final Editor Pro - Real Media Validation`, no evento `AI Test Event`.
   Esperado: cinco clipes 3840×2160 a 50 fps, **00:01:07:34**, 3384 frames,
   início da sequência em zero e ordem descrita no relatório.
6. Confira links, ausência de mídia offline/gaps/pretos inesperados e os primeiros
   e últimos frames de cada clipe. Compare timecodes de origem com o relatório.
7. No inspector/configuração de áudio, confira as quatro fontes mono a 48 kHz e
   escute cada canal. Canais silenciosos podem existir no original; registre-os.
   A declaração XML sozinha não comprova o mapeamento nem a mixagem correta.
8. Confira cor/camera LUT. Há matriz bt709 informada, mas faltam primárias/curva de
   transferência. Registre a interpretação adotada e qualquer aviso do editor.
9. Exporte manualmente o projeto por **File > Export XML** para uma pasta nova
   dentro de workspace/, sem sobrescrever a entrada. Preserve o bundle completo
   caso o editor gere .fcpxmld. Não importe em bibliotecas de produção.

Registre: versão do editor, sucesso/avisos, duração/fps, ordem, fontes de áudio,
links, timecodes, cor e caminho do XML de retorno. Isso completa o gate de
importação; geração e DTD sozinhas não o completam.

Fontes Apple:
- [Intercâmbio XML](https://support.apple.com/en-az/guide/final-cut-pro/verdbd66ae/mac)
- [Links de mídia](https://support.apple.com/guide/final-cut-pro/organize-files-during-import-ver392f50c2/12.4/mac/26.6)

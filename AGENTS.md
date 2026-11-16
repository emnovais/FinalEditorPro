# Final Editor Pro — instruções para Codex

Trabalhe somente neste repositório. Preserve histórico e alterações do usuário.
Nunca use push forçado nem crie outro repositório. Não altere visibilidade remota.
Se autenticação/acesso falhar, interrompa operações remotas e explique.

## Segurança e privacidade

- Originais são somente leitura. Nenhuma escrita, remoção, transcode ou rename
  sobre fontes. Derivados pertencem a pastas novas e ignoradas pelo Git.
- Não abra ou modifique bibliotecas Final Cut existentes. Importação manual em
  biblioteca de teste separada até autorização específica.
- LOCAL proíbe provedores remotos e fallback de nuvem. Não remover o sandbox
  de rede do adaptador local para contornar uma falha.
- Qualquer envio remoto, inclusive texto/evidências, exige consentimento explícito
  por payload/destino. `allow_uploads` não significa consentimento.
- Credenciais apenas no macOS Keychain (`FinalEditorPro`); nunca em config,
  JSON de projeto, variáveis persistidas, logs ou comandos de shell.
- Audite e obtenha aprovação antes de novas dependências ou código externo.
  Pydantic/pytest e wheels exatos de `requirements.lock` foram aprovados nesta
  inicialização. Isso não aprova novos runtimes, modelos, FFmpeg ou chamadas pagas.
- Não execute `audit/upstream/`. Essa pasta e wheels ficam locais, fora do Git.
- Provedores simulados apenas nos testes. Não reportar inferência ou VFX fictícios.

## Desenvolvimento e verificação

Python >=3.11; ambiente atual Python 3.15/macOS arm64. Lock específico em
`requirements.lock`; não regenerar silenciosamente para outra plataforma.
Use `.venv/bin/python`; testes:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Testes devem permanecer offline. Não carregar Keychain real nem modelos neles.
`ave/` mantém o motor determinístico e exportador existentes; `final_editor_pro/ai/`
contém contratos/configuração/roteamento/adapters. O motor não conhece provedores.
Não adicionar VFX complexo nesta fase; preserve ROADMAP.md.

Antes de cada commit: executar testes pertinentes, `git status`, `git ls-files`,
`git ls-files -ci --exclude-standard` e revisar o diff preparado. Remover apenas
do índice qualquer arquivo proibido previamente rastreado, preservando-o localmente.
Nunca versionar mídia, modelos, ambientes, renders, logs privados ou segredos.
Antes do push, conferir remoto e atualizar referências; push normal em `main`.

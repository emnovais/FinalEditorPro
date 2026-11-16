# Validação da inicialização — 16/11/2026

Ambiente: macOS arm64, Python 3.15.0, Pydantic 2.14.1, pytest 9.2.0.
Wheels fixados/auditados foram aprovados pelo usuário e instalados somente na venv.

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
33 passed

.venv/bin/python -m pip check
No broken requirements found.
```

Verificado:

- Regressão do MVP: DTD oficial Apple via xmllint, referências de mídia,
  timecodes NDF/DF, frações de frame, limites e integridade SHA-256.
- Publicação sem sobrescrita, reversão de artefatos e recusa em bibliotecas FCP.
- Três modos de IA, seleção por capacidade, overrides e operações locais reservadas.
- Ausência de sockets/DNS nos testes; seleção remota bloqueada em LOCAL,
  nenhuma chamada ao transporte remoto após falha local.
- Consentimento explícito, expiração, uso único, mudança de destino/modelo/payload.
- Contratos Pydantic, recusa de cortes inválidos e observações sobre frames ausentes.
- Custos estimados, journals sem conteúdo ou grants, JSON independente do provider.
- Fronteiras de adapters e bridge Keychain com mocks; nunca usar chaves reais.
- Gitignore para macOS/mídia/ambientes/segredos, preservando arquivos de desenvolvimento.

Não verificado: inferência com modelo real, Keychain real, chamadas HTTPS reais,
isolamento de runtime real sob sandbox, leitura de FX3/ffprobe, importação/round-trip
Final Cut ou desempenho 4K. Modelos de segmentação/VFX não foram implementados.
Os fixtures de mídia são bytes controlados, não vídeos decodificáveis. Nenhum
modelo, vídeo, credencial, render, wheel ou venv deve fazer parte do commit.

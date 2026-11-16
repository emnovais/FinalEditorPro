# Auditoria inicial das dependências — 16/11/2026

Escopo: wheels de Pydantic 2.14.1, pytest 9.2.0 e oito dependências transitivas.
Inventário, requisitos, arquivos nativos e SHA-256 em `audit/dependencies.json`.
`requirements.lock` fixa os artefatos para Python 3.15/macOS arm64 desta máquina.

Os wheels foram baixados de PyPI com `--only-binary=:all:`, sem build ou import.
Os hashes foram comparados aos metadados oficiais por versão. Inspeção do ZIP:
sem `.pth`, scripts de instalação ou caminhos com traversal. O módulo nativo
`pydantic-core` é esperado e não foi auditado em nível binário. Não se afirma
ausência de vulnerabilidades nem auditoria completa dos fontes transitivos.

Risco residual: importar dependências executa código de terceiros; pytest permite
plugins. Testes devem usar `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, venv dentro do projeto,
instalação `--no-index --require-hashes` dos wheels revisados e nenhuma chave de API.
Nenhum modelo ou motor de inferência foi baixado. Integrações reais permanecem
opcionais e desativadas até aprovação e validação própria.

Fontes: https://pypi.org/project/pydantic/2.14.1/ e
https://pypi.org/project/pytest/9.2.0/ (metadados dos demais no inventário).

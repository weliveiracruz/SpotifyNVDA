# Instruções para quem trabalha neste repositório (pessoas e agentes de IA)

## Regra obrigatória: testes a cada nova versão

Toda nova versão do SpotifyNVDA (toda mudança no campo `version` de `addon/manifest.ini`) **precisa** passar por todos os testes antes de ser gerada (`docs/SDD.md`, seção 8, e `docs/SDD-TESTES.md`):

1. Atualize `version` e `changelog` em `addon/manifest.ini` e `addon/locale/pt_BR/manifest.ini`, e o `CHANGELOG.md`.
2. Escreva ou atualize os testes das funções novas ou alteradas (funcionais em `tests/test_pure.py` ou `tests/test_gui.py`, acessibilidade em `tests/test_accessibility.py`, vulnerabilidade em `tests/test_security.py`) e acrescente os casos no `docs/SDD-TESTES.md`.
3. Rode todas as suítes: `python tests/run_all.py --note "o que mudou"` (precisa de `pip install wxPython bandit comtypes`; Python 3.11 e 3.13).
4. Se algo falhar: registre em `reports/PROBLEMAS-<versão>.md` (P-xx do complemento, T-xx dos testes), corrija e rode de novo até **0 falhas**.
5. Gere `reports/RELATORIO-TESTES-<versão>.md` com os números de `reports/execucoes.json`.
6. Gere o pacote só com `python build.py --release`: ele roda tudo de novo e **recusa** gerar o pacote se algum teste falhar.

Nunca apague nem edite à mão execuções antigas em `reports/execucoes.json`.

## Outras regras

* Só biblioteca padrão do Python e módulos do NVDA; sem `http.server`, `secrets` ou `hmac` (o NVDA pode não trazer).
* Indentação com tabulação, como no NVDA.
* Todo texto da interface passa por `_()`, com `# Translators:` na linha anterior, e é traduzido em `addon/locale/pt_BR/LC_MESSAGES/nvda.po`.
* Letras de atalho (&) únicas em cada janela, em inglês e em português.
* Nunca registrar tokens no log, na fala ou em mensagens de erro.
* Web API do Spotify no formato de 2026: `POST /me/playlists`, `/playlists/{id}/items`, busca com no máximo 10, `/me` sem `product`.

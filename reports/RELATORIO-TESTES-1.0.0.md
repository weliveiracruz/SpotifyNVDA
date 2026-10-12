# Relatório de testes da versão 1.0.0

* Pacote: `dist/SpotifyNVDA-1.0.0.nvda-addon`
* SHA-256: `59bc9fdb7dd17478118c22842567e7964a24c0fee4f7f3d073a5fc853b9e52a7`
* Ambiente: Windows 11, NVDA 2026.1.1 instalado, Python 3.11 e 3.13, wxPython 4.3.1, bandit, MSAA (comtypes)

## Resultado final

**367 testes · 367 aprovados · 0 falhas.** O pacote foi gerado por `python build.py --release`, que roda todas as suítes antes e recusa gerar o pacote se alguma falhar.

| Suíte | Testes | Aprovados | Falharam |
|---|---|---|---|
| Unidades (Python 3.11, NVDA 2024.1–2025.x) | 58 | 58 | 0 |
| Unidades (Python 3.13, NVDA 2026.x) | 58 | 58 | 0 |
| Interface | 70 | 70 | 0 |
| Acessibilidade (inglês, com MSAA) | 56 | 56 | 0 |
| Acessibilidade (português, com MSAA) | 56 | 56 | 0 |
| Tradução | 9 | 9 | 0 |
| Segurança (vulnerabilidades) | 52 | 52 | 0 |
| NVDA instalado | 6 | 6 | 0 |
| Pacote | 2 | 2 | 0 |

## Execuções completas (`reports/execucoes.json`)

| Nº | Testes | Aprovados | Falhas | Corrigidos | Observação |
|---|---|---|---|---|---|
| 1 | 361 | 361 | 0 | 0 | Primeira execução completa |
| 2 | 367 | 365 | 2 | 0 | Formato da Web API de 2026 no simulador (P-03); o mesmo teste falhou em 3.11 e 3.13 (T-07) |
| 3 | 367 | 367 | 0 | 2 | Teste ajustado |
| 4 | 367 | 367 | 0 | 0 | `build.py --release` (portão da versão) |

Antes da primeira execução completa, cada suíte foi rodada isoladamente durante a construção; as falhas dessas rodadas estão em [PROBLEMAS-1.0.0.md](PROBLEMAS-1.0.0.md).

## Problemas

* Do complemento: **3** (P-01 a P-03), todos corrigidos.
* Dos testes: **7** (T-01 a T-07), todos corrigidos.

## Pendente: roteiro manual

Os casos MAN-01 a MAN-15 de [TESTES-MANUAIS.md](../docs/TESTES-MANUAIS.md) precisam de uma conta Spotify Premium real e do NVDA falando; não foram executados de forma automática.

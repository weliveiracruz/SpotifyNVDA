# Relatório de testes da versão 1.2.0

* Pacote: `dist/SpotifyNVDA-1.2.0.nvda-addon`
* SHA-256: `353cc21621ea7a1ca64f18aa93bd53b96bbde7b47268009b70798d67d82f3261`
* Mudanças: pasta renomeada para `SpotifyNVDA`; playlists em árvore com as músicas; busca dentro das playlists; ordenar playlist (com opção de gravar no Spotify); excluir playlist.
* Ambiente: Windows 11, NVDA 2026.1.1, Python 3.11 e 3.13, wxPython 4.3.1, MSAA (comtypes)
* Endpoints conferidos na documentação do Spotify: `GET /playlists/{id}/items` (campo `item`, até 50 por página, só playlists próprias ou colaborativas), `PUT /playlists/{id}/items` (reordenar), `DELETE /me/library` (até 40 URIs, aceita `spotify:playlist:`).

## Resultado final

**510 testes · 510 aprovados · 0 falhas**, gerado por `python build.py --release`.

| Suíte | Testes | Aprovados | Falharam |
|---|---|---|---|
| Unidades (Python 3.11) | 86 | 86 | 0 |
| Unidades (Python 3.13) | 86 | 86 | 0 |
| Interface | 112 | 112 | 0 |
| Acessibilidade (inglês, com MSAA) | 75 | 75 | 0 |
| Acessibilidade (português, com MSAA) | 75 | 75 | 0 |
| Tradução | 9 | 9 | 0 |
| Segurança (vulnerabilidades) | 59 | 59 | 0 |
| NVDA instalado | 6 | 6 | 0 |
| Pacote | 2 | 2 | 0 |

Novos nesta versão: 19 de unidade (FUN-20 a FUN-23), 40 de interface, 19 de acessibilidade por idioma (ACE-18 e janela Ordenar), 4 de segurança (SEG-20).

## Execuções completas desta versão

| Nº | Testes | Aprovados | Falhas | Observação |
|---|---|---|---|---|
| 7 | 510 | 510 | 0 | Primeira execução completa da 1.2.0 |
| 8 | 510 | 510 | 0 | `build.py --release` (portão da versão) |

As falhas encontradas antes, ao rodar cada suíte durante a construção, estão em [PROBLEMAS-1.2.0.md](PROBLEMAS-1.2.0.md): 1 do complemento e 6 dos testes (T-12 e T-13 apareceram no GitHub Actions).

## GitHub Actions

Depois das correções T-12 e T-13, todas as suítes passaram no Windows do GitHub (Python 3.11 e 3.13). A versão foi publicada pela automação a partir da tag `v1.2.0` (commit `348dc4a`): [release v1.2.0](https://github.com/weliveiracruz/SpotifyNVDA/releases/tag/v1.2.0).

## Roteiro manual

| Item | Resultado |
|---|---|
| Quem testou | Wellington Cruz, com a própria conta do Spotify e o NVDA |
| Data | 12/10/2026 |
| Casos | MAN-18 a MAN-22 de [TESTES-MANUAIS.md](../docs/TESTES-MANUAIS.md): abrir playlists, tocar a partir de uma música, buscar nas playlists, ordenar (e gravar) e excluir uma playlist |
| Resultado | Aprovado: o usuário informou que está funcionando |

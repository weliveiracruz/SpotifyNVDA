# Relatório de testes da versão 1.3.0

* Branch: `feature/1.3.0-botao-unico-remover-musicas`
* Pacote: `dist/SpotifyNVDA-1.3.0.nvda-addon`
* SHA-256: `f456ea1037ee701ebff5badf80adf3e7b755f5cae24307523b757556c98880e9`
* Mudanças: um só botão de tocar (no lugar de Tocar, Continuar última música e Tocar ou pausar); playlists completas (até 10.000 músicas) com o número real; remover música da playlist.
* Endpoint conferido na documentação do Spotify: `DELETE /playlists/{id}/items` com `{"items": [{"uri": …}]}`, até 100 por vez, sem escolha de posição (todas as cópias saem).
* Ambiente: Windows 11, NVDA 2026.1.1, Python 3.11 e 3.13, wxPython 4.3.1, MSAA (comtypes). Executado sem o `nvda.mo` compilado, como no GitHub Actions.

## Resultado final

**553 testes · 553 aprovados · 0 falhas**, gerado por `python build.py --release`.

| Suíte | Testes | Aprovados | Falharam |
|---|---|---|---|
| Unidades (Python 3.11) | 95 | 95 | 0 |
| Unidades (Python 3.13) | 95 | 95 | 0 |
| Interface | 129 | 129 | 0 |
| Acessibilidade (inglês, com MSAA) | 79 | 79 | 0 |
| Acessibilidade (português, com MSAA) | 79 | 79 | 0 |
| Tradução | 9 | 9 | 0 |
| Segurança (vulnerabilidades) | 59 | 59 | 0 |
| NVDA instalado | 6 | 6 | 0 |
| Pacote | 2 | 2 | 0 |

Novos nesta versão: 9 de unidade (FUN-24, FUN-25), 17 de interface (FUN-24 a FUN-26), 4 de acessibilidade por idioma (ACE-19) e 2 casos a mais no SEG-20.

## Execuções completas desta versão

| Nº | Testes | Aprovados | Falhas | Observação |
|---|---|---|---|---|
| 10 | 553 | 553 | 0 | Primeira execução completa da 1.3.0 |
| 11 | 553 | 553 | 0 | `build.py --release` (portão da versão) |

As falhas das rodadas de cada suíte durante a construção estão em [PROBLEMAS-1.3.0.md](PROBLEMAS-1.3.0.md): 1 do complemento e 2 dos testes.

## Pendente: roteiro manual

MAN-23 a MAN-26 de [TESTES-MANUAIS.md](../docs/TESTES-MANUAIS.md), com a sua conta: playlist com mais de 2000 músicas, remover uma música de uma playlist de teste, o botão único "Tocar <nome>" e "Tocar/pausar" continuando a última música.

# Relatório de testes da versão 1.1.0

* Pacote: `dist/SpotifyNVDA-1.1.0.nvda-addon`
* SHA-256: `903299340eddcfe32d6e746b28f1b85e03c76dd3739fea1a7968c0c30d2752c0`
* Mudança: o Spotify é aberto em segundo plano, sem janela e sem tirar o foco (pedido do usuário após testar a 1.0.0).
* Ambiente: Windows 11, NVDA 2026.1.1, Spotify da Microsoft Store 1.304.258.0, Python 3.11 e 3.13, wxPython 4.3.1

## Resultado final

**390 testes · 390 aprovados · 0 falhas**, gerado por `python build.py --release`.

| Suíte | Testes | Aprovados | Falharam |
|---|---|---|---|
| Unidades (Python 3.11) | 67 | 67 | 0 |
| Unidades (Python 3.13) | 67 | 67 | 0 |
| Interface | 72 | 72 | 0 |
| Acessibilidade (inglês, com MSAA) | 56 | 56 | 0 |
| Acessibilidade (português, com MSAA) | 56 | 56 | 0 |
| Tradução | 9 | 9 | 0 |
| Segurança (vulnerabilidades) | 55 | 55 | 0 |
| NVDA instalado | 6 | 6 | 0 |
| Pacote | 2 | 2 | 0 |

Novos nesta versão: 9 testes FUN-19 (segundo plano), 2 de interface (opção e sua ligação com o iniciador), 3 de segurança SEG-19.

## Execuções completas desta versão (`reports/execucoes.json`)

| Nº | Testes | Aprovados | Falhas | Observação |
|---|---|---|---|---|
| 5 | 390 | 390 | 0 | Spotify em segundo plano |
| 6 | 390 | 390 | 0 | `build.py --release` (portão da versão) |

## Teste real com o Spotify instalado

O código do complemento (`background.py`) foi executado com o Spotify real deste computador:

| Verificação | Resultado |
|---|---|
| Spotify fechado antes | Sim |
| Janelas visíveis do Spotify a cada segundo, por 12 s e depois aos 60 s | Nenhuma |
| Foco ficou na janela em que o usuário estava | Sim, em todas as verificações |
| Spotify disponível como dispositivo para tocar | Sim ("WELLINGTON (computer)") |

## Problemas

Nenhuma falha nesta versão: todos os testes passaram na primeira execução completa.

## Pendente: roteiro manual

MAN-05, MAN-16 e MAN-17 de [TESTES-MANUAIS.md](../docs/TESTES-MANUAIS.md), com o NVDA falando e o som tocando.

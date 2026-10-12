# Problemas encontrados na versão 1.0.0

Encontrados durante a construção e os testes, antes de gerar a versão. Todos corrigidos; a versão só foi gerada com 0 falhas.

## Problemas do complemento (P)

| ID | Teste | Gravidade | Causa | Correção |
|---|---|---|---|---|
| P-01 | test_gui: RF-09 Sign out from the settings | Baixa | Ao encerrar (por exemplo, quando o NVDA recarrega os plugins), o plugin deixava o painel de configurações apontando para a instância encerrada; o botão Sair da conta do painel agia sobre ela | `terminate()` limpa `SpotifySettingsPanel.plugin`; novo teste FUN-15 "terminate releases the settings panel" |
| P-02 | test_security: SEG-17 bandit | Baixa | Três avisos baixos do bandit sem justificativa no código: URL do token confundida com senha (B105) e abertura do aplicativo pelo protocolo `spotify:` (B607) | Justificativas `# nosec` com o motivo; o teste aceita só os avisos justificados |
| P-03 | Revisão da documentação do Spotify (fevereiro de 2026) + FUN-18 | Média | Desde 2026, `GET /me` de aplicativos em modo de desenvolvimento não traz o plano (`product`) e playlists de outras pessoas vêm sem `items`; o simulador ainda usava o formato antigo, então a situação "Conectado como … (Premium)" nunca apareceria de verdade | Situação mostra só o nome quando o plano não vem; lista mostra a playlist sem número de músicas; simulador atualizado para o formato de 2026 e três testes FUN-18 |

## Problemas dos testes (T)

| ID | Teste | Causa | Correção |
|---|---|---|---|
| T-01 | test_gui: RF-09 | O teste criava um segundo plugin (NVDA reiniciado) e seguia usando o painel ligado a ele | Teste recoloca o plugin em uso, como no NVDA, que tem um só |
| T-02 | test_accessibility: ACE-03 New playlist | Comparava nomes de classe, mas o `guiHelper` do NVDA envolve os controles em uma subclasse | Compara os próprios controles |
| T-03 | test_accessibility (pt_BR): ACE-07 | Comparava com um trecho em inglês que não existe como texto traduzível | Compara com a frase traduzida de `messages.waitingBrowser()` |
| T-04 | test_accessibility: ACE-01 MSAA nos campos numéricos | Lia o MSAA da janela das setas do SpinCtrl; o foco vai para a caixa de edição, que tem o nome certo | O teste lê a janela que recebe o foco, como o NVDA |
| T-05 | test_security: SEG-16 | A expressão regular confundia `re.compile(` com `compile(` | Expressão ignora chamadas com ponto antes |
| T-06 | test_nvda_runtime | Lia o `library.zip` depois de fechá-lo | Arquivo mantido aberto durante a suíte |
| T-07 | test_pure: FUN-01 | Exigia `product` em `/me`, removido pelo Spotify em 2026 | Asserção removida; formato coberto por FUN-18 |

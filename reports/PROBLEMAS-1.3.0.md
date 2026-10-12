# Problemas encontrados na versão 1.3.0

Encontrados durante a construção e os testes, antes de gerar a versão. Todos corrigidos; a versão só foi gerada com 0 falhas.

## Problemas do complemento (P)

| ID | Onde foi visto | Gravidade | Causa | Correção |
|---|---|---|---|---|
| P-05 | test_gui: FUN-26 e FUN-04 (botão único) | Média | Depois de uma busca o primeiro resultado já vem selecionado pelo próprio complemento, então o botão continuava "Tocar/pausar": quem buscava uma música e ia ao botão pausava em vez de tocar o que encontrou | Depois de uma busca o botão oferece o resultado selecionado ("Tocar <nome>"); ao abrir a janela e ao listar as playlists ele continua "Tocar/pausar" |

## Problemas dos testes (T)

| ID | Teste | Causa | Correção |
|---|---|---|---|
| T-14 | test_accessibility (pt_BR): ACE-19 | Comparava o nome do botão com o texto em inglês | Compara com o texto traduzido |
| T-15 | test_security: SEG-16 | A lista de módulos permitidos não tinha o `contextlib`, da biblioteca padrão, que passou a ser usado | Incluído na lista; `test_nvda_runtime` confirma que o NVDA instalado traz o módulo |

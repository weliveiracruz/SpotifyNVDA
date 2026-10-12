# Problemas encontrados na versão 1.2.0

Encontrados durante a construção e os testes, antes de gerar a versão. Todos corrigidos; a versão só foi gerada com 0 falhas.

## Problemas do complemento (P)

| ID | Onde foi visto | Gravidade | Causa | Correção |
|---|---|---|---|---|
| P-04 | Sondagem da árvore com wxPython real | Baixa | Ao fechar a janela, a árvore dispara "seleção mudou" enquanto é destruída; o código tentava ler a árvore já destruída e gravava erros no log do NVDA | O evento só atualiza os botões se a janela ainda existe; teste FUN-15 "no unexpected errors in the log" cobre o fechamento |

## Problemas dos testes (T)

| ID | Teste | Causa | Correção |
|---|---|---|---|
| T-08 | test_gui: FUN-22 ordenar por título | O complemento ordena sem acentos ("Águas" antes de "Chega"), como pede o SDD; o teste comparava com a ordenação do Python, que põe "Á" depois do "Z" | O teste compara com a mesma regra sem acentos |
| T-09 | test_gui: FUN-23 tecla Delete | `TreeEvent.SetKeyEvent` não existe no wxPython 4 | A tecla Delete real é enviada à árvore (`WM_KEYDOWN`) |
| T-10 | test_gui: FUN-21 playlists de outras pessoas | O teste, como foi escrito, passava sempre e não verificava nada (achado na revisão, não por falha) | Reescrito: confere que nenhuma playlist de outra pessoa é lida durante a busca |
| T-11 | Sondagem da árvore | A tecla simulada pelo `UIActionSimulator` vai para a janela em primeiro plano, não para a do teste | Teclas enviadas direto à janela da árvore, sem depender do primeiro plano |

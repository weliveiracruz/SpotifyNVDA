# Roteiro de testes manuais do SpotifyNVDA

O que os testes automáticos não alcançam: a fala real do NVDA, o som e o login com uma conta de verdade. Faça a cada nova versão, com o NVDA instalado e uma conta Spotify Premium cadastrada no User Management do seu aplicativo.

Anote o resultado (OK ou o problema) em `reports/RELATORIO-TESTES-<versão>.md`.

| ID | Passos | Esperado |
|---|---|---|
| MAN-01 | Instalar o `.nvda-addon` e reiniciar o NVDA | Instalação sem aviso de incompatibilidade |
| MAN-02 | NVDA+Alt+P | Janela Spotify; NVDA lê "Spotify, diálogo" e "Entrar com o Spotify, botão" |
| MAN-03 | Entrar com o Spotify | Navegador abre a página do Spotify; após Concordo, a aba diz que pode fechar; NVDA fala "Conectado ao Spotify como …" |
| MAN-04 | Tab por toda a janela | Cada controle tem nome; a lista diz "Resultados: minhas playlists (N)" |
| MAN-05 | Enter em uma playlist com o aplicativo do Spotify fechado | A playlist toca **sem aparecer janela** do Spotify, sem botão na barra de tarefas e sem tirar o foco (Alt+Tab não mostra o Spotify) |
| MAN-16 | Desligar "Manter o aplicativo do Spotify escondido", fechar o Spotify e tocar | Spotify abre minimizado, sem tirar o foco |
| MAN-17 | Com o Spotify aberto por você, tocar pelo complemento | A janela do Spotify continua como estava |
| MAN-18 | Na árvore, Seta para a direita em uma playlist sua | NVDA lê "N músicas"; Seta para baixo lê cada música; Seta para a esquerda fecha |
| MAN-19 | Enter em uma música dentro da playlist | A playlist toca a partir daquela música |
| MAN-20 | Tipo "Músicas nas minhas playlists", buscar uma palavra sem acento | Playlists encontradas abertas, só com as músicas certas |
| MAN-21 | Ordenar músicas… por título; depois gravar no Spotify | A árvore muda; após gravar, o aplicativo do Spotify mostra a nova ordem |
| MAN-22 | Excluir uma playlist de teste | Pede confirmação; some da árvore e do aplicativo do Spotify; pode ser recuperada na conta |
| MAN-23 | Abrir uma playlist com mais de 2000 músicas | NVDA diz "Carregando N músicas…" e depois "N músicas" com o número real; o fim da playlist aparece |
| MAN-24 | Remover uma música de uma playlist de teste (botão e tecla Delete) | Pede confirmação; a música some da árvore e do aplicativo do Spotify |
| MAN-25 | Escolher uma música com as setas e ir ao botão com Tab | NVDA lê "Tocar <nome da música>"; ao pressionar, ela toca |
| MAN-26 | Fechar o Spotify, abrir a janela e pressionar Tocar/pausar | Continua a última música |
| MAN-06 | NVDA+Alt+Espaço duas vezes | "Pausado", depois "Tocando", com o som parando e voltando |
| MAN-07 | NVDA+Alt+Setas para a direita e esquerda | Música muda e o nome é falado |
| MAN-08 | NVDA+Alt+Setas para cima e para baixo | Volume muda e é falado |
| MAN-09 | Buscar uma música, Adicionar à playlist | Música aparece na playlist no aplicativo do Spotify |
| MAN-10 | Nova playlist… | Playlist aparece no aplicativo do Spotify |
| MAN-11 | Reiniciar o NVDA e pressionar NVDA+Alt+U | Ainda conectado; a última música continua de onde parou |
| MAN-12 | Sair da conta | Confirmação; depois NVDA+Alt+Espaço diz que não está conectado |
| MAN-13 | Atualizar o complemento com uma versão nova | Continua conectado |
| MAN-14 | NVDA, Preferências, Definir comandos, Spotify | Todos os comandos com descrição |
| MAN-15 | Tela de logon do Windows (Ctrl+Alt+Del) | Atalhos do Spotify não respondem |

# Histórico de versões

## 1.3.0

* **Um só botão de tocar** no lugar de Tocar, Continuar última música e Tocar ou pausar. O nome diz o que ele faz:
  * **Tocar <nome>**, quando você acabou de escolher uma música ou playlist na árvore ou depois de uma busca;
  * **Tocar/pausar** nos outros casos: pausa o que está tocando, retoma o que está pausado e, se nada estiver carregado na conta, continua a última música.
  * Enter na árvore continua tocando o item selecionado; NVDA+Alt+Espaço e NVDA+Alt+U continuam iguais.
* **Playlists completas**: ao abrir uma playlist, todas as músicas aparecem (até 10.000, o máximo de uma playlist do Spotify), e não só as 2.000 primeiras. O NVDA anuncia o número real ("Carregando 3500 músicas…", "3500 músicas") e o nome da playlist mostra esse número. Se o Spotify pedir para esperar durante a leitura, o complemento espera e continua.
* **Remover música da playlist**: botão Remover da playlist ou tecla Delete numa música de uma playlist sua, com confirmação. Se a música estiver repetida, o aviso diz que o Spotify remove todas as cópias. A árvore é atualizada e a seleção fica no mesmo lugar.

## 1.2.0

* Pasta do projeto renomeada para `SpotifyNVDA`.
* **Playlists em árvore**: cada playlist abre com a Seta para a direita (ou Enter no sinal de mais) e mostra as músicas; Seta para a esquerda fecha. Enter em uma música toca a playlist a partir dela. Arquivos locais aparecem como indisponíveis para tocar.
* **Buscar músicas dentro das playlists**: novo tipo de busca "Músicas nas minhas playlists", sem diferenciar acentos e maiúsculas; mostra cada playlist encontrada já aberta, só com as músicas que combinam.
* **Ordenar playlist** (botão Ordenar músicas…): por ordem da playlist, título, artista, álbum, data em que foi adicionada ou duração, crescente ou decrescente. A ordem fica lembrada para cada playlist. Nas suas playlists, há a opção de gravar a ordem no Spotify (pede confirmação; as músicas são só movidas, nunca removidas).
* **Excluir playlist** (botão ou tecla Delete na playlist): pede confirmação e tira a playlist da sua biblioteca, como o Spotify faz; uma playlist sua pode ser recuperada na página da conta.
* Correção: a janela não gera mais erro no log ao ser fechada.

## 1.1.0

* Toca em segundo plano: quando não há dispositivo do Spotify, o complemento abre o aplicativo do Spotify **minimizado, sem tirar o foco e com a janela escondida** (sem botão na barra de tarefas e fora do Alt+Tab). O som continua saindo dele.
* Se o Spotify já estiver aberto por você, nada muda nele.
* Nova opção nas configurações: **Manter o aplicativo do Spotify escondido** (ligada por padrão).

## 1.0.0

Primeira versão.

* Entrar com o Spotify pela página oficial (OAuth com PKCE, sem segredo guardado).
* Continuar conectado: sessão criptografada com DPAPI, renovação automática, mantida nas atualizações.
* Minhas playlists, busca de músicas e de playlists.
* Tocar música ou playlist (Spotify Connect; abre o aplicativo do Spotify se não houver dispositivo).
* Atalhos: NVDA+Alt+P (janela), NVDA+Alt+Espaço (tocar/pausar), NVDA+Alt+Setas para a esquerda e direita (anterior/próxima), NVDA+Alt+Setas para cima e para baixo (volume), NVDA+Alt+A (o que está tocando), NVDA+Alt+U (continuar a última música).
* Nova playlist e Adicionar à playlist.
* Continuar a última música tocada na conta, do ponto em que parou.
* Sair da conta, na janela, nas configurações e em Definir comandos.
* Interface em inglês e português do Brasil.

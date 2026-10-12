# SpotifyNVDA

Complemento do NVDA para ouvir o Spotify com a sua conta: as suas playlists, busca de músicas e de playlists, criação de playlists, tocar e pausar, trocar de música, mudar o volume e continuar a última música, tudo pelo teclado e com respostas faladas.

## Antes de começar (uma vez só)

O Spotify pede que cada pessoa use um "aplicativo" próprio, criado de graça no painel de desenvolvedor. Faça assim:

1. Entre em [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) com a sua conta do Spotify e aceite os termos, se pedir.
2. Escolha **Create app**. Preencha nome (por exemplo, "Meu NVDA") e descrição.
3. Em **Redirect URIs**, coloque exatamente `http://127.0.0.1:8898/callback` e escolha **Add**.
4. Em **Which API/SDKs are you planning to use?**, marque **Web API**. Aceite os termos e salve.
5. Abra o aplicativo criado, vá em **Settings** e copie o **Client ID** (32 letras e números).
6. Em **User Management**, cadastre o seu nome e o e-mail da sua conta do Spotify (aplicativos em modo de desenvolvimento só aceitam as contas da lista).
7. No NVDA, abra o menu NVDA, Preferências, Configurações, categoria **Spotify**, cole o Client ID em **Client ID do Spotify** e confirme com OK.

O Client ID não é uma senha: com o método PKCE usado pelo complemento, nenhum segredo fica guardado no computador.

## Entrar na conta

1. Pressione **NVDA+Alt+P** para abrir a janela Spotify.
2. Escolha **Entrar com o Spotify**. O navegador abre a página de login do próprio Spotify.
3. Entre na sua conta e escolha **Concordo** (Agree). A página diz que você já pode fechar a aba.
4. O NVDA anuncia "Conectado ao Spotify como …" e a janela mostra as suas playlists.

Você continua conectado nas próximas vezes que abrir o NVDA, inclusive depois de atualizar o complemento. A sessão fica criptografada com a proteção de dados do Windows, só para o seu usuário.

## Janela Spotify

| Controle | O que faz |
|---|---|
| Situação | Diz se você está conectado, com qual nome e se a conta é Premium |
| Entrar com o Spotify / Sair da conta | Entra ou sai da conta. Sair apaga a sessão e os dados guardados neste computador |
| Buscar e Tipo | Digite e pressione Enter. Tipo: Músicas, Playlists ou Músicas nas minhas playlists (busca dentro das suas playlists, sem diferenciar acentos) |
| Resultados | Árvore com as suas playlists ou o resultado da busca. Seta para a direita abre a playlist e mostra as músicas; Seta para a esquerda fecha. Enter toca a playlist ou, em uma música, toca a playlist a partir dela. Delete em uma playlist exclui |
| Tocar | Toca a música ou a playlist selecionada |
| Adicionar à playlist… | Coloca a música selecionada em uma das suas playlists |
| Minhas playlists | Mostra as suas playlists |
| Nova playlist… | Cria uma playlist (nome, descrição, pública ou não) e pode já colocar a música selecionada |
| Ordenar músicas… | Ordena a playlist selecionada por ordem da playlist, título, artista, álbum, data em que foi adicionada ou duração. Nas suas playlists, pode gravar a nova ordem no Spotify |
| Excluir playlist | Tira a playlist selecionada da sua biblioteca, depois de confirmar. Uma playlist sua pode ser recuperada na sua conta do Spotify, em Recuperar playlists |
| Continuar última música | Continua a última música tocada na sua conta, do ponto em que parou |
| Tocar ou pausar | Toca ou pausa |
| Fechar | Fecha a janela (Esc também fecha) |

## Músicas das playlists

O Spotify só mostra as músicas das playlists que são suas ou em que você colabora. Nas playlists de outras pessoas que você segue, a árvore avisa isso em vez de mostrar as músicas; elas continuam podendo ser tocadas inteiras.

## Atalhos

| Atalho | Ação |
|---|---|
| NVDA+Alt+P | Abrir a janela Spotify |
| NVDA+Alt+Espaço | Tocar ou pausar |
| NVDA+Alt+Seta para a direita | Próxima música |
| NVDA+Alt+Seta para a esquerda | Música anterior |
| NVDA+Alt+Seta para cima | Aumentar o volume |
| NVDA+Alt+Seta para baixo | Abaixar o volume |
| NVDA+Alt+A | Dizer o que está tocando |
| NVDA+Alt+U | Continuar a última música |

Todos podem ser mudados em NVDA, Preferências, Definir comandos, categoria Spotify. Lá também existe o comando "Sair da conta", sem atalho definido.

## De onde vem o som

O complemento controla o Spotify Connect: o som sai do aplicativo do Spotify neste computador (ou no celular, na caixa de som, onde estiver tocando).

Se nenhum dispositivo estiver aberto, o complemento abre o aplicativo do Spotify **em segundo plano**: minimizado, sem tirar o foco de onde você está e com a janela escondida (não aparece na barra de tarefas nem no Alt+Tab). Você só ouve a música. Se o Spotify já estiver aberto por você, o complemento não mexe nele.

O Spotify só permite tocar as músicas pelos aplicativos dele, por isso o aplicativo precisa estar instalado; o complemento só o usa escondido. Para ver a janela do Spotify, abra-o pelo menu Iniciar.

Tocar, pausar, trocar de música e mudar o volume pela API do Spotify **exigem Spotify Premium**. Sem Premium, listar, buscar e criar playlists continuam funcionando.

## Configurações (NVDA, Preferências, Configurações, Spotify)

* **Client ID do Spotify**: o identificador do seu aplicativo no painel do Spotify.
* **Porta do retorno**: porta usada para voltar do login (padrão 8898). Se mudar, cadastre o novo endereço mostrado logo abaixo no painel do Spotify.
* **Passo do volume (%)**: quanto o volume muda a cada atalho (padrão 10).
* **Abrir o aplicativo do Spotify quando não houver dispositivo**.
* **Manter o aplicativo do Spotify escondido**: toca em segundo plano, sem janela (ligada por padrão).
* **Abrir o painel de desenvolvedor do Spotify** e **Sair da conta do Spotify**.

## Privacidade e segurança

* Login pela página oficial do Spotify, com PKCE: o complemento nunca vê a sua senha.
* Tokens criptografados com a proteção de dados do Windows; nunca vão para o log, para a fala ou para o arquivo nvda.ini.
* Conexões só com o Spotify, em HTTPS com certificado verificado.
* Para remover também a permissão no site do Spotify, use a página de aplicativos da sua conta: [spotify.com/account/apps](https://www.spotify.com/account/apps/).

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| Informe o Client ID… | Siga "Antes de começar" |
| Esta conta não está cadastrada no seu aplicativo… | Cadastre o seu e-mail em User Management no painel |
| A porta … já está em uso | Escolha outra porta nas configurações e cadastre o novo endereço no painel |
| Tocar músicas por aqui exige Spotify Premium | A conta é gratuita |
| Nenhum dispositivo do Spotify disponível | Abra o aplicativo do Spotify e tente de novo |

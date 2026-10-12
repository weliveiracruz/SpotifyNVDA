# SDD do SpotifyNVDA

Documento de projeto de software (Software Design Document) do complemento **SpotifyNVDA** para o leitor de telas NVDA. Ele define **o que** o complemento faz, **como** é construído, **como** é testado e **como** uma versão é liberada. Vale para todas as versões a partir da 1.0.0.

* Pasta do projeto: `C:\git\ADDONS NVDA\SpotifyNVDA`
* Nome interno do complemento: `SpotifyNVDA` (pacote `dist/SpotifyNVDA-<versão>.nvda-addon`)
* Autor: Wellington Cruz
* Licença: GPL 2 (a mesma do NVDA)

---

## 1. Objetivo

Permitir que a pessoa que usa o NVDA conecte a sua conta do Spotify e ouça música sem depender da interface visual do Spotify: listar e buscar playlists, buscar músicas, tocar, pausar, trocar de música, mudar o volume, criar playlists e continuar a última música tocada, tudo por teclado e com respostas faladas.

## 2. Requisitos

### 2.1 Requisitos funcionais (RF)

| ID | Requisito | Como é atendido |
|---|---|---|
| RF-01 | Entrar com a conta do Spotify pela tela de login do próprio Spotify | OAuth 2.0 *Authorization Code* com PKCE: o navegador padrão abre `accounts.spotify.com`; o retorno chega em `http://127.0.0.1:<porta>/callback` |
| RF-02 | Continuar conectado sempre que abrir o complemento | O *refresh token* fica guardado criptografado (DPAPI do Windows); o *access token* é renovado sozinho antes de vencer e depois de um 401; o novo *refresh token* devolvido pelo Spotify é salvo a cada renovação; a sessão é mantida nas atualizações do complemento |
| RF-03 | Listar as playlists do usuário | `GET /v1/me/playlists`, com paginação (até 500 playlists) |
| RF-04 | Tocar música vinda do Spotify | Spotify Connect: `PUT /v1/me/player/play` no dispositivo ativo; se não houver dispositivo, o complemento abre o aplicativo do Spotify **em segundo plano** (minimizado, sem foco, janela escondida) e espera ele aparecer |
| RF-13 | Ver as músicas de cada playlist (1.2.0; completo na 1.3.0) | Resultados em árvore: cada playlist é um ramo que, ao abrir, lê `GET /v1/playlists/{id}/items` em páginas de 50 até o fim (máximo de 10.000, o limite do Spotify), com cache; anuncia e mostra o número real; espera quando o Spotify pede (429 até 30 s); Enter em uma música toca a playlist com `offset` nela |
| RF-17 | Um só botão de tocar (1.3.0) | "Tocar <nome>" quando o usuário acabou de escolher um item na árvore ou fez uma busca; senão "Tocar/pausar" (pausa, retoma ou continua a última música). Substitui Tocar, Continuar última música e Tocar ou pausar |
| RF-18 | Remover música da playlist (1.3.0) | `DELETE /v1/playlists/{id}/items` com `{"items": [{"uri": …}]}` (alternativa `/tracks`), com confirmação; o Spotify remove todas as cópias da música, e a confirmação avisa quando há mais de uma |
| RF-14 | Buscar músicas dentro das playlists (1.2.0) | Tipo "Músicas nas minhas playlists": lê as playlists do usuário (próprias ou colaborativas) e filtra por nome, artista e álbum sem diferenciar acentos e maiúsculas |
| RF-15 | Ordenar cada playlist (1.2.0) | Por ordem da playlist, título, artista, álbum, data em que foi adicionada ou duração, crescente ou decrescente; preferência guardada por playlist. Opcional: gravar no Spotify com `PUT /v1/playlists/{id}/items` (`range_start`/`insert_before`), uma música por vez, com `snapshot_id` encadeado |
| RF-16 | Excluir playlist (1.2.0) | `DELETE /v1/me/library?uris=spotify:playlist:{id}` (alternativa `DELETE /playlists/{id}/followers`), com confirmação |
| RF-12 | Tocar de forma independente, sem abrir outra janela (1.1.0) | `background.py`: inicia o Spotify com `--autostart --minimized` e `SW_SHOWMINNOACTIVE`, esconde as janelas do Spotify que ele mesmo iniciou e devolve o foco; um Spotify aberto pelo usuário nunca é alterado |
| RF-05 | Atalhos para tocar/pausar, próxima, anterior, aumentar e abaixar o volume | Scripts globais do NVDA (seção 5), reatribuíveis em Definir comandos |
| RF-06 | Criar playlist | `POST /v1/me/playlists` (com o caminho antigo `/users/{id}/playlists` como alternativa); músicas adicionadas com `POST /v1/playlists/{id}/items` (alternativa `/tracks`) |
| RF-07 | Buscar músicas | `GET /v1/search?type=track` |
| RF-08 | Buscar playlists | `GET /v1/search?type=playlist` |
| RF-09 | Botão para sair da conta (deslogar) | Botão "Sair da conta" na janela e nas configurações: apaga a sessão e todos os dados pessoais guardados |
| RF-10 | Continuar a última música tocada na conta | 1) se a conta tem uma reprodução pausada, retoma; 2) senão usa o que for mais recente entre a última música guardada pelo complemento (com a posição) e `GET /v1/me/player/recently-played` (histórico da conta), tocando no mesmo contexto (playlist/álbum) |
| RF-11 | Saber o que está tocando | Atalho anuncia música, artista e se está tocando ou pausada |

### 2.2 Requisitos de acessibilidade (RA)

| ID | Requisito |
|---|---|
| RA-01 | Todo controle que recebe foco tem nome acessível (rótulo) lido pelo NVDA |
| RA-02 | Todo botão e rótulo tem letra de atalho com Alt, sem repetição na mesma janela, em inglês e em português |
| RA-03 | Ordem de tabulação lógica: situação, entrar/sair, busca, tipo, buscar, resultados, ações |
| RA-04 | Tudo funciona só pelo teclado (Enter toca o item da lista, Esc fecha) |
| RA-05 | Toda ação e todo erro são anunciados em fala, em texto curto e sem jargão técnico |
| RA-06 | O foco nunca se perde depois de uma ação |
| RA-07 | Toda janela tem título próprio |
| RA-08 | Toda frase da interface é traduzível e está traduzida para português do Brasil, com comentário para tradutores |
| RA-09 | Atalhos padrão não conflitam com os comandos do próprio NVDA |
| RA-10 | Comandos aparecem na categoria "Spotify" de Definir comandos, cada um com descrição |
| RA-11 | Páginas mostradas no navegador (retorno do login) têm idioma, título e cabeçalho |

### 2.3 Requisitos de segurança (RS)

| ID | Requisito |
|---|---|
| RS-01 | Nenhum segredo de cliente no complemento: cliente público com PKCE S256 |
| RS-02 | `state` aleatório conferido em tempo constante (proteção contra CSRF) |
| RS-03 | O receptor do login escuta só em 127.0.0.1, na porta exclusiva, só responde `GET /callback`, limita o tamanho da requisição e tem tempo limite |
| RS-04 | Tokens criptografados em repouso (DPAPI, por usuário do Windows); nada sensível no `nvda.ini` |
| RS-05 | Tokens nunca aparecem no log, na fala, em mensagens de erro ou em endereços |
| RS-06 | Toda conexão em HTTPS com verificação de certificado; toda requisição com tempo limite |
| RS-07 | Redirecionamentos HTTP não são seguidos (o token nunca é reenviado a outro endereço) |
| RS-08 | Respostas acima de 4 MB são recusadas sem esgotar memória |
| RS-09 | Identificadores e URIs vindos da rede são validados antes de entrar em um endereço (sem injeção de caminho) |
| RS-10 | Nenhum `eval`, `exec`, `pickle`, `subprocess` ou shell; navegador aberto só com endereços HTTPS fixos do Spotify |
| RS-11 | Complemento desligado nas telas seguras (logon, controle de conta) |
| RS-12 | Sair da conta e desinstalar apagam tokens e dados pessoais; atualizar mantém |
| RS-13 | Só os escopos OAuth necessários são pedidos |

### 2.4 Restrições

* Somente biblioteca padrão do Python e módulos do NVDA: sem dependências externas e sem DLLs próprias. Os módulos usados precisam existir no Python embutido no NVDA (`library.zip`). Por isso o receptor do login usa `socket` puro e não `http.server`.
* Compatível com NVDA 2024.1 (Python 3.11, 32 bits) até 2026.x (Python 3.13, 64 bits).
* O áudio vem de um dispositivo Spotify Connect (aplicativo do Spotify no computador, celular, caixa de som). Os termos do Spotify não permitem tocar o áudio fora dos aplicativos e SDKs oficiais, então o complemento **controla** a reprodução pela Web API; ele não decodifica áudio.
* Comandos de reprodução da Web API exigem **Spotify Premium**. Sem Premium, listar, buscar e criar playlists funcionam, e o complemento avisa que tocar exige Premium.
* Cada pessoa cria o seu próprio aplicativo em developer.spotify.com (gratuito) e informa o *Client ID* nas configurações. Aplicativos em modo de desenvolvimento do Spotify aceitam só os usuários cadastrados no painel do aplicativo.

## 3. Arquitetura

```
NVDA
 └─ globalPlugins/SpotifyNVDA/
     __init__.py        GlobalPlugin: atalhos, menu Ferramentas, fila de comandos em segundo plano
     messages.py        Textos traduzidos e tradução de erros em fala
     mainDialog.py      Janela "Spotify" (wx): login, busca, resultados, playlists, ações
     settingsPanel.py   Painel nas Configurações do NVDA: Client ID, porta, passo de volume
     background.py      Abre o aplicativo do Spotify em segundo plano, sem janela (1.1.0)
     library.py         Músicas das playlists: cache, busca, ordenação e gravação da ordem (1.2.0)
     player.py          Regras de reprodução: dispositivo, tocar/pausar, volume, continuar a última
     api.py             Cliente da Web API (HTTPS, renovação, erros, validação de IDs)
     auth.py            OAuth PKCE, receptor 127.0.0.1, sessão e renovação de tokens
     credentials.py     Armazenamento criptografado com DPAPI
     errors.py          SpotifyError(kind)
 installTasks.py        Apaga dados só na desinstalação de verdade
```

Camadas:

1. **Núcleo sem interface** (`errors`, `credentials`, `auth`, `api`, `player`): não importa `wx` nem módulos do NVDA; é testado com servidores simulados e no Python 3.11 e 3.13.
2. **Interface** (`mainDialog`, `settingsPanel`, `messages`): wxPython e `gui.guiHelper` do NVDA.
3. **Integração** (`__init__`): scripts, menu, fila de trabalho. Chamadas de rede nunca rodam na linha principal do NVDA: uma fila em segundo plano executa um comando por vez (evita condições de corrida quando a pessoa aperta o volume várias vezes) e a fala volta pela `queueHandler`.

### 3.1 Fluxo de login (RF-01)

1. A pessoa escolhe **Entrar com o Spotify**. Sem Client ID, o complemento explica e abre as configurações.
2. São gerados `code_verifier` (48 bytes aleatórios), `code_challenge` (SHA-256, base64url) e `state` (32 bytes aleatórios).
3. O receptor abre `127.0.0.1:<porta>` (padrão 8898, com `SO_EXCLUSIVEADDRUSE`).
4. O navegador padrão abre `https://accounts.spotify.com/authorize?client_id&response_type=code&redirect_uri&code_challenge_method=S256&code_challenge&state&scope`.
5. O Spotify redireciona para `/callback?code&state`. O receptor confere o `state` em tempo constante, mostra uma página acessível ("pode fechar esta aba") e fecha.
6. O código é trocado em `POST https://accounts.spotify.com/api/token` com o `code_verifier`.
7. `GET /v1/me` traz nome e plano; a sessão (tokens + nome) é criptografada e salva. O NVDA anuncia "Conectado ao Spotify como <nome>".

Tempo limite do login: 5 minutos. Cancelar é possível pelo mesmo botão.

### 3.2 Sessão persistente (RF-02)

* Arquivo `%APPDATA%\nvda\SpotifyNVDA-credentials.json`, com cada valor criptografado pelo DPAPI do usuário do Windows (inútil em outra conta ou outro computador).
* O *access token* é renovado 60 s antes de vencer e uma vez após um 401.
* Se o Spotify recusar o *refresh token* (`invalid_grant`, acesso revogado), a sessão é encerrada e a pessoa é avisada para entrar de novo.
* `installTasks.onUninstall` só apaga o arquivo em uma desinstalação de verdade, nunca durante uma atualização.

### 3.3 Reprodução (RF-04, RF-05, RF-10)

* **Dispositivo**: usa o ativo; senão o primeiro do tipo *Computer*; senão o primeiro da lista. Sem nenhum, abre o aplicativo do Spotify em segundo plano, espera até 15 s e toca nele.
* **Segundo plano (1.1.0)**: o executável é procurado em `%APPDATA%\Spotify\Spotify.exe` (instalador do site) e depois no atalho da Microsoft Store (`%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe`). É aberto por `ShellExecuteW` com os mesmos argumentos que o Windows usa ao iniciar o Spotify com o computador (`--autostart --minimized`) e `SW_SHOWMINNOACTIVE`. Durante 25 s, toda janela visível do processo `spotify.exe` é escondida (`SW_HIDE`) e, se tiver roubado o foco, ele volta para a janela anterior. Se o Spotify já estava aberto, nada é feito. Instalação desconhecida: usa o protocolo `spotify:` (pode mostrar a janela).
* **Por que não tocar dentro do NVDA**: os termos do Spotify só permitem tocar pelos aplicativos e SDKs oficiais; o SDK de reprodução exige um navegador com DRM, e clientes não oficiais (como o librespot) violam os termos. O aplicativo oficial escondido é a forma permitida de tocar sem janela.
* **Tocar/pausar**: pausa se estiver tocando; senão retoma; sem reprodução nenhuma, continua a última música.
* **Volume**: lê o volume do dispositivo e soma ou subtrai o passo (padrão 10%, de 0 a 100). Dispositivo que não aceita volume gera aviso.
* **Próxima/anterior**: depois do comando, espera meio segundo e anuncia a nova música.
* **Última música**: a cada ação, o complemento guarda (criptografado) música, contexto e posição. "Continuar última música" segue a ordem da RF-10 e, se o contexto não puder ser usado, toca só a música.

### 3.4 Erros

Toda falha vira `SpotifyError(kind)` e uma frase curta:

| kind | Situação | Fala (pt_BR) |
|---|---|---|
| notSignedIn | Sem sessão | Você não está conectado ao Spotify… |
| noClientId / invalidClientId | Client ID vazio ou recusado | Informe o Client ID… / O Spotify não reconheceu o Client ID… |
| auth | Sessão revogada/expirada | A sua sessão do Spotify terminou. Entre de novo. |
| premiumRequired | Conta sem Premium | Tocar músicas por aqui exige Spotify Premium. |
| noDevice | Nenhum dispositivo | Nenhum dispositivo do Spotify disponível… |
| restricted | Ação não permitida no dispositivo | Este dispositivo não permite esta ação. |
| rateLimited | 429 | O Spotify pediu para esperar… |
| network / timeout / server | Rede, tempo, 5xx | Sem conexão… / demorou demais… / O Spotify está com problemas… |
| portInUse | Porta do retorno ocupada | A porta … já está em uso… |
| cancelled / denied | Login cancelado / negado | Entrada cancelada. / Você não autorizou… |
| nothingToResume | Sem histórico | Não encontrei nenhuma música tocada recentemente. |

## 4. Interface

### 4.1 Janela Spotify (NVDA+Alt+P ou menu Ferramentas > Spotify)

Ordem de tabulação:

1. **Situação** (texto somente leitura): "Conectado como Fulano" ou "Não conectado". O plano (Premium ou gratuito) só aparece quando o Spotify informa: desde fevereiro de 2026, aplicativos em modo de desenvolvimento não recebem mais esse dado.
2. **Entrar com o Spotify** / **Sair da conta** (um ou outro, conforme a situação; durante o login vira **Cancelar entrada**).
3. **Buscar** (campo; Enter busca), **Tipo** (Músicas ou Playlists), botão **Buscar**.
4. **Resultados** (árvore; o rótulo diz o que ela mostra e quantos itens tem). Playlists são ramos: Seta para a direita abre e mostra as músicas, Seta para a esquerda fecha; Enter toca a playlist ou, numa música, toca a playlist a partir dela; Delete numa playlist exclui. Tipo de busca: Músicas, Playlists ou Músicas nas minhas playlists.
5. Botões: **Tocar <nome>** ou **Tocar/pausar** (um só botão, RF-17), **Adicionar à playlist…** (só para músicas), **Remover da playlist** (música de uma playlist sua), **Minhas playlists**, **Nova playlist…**, **Ordenar músicas…** (playlist ou música dentro dela), **Excluir playlist** (só playlist), **Fechar**. Botões que não servem para o item selecionado ficam indisponíveis e saem da tabulação.

Ao abrir já conectado, a lista mostra as playlists do usuário.

### 4.2 Nova playlist

Campos **Nome** (obrigatório, até 100 caracteres), **Descrição** (até 300), caixa **Playlist pública**; botões OK e Cancelar. Se uma música estiver selecionada na busca, ela é adicionada à nova playlist.

### 4.3 Ordenar playlist (1.2.0)

Caixas **Ordenar por** (ordem da playlist, título, artista, álbum, data em que foi adicionada, duração) e **Sentido** (crescente ou decrescente). Só nas playlists do usuário ou colaborativas aparece a caixa **Gravar esta ordem no Spotify**; marcada, pede confirmação e move as músicas uma a uma (nunca remove nada, então uma interrupção não perde músicas). Ordenar sem acentos: "Águas" vem antes de "Chega". Acima de 500 movimentos, a gravação é recusada e a ordem fica só na janela.

### 4.4 Configurações do NVDA > Spotify

**Client ID do Spotify**, **Porta do retorno** (1024–65535), endereço de retorno para copiar (somente leitura), **Passo do volume (%)**, **Abrir o aplicativo do Spotify quando não houver dispositivo**, **Manter o aplicativo do Spotify escondido** (padrão ligado), botões **Abrir o painel de desenvolvedor do Spotify** e **Sair da conta**.

## 5. Atalhos padrão

Verificados contra os comandos do NVDA 2026.1 (NVDA+Alt+C, M, R, S, T, Home, End e Tab já são usados pelo NVDA; NVDA+Alt+I e D pelo NVDAIAs).

| Ação | Atalho |
|---|---|
| Abrir a janela do Spotify | NVDA+Alt+P |
| Tocar ou pausar | NVDA+Alt+Espaço |
| Próxima música | NVDA+Alt+Seta para a direita |
| Música anterior | NVDA+Alt+Seta para a esquerda |
| Aumentar o volume | NVDA+Alt+Seta para cima |
| Abaixar o volume | NVDA+Alt+Seta para baixo |
| Anunciar o que está tocando | NVDA+Alt+A |
| Continuar a última música | NVDA+Alt+U |
| Sair da conta | sem atalho (pode ser definido em Definir comandos) |

## 6. Dados guardados

| Dado | Onde | Proteção |
|---|---|---|
| Client ID, porta, passo do volume, abrir aplicativo, manter escondido | `nvda.ini`, seção `[SpotifyNVDA]` | Não são segredos |
| Access token, refresh token, validade, nome e plano do usuário | `SpotifyNVDA-credentials.json` | DPAPI |
| Última música (URI, contexto, posição, nome) | `SpotifyNVDA-credentials.json` | DPAPI |
| Ordem escolhida para cada playlist (1.2.0) | `SpotifyNVDA-credentials.json` | DPAPI; apagada ao sair da conta |

## 7. Plano de testes

O detalhamento de cada caso fica em [SDD-TESTES.md](SDD-TESTES.md). Resumo:

| Suíte | Arquivo | Tipo |
|---|---|---|
| Unidades (Python 3.11 e 3.13) | `tests/test_pure.py` | Funcionais e de segurança do núcleo, com servidor simulado do Spotify |
| Interface | `tests/test_gui.py` | Funcionais da janela, das configurações e dos atalhos, com wxPython real |
| Acessibilidade | `tests/test_accessibility.py` | Rótulos, letras de atalho, ordem de tabulação, foco, fala, títulos, nomes lidos pelo MSAA do Windows, conflito de atalhos |
| Tradução | `tests/test_translation.py` | Interface toda em português, marcadores iguais, atalhos únicos em pt_BR |
| Segurança | `tests/test_security.py` | bandit, padrões proibidos, DPAPI real, OAuth, receptor, vazamento de tokens, injeção |
| NVDA real | `tests/test_nvda_runtime.py` | Todo módulo importado existe no Python do NVDA instalado; manifesto aceito |
| Pacote | `tests/run_all.py` | `build.py` gera um pacote válido |

O que não é automatizável (áudio real, fala real do NVDA e login com uma conta de verdade) está no roteiro manual [TESTES-MANUAIS.md](TESTES-MANUAIS.md).

## 8. Processo de versão (obrigatório em toda nova versão)

1. Atualizar `version` e `changelog` em `addon/manifest.ini` e `addon/locale/pt_BR/manifest.ini`, e o `CHANGELOG.md`.
2. Escrever ou atualizar os testes das funções novas ou alteradas e acrescentar os casos no `SDD-TESTES.md`.
3. Rodar **todas** as suítes: `python tests/run_all.py --note "o que mudou"`.
4. Se algo falhar: registrar em `reports/PROBLEMAS-<versão>.md` (ID, gravidade, causa, correção), corrigir e rodar de novo até **0 falhas**.
5. Gerar `reports/RELATORIO-TESTES-<versão>.md` com os números de `reports/execucoes.json`.
6. Só então gerar o pacote com `python build.py --release`, que **roda todas as suítes de novo e recusa gerar o pacote se algum teste falhar**.

## 9. Riscos e decisões

| Risco | Decisão |
|---|---|
| Spotify muda a Web API (fev/2026: `/tracks` → `/items`, `POST /users/{id}/playlists` → `POST /me/playlists`, busca até 10, `/me` sem `product`, playlists de terceiros sem `items`) | Cliente usa os caminhos novos e só cai para os antigos em 404/405; lê os dois nomes de campo; campos ausentes não quebram nada |
| Porta do retorno ocupada | Porta configurável; erro claro com a porta |
| Conta sem Premium | Mensagem específica; funções de biblioteca continuam |
| Spotify fechado | Abre o aplicativo e espera o dispositivo |
| Aplicativo em modo de desenvolvimento | Documentação explica como cadastrar o próprio e-mail no painel |
| Músicas de playlists de outras pessoas (desde 2026 o Spotify só mostra as das playlists próprias ou colaborativas) | A árvore explica isso no lugar das músicas; a playlist continua podendo ser tocada inteira; a busca dentro das playlists só lê as próprias e colaborativas |
| Excluir playlist | No Spotify, excluir é tirar da biblioteca; a confirmação diz como recuperar |
| Limite de requisições (429) | Respeita `Retry-After` curto (até 3 s) uma vez; senão avisa |

# SDD de testes do SpotifyNVDA

Especificação dos testes do complemento SpotifyNVDA: **o que** é testado, **como** e **quando**. Vale para todas as versões a partir da 1.0.0. Complementa a seção 7 do [SDD.md](SDD.md).

## 1. Objetivo

Garantir, a cada nova versão, que o SpotifyNVDA:

1. **funciona**: entrar, continuar conectado, playlists, busca, reprodução, atalhos, criar playlist, continuar a última música e sair (prefixo FUN);
2. **é acessível** para quem usa o NVDA (prefixo ACE);
3. **não expõe o usuário**: tokens, sessão, rede e computador (prefixo SEG).

## 2. Ambiente de teste

| Item | Como é feito |
|---|---|
| Interface | wxPython real (a mesma biblioteca do NVDA). No Windows, as janelas são reais; no Linux, com Xvfb |
| NVDA | Módulos simulados (`tests/nvda_stubs.py`), exceto o `gui.guiHelper`, que é o arquivo original do NVDA |
| Leitor de telas | No Windows, os nomes dos controles são lidos pelo MSAA (`oleacc`), a mesma interface que o NVDA usa nesses controles |
| Spotify | Servidor local (`tests/mock_spotify.py`) que imita `accounts.spotify.com` (PKCE, renovação com rotação, revogação) e a Web API no formato de 2026 (sem `product` em `/me`, `items` no lugar de `tracks`, busca até 10, Premium para tocar, dispositivo ativo), com um navegador simulado |
| Criptografia | DPAPI real do Windows |
| NVDA instalado | `tests/test_nvda_runtime.py` confere o `library.zip` do NVDA instalado |
| Python | 3.11 (NVDA 2024.1 a 2025.x) e 3.13 (NVDA 2026.x) |
| Análise estática | `bandit` e varredura de padrões proibidos |

## 3. Suítes

| Suíte | Arquivo | Tipo |
|---|---|---|
| Unidades | `tests/test_pure.py` (via `_run_unittest.py`) | FUN |
| Interface | `tests/test_gui.py` | FUN |
| Acessibilidade (inglês e português) | `tests/test_accessibility.py` | ACE |
| Tradução | `tests/test_translation.py` | ACE |
| Segurança | `tests/test_security.py` | SEG |
| NVDA instalado | `tests/test_nvda_runtime.py` | FUN |
| Pacote | `tests/run_all.py` (etapa build) | FUN |

`python tests/run_all.py --note "o que mudou"` roda tudo, grava o histórico em `reports/execucoes.json` e o resumo em `reports/ULTIMA-EXECUCAO.md`.

## 4. Casos funcionais (FUN)

| ID | Caso | Resultado esperado | Suíte |
|---|---|---|---|
| FUN-01 | Entrar com o Spotify | URL de autorização correta (code, S256, escopos, 127.0.0.1/callback), código trocado, nome anunciado; sem Client ID explica e abre as configurações; formato errado, recusa, cancelamento, tempo esgotado, porta ocupada e conta fora do User Management tratados | pure, gui |
| FUN-02 | Continuar conectado | Sessão lida depois de reiniciar o NVDA; token renovado antes de vencer e após 401; novo refresh token salvo; revogado encerra a sessão; erro de rede mantém a sessão; arquivo danificado = desconectado | pure, gui |
| FUN-03 | Listar playlists | Todas (paginação de 50 em 50), com nome, dono e número de músicas | pure, gui |
| FUN-04 | Tocar | Música ou playlist toca no computador; abre o aplicativo do Spotify sem dispositivo; avisa quando não há nenhum | pure, gui |
| FUN-05 | Atalhos | Tocar/pausar, próxima, anterior, volume para cima e para baixo (passo configurável, de 0 a 100) | pure, gui |
| FUN-06 | Criar playlist e adicionar música | Cria com nome, descrição e visibilidade; nome vazio recusado; adiciona a música selecionada; só playlists próprias oferecidas | pure, gui |
| FUN-07 | Buscar músicas | Resultados com nome, artista e álbum; busca vazia e sem resultados anunciadas | pure, gui |
| FUN-08 | Buscar playlists | Resultados sem itens nulos, no máximo 10 por busca | pure, gui |
| FUN-09 | Sair da conta | Apaga sessão e última música; comandos passam a pedir login | pure, gui |
| FUN-10 | Continuar última música | Retoma reprodução pausada; senão a mais recente entre a guardada (com posição) e o histórico da conta; contexto inválido toca só a música; sem histórico avisa | pure, gui |
| FUN-11 | O que está tocando | Música, artista e estado; nada tocando anunciado | pure, gui |
| FUN-12 | Erros | 429 curto repetido, 429 longo, 5xx, rede, Premium, sem login: frase certa | pure, gui |
| FUN-13 | Janela Spotify | Abre pelo atalho e menu, reaproveita a janela, estado conectado/desconectado | gui |
| FUN-14 | Configurações | Client ID, porta e endereço de retorno, passo do volume, abrir aplicativo | gui |
| FUN-15 | Encerrar | Fecha a janela, remove o painel, sem erros no log | gui |
| FUN-16 | NVDA real e Python | Todo módulo e função usados existem no NVDA instalado; manifesto aceito; código compila em 3.11 e 3.13 | runtime, pure |
| FUN-17 | Pacote | `build.py` valida o manifesto e gera o `.nvda-addon` com tudo que é preciso | run_all |
| FUN-20 | Músicas das playlists em árvore (1.2.0) | Playlist é ramo; Seta para a direita (tecla real enviada à árvore) lê e mostra as músicas na ordem, anuncia quantas; Seta para a esquerda fecha; Enter toca a playlist a partir da música; cache; arquivo local indisponível; playlist de outra pessoa explicada; paginação de 50; formato antigo (`track`) aceito | pure, gui |
| FUN-21 | Busca dentro das playlists (1.2.0) | Sem acentos e maiúsculas; só playlists próprias ou colaborativas são lidas; playlists encontradas abertas só com as músicas que combinam; anúncio e rótulo com o total; música encontrada toca dentro da playlist | pure, gui |
| FUN-22 | Ordenar playlist (1.2.0) | Seis critérios, crescente e decrescente, estável; ordem lembrada por playlist; gravar no Spotify só nas próprias, com confirmação, movendo uma música por vez com snapshot encadeado, sem perder arquivos locais; plano de movimentos correto para qualquer ordem; limite de 500 movimentos; caminho antigo `/tracks` | pure, gui |
| FUN-23 | Excluir playlist (1.2.0) | Botão e tecla Delete pedem confirmação; Não mantém; Sim usa `DELETE /me/library` (alternativa `/followers`), tira da árvore, atualiza a contagem e seleciona a próxima | pure, gui |
| FUN-19 | Segundo plano (1.1.0) | Spotify aberto com `--autostart --minimized` e sem foco; só janelas do `spotify.exe` iniciado pelo complemento são escondidas; foco devolvido; Spotify já aberto não é tocado; opção desligada não esconde; instalação desconhecida usa o protocolo | pure, gui |
| FUN-18 | Formato da Web API de 2026 | `/me` sem `product`, playlists de terceiros sem `items`, endpoints novos usados primeiro | pure |

## 5. Casos de acessibilidade (ACE)

Referências: WCAG 2.2 AA (aplicável a software), guia de complementos do NVDA, práticas de acessibilidade do Windows.

| ID | Caso | Resultado esperado |
|---|---|---|
| ACE-01 | Nome acessível | Todo controle com foco tem nome; o nome lido pelo MSAA é igual ao rótulo (inclui campos numéricos) |
| ACE-02 | Letras de atalho | Todo botão e rótulo tem letra com Alt, sem repetição, em inglês e português |
| ACE-03 | Ordem de tabulação | Situação, entrar/sair, buscar, tipo, buscar, resultados, ações, fechar; Nova playlist: nome, descrição, pública, adicionar música, OK, Cancelar |
| ACE-04 | Controles escondidos ou indisponíveis | Fora da ordem de tabulação |
| ACE-05 | Teclado | Enter busca, Enter na lista toca, setas andam na lista, Esc fecha |
| ACE-06 | Foco | Começa em Entrar; após entrar, nas playlists; após buscar, nos resultados; após sair ou cancelar, em Entrar |
| ACE-07 | Anúncios | Aguardando login, resultados, reprodução e erros falados |
| ACE-08 | Títulos | Toda janela e a categoria das configurações têm título |
| ACE-09 | Atalhos sem conflito | Nenhum conflito com os comandos do NVDA instalado nem com outros complementos instalados |
| ACE-10 | Definir comandos | Todo comando com descrição, na categoria Spotify |
| ACE-11 | Página no navegador | Idioma, título, `main` e cabeçalho |
| ACE-12 | Tradutores | Todo texto traduzível com comentário `Translators:` |
| ACE-13 | Situação | Texto somente leitura alcançável com Tab |
| ACE-14 | Rótulo da lista | Diz o que mostra e quantos itens; MSAA acompanha a mudança |
| ACE-15 | Desconectado | Só Situação, Entrar e Fechar na tabulação |
| ACE-16 | Documentação | HTML com idioma, títulos e tabelas reais |
| ACE-18 | Árvore de playlists (1.2.0) | Pelo MSAA, a playlist é lida com o nome, "recolhido"/"expandido" e nível 0; a música, com o nome e nível 1; janela Ordenar com rótulos, letras de atalho e ordem de tabulação; Gravar no Spotify ausente nas playlists de outras pessoas |
| ACE-17 | Tradução completa | Tudo traduzido para pt_BR, marcadores, letras de atalho e reticências mantidos |

## 6. Casos de vulnerabilidade (SEG)

Referências: OWASP ASVS 4 (V2, V3, V6, V8, V9, V13), RFC 8252 (OAuth para aplicativos nativos), RFC 7636 (PKCE), recomendações da NV Access.

| ID | Caso | Resultado esperado |
|---|---|---|
| SEG-01 | Tokens em repouso | Arquivo sem tokens nem nome em texto puro; DPAPI em uso; ilegível sem DPAPI; nada secreto no nvda.ini |
| SEG-02 | Vazamento | Tokens e endereço com código nunca na fala, log ou mensagens |
| SEG-03 | TLS | Verificação de certificado e nome ligadas; nenhum código que desligue |
| SEG-04 | Tempo limite | Toda requisição com tempo limite |
| SEG-05 | Endereços | Só HTTPS em domínios spotify.com |
| SEG-06 | Redirecionamento | Não seguido; token nunca vai a outro endereço |
| SEG-07 | Resposta gigante | Recusada sem ler tudo |
| SEG-08 | Injeção | IDs e URIs com caracteres de caminho recusados antes da rede; texto da busca não altera parâmetros |
| SEG-09 | OAuth | PKCE S256, verificador de 64 caracteres, state aleatório comparado em tempo constante, sem segredo de cliente, retorno só em 127.0.0.1/callback, state diferente recusado (CSRF) |
| SEG-10 | Receptor local | Só 127.0.0.1, porta exclusiva, 404 em outros caminhos, 405 em POST, requisição grande recusada, porta liberada |
| SEG-11 | Página de retorno | Nada do endereço repetido na página (XSS), textos escapados, no-store, CSP e nosniff |
| SEG-12 | Sair e desinstalar | Sair apaga a sessão; desinstalar apaga; atualizar mantém |
| SEG-13 | Escopos | Só os nove escopos usados |
| SEG-14 | Navegador | Só os endereços HTTPS fixos do Spotify |
| SEG-15 | Telas seguras | Complemento desligado |
| SEG-16 | Funções perigosas e dependências | Sem eval, exec, pickle, subprocess, shell; sem bibliotecas de terceiros |
| SEG-17 | bandit | Nenhum problema médio ou alto; os baixos são só os justificados no código |
| SEG-18 | Detalhes de erro | Limitados a 200 caracteres |
| SEG-20 | Mudanças nas playlists (1.2.0) | IDs conferidos antes de ler, reordenar ou excluir; excluir e gravar ordem sempre pedem confirmação; gravar ordem só move (nunca remove); nenhum escopo novo |
| SEG-19 | Segundo plano (1.1.0) | Só executa os caminhos fixos do Spotify com argumentos fixos; nunca esconde janelas de outros programas |

## 7. Critérios de aprovação

* Uma versão só é gerada com **0 falhas** em todas as suítes (`build.py --release` recusa gerar o pacote se algo falhar).
* Falha de SEG ou ACE é sempre bloqueante.
* Cada problema encontrado vai para `reports/PROBLEMAS-<versão>.md`: problemas do complemento (P-xx) e dos testes (T-xx), com gravidade, causa e correção.

## 8. Fora da automação

Áudio real, fala real do NVDA e login com uma conta de verdade: roteiro em [TESTES-MANUAIS.md](TESTES-MANUAIS.md).

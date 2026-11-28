# Ragas · central de vagas

Contexto do projeto para o Claude Code. Este arquivo é lido automaticamente no começo de cada conversa.

## O que é

Sistema pessoal que coleta vagas de dev júnior, filtra, manda e-mail com as novas e mostra tudo num painel estático. Roda de graça no GitHub (Actions coleta 2x por dia, Pages hospeda o painel em `docs/`). Também serve de portfólio.

Quem usa: uma pessoa que trabalha com suporte, termina a faculdade no meio de 2027 e busca o primeiro emprego como dev júnior. Responda sempre em português do Brasil, em linguagem simples, e explique o que mudou depois de mexer.

## Critérios das vagas (não mudar sem pedir)

- Dev júnior em Salvador/região ou remoto no Brasil.
- Remoto do exterior só se o inglês exigido for até intermediário.
- Suporte técnico é uma área como as outras: aparece para quem marca no perfil, sem exigência de salário.
- Salário mínimo é geral (perfil `salario_min`, config `min_salary`): vale para qualquer vaga que informa salário. Vaga sem salário continua aparecendo, a não ser que a pessoa desligue (`sem_salario`).
- Notícias de processos seletivos de grandes empresas entram numa seção própria.
- Notícia de vaga de outro estado fica de fora (vale o `state` do config ou o estado do perfil). Notícia remota, EaD, nacional ou sem lugar citado aparece para todos.
- Tudo isso fica em `config.toml`. Prefira ajustar lá a mexer no código.

## Estrutura

```
config.toml        termos de busca, filtro, e-mail
vagas/             coletor em Python 3.11+, só biblioteca padrão
  sources/         uma fonte por arquivo (gupy, adzuna, workday, smartrecruiters,
                   greenhouse, lever, ashby, noticias; freelas: workana, freelas99)
  filters.py       regras de júnior, idade da vaga, relevância, notícias
  storage.py       junta e atualiza docs/data/jobs.json
  emailer.py       monta e envia o e-mail
  runner.py        comandos run, check, perfil e avisos
  firebase.py      robô lê o Firebase (liberados e perfis) para os avisos por pessoa
  avisos.py        quem recebe o quê: vagas novas filtradas pelo perfil de cada pessoa
  telegram.py      bot do Telegram: liga a conversa pelo código do perfil e manda os avisos
docs/              painel em HTML, CSS e JS puro (sem build)
  app.js           lista de vagas, abas, filtros
  store.js         regras do quadro de candidaturas
  kanban.js        tela do quadro (arrastar, menu, folha no celular)
  sync.js          login e sincronização com Firebase
  login.js         tela de entrada (login obrigatório quando o Firebase está ligado)
  perfil.js        regras e filtro do perfil (cópia em JS de evaluate_profile) e janela "Meu perfil"
  perfil-padrao.json  perfil do config.toml e opções do formulário (python -m vagas perfil)
  admin.js         janela "Acessos": o admin libera ou recusa quem criou conta
  dados.html       página "Seus dados": o que é guardado, quem vê, botão de apagar a conta
  conta.js         janela "Apagar minha conta" (abre com #apagar-conta; quem apaga é Sync.deleteAccount)
  sw.js            painel instalável (PWA): rede primeiro, cópia para abrir sem internet
  manifest.webmanifest  nome, cores e ícones do app (icon-192, icon-512, icon-maskable-512)
tests/             pytest (Python) e node:test (store.js, perfil.js)
.github/workflows/ agendamento
```

## Comandos

```bash
python -m pytest -q                  # 208 testes, todos offline
node --test tests/store.test.js tests/perfil.test.js   # 30 testes do quadro e do perfil (Node 20+)
python tests/make_paridade.py        # regrava o teste de paridade Python x JS do filtro do perfil
python -m vagas check                # testa as fontes sem salvar nada
python -m vagas check --source gupy  # uma fonte só
python -m vagas run                  # coleta de verdade, salva e envia e-mail
python -m vagas perfil               # regrava docs/perfil-padrao.json depois de mudar o [filter]
python -m vagas avisos               # robô entra no Firebase, liga conversas novas do Telegram e lista quem receberia aviso
python -m vagas avisos --previa      # salva em out/ o aviso de cada pessoa (últimos 3 dias), sem enviar
```

Rode os testes depois de qualquer mudança em `vagas/` ou `docs/store.js`. Para mudanças visuais em `docs/`, abra `docs/index.html` por um servidor local (`python -m http.server -d docs 8000`) e confira no navegador, no tamanho de computador e de celular (390px).

## Regras importantes

- **Nunca leia, mostre nem comite o `.env`.** Ele tem a senha de app do Gmail e as chaves da Adzuna. Está no `.gitignore`. O `.env.example` é só um modelo em branco e deve continuar em branco.
- **`docs/data/jobs.json` é escrito pelo robô do GitHub Actions.** Não edite à mão. Em conflito de Git nesse arquivo, vale a versão do repositório remoto.
- Antes de enviar ao GitHub: `git pull --rebase origin main`, depois `git push`.
- Sem dependências externas no Python e sem etapa de build no painel. Mantenha assim, a não ser que eu peça.
- Uma fonte que falha só gera aviso. Nunca deixe uma fonte derrubar a coleta inteira.
- A Gupy busca a frase exata do termo ("estagio desenvolvimento" não acha nada; "estágio" acha tudo). Antes de pôr um termo novo em `config.toml`, teste com `check --source gupy`. Estados da coleta presencial ficam em `sources.gupy.states`.
- Fontes de vagas usam endpoints públicos sem documentação oficial (principalmente a Gupy, `portal.gupy.io/api/job-search/jobs`). Se uma fonte quebrar, rode `check --source nome` e leia o erro antes de mudar qualquer coisa.
- Textos do painel e do e-mail em português, frases curtas, sem jargão.
- Visual: cores em variáveis no topo de `docs/style.css`. `--neon` é o verde de preenchimento (botões, logo), `--accent` o verde de texto e borda (mais escuro no tema claro, para dar leitura), `--glow-c` a cor do brilho. Logo é o pin com R desenhado direto no HTML (classe `pin`), para seguir o tema. Tema fica no menu da conta. No celular (até 860px) as abas viram a barra de navegação de baixo (`bottom-nav`).
- O filtro do perfil existe em Python (`evaluate_profile` e `evaluate_freela` em `filters.py`) e em JS (`evaluate` e `evaluateFreela` em `docs/perfil.js`). Mudou um, mude o outro e rode `python tests/make_paridade.py`; o teste de paridade compara os dois.

## Quadro de candidaturas

- Etapas: Inscrição feita, Dinâmica e testes, Entrevista, Proposta, Encerrada.
- Dá para encerrar de qualquer etapa. O cartão guarda em que etapa parou (`stoppedAt`) e o motivo (`closedReason`).
- Dados no navegador (`localStorage`, chave `vagas-junior:candidaturas:v1`). Com Firebase configurado em `docs/firebase-config.js`, sincroniza entre aparelhos. Em conflito, vale a alteração mais recente (`updatedAt`).
- Vagas salvas e ocultas ainda não sincronizam.

## Ideias combinadas e ainda não feitas

1. Botão "coletar agora" no painel, com no máximo 3 usos por dia.
2. Rodar localmente como aplicativo (primeiro um arquivo `.bat`, depois talvez um `.exe`).
3. Fonte de vagas remotas do exterior (quadros globais).
4. Sincronizar vagas salvas e ocultas.
5. Confirmar por que duas vagas da Gupy aparecem com a empresa "ADMINISTRADOR DE REDES".
6. (concluída em 28/11/2026) Abrir para amigos testarem (uso real, não venda):
   - Perfil por pessoa no Firestore (cidade, remoto, tecnologias, salário mínimo).
   - Robô coleta mais amplo; cada pessoa filtra no painel pelo próprio perfil.
   - (feito) Acesso por pedido: quem cria conta fica pendente em `acesso/{uid}`; o admin libera em "Acessos". Regras no README, passo 9.
   - (feito) Cadastro com e-mail e senha, além do Google.
   - Aviso de vagas novas por pessoa, por e-mail ou Telegram (a pessoa escolhe). Em andamento: A (robô lê o Firebase com a conta `FIREBASE_ROBO_EMAIL`/`FIREBASE_ROBO_SENHA`) e B (e-mail por pessoa; o e-mail do config.toml só sai se o Firebase falhar) C (opções no Meu perfil, campo `aviso`: ativo, canal, frequência, telegram_codigo) e D (Telegram: Secret `TELEGRAM_BOT_TOKEN`, `telegram_bot` no `[avisos]` do config, conversa em `telegram/{uid}`; sem ligar, vai por e-mail) feitas.
   - (feito) Painel instalável no celular (PWA): `sw.js` + `manifest.webmanifest`, item "Instalar o app" no menu da conta. Só registra em https (no localhost não, para não guardar cópia velha enquanto mexe).
   - (feito) Página "Seus dados" (`dados.html`) e "Apagar minha conta". Se mudar o que é guardado, atualize o texto dela.
7. Central de notícias do mundo dev (depois de terminar a ideia 6, com plano próprio): notícias que não são de vaga vão para uma central separada; notícias de vaga continuam junto com as vagas.
8. (concluída em 28/11/2026) Freelas de TI, numa aba própria "Freelas". Plano em 3 etapas: 1 coleta, 2 aba no painel, 3 perfil e avisos.
   - (feito) Etapa 1: fontes `workana` (JSON da página /jobs com o cabeçalho X-Requested-With) e `freelas99` (lê o HTML; traz o nível Iniciante/Intermediário/Especialista). Item com `tipo = "freela"`, filtro `classify_freela` (descarta o que não é TI e golpe, lista `FREELA_BLOCK` + `freela_bloquear` no config), sai do arquivo em `keep_days_freela` dias. O nome do cliente não é guardado (o jobs.json é público). O e-mail e os avisos ainda não mandam freelas.
   - Freela não "encerra" quando some: o robô só lê as primeiras páginas.
   - (feito) Etapa 2: aba "Freelas" (`data-tab="freelas"`, também na barra do celular), cartão próprio (`freelaRow` em app.js), filtros só da aba (classes `only-freelas`/`only-vagas` em index.html, modo `.filters.freela-mode`), e a aba Salvas junta vagas e freelas.
   - (feito) Etapa 3: campo `freelas` no perfil (ver, nivel, orcamento_min, propostas_max, so_minhas_techs, avisar). O filtro existe em Python (`freela_prefs`/`evaluate_freela`) e em JS (`freelas`/`evaluateFreela` em perfil.js), e a paridade fica em `paridade.json` → `freelas`. Quem liga "avisar" recebe até 5 freelas novos (`avisos.MAX_FREELAS`) no e-mail ou no Telegram. Desligar "ver" esconde a aba.

## Firebase (ligado)

- Projeto `app-vagas-89a57`, plano Spark. Login com Google, Firestore em `southamerica-east1`.
- Domínios autorizados: `localhost` e `ravas7.github.io`.
- Testado ao vivo em 24/11/2026 pelo `localhost`: login e gravação em `users/{uid}/candidaturas` funcionaram.
- Se der erro ao entrar, leia a mensagem no quadro e o passo 9 do README.

# Ragas · central de vagas

Busca vagas de desenvolvimento para nível júnior em várias fontes, descarta o que não serve (sênior, pleno, pede muita experiência), **manda um e-mail só com as vagas novas** e mantém um **painel web** com filtros para você acompanhar tudo.

Além das vagas de dev, ele acompanha:

- **Só o que dá para trabalhar:** vagas remotas (do Brasil ou do exterior) ou presenciais/híbridas em Salvador e região metropolitana (Lauro de Freitas, Camaçari, Simões Filho e outras, lista em `allowed_cities`). "El Salvador" não conta como Salvador. Presencial sem local informado é descartada (`unknown_location = "incluir"` muda isso). Remoto no exterior ganha o selo "Remoto no exterior"; para escondê-lo, `remote_abroad = false`.
- **Limite de inglês:** a descrição é lida atrás do nível pedido. Vaga que exige inglês **avançado, fluente ou C1/C2** é descartada; **básico e intermediário (A1 a B2)** passam, e sem informação também passa, com o selo "Inglês não informado". Nível citado como diferencial ("avançado é um plus") não conta como exigência. O limite vale para todas as vagas, não só as do exterior; ajuste em `max_english` (`"basico"`, `"intermediario"` ou `"qualquer"`).
- **Áreas correlatas:** dados, BI, QA, DevOps/cloud, segurança e infraestrutura. Essas só entram quando o título diz "júnior" (ou trainee), para não encher de vaga que não combina. 
- **Suporte técnico com piso salarial:** N1, N2, service desk e help desk só aparecem se a vaga informar salário igual ou acima de `support_min_salary` (R$ 3.200 por padrão). Sem salário informado, a vaga é descartada; troque `support_unknown_salary` para `"incluir"` se preferir ver todas e conferir o valor você mesmo. Suporte ao cliente (SAC, atendimento) não conta como suporte técnico.
- **Grandes empresas e multinacionais:** vagas de empresas da lista interna (Itaú, Nubank, Accenture, Microsoft...) ganham selo e +10 de nota, e há fontes só de sites de carreira de multinacionais (Workday, SmartRecruiters).
- **Processos seletivos nas notícias:** programas de trainee e anúncios de seleção em tecnologia publicados pela imprensa, buscados no Google Notícias. Aparecem no painel com o selo "Notícia" e numa seção própria do e-mail.

Roda de graça no GitHub: o GitHub Actions executa o coletor 2 vezes por dia e o GitHub Pages hospeda o painel. Não precisa de servidor.

## Como funciona

```
 Gupy · Adzuna · Workday · SmartRecruiters    (vagas.sources)
 Greenhouse · Lever · Ashby · Notícias
              │  coleta
              ▼
   filtro de júnior + nota de relevância     (vagas.filters)
              │
              ▼
     junta com o que já se conhecia          (vagas.storage)
        │                      │
        ▼                      ▼
 e-mail com as vagas      docs/data/jobs.json  ──►  painel (docs/index.html)
 novas (SMTP/Gmail)       (commitado no repo)       hospedado no GitHub Pages
```

- **Uma vaga só é avisada uma vez.** O e-mail sai com as vagas ainda não avisadas. Se o envio falhar, elas continuam pendentes e vão na próxima execução.
- **Duplicadas** (mesma vaga em duas fontes) são unificadas por título + empresa + local.
- **Vaga que sumiu** da fonte fica como "encerrada" no painel; depois de 45 dias sem aparecer, é removida.
- Se **todas** as fontes falharem, a execução termina com erro (o GitHub te avisa por e-mail) e nada é sobrescrito. Se só uma falhar, o painel mostra um aviso no rodapé.

## Estrutura

```
config.toml          tudo que você ajusta: termos de busca, filtro, e-mail
vagas/               o coletor (Python 3.11+, sem dependências externas)
  sources/           uma fonte por arquivo (gupy, adzuna, workday, smartrecruiters,
                     greenhouse, lever, ashby, noticias)
  filters.py         regras de júnior, áreas correlatas, grandes empresas e notícias
  storage.py         junta/atualiza o jobs.json
  emailer.py         monta e envia o e-mail
  runner.py          orquestra tudo e traz os comandos run / check
docs/                o painel (HTML + CSS + JS puro) e os dados
  store.js           regras do quadro de candidaturas (etapas, encerrar, mesclar)
  kanban.js          tela do quadro (arrastar, menu, janela no celular)
  sync.js            sincronização opcional com o Firebase
tests/               128 testes em Python e 18 em JS, todos offline
.github/workflows/   agendamento
```

## Passo a passo

### 1. Rodar no seu computador

```bash
python -m pytest -q            # opcional: pip install pytest
node --test tests/store.test.js  # opcional: testes do quadro (Node 20+)
python -m vagas check          # testa as fontes e o filtro, não salva nada
python -m vagas run --no-email # coleta, salva e gera out/email_preview.html
```

Precisa de Python 3.11 ou mais novo.

### 2. Senha de app do Gmail (para o e-mail)

1. Ative a verificação em duas etapas na sua conta Google.
2. Entre em <https://myaccount.google.com/apppasswords>, crie uma senha de app e copie as 16 letras.
3. Copie `.env.example` para `.env` e preencha `EMAIL_USER` e `EMAIL_APP_PASSWORD`.
4. Rode `python -m vagas run`. O e-mail chega na sua caixa.

Use sempre a senha de app, nunca a senha da conta. O `.env` está no `.gitignore`.

### 3. Chave do Adzuna (opcional, mas recomendado)

O Adzuna é um agregador com API oficial e gratuita, então é a fonte mais estável. Crie uma conta em <https://developer.adzuna.com/> e coloque `ADZUNA_APP_ID` e `ADZUNA_APP_KEY` no `.env`. Sem as chaves, ele é ignorado.

### 4. Subir para o GitHub

1. Crie um repositório (público, para o Pages grátis) e envie esta pasta.
2. Em **Settings → Secrets and variables → Actions → New repository secret**, crie: `EMAIL_USER`, `EMAIL_APP_PASSWORD`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (e `EMAIL_TO` se quiser receber em outro e-mail).
3. Em **Settings → Pages**, escolha *Deploy from a branch*, branch `main`, pasta `/docs`.
4. Em **Actions → Buscar vagas → Run workflow** para a primeira coleta. Depois ele roda sozinho às 08h e 18h (Brasília); mude em `.github/workflows/vagas.yml`.

O painel fica em `https://SEU_USUARIO.github.io/NOME_DO_REPO/`, e o link já vai no e-mail.

> Repositório público significa que `docs/data/jobs.json` também é público. Ele só tem vagas, nada seu. Suas marcações (salvar, candidatei-me) ficam apenas no navegador.

### 5. Ajustar o filtro

Tudo em `config.toml`. As mais usadas: `preferred_states` (ex.: `["BA"]`), `include_estagio`, `exclude_title_terms` (ex.: `["suporte", "sap"]`), `dev_terms_extra` (ex.: `["devops"]`) e `min_score`. Rode `python -m vagas check` e veja as seções "aceitos" e "descartados" para entender o que o filtro está fazendo.

Como o salário é lido: o Adzuna informa em campo próprio (valores estimados por ele são ignorados; acima de R$ 30 mil, tratado como anual e dividido por 12). Nas demais fontes, o coletor procura "R$ ..." logo depois de palavras como salário, remuneração, faixa salarial e bolsa. Gupy, Workday e SmartRecruiters quase nunca trazem salário na lista, então suporte tende a vir mais do Adzuna e de descrições que citem o valor.

Como a nota é calculada (suporte técnico parte de 40 e fica abaixo das vagas de dev): termo de dev no título (+20; área correlata +10), "júnior" no título (+50) ou só na descrição (+20), grande empresa (+10), remoto (+10), estado preferido (+10), pede até 2 anos (+5), pede mais que o limite (−30).

Notícias têm regra própria: o título precisa parecer anúncio de seleção ("processo seletivo", "trainee", "abre vagas"...) e falar de tecnologia. Concurso público, prefeitura, resultado e notícia de demissão são descartados. Nota: seleção +20, tecnologia +20, trainee/júnior +30, grande empresa +25, publicada nos últimos 7 dias +10; o mínimo é `news_min_score`.

A lista de grandes empresas está em `BIG_COMPANIES` (`vagas/filters.py`); acrescente as suas em `big_companies_extra`.

### 6. Se a Gupy não trouxer vagas

A Gupy **não tem API pública documentada**: o coletor usa o endereço que o próprio portal chama hoje, e esse endereço já mudou duas vezes (os endereços `employability-portal.gupy.io` e `portal.api.gupy.io` saíram do ar; hoje é `portal.gupy.io/api/job-search/jobs`). Se `python -m vagas check --source gupy` mostrar erro ou 0 vagas:

1. Abra <https://portal.gupy.io>, aperte **F12**, aba **Network**, filtre por **Fetch/XHR**.
2. Pesquise "desenvolvedor junior" no site e clique na requisição que devolve a lista de vagas (resposta em JSON).
3. Copie a URL sem a parte depois do `?` para `url` no `config.toml`, e o nome do parâmetro da busca (o que leva o texto que você digitou) para `term_param`. Faça o mesmo com `limit_param` e `offset_param` se os nomes forem outros.
4. Rode o `check` de novo. O leitor aceita vários nomes de campo (`name`/`title`, `jobUrl`/`url`, etc.).

### 6b. Buscar mais vagas de Salvador e remotas

O filtro de local roda sempre, mas só vê o que as fontes trazem. Para trazer mais vagas de lá:

- **Adzuna:** já busca "Salvador" com raio de `distance_km` e, em separado, o país todo com a palavra "remoto" (`wheres` no `config.toml`).
- **Gupy:** na busca do portal, filtre por estado/cidade e por "remoto" e, no DevTools, anote os nomes dos parâmetros que aparecem na requisição. Os nomes que já vêm no `config.toml` são `state` (nome completo, como `Bahia`) e `workplaceType`. Se mudarem, liste os novos em `variants`, por exemplo `variants = [ { state = "Bahia" }, { workplaceType = "remote" } ]`. Sem isso, a Gupy devolve vagas do país inteiro e a maioria cai fora no filtro de local.

Vagas remotas do exterior só chegam pelas fontes de empresas (Greenhouse, Lever, Ashby, Workday, SmartRecruiters). Como essas listas começam quase vazias, é você quem escolhe as empresas (passo 7).

### 7. Empresas grandes e multinacionais

Cada sistema de recrutamento tem um jeito de listar as empresas. Veja o endereço da página de vagas da empresa e use a tabela:

| Endereço da página de vagas | Fonte | O que colocar no `config.toml` |
|---|---|---|
| `xxx.wd5.myworkdayjobs.com/Site` | Workday | o endereço inteiro, em `sites` |
| `jobs.smartrecruiters.com/Nome` | SmartRecruiters | `"Nome"` em `companies` (maiúsculas importam) |
| `boards.greenhouse.io/nome` | Greenhouse | `"nome"` em `companies` |
| `jobs.lever.co/nome` | Lever | `"nome"` em `companies` |
| `jobs.ashbyhq.com/nome` | Ashby | `"nome"` em `companies` |

Já vêm configurados Accenture, Salesforce, NVIDIA e Adobe (Workday) e Bosch e Visa (SmartRecruiters). Grandes empresas brasileiras costumam usar a Gupy, que já é coberta pela busca geral. Slug ou endereço errado só gera um aviso, não derruba a execução.

O Workday só guarda vagas com "Brazil/Brasil" ou "Remote" no local. Vagas multi-local ("2 Locations") são descartadas por padrão (`keep_multi_location`).

### 8. Notícias de processos seletivos

A fonte `noticias` usa o RSS de busca do Google Notícias, com buscas fixas (`queries`) e buscas montadas com os nomes das grandes empresas (`company_queries = true`). Rode `python -m vagas check --source noticias` e leia a lista de aceitos e descartados para ajustar `news_exclude_extra` e `news_min_score`. O link de cada notícia abre a matéria no veículo.

### 9. Quadro de candidaturas e sincronização entre aparelhos

A aba **Candidaturas** é um quadro Kanban: Inscrição feita → Dinâmica e testes → Entrevista → Proposta → Encerrada. No computador você arrasta os cartões; no celular escolhe a etapa no topo e usa **Avançar** ou **Mover ou encerrar**. Dá para encerrar a candidatura de qualquer etapa (Recusada pela empresa, Sem retorno, Desisti, Vaga cancelada, ou Fui contratado quando está em Proposta). O cartão vai direto para Encerrada e guarda em que etapa parou. Cada cartão aceita um próximo passo com data (fica em destaque quando falta pouco) e uma anotação.

**Sem configurar nada**, tudo fica salvo no navegador. Use *Baixar backup* e *Importar backup* para levar para outro aparelho ou guardar uma cópia.

**Para sincronizar entre aparelhos** (opcional, de graça no plano Spark do Firebase):

1. Em [console.firebase.google.com](https://console.firebase.google.com), crie um projeto (pode desligar o Google Analytics).
2. **Authentication > Sign-in method**: ative **Google** e **E-mail/senha**. Em **Configurações > Domínios autorizados**, adicione `SEU-USUARIO.github.io`. Em **Templates**, dá para trocar o idioma do e-mail de "nova senha" para português.
3. **Firestore Database > Criar banco de dados** (modo produção, região `southamerica-east1`).
4. Na aba **Regras** do Firestore, cole e publique (troque `SEU_EMAIL` pelo seu e-mail, o do admin):
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       function logado() { return request.auth != null; }
       function admin() {
         return logado() && request.auth.token.email == 'SEU_EMAIL'
                && request.auth.token.email_verified == true;
       }
       function aprovado() {
         return logado() && exists(/databases/$(database)/documents/acesso/$(request.auth.uid))
                && get(/databases/$(database)/documents/acesso/$(request.auth.uid)).data.status == 'aprovado';
       }

       // dados de cada pessoa: só ela, e só depois de liberada
       match /users/{uid}/{document=**} {
         allow read, write: if logado() && request.auth.uid == uid && (admin() || aprovado());
       }

       // pedidos de acesso: a pessoa cria o próprio pedido (pendente); só o admin decide
       match /acesso/{uid} {
         allow read: if admin() || (logado() && request.auth.uid == uid);
         allow create: if logado() && request.auth.uid == uid
                       && request.resource.data.keys().hasOnly(['email', 'nome', 'status', 'pedidoEm'])
                       && request.resource.data.status == 'pendente'
                       && request.resource.data.email == request.auth.token.email
                       && request.resource.data.nome is string && request.resource.data.nome.size() <= 60;
         allow update, delete: if admin();
       }
     }
   }
   ```
   **Como funciona o acesso:** qualquer pessoa cria conta na tela de entrada. Na primeira vez, o painel cria sozinho um pedido em `acesso/{uid}` e mostra "Pedido enviado". Você (admin) vê o link **Acessos** no topo, com o número de pedidos esperando, e clica em **Liberar** ou **Recusar**. Quando libera, a tela da pessoa abre sozinha. Dá para **Bloquear** depois. Quem é admin fica só nas regras, não no código do site.
5. **Configurações do projeto > Seus apps > Web (`</>`)**: registre um app e copie o objeto `firebaseConfig`. Cole em `docs/firebase-config.js`, no lugar de `null`. Esses valores não são segredos; quem protege os dados são as regras acima.
6. Faça o commit. Com o Firebase configurado, **o painel pede login antes de abrir**: a tela de entrada aceita Google ou e-mail e senha, tem **Criar conta** e **Esqueci minha senha**. Sem `firebase-config.js` (valor `null`), o painel abre direto, sem login.

> O login esconde a tela, mas o arquivo `data/jobs.json` continua público no GitHub Pages. Não coloque nada secreto nele.

Os dados ficam em `users/{seu-uid}/candidaturas` e o perfil em `users/{seu-uid}/perfil/atual`. Se dois aparelhos mexerem no mesmo cartão, vale a alteração mais recente. Sem internet nada se perde: o que mudou é enviado quando voltar. Vagas salvas e ocultas ainda ficam só no navegador.

**Perfil:** no primeiro login abre a janela **Monte seu perfil** (níveis, áreas, onde, experiência, salário de suporte e tecnologias). Depois, mude em **Meu perfil**, no topo. Com o perfil salvo, a lista mostra só as vagas que combinam com ele, com a nota calculada para você; sem perfil, vale o do `config.toml`. O formulário começa com os critérios do `config.toml`, lidos de `docs/perfil-padrao.json`. Mudou o `[filter]` do config? Rode `python -m vagas perfil` e faça o commit desse arquivo (um teste avisa se esquecer).

> A sincronização foi escrita seguindo a documentação do Firebase 10, mas só pôde ser testada sem o servidor (o ambiente de desenvolvimento não tem acesso a ele). Se aparecer erro ao entrar, a mensagem no quadro diz o motivo; o mais comum é domínio não autorizado ou regras ainda não publicadas.

## Adicionar uma fonte nova

Copie `vagas/sources/lever.py`, mude `NAME`, escreva `fetch(cfg)` devolvendo uma lista de `Job` (sem filtrar), registre em `vagas/sources/__init__.py` e crie `[sources.nome]` no `config.toml`. Escreva um teste em `tests/test_sources.py` com uma resposta de exemplo.

## O que ficou de fora de propósito

- **LinkedIn e Indeed:** os termos de uso proíbem coleta automática e eles bloqueiam. Use os alertas de e-mail que eles mesmos oferecem, em paralelo com este projeto.
- **Páginas de carreira próprias** (Google, Meta, Mercado Livre, Itaú...): cada uma tem um sistema diferente e a maioria exige raspagem de HTML. Para essas, a cobertura vem da Gupy, do Adzuna e das notícias.
- **Remotive:** a API pede que as vagas não sejam repassadas a terceiros e há relatos de restrição a uso automatizado, então preferi não incluir.
- **Raspagem de HTML** de sites sem API: quebra a cada mudança de layout. Só vale a pena depois que o resto estiver estável.

## Próximos passos (para crescer como projeto de portfólio)

1. **Back-end próprio:** trocar o `jobs.json` por uma API em FastAPI com SQLite ou PostgreSQL. O painel passa a consultar `/vagas?uf=BA&remoto=true` em vez de baixar o arquivo.
2. **Contas e marcações no servidor**, para as marcações acompanharem você em qualquer aparelho.
3. **Notificação por Telegram**, além do e-mail.
4. **Nota por currículo:** comparar a descrição da vaga com as suas tecnologias e subir as que combinam.

# Radar de vagas júnior

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
tests/               127 testes, todos offline
.github/workflows/   agendamento
```

## Passo a passo

### 1. Rodar no seu computador

```bash
python -m pytest -q            # opcional: pip install pytest
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

A Gupy **não tem API pública documentada**: o coletor usa o endereço que o próprio portal chama hoje, e esse endereço já mudou antes. Se `python -m vagas check --source gupy` mostrar erro ou 0 vagas:

1. Abra <https://portal.gupy.io>, aperte **F12**, aba **Network**, filtre por **Fetch/XHR**.
2. Pesquise "desenvolvedor junior" no site e clique na requisição que devolve a lista de vagas (resposta em JSON).
3. Copie a URL sem a parte depois do `?` para `url` no `config.toml`, e o nome do parâmetro da busca (o que leva o texto que você digitou) para `term_param`. Faça o mesmo com `limit_param` e `offset_param` se os nomes forem outros.
4. Rode o `check` de novo. O leitor aceita vários nomes de campo (`name`/`title`, `jobUrl`/`url`, etc.).

### 6b. Buscar mais vagas de Salvador e remotas

O filtro de local roda sempre, mas só vê o que as fontes trazem. Para trazer mais vagas de lá:

- **Adzuna:** já busca "Salvador" com raio de `distance_km` e, em separado, o país todo com a palavra "remoto" (`wheres` no `config.toml`).
- **Gupy:** na busca do portal, filtre por estado/cidade e por "remoto" e, no DevTools, anote os nomes dos parâmetros que aparecem na requisição. Liste-os em `variants`, por exemplo `variants = [ { state = "Bahia" }, { workplaceType = "remote" } ]`. Sem isso, a Gupy devolve vagas do país inteiro e a maioria cai fora no filtro de local.

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

# Radar de vagas júnior

Contexto do projeto para o Claude Code. Este arquivo é lido automaticamente no começo de cada conversa.

## O que é

Sistema pessoal que coleta vagas de dev júnior, filtra, manda e-mail com as novas e mostra tudo num painel estático. Roda de graça no GitHub (Actions coleta 2x por dia, Pages hospeda o painel em `docs/`). Também serve de portfólio.

Quem usa: uma pessoa que trabalha com suporte, termina a faculdade no meio de 2027 e busca o primeiro emprego como dev júnior. Responda sempre em português do Brasil, em linguagem simples, e explique o que mudou depois de mexer.

## Critérios das vagas (não mudar sem pedir)

- Dev júnior em Salvador/região ou remoto no Brasil.
- Remoto do exterior só se o inglês exigido for até intermediário.
- Suporte técnico só com salário de pelo menos R$ 3.200.
- Notícias de processos seletivos de grandes empresas entram numa seção própria.
- Tudo isso fica em `config.toml`. Prefira ajustar lá a mexer no código.

## Estrutura

```
config.toml        termos de busca, filtro, e-mail
vagas/             coletor em Python 3.11+, só biblioteca padrão
  sources/         uma fonte por arquivo (gupy, adzuna, workday, smartrecruiters,
                   greenhouse, lever, ashby, noticias)
  filters.py       regras de júnior, idade da vaga, relevância, notícias
  storage.py       junta e atualiza docs/data/jobs.json
  emailer.py       monta e envia o e-mail
  runner.py        comandos run e check
docs/              painel em HTML, CSS e JS puro (sem build)
  app.js           lista de vagas, abas, filtros
  store.js         regras do quadro de candidaturas
  kanban.js        tela do quadro (arrastar, menu, folha no celular)
  sync.js          sincronização opcional com Firebase
tests/             pytest (Python) e node:test (store.js)
.github/workflows/ agendamento
```

## Comandos

```bash
python -m pytest -q                  # 128 testes, todos offline
node --test tests/store.test.js      # 18 testes do quadro (Node 20+)
python -m vagas check                # testa as fontes sem salvar nada
python -m vagas check --source gupy  # uma fonte só
python -m vagas run                  # coleta de verdade, salva e envia e-mail
```

Rode os testes depois de qualquer mudança em `vagas/` ou `docs/store.js`. Para mudanças visuais em `docs/`, abra `docs/index.html` por um servidor local (`python -m http.server -d docs 8000`) e confira no navegador, no tamanho de computador e de celular (390px).

## Regras importantes

- **Nunca leia, mostre nem comite o `.env`.** Ele tem a senha de app do Gmail e as chaves da Adzuna. Está no `.gitignore`. O `.env.example` é só um modelo em branco e deve continuar em branco.
- **`docs/data/jobs.json` é escrito pelo robô do GitHub Actions.** Não edite à mão. Em conflito de Git nesse arquivo, vale a versão do repositório remoto.
- Antes de enviar ao GitHub: `git pull --rebase origin main`, depois `git push`.
- Sem dependências externas no Python e sem etapa de build no painel. Mantenha assim, a não ser que eu peça.
- Uma fonte que falha só gera aviso. Nunca deixe uma fonte derrubar a coleta inteira.
- Fontes de vagas usam endpoints públicos sem documentação oficial (principalmente a Gupy, `portal.gupy.io/api/job-search/jobs`). Se uma fonte quebrar, rode `check --source nome` e leia o erro antes de mudar qualquer coisa.
- Textos do painel e do e-mail em português, frases curtas, sem jargão.

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

## Não testado ao vivo

A sincronização com Firebase foi escrita sem acesso ao servidor. Se der erro ao entrar, leia a mensagem no quadro e o passo 9 do README.

# Como continuar o projeto com o Claude no Visual Studio Code

Guia para você abrir o projeto no VS Code e seguir evoluindo o Radar de vagas júnior com o Claude Code, a versão do Claude que lê e edita os arquivos do projeto no seu computador.

## 1. O que você precisa

- **VS Code** na versão 1.94 ou mais nova.
- Uma conta da Anthropic: uma assinatura paga do Claude (Pro, Max, Team ou Enterprise) ou uma conta no Claude Console. Não precisa de chave de API.
- **Git** instalado (você já usa, pelo Git Bash).
- **Python 3.11+** para rodar o coletor e os testes. **Node 20+** só para o teste do quadro (`tests/store.test.js`).

## 2. Instalar a extensão

1. No VS Code, aperte `Ctrl+Shift+X` (abre as Extensões).
2. Procure por **Claude Code** e instale a que tem **Anthropic** como autor.
3. Se ela não aparecer depois de instalar, feche e abra o VS Code. Ou aperte `Ctrl+Shift+P` e rode **Developer: Reload Window**.

## 3. Abrir a pasta do projeto

1. **File > Open Folder** e escolha a pasta `vagas-junior` (a mesma onde você roda o Git Bash).
2. Abra a pasta do projeto, não só um arquivo. O Claude só enxerga o que está dentro da pasta aberta.
3. Quando o VS Code perguntar se você confia nos autores dessa pasta, clique em **Yes, I trust the authors**. É o seu projeto.

## 4. Abrir o Claude

- Abra qualquer arquivo (por exemplo `README.md`) e clique no **ícone de faísca** no canto superior direito do editor.
- Ou clique no mesmo ícone na barra lateral esquerda, que mostra a lista das suas conversas.
- Na primeira vez, ele pede o login. Escolha a conta do Claude e autorize no navegador.

O arquivo **`CLAUDE.md`**, na raiz do projeto, é lido sozinho no começo de cada conversa. Ele já explica para o Claude o que o projeto faz, os critérios das vagas, os comandos e as regras de segurança. Quando o projeto mudar muito, peça: *"atualize o CLAUDE.md com o que fizemos hoje"*.

## 5. Atalhos úteis (Windows)

| O que faz | Atalho |
|---|---|
| Alternar entre o editor e a caixa do Claude | `Ctrl+Esc` |
| Abrir uma conversa nova numa aba do editor | `Ctrl+Shift+Esc` |
| Mandar o trecho selecionado para o Claude (`@arquivo#linhas`) | `Alt+K` |
| Citar um arquivo na conversa | digite `@` e o nome do arquivo |

Quando você seleciona um texto no editor, o Claude já enxerga a seleção. O `Alt+K` só coloca a referência escrita na mensagem.

## 6. Como ele pede permissão

Embaixo da caixa de mensagem tem o **modo de permissão**. Clique nele para trocar:

- **Pedir antes de agir** (manual): ele mostra cada mudança e espera o seu OK. É o melhor enquanto você está aprendendo o fluxo.
- **Aceitar edições automaticamente:** ele edita os arquivos sem perguntar. Use quando confiar no pedido e quiser rapidez.
- **Modo plano:** ele só planeja, sem mexer em nada, e você aprova o plano antes. Para ativar, digite `/plan` ou `/plan` seguido da tarefa. Use em mudanças grandes, como "adicionar uma fonte nova de vagas".

As mudanças aparecem como **diferenças coloridas** (verde entra, vermelho sai). Leia antes de aceitar. Se não gostou, recuse e explique o que quer diferente.

## 7. Como pedir bem

Peça o resultado, diga onde fica e como você vai conferir. Exemplos para este projeto:

- *"A Gupy trouxe a vaga X como júnior, mas ela é pleno. Descubra por que o filtro deixou passar e corrija, com um teste."*
- *"Adicione a Greenhouse da empresa Y. Rode o `check` dessa fonte e me diga quantas vagas entraram."*
- *"No quadro de candidaturas, quero que o cartão mostre há quantos dias a candidatura está parada na etapa. Faça só o visual, no estilo dos outros cartões."*
- *"Explique o que o `filters.py` faz, como se eu estivesse vendo pela primeira vez."*

Dicas:

- **Uma tarefa por conversa.** Para um assunto novo, abra uma conversa nova. Ela fica mais rápida e mais certeira.
- Se o resultado ficou estranho, cole a mensagem de erro inteira ou descreva o que você esperava e o que apareceu.
- Peça sempre que ele **rode os testes** depois de mexer (`python -m pytest -q`).
- Para entender o código, pergunte. Isso também ajuda quando você mostrar o projeto numa entrevista.

## 8. Rotina com o Git

O robô do GitHub grava o `docs/data/jobs.json` duas vezes por dia, então o repositório quase sempre está à frente do seu computador. Sempre assim:

```bash
git status                       # o que mudou
git add -A
git commit -m "Descrição curta do que mudou"
git pull --rebase origin main    # traz o que o robô gravou
git push
```

Se der conflito em `docs/data/jobs.json`, mantenha a versão do GitHub (rebase inverte os nomes, por isso `--ours`):

```bash
git checkout --ours docs/data/jobs.json
git add docs/data/jobs.json
git rebase --continue
git push
```

Se o Git abrir o editor Vim pedindo a mensagem do commit, aperte `Esc`, digite `:wq` e `Enter`.

Você também pode pedir ao Claude: *"faça o commit com uma mensagem clara"*. Leia a mensagem e o que entra no commit antes de aceitar.

## 9. Segurança: o que nunca fazer

- **Não cole chaves nem senhas na conversa.** Isso vale para a senha de app do Gmail e as chaves da Adzuna. Elas ficam só no arquivo `.env`.
- **Não peça para o Claude abrir ou mostrar o `.env`.** O `CLAUDE.md` já diz para ele não ler esse arquivo.
- **Confira que o `.env` não vai para o GitHub.** Rode `git check-ignore .env`: se ele responder `.env`, está protegido. Se não responder nada, ou se o `.env` aparecer no `git status` para ser commitado, pare e não faça o commit.
- O `.env.example` é só um modelo e fica em branco.
- Se uma chave vazar (em print, conversa ou commit), **apague essa chave no site que a gerou e crie outra**. Apagar o commit não basta.
- Nunca aceite o modo de permissão mais solto sem entender o que ele libera.

## 10. Rodar e testar no seu computador

```bash
python -m pytest -q                  # testes do coletor (128)
node --test tests/store.test.js      # testes do quadro (18)
python -m vagas check                # testa as fontes sem salvar nada
python -m http.server -d docs 8000   # painel em http://localhost:8000
```

O Claude também consegue rodar esses comandos por você no terminal do VS Code (`Ctrl+'`), pedindo permissão.

## 11. Próximos passos combinados

Boas tarefas para pedir, uma de cada vez (use o modo plano nas maiores):

1. **Ligar o Firebase** para o quadro sincronizar entre aparelhos (README, passo 9). Peça: *"me guie no passo 9 do README e confira cada etapa comigo"*.
2. **Botão "coletar agora"**, limitado a 3 usos por dia.
3. **Rodar localmente** com um `.bat` que abre o painel e a coleta (depois, talvez um `.exe`).
4. **Vagas remotas do exterior** como fonte nova.
5. **Sincronizar vagas salvas e ocultas** junto com o quadro.
6. Investigar a empresa "ADMINISTRADOR DE REDES" que aparece em duas vagas da Gupy.

## 12. Se algo der errado

| Problema | O que fazer |
|---|---|
| O ícone de faísca não aparece | Abra um arquivo primeiro: o ícone do editor só aparece com um arquivo aberto. Ou use o ícone da barra lateral. |
| A extensão não aparece depois de instalar | Reinicie o VS Code ou rode **Developer: Reload Window**. |
| `claude` não funciona no terminal | A extensão não coloca o comando no terminal. Isso só vale se você quiser usar o Claude pelo terminal. Para o painel do VS Code, não precisa. |
| `Ctrl+Esc` não faz nada | Outro programa pode estar usando esse atalho. Troque em **File > Preferences > Keyboard Shortcuts**. |
| A conversa antiga sumiu | Clique no ícone de faísca da barra lateral esquerda: as conversas ficam na lista. |
| O Claude "esqueceu" o projeto | Peça: *"leia o CLAUDE.md e o README.md e me diga o que entendeu do projeto"*. |
| Um teste falhou depois da mudança | Cole a saída do teste e peça: *"explique o que falhou e corrija"*. |

Documentação oficial da extensão: https://code.claude.com/docs/en/vs-code

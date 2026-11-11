# Gitflow e publicação

`main` contém apenas releases aceites. `develop` integra o próximo ciclo.
Trabalho normal: `feature/*` ou `fix/*` a partir de `develop`, PR para `develop`.
Releases: `release/vYYYY.MM.N`, PR para `main`, tag depois da aceitação e
reconciliação de alterações exclusivas de release com `develop`. Hotfixes
partem de `main` e têm de chegar às duas branches. Nunca fazer force-push às bases.

Na inicialização deste repositório, `main` e `develop` apontam para o mesmo commit
que contém apenas um README. Toda a implementação fica em `feature/initial-macos`.
Publicar esse commit inicial nas duas branches é a única exceção de bootstrap.

## Publicar o pacote preparado

O pacote de entrega contém um clone Git local completo, incluindo as três branches.
Extrair, entrar em `dotfiles-macos` e executar, com GitHub CLI instalado:

```sh
gh auth login --hostname github.com
gh auth setup-git --hostname github.com
./setup-scripts/publish.sh
```

O script confirma a conta `abrioso`, origem, árvore limpa e histórico inicial;
cria `abrioso/dotfiles-macos` como **privado** se ainda não existir; publica as
bases iniciais e a feature; abre um PR para `develop`. Se existir trabalho remoto
incompatível, para sem o sobrescrever. Não faz merge, não cria tags nem releases.
Para o tornar público, a visibilidade deve ser alterada explicitamente pelo dono
depois da revisão. Se o utilizador já tiver criado o repositório, mantê-lo vazio.

Uma falha de rede pode deixar algumas etapas concluídas. É possível repetir o
script enquanto `main` e `develop` ainda apontarem para o commit inicial; não o
usar depois do primeiro merge em `develop`. O script reutiliza um PR já aberto.

## Proteções recomendadas

Configurar regras do servidor para `main` e `develop`: exigir PR, proibir
force-push/eliminação e exigir os checks `Validate (ubuntu-latest)`,
`Validate (macos-15)` e `Validate (macos-15-intel)` depois da primeira execução.
A disponibilidade de regras em repositórios privados depende do plano GitHub.
Não se afirma que existam proteções do servidor enquanto não forem verificadas.

Instalar os hooks apenas neste clone:

```sh
git config --local core.hooksPath git-hooks
```

`pre-push` bloqueia os nomes completos `refs/heads/main` e `refs/heads/develop`;
não bloqueia `feature/main` ou uma tag `main`. `pre-commit` valida whitespace e
impede a inclusão acidental dos JSON locais e de padrões de credenciais. Os hooks
podem ser contornados e não substituem regras do servidor ou uma revisão de segredos.

As Actions usam permissões de leitura, checkout fixado a commit e atualizações
Dependabot para `develop`. Testes usam diretórios temporários, sem aplicar os
dotfiles ao runner. A matriz não substitui aceitação numa conta real do Mac.

# Configuração e operação

## Primeira utilização

1. Confirmar `uname -m` e `sw_vers -productVersion`; usar Terminal sem Rosetta.
2. Instalar as Apple Command Line Tools com `xcode-select --install`, se necessário.
3. Obter o repositório e permanecer no checkout pretendido. Antes da primeira
   release, usar a branch de implementação/revisão indicada no README.
4. Rever e executar `./setup-scripts/bootstrap.sh`. Se Homebrew estiver ausente,
   voltar a executar com `--install-homebrew`. O instalador oficial é descarregado
   para um ficheiro, verificado por SHA-256 e só depois executado. Pode pedir sudo.
5. Executar o comando `export PATH=...` apresentado, se necessário. O script não
   consegue alterar o ambiente do terminal que o chamou.
6. Executar `./setup-scripts/configure.sh`. Setas movem, espaço alterna, S guarda,
   Q/Esc cancela sem escrever ficheiros. A janela deve ter pelo menos 35×8.
7. Editar `dotfiles-configurations/config.json` para preencher `user.name` e
   `user.email`. Campos vazios preservam a identidade Git existente.
8. Rever `./setup-scripts/setup.sh --plan` e aplicar com `./setup-scripts/setup.sh`.
9. Abrir um terminal novo e executar `./setup-scripts/verify.sh --check-packages`.

Para criar a configuração sem TUI:

```sh
./setup-scripts/configure.sh --defaults
./setup-scripts/setup.sh --plan --json
./setup-scripts/setup.sh --yes
```

`--defaults` inicializa ficheiros em falta e conserva as escolhas guardadas;
não significa repor valores de fábrica. `--yes` aceita a aplicação dos dotfiles,
mas não suprime prompts do Homebrew, macOS, instaladores ou licenças de aplicações.
Não executar setup com sudo. Se Python tiver sido instalado via Homebrew, uma
janela nova pode precisar do PATH indicado pelo bootstrap antes da aplicação do Zsh.

## Modelo dos ficheiros

`config.json.example` e `packages.json.example` são versionados. As cópias sem
`.example` são privadas e ignoradas pelo Git. Arrays vazios significam seleção
vazia; valores desconhecidos, chaves duplicadas e dependências inválidas falham.
Um catálogo local pode retirar pacotes de um grupo sem alterar o template partilhado.

O módulo `pwsh` requer o grupo homónimo. Docker Desktop e Colima são mutuamente
exclusivos na seleção; mudar a seleção não migra os dados do runtime anterior.
Rever manualmente instalações existentes e contextos Docker antes de mudar.

As configurações são específicas de cada máquina. Não colocar tokens em templates,
no tema ou nos perfis versionados. Credenciais Homebrew/GitHub/Microsoft/Tailscale,
chaves SSH, autenticação OneDrive e perfis rclone são geridos fora do repositório.
O grupo `data` instala apenas rclone; não copia, sincroniza ou elimina dados.

## Perfis e Git

Ficheiros aplicados:

| Destino | Conteúdo |
| --- | --- |
| `~/.config/dotfiles-macos/zprofile` | Ambiente Homebrew nativo |
| `~/.config/dotfiles-macos/zshrc` | Aliases, completion e prompt |
| `~/.config/dotfiles-macos/theme.omp.json` | Cópia independente do tema |
| `~/.zprofile`, `~/.zshrc` | Bloco de carregamento; conteúdo pessoal preservado |
| `~/.config/dotfiles-macos/gitconfig` | Definições Git selecionadas |
| `~/.gitconfig` | Bloco `[include]` gerido; outras definições preservadas |
| `~/.config/dotfiles-macos/profile.ps1` | Perfil PowerShell opcional |
| `~/.config/powershell/profile.ps1` | Bloco PowerShell comum aos hosts |

Alterações ao conteúdo dentro dos marcadores são substituídas na aplicação
seguinte, depois de backup. Conteúdo fora dos marcadores é preservado. Symlinks
nos destinos ou nos seus diretórios são recusados; marcadores incompletos ou
duplicados também. Configurações `ZDOTDIR`, `XDG_CONFIG_HOME` personalizadas e
layouts Git XDG-only podem exigir integração manual, conforme o módulo.

O include Git é inserido no fim na primeira aplicação. Pode sobrepor valores
anteriores das mesmas chaves, mas não elimina o texto anterior. Ficheiros incluídos
ou definições posteriores podem prevalecer; `verify` identifica essa divergência.
Não se impõe `core.ignorecase` nem `core.filemode`. Para segredos/ajustes privados,
carregar um ficheiro local explicitamente fora do bloco gerido.

Selecionar manualmente a fonte **CaskaydiaCove Nerd Font** nas preferências do
Terminal/iTerm2 ou do VS Code, se pretendido. O script instala a fonte quando
selecionada, mas não substitui perfis gráficos ou preferências dos terminais.
Perfis adicionais VS Code/PowerShell existentes podem alterar o prompt depois
do perfil comum; confirmar ambos os terminais na aceitação.

## PowerShell e Azure

O catálogo usa `brew "powershell"`, atualmente uma compilação da comunidade
Homebrew. Para suporte Microsoft, preferir o PKG assinado/notarizado indicado na
[documentação oficial](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-macos).
Nesse caso, instalar o PKG manualmente e remover `powershell` da lista `formulae`
do grupo `pwsh` no JSON local, mantendo `oh-my-posh` e o módulo `pwsh`.
Não sobrepor instalações anteriores de origens diferentes sem as rever.

Azure CLI usa o cask `azure-cli`. Azure Developer CLI (`azd`) não integra esta
primeira versão. A migração de uma instalação antiga de Azure CLI por fórmula
fica para intervenção explícita, segundo a documentação Microsoft.

## Docker

Docker Desktop instala a aplicação; o primeiro arranque, licença, permissões,
recursos e início automático ficam para configuração manual. Nenhum container
do `akb-docker-stack` é lançado por este repositório.

Colima instala `colima`, `docker` e `docker-compose`, mas não cria/inicia uma VM.
Para a primeira utilização, rever os recursos pretendidos e executar `colima start`.
Segundo as instruções Homebrew, o plugin Compose pode precisar de
`cliPluginsExtraDirs` no ficheiro `~/.docker/config.json`:

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

Em Intel, o caminho é `/usr/local/lib/docker/cli-plugins`. **Integrar a chave no
JSON existente; não substituir o ficheiro**, que pode conter autenticação e
outros contextos. Confirmar `docker context ls`, `docker info` e
`docker compose version` antes de utilizar stacks. O diagnóstico desta versão
confirma presença de pacotes, não saúde do daemon ou equivalência entre runtimes.

## Atualizações

```sh
./setup-scripts/update.sh
./setup-scripts/setup.sh --plan
./setup-scripts/setup.sh
```

`update` exige árvore limpa, branch anexada e upstream em `origin`. Faz fetch e
fast-forward dessa branch; divergências falham. Não troca de branch nem repõe JSON
local. Rever diferenças dos templates manualmente e incorporar apenas o necessário.
Atualizações de pacotes são uma operação separada, por exemplo `brew outdated`
seguido de `brew upgrade <pacote>` após revisão. Não se executa `brew bundle cleanup`.

## Diagnóstico

`verify --json` omite valores de identidade e conteúdo de ficheiros. Os nomes
de pacotes e chaves são apresentados. Não cria relatórios automaticamente.

| Código | Significado |
| --- | --- |
| 0 | Todos os controlos pedidos conclusivos e conformes |
| 1 | Pelo menos uma divergência confirmada |
| 2 | Configuração inválida ou erro de pré-validação |
| 3 | Sem divergência confirmada, mas com verificações inconclusivas |
| 130 | Operação interrompida |

Sem `--check-packages`, os pacotes selecionados ficam inconclusivos. Com essa
opção, consultam-se apenas listas locais do Homebrew, sem auto-update.
Não se verificam versões exatas, integridade de bundles `.app`, licenças,
fontes selecionadas, autenticação, conectividade ou estado de serviços.

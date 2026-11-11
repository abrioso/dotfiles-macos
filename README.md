# dotfiles-macos

Configuração modular de um Mac, baseada em
[dotfiles-windows](https://github.com/abrioso/dotfiles-windows): escolhas por máquina,
TUI com toggles, plano antes da aplicação, cópias de segurança e diagnóstico.
Usa Homebrew, Zsh e, opcionalmente, PowerShell com o mesmo tema Oh My Posh.

**Estado:** implementação inicial em `feature/initial-macos`, destinada a PR para
`develop`. `main` contém apenas o ponto inicial do repositório. Ainda não existe
uma release aceite num Mac físico. A implementação está publicada no
[PR #1 para develop](https://github.com/abrioso/dotfiles-macos/pull/1).
Consultar os checks desse PR antes de integrar; ver [Gitflow](docs/GITFLOW.md).

## Começar

Alvo inicial: **macOS 15+**, Apple Silicon ou Intel, terminal nativo sem Rosetta.
São necessários Git/Apple Command Line Tools, Homebrew e Python 3.9+. O bootstrap
orienta a preparação e só instala Homebrew com uma opção explícita. Intel pode
ter limitações adicionais de disponibilidade/suporte dos pacotes.

Se recebeu o arquivo de entrega, extraia-o e entre na pasta `dotfiles-macos`.
Depois da publicação, para avaliar a implementação inicial:

```sh
xcode-select --install  # Apenas se as Command Line Tools estiverem em falta.
git clone --branch feature/initial-macos https://github.com/abrioso/dotfiles-macos.git
cd dotfiles-macos
./setup-scripts/bootstrap.sh
# Se necessário, rever e executar:
./setup-scripts/bootstrap.sh --install-homebrew
# Executar o export PATH apresentado pelo bootstrap, se necessário.
./setup-scripts/configure.sh
./setup-scripts/setup.sh --plan
./setup-scripts/setup.sh
./setup-scripts/verify.sh --check-packages
```

Na TUI, usar **setas**, **espaço** para ativar/desativar, **S** para guardar e
**Q/Esc** para cancelar. A gravação não instala software. O setup pede confirmação;
`--yes` dispensa apenas essa confirmação. Não executar com sudo.

Os valores `user.name` e `user.email` ficam vazios no template. Preenchê-los no
ficheiro local `dotfiles-configurations/config.json` antes de aplicar, se pretendido.

## Operações

| Comando | Resultado |
| --- | --- |
| `configure.sh` | Edita a seleção com toggles e guarda apenas no final |
| `configure.sh --defaults` | Inicializa ficheiros em falta; preserva escolhas existentes |
| `setup.sh --plan [--json]` | Valida e mostra intenção, sem alterações nem consultas externas |
| `setup.sh [--yes]` | Instala pacotes em falta e aplica este checkout |
| `verify.sh [--json] [--check-packages]` | Deteta divergências; não aplica correções |
| `update.sh` | Atualiza apenas a branch atual, por fast-forward |

Todos os comandos ficam em `setup-scripts/`. Um plano não garante que a instalação
venha a ser possível: permissões, ficheiros existentes e disponibilidade dos pacotes
são verificados na aplicação. Não há atualizações de pacotes ou remoções implícitas.

## Seleção inicial

Ativos por defeito: `base`, `terminal`, `dev`; módulos `shell` e `git`.
O catálogo inclui grupos opcionais para PowerShell, browsers, Microsoft 365,
Docker Desktop ou Colima, Azure CLI, multimédia, produtividade avançada,
Tailscale, Yubico, Google Drive, Windows App e rclone.

Desmarcar uma opção impede aplicações futuras, mas não remove software ou
configurações já aplicadas. Docker Desktop e Colima não podem estar selecionados
ao mesmo tempo. Nenhum runtime, serviço ou container é iniciado automaticamente.

As preferências do Finder são opcionais. A seleção da fonte no terminal, o primeiro
arranque das aplicações, as permissões do macOS e as autenticações são manuais.
Não se alteram políticas de segurança ou configuração MDM.

## Documentação e validação

- [Arquitetura e equivalências com Windows](docs/ARCHITECTURE.md)
- [Configuração, instalação e operação](docs/CONFIGURATION.md)
- [Reposição e remoção](docs/ROLLBACK.md)
- [Gitflow e publicação inicial](docs/GITFLOW.md)
- [Aceitação num Mac](docs/ACCEPTANCE.md)
- [Resultados e limites da validação](docs/VALIDATION.md)

```sh
./tests/validate.sh
```

Os testes não provisionam o host. A CI está preparada para Linux, macOS Apple
Silicon e macOS Intel. Hooks locais e regras de branch devem ser ativados segundo
o guia Gitflow. Usam-se Conventional Commits e versões `vYYYY.MM.N`.

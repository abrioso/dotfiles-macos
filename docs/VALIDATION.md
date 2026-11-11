# Evidência de validação inicial

Data: 11/11/2026. Ambiente de execução local: Linux, Python 3.12.14,
Zsh do ambiente e ShellCheck 0.11.0. Nenhum teste aplicou configurações ao Mac
do utilizador, iniciou runtimes ou instalou os pacotes do catálogo.

## Concluído

- **30 testes automatizados passaram**, incluindo TUI numa pseudo-terminal,
  cancelamento sem escrita, gravação de toggles, validação estrita, opt-outs,
  planos/diagnósticos sem escrita ou exposição da identidade, cópias independentes,
  idempotência, backups, falhas de publicação, symlinks/hardlinks, integração Git,
  falha de instalação antes da aplicação e atualização Git fast-forward/divergente.
- Análise sintática Python com gramática 3.9; JSON dos templates e tema válidos.
- Sintaxe Bash e POSIX shell, sintaxe Zsh, ShellCheck sem findings e whitespace Git.
- **34 tokens únicos do catálogo confirmados** na API oficial Homebrew, sem estado
  disabled/deprecated nas respostas observadas. Evidência em
  `package-catalog-validation.json`. É uma consulta de disponibilidade, não um
  teste de instalação ou de compatibilidade com cada modelo/versão macOS.
- Instalador Homebrew obtido do commit
  `7986efac25016e41eed7e471666140c06f9d97cf`; SHA-256 confirmado como
  `5f333bbe53bc490e51e7ccb1df8779b3dd6ee73a1a7379efda216edb08ccb148`.

## Pendente

- Publicação em GitHub e execução da matriz CI; o conector usado nesta preparação
  não oferece criação de repositórios e não havia sessão web/CLI autenticada.
- Validação real em macOS Apple Silicon/Intel e PowerShell; a CI inclui parsing
  PowerShell, mas o executável não estava disponível no ambiente local.
- Aceitação no Mac, incluindo fonte, perfis gráficos, aplicações, permissões,
  eventual runtime Docker e reposição conforme `ACCEPTANCE.md`.
- Configuração/verificação das regras de proteção de branches no GitHub.

Não foi criada uma tag de release. Os testes não demonstram compatibilidade com
todo o parque macOS, nem substituem revisão e aceitação do commit que for publicado.

## Fontes técnicas consultadas

- [Homebrew: instalação e plataformas](https://docs.brew.sh/Installation)
- [Homebrew: Bundle e ausência de lockfile](https://docs.brew.sh/Brew-Bundle-and-Brewfile)
- [Homebrew: API de fórmulas/casks](https://formulae.brew.sh/docs/api/)
- [Homebrew: plugin Docker Compose](https://formulae.brew.sh/formula/docker-compose)
- [Microsoft: PowerShell no macOS](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-macos)
- [Microsoft: PowerShell via Homebrew](https://learn.microsoft.com/en-us/powershell/scripting/install/alternate-install-methods)
- [Microsoft: Azure CLI no macOS](https://learn.microsoft.com/cli/azure/install-azure-cli-macos)
- [GitHub: imagens de runners](https://github.com/actions/runner-images)

Estas fontes foram usadas para resolver alterações atuais de empacotamento e
confirmar os rótulos da matriz CI. Voltar a verificar quando forem atualizados
os pré-requisitos, os pacotes ou as versões de macOS suportadas.

# Arquitetura e relação com dotfiles-windows

Referência analisada: `abrioso/dotfiles-windows`, branch `develop`, commit
`e53a286` (consulta de 11/11/2026). A implementação macOS é independente;
não executa os scripts Windows nem partilha configurações locais entre sistemas.
O tema `themes/theme.omp.json` foi reutilizado do ficheiro
`poshthemes/jandedobbeleer.omp.json` dessa revisão.

## Correspondência funcional

| Windows | macOS |
| --- | --- |
| Orquestrador PowerShell | Python 3.9+ com biblioteca padrão; entradas Bash 3.2 |
| Winget por grupos | Homebrew Bundle; catálogo JSON por grupos |
| TUI com toggles | Curses: setas, espaço, guardar ou cancelar |
| PowerShell como shell principal | Zsh; PowerShell opcional |
| Windows Terminal + Nerd Font + Oh My Posh | Terminal/iTerm2 + Nerd Font + o mesmo tema Oh My Posh |
| JSON privado e templates versionados | Mesmo princípio, dois ficheiros JSON locais |
| Aplicação, atualização e diagnóstico separados | `setup.sh`, `update.sh`, `verify.sh` |
| Perfis copiados para armazenamento local | Cópias em `~/.config/dotfiles-macos`; blocos nos perfis |
| Gitflow e CI | `main`, `develop`, feature branches, PRs e testes Linux/macOS |
| WSL, Hyper-V, Sandbox, RSAT | Sem tradução automática; não aplicáveis nativamente |
| Docker Desktop | Docker Desktop ou Colima, seleção exclusiva |
| Power BI Desktop | Fora do catálogo; usar serviço web ou Windows remoto conforme necessidade |

Python permite validar JSON, publicar ficheiros atomicamente e testar falhas sem
dependências externas. Bash é apenas a entrada e o bootstrap; Zsh continua a ser
o shell do utilizador. A opção evita depender de PowerShell para preparar um Mac.

## Componentes

- `setup-scripts/lib/config.py`: leitura estrita, dependências e Brewfile.
- `setup-scripts/lib/tui.py`: seleção em memória; gravação apenas ao premir S.
- `setup-scripts/lib/deployment.py`: cópias independentes, marcadores e backups.
- `setup-scripts/lib/modules.py`: preparação dos ficheiros e preferências.
- `setup-scripts/lib/system.py`: comandos externos e deteção de Homebrew.
- `setup-scripts/dotfiles.py`: orquestração e códigos de saída.
- `dotfiles-configurations`: templates e cópias locais ignoradas pelo Git.
- `shell`, `powershell-profiles`, `themes`: conteúdo a aplicar, sem symlinks.

## Decisões e limites

O alvo inicial é macOS 15 ou posterior, com prioridade a Apple Silicon. Intel é
detetado e tem CI próprio, mas a disponibilidade de pacotes depende do suporte
atual do Homebrew e dos fabricantes. A execução através de Rosetta é recusada.
Não se instala Rosetta automaticamente. O modelo e a versão do Mac de André
ainda não foram confirmados; esta compatibilidade deve ser validada na aceitação.

O catálogo inicial seleciona `base`, `terminal`, `dev` e os módulos `shell`, `git`.
Os grupos de aplicações, Docker, identidade, sincronização e dados são opcionais.
Preferências Finder são opcionais e restritas a três valores booleanos; não há
alterações automáticas a FileVault, Gatekeeper, SIP, firewall, SSH, MDM ou login.

`setup` instala pacotes em falta com `brew bundle --no-upgrade`, depois aplica
ficheiros e preferências. Falhas de instalação impedem a fase de ficheiros.
A aplicação completa não é uma transação: pacotes já instalados e alterações
anteriores à falha permanecem, com informação de backup para os ficheiros.

Desmarcar um grupo impede a sua aplicação futura. Não desinstala software, não
remove um bloco já instalado, nem repõe preferências. A remoção é uma operação
explícita descrita em `ROLLBACK.md`. Isto preserva o estado e as configurações
de aplicações que o utilizador pode continuar a utilizar.

O Brewfile é gerado num diretório temporário a partir de tokens validados e
eliminado no fim. Não são aceites Ruby livre, taps arbitrários ou código nos
catálogos. As versões das aplicações não estão fixadas; a opção `--no-upgrade`
evita atualizações implícitas, mas não torna as instalações reproduzíveis bit a bit.

`plan` mostra intenção validada e não inspeciona o estado real. `verify` lê esse
estado, sem tentar corrigi-lo. Atualizar o checkout não altera cópias já aplicadas.
Aplicar o checkout não o atualiza. O bootstrap de pré-requisitos é igualmente separado.

# Reposição e remoção

Cada aplicação com alterações cria um diretório privado em
`~/.local/state/dotfiles-macos/backups/<timestamp>-<sufixo>`. O caminho é mostrado
também quando uma fase falha. Repetições sem alterações não criam novo backup.
Os backups podem conter dados pessoais existentes nos perfis: não os publicar.

`manifest.json` identifica destinos, existência anterior, cópia de segurança e
permissões anteriores. Antes de repor, fechar os terminais afetados e guardar
quaisquer alterações realizadas depois da aplicação. Para cada entrada com
`existed: true`, comparar o ficheiro `.bak` com o destino e copiar a versão
pretendida. Repor as permissões originais indicadas no campo `mode` (valor decimal).
Para entradas com `existed: false`, remover apenas o ficheiro criado se continuar
sem alterações pessoais e já não for necessário. Não eliminar diretórios inteiros.

Para remover só a integração, retirar os blocos delimitados por
`# >>> dotfiles-macos >>>` e `# <<< dotfiles-macos <<<` de `.zshrc`, `.zprofile`,
`.gitconfig` e/ou `~/.config/powershell/profile.ps1`. Preservar o restante conteúdo.
Retirar o include Git antes de remover o ficheiro `gitconfig` gerido. As cópias
em `~/.config/dotfiles-macos` podem então ser revistas e removidas individualmente.

`macos-preferences.json`, quando existe, guarda o valor anterior de cada preferência
alterada. Para uma chave que não existia, usar `defaults delete <domain> <key>`;
para uma chave que existia, usar `defaults write <domain> <key> -bool true|false`
com o valor anterior. Só executar para as chaves registadas e depois de comparar
com o estado atual. Pode ser necessário terminar sessão para refletir o resultado.

Não existe rollback automático global: poderia eliminar alterações posteriores.
A reposição dos ficheiros não remove pacotes Homebrew nem dados de aplicações.
Rever individualmente qualquer desinstalação. Não usar `brew bundle cleanup`
para este efeito; o catálogo cobre apenas parte do software da máquina.

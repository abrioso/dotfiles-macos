# Aceitação num Mac antes da primeira release

Registar localmente: commit completo em teste, modelo/arquitetura, versão macOS,
versão Python/Homebrew, grupos/módulos selecionados e resultado de cada etapa.
Não publicar nomes de conta, emails, tokens, logs completos ou configurações privadas.

- [ ] Confirmar macOS 15+ e terminal nativo; verificar comportamento Intel se aplicável.
- [ ] Rever bootstrap, instalar pré-requisitos e confirmar PATH numa nova janela.
- [ ] Testar TUI: setas/espaço, cancelamento sem ficheiros novos e gravação explícita.
- [ ] Introduzir identidade Git apenas no JSON local; confirmar que `git status` a ignora.
- [ ] Guardar cópia dos perfis e configurações antes da primeira aplicação.
- [ ] Executar plano texto/JSON e confirmar ausência de alterações/elevação/downloads.
- [ ] Aplicar a seleção mínima numa conta de teste; confirmar aplicações e prompt Zsh.
- [ ] Repetir setup; ficheiros idênticos não devem mudar nem gerar novos backups.
- [ ] Selecionar a Nerd Font no terminal e verificar caracteres e path/git no prompt.
- [ ] Testar PowerShell normal e integrado no VS Code, se selecionados.
- [ ] Confirmar `git config --global --includes --get user.name` e aliases, sem publicar os valores.
- [ ] Simular conflito de marcador/symlink numa conta de teste; setup deve parar antes de instalar.
- [ ] Executar diagnóstico com e sem `--check-packages`; interpretar os códigos documentados.
- [ ] Confirmar que Docker/Tailscale não foram arrancados/autenticados automaticamente.
- [ ] Se usar Colima, configurar Compose e recursos, iniciar manualmente e testar uma stack descartável.
- [ ] Se usar preferências Finder, confirmar valores e testar reposição de uma chave.
- [ ] Testar reposição de um perfil através do manifesto; preservar alterações posteriores.
- [ ] Confirmar que atualizar o checkout não altera perfis aplicados e não repõe JSON local.
- [ ] Aguardar CI das três plataformas e revisão do PR antes de integrar em `develop`.

Aceitação física: **pendente** na criação inicial. Não foi executada instalação
de software nem alteração de preferências no Mac do utilizador.

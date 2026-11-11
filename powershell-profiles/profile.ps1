# Cross-platform prompt only. No Windows-only modules or environment changes.
if (Get-Command oh-my-posh -ErrorAction SilentlyContinue) {
    $themePath = Join-Path $HOME '.config/dotfiles-macos/theme.omp.json'
    oh-my-posh init pwsh --config $themePath | Invoke-Expression
}
function Get-GitStatus { git status @args }
Set-Alias -Name gs -Value Get-GitStatus
# Keep personal overrides in the original profile, outside the managed markers.

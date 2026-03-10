$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $repoRoot "scripts\install_project_module.py"

python $installer cursor-openspec-kit --target $repoRoot --force

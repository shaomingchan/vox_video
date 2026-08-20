param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$VoxArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WhiteboardPython = Join-Path $Root "..\whiteboard\.venv\Scripts\python.exe"
$Python = if ($env:VOXFLOW_PYTHON) {
    $env:VOXFLOW_PYTHON
} elseif (Test-Path $WhiteboardPython) {
    $WhiteboardPython
} else {
    "python"
}
$LocalConfig = Join-Path $Root "config.local.toml"
$DefaultConfig = Join-Path $Root "config.toml"
$ExampleConfig = Join-Path $Root "config.example.toml"
$Config = if ($env:VOXFLOW_CONFIG) {
    $env:VOXFLOW_CONFIG
} elseif (Test-Path $LocalConfig) {
    $LocalConfig
} elseif (Test-Path $DefaultConfig) {
    $DefaultConfig
} else {
    $ExampleConfig
}
$env:PYTHONPATH = Join-Path $Root "src"

& $Python -m voxflow.cli --config $Config @VoxArgs
exit $LASTEXITCODE

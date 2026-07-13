$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

$LogDir = Join-Path $Root 'material_ai_workbench\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLog = Join-Path $LogDir 'streamlit_app.out.log'
$ErrLog = Join-Path $LogDir 'streamlit_app.err.log'

$env:PYTHONPATH = "$Root;$($env:PYTHONPATH)"
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$StreamlitExe = 'D:\Anaconda3\envs\pylabfea\Scripts\streamlit.exe'
if (-not (Test-Path -LiteralPath $StreamlitExe)) {
  throw "Streamlit executable not found: $StreamlitExe"
}

& $StreamlitExe run material_ai_workbench\streamlit_app.py `
  --server.port 8501 `
  --server.address 127.0.0.1 `
  --server.headless true `
  1>> $OutLog `
  2>> $ErrLog

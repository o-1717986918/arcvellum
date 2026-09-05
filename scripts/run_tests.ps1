$ErrorActionPreference = "Stop"
$Repository = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Repository ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$env:PYTHONPATH = Join-Path $Repository "src"

& $Python (Join-Path $PSScriptRoot "verify_checkout_import.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m unittest discover -s (Join-Path $Repository "tests") @args
exit $LASTEXITCODE

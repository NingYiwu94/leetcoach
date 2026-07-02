param(
    [switch]$SkipEnvPrompt
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @("python")
    }

    throw "Python was not found. Please install Python 3.10+ from https://www.python.org/downloads/ and rerun setup."
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

Write-Host "LeetCoach Windows Setup" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

Write-Step "Checking Python"
$pythonCommand = Get-PythonCommand
Write-Host "Python command: $($pythonCommand -join ' ')"

Write-Step "Creating local virtual environment"
$VenvDir = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $VenvDir)) {
    if ($pythonCommand.Count -eq 2) {
        & $pythonCommand[0] $pythonCommand[1] -m venv ".venv"
    } else {
        & $pythonCommand[0] -m venv ".venv"
    }
} else {
    Write-Host ".venv already exists, skipping creation."
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPythonw = Join-Path $VenvDir "Scripts\pythonw.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment Python was not found: $VenvPython"
}

& $VenvPython -c "import sys, tkinter; print('Python OK:', sys.version.split()[0])"

Write-Step "Preparing .env"
$EnvPath = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvPath)) {
    @"
# LeetCoach local environment
# Fill these values if you want to use cloud LLM features.

LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
EMBEDDING_API_KEY=
"@ | Set-Content -Path $EnvPath -Encoding UTF8
    Write-Host "Created .env template."
} else {
    Write-Host ".env already exists, keeping it unchanged."
}

if (-not $SkipEnvPrompt) {
    $answer = Read-Host "Open .env in Notepad now? You can fill API settings later too. (Y/N)"
    if ($answer -match "^[Yy]") {
        notepad $EnvPath
    }
}

Write-Step "Preparing LeetCode sync config"
$LeetCodeConfig = Join-Path $ProjectRoot "config\leetcode_config.json"
$LeetCodeExample = Join-Path $ProjectRoot "config\leetcode_config.example.json"
if ((-not (Test-Path $LeetCodeConfig)) -and (Test-Path $LeetCodeExample)) {
    Copy-Item $LeetCodeExample $LeetCodeConfig
    Write-Host "Created config\leetcode_config.json from example."

    if (-not $SkipEnvPrompt) {
        $username = Read-Host "LeetCode username for sync (press Enter to skip)"
        if ($username.Trim()) {
            $json = Get-Content -Raw -Path $LeetCodeConfig | ConvertFrom-Json
            $json.leetcode_username = $username.Trim()
            $json | ConvertTo-Json -Depth 8 | Set-Content -Path $LeetCodeConfig -Encoding UTF8
            Write-Host "Saved LeetCode username."
        }
    }
} else {
    Write-Host "config\leetcode_config.json already exists or example is missing, skipping."
}

Write-Step "Creating Desktop shortcut"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "LeetCoach.lnk"
$IconPath = Join-Path $ProjectRoot "resources\assets\leetcoach.ico"
$PythonForShortcut = if (Test-Path $VenvPythonw) { $VenvPythonw } else { $VenvPython }

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonForShortcut
$Shortcut.Arguments = "`"$ProjectRoot\coach_app.py`""
$Shortcut.WorkingDirectory = "$ProjectRoot"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath"
}
$Shortcut.Description = "LeetCoach"
$Shortcut.Save()

Write-Host "Desktop shortcut created: $ShortcutPath" -ForegroundColor Green

Write-Step "Done"
Write-Host "You can now start LeetCoach from the Desktop shortcut."
Write-Host "If AI features are not available, check your local .env file."

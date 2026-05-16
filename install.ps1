#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# ── Helpers ─────────────────────────────────────────────────────────────
function Write-Info($msg)  { Write-Host "  " -NoNewline; Write-Host "ℹ" -ForegroundColor Cyan -NoNewline; Write-Host " $msg" }
function Write-Ok($msg)    { Write-Host "  " -NoNewline; Write-Host "✔" -ForegroundColor Green -NoNewline; Write-Host " $msg" }
function Write-Warn($msg)  { Write-Host "  " -NoNewline; Write-Host "⚠" -ForegroundColor Yellow -NoNewline; Write-Host " $msg" }
function Write-Err($msg)   { Write-Host "  " -NoNewline; Write-Host "✖" -ForegroundColor Red -NoNewline; Write-Host " $msg" }

# ── Resolve script directory ────────────────────────────────────────────
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
Set-Location $ScriptDir

# ── Check uv ────────────────────────────────────────────────────────────
$uvCmd = $null

function Resolve-Uv {
    # 1. In PATH
    $inPath = Get-Command uv -ErrorAction SilentlyContinue
    if ($inPath) {
        $script:uvCmd = $inPath.Source
        return $true
    }

    # 2. Common Windows locations
    $candidates = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:USERPROFILE\.cargo\bin\uv.exe",
        "$env:LOCALAPPDATA\uv\uv.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $script:uvCmd = $c
            return $true
        }
    }

    return $false
}

if (Resolve-Uv) {
    Write-Ok "Found uv: $uvCmd"
}
else {
    Write-Warn "uv not found in PATH."
    Write-Host ""
    Write-Host "  " -NoNewline; Write-Host "1)" -ForegroundColor White -NoNewline; Write-Host " Install uv automatically (recommended)"
    Write-Host "  " -NoNewline; Write-Host "2)" -ForegroundColor White -NoNewline; Write-Host " Provide the path to uv manually"
    Write-Host "  " -NoNewline; Write-Host "3)" -ForegroundColor White -NoNewline; Write-Host " Abort"
    Write-Host ""

    while ($true) {
        $choice = Read-Host "Choose [1/2/3]"
        switch ($choice) {
            "1" {
                Write-Info "Installing uv..."
                $tmpFile = Join-Path $env:TEMP "uv-install.ps1"
                try {
                    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $tmpFile -ErrorAction Stop
                    & powershell -ExecutionPolicy Bypass -File $tmpFile
                }
                finally {
                    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
                }
                # Refresh PATH from registry so Resolve-Uv can find the new install
                $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
                $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
                $env:PATH = "$machinePath;$userPath"
                # Re-check
                if (Resolve-Uv) {
                    Write-Ok "uv installed: $uvCmd"
                }
                else {
                    Write-Err "uv still not found after installation. Please restart your terminal and try again."
                    exit 1
                }
                break
            }
            "2" {
                while ($true) {
                    $uvPath = Read-Host "Enter path to uv.exe"
                    $uvPath = $uvPath -replace '^~', $env:USERPROFILE
                    if (Test-Path $uvPath) {
                        $script:uvCmd = (Resolve-Path $uvPath).Path
                        Write-Ok "Using uv at: $uvCmd"
                        break
                    }
                    else {
                        Write-Err "File not found: $uvPath"
                    }
                }
                break
            }
            "3" {
                Write-Err "Aborted."
                exit 1
            }
            default {
                Write-Warn "Invalid choice. Enter 1, 2, or 3."
            }
        }
        if ($choice -in @("1", "2")) { break }
    }
}

# ── uv sync ─────────────────────────────────────────────────────────────
Write-Info "Installing Python dependencies with uv sync..."
& $uvCmd sync
if ($LASTEXITCODE -ne 0) {
    Write-Err "uv sync failed."
    exit 1
}
Write-Ok "Python dependencies installed."

# ── .env ────────────────────────────────────────────────────────────────
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item .env.example .env
    Write-Ok "Created .env from .env.example (edit it to fill in your API keys)"
}
else {
    Write-Info ".env already exists, skipping."
}

# ── subscriptions.yaml ─────────────────────────────────────────────────
if (-not (Test-Path "subscriptions.yaml") -and (Test-Path "subscriptions.example.yaml")) {
    Copy-Item subscriptions.example.yaml subscriptions.yaml
    Write-Ok "Created subscriptions.yaml from subscriptions.example.yaml"
}
else {
    if (-not (Test-Path "subscriptions.yaml")) {
        Write-Warn "subscriptions.yaml not found. You can create one later."
    }
    else {
        Write-Info "subscriptions.yaml already exists, skipping."
    }
}

# ── Data directories ───────────────────────────────────────────────────
New-Item -ItemType Directory -Path data, logs, output -Force | Out-Null
Write-Ok "Created data/, logs/, output/ directories."

# ── Verify ──────────────────────────────────────────────────────────────
Write-Info "Verifying installation..."
$version = & $uvCmd run compsynth --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "compsynth $version installed successfully."
}
else {
    Write-Warn "compsynth --version check failed. Try 'uv run compsynth --version' manually."
}

# ── Frontend (optional) ────────────────────────────────────────────────
Write-Host ""
$feChoice = Read-Host "Install frontend dependencies? [Y/n]"
switch -Regex ($feChoice) {
    "^(n|N|no|No|NO)$" {
        Write-Info "Skipping frontend. You can install later with: cd frontend && npm install"
    }
    default {
        if (Test-Path "frontend/package.json") {
            $npm = Get-Command npm -ErrorAction SilentlyContinue
            if ($npm) {
                Write-Info "Installing frontend dependencies..."
                Push-Location frontend
                try {
                    & npm install
                    if ($LASTEXITCODE -eq 0) {
                        Write-Ok "Frontend dependencies installed."
                    }
                    else {
                        Write-Warn "npm install returned exit code $LASTEXITCODE."
                    }
                }
                finally {
                    Pop-Location
                }
            }
            else {
                Write-Warn "npm not found. Install Node.js 18+ to set up the frontend."
            }
        }
        else {
            Write-Warn "frontend/package.json not found, skipping."
        }
    }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Ok "Setup complete!"
Write-Host ""
Write-Host "  Quick start:"
Write-Host "    " -NoNewline; Write-Host "compsynth serve" -ForegroundColor White -NoNewline; Write-Host "          # Start API server"
Write-Host "    " -NoNewline; Write-Host "cd frontend && npm run dev" -ForegroundColor White -NoNewline; Write-Host "  # Start frontend"
Write-Host ""
Write-Host "  First time? Run:"
Write-Host "    " -NoNewline; Write-Host "compsynth doctor" -ForegroundColor White -NoNewline; Write-Host "           # Check your setup"
Write-Host "    " -NoNewline; Write-Host "compsynth status" -ForegroundColor White -NoNewline; Write-Host "            # System health"
Write-Host ""
Write-Host "  Edit " -NoNewline; Write-Host ".env" -ForegroundColor White -NoNewline; Write-Host " to configure LLM API keys."
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

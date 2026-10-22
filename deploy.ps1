# =============================================================================
# VidHarbor one-click deployment script - Windows PowerShell
#
# Usage:
#   .\deploy.ps1              # deploy / start (incl. Evil0ctal stack + GPU autodetect)
#   .\deploy.ps1 up           # same as above
#   .\deploy.ps1 logs         # show logs (-Follow to tail)
#   .\deploy.ps1 status       # show container status (incl. Evil0ctal)
#   .\deploy.ps1 update       # git pull + rebuild image + restart
#   .\deploy.ps1 restart      # restart
#   .\deploy.ps1 backup       # stop -> archive data\ + library\ to backup\ -> start
#   .\deploy.ps1 down         # stop and remove the containers (incl. Evil0ctal)
#   .\deploy.ps1 buildx <registry/namespace/vidharbor:tag>
#                             # build & push multi-arch image (linux/amd64 + linux/arm64)
#
# .env settings (auto-generated on first run):
#   PORT=8666                # VidHarbor host port
#   TZ=Asia/Shanghai         # container timezone
#   GPU=auto                 # hardware transcode: auto / nvidia / intel / cpu
#   WITH_EVIL0CTAL=1         # deploy the Evil0ctal fallback service with this script (0 = off)
#   EVIL0CTAL_API_KEY=       # paste the API key created in its console (or use VidHarbor Settings)
#   PROXY=                   # egress proxy, e.g. http://host.docker.internal:7890 (empty = off)
#   PROXY_PLATFORMS=         # platforms routed via the proxy, JSON array, e.g. ["youtube","tiktok"]
# =============================================================================
param(
    [Parameter(Position = 0)][string]$Command = "up",
    [Parameter(Position = 1)][string]$BuildxRef = "",
    [switch]$Follow
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$DTK_DIR = "tools\dtk"

function Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Die "Docker not found. Install Docker Desktop first: winget install -e --id Docker.DockerDesktop (or https://docker.com), start it, then re-run."
    }
    # PS 5.1: redirecting native stderr under EAP=Stop can throw - always guarded
    $daemonOk = $true
    try { docker info *> $null } catch { $daemonOk = $false }
    if (-not $daemonOk -or $LASTEXITCODE -ne 0) {
        Die "Docker CLI found but the daemon is not running. Start Docker Desktop and re-run."
    }
}

function Compose {
    docker compose @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Get-EnvValue([string]$key, [string]$def) {
    if (Test-Path ".env") {
        $m = Select-String -Path ".env" -Pattern ("^" + $key + "=(.*)$") | Select-Object -Last 1
        if ($m) {
            $v = $m.Matches[0].Groups[1].Value.Trim()
            if ($v) { return $v }
        }
    }
    return $def
}

function Add-EnvValueIfMissing([string]$key, [string]$value) {
    if (-not (Test-Path ".env") -or -not (Select-String -Path ".env" -Pattern ("^" + $key + "=") -Quiet)) {
        Add-Content ".env" "$key=$value" -Encoding ASCII
    }
}

function Set-EnvValue([string]$key, [string]$value) {
    if (Test-Path ".env") {
        $found = $false
        $lines = Get-Content ".env" | ForEach-Object {
            if ($_ -match "^$key=") { $found = $true; "$key=$value" } else { $_ }
        }
        Set-Content ".env" $lines -Encoding ASCII
        if (-not $found) { Add-Content ".env" "$key=$value" -Encoding ASCII }
    } else {
        Set-Content ".env" "$key=$value" -Encoding ASCII
    }
}

function Ensure-Env {
    if (-not (Test-Path "docker-compose.yml")) {
        Die "docker-compose.yml not found - run this script from the repository root."
    }
    if (-not (Test-Path ".env")) {
        Set-Content ".env" -Encoding ASCII -Value @(
            "# VidHarbor Docker deployment settings (read by docker-compose.yml)",
            "# Host port",
            "PORT=8666",
            "# Container timezone",
            "TZ=Asia/Shanghai",
            "# GPU hardware transcode: auto / nvidia / intel / cpu",
            "GPU=auto",
            "# Deploy the Evil0ctal fallback service with this script (Douyin/TikTok; ~5 GB disk)",
            "WITH_EVIL0CTAL=1",
            "# Paste the API key created in the Evil0ctal console (douyin:read + tiktok:read)",
            "EVIL0CTAL_API_KEY=",
            "# Egress proxy for selected platforms only (Settings page can override);",
            "# a proxy on the host is reached as http://host.docker.internal:7890",
            "PROXY=",
            "# Platforms routed via the proxy (JSON array): youtube/tiktok/bilibili/douyin",
            "PROXY_PLATFORMS="
        )
        Info "Created .env. Edit PORT/TZ/GPU/WITH_EVIL0CTAL, then re-run '.\deploy.ps1 up' to apply."
    }
    Add-EnvValueIfMissing "PORT" "8666"
    Add-EnvValueIfMissing "TZ" "Asia/Shanghai"
    Add-EnvValueIfMissing "GPU" "auto"
    Add-EnvValueIfMissing "WITH_EVIL0CTAL" "1"
    Add-EnvValueIfMissing "EVIL0CTAL_API_KEY" ""
    Add-EnvValueIfMissing "PROXY" ""
    Add-EnvValueIfMissing "PROXY_PLATFORMS" ""
}

# --------------------------------------------------------------- GPU / compose ---
function Test-NvidiaRuntime {
    try { return [bool](docker info 2>$null | Select-String -Quiet nvidia) } catch { return $false }
}

function Get-DetectedGpu {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        if (Test-NvidiaRuntime) {
            # Docker Desktop (WSL2) GPU passthrough carries CUDA only - no NVENC video
            # encoder - so hardware transcoding cannot work; keep CPU in auto mode.
            Warn "NVIDIA detected, but Docker Desktop/WSL2 does not pass the NVENC video encoder - auto mode stays on CPU (a native Linux host enables it fully; force with GPU=nvidia)"
            return "cpu"
        }
        Warn "NVIDIA driver detected but Docker has no nvidia runtime - enable GPU support in Docker Desktop settings; falling back for this run"
    }
    return "cpu"
}

function Write-ComposeFile([string]$UseDtk) {
    $files = @("docker-compose.yml")
    if ($UseDtk -eq "1") { $files += "docker-compose.evil0ctal.yml" }
    $gpu = Get-EnvValue "GPU" "auto"
    if ($gpu -eq "auto") { $gpu = Get-DetectedGpu }
    switch ($gpu) {
        "nvidia" {
            if (Test-NvidiaRuntime) { $files += "docker-compose.gpu-nvidia.yml" }
            else { Warn "GPU=nvidia but Docker lacks the nvidia runtime - GPU passthrough disabled for this run" }
        }
        "intel" { $files += "docker-compose.gpu-intel.yml" }
        "cpu" { }
        default { Warn "Unknown GPU value: $gpu (auto/nvidia/intel/cpu); treating as cpu" }
    }
    Info "GPU transcode: $gpu | Evil0ctal integration: $(if ($UseDtk -eq '1') {'on'} else {'off'})"
    # Windows compose uses ';' as the COMPOSE_FILE path separator
    Set-EnvValue "COMPOSE_FILE" ($files -join ";")
}

# ------------------------------------------------------------- Evil0ctal (dtk) ---
function Rand-Bytes([int]$n) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $b = New-Object byte[] $n
    $rng.GetBytes($b)
    $rng.Dispose()
    return $b
}
function Rand-Hex([int]$n) { (Rand-Bytes $n | ForEach-Object { $_.ToString("x2") }) -join "" }
function Rand-B64([int]$n) { [Convert]::ToBase64String((Rand-Bytes $n)) }

function Invoke-DtkCompose {
    Push-Location $DTK_DIR
    try {
        $env:COMPOSE_ENV_FILES = ".env"
        docker compose -p dtk -f docker/compose.yml @args
    } finally {
        Remove-Item Env:COMPOSE_ENV_FILES -ErrorAction SilentlyContinue
        Pop-Location
    }
}

$script:DtkReady = $false

function Ensure-Dtk {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Warn "git not found - skipping Evil0ctal"; return }
    if (-not (Test-Path "$DTK_DIR\.git")) {
        Info "Cloning Evil0ctal (Douyin_TikTok_Download_API v5) -> $DTK_DIR ..."
        New-Item -ItemType Directory -Force -Path "tools" | Out-Null
        git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git $DTK_DIR
        if ($LASTEXITCODE -ne 0) { Warn "Clone failed - skipping Evil0ctal"; return }
    }
    if (-not (Test-Path "$DTK_DIR\.env")) {
        $pg = Rand-Hex 24; $pw = Rand-Hex 24
        Set-Content "$DTK_DIR\.env" -Encoding ASCII -Value @(
            "# Generated by deploy.ps1 - back it up; losing DTK_SECRET_KEY makes stored cookies undecryptable",
            "# Prebuilt image from Docker Hub (amd64/arm64); pin a version via DTK_IMAGE_TAG (e.g. 5.1.6)",
            "DTK_IMAGE=evil0ctal/douyin_tiktok_download_api",
            "DTK_IMAGE_TAG=latest",
            "DTK_SECRET_KEY=$(Rand-B64 48)",
            "POSTGRES_PASSWORD=$pg",
            "REDIS_PASSWORD=$pw",
            "DTK_DATABASE_URL=postgresql+asyncpg://dtk:$pg@postgres:5432/dtk",
            "DTK_REDIS_URL=redis://:$pw@redis:6379/0",
            "DTK_BROWSER_RPC_URL=http://browser-rpc:9000"
        )
        Info "Generated $DTK_DIR\.env (random secrets)"
    }
    # Shared external network declared in docker-compose.evil0ctal.yml
    try { docker network create dtk_edge 2>$null } catch { }
    Info "Starting Evil0ctal stack (api/postgres/redis pull prebuilt images, browser container builds locally; ~10 min first run)..."
    Invoke-DtkCompose --profile browser up -d --build --wait --wait-timeout 300
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType File -Force -Path "$DTK_DIR\.deploy-ok" | Out-Null
        $script:DtkReady = $true
        Show-DtkSetupHint
        return
    }
    if (Test-Path "$DTK_DIR\.deploy-ok") {
        Warn "Evil0ctal failed to start (a previous deployment exists - its data volumes are kept); retry '.\deploy.ps1 up' later"
        return
    }
    # First-ever deployment failed: usually a postgres init race; reset the (still empty) volumes and retry once
    Warn "First start failed - resetting Evil0ctal volumes and retrying once..."
    try { Invoke-DtkCompose down -v *> $null } catch { }
    Invoke-DtkCompose --profile browser up -d --build --wait --wait-timeout 300
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType File -Force -Path "$DTK_DIR\.deploy-ok" | Out-Null
        $script:DtkReady = $true
        Show-DtkSetupHint
        return
    }
    Warn "Evil0ctal failed to start - VidHarbor deployment continues; retry '.\deploy.ps1 up' later"
}

function Show-DtkSetupHint {
    try { $logs = Invoke-DtkCompose logs api } catch { $logs = $null }
    $token = $null
    if ($logs) {
        $m = ($logs | Select-String -Pattern 'token=([A-Za-z0-9._-]+)') | Select-Object -Last 1
        if ($m) { $token = $m.Matches[0].Groups[1].Value }
    }
    Write-Host ""
    Info "Evil0ctal console: http://127.0.0.1:8000"
    if ($token) { Info "First-run setup link (valid 24 h): http://127.0.0.1:8000/setup?token=$token" }
    if (-not (Get-EnvValue "EVIL0CTAL_API_KEY" "")) {
        Write-Host "  Wizard: create admin -> skip proxy -> mint douyin identity -> smoke test,"
        Write-Host "  then create an API key in its console (scopes douyin:read + tiktok:read),"
        Write-Host "  put it into .env as EVIL0CTAL_API_KEY= and re-run '.\deploy.ps1 up' (or use VidHarbor Settings)."
    }
}

function Test-DtkNetwork {
    try {
        $name = docker network ls --filter "name=^dtk_edge$" --format "{{.Name}}" 2>$null
    } catch { $name = "" }
    return ("$name" -eq "dtk_edge")
}

function Get-EnvValueIn([string]$file, [string]$key, [string]$def) {
    if (Test-Path $file) {
        $m = Select-String -Path $file -Pattern ("^" + $key + "=(.*)$") | Select-Object -Last 1
        if ($m) {
            $v = $m.Matches[0].Groups[1].Value.Trim()
            if ($v) { return $v }
        }
    }
    return $def
}

# --- Evil0ctal first-run wizard + API key, fully automatic (no manual console steps) ---
# Returns the API key string, or $null on failure.
function Ensure-DtkApikey {
    $api = "http://127.0.0.1:8000"
    $dtkEnv = "$DTK_DIR\.env"
    $user = Get-EnvValueIn $dtkEnv "DTK_ADMIN_USER" "vidharbor"
    $pass = Get-EnvValueIn $dtkEnv "DTK_ADMIN_PASSWORD" ""
    if (-not $pass) {
        $pass = Rand-Hex 12
        Add-Content $dtkEnv "DTK_ADMIN_USER=$user" -Encoding ASCII
        Add-Content $dtkEnv "DTK_ADMIN_PASSWORD=$pass" -Encoding ASCII
        Info "Evil0ctal admin credentials generated into $dtkEnv"
    }
    try { $status = Invoke-RestMethod -Uri "$api/api/setup/status" -TimeoutSec 5 } catch { $status = $null }
    $initialized = $status -and (($status.data -and $status.data.initialized) -or $status.initialized)
    if (-not $initialized) {
        $logs = Invoke-DtkCompose logs api
        $m = ($logs | Select-String -Pattern 'token=([A-Za-z0-9._-]+)') | Select-Object -Last 1
        if (-not $m) { Warn "No Evil0ctal setup token found - skipping automatic API key"; return $null }
        $token = $m.Matches[0].Groups[1].Value
        try {
            $body = @{ token = $token; username = $user; password = $pass } | ConvertTo-Json
            Invoke-RestMethod -Method Post -Uri "$api/api/setup/init" -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        } catch {
            Warn "Evil0ctal admin init failed (probably initialized manually with a different password) - skipping automatic API key"
            return $null
        }
        Info "Evil0ctal admin created automatically (user: $user, password in $dtkEnv)"
    }
    $key = Get-EnvValueIn $dtkEnv "DTK_VIDHARBOR_KEY" ""
    if ($key) { return $key }
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    try {
        $body = @{ username = $user; password = $pass } | ConvertTo-Json
        Invoke-RestMethod -Method Post -Uri "$api/api/v1/auth/login" -WebSession $session -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
    } catch {
        Warn "Evil0ctal console login failed - skipping automatic API key (create one manually in the console)"
        return $null
    }
    try {
        $body = @{ name = "vidharbor"; scopes = @("douyin:read", "tiktok:read") } | ConvertTo-Json
        $resp = Invoke-RestMethod -Method Post -Uri "$api/api/v1/admin/api-keys" -WebSession $session -ContentType "application/json" -Body $body -TimeoutSec 10
        $key = $resp.key
        if (-not $key -and $resp.data) { $key = $resp.data.key }
    } catch {
        Warn "Evil0ctal API key creation failed"
        return $null
    }
    if (-not $key) { Warn "Evil0ctal API key missing in response"; return $null }
    Add-Content $dtkEnv "DTK_VIDHARBOR_KEY=$key" -Encoding ASCII
    Info "Evil0ctal API key created (douyin:read + tiktok:read); it will be synced into VidHarbor settings"
    return $key
}

# Sync the fallback engine settings into VidHarbor (URL -> container network; API key -> the
# automatically created one; writes only when something differs)
function Sync-Evil0ctalSettings([string]$port, [string]$key) {
    $cur = $null
    foreach ($i in 1..6) {
        try { $cur = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/settings" -TimeoutSec 5; break } catch { Start-Sleep -Seconds 5 }
    }
    if (-not $cur) { Warn "VidHarbor API not ready - skipped fallback engine sync"; return }
    $evil = $cur.settings.evil0ctal
    $patch = @{}
    if ($evil.base_url -ne "http://api:8000") { $patch.base_url = "http://api:8000" }
    # A manual EVIL0CTAL_API_KEY in .env means the user manages the key themselves
    if ($key -and (Get-EnvValue "EVIL0CTAL_API_KEY" "")) { $key = "" }
    if ($key -and $evil.api_key -ne $key) { $patch.api_key = $key }
    if ($patch.Count -eq 0) { return }
    try {
        $body = @{ evil0ctal = $patch } | ConvertTo-Json
        Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:$port/api/settings" `
            -ContentType "application/json" -Body $body -TimeoutSec 5 | Out-Null
        Info "Fallback engine settings synced (URL=http://api:8000$(if ($key) {', API key updated'}); effective within ~1 min)"
    } catch {
        Warn "Could not sync the fallback engine settings - set them in VidHarbor Settings"
    }
}

# ------------------------------------------------------------------- commands ---
function Invoke-Up {
    Ensure-Docker; Ensure-Env
    $useDtk = 1
    if ((Get-EnvValue "WITH_EVIL0CTAL" "1") -ne "1") { $useDtk = 0 }
    $script:DtkReady = $false
    $dtkKey = $null
    if ($useDtk -eq 1) {
        Ensure-Dtk
        if ($script:DtkReady) { $dtkKey = Ensure-DtkApikey }
        if (-not $script:DtkReady -and -not (Test-DtkNetwork)) {
            Warn "Evil0ctal not ready and shared network dtk_edge missing - starting standalone this time"
            $useDtk = 0
        }
    }
    Write-ComposeFile $useDtk
    Info "Building and starting VidHarbor (first build takes a few minutes: npm + ffmpeg + Python deps)..."
    Compose up -d --build
    if ($useDtk -eq 1) { Sync-Evil0ctalSettings (Get-EnvValue "PORT" "8666") $dtkKey }
    $port = Get-EnvValue "PORT" "8666"
    Info "Started: http://127.0.0.1:$port  (data persists in .\data and .\library)"
    Compose ps
}

switch ($Command.ToLower()) {
    "up"      { Invoke-Up }
    "down" {
        Ensure-Docker
        Compose down
        if (Test-Path "$DTK_DIR\docker\compose.yml") {
            Info "Stopping Evil0ctal ..."
            # --profile browser is required: compose only removes services in active profiles,
            # otherwise the browser container is left behind
            Invoke-DtkCompose --profile browser down --remove-orphans
            if ($LASTEXITCODE -ne 0) { Warn "Evil0ctal stop failed (can be ignored)" }
        }
        Info "Stopped."
    }
    "restart" { Ensure-Docker; Compose restart; Compose ps }
    "status" {
        Ensure-Docker
        Compose ps
        if (Test-Path "$DTK_DIR\docker\compose.yml") {
            Write-Host "--- Evil0ctal ---"
            Invoke-DtkCompose --profile browser ps
        }
    }
    "logs" {
        Ensure-Docker
        if ($Follow) { Compose logs -f } else { Compose logs --tail=200 }
    }
    "update" {
        Ensure-Docker; Ensure-Env
        if (Test-Path ".git") {
            Info "Pulling latest code..."
            git pull --ff-only
            if ($LASTEXITCODE -ne 0) { Warn "git pull failed (local changes?) - continuing with current code." }
        }
        if (Test-Path "$DTK_DIR\.git") {
            Info "Pulling latest Evil0ctal code..."
            Push-Location $DTK_DIR
            git pull --ff-only
            if ($LASTEXITCODE -ne 0) { Warn "Evil0ctal git pull failed - continuing with current code." }
            Pop-Location
        }
        Info "Rebuilding image and restarting..."
        Invoke-Up
    }
    "backup" {
        Ensure-Docker
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        New-Item -ItemType Directory -Force -Path "backup" | Out-Null
        $dest = "backup\vidharbor-$stamp.tar.gz"
        Info "Stopping VidHarbor for a consistent SQLite backup (Evil0ctal keeps running)..."
        Compose stop
        # bsdtar ships with Windows 10+; same archive format as the bash script
        tar --exclude=library/.tmp -czf $dest data library
        if ($LASTEXITCODE -eq 0) {
            $size = "{0:N1} MB" -f ((Get-Item $dest).Length / 1MB)
            Info "Backup created: $dest ($size)"
            Info "Restore: stop the stack, then extract with: tar -xzf $dest (from the repo root)"
        } else {
            Die "Backup failed."
        }
        Compose start
    }
    "buildx" {
        Ensure-Docker
        if (-not $BuildxRef) {
            Die "Usage: .\deploy.ps1 buildx <registry/namespace/vidharbor:tag>   e.g. ghcr.io/you/vidharbor:latest"
        }
        try { docker buildx version *> $null } catch { }
        if ($LASTEXITCODE -ne 0) { Die "buildx is required: https://github.com/docker/buildx#installing" }
        Info "Building and pushing multi-arch image linux/amd64,linux/arm64 -> $BuildxRef ..."
        docker buildx build --platform linux/amd64,linux/arm64 -t $BuildxRef --push .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    "help" {
        $lines = Get-Content -Path $PSCommandPath
        $end = 1
        for ($i = 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^# =====') { $end = $i; break }
        }
        $lines[1..$end] | ForEach-Object { $_ -replace '^# ?', '' }
    }
    default { Die "Unknown command: $Command (see: .\deploy.ps1 help)" }
}

# Jetstream periodic refresh (Phase 0 orchestration).
# Ensures the Postgres container is up, then rebuilds board/detail/digest from GDELT.
# Registered as a Windows Scheduled Task "JetstreamRefresh" (see CLAUDE.md). Logs to refresh.log.
$ErrorActionPreference = "Continue"
$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $repo "refresh.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Set-Location $repo

"[$ts] --- refresh start ---" | Out-File -Append -Encoding utf8 $log
docker compose up -d *>> $log
$env:DATABASE_URL = "postgresql://meridian:meridian@localhost:5432/meridian"
python -m scripts.build_board *>> $log
"[$ts] refresh done (exit $LASTEXITCODE)" | Out-File -Append -Encoding utf8 $log

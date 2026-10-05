# VigilantEye PostgreSQL backup (Windows / Compose).
# Non-destructive. Does not embed passwords in the script.
#
# Usage (from repo root):
#   .\scripts\backup_postgres.ps1
#
# Operator retention recommendation:
#   - daily dumps for 14 days
#   - weekly dumps for 8 weeks
#   - store off-host / encrypted
#   - verify with restore test monthly (see docs/DATABASE.md)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Root) { $Root = (Get-Location).Path }
$OutDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $Root "backups" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMddTHHmmssZ"
$OutFile = Join-Path $OutDir "vigilanteye_$Stamp.dump"
$TmpName = "ve_backup_$Stamp.dump"

Push-Location $Root
try {
  docker compose exec -T db pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -Fc -f "/tmp/$TmpName"
  if (-not $env:POSTGRES_USER) {
    docker compose exec -T db pg_dump -U vigilant -d vigilant_eye -Fc -f "/tmp/$TmpName"
  }
  docker compose cp "db:/tmp/$TmpName" $OutFile
  Write-Host "Backup written: $OutFile"
  Get-Item $OutFile | Format-List Name, Length, FullName
}
finally {
  Pop-Location
}

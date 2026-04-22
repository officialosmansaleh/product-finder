param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$fileName = "productfinder-$timestamp.sql"
$tempPath = "/tmp/$fileName"
$localPath = Join-Path $OutputDir $fileName

docker compose -f $ComposeFile exec -T postgres sh -lc "pg_dump -U `$POSTGRES_USER -d `$POSTGRES_DB > $tempPath"
docker compose -f $ComposeFile cp "postgres:$tempPath" $localPath
docker compose -f $ComposeFile exec -T postgres rm -f $tempPath

Write-Host "Backup created: $localPath"

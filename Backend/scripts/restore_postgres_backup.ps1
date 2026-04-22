param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$DatabaseName = "productfinder_restore_check",
    [string]$Host = "localhost",
    [string]$User = "postgres"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

if (-not $env:PGPASSWORD) {
    throw "PGPASSWORD is not set in the current shell."
}

$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"

& $psql -U $User -h $Host -d postgres -c "DROP DATABASE IF EXISTS $DatabaseName;"
& $psql -U $User -h $Host -d postgres -c "CREATE DATABASE $DatabaseName;"
& $psql -U $User -h $Host -d $DatabaseName -f $BackupFile

Write-Host "Restore completed into database: $DatabaseName"

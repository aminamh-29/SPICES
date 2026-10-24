# Starts the MH Spices test server with Gmail email turned on.
# Right-click this file > "Run with PowerShell", or in the VS Code terminal run:  .\start-server.ps1
# The App Password is only kept in memory while the server runs. It is never saved to a file.

Set-Location $PSScriptRoot

# stop an older copy of the server if one is still running on port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$env:GMAIL_USER = "aminamh2920@gmail.com"
$secure = Read-Host "Paste your 16-character Gmail App Password" -AsSecureString
$env:GMAIL_APP_PASSWORD = [System.Net.NetworkCredential]::new("", $secure).Password

Start-Process "http://localhost:8000/mhspices.html"
python server.py

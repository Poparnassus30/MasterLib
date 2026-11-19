
# REINEROUGE - Audit reseau Windows
# Lecture seule - aucune modification du systeme

$Date = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Dossier = Join-Path $env:USERPROFILE "Documents\REINEROUGE\Audits"
New-Item -ItemType Directory -Path $Dossier -Force | Out-Null

$Fichier = Join-Path $Dossier "audit_reseau_$Date.txt"

function Section {
    param([string]$Titre)
    "`n========== $Titre ==========`n" |
        Out-File $Fichier -Append -Encoding utf8
}

function Collecter {
    param(
        [string]$Titre,
        [scriptblock]$Commande
    )

    Section $Titre

    try {
        & $Commande 2>&1 |
            Out-String -Width 250 |
            Out-File $Fichier -Append -Encoding utf8
    }
    catch {
        "ERREUR : $_" |
            Out-File $Fichier -Append -Encoding utf8
    }
}

"REINEROUGE - AUDIT RESEAU" |
    Out-File $Fichier -Encoding utf8

"Date : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
    Out-File $Fichier -Append -Encoding utf8

"Machine : $env:COMPUTERNAME" |
    Out-File $Fichier -Append -Encoding utf8

Collecter "SYSTEME" {
    Get-ComputerInfo |
        Select-Object CsName, WindowsProductName, OsVersion, OsBuildNumber
}

Collecter "INTERFACES RESEAU" {
    Get-NetAdapter |
        Format-Table Name, InterfaceDescription, Status, LinkSpeed -AutoSize
}

Collecter "CONFIGURATION IP ET DNS" {
    Get-NetIPConfiguration -Detailed
}

Collecter "ROUTES IPV4" {
    route print -4
}

Collecter "ROUTES IPV6" {
    route print -6
}

Collecter "ROUTAGE TEST IPV4" {
    Find-NetRoute -RemoteIPAddress 1.1.1.1
}

Collecter "ROUTAGE TEST IPV6" {
    Find-NetRoute -RemoteIPAddress 2606:4700:4700::1111
}

Collecter "PROCESSUS VPN ET TUNNELS" {
    Get-Process |
        Where-Object {
            $_.ProcessName -match "warp|cloudflare|tailscale"
        } |
        Select-Object ProcessName, Id, CPU, Path
}

Collecter "SERVICES VPN ET TUNNELS" {
    Get-Service |
        Where-Object {
            $_.Name -match "warp|cloudflare|tailscale"
        } |
        Format-Table Name, Status, StartType
}

Collecter "CONNEXIONS TCP" {
    Get-NetTCPConnection -State Established |
        Select-Object LocalAddress, LocalPort,
            RemoteAddress, RemotePort, OwningProcess
}

Collecter "PORTS UDP" {
    Get-NetUDPEndpoint |
        Select-Object LocalAddress, LocalPort, OwningProcess
}

if (Get-Command warp-cli -ErrorAction SilentlyContinue) {
    Collecter "WARP STATUS" {
        warp-cli status
    }

    Collecter "WARP SETTINGS" {
        warp-cli settings
    }
}

if (Get-Command tailscale -ErrorAction SilentlyContinue) {
    Collecter "TAILSCALE STATUS" {
        tailscale status
    }
}

Write-Host ""
Write-Host "Audit termine !" -ForegroundColor Green
Write-Host "Rapport : $Fichier" -ForegroundColor Cyan

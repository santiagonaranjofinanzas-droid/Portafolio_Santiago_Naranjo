# Shared utility functions for AI Development Framework

# Set encoding to UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Log ($message) {
    Write-Output "[INFO] $message"
}

function Write-Success ($message) {
    if ($Host.UI.RawUI) {
        Write-Host "[SUCCESS] $message" -ForegroundColor Green
    } else {
        Write-Output "[SUCCESS] $message"
    }
}

function Write-Warning ($message) {
    if ($Host.UI.RawUI) {
        Write-Host "[WARNING] $message" -ForegroundColor Yellow
    } else {
        Write-Output "[WARNING] $message"
    }
}

function Write-Error ($message) {
    if ($Host.UI.RawUI) {
        Write-Host "[ERROR] $message" -ForegroundColor Red
    } else {
        Write-Output "[ERROR] $message"
    }
}

function Copy-Safe ($source, $destination) {
    if (Test-Path $destination) {
        # Check if identical to avoid unnecessary writes
        $srcHash = Get-FileHash $source -Algorithm SHA256
        $destHash = Get-FileHash $destination -Algorithm SHA256
        if ($srcHash.Hash -eq $destHash.Hash) {
            return $false # No change needed
        }
        
        # Backup existing file
        $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
        $backup = "$destination.$timestamp.bak"
        Copy-Item $destination $backup -Force
        Write-Warning "Backup created: $(Split-Path $backup -Leaf)"
    }
    
    # Ensure destination folder exists
    $parent = Split-Path $destination -Parent
    if (!(Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    
    Copy-Item $source $destination -Force
    return $true
}

function Test-CommandExists ($commandName) {
    $cmd = Get-Command $commandName -ErrorAction SilentlyContinue
    return $null -ne $cmd
}

function Get-CommandPath ($commandName) {
    $cmd = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    return $null
}

function Validate-JsonFile ($path) {
    try {
        Get-Content $path -Raw | ConvertFrom-Json | Out-Null
        return $true
    } catch {
        Write-Error "Invalid JSON in ${path}: $_"
        return $false
    }
}

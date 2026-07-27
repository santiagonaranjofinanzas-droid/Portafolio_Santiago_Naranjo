#!/usr/bin/env bash
# AI Development Framework Unix Bootstrap Wrapper

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# Determine PowerShell executable
if command -v pwsh &> /dev/null; then
    PS_BIN="pwsh"
elif command -v powershell &> /dev/null; then
    PS_BIN="powershell"
else
    echo "[ERROR] PowerShell Core (pwsh) or powershell is required to run this bootstrap."
    echo "Please install PowerShell Core for your platform: https://github.com/PowerShell/PowerShell"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
$PS_BIN -ExecutionPolicy Bypass -File "$SCRIPT_DIR/bootstrap_project.ps1" "$@"
exit $?

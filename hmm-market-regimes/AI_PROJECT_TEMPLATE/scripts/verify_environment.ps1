# Verify development environment tools
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Output "--- Environment Verification ---"
$tools = @("node", "npm", "python", "uv", "git", "serena", "graphify", "codex", "antigravity-ide")
foreach ($t in $tools) {
    $cmd = Get-Command $t -ErrorAction SilentlyContinue
    if ($cmd) {
        $version = ""
        try {
            if ($t -eq "git" -or $t -eq "python" -or $t -eq "node" -or $t -eq "npm" -or $t -eq "uv") {
                $version = (& $t --version 2>&1).ToString().Trim()
            } else {
                $version = (& $t --version 2>&1).ToString().Trim()
            }
        } catch {
            $version = "Installed (Version check failed: $_)"
        }
        Write-Output "[SUCCESS] $t is available in PATH"
        Write-Output "          Path: $($cmd.Source)"
        Write-Output "          Version: $version"
    } else {
        Write-Output "[WARNING] $t is NOT available in PATH"
    }
}
Write-Output "---------------------------------"

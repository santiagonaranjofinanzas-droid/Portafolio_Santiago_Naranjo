# Project configuration module

param (
    [string]$projectRoot = ".",
    [string]$detectionJson = ""
)

# Import shared utils using PSScriptRoot
. (Join-Path $PSScriptRoot "..\shared\utils.ps1")

if ([string]::IsNullOrEmpty($detectionJson)) {
    Write-Error "No detection JSON provided."
    exit 1
}

$info = $detectionJson | ConvertFrom-Json
$projectName = $info.project_name
$resolvedRoot = (Resolve-Path $projectRoot).Path

Write-Log "Configuring project: $projectName in $resolvedRoot"

$templateDir = (Resolve-Path (Join-Path $PSScriptRoot "..\templates")).Path
$frameworkRootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# 1. Configure Git if needed
if (!$info.git) {
    Write-Log "Initializing Git repository..."
    if (Test-CommandExists "git") {
        # Run git init
        & git init $resolvedRoot | Out-Null
        Write-Success "Git repository initialized."
    } else {
        Write-Warning "Git not found in PATH; skipping Git initialization."
    }
}

# Copy Git ignore/attributes templates
Copy-Safe (Join-Path $templateDir "git\.gitignore") (Join-Path $resolvedRoot ".gitignore") | Out-Null
Copy-Safe (Join-Path $templateDir "git\.gitattributes") (Join-Path $resolvedRoot ".gitattributes") | Out-Null

# 2. Configure Serena
if (Test-CommandExists "serena") {
    Write-Log "Configuring Serena..."
    $serenaTargetDir = Join-Path $resolvedRoot ".serena"
    if (!(Test-Path $serenaTargetDir)) {
        New-Item -ItemType Directory -Path $serenaTargetDir -Force | Out-Null
    }
    
    # Customize project.yml
    $serenaProjYaml = Join-Path $templateDir "serena\project.yml"
    $targetProjYaml = Join-Path $serenaTargetDir "project.yml"
    
    # Form languages yaml list
    $langListStr = ""
    foreach ($lang in $info.languages) {
        $langListStr += "  - $lang`n"
    }
    if ($langListStr -eq "") {
        $langListStr = "  - python`n" # Default fallback
    }
    $langListStr = $langListStr.TrimEnd()
    
    $content = Get-Content $serenaProjYaml -Raw
    $content = $content -replace "{{PROJECT_NAME}}", $projectName
    $content = $content -replace "{{LANGUAGES}}", $langListStr
    
    [System.IO.File]::WriteAllText($targetProjYaml, $content, [System.Text.Encoding]::UTF8)
    Write-Success "Serena project configuration generated."
    
    # Create empty memories directory if not exists
    $memoriesDir = Join-Path $serenaTargetDir "memories"
    if (!(Test-Path $memoriesDir)) {
        New-Item -ItemType Directory -Path $memoriesDir -Force | Out-Null
    }
} else {
    Write-Warning "Serena not found in PATH; skipping Serena configuration."
}

# 3. Configure Antigravity
Write-Log "Configuring Antigravity..."
$agentsDir = Join-Path $resolvedRoot ".agents"
if (!(Test-Path $agentsDir)) {
    New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
}

# Copy mcp_config.json
Copy-Safe (Join-Path $templateDir "antigravity\mcp_config.json") (Join-Path $agentsDir "mcp_config.json") | Out-Null

# Copy hooks.json and replace {{WORKSPACE_PATH}}
$hooksTemplate = Join-Path $templateDir "antigravity\hooks.json"
$targetHooks = Join-Path $agentsDir "hooks.json"
$escapedRoot = $resolvedRoot -replace "\\", "\\"
$hooksContent = Get-Content $hooksTemplate -Raw
$hooksContent = $hooksContent -replace "{{WORKSPACE_PATH}}", $escapedRoot
[System.IO.File]::WriteAllText($targetHooks, $hooksContent, [System.Text.Encoding]::UTF8)

# Copy rules and workflows of Graphify
$rulesDir = Join-Path $agentsDir "rules"
$workflowsDir = Join-Path $agentsDir "workflows"
if (!(Test-Path $rulesDir)) { New-Item -ItemType Directory -Path $rulesDir -Force | Out-Null }
if (!(Test-Path $workflowsDir)) { New-Item -ItemType Directory -Path $workflowsDir -Force | Out-Null }

Copy-Safe (Join-Path $templateDir "antigravity\startup.bat") (Join-Path $agentsDir "startup.bat") | Out-Null
Copy-Safe (Join-Path $templateDir "antigravity\startup.ps1") (Join-Path $agentsDir "startup.ps1") | Out-Null

# Copy graphify rules if graphify is installed
if (Test-CommandExists "graphify") {
    $scratchRules = "C:\Users\NuevoAdmin\.gemini\antigravity-ide\scratch\test_install\.agents\rules\graphify.md"
    $scratchWorkflows = "C:\Users\NuevoAdmin\.gemini\antigravity-ide\scratch\test_install\.agents\workflows\graphify.md"
    if (Test-Path $scratchRules) {
        Copy-Safe $scratchRules (Join-Path $rulesDir "graphify.md") | Out-Null
    }
    if (Test-Path $scratchWorkflows) {
        Copy-Safe $scratchWorkflows (Join-Path $workflowsDir "graphify.md") | Out-Null
    }
}
Write-Success "Antigravity configuration generated."

# 4. Configure Codex if Codex is installed
if (Test-CommandExists "codex") {
    Write-Log "Configuring Codex..."
    $codexConfig = Join-Path $resolvedRoot "config.toml"
    if (!(Test-Path $codexConfig)) {
        $tomlTemplate = Join-Path $templateDir "codex\config.toml"
        $tomlContent = Get-Content $tomlTemplate -Raw
        $tomlContent = $tomlContent -replace "{{PROJECT_NAME}}", $projectName
        $tomlContent = $tomlContent -replace "{{WORKSPACE_PATH}}", $escapedRoot
        [System.IO.File]::WriteAllText($codexConfig, $tomlContent, [System.Text.Encoding]::UTF8)
        Write-Success "Codex configuration generated."
    }
}

# 5. Generate Documentation templates in docs/
$docsTargetDir = Join-Path $resolvedRoot "docs"
if (!(Test-Path $docsTargetDir)) {
    New-Item -ItemType Directory -Path $docsTargetDir -Force | Out-Null
}

$docFiles = @("README.md", "README_AGENT.md", "PROJECT_STRUCTURE.md", "ARCHITECTURE.md", "DECISIONS.md", "SETUP.md", "CONTRIBUTING.md", "AI_GUIDELINES.md")
foreach ($doc in $docFiles) {
    $srcDoc = Join-Path $templateDir "docs\$doc"
    $destDoc = if ($doc -eq "README.md" -or $doc -eq "README_AGENT.md") { Join-Path $resolvedRoot $doc } else { Join-Path $docsTargetDir $doc }
    
    if (!(Test-Path $destDoc)) {
        $docContent = Get-Content $srcDoc -Raw
        $docContent = $docContent -replace "{{PROJECT_NAME}}", $projectName
        
        # Replace language list
        $langsComma = $info.languages -join ", "
        $docContent = $docContent -replace "{{LANGUAGES_LIST}}", $langsComma
        
        # Replace framework list
        $fraworkComma = $info.frameworks -join ", "
        if ($fraworkComma -eq "") { $fraworkComma = "None" }
        $docContent = $docContent -replace "{{FRAMEWORKS_LIST}}", $fraworkComma
        
        # Typology description
        $typologyStr = $info.project_types -join ", "
        if ($typologyStr -eq "") { $typologyStr = "general software development" }
        $docContent = $docContent -replace "{{PROJECT_TYPE}}", $typologyStr
        
        # Directory structure using safe ASCII characters
        $treeASCII = "+-- docs/`r`n+-- .serena/`r`n+-- .agents/`r`n+-- graphify-out/"
        $docContent = $docContent -replace "{{DIR_STRUCTURE_TREE}}", $treeASCII
        
        # Prereqs
        $prereqs = "Python 3.12"
        if ($info.languages -contains "typescript") { $prereqs += ", Node.js" }
        if ($info.languages -contains "cpp") { $prereqs += ", C++ Compiler" }
        if ($info.languages -contains "java") { $prereqs += ", JDK" }
        if ($info.languages -contains "rust") { $prereqs += ", Rust Cargo" }
        $docContent = $docContent -replace "{{LANGUAGE_ENV_REQ}}", $prereqs
        
        # Package manager
        $pkgMgr = "uv / pip"
        if ($info.languages -contains "typescript") { $pkgMgr = "npm / yarn" }
        if ($info.languages -contains "rust") { $pkgMgr = "cargo" }
        $docContent = $docContent -replace "{{PACKAGE_MANAGER_REQ}}", $pkgMgr
        
        # Install cmd
        $instCmd = "uv pip install -r requirements.txt"
        if ($info.languages -contains "typescript") { $instCmd = "npm install" }
        if ($info.languages -contains "rust") { $instCmd = "cargo build" }
        $docContent = $docContent -replace "{{DEPENDENCY_INSTALL_CMD}}", $instCmd
        
        [System.IO.File]::WriteAllText($destDoc, $docContent, [System.Text.Encoding]::UTF8)
    }
}
Write-Success "Documentation templates generated."

# 6. Copy VS Code settings
$vscodeTargetDir = Join-Path $resolvedRoot ".vscode"
if (!(Test-Path $vscodeTargetDir)) {
    New-Item -ItemType Directory -Path $vscodeTargetDir -Force | Out-Null
}
Copy-Safe (Join-Path $templateDir "vscode\settings.json") (Join-Path $vscodeTargetDir "settings.json") | Out-Null

# 7. Copy Maintenance scripts
$scriptsTargetDir = Join-Path $resolvedRoot ".agents\scripts"
if (!(Test-Path $scriptsTargetDir)) {
    New-Item -ItemType Directory -Path $scriptsTargetDir -Force | Out-Null
}
$frameworkScriptsDir = (Resolve-Path (Join-Path $frameworkRootDir "scripts")).Path
$scriptFiles = Get-ChildItem -Path $frameworkScriptsDir -Filter "*.ps1" -File
foreach ($sf in $scriptFiles) {
    Copy-Safe $sf.FullName (Join-Path $scriptsTargetDir $sf.Name) | Out-Null
}
# Copy shared/utils.ps1 to target scripts folder as utils.ps1
Copy-Safe (Join-Path $frameworkRootDir "shared\utils.ps1") (Join-Path $scriptsTargetDir "utils.ps1") | Out-Null
Write-Success "Maintenance scripts copied."

# 8. Copy CLI controllers
Copy-Safe (Join-Path $frameworkRootDir "framework.ps1") (Join-Path $resolvedRoot "framework.ps1") | Out-Null
Copy-Safe (Join-Path $frameworkRootDir "framework.bat") (Join-Path $resolvedRoot "framework.bat") | Out-Null
Write-Success "Framework CLI controllers copied."

# 9. Generate framework.json and write to project root
$targetMetaJson = Join-Path $resolvedRoot "framework.json"
$srcMetaJson = Join-Path $frameworkRootDir "framework.json"
if (Test-Path $srcMetaJson) {
    $metaContent = Get-Content $srcMetaJson -Raw
    # We can inject/update the template_path to be absolute for this setup
    $metaObj = $metaContent | ConvertFrom-Json
    $metaObj.template_path = $frameworkRootDir
    $updatedMetaContent = $metaObj | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($targetMetaJson, $updatedMetaContent, [System.Text.Encoding]::UTF8)
    Write-Success "Framework version metadata generated in project root."
}

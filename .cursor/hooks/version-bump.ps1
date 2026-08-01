param([string]$InputData)

$json = $InputData | ConvertFrom-Json

$toolName = $json.toolName
$path = $json.input.path

# Only trigger on file write/edit tools targeting home-assistant-addon/
if ($toolName -ne "StrReplace" -and $toolName -ne "Write") { return }
if (-not $path) { return }
if (-not $path.StartsWith("home-assistant-addon/")) { return }

# Skip if editing config.json directly (avoid double-bump)
if ($path -eq "home-assistant-addon/config.json") { return }

# Read current version
$configPath = Join-Path $PWD "home-assistant-addon\config.json"
if (-not (Test-Path $configPath)) { return }

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$version = $config.version

# Parse version
$parts = $version -split '\.'
$patch = [int]$parts[2] + 1
$newVersion = "$($parts[0]).$($parts[1]).$patch"

$stateFile = Join-Path $PWD ".cursor\hooks\bumped.txt"

# Skip if already bumped this session
if (Test-Path $stateFile) { return }

# Bump config.json in place
$config.version = $newVersion
$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -NoNewline -Encoding UTF8

# Mark as bumped for this session
"bumped" | Set-Content $stateFile -Encoding UTF8

$additionalContext = @"
[Version Bump Hook] Automatically bumped `home-assistant-addon/config.json` from $version to $new.0 (patch) since you edited: $path
"@

$result = @{
    additional_context = $additionalContext
} | ConvertTo-Json -Compress

Write-Output $result

# Creates "Ascensus ad Mathematica.lnk" in the project folder and on the Desktop.
# Target: .venv\Scripts\pythonw.exe -m ascensus (working dir = project folder, icon = ascensus\assets\icon.ico).
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$name = "Ascensus ad Mathematica.lnk"
$target = Join-Path $project ".venv\Scripts\pythonw.exe"
$icon = Join-Path $project "ascensus\assets\icon.ico"
$shell = New-Object -ComObject WScript.Shell
$folders = @($project, [Environment]::GetFolderPath("Desktop"))
foreach ($folder in $folders) {
    if (-not $folder -or -not (Test-Path $folder)) { continue }
    $link = $shell.CreateShortcut((Join-Path $folder $name))
    $link.TargetPath = $target
    $link.Arguments = "-m ascensus"
    $link.WorkingDirectory = $project
    $link.IconLocation = "$icon,0"
    $link.Description = "Ascensus ad Mathematica"
    $link.Save()
    Write-Host "Created $(Join-Path $folder $name)"
}

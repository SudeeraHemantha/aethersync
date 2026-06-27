$ErrorActionPreference = "Stop"
$jdkDir = "c:\Users\Elite computers\OneDrive\Documents\LNBTI\AntiGravity\aethersync\android\jdk17"
if (!(Test-Path $jdkDir)) {
    New-Item -ItemType Directory -Force -Path $jdkDir | Out-Null
}

$zipPath = "$jdkDir\jdk17.zip"
$url = "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"

Write-Host "Downloading JDK 17 from $url..."
Invoke-WebRequest -Uri $url -OutFile $zipPath

Write-Host "Extracting JDK 17..."
Expand-Archive -Path $zipPath -DestinationPath $jdkDir

Write-Host "Cleaning up ZIP file..."
Remove-Item $zipPath

$subDirs = Get-ChildItem -Path $jdkDir -Directory
if ($subDirs.Count -eq 1) {
    Write-Host "JDK 17 installed successfully at: $($subDirs[0].FullName)"
} else {
    Write-Host "JDK 17 extracted to: $jdkDir"
}

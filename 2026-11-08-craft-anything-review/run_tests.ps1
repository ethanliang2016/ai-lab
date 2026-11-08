# craft-anything local test driver (Windows native CLI)
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$cli = Join-Path $root "craft-anything\target\release\craft-anything-cli.exe"
$evi = Join-Path $root "evidence"
New-Item -ItemType Directory -Force $evi | Out-Null
$log = Join-Path $evi "run_log.txt"
$proj = Join-Path $evi "proj.cany"
"" | Out-File $log -Encoding utf8

function Step($name, [scriptblock]$block) {
    $sep = "=" * 66
    "$sep`n$name`n$sep" | Tee-Object -FilePath $log -Append
    $out = & $block 2>&1 | Out-String
    $out | Tee-Object -FilePath $log -Append
    "" | Tee-Object -FilePath $log -Append
}

Step "T0 version" { & $cli --version }
Step "T1 doctor" { & $cli doctor }
Step "T2 capabilities" { & $cli capabilities }
Step "T3 commands (full tool list)" { & $cli commands }
Step "T3b tool count" { (& $cli commands | Measure-Object -Line).Lines }
Step "T4 triage notepad.exe (first-look)" { & $cli --project $proj triage C:\Windows\System32\notepad.exe }
Step "T5 report --html" { & $cli --project $proj report --html --out (Join-Path $evi "report.html") }
"ALL DONE" | Tee-Object -FilePath $log -Append

[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$InputFile,
 [int]$ExpectedParameters = -1,
 [Parameter(Mandatory=$true)][string]$HighScoreExe,
 [Parameter(Mandatory=$true)][string]$BatchTemplateName,
 [string]$BackgroundTemplateName = '', 
 [switch]$EstimateBackground,
 [ValidateRange(0,100)][int]$BackgroundBendingFactor = 2,
 [ValidateRange(1,10000)][int]$BackgroundGranularity = 20,
 [switch]$NoSmoothedBackground,
 [switch]$NormalizeOnly,
 [int]$TimeoutSeconds = 180
)
$ErrorActionPreference='Stop'
if ($BackgroundBendingFactor -ne 2 -or $BackgroundGranularity -ne 20 -or $NoSmoothedBackground) {throw 'The user requires fixed background settings: 2/20/smoothed.'}
if (-not $NormalizeOnly) {$EstimateBackground=$true}
$hsInput=(Resolve-Path -LiteralPath $InputFile).Path
$hsExe=(Resolve-Path -LiteralPath $HighScoreExe).Path
$hsStage=Split-Path -Parent $hsInput
if ([IO.Path]::GetExtension($hsInput) -ine '.HPF') {throw 'Input must be HPF.'}
if ((Get-Item -LiteralPath $hsExe).VersionInfo.FileVersion -ne '3.0.5.15611') {throw 'Validate another software version before using this launcher.'}
if (Get-Process -Name HighScorePlus -ErrorAction SilentlyContinue) {throw 'HighScore is already running; finish that session before dispatching a backend job.'}
$hsReg="HKCU:\Software\PANalytical\X'Pert HighScore Plus\TColPSUserBatch"
$hsBgReg="HKCU:\Software\PANalytical\X'Pert HighScore Plus\TColPSCorrectBackground"
$hsReference=Get-ItemPropertyValue -LiteralPath $hsReg -Name $BatchTemplateName
$hsSplit=$hsReference.IndexOf('actCorrectBackground;')
if ($hsSplit -lt 0) {throw 'Unrecognized native batch header.'}
$hsBatchName='Codex_XRD_'+[Guid]::NewGuid().ToString('N')
$hsBackgroundName=$null
$hsBackgroundProfile=$null
$hsActions='actEditAutoRefinerSteps;Clinker;actSaveDoc;Default;EndOfBatchItems;'
if ($NormalizeOnly) { $hsActions='actSaveDoc;Default;EndOfBatchItems;' }
if ($NormalizeOnly -and $EstimateBackground) {throw 'Normalization must not alter background.'}
$hsInitialHash=(Get-FileHash -LiteralPath $hsInput -Algorithm SHA256).Hash
$hsBeforeFiles=@(Get-ChildItem -LiteralPath $hsStage -File -Filter '*.HPF' | ForEach-Object {$_.FullName})
$hsCompleted=$false;$hsProc=$null
try {
 if ($EstimateBackground) {
  # Derive an isolated preset from the user's explicitly configured native preset.
  if (-not $BackgroundTemplateName) {throw 'Configure a native background preset name before solving.'}
  $hsBgParts=(Get-ItemPropertyValue -LiteralPath $hsBgReg -Name $BackgroundTemplateName).Split(';')
  if ($hsBgParts.Count -ne 13 -or $hsBgParts[2] -ne '0' -or $hsBgParts[3] -ne '-5' -or $hsBgParts[4] -ne '0') {throw 'Background preset format changed; inspect the native UI before editing.'}
  if (($hsBgParts[6..9] -join ';') -ne '0.7;0;1;2') {throw 'Background preset ancillary fields changed; verify Accept / Add to net scan=Nothing in the native UI.'}
  $hsBgParts[5]='2';$hsBgParts[10]='1';$hsBgParts[11]='20' 
  $hsBackgroundProfile=$hsBgParts -join ';'
  $hsBackgroundName='Codex_XRD_BG_'+[Guid]::NewGuid().ToString('N')
  New-ItemProperty -LiteralPath $hsBgReg -Name $hsBackgroundName -PropertyType String -Value $hsBackgroundProfile | Out-Null
  $hsActions='actCorrectBackground;'+$hsBackgroundName+';'+$hsActions
 }
 $hsBatch=$hsReference.Substring(0,$hsSplit)+$hsActions
 New-ItemProperty -LiteralPath $hsReg -Name $hsBatchName -PropertyType String -Value $hsBatch | Out-Null
 $hsArgs='"'+$hsInput+'" /Q /B="'+$hsBatchName+'"'
 $hsProc=Start-Process -FilePath $hsExe -ArgumentList $hsArgs -WorkingDirectory $hsStage -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $hsStage 'solver_stdout.log') -RedirectStandardError (Join-Path $hsStage 'solver_stderr.log')
 @{PID=$hsProc.Id;BatchName=$hsBatchName;BackgroundName=$hsBackgroundName;BackgroundProfile=$hsBackgroundProfile;Arguments=$hsArgs} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $hsStage 'started.json') -Encoding UTF8
 if (-not $hsProc.WaitForExit($TimeoutSeconds*1000)) {throw "Native process $($hsProc.Id) still running. Stop dispatching new jobs. Keep its temporary input and inspect the logs."}
 $hsCompleted=$true;$hsProc.Refresh()
 $hsLog=Get-Content -LiteralPath (Join-Path $hsStage 'solver_stdout.log') -Raw
 $hsCounts=@([regex]::Matches($hsLog,'parameters\s*\.+(\d+)')|ForEach-Object {[int]$_.Groups[1].Value}|Select-Object -Unique)
 $hsOutputs=@(Get-ChildItem -LiteralPath $hsStage -File -Filter '*.HPF'|Where-Object {$_.FullName -notin $hsBeforeFiles})
 if ($hsOutputs.Count -eq 0 -and (Get-FileHash -LiteralPath $hsInput -Algorithm SHA256).Hash -ne $hsInitialHash) {$hsOutput=$hsInput}
 elseif ($hsOutputs.Count -eq 1) {$hsOutput=$hsOutputs[0].FullName}
 else {throw 'Native save output is missing or ambiguous.'}
 $hsStatus=@{ExitCode=$hsProc.ExitCode;Completed=$true;OutputFile=$hsOutput;SolverParameterCounts=$hsCounts;ExpectedParameters=$ExpectedParameters;NormalizeOnly=[bool]$NormalizeOnly;BackgroundEstimated=[bool]$EstimateBackground;BackgroundBendingFactor=$BackgroundBendingFactor;BackgroundGranularity=$BackgroundGranularity;BackgroundSmoothed=(-not $NoSmoothedBackground)}
 $hsStatus|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $hsStage 'exit.json') -Encoding UTF8
 if ($hsProc.ExitCode -ne 0) {throw 'Native job failed.'}
 if (-not $NormalizeOnly -and ($hsCounts.Count -ne 1 -or $hsCounts[0] -ne $ExpectedParameters -or $hsLog -notmatch 'Solution found')) {throw 'Native solve/save/parameter-count verification failed.'}
 if ($NormalizeOnly -and $hsLog -match 'Solution found') {throw 'Unexpected refinement during normalization; inspect the temporary output.'}
 $hsStatus|ConvertTo-Json
} finally {
 if ($hsCompleted -or -not $hsProc) {
  Remove-ItemProperty -LiteralPath $hsReg -Name $hsBatchName -ErrorAction SilentlyContinue
  if ($hsBackgroundName) {Remove-ItemProperty -LiteralPath $hsBgReg -Name $hsBackgroundName -ErrorAction SilentlyContinue}
 }
}

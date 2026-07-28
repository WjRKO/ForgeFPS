# Stub ambiente
$script:PM_ON = $true
$script:PM_ROWS = 0
$script:PM_OUT = '/tmp/pm_fake.csv'
function Read-Shared($p) { if (Test-Path $p) { Get-Content $p -Raw } else { $null } }
. /tmp/getfps.ps1

# CSV finto PresentMon v1: 100 frame ~7ms (=143fps) con 3 hitch >50ms
$lines = @('Application,ProcessID,msBetweenPresents,msUntilDisplayed')
for ($i = 0; $i -lt 100; $i++) {
  $ms = 7.0 + ($i % 5) * 0.3
  if ($i -in 30, 60, 90) { $ms = 75.5 }
  $lines += ('game.exe,123,{0},20.1' -f $ms.ToString([Globalization.CultureInfo]::InvariantCulture))
}
Set-Content /tmp/pm_fake.csv ($lines -join "`n")

$f = Get-Fps
if (-not $f) { Write-Output 'FAIL: Get-Fps null'; exit 1 }
Write-Output ("fps={0} game={1} lat={2}" -f $f.fps, $f.game, $f.latency_ms)
if ($f.gd) {
  Write-Output ("gd: ft_p99={0} ft_worst={1} hitches={2} pace_dev={3}" -f $f.gd.ft_p99, $f.gd.ft_worst, $f.gd.hitches, $f.gd.pace_dev)
  if ($f.gd.hitches -eq 3 -and $f.gd.ft_worst -eq 75.5 -and $f.fps -gt 90 -and $f.fps -lt 130) { Write-Output 'GET-FPS TEST PASS' } else { Write-Output 'CHECK VALUES' }
} else { Write-Output 'FAIL: gd null' }

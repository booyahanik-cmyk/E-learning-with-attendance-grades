Add-Type -AssemblyName System.Drawing
$bmp = [System.Drawing.Bitmap]::FromFile((Resolve-Path "ref.png").Path)
for ($y = 60; $y -le 68; $y++) {
    $c = $bmp.GetPixel(945, $y)
    Write-Host ('under Grades y={0}: #{1:X2}{2:X2}{3:X2}' -f $y, $c.R, $c.G, $c.B)
}
$bmp.Dispose()

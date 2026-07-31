$b = [System.IO.File]::ReadAllBytes('c:\Users\USER\Documents\GitHub\MediaHa\home-assistant-addon\src\ui\js\fileBrowser.js')
$last20 = $b[($b.Length-25)..($b.Length-1)]
foreach ($byte in $last20) { Write-Host ("{0:X2}" -f $byte) }
Write-Host "Total length:" $b.Length

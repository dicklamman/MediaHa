$lines = Get-Content 'c:\Users\USER\Documents\GitHub\MediaHa\home-assistant-addon\src\opds.py' -Encoding UTF8
Write-Host "Total lines: $($lines.Count)"

$komgaStart = 766
$komgaEnd = 1108   # End before the catchall (line 1109)

# Extract sections  
$komgaSection = $lines[($komgaStart - 1)..($komgaEnd - 1)]
$before = $lines[0..($komgaStart - 2)]       # everything before komga
$after = $lines[$komgaEnd..($lines.Count - 1)]  # catchall and beyond

Write-Host "Komga section: $($komgaSection.Count) lines ($komgaStart-$komgaEnd)"
Write-Host "Before: $($before.Count) lines"
Write-Host "After: $($after.Count) lines"

# Reassemble: before + komga + after
$newLines = $before + $komgaSection + $after
$newLines | Set-Content 'c:\Users\USER\Documents\GitHub\MediaHa\home-assistant-addon\src\opds.py' -Encoding UTF8
Write-Host "Done. New line count: $($newLines.Count)"

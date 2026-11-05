# Copia as fotos baixadas em Downloads\fotos-carros para o site e publica.
# Rodar no PC, dentro da pasta do repositório: powershell -ExecutionPolicy Bypass -File atualizar-fotos.ps1
$ErrorActionPreference = 'Continue'
$repo = $PSScriptRoot
$src = Join-Path $env:USERPROFILE 'Downloads\fotos-carros'
$dst = Join-Path $repo 'fotos'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Set-Location $repo
git pull --rebase --quiet 2>$null
Add-Type -AssemblyName System.Drawing
$novas = 0
foreach ($file in (Get-ChildItem $src -Filter *.jpg | Where-Object { $_.Name -match '^\d+_\d+\.jpg$' })) {
  $out = Join-Path $dst $file.Name
  if (-not (Test-Path $out)) {
    try {
      $img = [System.Drawing.Image]::FromFile($file.FullName)
      $w = [Math]::Min(520, $img.Width); $h = [int]($img.Height * $w / $img.Width)
      $bmp = New-Object System.Drawing.Bitmap $w, $h
      $g = [System.Drawing.Graphics]::FromImage($bmp); $g.InterpolationMode = 'HighQualityBicubic'; $g.DrawImage($img, 0, 0, $w, $h)
      $enc = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
      $p = New-Object System.Drawing.Imaging.EncoderParameters 1
      $p.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 72L
      $bmp.Save($out, $enc, $p); $g.Dispose(); $bmp.Dispose(); $img.Dispose(); $novas++
    } catch { Copy-Item $file.FullName $out; $novas++ }
  }
}
$lista = Get-ChildItem $dst -Filter *.jpg | Sort-Object Name | ForEach-Object { $_.Name }
ConvertTo-Json @($lista) -Compress | Set-Content -Encoding UTF8 (Join-Path $dst 'index.json')
git add fotos
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m "Fotos: $novas novas" --quiet; git push --quiet 2>&1 | Out-Null }
"fotos novas: $novas; total: $($lista.Count)"

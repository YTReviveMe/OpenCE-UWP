param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$root=Split-Path -Parent $PSScriptRoot
$sourcePath=Join-Path $root 'port\xbox\assets\AppLogo.png'
[IO.Directory]::CreateDirectory($OutputDirectory)|Out-Null
$sourceImage=[Drawing.Image]::FromFile($sourcePath)
$source=[Drawing.Bitmap]::new($sourceImage)
try {
 function ContentBounds([Drawing.Bitmap]$bitmap) {
  $left=$bitmap.Width; $top=$bitmap.Height; $right=-1; $bottom=-1
  for($y=0;$y -lt $bitmap.Height;$y++){for($x=0;$x -lt $bitmap.Width;$x++){if($bitmap.GetPixel($x,$y).A){if($x -lt $left){$left=$x};if($x -gt $right){$right=$x};if($y -lt $top){$top=$y};if($y -gt $bottom){$bottom=$y}}}}
  if($right -lt $left){return [Drawing.Rectangle]::new(0,0,$bitmap.Width,$bitmap.Height)}
  return [Drawing.Rectangle]::new($left,$top,$right-$left+1,$bottom-$top+1)
 }
 $sourceBounds=ContentBounds $source
 function Square([string]$name,[int]$size) {
  $image=[Drawing.Bitmap]::new($size,$size,[Drawing.Imaging.PixelFormat]::Format32bppArgb); $g=[Drawing.Graphics]::FromImage($image)
  try { $g.Clear([Drawing.Color]::Transparent); $g.InterpolationMode='HighQualityBicubic'; $g.DrawImage($source,[Drawing.Rectangle]::new(0,0,$size,$size),$sourceBounds,[Drawing.GraphicsUnit]::Pixel); $image.Save((Join-Path $OutputDirectory $name),'Png') }
  finally { $g.Dispose(); $image.Dispose() }
 }
 Square 'StoreLogo.png' 50; Square 'Square44x44Logo.png' 44; Square 'Square150x150Logo.png' 150
 $image=[Drawing.Bitmap]::new(620,300); $g=[Drawing.Graphics]::FromImage($image)
 try { $g.Clear([Drawing.Color]::FromArgb(255,16,24,32)); $g.InterpolationMode='HighQualityBicubic'; $g.DrawImage($source,170,10,280,280)
  $image.Save((Join-Path $OutputDirectory 'SplashScreen.png'),'Png') }
 finally { $g.Dispose(); $image.Dispose() }
} finally { $source.Dispose(); $sourceImage.Dispose() }

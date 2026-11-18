# Normalize every videos/raw/*.mp4 to spec: H.264, 720p, 15 fps, -g 15 (playbook §1.3).
# Usage: powershell -File scripts/prepare_videos.ps1
# Mapping matches config.yaml camera order.
$targets = @("FOD_02_N_30_AXIS_Trim", "FID_01_Y_SAMSUNG_Trim", "FID_01_Y_HIK_Trim", "FID_01_Y_AXIS_Trim")
for ($i = 0; $i -lt $targets.Count; $i++) {
    $cam = "cam{0:d2}" -f ($i + 1)
    $src = "videos/raw/$($targets[$i]).mp4"
    ffmpeg -y -hide_banner -loglevel error -i $src -vf fps=15 `
        -c:v libx264 -preset veryfast -g 15 -pix_fmt yuv420p -an "videos/$cam.mp4"
    Write-Host "$src -> videos/$cam.mp4"
}

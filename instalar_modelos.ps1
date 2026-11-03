# ==========================================================
# instalar_modelos.ps1
# Descarga los archivos pesados de Oddye que no están en GitHub.
# Uso (PowerShell, desde la carpeta del proyecto):
#     powershell -ExecutionPolicy Bypass -File .\instalar_modelos.ps1
# Si una descarga se corta, vuelve a ejecutarlo: continúa donde quedó.
# ==========================================================
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

$archivos = @(
    @{ Nombre = "Cerebro: Qwen3-4B (2.5 GB)";
       Url    = "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf";
       Destino = "Modelos\Cerebro 4B (llama.cpp)\Qwen3-4B-Q4_K_M.gguf"; Bytes = 2497280256 },
    @{ Nombre = "Oidos: Whisper base (148 MB)";
       Url    = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin";
       Destino = "Modelos\Oidos (Whisper Base)\ggml-base.bin"; Bytes = 147951465 },
    @{ Nombre = "Voz: Piper es_MX-claude-high (63 MB)";
       Url    = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx";
       Destino = "Voz (Piper)\es_MX-claude-high.onnx"; Bytes = 63122309 }
)

foreach ($a in $archivos) {
    $ruta = Join-Path $raiz $a.Destino
    New-Item -ItemType Directory -Force -Path (Split-Path $ruta) | Out-Null
    Write-Host "`n>> $($a.Nombre)" -ForegroundColor Cyan
    if ((Test-Path $ruta) -and ((Get-Item $ruta).Length -eq $a.Bytes)) {
        Write-Host "   Ya estaba descargado." -ForegroundColor Green
        continue
    }
    # curl.exe viene con Windows 10/11: -L sigue redirecciones, -C - reanuda
    curl.exe -L -C - --fail -o "$ruta" $a.Url
    if ((Test-Path $ruta) -and ((Get-Item $ruta).Length -eq $a.Bytes)) {
        Write-Host "   Listo: $ruta" -ForegroundColor Green
    } else {
        Write-Host "   No se completó. Vuelve a ejecutar el script o bájalo a mano desde:`n   $($a.Url)`n   y guárdalo en: $ruta" -ForegroundColor Yellow
    }
}

Write-Host "`nModelos listos. Siguiente paso:" -ForegroundColor Cyan
Write-Host "   python -m venv venv"
Write-Host "   .\venv\Scripts\activate"
Write-Host "   pip install -r requirements.txt"
Write-Host "   python main.py"

$ErrorActionPreference = "Stop"
Set-Location "D:\JuWade_research\Per_stage_FFT"
& "C:\Program Files\Inkscape\bin\python.exe" `
  "experiments\fault_injection_1024\common\tools\run_p1_yosys_v4_attempt2.py"
exit $LASTEXITCODE

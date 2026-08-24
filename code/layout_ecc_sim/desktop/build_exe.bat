@echo off
rem LayoutECC desktop packer. Run from code\layout_ecc_sim
rem Output: dist\LayoutECC_StrikeViewer.exe
rem Packaging list (--add-data) MUST match LayoutECC_StrikeViewer.spec datas; this bat is the build entry.
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name LayoutECC_StrikeViewer ^
  --icon desktop\icon.ico ^
  --add-data layout_ecc\webapp;layout_ecc\webapp ^
  --add-data data\layout\p1_ooc_win\primitive_map.csv;data\layout\p1_ooc_win ^
  --add-data data\weibull_7series_measured.json;data ^
  --add-data data\rpm_grid_calibration.json;data ^
  --add-data data\golden;data\golden ^
  --add-data ..\..\experiments\fault_injection_1024\common\python;experiments\fault_injection_1024\common\python ^
  --add-data ..\..\experiments\fault_injection_1024\projects\P1;experiments\fault_injection_1024\projects\P1 ^
  --add-data desktop\orbit_env.py;. ^
  --add-data C:\Users\zhuao\tcas\code\orbit_seu\orbit_seu;orbit_seu_lib\orbit_seu ^
  --add-data C:\Users\zhuao\tcas\code\orbit_seu\env_data\spenvis_let;orbit_seu_env\env_data\spenvis_let ^
  --add-data C:\Users\zhuao\tcas\code\orbit_seu\examples;orbit_seu_env\examples ^
  --add-data C:\Users\zhuao\tcas\code\orbit_seu\env_data\oneill_lis_coefficients.csv;orbit_seu_lib\env_data ^
  --paths . ^
  desktop\app.py

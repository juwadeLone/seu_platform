# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('layout_ecc/webapp', 'layout_ecc/webapp'), ('data/layout/p1_ooc_win/primitive_map.csv', 'data/layout/p1_ooc_win'), ('data/weibull_7series_measured.json', 'data'), ('data/rpm_grid_calibration.json', 'data'), ('data/golden', 'data/golden'), ('../../experiments/fault_injection_1024/common/python', 'experiments/fault_injection_1024/common/python'), ('../../experiments/fault_injection_1024/projects/P1', 'experiments/fault_injection_1024/projects/P1'), ('desktop/orbit_env.py', '.'), ('C:/Users/zhuao/tcas/code/orbit_seu/orbit_seu', 'orbit_seu_lib/orbit_seu'), ('C:/Users/zhuao/tcas/code/orbit_seu/env_data/spenvis_let', 'orbit_seu_env/env_data/spenvis_let'), ('C:/Users/zhuao/tcas/code/orbit_seu/examples', 'orbit_seu_env/examples'), ('C:/Users/zhuao/tcas/code/orbit_seu/env_data/oneill_lis_coefficients.csv', 'orbit_seu_lib/env_data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LayoutECC_StrikeViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['desktop/icon.ico'],
)

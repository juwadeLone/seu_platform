"""orbit_seu 轨道辐射环境的桌面集成层。

复用 tcas 仓库的 orbit_seu 包（与冻结基线 out_vx690t_measured 同一套代码）：
开发态直接 import tcas 里的包；exe 冻结态用打包进去的副本
（--add-data 到 orbit_seu_lib/ 与 orbit_seu_env/）。

不修改 orbit_seu 的任何文件；只把 config 里的相对谱文件路径改写为绝对路径，
使 run() 与 cwd 无关。输入谱文件为冻结数据，只读。不编造谱。
"""
import copy
import json
import os
import sys

_ORBIT_PAYLOAD = None
_TCAS_ORBIT_SEU = r"C:\Users\zhuao\tcas\code\orbit_seu"
_CFG_REL = os.path.join("examples", "xc7vx690t_measured_meo.json")


def _usable(lib, env):
    return (
        os.path.isdir(os.path.join(lib, "orbit_seu"))
        and os.path.isfile(os.path.join(env, _CFG_REL))
    )


def _roots():
    """Return (lib_root, env_root, config_path).

    lib_root  —— 含 orbit_seu 包的目录（加入 sys.path）
    env_root  —— env_data/ 与 examples/ 所在目录

    解析顺序（不编造谱文件）：
      (a) 冻结态 _MEIPASS 副本（orbit_seu_lib / orbit_seu_env）若完整
      (b) 环境变量 ORBIT_SEU_ROOT（指向含 orbit_seu 包与 examples/ 的树）
      (c) C:\\Users\\zhuao\\tcas\\code\\orbit_seu 若该目录存在且完整
      (d) 清晰报错
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
        lib = os.path.join(base, "orbit_seu_lib")
        env = os.path.join(base, "orbit_seu_env")
        if _usable(lib, env):
            return lib, env, os.path.join(env, _CFG_REL)

    env_var = (os.environ.get("ORBIT_SEU_ROOT") or "").strip()
    if env_var:
        root = os.path.abspath(env_var)
        # 常见两种布局：树根即 orbit_seu 仓库（lib==env）；或含 orbit_seu_lib/env。
        candidates = [
            (root, root),
            (os.path.join(root, "orbit_seu_lib"), os.path.join(root, "orbit_seu_env")),
        ]
        for lib, env in candidates:
            if _usable(lib, env):
                return lib, env, os.path.join(env, _CFG_REL)

    if os.path.isdir(_TCAS_ORBIT_SEU) and _usable(_TCAS_ORBIT_SEU, _TCAS_ORBIT_SEU):
        return (
            _TCAS_ORBIT_SEU,
            _TCAS_ORBIT_SEU,
            os.path.join(_TCAS_ORBIT_SEU, _CFG_REL),
        )

    raise FileNotFoundError(
        "orbit_seu not found. Tried: (a) frozen _MEIPASS copies "
        "(orbit_seu_lib/orbit_seu_env), (b) ORBIT_SEU_ROOT, "
        "(c) C:\\Users\\zhuao\\tcas\\code\\orbit_seu. "
        "Set ORBIT_SEU_ROOT to a tree that contains the orbit_seu package "
        "and examples/xc7vx690t_measured_meo.json. Spectra are not invented."
    )


def compute_orbit_payload():
    """Run orbit_seu.mission.run on the frozen MEO config; cache and return."""
    global _ORBIT_PAYLOAD
    if _ORBIT_PAYLOAD is not None:
        return _ORBIT_PAYLOAD
    lib, env, cfg_path = _roots()
    if lib not in sys.path:
        sys.path.append(lib)

    with open(cfg_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    config = copy.deepcopy(config)

    # 相对路径 -> 绝对路径（env_data 冻结谱文件，只读）
    files = (((config.get("environment") or {}).get("let_spectra_files")) or {})
    for k, rel in list(files.items()):
        files[k] = os.path.normpath(os.path.join(env, rel))

    from orbit_seu.mission import run  # noqa: E402  (path added above)

    result = run(config)
    result["_config_source"] = os.path.basename(cfg_path)
    result["_frozen_baseline"] = {
        "note": "out_vx690t_measured/results.json（layout_ecc 仓库现行次数表，2026-08-20 实跑）",
        "per_domain_rates_day_per_bit": {
            "CRAM": 2.2145206308470516e-10,
            "BRAM": 9.154913262420707e-10,
            "FF": 2.371627141428757e-10,
        },
        "device_events_per_day": 0.10072309318190643,
    }
    _ORBIT_PAYLOAD = result
    return result

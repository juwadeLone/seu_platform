"""STK Connect (TCP socket) 客户端。

按 STK Connect 文档的线协议实现（help.agi.com STK 12/13,
Connect Input & Output Formats）：

- 客户端每条请求发送一行 ASCII 命令；
- 服务端回 `ACK` 或 `NACK`；
- 带数据命令在 ACK 后跟一个定长 40 字节头包（含命令名 + 数据长度），
  再跟该长度的数据体；
- `ConControl AckOn` 开启 ACK/NACK 握手，`AsyncOff` 保持同步问答。

用到的命令（均为 Connect 字母表命令表中的稳定命令）：
- `ConControl`            连接控制（AckOn / AsyncOff）
- `GetAnimTime`           当前动画历元
- `Position <path> "<t>"` 返回 18 个实数：lat,lon,alt(Connect 距离单位,
  默认 km) + 三者变化率；ECF 位置/速度(x,y,z,vx,vy,vz)；ICRF 同序。
  lat/lon 单位为度。

真实 STK 上可能有方言差异（如 Connect 距离单位被 SetUnits 改过）——
这类常数集中在文件顶部 DISTANCE_UNIT_KM 等位置，便于现场调。
协议层的验证靠 tests/test_stk_live.py 里的 MockStkServer（镜像文档格式）。
"""
from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001            # STK Connect 默认监听端口
CONNECT_TIMEOUT_S = 10.0
# STK Connect 默认距离单位为 km、角度为度；真机上被 SetUnits 改过就改这里
DISTANCE_UNIT_KM = 1.0         # 返回值换算到 km 的倍率（默认已是 km）
ANGLE_UNIT_DEG = 1.0           # 返回值换算到度的倍率（默认已是度）

_HEADER_LEN = 40               # 文档：定长 40 字节头包
_ANIM_RE = re.compile(r"[-+0-9.eE]+")


class StkConnectError(RuntimeError):
    pass


@dataclass
class StkPosition:
    """`Position` 命令返回的一次历元状态（lat/lon 度、alt/xyz km）。"""
    epoch: str                       # 请求的历元（STK 时间字符串）
    lat_deg: float
    lon_deg: float
    alt_km: float
    lat_rate: float = 0.0            # deg/Connect 时间单位
    lon_rate: float = 0.0
    alt_rate: float = 0.0
    ecef_km: tuple = ()              # ECF x,y,z
    ecef_vel: tuple = ()
    icrf_km: tuple = ()              # 惯性系 x,y,z
    icrf_vel: tuple = ()

    def as_dict(self):
        return {
            "epoch": self.epoch,
            "lat_deg": self.lat_deg,
            "lon_deg": self.lon_deg,
            "alt_km": self.alt_km,
            "lat_rate": self.lat_rate,
            "lon_rate": self.lon_rate,
            "alt_rate": self.alt_rate,
            "ecef_km": list(self.ecef_km),
            "ecef_vel": list(self.ecef_vel),
            "icrf_km": list(self.icrf_km),
            "icrf_vel": list(self.icrf_vel),
        }


class StkConnectClient:
    """同步问答式 STK Connect 客户端（stdlib 纯 socket）。"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 timeout=CONNECT_TIMEOUT_S):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self._sock = None
        self._buf = b""

    # ---- connection -------------------------------------------------------
    def connect(self):
        """开 TCP 连接并启用 ACK 握手 + 同步模式。"""
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)
        self.send("ConControl AckOn AsyncOff", expect_data=False)
        return self

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # ---- wire -------------------------------------------------------------
    def _readline(self):
        while b"\n" not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise StkConnectError("connection closed by STK")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.rstrip(b"\r").decode("ascii", "replace").strip()

    def _read_exact(self, n):
        while len(self._buf) < n:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise StkConnectError("connection closed by STK")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def send(self, command, expect_data=True):
        """发一条命令；返回数据段文本（expect_data=False 时返回 None）。"""
        if self._sock is None:
            raise StkConnectError("not connected")
        self._sock.sendall(command.rstrip() + b"\n" if isinstance(command, bytes)
                           else (command.rstrip() + "\n").encode("ascii"))
        status = self._readline()
        if status.startswith("NACK"):
            raise StkConnectError(f"NACK: {command} -> {status}")
        if not status.startswith("ACK"):
            # 容错：有些版本直接把数据放在第一行
            return status if expect_data else None
        if not expect_data:
            return None
        header = self._read_exact(_HEADER_LEN).decode("ascii", "replace")
        m = re.search(r"(\d+)\s*$", header)
        if not m:
            raise StkConnectError(
                f"bad 40-byte header for {command!r}: {header!r}")
        n = int(m.group(1))
        data = self._read_exact(n).decode("utf-8", "replace") if n else ""
        return data

    # ---- commands ---------------------------------------------------------
    def get_anim_time(self):
        """GetAnimTime -> 当前动画历元字符串（原样返回，如 '1 Jan 2025 00:00:00.000'）。"""
        data = self.send("GetAnimTime")
        return data.strip().strip('"')

    def get_position(self, satellite_path, time_str=None):
        """Position <sat> "<t>" -> StkPosition（18 实数格式，见模块注释）。"""
        cmd = f"Position {satellite_path}"
        if time_str:
            cmd += f' "{time_str}"'
        data = self.send(cmd)
        nums = [float(v) for v in _ANIM_RE.findall(data)]
        if len(nums) < 18:
            raise StkConnectError(
                f"Position returned {len(nums)} numbers (need 18): {data!r}")
        lat, lon, alt = nums[0:3]
        return StkPosition(
            epoch=time_str or "",
            lat_deg=lat * ANGLE_UNIT_DEG,
            lon_deg=lon * ANGLE_UNIT_DEG,
            alt_km=alt * DISTANCE_UNIT_KM,
            lat_rate=nums[3], lon_rate=nums[4], alt_rate=nums[5],
            ecef_km=tuple(nums[6:9]), ecef_vel=tuple(nums[9:12]),
            icrf_km=tuple(nums[12:15]), icrf_vel=tuple(nums[15:18]),
        )


def poll_position(client, satellite_path):
    """一次实时采样：GetAnimTime + Position，返回 StkPosition。"""
    t = client.get_anim_time()
    return client.get_position(satellite_path, t)

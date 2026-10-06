"""WP6: cycle → (frame, sample) for P1 SDF depths.

Derived from ``p1_pfft_ecc_core_v4`` instantiations in
``experiments/※seven_arch_rtl/P1/hdl/rtl/top_p1_kernel.sv``:

    s1 DEPTH=128, s2=64, s3=32, s4=16, s5=8, s6=4, s7=2
    s8/s9 TMR stages have no deep delay line (offset 1 = next-cycle voter)
    s10 two-beat aligner (pair_phase) → offset 2

Four-lane PFFT: 1024 samples = 256 beats × 4 lanes. Address wrapping of
the stage delay line is DEPTH long; a value written at cycle t is read
about ``depth`` cycles later and overwritten on the next pass.

This is an architectural mapping, not a post-route timing simulation.
"""
from .stage_tags import N_STAGES

# delay-line depth (samples per lane) from RTL parameters
STAGE_DEPTH = {
    1: 128, 2: 64, 3: 32, 4: 16, 5: 8, 6: 4, 7: 2,
    8: 1, 9: 1, 10: 2,
}
BEATS_PER_FRAME = 256
LANES = 4
SAMPLES_PER_FRAME = BEATS_PER_FRAME * LANES  # 1024

SOURCE = (
    "p1_pfft_ecc_core_v4 #(.DEPTH(..),.STAGE(k)) sK in top_p1_kernel.sv; "
    "s8/s9 TMR have no SDF memory (offset=1); s10 pair_phase offset=2"
)


def delay_table():
    return {
        "source": SOURCE,
        "beats_per_frame": BEATS_PER_FRAME,
        "lanes": LANES,
        "samples_per_frame": SAMPLES_PER_FRAME,
        "depth_by_stage": dict(STAGE_DEPTH),
    }


def map_cycle(stage_id, cycle, address=None, lane=0, component="real"):
    """Map an injection time to the data identity sitting in that stage.

    address: delay-line address if known; defaults to cycle % depth.
    """
    st = int(stage_id)
    depth = STAGE_DEPTH.get(st, 1)
    lane = int(lane) % LANES
    cyc = int(cycle)
    addr = int(address) % max(depth, 1) if address is not None else (cyc % max(depth, 1))
    # written at cycle_write, read ~depth later
    cycle_write = cyc - addr
    age = addr  # cycles since write at this address head
    # SDF 延时线约定：地址回绕同一拍里，读出发生在下一次写入之前，
    # 因此 cycles_until_read <= cycles_until_overwrite 恒成立——
    # delay 角色在本模型下永远是 OBSERVED。masked_by_lifetime 的 MASKED
    # 分支只对外部构造的（覆写先于读出的）identity 有意义。
    cycles_until_read = max(depth - addr, 0)
    cycles_until_overwrite = max(depth - addr, 1)
    beat = (cycle_write % BEATS_PER_FRAME + BEATS_PER_FRAME) % BEATS_PER_FRAME
    # Python // 是向下取整：frame*256 + beat == cycle_write 对负数同样成立
    frame = cycle_write // BEATS_PER_FRAME
    sample = beat * LANES + lane
    return {
        "stage_id": st,
        "cycle": cyc,
        "address": addr,
        "lane": lane,
        "component": component,
        "frame": int(frame),
        "beat": int(beat),
        "sample": int(sample),
        "depth": depth,
        "cycles_since_write": age,
        "cycles_until_read": int(cycles_until_read),
        "cycles_until_overwrite": int(cycles_until_overwrite),
        "source": SOURCE,
    }


def masked_by_lifetime(identity, role="delay"):
    """Parse MASKED vs OBSERVED from the delay-line schedule.

    Overwritten before the scheduled read → MASKED (never enters the
    observation chain). Otherwise the value is OBSERVED and WP2 decides
    CORRECTED/DUE/SDC/MASKED-by-TMR.

    map_cycle() 产生的 delay 身份恒为 OBSERVED（见其中注释的读写同拍约定）；
    MASKED 只在外部传入 until_read > until_overwrite 的 identity 时出现。
    """
    until_read = identity.get("cycles_until_read")
    until_over = identity.get("cycles_until_overwrite")
    if role not in ("delay",) and identity.get("depth", 1) <= 1:
        return {
            "lifetime_class": "OBSERVED",
            "reason": "pipeline/TMR/ECC register is read next cycle",
        }
    if until_read is not None and until_over is not None and until_read > until_over:
        return {
            "lifetime_class": "MASKED",
            "reason": "overwritten before the SDF pairing read",
        }
    if until_read == 0:
        return {
            "lifetime_class": "OBSERVED",
            "reason": "read is due this cycle",
        }
    return {
        "lifetime_class": "OBSERVED",
        "reason": "will be read before overwrite",
    }

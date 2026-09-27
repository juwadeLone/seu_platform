"""What one ion strike does to the chip: effect classes and consequences.

Input is a run_strike() result; output is a short list of effect records
for the viewer. Status values:

  occurred   the sampled strike produced it (bits actually flipped)
  possible   physically possible for this hit, not quantified here
  risk       the LET is at or above a measured onset
  none       did not happen / below the measured onset
  unmodeled  the platform has no model or placement data for it

Numbers are only given where a source exists:
  - SEL onset: Lee, Wirthlin, Swift, Le, 2014 IEEE REDW (Kintex-7 XC7K325T):
    VCCAUX latch-up observed at effective LET as low as 15 MeV*cm^2/mg,
    in ~130 mA current steps, cleared by lowering VCCAUX.
  - Multi-bit share vs LET: same paper, Table 3 (single / multiple bit).
  - BRAM ECC: 7-series RAMB36E1 built-in SECDED for 64-bit words (UG473).
"""

SEL_ONSET_LET = 15.0
LEE_T3_MULTI = [(1.5, 0.068), (2.2, 0.097), (3.7, 0.437),
                (49.3, 0.486), (60.0, 0.479), (126.0, 0.498)]
LOGIC_KINDS = ("SLICE", "DSP")

CONSEQUENCE = {
    "CFG": ("配置位错",
            "所在 LUT / 布线逻辑持续出错，直到刷新把该配置帧写回", "scrub"),
    "BRAM_STATE": ("存储字错",
                   "读出即错；开 ECC 时单比特在读出时纠正", "ecc"),
    "FF_STATE": ("寄存器状态错",
                 "错一拍后随数据流向下游传播，下一次写入覆盖", "overwrite"),
}


def multi_share(let):
    """Lee 2014 Table 3 multi-bit share at the nearest measured LET."""
    let = float(let)
    lo = min(LEE_T3_MULTI, key=lambda p: abs(p[0] - let))
    return lo


def classify(strike, let):
    flipped = strike.get("flipped") or []
    cands = strike.get("candidates") or []
    bits = {}
    for f in flipped:
        n = int(f.get("n_bits") or 1)
        bits[f["domain"]] = bits.get(f["domain"], 0) + n
    total = sum(bits.values())
    n_sites_flip = len({f["unit_id"] for f in flipped})

    effects = []
    parts = " · ".join(f"{d.split('_')[0]} {n}" for d, n in bits.items())
    effects.append({
        "id": "seu", "name": "单粒子翻转", "abbr": "SEU",
        "status": "occurred" if total else "none",
        "text": f"{total} bit（{parts}）" if total else "本次没有位被翻",
    })

    ref_let, share = multi_share(let)
    multi = total >= 2
    effects.append({
        "id": "mcu", "name": "多位翻转", "abbr": "MCU",
        "status": "occurred" if multi else "none",
        "text": (f"一颗离子翻了 {total} bit、跨 {n_sites_flip} 个 Site" if multi
                 else "只翻 1 bit 或没翻"),
        "ref": f"实测：LET {ref_let:g} 时多位事件占 {share:.0%}（Lee 2014 表 3）",
    })

    logic_hit = any(c.get("res_type") in LOGIC_KINDS for c in cands)
    effects.append({
        "id": "set", "name": "单粒子瞬态", "abbr": "SET",
        "status": "possible" if logic_hit else "none",
        "text": ("打中逻辑/布线产生毛刺，被时钟沿采到才变成错误（未计量）"
                 if logic_hit else "没打中逻辑 Site"),
    })

    effects.append({
        "id": "sefi", "name": "功能中断", "abbr": "SEFI",
        "status": "unmodeled",
        "text": "打中配置控制电路会整片失常、需重配；平台无该电路位置",
    })

    sel = float(let) >= SEL_ONSET_LET
    effects.append({
        "id": "sel", "name": "单粒子闩锁", "abbr": "SEL",
        "status": "risk" if sel else "none",
        "text": ("LET ≥ 15：实测会闩锁，电流阶跃约 130 mA，需降压/断电"
                 if sel else "低于实测起始 LET 15"),
        "ref": "Lee 2014：VCCAUX 在有效 LET 15 起观测到闩锁",
    })

    consequences = []
    for dom, n in bits.items():
        if dom not in CONSEQUENCE:
            continue
        title, text, recovery = CONSEQUENCE[dom]
        consequences.append({"domain": dom, "bits": n, "title": title,
                             "text": text, "recovery": recovery})

    mods = {}
    for f in flipped:
        m = f.get("module") or "(未知)"
        mods[m] = mods.get(m, 0) + int(f.get("n_bits") or 1)

    return {
        "let": float(let),
        "bits": total,
        "bits_by_domain": bits,
        "sites_flipped": n_sites_flip,
        "effects": effects,
        "consequences": consequences,
        "modules_hit": [{"module": k, "bits": v} for k, v in
                        sorted(mods.items(), key=lambda kv: -kv[1])],
    }

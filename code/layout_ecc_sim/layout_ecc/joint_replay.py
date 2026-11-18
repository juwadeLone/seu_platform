"""Joint multi-bit replay of one strike as one event (P0 joint injection).

``functional_mapper.replay_strike`` injects each flipped (site x domain) row
on its own, at bit 0 of the real part. Here every bit one strike flips is
injected together, in one pass through the P1 PFFT:

* bits that land in the same codeword go into ONE decode (two bits in one
  SECDED word -> double_detected, never two single corrections);
* bits in different codewords keep the strike's ``event_id``;
* CFG bits, DSP state, decoder/shared logic and sites with no inferred
  codeword are ``unmapped``: they are counted, reported as a mapping rate,
  and an event that has any of them is never reported as CORRECTED/MASKED.

Scope v1: FF_STATE and BRAM_STATE bits on arithmetic [6,4,3], memory
SECDED and stage-8/9 TMR words. The layout gives site-level multiplicity,
not bit addresses: bit positions inside a word are taken from the row's
``bit_positions`` when present, otherwise drawn from a RNG seeded by
(seed, event_id, codeword, symbol) and written into the fault list, so the
fault list replays exactly. Lifetime (overwrite before read) is not applied:
every mapped bit is treated as read.

``protection="off"`` bypasses decoders and voters on the same fault list:
check symbols of an arithmetic word do not exist, SECDED parity bits do not
exist, and every hit TMR replica folds into the single unprotected copy.
"""
from __future__ import annotations

import random

from .functional import (
    _EXP,  # noqa: F401  (ensures the frozen injector is on sys.path)
    bit_reverse_order,
    ensure_golden,
    exchange_phi,
    exchanged_dif_stage,
    flip_component_bit,
    independent_operator_group,
    operator_input,
    pfft_stage_inputs,
    secded_decode,
    secded_encode_complex,
    tmr_vote,
)
from common.python.fixed_fft import DATA_WIDTH  # noqa: E402
from common.python.protection import (  # noqa: E402
    MEMORY_CODEWORD_BITS,
    MEMORY_HAMMING_BITS,
    arithmetic_643_decode,
    unpack_complex,
)

MAPPABLE_DOMAINS = ("FF_STATE", "BRAM_STATE")
WORD_BITS = 2 * DATA_WIDTH  # real + imag payload of one complex symbol
OUTCOME_ORDER = ("NO_FAULT", "MASKED", "CORRECTED", "DUE", "SDC", "UNMAPPED")


def _scheme(codeword_id):
    cw = codeword_id or ""
    if ":secded:" in cw:
        return "memory_secded"
    if cw.endswith(":tmr"):
        return "tmr3"
    if cw.endswith(":decoder"):
        return None
    if ":arith" in cw:
        return "arithmetic_643"
    return None


def _unmapped_reason(row):
    domain = row.get("domain")
    if domain == "CFG":
        return "cfg_no_essential_bit_map"
    if domain not in MAPPABLE_DOMAINS:
        return f"{str(domain).lower()}_not_modeled"
    cw = row.get("codeword_id")
    if not cw or (row.get("codeword_confidence") or "proxy") == "proxy":
        return "unknown_address"
    scheme = _scheme(cw)
    if scheme is None:
        return "decoder_or_shared_logic"
    if scheme in ("arithmetic_643", "tmr3") and row.get("symbol_id") is None:
        return "decoder_or_shared_logic"
    stage = int(row.get("stage_id") or -1)
    if scheme == "arithmetic_643" and not (1 <= stage <= 7 or stage == 10):
        return "unknown_address"
    if scheme == "tmr3" and stage not in (8, 9):
        return "unknown_address"
    if scheme == "memory_secded" and not 1 <= stage <= 10:
        return "unknown_address"
    return None


def _instance(rng, scheme, codeword_id):
    """Which word instance (sample / operator group) the codeword hit is."""
    if scheme == "arithmetic_643":
        return rng.randrange(128 if codeword_id.startswith("s10:") else 256)
    return rng.randrange(1024)


def build_event(flipped, event_id, seed=0, meta=None):
    """Expand run_strike()['flipped'] into one replayable event record."""
    bits = []
    word_rng = {}
    used = {}
    instances = {}
    for row_i, row in enumerate(flipped or []):
        n_raw = row.get("n_bits")
        n = max(int(1 if n_raw is None else n_raw), 0)
        reason = _unmapped_reason(row)
        cw = row.get("codeword_id")
        scheme = None if reason else _scheme(cw)
        sym = row.get("symbol_id")
        explicit = list(row.get("bit_positions") or [])
        base = {
            "event_id": event_id,
            "row": row_i,
            "domain": row.get("domain"),
            "stage_id": int(row.get("stage_id") or -1),
            "unit_id": row.get("unit_id"),
            "site": row.get("site"),
            "codeword_id": cw,
            "symbol_id": sym,
        }
        def unmapped(why):
            bits.append(dict(base, bit_id=f"{event_id}/b{len(bits)}",
                             mapped=False, unmapped_reason=why,
                             scheme=None, instance=None, bit=None,
                             bit_source=None))

        if reason:
            for k in range(n):
                unmapped(reason)
            continue
        if cw not in instances:
            instances[cw] = _instance(
                random.Random(f"{seed}|{event_id}|{cw}|instance"), scheme, cw)
        key = (cw, sym if scheme != "memory_secded" else None)
        width = MEMORY_CODEWORD_BITS if scheme == "memory_secded" else WORD_BITS
        taken = used.setdefault(key, set())
        rng = word_rng.setdefault(
            key, random.Random(f"{seed}|{event_id}|{key[0]}|{key[1]}"))
        for k in range(n):
            if k < len(explicit):
                pos, src = int(explicit[k]) % width, "explicit"
            elif len(taken) < width:
                pos, src = rng.choice(
                    [p for p in range(width) if p not in taken]), "sampled"
            else:
                pos = None
            if pos is None or pos in taken:
                unmapped("exceeds_word_bits")
                continue
            taken.add(pos)
            bits.append(dict(base, bit_id=f"{event_id}/b{len(bits)}",
                             mapped=True, unmapped_reason=None,
                             scheme=scheme, instance=instances[cw], bit=pos,
                             bit_source=src))
    n_mapped = sum(1 for b in bits if b["mapped"])
    return {
        "event_id": event_id,
        "seed": seed,
        "meta": dict(meta or {}),
        "n_bits": len(bits),
        "n_mapped": n_mapped,
        "n_unmapped": len(bits) - n_mapped,
        "mapping_rate": (n_mapped / len(bits)) if bits else None,
        "bits": bits,
    }


def _flip_word(word, positions):
    for p in positions:
        comp = "real" if p >= DATA_WIDTH else "imag"
        word = flip_component_bit(word, comp, p % DATA_WIDTH)
    return word


def _raw_payload(codeword):
    """SECDED payload without correction (protection off)."""
    payload, idx = 0, 0
    for pos in range(1, MEMORY_HAMMING_BITS + 1):
        if pos & (pos - 1):
            payload |= ((codeword >> (pos - 1)) & 1) << idx
            idx += 1
    return unpack_complex(payload)


def _group_indices(codeword_id, instance):
    if codeword_id.startswith("s10:"):
        base = 8 * instance
        first = 0 if codeword_id.endswith(":upper") else 1
        return [base + first + 2 * k for k in range(4)]
    return [4 * instance + k for k in range(4)]


def _apply_secded(state, cw_bits, protection):
    pos = cw_bits[0]["instance"]
    received = secded_encode_complex(state[pos])
    for b in cw_bits:
        received ^= 1 << b["bit"]
    if protection == "off":
        state[pos] = _raw_payload(received)
        return {"detected": False, "corrected": False, "uncorrectable": False,
                "decoder": "bypassed"}
    dec = secded_decode(received)
    state[pos] = dec.complex_word
    return {"detected": dec.detected, "corrected": dec.corrected,
            "uncorrectable": dec.detected and not dec.corrected,
            "decoder": dec.status}


def _apply_arith(state_in, state_out, stage, cw_id, cw_bits, protection, phi):
    idx = _group_indices(cw_id, cw_bits[0]["instance"])
    stage_phi = [[0] * 1024 for _ in range(9)] if stage == 10 else phi
    group = independent_operator_group(
        [operator_input(state_in, stage, i, stage_phi) for i in idx])
    received = list(group.outputs)
    by_sym = {}
    for b in cw_bits:
        by_sym.setdefault(int(b["symbol_id"]), []).append(b["bit"])
    for sym, positions in by_sym.items():
        received[sym] = _flip_word(received[sym], positions)
    if protection == "off":
        delivered = received[:4]
        info = {"detected": False, "corrected": False, "uncorrectable": False,
                "decoder": "bypassed"}
    else:
        dec = arithmetic_643_decode(received, group.expected_residual)
        delivered = list(dec.functional)
        info = {"detected": dec.detected, "corrected": dec.corrected,
                "uncorrectable": dec.uncorrectable,
                "decoder": ("clean" if not dec.detected else
                            "corrected" if dec.corrected else "uncorrectable")}
    for i, v in zip(idx, delivered):
        state_out[i] = v
    info["symbols"] = sorted(by_sym)
    return info


def _apply_tmr(state_out, cw_bits, protection):
    pos = cw_bits[0]["instance"]
    good = state_out[pos]
    copies = [good, good, good]
    by_rep = {}
    for b in cw_bits:
        by_rep.setdefault(int(b["symbol_id"]) % 3, []).append(b["bit"])
    if protection == "off":
        state_out[pos] = _flip_word(
            good, sorted({p for ps in by_rep.values() for p in ps}))
        return {"detected": False, "corrected": False, "uncorrectable": False,
                "decoder": "bypassed", "symbols": sorted(by_rep)}
    for rep, positions in by_rep.items():
        copies[rep] = _flip_word(copies[rep], positions)
    voted, disagree = tmr_vote(copies)
    state_out[pos] = voted
    # voter saw a mismatch but the majority itself was wrong
    failed = disagree and voted != good
    return {"detected": disagree, "corrected": False, "uncorrectable": failed,
            "decoder": "vote", "symbols": sorted(by_rep)}


def _event_from(source, event_id, seed):
    if isinstance(source, dict) and "bits" in source:
        return source
    if isinstance(source, dict):
        return build_event(source.get("flipped") or [],
                           source.get("event_id", event_id),
                           seed=source.get("seed", seed))
    return build_event(source or [], event_id or "e0", seed=seed)


def replay_event(source, event_id=None, seed=0, protection="on", golden=None):
    """Inject every mapped bit of one event together; classify the event.

    source: run_strike()['flipped'] rows, an events.jsonl line
    ({event_id, seed, flipped}), or a build_event() record.
    """
    golden = golden or ensure_golden()
    event = _event_from(source, event_id, seed)
    mapped = [b for b in event["bits"] if b["mapped"]]
    words = {}
    for b in mapped:
        words.setdefault((b["stage_id"], b["codeword_id"]), []).append(b)

    gold_out = list(golden["result"].output)
    codewords = []
    if not words:
        output = gold_out
    else:
        if "_stage_inputs" not in golden:
            golden["_stage_inputs"] = pfft_stage_inputs(golden["frame"])
        phi = exchange_phi(1024)
        first = min(s for s, _ in words)
        state = list(golden["_stage_inputs"][first - 1])
        for stage in range(first, 11):
            here = sorted((cw, bs) for (s, cw), bs in words.items()
                          if s == stage)
            for cw, bs in here:
                if bs[0]["scheme"] == "memory_secded":
                    info = _apply_secded(state, bs, protection)
                    codewords.append(dict(info, codeword_id=cw, stage_id=stage,
                                          scheme="memory_secded"))
            out = list(exchanged_dif_stage(state, stage, phi).values)
            for cw, bs in here:
                scheme = bs[0]["scheme"]
                if scheme == "arithmetic_643":
                    info = _apply_arith(state, out, stage, cw, bs,
                                        protection, phi)
                elif scheme == "tmr3":
                    info = _apply_tmr(out, bs, protection)
                else:
                    continue
                codewords.append(dict(info, codeword_id=cw, stage_id=stage,
                                      scheme=scheme))
            state = out
        output = bit_reverse_order(state)
    for cw in codewords:
        bs = words[(cw["stage_id"], cw["codeword_id"])]
        cw.update(event_id=event["event_id"], instance=bs[0]["instance"],
                  n_bits=len(bs), bit_ids=[b["bit_id"] for b in bs])

    dev = max((max(abs(a.real - b.real), abs(a.imag - b.imag))
               for a, b in zip(output, gold_out)), default=0)
    match = dev == 0
    detected = any(c["detected"] for c in codewords)
    any_due = any(c["uncorrectable"] for c in codewords)
    any_corr = any(c["corrected"] for c in codewords)
    if not mapped:
        mapped_outcome = "NO_FAULT"
    elif not match:
        mapped_outcome = "DUE" if (detected and any_due) else "SDC"
    elif any_due:
        mapped_outcome = "DUE"
    elif any_corr:
        mapped_outcome = "CORRECTED"
    else:
        mapped_outcome = "MASKED"
    outcome = mapped_outcome
    if event["n_unmapped"] and mapped_outcome in ("NO_FAULT", "MASKED",
                                                  "CORRECTED"):
        outcome = "UNMAPPED"
    return {
        "event_id": event["event_id"],
        "protection": protection,
        "outcome": outcome,
        "mapped_outcome": mapped_outcome,
        "output_match": match,
        "max_output_deviation": int(dev),
        "n_bits": event["n_bits"],
        "n_mapped": event["n_mapped"],
        "n_unmapped": event["n_unmapped"],
        "mapping_rate": event["mapping_rate"],
        "unmapped_reasons": sorted({b["unmapped_reason"] for b in event["bits"]
                                    if not b["mapped"]}),
        "codewords": codewords,
        "event": event,
    }


def summarize(results):
    """Campaign counts; UNMAPPED is its own class, never CORRECTED."""
    counts = {k: 0 for k in OUTCOME_ORDER}
    mapped_counts = {k: 0 for k in OUTCOME_ORDER if k != "UNMAPPED"}
    n_bits = n_mapped = 0
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        mapped_counts[r["mapped_outcome"]] += 1
        n_bits += r["n_bits"]
        n_mapped += r["n_mapped"]
    return {
        "n_events": len(results),
        "outcomes": counts,
        # same events, classified on their mapped bits only
        "mapped_outcomes": mapped_counts,
        "n_bits": n_bits,
        "n_bits_mapped": n_mapped,
        "n_bits_unmapped": n_bits - n_mapped,
        "mapping_rate": (n_mapped / n_bits) if n_bits else None,
    }


def replay_events(lines, protection="on", golden=None):
    """Replay events.jsonl-style dicts ({event_id, seed, flipped})."""
    golden = golden or ensure_golden()
    results = [replay_event(line, protection=protection, golden=golden)
               for line in lines]
    return results, summarize(results)


def compare_protection(lines, golden=None):
    """Unprotected vs protected from ONE fault list (events built once)."""
    golden = golden or ensure_golden()
    events = [_event_from(line, None, 0) for line in lines]
    out = {}
    for prot in ("off", "on"):
        res = [replay_event(e, protection=prot, golden=golden)
               for e in events]
        out[prot] = {"summary": summarize(res), "results": res}
    out["fault_list"] = events
    return out

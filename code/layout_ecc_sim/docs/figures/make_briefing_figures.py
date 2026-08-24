"""Draw the three briefing figures for 平台讲解.pdf (Pillow, no matplotlib)."""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BD = r"C:\Windows\Fonts\msyhbd.ttc"

BG = (250, 251, 252)
INK = (28, 40, 51)
MUTED = (90, 98, 108)
BLUE = (27, 79, 114)
BLUE_FILL = (232, 241, 248)
ORANGE = (160, 64, 0)
ORANGE_FILL = (253, 242, 233)
GREEN = (20, 90, 50)
GREEN_FILL = (232, 245, 233)
GRAY = (127, 140, 141)
GRAY_FILL = (244, 244, 244)
RED = (146, 43, 33)
LINE = (44, 62, 80)
WHITE = (255, 255, 255)


def font(size, bold=False):
    path = FONT_BD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size, index=0)
    except OSError:
        return ImageFont.truetype(FONT_REG, size, index=0)


def rounded(draw, xy, fill, outline, width=2, radius=14):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def dashed_rounded(draw, xy, outline, width=2, radius=14, fill=GRAY_FILL, dash=10, gap=7):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=None)
    # approximate dashes on the four sides (corners stay solid-ish)
    def hline(x_a, x_b, y):
        x = x_a
        while x < x_b:
            x_end = min(x + dash, x_b)
            draw.line([(x, y), (x_end, y)], fill=outline, width=width)
            x = x_end + gap

    def vline(y_a, y_b, x):
        y = y_a
        while y < y_b:
            y_end = min(y + dash, y_b)
            draw.line([(x, y), (x, y_end)], fill=outline, width=width)
            y = y_end + gap

    inset = radius
    hline(x0 + inset, x1 - inset, y0)
    hline(x0 + inset, x1 - inset, y1)
    vline(y0 + inset, y1 - inset, x0)
    vline(y0 + inset, y1 - inset, x1)


def center_text(draw, xy, text, fnt, fill=INK):
    x0, y0, x1, y1 = xy
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((x0 + x1 - tw) / 2, (y0 + y1 - th) / 2 - bbox[1]), text, font=fnt, fill=fill)


def wrap_center(draw, xy, lines, fnts, fills):
    x0, y0, x1, y1 = xy
    heights = []
    widths = []
    for line, fnt in zip(lines, fnts):
        b = draw.textbbox((0, 0), line, font=fnt)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    gap = 4
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = (y0 + y1 - total_h) / 2
    cx = (x0 + x1) / 2
    for line, fnt, fill, tw, th in zip(lines, fnts, fills, widths, heights):
        draw.text((cx - tw / 2, y), line, font=fnt, fill=fill)
        y += th + gap


def arrow_right(draw, x0, y, x1, color=LINE, w=3):
    draw.line([(x0, y), (x1 - 12, y)], fill=color, width=w)
    draw.polygon([(x1, y), (x1 - 14, y - 7), (x1 - 14, y + 7)], fill=color)


def arrow_down(draw, x, y0, y1, color=LINE, w=3):
    draw.line([(x, y0), (x, y1 - 12)], fill=color, width=w)
    draw.polygon([(x, y1), (x - 7, y1 - 14), (x + 7, y1 - 14)], fill=color)


def caption(draw, x, y, text, fnt, fill=MUTED):
    draw.text((x, y), text, font=fnt, fill=fill)


def save(img, name):
    path = os.path.join(HERE, name)
    img.save(path, "PNG", optimize=True)
    print("wrote", path)


def fig1_pipeline():
    W, H = 2000, 1180
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title_f = font(40, True)
    sub_f = font(22)
    box_title = font(24, True)
    box_body = font(18)
    tiny = font(16)
    legend_f = font(18)

    d.text((60, 36), "图 1  一条粒子打击如何走完全程", font=title_f, fill=BLUE)
    d.text(
        (60, 92),
        "计算在芯片平面上进行。三维查看器只用来显示径迹和椭圆核，不参与分类。",
        font=sub_f,
        fill=MUTED,
    )

    boxes = [
        ("P1 布局", "primitive_map.csv", "24446 Site · xc7vx690t", BLUE, BLUE_FILL),
        ("WP1 标签", "stage / role / replica", "层次名 → FFT 架构", BLUE, BLUE_FILL),
        ("打击核", "WP8 锚定 + WP9 图案", "椭圆 ∩ (Site × 域)", BLUE, BLUE_FILL),
        ("域翻转", "CFG / FF / BRAM / DSP", "同平面逻辑叠加，非立体层", BLUE, BLUE_FILL),
        ("WP3 翻译", "功能故障记录", "接入 WP5 码字、WP1 级", BLUE, BLUE_FILL),
        ("WP2 分类", "注入黄金帧", "接入 WP6 生命周期", BLUE, BLUE_FILL),
        ("结局", "CORRECTED / DUE", "SDC / MASKED", GREEN, GREEN_FILL),
    ]

    n = len(boxes)
    margin_x = 50
    gap = 18
    bw = (W - 2 * margin_x - gap * (n - 1)) / n
    bh = 168
    y = 180
    xs = []
    for i, (t, a, b, outline, fill) in enumerate(boxes):
        x0 = margin_x + i * (bw + gap)
        x1 = x0 + bw
        y0, y1 = y, y + bh
        xs.append((x0, x1))
        rounded(d, (x0, y0, x1, y1), fill, outline, width=3, radius=16)
        wrap_center(
            d,
            (x0 + 8, y0 + 10, x1 - 8, y1 - 8),
            [t, a, b],
            [box_title, box_body, tiny],
            [outline, INK, MUTED],
        )

    for i in range(n - 1):
        x_end_prev = xs[i][1]
        x_start_next = xs[i + 1][0]
        arrow_right(d, x_end_prev + 2, y + bh / 2, x_start_next - 2)

    # annotation row
    note_y = y + bh + 36
    notes = [
        (xs[0][0], "输入：Vivado 2018.3\nOOC 布线 DCP 导出\n不改冻结 experiments/"),
        (xs[2][0], "默认仍是 legacy_linear\n+ bernoulli，保证旧数据\n可回归"),
        (xs[4][0], "CFG / twiddle LUT 锥\n仍为 proxy；算术路径\n已升 inferred"),
        (xs[6][0], "分类器看的是 ECC 结局\n不是软错误率 FIT"),
    ]
    for x, text in notes:
        d.text((x, note_y), text, font=tiny, fill=MUTED)

    # missing pieces bar
    bar_y0 = 620
    d.text((60, bar_y0), "这条链上还没接上的两块（虚线）", font=box_title, fill=ORANGE)

    miss = [
        ((80, 680, 620, 860), "WP7 统计设施  ·  未启动",
         "run_id 目录、Wilson 置信区间、网格扫描\nP(class | strike, LET, θ) 条件概率曲面\n手册把它排在 WP8/WP9 之后，至今未做"),
        ((680, 680, 1220, 860), "L3 符号感知布局  ·  未启动",
         "用 pblock 拉开同一码字的异符号\n目标：把 η 从默认布局的 <1 做到 >1\n需要新的 Vivado 实现授权"),
        ((1280, 680, 1920, 860), "M9 翻转概率标定  ·  未接线",
         "Weibull σ 已落盘（WP10）\ndomains.py 的 P_DEFAULT 仍是拍的常数\n建议式：P ≈ 1−exp(−bits·σ / A)"),
    ]
    for xy, head, body in miss:
        dashed_rounded(d, xy, GRAY, width=3, radius=16, fill=GRAY_FILL)
        d.text((xy[0] + 24, xy[1] + 18), head, font=box_title, fill=ORANGE)
        d.text((xy[0] + 24, xy[1] + 62), body, font=box_body, fill=INK)

    # legend
    ly = 920
    rounded(d, (80, ly, 220, ly + 44), BLUE_FILL, BLUE, width=2, radius=8)
    center_text(d, (80, ly, 220, ly + 44), "已完成", legend_f, BLUE)
    dashed_rounded(d, (250, ly, 390, ly + 44), GRAY, width=2, radius=8, fill=GRAY_FILL)
    center_text(d, (250, ly, 390, ly + 44), "未完成", legend_f, GRAY)
    rounded(d, (420, ly, 560, ly + 44), GREEN_FILL, GREEN, width=2, radius=8)
    center_text(d, (420, ly, 560, ly + 44), "平台产出", legend_f, GREEN)
    d.text(
        (590, ly + 8),
        "数字不回流当前 TCAS 稿件。Yosys 资源表与本 DCP 不得混用。",
        font=sub_f,
        fill=MUTED,
    )

    d.text(
        (60, 1100),
        "来源：第一阶段执行手册 WP1–WP6、WP8–WP10；查看器 python -m layout_ecc → 127.0.0.1:8610",
        font=tiny,
        fill=MUTED,
    )
    save(img, "fig1_pipeline.png")


def fig2_dependency():
    W, H = 2000, 1280
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title_f = font(40, True)
    sub_f = font(22)
    ht = font(22, True)
    bd = font(17)
    tiny = font(15)

    d.text((60, 32), "图 2  工作包依赖：先修语义，再上统计", font=title_f, fill=BLUE)
    d.text(
        (60, 88),
        "排序逻辑：在占位语义上跑 10⁵ 样本只是精确的垃圾。WP8/WP9 插在 WP7 之前，就是为了先把核修对。",
        font=sub_f,
        fill=MUTED,
    )

    def box(xy, title, body, kind="done"):
        if kind == "done":
            rounded(d, xy, BLUE_FILL, BLUE, width=3, radius=14)
            tc, bc = BLUE, INK
        elif kind == "out":
            rounded(d, xy, GREEN_FILL, GREEN, width=3, radius=14)
            tc, bc = GREEN, INK
        elif kind == "data":
            rounded(d, xy, ORANGE_FILL, ORANGE, width=3, radius=14)
            tc, bc = ORANGE, INK
        else:
            dashed_rounded(d, xy, GRAY, width=3, radius=14, fill=GRAY_FILL)
            tc, bc = GRAY, INK
        d.text((xy[0] + 16, xy[1] + 12), title, font=ht, fill=tc)
        d.text((xy[0] + 16, xy[1] + 48), body, font=bd, fill=bc)

    def link(a, b, y=None, x=None):
        if y is not None:
            arrow_right(d, a, y, b)
        else:
            arrow_down(d, x, a, b)

    # row 0 input
    box((80, 160, 420, 270), "输入：P1 布局 CSV", "Vivado 2018.3 OOC · 不新跑实现", "done")

    # row 1 WP1
    box((80, 330, 420, 440), "WP1  stage / role 标签", "unknown 0.02% · 共享 Site 2.5%", "done")
    arrow_down(d, 250, 270, 330)

    # row 2: WP4 WP5 WP2/WP6
    box((80, 510, 420, 640), "WP4  纯几何", "AABB / 邻接 / 质心伪影", "done")
    box((500, 510, 840, 640), "WP5  码字真实化", "算术/SECDED/TMR · 92.6% inferred", "done")
    box((920, 510, 1260, 640), "WP2  注入 + 分类", "黄金帧 SHA-256 已冻结", "done")
    box((1340, 510, 1680, 640), "WP6  生命周期", "cycle → (frame, sample)", "done")
    arrow_down(d, 250, 440, 510)
    arrow_right(d, 420, 385, 670)
    arrow_down(d, 670, 440, 510)
    arrow_right(d, 840, 575, 920)
    arrow_right(d, 1260, 575, 1340)

    # WP1 also to WP2 conceptually - skip extra arrows to avoid spaghetti
    d.text((430, 360), "标签喂给几何 / 码字 / 翻译", font=tiny, fill=MUTED)

    # row 3 WP3
    box((500, 710, 840, 840), "WP3  打击→功能翻译", "闭环：打击 → 翻译 → 注入 → 结局", "done")
    arrow_down(d, 250, 640, 760)
    arrow_right(d, 420, 760, 500)
    arrow_down(d, 670, 640, 710)
    arrow_down(d, 1090, 640, 760)
    arrow_left_y = 760
    # from WP2 down-left to WP3
    d.line([(1090, 760), (840, 760)], fill=LINE, width=3)
    d.polygon([(840, 760), (854, 753), (854, 767)], fill=LINE)

    # row 4 kernel
    box((80, 910, 420, 1040), "WP8  核尺寸锚定", "Radaelli α=0.70 · 默认仍 legacy", "done")
    box((500, 910, 840, 1040), "WP9  MBU 图案", "P(k=1)=0.70 · 粒度教训", "done")
    box((920, 910, 1260, 1040), "WP10  σ 材料", "Lee 2014 重离子 + UG116 中子", "data")
    arrow_down(d, 670, 840, 910)
    arrow_right(d, 420, 975, 500)

    # missing row
    box((1340, 710, 1920, 840), "WP7  统计  ·  未启动", "Wilson CI · 网格扫 LET/A\n中心必须均匀，勿钉质心", "miss")
    box((1340, 910, 1920, 1040), "M9  P_DEFAULT  ·  未接线", "σ 数据已齐，翻转概率未替换", "miss")
    box((1340, 160, 1920, 300), "L3  符号感知布局  ·  未启动", "需 Vivado 授权\n同一打击清单回放依赖 WP7+L3", "miss")

    d.text((500, 860), "核模型修好之后，才轮到 WP7", font=tiny, fill=ORANGE)
    d.text((1280, 385), "布局变体是另一条支路，不阻塞认识建设", font=tiny, fill=MUTED)

    d.text(
        (60, 1100),
        "实心蓝 = 已验收。橙 = 数据已落盘但未驱动仿真。虚线灰 = 未启动。WP 编号不是时间顺序：WP8–WP10 插在 WP7 之前。",
        font=bd,
        fill=MUTED,
    )
    d.text(
        (60, 1140),
        "单测节点：WP1–WP3 结束 32 passed → WP4–WP6 结束 51 passed → WP8–WP9 结束 65 passed。",
        font=bd,
        fill=MUTED,
    )
    save(img, "fig2_dependency.png")


def fig3_gaps():
    W, H = 2000, 1180
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title_f = font(40, True)
    sub_f = font(22)
    col_t = font(26, True)
    item_t = font(20, True)
    item_b = font(17)
    tiny = font(16)

    d.text((60, 32), "图 3  还差什么：按能不能立刻做来排，不按 WP 编号", font=title_f, fill=BLUE)
    d.text(
        (60, 88),
        "讲解稿写完即停。下一步由作者指定，不在这份文档里替你开工。",
        font=sub_f,
        fill=MUTED,
    )

    cols = [
        (60, GREEN, GREEN_FILL, "现在就能做", "不需要新 Vivado，现有 CSV / JSON 够用"),
        (700, ORANGE, ORANGE_FILL, "数据已齐，代码未接", "材料在磁盘上，仿真默认值还没换"),
        (1340, GRAY, GRAY_FILL, "需授权 或 明确暂缓", "缺实现、缺 bitstream、或缺环境谱接线"),
    ]

    for x, outline, fill, head, sub in cols:
        rounded(d, (x, 150, x + 600, 230), fill, outline, width=3, radius=14)
        d.text((x + 24, 162), head, font=col_t, fill=outline)
        d.text((x + 24, 198), sub, font=tiny, fill=MUTED)

    left_items = [
        ("L0 的 η（每级每符号）", "纯几何：同码字异符号 Site 的最小间距\n除以锚定核直径。证伪条件：η ≥ 1。"),
        ("WP7 统计骨架", "run_id、Wilson CI、网格扫描。网格扫\nanchored 的 LET/A，中心均匀占用采样。"),
        ("跨级 vs 同码字多符号分开统计", "WP4 已证明这两件事不是一回事。\nWP7 若混在一个率里，会重复质心伪影。"),
    ]
    mid_items = [
        ("M9：替换 P_DEFAULT", "Lee 2014 Weibull 已在\nweibull_7series_measured.json。"),
        ("建议换算（未落地）", "P_d(LET) ≈ 1 − exp(−bits_d · σ_d / A)\n落地前必须与手册 M9 对齐。"),
        ("粒子体系必须先选定", "GCR 重离子走 Lee；大气中子走 UG116。\n混用会把率算错约 3 个数量级。"),
    ]
    right_items = [
        ("L3 pblock + L0 vs L3 回放", "需 Vivado 授权。回放依赖 WP7 + L3。\n这是主命题 P2–P6 的实验。"),
        ("CFG essential bits", "需 bitstream / SEM。没有它，CFG\n翻转语义只能继续标 proxy。"),
        ("暂缓：SET、质子 σ(E)、\n中子等效 FIT、orbit_seu 率对接", "手册已声明排除或 PENDING。\n不是当前认识瓶颈。"),
    ]

    def draw_items(x0, items, outline):
        y = 260
        for title, body in items:
            h = 230
            rounded(d, (x0, y, x0 + 600, y + h), WHITE, outline, width=2, radius=12)
            d.text((x0 + 22, y + 18), title, font=item_t, fill=outline)
            d.text((x0 + 22, y + 64), body, font=item_b, fill=INK)
            y += h + 18

    draw_items(60, left_items, GREEN)
    draw_items(700, mid_items, ORANGE)
    draw_items(1340, right_items, GRAY)

    save(img, "fig3_gaps.png")


if __name__ == "__main__":
    fig1_pipeline()
    fig2_dependency()
    fig3_gaps()

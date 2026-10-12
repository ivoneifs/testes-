"""Vídeo de apresentação do NeuroScore — animação quadro a quadro (Pillow).
Uso: python render.py <pasta>   (lê roteiro.json e timing.json; grava frames/00001.jpg…)
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 24
D = sys.argv[1] if len(sys.argv) > 1 else '.'
SEGS = json.load(open(f'{D}/roteiro.json'))
TIM = json.load(open(f'{D}/timing.json'))          # [{"start":s,"dur":s}]
OUT = f'{D}/frames'; os.makedirs(OUT, exist_ok=True)

BG = (7, 10, 23); INK = (238, 241, 255); INK2 = (183, 191, 220); MUTED = (128, 137, 171)
P1 = (124, 92, 255); P2 = (0, 224, 255); ACC = (255, 122, 61); OK = (46, 229, 157); RED = (255, 107, 138)
CARD = (20, 26, 52); LINE = (44, 52, 86)


def font(name, size, weight='Bold'):
    f = ImageFont.truetype(f'{D}/fonts/{name}.ttf', size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


FT = {k: font('SpaceGrotesk', s) for k, s in (('h0', 74), ('h1', 58), ('h2', 40), ('h3', 30))}
FI = {k: font('Inter', s, w) for k, s, w in (('b', 24, 'SemiBold'), ('r', 22, 'Regular'), ('s', 18, 'Medium'),
                                             ('cap', 27, 'SemiBold'), ('big', 44, 'Bold'), ('xs', 15, 'Medium'))}


def ease(x):  # easeOutCubic
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def lerp(a, b, t): return a + (b - a) * t


def mix(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def grad_img(w, h, c1=P1, c2=P2, horizontal=True):
    g = Image.new('RGB', (w, h))
    px = g.load()
    for x in range(w):
        for y in range(h):
            t = (x / max(1, w - 1)) * .75 + (y / max(1, h - 1)) * .25 if horizontal else y / max(1, h - 1)
            px[x, y] = mix(c1, c2, t)
    return g


# ---------- fundo (pré-calculado; desliza devagar) ----------
def make_bg():
    bw, bh = W + 200, H + 140
    bg = Image.new('RGB', (bw, bh), BG)
    glow = Image.new('RGB', (bw, bh), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (cx, cy, r, c) in ((260, 160, 380, (70, 50, 170)), (1150, 120, 320, (0, 90, 120)), (900, 700, 420, (60, 40, 150))):
        gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    bg = Image.blend(bg, glow, .55)
    d = ImageDraw.Draw(bg)
    for x in range(0, bw, 56):
        d.line((x, 0, x, bh), fill=(16, 21, 42))
    for y in range(0, bh, 56):
        d.line((0, y, bw, y), fill=(16, 21, 42))
    return bg


BGIMG = make_bg()
GRAD_BAR = grad_img(64, 8)


def rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def text_c(d, y, s, f, fill=INK):
    w = d.textlength(s, font=f); d.text(((W - w) / 2, y), s, font=f, fill=fill)


def paste_grad_text(img, xy, s, f, alpha=1.0):
    """Texto com gradiente roxo→ciano."""
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).text(xy, s, font=f, fill=int(255 * alpha))
    bbox = mask.getbbox()
    if not bbox: return
    g = grad_img(bbox[2] - bbox[0], bbox[3] - bbox[1]).resize((bbox[2] - bbox[0], bbox[3] - bbox[1]))
    img.paste(g, bbox[:2], mask.crop(bbox))


def wrap(d, s, f, maxw):
    out, cur = [], ''
    for w in s.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out


def layer():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def fade_paste(img, lay, a):
    if a <= 0: return
    if a < 1:
        al = lay.getchannel('A').point(lambda v: int(v * a)); lay.putalpha(al)
    img.alpha_composite(lay)


def logo(d, x, y, s=1.0, alpha=255, img=None):
    sz = int(44 * s)
    box = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    g = grad_img(sz, sz).convert('RGBA')
    m = Image.new('L', (sz, sz), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, sz - 1, sz - 1), radius=int(13 * s), fill=alpha)
    box.paste(g, (0, 0), m)
    bd = ImageDraw.Draw(box); f = font('SpaceGrotesk', int(19 * s))
    tw = bd.textlength('NS', font=f); bd.text(((sz - tw) / 2, sz * .2), 'NS', font=f, fill=(255, 255, 255, alpha))
    img.alpha_composite(box, (int(x), int(y)))
    d.text((x + sz + 12 * s, y + sz * .12), 'NeuroScore', font=font('SpaceGrotesk', int(28 * s)), fill=INK + (alpha,))


def caption(img, s, a):
    if a <= 0: return
    lay = layer(); d = ImageDraw.Draw(lay)
    lines = wrap(d, s, FI['cap'], 1040)
    lh = 36; h = lh * len(lines) + 26; y0 = H - h - 26
    w = max(d.textlength(l, font=FI['cap']) for l in lines) + 48
    rr(d, ((W - w) / 2, y0, (W + w) / 2, y0 + h), 16, fill=(4, 6, 16, 205))
    for i, l in enumerate(lines):
        tw = d.textlength(l, font=FI['cap']); d.text(((W - tw) / 2, y0 + 13 + i * lh), l, font=FI['cap'], fill=INK)
    fade_paste(img, lay, a)


def card(d, box, r=18):
    rr(d, box, r, fill=CARD + (235,), outline=LINE + (255,), width=1)


# ---------- cenas ----------
def sc_hook(img, t, dur):
    d = ImageDraw.Draw(img)
    a1, a2 = ease(t / .8), ease((t - 2.4) / .8)
    lay = layer(); ld = ImageDraw.Draw(lay)
    y = 190 - 30 * (1 - a1)
    text_c(ld, y, 'Você estudou para', FT['h1'], INK)
    fade_paste(img, lay, a1)
    lay = layer(); ld = ImageDraw.Draw(lay)
    w = ld.textlength('entender pessoas.', font=FT['h0'])
    paste_grad_text(lay, ((W - w) / 2, 262 - 30 * (1 - a1)), 'entender pessoas.', FT['h0'])
    fade_paste(img, lay, a1)
    if t > 2.4:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 380 + 20 * (1 - a2), 'Não para passar a noite', FT['h2'], INK2)
        s = 'convertendo tabelas e escrevendo laudos.'
        tw = ld.textlength(s, font=FT['h2']); x0 = (W - tw) / 2; yy = 432 + 20 * (1 - a2)
        ld.text((x0, yy), s, font=FT['h2'], fill=RED)
        k = ease((t - 3.6) / 1.0)
        if k > 0: ld.line((x0 - 6, yy + 26, x0 - 6 + (tw + 12) * k, yy + 22), fill=RED, width=5)
        fade_paste(img, lay, a2)
    # relógio no canto
    hh = 23; mm = 47 + int(t * 2.2)
    d.text((W - 190, 40), f'{hh}:{mm % 60:02d}', font=FI['b'], fill=MUTED)


CHIPS = ['WISC-IV', 'WAIS-III', 'RAVLT', 'FDT', 'ETDAH-2', 'SNAP-IV', 'BRIEF-2', 'Vineland-3', 'Perfil Sensorial 2',
         'SRS-2', 'CBCL', 'Stroop', 'Trilhas', 'Torre de Londres', 'd2-R', 'TDE-II']


def sc_intro(img, t, dur):
    s = ease(t / .9)
    lay = layer(); ld = ImageDraw.Draw(lay)
    logo(ld, W / 2 - 150 * (0.6 + .4 * s) * 1.6 / 1.6 - 60, 150, 1.6 * (0.6 + .4 * s), img=lay)
    fade_paste(img, lay, s)
    lay = layer(); ld = ImageDraw.Draw(lay)
    text_c(ld, 255, 'Plataforma clínica de neuropsicologia', FI['b'], INK2)
    fade_paste(img, lay, ease((t - .5) / .8))
    n = int(71 * ease((t - 1.2) / 2.2))
    if t > 1.2:
        lay = layer(); ld = ImageDraw.Draw(lay)
        s1 = f'{n}'; s2 = ' instrumentos corrigidos pelas normas'
        w1 = ld.textlength(s1, font=FT['h0']); w2 = ld.textlength(s2, font=FT['h2'])
        x0 = (W - w1 - w2) / 2
        paste_grad_text(lay, (x0, 312), s1, FT['h0'])
        ld.text((x0 + w1, 336), s2, font=FT['h2'], fill=INK)
        fade_paste(img, lay, ease((t - 1.2) / .6))
    # chips aparecendo
    lay = layer(); ld = ImageDraw.Draw(lay)
    x, y = 120, 430
    for i, c in enumerate(CHIPS):
        a = ease((t - 2.4 - i * .18) / .4)
        if a <= 0: break
        w = ld.textlength(c, font=FI['s']) + 30
        if x + w > W - 120: x = 120; y += 50
        rr(ld, (x, y + 10 * (1 - a), x + w, y + 38 + 10 * (1 - a)), 19, fill=(26, 32, 62, int(240 * a)), outline=(70, 80, 130, int(255 * a)))
        ld.text((x + 15, y + 8 + 10 * (1 - a)), c, font=FI['s'], fill=INK2 + (int(255 * a),))
        x += w + 10
    img.alpha_composite(lay)


def doc_page(ld, box, lines, prog, title=None, typing=True):
    x0, y0, x1, y1 = box
    rr(ld, box, 12, fill=(247, 248, 252, 255))
    y = y0 + 24
    if title:
        tf = font('Inter', 17, 'Bold'); ld.text((x0 + 26, y), title, font=tf, fill=(27, 32, 51)); y += 38
    total = len(lines)
    for i, (kind, w) in enumerate(lines):
        p = max(0.0, min(1.0, prog * total - i)) if typing else 1.0
        if p <= 0: break
        if kind == 'h':
            ld.rounded_rectangle((x0 + 26, y, x0 + 26 + (x1 - x0 - 52) * .35 * p, y + 11), 5, fill=(110, 96, 220)); y += 26
        else:
            ld.rounded_rectangle((x0 + 26, y, x0 + 26 + (x1 - x0 - 52) * w * p, y + 9), 4, fill=(208, 212, 230)); y += 21


def sc_ocr(img, t, dur):
    lay = layer(); ld = ImageDraw.Draw(lay)
    a = ease(t / .7)
    # documento à esquerda (a "foto" da anamnese)
    bx = (130, 120 + 20 * (1 - a), 530, 560 + 20 * (1 - a))
    doc_page(ld, bx, [('h', 0), ('l', .9), ('l', .8), ('l', .95), ('l', .6), ('h', 0), ('l', .85), ('l', .9), ('l', .7), ('l', .8), ('h', 0), ('l', .92), ('l', .55)],
             1.0, 'ANAMNESE', typing=False)
    fade_paste(img, lay, a)
    # barra de leitura
    if 0.6 < t < dur - .4:
        lay = layer(); ld = ImageDraw.Draw(lay)
        yy = 140 + ((t - .6) * 220) % 400
        for k in range(26):
            al = int(120 * (1 - k / 26))
            ld.line((130, yy - k, 530, yy - k), fill=P2 + (al,))
        ld.line((130, yy, 530, yy), fill=P2 + (255,), width=3)
        img.alpha_composite(lay)
    # seta + cartão da História de Vida
    lay = layer(); ld = ImageDraw.Draw(lay)
    b = ease((t - 1.6) / .7)
    ld.text((575, 300), '→', font=FT['h1'], fill=P2)
    card(ld, (670, 140, 1150, 540))
    ld.text((700, 165), 'História de Vida', font=FI['b'], fill=INK)
    rr(ld, (1000, 166, 1124, 196), 15, fill=(18, 70, 60, 255)); ld.text((1016, 170), 'OCR ✓', font=FI['s'], fill=OK)
    topics = ['História da doença atual', 'Período gestacional', 'Desenvolvimento global', 'Alimentação e sono', 'Histórico escolar']
    for i, tp in enumerate(topics):
        k = ease((t - 2.2 - i * .7) / .6)
        if k <= 0: break
        y = 218 + i * 62
        ld.text((700, y), tp, font=FI['s'], fill=INK2 + (int(255 * k),))
        ld.rounded_rectangle((700, y + 28, 700 + 410 * k, y + 37), 4, fill=(60, 70, 120, 255))
    fade_paste(img, lay, b)


def sc_score(img, t, dur):
    lay = layer(); ld = ImageDraw.Draw(lay)
    a = ease(t / .6)
    card(ld, (110, 120, 600, 560))
    ld.text((138, 142), 'Vineland-3 · item a item', font=FI['b'], fill=INK)
    vals = [2, 2, 2, 2, 1, 2, 1, 1, 0, 1, 0, 0, 0, 0]
    for i, v in enumerate(vals):
        col, row = i % 2, i // 2
        x, y = 138 + col * 230, 196 + row * 50
        on = t > .5 + i * .22
        ld.text((x, y + 8), f'{18 + i:>2}', font=FI['s'], fill=MUTED)
        for k, opt in enumerate((2, 1, 0)):
            bx = (x + 46 + k * 48, y, x + 86 + k * 48, y + 38)
            sel = on and opt == v
            rr(ld, bx, 9, fill=(P1 + (255,)) if sel else (16, 21, 42, 255), outline=LINE + (255,))
            ld.text((bx[0] + 14, y + 7), str(opt), font=FI['s'], fill=(255, 255, 255) if sel else INK2)
    if t > 4.0:
        rr(ld, (138, 510, 572, 546), 10, fill=(18, 70, 60, 255))
        ld.text((154, 516), 'basal ✓ · teto ✓ · bruto = 50', font=FI['s'], fill=OK)
    fade_paste(img, lay, a)
    # gráfico + KPIs
    lay = layer(); ld = ImageDraw.Draw(lay)
    b = ease((t - 2.0) / .6)
    card(ld, (660, 120, 1170, 560))
    ld.text((690, 142), 'WISC-IV · índices', font=FI['b'], fill=INK)
    kp = [('ICV', 110), ('IOP', 106), ('IMO', 94), ('IVP', 103)]
    for i, (k, v) in enumerate(kp):
        x = 690 + i * 118
        rr(ld, (x, 186, x + 104, 252), 12, fill=(16, 21, 42, 255), outline=LINE + (255,))
        ld.text((x + 12, 192), k, font=FI['xs'], fill=MUTED)
        ld.text((x + 12, 210), str(int(v * ease((t - 2.4) / 1.2))), font=font('SpaceGrotesk', 30), fill=INK)
    hs = [.62, .78, .55, .86, .7, .92, .66]
    for i, hgt in enumerate(hs):
        g = ease((t - 2.6 - i * .12) / .9)
        x = 700 + i * 64; top = 520 - 230 * hgt * g
        if g > 0:
            bar = grad_img(40, max(2, int(520 - top)), P2, P1, horizontal=False).convert('RGBA')
            m = Image.new('L', bar.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, 39, bar.size[1] - 1), radius=7, fill=255)
            lay.paste(bar, (int(x), int(top)), m)
    if t > 4.6:
        rr(ld, (1020, 140, 1146, 172), 16, fill=(18, 70, 60, 255)); ld.text((1036, 145), 'QIT 105', font=FI['s'], fill=OK)
    fade_paste(img, lay, b)


def sc_laudo(img, t, dur):
    lay = layer(); ld = ImageDraw.Draw(lay)
    a = ease(t / .6)
    doc_page(ld, (300, 80 - 10 * (1 - a), 860, 556),
             [('h', 0), ('l', .7), ('l', .5), ('h', 0), ('l', .95), ('l', .9), ('l', .85), ('l', .92), ('h', 0), ('l', .88), ('l', .93), ('l', .7),
              ('h', 0), ('l', .9), ('l', .8), ('l', .6)], ease((t - .5) / 5.5), 'LAUDO NEUROPSICOLÓGICO')
    fade_paste(img, lay, a)
    lay = layer(); ld = ImageDraw.Draw(lay)
    items = [('Escrito no seu modelo', 1.2), ('Tabelas e gráficos', 2.4), ('Você revisa e assina', 3.6)]
    for i, (s, t0) in enumerate(items):
        k = ease((t - t0) / .5)
        if k <= 0: continue
        y = 170 + i * 80
        rr(ld, (900 + 20 * (1 - k), y, 1200, y + 56), 14, fill=(20, 26, 52, int(240 * k)), outline=(70, 80, 130, int(255 * k)))
        ld.text((920 + 20 * (1 - k), y + 14), s, font=FI['s'], fill=INK + (int(255 * k),))
    for i, (s, col) in enumerate((('Word', P1), ('PDF', ACC))):
        k = ease((t - 5.6 - i * .3) / .5)
        if k <= 0: continue
        x = 920 + i * 140
        rr(ld, (x, 440, x + 120, 500), 14, fill=col + (int(255 * k),))
        ld.text((x + 28, 455), s, font=FI['b'], fill=(255, 255, 255, int(255 * k)))
    img.alpha_composite(lay)
    if t > 7.0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        k = ease((t - 7.0) / .5)
        ld.text((80, 300), '✓', font=font('Inter', 120, 'Bold'), fill=OK)
        ld.text((70, 440), 'Pronto para', font=FI['b'], fill=INK)
        ld.text((70, 470), 'a devolutiva', font=FI['b'], fill=INK)
        fade_paste(img, lay, k)


def sc_price(img, t, dur):
    lay = layer(); ld = ImageDraw.Draw(lay)
    a = ease(t / .7)
    s = 'Sem mensalidade.'
    w = ld.textlength(s, font=FT['h0'])
    paste_grad_text(lay, ((W - w) / 2, 140 - 20 * (1 - a)), s, FT['h0'])
    text_c(ld, 238, 'Você paga só pelo que usar.', FT['h2'], INK)
    fade_paste(img, lay, a)
    lay = layer(); ld = ImageDraw.Draw(lay)
    cards = [('1 crédito', 'por teste, laudo ou\nHistória de Vida'), ('14 dias', 'de acesso grátis\napós a aprovação'), ('3 créditos', 'de boas-vindas\npara começar')]
    for i, (h, sub) in enumerate(cards):
        k = ease((t - 2.0 - i * .5) / .6)
        if k <= 0: continue
        x = 150 + i * 340; y = 330 + 30 * (1 - k)
        rr(ld, (x, y, x + 300, y + 190), 22, fill=(20, 26, 52, int(240 * k)), outline=(110, 90, 240, int(255 * k)), width=2)
        f = font('SpaceGrotesk', 46); tw = ld.textlength(h, font=f)
        ld.text((x + (300 - tw) / 2, y + 28), h, font=f, fill=INK + (int(255 * k),))
        for j, l in enumerate(sub.split('\n')):
            tw = ld.textlength(l, font=FI['r']); ld.text((x + (300 - tw) / 2, y + 100 + j * 30), l, font=FI['r'], fill=INK2 + (int(255 * k),))
    img.alpha_composite(lay)


def sc_end(img, t, dur):
    lay = layer(); ld = ImageDraw.Draw(lay)
    a = ease(t / .8)
    logo(ld, W / 2 - 150, 150, 1.8, img=lay)
    s = 'Do protocolo ao laudo, em minutos.'
    w = ld.textlength(s, font=FT['h1'])
    paste_grad_text(lay, ((W - w) / 2, 275), s, FT['h1'])
    rr(ld, (W / 2 - 300, 380, W / 2 + 300, 446), 18, fill=ACC + (255,))
    text_c(ld, 395, 'Teste grátis: neuro-testes.appsbrasil.store/page', FI['s'], (255, 255, 255))
    text_c(ld, 470, 'WhatsApp (74) 98825-9925', FI['b'], OK)
    fade_paste(img, lay, a)


SCENES = [sc_hook, sc_intro, sc_ocr, sc_score, sc_laudo, sc_price, sc_end]


def render():
    total = TIM[-1]['start'] + TIM[-1]['dur']
    n = int(total * FPS)
    for f in range(n):
        tt = f / FPS
        i = max(k for k in range(len(TIM)) if TIM[k]['start'] <= tt + 1e-9)
        t = tt - TIM[i]['start']; dur = TIM[i]['dur']
        ox = int(100 + 80 * math.sin(tt / 9)); oy = int(70 + 50 * math.cos(tt / 11))
        img = BGIMG.crop((ox, oy, ox + W, oy + H)).convert('RGBA')
        SCENES[i](img, t, dur)
        if i > 0 and i < len(SCENES) - 1:
            d = ImageDraw.Draw(img); logo(d, 40, 30, .8, img=img)
        # transição: escurece no início/fim de cada cena
        fin = min(1, t / .35, (dur - t) / .35) if i < len(SCENES) - 1 else min(1, t / .35)
        if fin < 1:
            img = Image.blend(Image.new('RGBA', (W, H), BG + (255,)), img, max(0, fin))
        caption(img, SEGS[i], ease(t / .4) * (1 if i == len(SCENES) - 1 else min(1, (dur - t) / .3)))
        # barra de progresso do vídeo
        d = ImageDraw.Draw(img)
        d.rectangle((0, H - 4, int(W * tt / total), H), fill=P2)
        img.convert('RGB').save(f'{OUT}/{f + 1:05d}.jpg', quality=90)
        if f % 120 == 0:
            print(f'{f}/{n}', flush=True)
    print('ok', n)


if __name__ == '__main__':
    if len(sys.argv) > 2:          # prévia: python render.py <pasta> <segundo>
        tt = float(sys.argv[2])
        i = max(k for k in range(len(TIM)) if TIM[k]['start'] <= tt)
        img = BGIMG.crop((100, 70, 100 + W, 70 + H)).convert('RGBA')
        SCENES[i](img, tt - TIM[i]['start'], TIM[i]['dur'])
        caption(img, SEGS[i], 1)
        img.convert('RGB').save(f'{D}/preview_{tt:.0f}.jpg', quality=88)
    else:
        render()

# Dibujo de las cintas de Bonfim con Pillow (sin ursina: se prueba sin ventana). Una cinta es una tira vertical con
# CUATRO canales de lectura (ver backend/logica/manillas.py): color, tejido (lisa, rayada, punteada, trenzada, zigzag,
# deshilachada), nudos (3, 2, 1, 0) y desgaste (bordes mordidos y punta deshilachada, 0.0 nueva .. 1.0 a punto de romperse).
#
#   dibujar_cinta(color, patron, nudos, desgaste, ancho=64, alto=160)  -> PIL.Image RGBA (transparente fuera de la cinta)
#   dibujar_dije(simbolo, lado=48)                                      -> PIL.Image RGBA (símbolo del indicador, sin color)
#   forma_de(imagen)                                                    -> máscara L de la silueta (para probar la forma)
#
# La cinta lleva un doble contorno (crema por dentro, tinta por fuera) para leerse sobre fondo claro y oscuro (la cinta
# violeta oscura del nivel «apagado» no se pierde en un HUD de tinta). Es determinista: sin azar.

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from frontend import estilo

SS = 3                                 # supersampling (se dibuja a 4x y se reduce con LANCZOS)
CREMA = (250, 246, 232)
TINTA = tuple(estilo.TINTA)
PATRONES = ("lisa", "rayada", "punteada", "trenzada", "zigzag", "deshilachada")
SIMBOLOS = ("manos", "llave", "megafono", "sol", "rayo")


def _luminancia(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _pseudo(i):
    """Número 0..1 determinista (sin random) para el mordisco de los bordes y los hilos."""
    x = math.sin(i * 12.9898 + 78.233) * 43758.5453
    return x - math.floor(x)


def _sombrear(c, factor):
    return tuple(max(0, min(255, int(v * factor))) for v in c)


def _dilatar(mascara, grosor):
    tam = 2 * int(grosor) + 1
    return mascara.filter(ImageFilter.MaxFilter(tam)) if tam > 1 else mascara


def forma_de(imagen):
    """Máscara L (0/255) de la silueta de una imagen RGBA."""
    return imagen.getchannel("A").point(lambda v: 255 if v > 40 else 0)


def _cuerpo(W, H, desgaste):
    """Máscara del cuerpo de la cinta: tira con muesca en V al final y, con desgaste, bordes mordidos y punta de hilos."""
    x0, x1 = W * 0.24, W * 0.76
    xm = (x0 + x1) / 2
    arriba = H * 0.03
    fin = H * (0.96 - 0.08 * desgaste)
    mascara = Image.new("L", (W, H), 0)
    pincel = ImageDraw.Draw(mascara)
    if desgaste < 0.12:
        pincel.polygon([(x0, arriba), (x1, arriba), (x1, fin), (xm, fin - H * 0.07), (x0, fin)], fill=255)
    else:
        base = fin - H * 0.13
        pincel.polygon([(x0, arriba), (x1, arriba), (x1, base), (x0, base)], fill=255)
        hilos = 4 + int(round(desgaste * 6))
        ancho_hilo = (x1 - x0) / (hilos * 1.7)
        paso = (x1 - x0 - ancho_hilo) / max(1, hilos - 1)
        for k in range(hilos):
            cx = x0 + ancho_hilo / 2 + k * paso
            largo = H * (0.045 + 0.11 * (0.35 + 0.65 * _pseudo(k + 3)) * (0.4 + 0.6 * desgaste))
            ladeo = (_pseudo(k + 11) - 0.5) * W * 0.08
            pincel.line([(cx, base - 2 * SS), (cx + ladeo, base + largo)], fill=255, width=max(2, int(ancho_hilo)))
    for k in range(int(round(desgaste * 8))):                     # bordes mordidos
        y = H * (0.10 + 0.78 * _pseudo(k + 29))
        lado = x0 if k % 2 == 0 else x1
        sentido = 1 if k % 2 == 0 else -1
        r = W * (0.05 + 0.05 * desgaste)
        pincel.polygon([(lado - sentido * r * 0.6, y - r), (lado + sentido * r * 1.1, y), (lado - sentido * r * 0.6, y + r)],
                       fill=0)
    return mascara, (x0, x1, arriba, fin)


def _marcas(W, H, patron, marca, caja):
    """Capa RGBA con el tejido dibujado encima del cuerpo (se recorta con la máscara del cuerpo)."""
    x0, x1, arriba, fin = caja
    xm = (x0 + x1) / 2
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    p = ImageDraw.Draw(capa)
    tinta = (*marca, 255)
    g = 3 * SS
    if patron == "lisa":
        p.line([(x0 + (x1 - x0) * 0.22, arriba + H * 0.04), (x0 + (x1 - x0) * 0.22, fin - H * 0.10)], fill=(*marca, 120), width=g)
    elif patron == "rayada":
        y = arriba + H * 0.08
        while y < fin - H * 0.06:
            p.rectangle([x0, y, x1, y + H * 0.045], fill=tinta)
            y += H * 0.11
    elif patron == "punteada":
        fila, y = 0, arriba + H * 0.07
        while y < fin - H * 0.05:
            for cx in ((x0 + (x1 - x0) * 0.3, x0 + (x1 - x0) * 0.7) if fila % 2 == 0 else (xm,)):
                r = W * 0.055
                p.ellipse([cx - r, y - r, cx + r, y + r], fill=tinta)
            fila += 1
            y += H * 0.075
    elif patron == "trenzada":
        y = arriba + H * 0.05
        while y < fin - H * 0.10:
            p.line([(x0, y), (xm, y + H * 0.05), (x1, y)], fill=tinta, width=g)
            p.line([(x0, y + H * 0.05), (xm, y + H * 0.10), (x1, y + H * 0.05)], fill=(*marca, 150), width=g)
            y += H * 0.12
    elif patron == "zigzag":
        puntos, y, lado = [], arriba + H * 0.03, 0
        while y < fin - H * 0.04:
            puntos.append((x0 + (x1 - x0) * (0.12 if lado == 0 else 0.88), y))
            y += H * 0.075
            lado = 1 - lado
        p.line(puntos, fill=tinta, width=int(g * 1.4), joint="curve")
    elif patron == "deshilachada":
        for k, (ax, ay, bx, by) in enumerate(((0.15, 0.12, 0.7, 0.2), (0.4, 0.34, 0.9, 0.28), (0.1, 0.5, 0.55, 0.58),
                                              (0.5, 0.7, 0.95, 0.66))):
            p.line([(x0 + (x1 - x0) * ax, H * ay), (x0 + (x1 - x0) * bx, H * by)], fill=(*marca, 200), width=2 * SS)
    return capa


def dibujar_cinta(color, patron, nudos, desgaste, ancho=64, alto=160):
    """Cinta vertical de `ancho` x `alto` px (RGBA). `nudos` 0..3; `desgaste` 0..1."""
    if patron not in PATRONES:
        raise ValueError(f"Tejido desconocido: {patron!r}; válidos: {PATRONES}.")
    nudos = max(0, min(3, int(nudos)))
    desgaste = max(0.0, min(1.0, float(desgaste)))
    W, H = ancho * SS, alto * SS
    cuerpo, caja = _cuerpo(W, H, desgaste)
    x0, x1, arriba, _fin = caja
    marca = TINTA if _luminancia(color) > 110 else CREMA
    relleno = Image.new("RGBA", (W, H), (*color, 255))
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lienzo.paste(relleno, (0, 0), cuerpo)
    marcas = _marcas(W, H, patron, marca, caja)
    marcas.putalpha(ImageChops.multiply(marcas.getchannel("A"), cuerpo))
    lienzo = Image.alpha_composite(lienzo, marcas)
    # Nudos: bultos redondos sobre la cinta, cada uno con su contorno (se cuentan a simple vista).
    xm, rx, ry = W / 2, W * 0.34, H * 0.055
    capa_nudos = ImageDraw.Draw(lienzo)
    for k in range(nudos):
        cy = arriba + H * (0.10 + 0.155 * k)
        caja_n = [xm - rx, cy - ry, xm + rx, cy + ry]
        capa_nudos.ellipse(caja_n, fill=(*_sombrear(color, 0.82), 255), outline=(*TINTA, 255), width=int(1.6 * SS))
        capa_nudos.ellipse([xm - rx * 0.6, cy - ry * 0.55, xm + rx * 0.1, cy - ry * 0.05], fill=(*_sombrear(color, 1.12), 255))
    # Se reduce primero y el doble contorno (crema por dentro, tinta por fuera) se dilata ya a tamaño final: es barato.
    relleno_final = lienzo.resize((ancho, alto), Image.LANCZOS)
    alfa = relleno_final.getchannel("A")
    tinta_m = alfa.filter(ImageFilter.MaxFilter(5))
    crema_m = alfa.filter(ImageFilter.MaxFilter(3))
    salida = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    salida.paste(Image.new("RGBA", (ancho, alto), (*TINTA, 255)), (0, 0), tinta_m)
    salida.paste(Image.new("RGBA", (ancho, alto), (*CREMA, 255)), (0, 0), crema_m)
    return Image.alpha_composite(salida, relleno_final)


# ---------------------------------------------------------------- dijes (identidad del indicador sin color)

def _glifo(p, simbolo, c, s):
    """Dibuja el símbolo con tinta en un cuadrado de lado `s` (coordenadas ya en SS)."""
    t = (*TINTA, 255)
    if simbolo == "manos":                       # dos anillos enlazados: gente que se une
        p.ellipse([c - s * 0.38, c - s * 0.2, c + s * 0.06, c + s * 0.24], outline=t, width=int(s * 0.1))
        p.ellipse([c - s * 0.06, c - s * 0.24, c + s * 0.38, c + s * 0.2], outline=t, width=int(s * 0.1))
    elif simbolo == "llave":
        p.ellipse([c - s * 0.34, c - s * 0.12, c - s * 0.06, c + s * 0.16], outline=t, width=int(s * 0.1))
        p.line([(c - s * 0.06, c + s * 0.02), (c + s * 0.34, c + s * 0.02)], fill=t, width=int(s * 0.1))
        p.line([(c + s * 0.22, c + s * 0.02), (c + s * 0.22, c + s * 0.18)], fill=t, width=int(s * 0.09))
        p.line([(c + s * 0.34, c + s * 0.02), (c + s * 0.34, c + s * 0.16)], fill=t, width=int(s * 0.09))
    elif simbolo == "megafono":
        p.polygon([(c - s * 0.3, c - s * 0.1), (c + s * 0.1, c - s * 0.3), (c + s * 0.1, c + s * 0.3), (c - s * 0.3, c + s * 0.1)],
                  fill=t)
        p.rectangle([c - s * 0.4, c - s * 0.1, c - s * 0.28, c + s * 0.1], fill=t)
        p.line([(c + s * 0.2, c - s * 0.16), (c + s * 0.34, c - s * 0.24)], fill=t, width=int(s * 0.07))
        p.line([(c + s * 0.22, c), (c + s * 0.38, c)], fill=t, width=int(s * 0.07))
        p.line([(c + s * 0.2, c + s * 0.16), (c + s * 0.34, c + s * 0.24)], fill=t, width=int(s * 0.07))
    elif simbolo == "sol":
        p.ellipse([c - s * 0.16, c - s * 0.16, c + s * 0.16, c + s * 0.16], fill=t)
        for k in range(8):
            a = k * math.pi / 4
            p.line([(c + s * 0.24 * math.cos(a), c + s * 0.24 * math.sin(a)),
                    (c + s * 0.38 * math.cos(a), c + s * 0.38 * math.sin(a))], fill=t, width=int(s * 0.07))
    elif simbolo == "rayo":
        p.polygon([(c + s * 0.08, c - s * 0.4), (c - s * 0.24, c + s * 0.06), (c - s * 0.02, c + s * 0.06),
                   (c - s * 0.1, c + s * 0.4), (c + s * 0.26, c - s * 0.1), (c + s * 0.02, c - s * 0.1)], fill=t)


def dibujar_dije(simbolo, lado=48):
    """Dije (medallón crema con el símbolo en tinta) de un indicador: su identidad NO depende del color."""
    if simbolo not in SIMBOLOS:
        raise ValueError(f"Símbolo desconocido: {simbolo!r}; válidos: {SIMBOLOS}.")
    S = lado * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    p = ImageDraw.Draw(img)
    p.ellipse([SS, SS, S - SS, S - SS], fill=(*CREMA, 255), outline=(*TINTA, 255), width=int(2 * SS))
    _glifo(p, simbolo, S / 2, S * 0.9)
    return img.resize((lado, lado), Image.LANCZOS)

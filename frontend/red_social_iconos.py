# Iconos y vistas previas de la red social «Civitas», dibujados por código con Pillow (sin arte
# externo, sin escribir en disco). Capa pura: devuelven PIL.Image RGBA (testeable sin ventana).
# Los iconos de línea se dibujan BLANCOS sobre transparente: en Ursina se tiñen con `color`
# (gris tenue, verde de republicar, rosa del corazón...). Se dibujan a 4x y se reducen (antialias).
#
#   dibujar_icono(nombre, lleno=False, lado=96)            -> icono blanco de línea (o relleno)
#   dibujar_verificado(color)                              -> insignia con su marca de verificación
#   dibujar_logo()                                         -> logo «C» sobre rombo de Civitas
#   dibujar_vista_previa(variante, semilla, ancho, alto)   -> «foto» de la publicación hecha con formas
# Capa Ursina (importa ursina solo al usarse): textura_icono(...), textura_vista_previa(...).

import math

from PIL import Image, ImageDraw

from frontend import estilo

SUPER = 4          # factor de supersampling
BLANCO = (255, 255, 255, 255)
NOMBRES_ICONOS = (
    "inicio", "explorar", "notificaciones", "mensajes", "perfil", "responder", "republicar",
    "me_gusta", "vistas", "guardar", "bandera", "mas", "buscar",
)


def _punto(k, x, y):
    return (x * k, y * k)


def _puntos(k, lista):
    return [(x * k, y * k) for x, y in lista]


# Arco como lista de puntos: centro (cx, cy), radios, ángulos en grados (0 = derecha, 90 = abajo).
def _arco(cx, cy, rx, ry, desde, hasta, pasos=24):
    return [(cx + rx * math.cos(math.radians(desde + (hasta - desde) * i / pasos)),
             cy + ry * math.sin(math.radians(desde + (hasta - desde) * i / pasos))) for i in range(pasos + 1)]


# Contorno del corazón (curva clásica), escalado al cuadro 100x100.
def _corazon():
    puntos = []
    for i in range(61):
        t = math.pi * 2 * i / 60
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        puntos.append((50 + x * 2.55, 46 - y * 2.55 + 4))
    return puntos


def _linea(d, k, puntos, grosor, cerrado=False):
    pts = _puntos(k, puntos + ([puntos[0]] if cerrado else []))
    d.line(pts, fill=BLANCO, width=int(grosor * k), joint="curve")
    r = grosor * k / 2
    for x, y in pts:       # puntas redondas
        d.ellipse((x - r, y - r, x + r, y + r), fill=BLANCO)


# Dibuja el icono `nombre` en blanco, `lleno` rellena la forma (corazón lleno, bandera llena...).
def dibujar_icono(nombre, lleno=False, lado=96):
    if nombre not in NOMBRES_ICONOS:
        raise ValueError(f"icono desconocido: {nombre!r}")
    L = lado * SUPER
    k = L / 100
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    g = 7.5   # grosor de línea (en el cuadro de 100)

    if nombre == "inicio":
        contorno = [(14, 50), (50, 16), (86, 50)]
        casa = [(22, 44), (22, 86), (78, 86), (78, 44)]
        if lleno:
            d.polygon(_puntos(k, [(50, 14), (90, 50), (80, 50), (80, 88), (20, 88), (20, 50), (10, 50)]), fill=BLANCO)
            d.rectangle((42 * k, 62 * k, 58 * k, 88 * k), fill=(0, 0, 0, 0))
        else:
            _linea(d, k, contorno, g)
            _linea(d, k, casa, g)
            _linea(d, k, [(42, 86), (42, 62), (58, 62), (58, 86)], g)
    elif nombre in ("explorar", "buscar"):
        d.ellipse((16 * k, 14 * k, 64 * k, 62 * k), outline=BLANCO, width=int(g * k))
        _linea(d, k, [(58, 56), (86, 84)], g + 1)
    elif nombre == "notificaciones":
        borde = _arco(50, 42, 26, 26, 180, 360) + [(76, 64), (84, 74), (16, 74), (24, 64)]
        if lleno:
            d.polygon(_puntos(k, borde), fill=BLANCO)
        else:
            _linea(d, k, borde, g, cerrado=True)
        d.pieslice((40 * k, 74 * k, 60 * k, 94 * k), 0, 180, fill=BLANCO)
        _linea(d, k, [(50, 12), (50, 18)], g)
    elif nombre == "mensajes":
        d.rounded_rectangle((10 * k, 22 * k, 90 * k, 78 * k), radius=10 * k, outline=BLANCO, width=int(g * k))
        _linea(d, k, [(14, 28), (50, 56), (86, 28)], g - 1)
    elif nombre == "perfil":
        if lleno:
            d.ellipse((32 * k, 12 * k, 68 * k, 48 * k), fill=BLANCO)
            d.pieslice((14 * k, 54 * k, 86 * k, 126 * k), 180, 360, fill=BLANCO)
        else:
            d.ellipse((33 * k, 14 * k, 67 * k, 48 * k), outline=BLANCO, width=int(g * k))
            _linea(d, k, _arco(50, 90, 34, 34, 182, 358), g)
    elif nombre == "responder":
        d.rounded_rectangle((10 * k, 16 * k, 90 * k, 66 * k), radius=18 * k, outline=BLANCO, width=int(g * k))
        _linea(d, k, [(30, 64), (30, 86), (54, 66)], g)
    elif nombre == "republicar":
        _linea(d, k, [(22, 52), (22, 34), (66, 34)], g)
        d.polygon(_puntos(k, [(60, 20), (82, 34), (60, 48)]), fill=BLANCO)
        _linea(d, k, [(78, 48), (78, 66), (34, 66)], g)
        d.polygon(_puntos(k, [(40, 52), (18, 66), (40, 80)]), fill=BLANCO)
    elif nombre == "me_gusta":
        if lleno:
            d.polygon(_puntos(k, _corazon()), fill=BLANCO)
        else:
            _linea(d, k, _corazon(), g, cerrado=True)
    elif nombre == "vistas":
        _linea(d, k, [(24, 84), (24, 52)], g + 1)
        _linea(d, k, [(50, 84), (50, 20)], g + 1)
        _linea(d, k, [(76, 84), (76, 62)], g + 1)
    elif nombre == "guardar":
        forma = [(26, 12), (74, 12), (74, 90), (50, 68), (26, 90)]
        if lleno:
            d.polygon(_puntos(k, forma), fill=BLANCO)
        else:
            _linea(d, k, forma, g, cerrado=True)
    elif nombre == "bandera":
        bandera = [(30, 16), (84, 24), (68, 42), (84, 60), (30, 52)]
        if lleno:
            d.polygon(_puntos(k, bandera), fill=BLANCO)
        else:
            _linea(d, k, bandera, g - 1, cerrado=True)
        _linea(d, k, [(28, 12), (28, 92)], g + 1)
    elif nombre == "mas":
        for cx in (22, 50, 78):
            d.ellipse(((cx - 7) * k, 43 * k, (cx + 7) * k, 57 * k), fill=BLANCO)
    return img.resize((lado, lado), Image.LANCZOS)


# Insignia de verificado: sello festoneado de `color` con la marca de verificación en tinta.
def dibujar_verificado(color, lado=64):
    L = lado * SUPER
    k = L / 100
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    puntos = []
    for i in range(32):
        radio = 47 if i % 2 == 0 else 40
        a = math.pi * 2 * i / 32
        puntos.append((50 + radio * math.cos(a), 50 + radio * math.sin(a)))
    d.polygon(_puntos(k, puntos), fill=(*color, 255), outline=(*estilo.TINTA, 255), width=int(3 * k))
    tinta = (*estilo.TINTA, 255)
    d.line(_puntos(k, [(29, 52), (44, 66), (72, 34)]), fill=tinta, width=int(10 * k), joint="curve")
    return img.resize((lado, lado), Image.LANCZOS)


# Logo de Civitas: rombo amarillo con borde de tinta y una «C» (anillo abierto) de tinta, con un punto cian.
def dibujar_logo(lado=128):
    L = lado * SUPER
    k = L / 100
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rombo = [(50, 4), (96, 50), (50, 96), (4, 50)]
    d.polygon(_puntos(k, rombo), fill=(*estilo.ACENTO_PRIMARIO, 255), outline=(*estilo.TINTA, 255), width=int(5 * k))
    d.arc((27 * k, 27 * k, 73 * k, 73 * k), 40, 320, fill=(*estilo.TINTA, 255), width=int(10 * k))
    d.ellipse((60 * k, 44 * k, 72 * k, 56 * k), fill=(*estilo.ACENTO_SECUNDARIO, 255), outline=(*estilo.TINTA, 255), width=int(2 * k))
    return img.resize((lado, lado), Image.LANCZOS)


# ---------------------------------------------------------------- vistas previas («fotos» por código)

_PALETAS = (
    ((255, 168, 76), (240, 98, 120)),     # atardecer
    ((90, 170, 235), (60, 110, 200)),     # cielo
    ((120, 205, 160), (50, 150, 130)),    # verde
    ((190, 140, 230), (110, 80, 190)),    # violeta
)


def _degradado(ancho, alto, arriba, abajo):
    img = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / max(1, alto - 1)
        d.line((0, y, ancho, y), fill=tuple(int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)))
    return img


# Puntos de semitono (comic) en una esquina, con baja opacidad.
def _semitono(d, ancho, alto, tono, paso):
    for j, y in enumerate(range(0, alto, paso)):
        for x in range(paso // 2 * (j % 2), ancho, paso):
            r = max(1, int(paso * 0.22 * (1 - x / ancho)))
            d.ellipse((x - r, y - r, x + r, y + r), fill=tono)


# «Foto» de la publicación hecha con formas planas y contorno de tinta. `variante` en
# red_social_calculos.VARIANTES_IMAGEN; `semilla` varía colores y posiciones sin azar global.
def dibujar_vista_previa(variante, semilla, ancho, alto):
    S = 2
    W, H = ancho * S, alto * S
    arriba, abajo = _PALETAS[semilla % len(_PALETAS)]
    img = _degradado(W, H, arriba, abajo).convert("RGBA")
    d = ImageDraw.Draw(img)
    tinta = (*estilo.TINTA, 255)
    papel = (*estilo.PAPEL, 255)
    grueso = max(3, H // 38)
    desfase = (semilla // 7) % 5

    if variante == "ciudad":
        d.ellipse((W * 0.72, H * 0.10, W * 0.72 + H * 0.34, H * 0.10 + H * 0.34), fill=(255, 232, 110, 255), outline=tinta, width=grueso)
        x = -W * 0.02
        i = 0
        while x < W:
            ancho_e = W * (0.07 + 0.025 * ((i + desfase) % 3))
            alto_e = H * (0.34 + 0.12 * ((i * 3 + desfase) % 4))
            color = [(46, 50, 71), (58, 62, 88), (36, 39, 56), (70, 90, 150)][(i + semilla) % 4]
            d.rectangle((x, H - alto_e, x + ancho_e, H), fill=(*color, 255), outline=tinta, width=grueso)
            for wy in range(int(H - alto_e + H * 0.06), int(H - H * 0.06), max(6, H // 9)):
                for wx in range(int(x + ancho_e * 0.2), int(x + ancho_e * 0.8), max(6, W // 40)):
                    d.rectangle((wx, wy, wx + W // 90, wy + H // 22), fill=(255, 220, 60, 230) if (wx + wy + i) % 3 else (40, 44, 64, 255))
            x += ancho_e + W * 0.012
            i += 1
    elif variante == "multitud":
        d.rectangle((0, H * 0.66, W, H), fill=(36, 39, 56, 255), outline=tinta, width=grueso)
        for i in range(9):
            cx = W * (0.07 + 0.108 * i) + ((i * 5 + desfase) % 3 - 1) * W * 0.01
            r = H * (0.12 + 0.02 * ((i + desfase) % 3))
            color = _AVATARES[(i + semilla) % len(_AVATARES)]
            d.pieslice((cx - r * 1.25, H * 0.70, cx + r * 1.25, H * 0.70 + r * 2.6), 180, 360, fill=(*color, 255), outline=tinta, width=grueso)
            d.ellipse((cx - r * 0.8, H * 0.46 - r * 0.2 + ((i * 7) % 3) * H * 0.02, cx + r * 0.8, H * 0.46 + r * 1.4 + ((i * 7) % 3) * H * 0.02),
                      fill=(240, 200, 160, 255), outline=tinta, width=grueso)
        d.rectangle((W * 0.34, H * 0.08, W * 0.66, H * 0.30), fill=papel, outline=tinta, width=grueso)
        for fila in range(2):
            d.line((W * 0.38, H * (0.15 + fila * 0.08), W * 0.62 - fila * W * 0.08, H * (0.15 + fila * 0.08)), fill=tinta, width=grueso)
        d.line((W * 0.5, H * 0.30, W * 0.5, H * 0.50), fill=tinta, width=grueso)
    elif variante == "captura":
        d.rectangle((0, 0, W, H), fill=(24, 26, 38, 255))
        d.rectangle((W * 0.03, H * 0.08, W * 0.97, H * 0.92), fill=(36, 39, 56, 255), outline=tinta, width=grueso)
        for i in range(7):
            alto_b = H * (0.20 + 0.50 * (((i * 5 + semilla) % 7) / 7))
            x0 = W * (0.30 + 0.09 * i)
            d.rectangle((x0, H * 0.84 - alto_b, x0 + W * 0.06, H * 0.84), fill=(*estilo.ACENTO_SECUNDARIO, 255), outline=tinta, width=grueso)
        d.polygon([(W * 0.10, H * 0.78), (W * 0.20, H * 0.26), (W * 0.30 - W * 0.02, H * 0.78)], fill=(*estilo.ESTADO_ERROR, 255), outline=tinta, width=grueso)
        d.rectangle((W * 0.188, H * 0.40, W * 0.212, H * 0.62), fill=papel)
        d.ellipse((W * 0.186, H * 0.66, W * 0.214, H * 0.72), fill=papel)
    elif variante == "calle":
        d.rectangle((0, 0, W, H), fill=(*arriba, 255))
        for i in range(5):
            x0 = W * (0.02 + 0.2 * i)
            color = [(230, 120, 150), (240, 200, 90), (80, 170, 100), (70, 110, 190), (235, 140, 60)][(i + semilla) % 5]
            alto_c = H * (0.45 + 0.1 * ((i + desfase) % 3))
            d.rectangle((x0, H - alto_c, x0 + W * 0.17, H), fill=(*color, 255), outline=tinta, width=grueso)
            d.polygon([(x0 - W * 0.01, H - alto_c), (x0 + W * 0.085, H - alto_c - H * 0.12), (x0 + W * 0.18, H - alto_c)], fill=(150, 154, 170, 255), outline=tinta, width=grueso)
            d.rectangle((x0 + W * 0.06, H - H * 0.22, x0 + W * 0.11, H), fill=(40, 30, 40, 255), outline=tinta, width=grueso // 2 or 1)
        d.polygon([(W * 0.40, H), (W * 0.60, H), (W * 0.54, H * 0.62), (W * 0.46, H * 0.62)], fill=(214, 190, 140, 255), outline=tinta, width=grueso)
        d.line((W * 0.05, H * 0.30, W * 0.95, H * 0.22), fill=tinta, width=max(2, grueso // 2))   # cable
    else:   # video
        d.rectangle((0, 0, W, H), fill=(*arriba, 255))
        radio = H * 0.30
        cx, cy = W / 2, H * 0.46
        d.ellipse((cx - radio, cy - radio, cx + radio, cy + radio), fill=papel, outline=tinta, width=grueso)
        d.polygon([(cx - radio * 0.32, cy - radio * 0.5), (cx - radio * 0.32, cy + radio * 0.5), (cx + radio * 0.52, cy)], fill=tinta)
        d.rectangle((W * 0.04, H * 0.84, W * 0.96, H * 0.92), fill=(36, 39, 56, 255), outline=tinta, width=grueso)
        d.rectangle((W * 0.04, H * 0.84, W * (0.30 + 0.05 * (semilla % 8)), H * 0.92), fill=(*estilo.ESTADO_ERROR, 255), outline=tinta, width=grueso)

    # Semitono de cómic en la esquina superior izquierda + borde de tinta.
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _semitono(ImageDraw.Draw(capa), W // 3, H // 2, (18, 20, 32, 70), max(8, H // 14))
    img = Image.alpha_composite(img, capa)
    ImageDraw.Draw(img).rectangle((0, 0, W - 1, H - 1), outline=tinta, width=grueso)
    return img.resize((ancho, alto), Image.LANCZOS)


_AVATARES = ((232, 84, 150), (46, 184, 116), (66, 133, 244), (240, 150, 40), (140, 110, 200), (60, 180, 170))


# ---------------------------------------------------------------- capa Ursina (caché)

_CACHE = {}


def _textura(clave, hacer):
    if clave not in _CACHE:
        from ursina import Texture
        textura = Texture(hacer())
        textura.filtering = "bilinear"
        _CACHE[clave] = textura
    return _CACHE[clave]


def textura_icono(nombre, lleno=False):
    return _textura(("icono", nombre, bool(lleno)), lambda: dibujar_icono(nombre, lleno))


def textura_verificado(tipo):
    color = (64, 160, 255) if tipo == "azul" else (255, 200, 80)
    return _textura(("verificado", tipo), lambda: dibujar_verificado(color))


def textura_logo():
    return _textura(("logo",), dibujar_logo)


def textura_vista_previa(variante, semilla, ancho, alto):
    return _textura(("vista", variante, semilla % 1000, ancho, alto),
                    lambda: dibujar_vista_previa(variante, semilla, ancho, alto))

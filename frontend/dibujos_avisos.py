# Dibujos sencillos de las tarjetas de primera vez del teléfono grande (frontend/tarjeta_aviso.py), hechos con Pillow:
# formas con borde de tinta, como las viñetas de cómic del juego. Sin emojis ni flechas de texto (la fuente no los tiene)
# y sin arte externo. Capa pura: dibujar(nombre) -> PIL.Image RGBA (se prueba sin ventana). La capa Ursina (textura) va
# al final y guarda cada textura en caché: se crean una vez por partida, no por tarjeta.
#
#   NOMBRES                 los dibujos que se pueden pedir desde backend/datos/explicaciones_avisos.json
#   dibujar(nombre, lado)   -> PIL.Image RGBA cuadrada
#   textura(nombre)         -> ursina.Texture (en caché)

import math

from PIL import Image, ImageDraw

from frontend import estilo

LADO = 192
SUPER = 3
TINTA = (*estilo.TINTA, 255)
PAPEL = (*estilo.PAPEL, 255)
AMARILLO = (*estilo.COLOR_ACENTO, 255)
CIAN = (*estilo.ACENTO_SECUNDARIO, 255)
ROJO = (*estilo.ESTADO_ERROR, 255)
VERDE = (*estilo.ESTADO_EXITO, 255)
AZUL = (*estilo.COLOR_BOTON, 255)
GRIS = (*estilo.COLOR_TARJETA, 255)
AVATARES = ((232, 84, 150, 255), (46, 184, 116, 255), (66, 133, 244, 255), (240, 150, 40, 255))


def _caja(k, x0, y0, x1, y1):
    return (x0 * k, y0 * k, x1 * k, y1 * k)


def _g(k):
    return max(2, int(5 * k / 4))


def _lupa(d, k, cx, cy, r):
    g = _g(k)
    angulo = math.radians(45)
    x0, y0 = cx + r * math.cos(angulo), cy + r * math.sin(angulo)
    x1, y1 = cx + r * 2.0 * math.cos(angulo), cy + r * 2.0 * math.sin(angulo)
    d.line((x0 * k, y0 * k, x1 * k, y1 * k), fill=TINTA, width=g * 3)
    d.ellipse(_caja(k, cx - r, cy - r, cx + r, cy + r), fill=(*estilo.ACENTO_SECUNDARIO, 120), outline=TINTA, width=g * 2)


def _sobre(d, k, x0, y0, x1, y1):
    g = _g(k)
    d.rectangle(_caja(k, x0, y0, x1, y1), fill=PAPEL, outline=TINTA, width=g)
    cx = (x0 + x1) / 2
    d.line(((x0 * k, y0 * k), (cx * k, (y0 + (y1 - y0) * 0.55) * k), (x1 * k, y0 * k)), fill=TINTA, width=g)


def _burbuja_lupa(d, k):
    g = _g(k)
    d.rounded_rectangle(_caja(k, 18, 30, 150, 112), radius=18 * k, fill=PAPEL, outline=TINTA, width=g)
    d.polygon([(40 * k, 108 * k), (34 * k, 136 * k), (66 * k, 110 * k)], fill=PAPEL, outline=TINTA)
    for i, ancho in enumerate((100, 80, 60)):
        y = 50 + i * 20
        d.line((36 * k, y * k, (36 + ancho) * k, y * k), fill=GRIS, width=g * 2)
    _lupa(d, k, 120, 110, 30)


def _sobre_candado(d, k):
    g = _g(k)
    _sobre(d, k, 22, 54, 150, 140)
    # candado verde: el mensaje es de alguien que conoces
    d.arc(_caja(k, 120, 86, 160, 126), 180, 360, fill=TINTA, width=g * 2)
    d.rectangle(_caja(k, 112, 106, 168, 156), fill=VERDE, outline=TINTA, width=g)
    d.ellipse(_caja(k, 135, 122, 145, 132), fill=TINTA)


def _sobre_anzuelo(d, k):
    g = _g(k)
    _sobre(d, k, 22, 70, 150, 156)
    # hilo y anzuelo rojo: el mensaje quiere pescarte
    d.line((130 * k, 14 * k, 130 * k, 92 * k), fill=TINTA, width=g)
    d.arc(_caja(k, 110, 78, 150, 122), 0, 200, fill=ROJO, width=g * 3)
    d.polygon([(110 * k, 96 * k), (102 * k, 84 * k), (118 * k, 88 * k)], fill=ROJO)


def _foto_pegatina(d, k):
    g = _g(k)
    d.rectangle(_caja(k, 16, 22, 176, 150), fill=(*estilo.ACENTO_SECUNDARIO, 255), outline=TINTA, width=g)
    # casa con puerta y número
    d.rectangle(_caja(k, 46, 76, 136, 150), fill=(240, 150, 40, 255), outline=TINTA, width=g)
    d.polygon([(38 * k, 78 * k), (91 * k, 40 * k), (144 * k, 78 * k)], fill=ROJO, outline=TINTA)
    d.rectangle(_caja(k, 78, 108, 104, 150), fill=(120, 72, 40, 255), outline=TINTA, width=g)
    # la pegatina tapa el número de la puerta
    d.ellipse(_caja(k, 96, 80, 140, 124), fill=AMARILLO, outline=TINTA, width=g)
    d.line((104 * k, 102 * k, 132 * k, 102 * k), fill=TINTA, width=g)
    d.line((118 * k, 88 * k, 118 * k, 116 * k), fill=TINTA, width=g)


def _post(d, k, x0, y0, x1, y1, tono):
    g = _g(k)
    d.rounded_rectangle(_caja(k, x0, y0, x1, y1), radius=10 * k, fill=PAPEL, outline=TINTA, width=g)
    d.ellipse(_caja(k, x0 + 8, y0 + 8, x0 + 26, y0 + 26), fill=tono, outline=TINTA, width=max(1, g // 2))
    for i in range(2):
        y = y0 + 38 + i * 14
        d.line(((x0 + 10) * k, y * k, (x1 - 12 - i * 18) * k, y * k), fill=GRIS, width=g * 2)


def _post_tachado(d, k):
    g = _g(k)
    _post(d, k, 18, 40, 170, 130, AVATARES[0])
    d.line((22 * k, 126 * k, 166 * k, 44 * k), fill=ROJO, width=g * 3)
    d.line((22 * k, 44 * k, 166 * k, 126 * k), fill=ROJO, width=g * 3)


def _post_corregido(d, k):
    g = _g(k)
    _post(d, k, 18, 40, 170, 130, AVATARES[1])
    # sello de corrección: círculo verde con visto
    d.ellipse(_caja(k, 118, 92, 168, 142), fill=VERDE, outline=TINTA, width=g)
    d.line(((130 * k, 118 * k), (140 * k, 128 * k), (158 * k, 104 * k)), fill=PAPEL, width=g * 2)


def _camara_captura(d, k):
    g = _g(k)
    d.rounded_rectangle(_caja(k, 24, 60, 168, 150), radius=14 * k, fill=GRIS, outline=TINTA, width=g)
    d.rectangle(_caja(k, 70, 44, 120, 62), fill=GRIS, outline=TINTA, width=g)
    d.ellipse(_caja(k, 66, 72, 126, 132), fill=PAPEL, outline=TINTA, width=g)
    d.ellipse(_caja(k, 82, 88, 110, 116), fill=TINTA)
    d.ellipse(_caja(k, 138, 70, 154, 86), fill=ROJO, outline=TINTA, width=max(1, g // 2))


def _persona(d, k, cx, cy, r, tono):
    g = _g(k)
    d.pieslice(_caja(k, cx - r * 1.4, cy + r * 0.7, cx + r * 1.4, cy + r * 3.4), 180, 360, fill=tono, outline=TINTA, width=g)
    d.ellipse(_caja(k, cx - r, cy - r, cx + r, cy + r), fill=PAPEL, outline=TINTA, width=g)


def _grupo_aparte(d, k):
    for i, cx in enumerate((34, 66, 98)):
        _persona(d, k, cx, 74 + (i % 2) * 6, 16, AVATARES[i])
    # el que queda aparte, más abajo y solo
    _persona(d, k, 156, 96, 16, AVATARES[3])
    g = _g(k)
    d.line((128 * k, 40 * k, 128 * k, 156 * k), fill=GRIS, width=g)


def _reloj(d, k):
    g = _g(k)
    d.ellipse(_caja(k, 26, 26, 166, 166), fill=PAPEL, outline=TINTA, width=g * 2)
    for i in range(12):
        a = math.radians(i * 30)
        r0, r1 = 58, 66
        d.line(((96 + r0 * math.sin(a)) * k, (96 - r0 * math.cos(a)) * k,
                (96 + r1 * math.sin(a)) * k, (96 - r1 * math.cos(a)) * k), fill=TINTA, width=g)
    d.line((96 * k, 96 * k, 96 * k, 46 * k), fill=TINTA, width=g * 2)
    d.line((96 * k, 96 * k, 136 * k, 112 * k), fill=ROJO, width=g * 2)
    d.ellipse(_caja(k, 90, 90, 102, 102), fill=TINTA)


def _dedo_deslizando(d, k):
    g = _g(k)
    # pantalla con dos publicaciones y un dedo que sube
    d.rounded_rectangle(_caja(k, 46, 12, 146, 180), radius=14 * k, fill=TINTA)
    d.rounded_rectangle(_caja(k, 54, 26, 138, 166), radius=6 * k, fill=GRIS)
    d.rectangle(_caja(k, 60, 34, 132, 86), fill=PAPEL)
    d.rectangle(_caja(k, 60, 96, 132, 150), fill=PAPEL)
    for i, y in enumerate((150, 136, 122)):
        d.ellipse(_caja(k, 112 - 3 + i, y, 112 + 3 + i, y + 6), fill=(*estilo.ACENTO_SECUNDARIO, 120 + 40 * i))
    d.rounded_rectangle(_caja(k, 100, 104, 126, 176), radius=12 * k, fill=(240, 196, 150, 255), outline=TINTA, width=g)
    d.rounded_rectangle(_caja(k, 104, 108, 122, 124), radius=6 * k, fill=PAPEL, outline=TINTA, width=max(1, g // 2))


def _cadena_reenvios(d, k):
    g = _g(k)
    # tres burbujas que se pasan el mismo mensaje, unidas por una línea de puntos; la última, más grande
    centros = ((40, 140, 22), (96, 96, 28), (150, 52, 34))
    for (x0, y0, _r0), (x1, y1, _r1) in zip(centros, centros[1:]):
        for t in range(1, 6):
            x = x0 + (x1 - x0) * t / 6
            y = y0 + (y1 - y0) * t / 6
            d.ellipse(_caja(k, x - 3, y - 3, x + 3, y + 3), fill=PAPEL)
    for i, (cx, cy, r) in enumerate(centros):
        d.rounded_rectangle(_caja(k, cx - r, cy - r * 0.7, cx + r, cy + r * 0.7), radius=8 * k,
                            fill=AMARILLO if i == 2 else PAPEL, outline=TINTA, width=g)
        d.line(((cx - r * 0.55) * k, cy * k, (cx + r * 0.55) * k, cy * k), fill=TINTA, width=g)


_DIBUJOS = {
    "cadena_reenvios": _cadena_reenvios,
    "burbuja_lupa": _burbuja_lupa, "sobre_candado": _sobre_candado, "sobre_anzuelo": _sobre_anzuelo,
    "foto_pegatina": _foto_pegatina, "post_tachado": _post_tachado, "post_corregido": _post_corregido,
    "camara_captura": _camara_captura, "grupo_aparte": _grupo_aparte, "reloj": _reloj,
    "dedo_deslizando": _dedo_deslizando,
}
NOMBRES = tuple(_DIBUJOS)


def dibujar(nombre, lado=LADO):
    """Imagen RGBA cuadrada del dibujo `nombre` (fondo transparente). KeyError si no existe."""
    hacer = _DIBUJOS[nombre]
    k = SUPER * lado / LADO
    img = Image.new("RGBA", (int(lado * SUPER), int(lado * SUPER)), (0, 0, 0, 0))
    hacer(ImageDraw.Draw(img), k)
    return img.resize((lado, lado), Image.LANCZOS)


# ---------------------------------------------------------------- capa Ursina (caché)

_CACHE = {}


def textura(nombre):
    if nombre not in _CACHE:
        from ursina import Texture
        tex = Texture(dibujar(nombre))
        tex.filtering = "bilinear"
        _CACHE[nombre] = tex
    return _CACHE[nombre]

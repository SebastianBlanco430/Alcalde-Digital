# «Fotos» de las pantallas del teléfono grande (publicaciones, chats y cadenas), dibujadas con Pillow: formas con borde
# de tinta, sin arte externo. Las de las publicaciones (selfie, fachada, pasajes) ponen cada objeto marcable en las
# coordenadas relativas (x, y de 0 a 1) que dice backend/datos/canales_avisos.json, así la pegatina cae encima.
#
#   NOMBRES                          fotos que se pueden pedir desde el JSON
#   dibujar(nombre, ancho, alto)     -> PIL.Image RGBA (pura, se prueba sin ventana)
#   textura(nombre)                  -> ursina.Texture en caché (una por foto)

import math

from PIL import Image, ImageDraw, ImageFilter

from frontend import estilo

ANCHO, ALTO = 400, 240
SUPER = 2
TINTA = (*estilo.TINTA, 255)
PAPEL = (*estilo.PAPEL, 255)
PIEL = (196, 140, 100, 255)
PIEL_CLARA = (238, 196, 160, 255)


def _k(d):
    return d._k


def _r(d, x0, y0, x1, y1, fill, ancho=True, radio=0):
    """Rectángulo en coordenadas RELATIVAS (0..1) con borde de tinta."""
    W, H = d._W, d._H
    caja = (x0 * W, y0 * H, x1 * W, y1 * H)
    g = d._g if ancho else 0
    if radio:
        d.rounded_rectangle(caja, radius=radio * H, fill=fill, outline=TINTA if g else None, width=g)
    else:
        d.rectangle(caja, fill=fill, outline=TINTA if g else None, width=g)


def _e(d, cx, cy, rx, ry, fill, borde=True):
    W, H = d._W, d._H
    d.ellipse(((cx - rx) * W, (cy - ry) * H, (cx + rx) * W, (cy + ry) * H), fill=fill,
              outline=TINTA if borde else None, width=d._g if borde else 0)


def _p(d, puntos, fill):
    W, H = d._W, d._H
    d.polygon([(x * W, y * H) for x, y in puntos], fill=fill, outline=TINTA)


def _l(d, x0, y0, x1, y1, fill=TINTA, grosor=1.0):
    W, H = d._W, d._H
    d.line((x0 * W, y0 * H, x1 * W, y1 * H), fill=fill, width=max(1, int(d._g * grosor)))


def _fondo(d, arriba, abajo):
    W, H = d._W, d._H
    for y in range(H):
        t = y / max(1, H - 1)
        tono = tuple(int(a + (b - a) * t) for a, b in zip(arriba, abajo))
        d.line((0, y, W, y), fill=(*tono, 255))


def _persona(d, cx, cy, escala, piel, ropa, pelo=TINTA):
    _p(d, [(cx - 0.12 * escala, cy + 0.55 * escala), (cx - 0.09 * escala, cy + 0.22 * escala),
           (cx + 0.09 * escala, cy + 0.22 * escala), (cx + 0.12 * escala, cy + 0.55 * escala)], ropa)
    _e(d, cx, cy, 0.075 * escala, 0.14 * escala, piel)
    _e(d, cx, cy - 0.1 * escala, 0.07 * escala, 0.05 * escala, pelo, borde=False)


# ----------------------------------------------------------------------------- fotos de publicar (con coordenadas)

def _selfie(d):
    _fondo(d, (255, 170, 120), (120, 160, 230))
    # amanecer sobre el morro (cielo: 0.82, 0.22)
    _e(d, 0.82, 0.22, 0.07, 0.11, (255, 230, 120, 255))
    _p(d, [(0.0, 0.62), (0.18, 0.45), (0.35, 0.58), (0.6, 0.42), (0.78, 0.55), (1.0, 0.4), (1.0, 1.0), (0.0, 1.0)],
       (70, 110, 80, 255))
    for i in range(7):
        x = 0.62 + i * 0.055
        _r(d, x, 0.5 + (i % 3) * 0.04, x + 0.045, 0.62, ((200, 120, 90, 255), (230, 200, 120, 255))[i % 2])
    # tú: cara (0.42, 0.40) y uniforme con escudo de la escuela (0.42, 0.84)
    _p(d, [(0.22, 1.0), (0.27, 0.68), (0.57, 0.68), (0.62, 1.0)], (240, 240, 250, 255))
    _e(d, 0.42, 0.84, 0.05, 0.075, (60, 90, 170, 255))
    _r(d, 0.405, 0.81, 0.435, 0.87, (255, 220, 60, 255), ancho=False)
    _e(d, 0.42, 0.42, 0.11, 0.2, PIEL)
    _e(d, 0.42, 0.25, 0.115, 0.08, TINTA, borde=False)
    _l(d, 0.37, 0.4, 0.4, 0.4)
    _l(d, 0.44, 0.4, 0.47, 0.4)
    _l(d, 0.39, 0.5, 0.45, 0.5)


def _fachada(d):
    # pared amarilla (pintura: 0.16, 0.28)
    _fondo(d, (250, 215, 90), (235, 190, 70))
    _r(d, 0.0, 0.92, 1.0, 1.0, (150, 150, 150, 255), ancho=False)
    # ventana con macetas (0.17, 0.66)
    _r(d, 0.06, 0.38, 0.28, 0.6, (120, 180, 220, 255))
    _r(d, 0.06, 0.6, 0.28, 0.72, (200, 90, 60, 255))
    for x in (0.1, 0.17, 0.24):
        _e(d, x, 0.58, 0.03, 0.05, (60, 160, 80, 255))
    # puerta con el número (0.45, 0.36) y las llaves en la cerradura (0.55, 0.66)
    _r(d, 0.35, 0.3, 0.57, 0.92, (110, 70, 45, 255))
    _r(d, 0.4, 0.32, 0.5, 0.41, PAPEL)
    _l(d, 0.43, 0.35, 0.43, 0.39)
    _l(d, 0.46, 0.35, 0.47, 0.39)
    _e(d, 0.55, 0.64, 0.012, 0.02, (220, 200, 90, 255))
    _l(d, 0.55, 0.66, 0.565, 0.74, (220, 200, 90, 255))
    _e(d, 0.57, 0.75, 0.015, 0.025, (220, 200, 90, 255))
    # moto con la placa (0.82, 0.88)
    _e(d, 0.7, 0.84, 0.06, 0.1, (40, 40, 50, 255))
    _e(d, 0.92, 0.84, 0.06, 0.1, (40, 40, 50, 255))
    _p(d, [(0.68, 0.74), (0.76, 0.6), (0.9, 0.62), (0.94, 0.76)], (200, 50, 50, 255))
    _r(d, 0.77, 0.84, 0.87, 0.93, PAPEL)
    _l(d, 0.79, 0.885, 0.85, 0.885, grosor=0.8)


def _pasajes(d):
    _fondo(d, (150, 100, 70), (120, 80, 55))
    # termo de café (0.12, 0.50)
    _r(d, 0.08, 0.3, 0.16, 0.72, (60, 140, 120, 255), radio=0.03)
    _r(d, 0.085, 0.24, 0.155, 0.31, (40, 40, 50, 255))
    # pasajes con nombre y código (0.42, 0.52)
    for i, (x, y) in enumerate(((0.25, 0.32), (0.32, 0.42))):
        _r(d, x, y, x + 0.34, y + 0.3, PAPEL, radio=0.02)
        _r(d, x, y, x + 0.34, y + 0.07, (66, 133, 244, 255))
        for j in range(3):
            _l(d, x + 0.03, y + 0.12 + j * 0.05, x + 0.25 - j * 0.04, y + 0.12 + j * 0.05, (120, 120, 140, 255), 0.8)
    # mochila (0.83, 0.48)
    _r(d, 0.74, 0.28, 0.92, 0.72, (230, 120, 60, 255), radio=0.05)
    _r(d, 0.77, 0.48, 0.89, 0.62, (200, 95, 40, 255), radio=0.02)
    _l(d, 0.79, 0.28, 0.81, 0.2)
    _l(d, 0.87, 0.28, 0.85, 0.2)


# ----------------------------------------------------------------------------- fotos de dilemas y chats

def _cumple(d):
    _fondo(d, (60, 50, 90), (40, 35, 60))
    for i in range(9):
        x = 0.05 + i * 0.11
        _e(d, x, 0.12 + (i % 2) * 0.05, 0.02, 0.03, ((255, 120, 150, 255), (120, 220, 255, 255), (255, 220, 60, 255))[i % 3])
    _r(d, 0.04, 0.2, 0.2, 0.32, PAPEL)                   # letrero de la calle
    _r(d, 0.82, 0.22, 0.95, 0.34, PAPEL)                 # número de la casa
    for i, x in enumerate((0.22, 0.4, 0.6, 0.78)):
        _persona(d, x, 0.42, 0.9, (PIEL, PIEL_CLARA)[i % 2], ((232, 84, 150, 255), (46, 184, 116, 255),
                                                               (66, 133, 244, 255), (240, 150, 40, 255))[i])
    _r(d, 0.38, 0.78, 0.62, 0.95, (240, 200, 220, 255), radio=0.02)   # la torta
    for x in (0.44, 0.5, 0.56):
        _l(d, x, 0.72, x, 0.78, (255, 220, 60, 255), 1.2)


def _feira(d):
    _fondo(d, (250, 230, 190), (230, 200, 150))
    _p(d, [(0.0, 0.1), (0.5, 0.0), (1.0, 0.1), (1.0, 0.2), (0.0, 0.2)], (214, 62, 62, 255))
    _r(d, 0.05, 0.55, 0.95, 0.68, (150, 100, 60, 255))
    _r(d, 0.38, 0.4, 0.62, 0.55, (180, 180, 190, 255))  # la balanza
    _r(d, 0.43, 0.43, 0.57, 0.5, (30, 40, 30, 255))
    _l(d, 0.45, 0.465, 0.55, 0.465, (90, 220, 110, 255))
    _persona(d, 0.2, 0.35, 1.1, PIEL, (140, 110, 200, 255))           # doña Cida
    _persona(d, 0.8, 0.35, 1.1, PIEL_CLARA, (60, 180, 170, 255))
    _persona(d, 0.12, 0.72, 0.6, PIEL_CLARA, (255, 220, 60, 255))     # el niño al fondo
    # botón de reproducir: es un video
    _e(d, 0.5, 0.82, 0.07, 0.11, (0, 0, 0, 160), borde=False)
    _p(d, [(0.485, 0.76), (0.485, 0.88), (0.535, 0.82)], PAPEL)


def _pan(d):
    _fondo(d, (240, 225, 200), (220, 200, 170))
    _e(d, 0.5, 0.58, 0.32, 0.26, (220, 160, 80, 255))
    _e(d, 0.5, 0.52, 0.26, 0.16, (240, 190, 110, 255), borde=False)
    W, H = d._W, d._H
    puntos = [(0.3 + t * 0.4, 0.5 + 0.08 * math.sin(t * 9)) for t in [i / 30 for i in range(31)]]
    d.line([(x * W, y * H) for x, y in puntos], fill=(250, 220, 120, 255), width=max(2, d._g))


def _samba(d):
    _fondo(d, (40, 20, 60), (90, 30, 70))
    for i in range(5):
        x = 0.12 + i * 0.19
        _persona(d, x, 0.3, 0.9, (PIEL, PIEL_CLARA)[i % 2], ((255, 220, 60, 255), (46, 184, 116, 255))[i % 2])
        _e(d, x, 0.82, 0.07, 0.1, (220, 220, 230, 255))
        _e(d, x, 0.82, 0.05, 0.07, (180, 40, 60, 255), borde=False)
    _r(d, 0.03, 0.04, 0.2, 0.14, (214, 62, 62, 255), radio=0.02)      # EN VIVO
    _e(d, 0.06, 0.09, 0.012, 0.02, PAPEL, borde=False)


def _meme(d):
    _fondo(d, (230, 230, 235), (210, 210, 220))
    _e(d, 0.5, 0.62, 0.3, 0.22, (150, 140, 130, 255))                 # el burro
    _e(d, 0.28, 0.42, 0.06, 0.16, (150, 140, 130, 255))
    _e(d, 0.42, 0.38, 0.06, 0.16, (150, 140, 130, 255))
    _e(d, 0.5, 0.45, 0.12, 0.17, PIEL_CLARA)                           # la cara pegada
    _l(d, 0.46, 0.43, 0.48, 0.43)
    _l(d, 0.52, 0.43, 0.54, 0.43)
    _r(d, 0.1, 0.05, 0.9, 0.16, PAPEL, ancho=False)
    _l(d, 0.2, 0.105, 0.8, 0.105, TINTA, 2.0)


def _ana(d):
    _fondo(d, (240, 200, 150), (200, 160, 120))
    _r(d, 0.0, 0.6, 1.0, 0.75, (150, 100, 60, 255))                    # el mostrador
    _persona(d, 0.62, 0.32, 1.2, PIEL, (255, 255, 255, 255))           # Ana, de espaldas a la cámara
    for i in range(4):
        _e(d, 0.12 + i * 0.09, 0.56, 0.035, 0.03, (220, 160, 80, 255))


def _borrosa(d):
    _fondo(d, (120, 130, 140), (90, 95, 105))
    _r(d, 0.0, 0.7, 1.0, 1.0, (70, 70, 75, 255), ancho=False)
    _persona(d, 0.5, 0.35, 1.2, PIEL, (60, 90, 170, 255))
    _r(d, 0.58, 0.48, 0.66, 0.6, PAPEL)                                # la planilla


def _colecta(d):
    _fondo(d, (240, 240, 250), (220, 225, 240))
    _r(d, 0.08, 0.1, 0.92, 0.3, (214, 62, 62, 255), radio=0.03)
    _l(d, 0.2, 0.2, 0.8, 0.2, PAPEL, 2.0)
    _persona(d, 0.5, 0.45, 0.9, PIEL, (66, 133, 244, 255))
    _r(d, 0.1, 0.8, 0.9, 0.88, (220, 220, 230, 255), radio=0.02)
    _r(d, 0.1, 0.8, 0.42, 0.88, (46, 184, 116, 255), radio=0.02)


def _lista(d):
    _fondo(d, (250, 250, 250), (240, 240, 245))
    for i in range(6):
        y = 0.1 + i * 0.14
        _e(d, 0.08, y + 0.04, 0.03, 0.05, (66, 133, 244, 255))
        _l(d, 0.16, y + 0.02, 0.5, y + 0.02, (60, 60, 70, 255), 1.0)
        _l(d, 0.16, y + 0.07, 0.75, y + 0.07, (150, 150, 160, 255), 0.8)


_FOTOS = {"selfie": _selfie, "fachada": _fachada, "pasajes": _pasajes, "cumple": _cumple, "feira": _feira,
          "pan": _pan, "samba": _samba, "meme": _meme, "ana": _ana, "borrosa": _borrosa, "colecta": _colecta,
          "lista": _lista}
NOMBRES = tuple(_FOTOS)


def dibujar(nombre, ancho=ANCHO, alto=ALTO):
    """Imagen RGBA de la foto `nombre`. KeyError si no existe. «borrosa» sale desenfocada a propósito."""
    W, H = ancho * SUPER, alto * SUPER
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    d._W, d._H, d._g = W, H, max(2, H // 90)
    _FOTOS[nombre](d)
    if nombre == "borrosa":
        img = img.filter(ImageFilter.GaussianBlur(radius=H // 40))
    return img.resize((ancho, alto), Image.LANCZOS)


_CACHE = {}


def textura(nombre):
    if nombre not in _CACHE:
        from ursina import Texture
        tex = Texture(dibujar(nombre))
        tex.filtering = "bilinear"
        _CACHE[nombre] = tex
    return _CACHE[nombre]

# Iconos del HUD y retratos de rol dibujados por código con Pillow (T6,
# docs/DISENO.md sección 5). Sin arte externo y SIN escribir en disco: se
# dibuja a 256 px, se reduce con LANCZOS y se guarda en una caché en memoria.
#
# Capa pura (testeable sin ventana ni ursina):
#   formas_icono(nombre) / formas_retrato(rol)  -> listas de formas (datos)
#   dibujar_icono(nombre, lado=64)              -> PIL.Image RGBA
#   dibujar_retrato(rol, lado=128, gris=False)  -> PIL.Image RGBA
# Capa Ursina (importa ursina solo al usarse):
#   textura_icono(nombre) / textura_retrato(rol, gris=False)  -> Texture (caché)
#
# Una forma es una tupla (tipo, geometría, relleno, borde):
#   ("rect", (x0, y0, x1, y1, radio), rgb, borde)  rectángulo redondeado
#   ("elipse", (x0, y0, x1, y1), rgb, borde)
#   ("poligono", ((x, y), ...), rgb, borde)
#   ("linea", ((x, y), ...), rgb, borde, grosor)   polilínea
# `borde` True dibuja contorno de tinta de BORDE_PX (a 256 px) alrededor.
from PIL import Image, ImageDraw, ImageFilter

from frontend import estilo

LADO_BASE = 256       # se dibuja a 256 px
LADO_ICONO = 64       # tamaño final del icono del HUD
LADO_RETRATO = 128    # tamaño final del retrato de rol
BORDE_PX = 4          # grosor del contorno de tinta a 256 px

NOMBRES_ICONOS = ("telefono", "mision", "convivencia", "confianza", "desinformacion", "interactuar")
ROLES_RETRATO = ("ciudadano", "periodista", "influencer", "candidato")

_PIEL = (240, 200, 160)
_PIEL_SOMBRA = (214, 168, 128)
_PAPEL_SOMBRA = (200, 194, 176)
_ROJO_CORBATIN = (214, 62, 62)
_PELO = (60, 44, 40)


def _rect(caja, radio, relleno, borde=True):
    return ("rect", (*caja, radio), relleno, borde)


def _elipse(caja, relleno, borde=True):
    return ("elipse", caja, relleno, borde)


def _poligono(puntos, relleno, borde=True):
    return ("poligono", tuple(puntos), relleno, borde)


def _linea(puntos, relleno, grosor, borde=True):
    return ("linea", tuple(puntos), relleno, borde, grosor)


def _formas_telefono():
    return [
        _rect((76, 20, 180, 236), 30, estilo.PAPEL),
        _rect((92, 52, 164, 196), 10, estilo.ACENTO_SECUNDARIO, borde=False),
        _elipse((120, 30, 136, 44), estilo.TINTA, borde=False),
        _rect((112, 208, 144, 218), 5, estilo.TINTA, borde=False),
    ]


def _formas_mision():
    return [
        _rect((84, 196, 172, 232), 10, estilo.PAPEL),
        _poligono([(128, 24), (200, 108), (128, 192), (56, 108)], estilo.ACENTO_PRIMARIO),
        _elipse((110, 90, 146, 126), estilo.TINTA, borde=False),
    ]


def _formas_convivencia():
    return [
        _elipse((130, 150, 244, 300), estilo.ACENTO_PRIMARIO),
        _elipse((132, 40, 208, 116), estilo.ACENTO_PRIMARIO),
        _elipse((12, 160, 152, 316), estilo.PAPEL),
        _elipse((44, 56, 124, 136), estilo.PAPEL),
    ]


def _formas_confianza():
    return [
        _poligono([(128, 20), (218, 54), (210, 150), (128, 236), (46, 150), (38, 54)], estilo.ACENTO_SECUNDARIO),
        _linea([(82, 128), (116, 164), (176, 92)], estilo.PAPEL, 20),
    ]


def _formas_desinformacion():
    return [
        _poligono([(62, 170), (50, 240), (126, 182)], estilo.ESTADO_ERROR),
        _rect((24, 32, 232, 196), 44, estilo.ESTADO_ERROR),
        _rect((114, 62, 142, 132), 12, estilo.PAPEL, borde=False),
        _elipse((113, 146, 143, 176), estilo.PAPEL, borde=False),
    ]


def _formas_interactuar():
    return [
        _rect((36, 66, 220, 232), 30, _PAPEL_SOMBRA),   # base gruesa de la tecla
        _rect((36, 34, 220, 204), 30, estilo.PAPEL),    # cara de la tecla
        _rect((92, 70, 116, 168), 4, estilo.TINTA, borde=False),   # «E»: barra
        _rect((92, 70, 168, 94), 4, estilo.TINTA, borde=False),
        _rect((92, 107, 156, 131), 4, estilo.TINTA, borde=False),
        _rect((92, 144, 168, 168), 4, estilo.TINTA, borde=False),
    ]


_FORMAS_ICONO = {
    "telefono": _formas_telefono,
    "mision": _formas_mision,
    "convivencia": _formas_convivencia,
    "confianza": _formas_confianza,
    "desinformacion": _formas_desinformacion,
    "interactuar": _formas_interactuar,
}


# Busto común: cuerpo del color del rol, cuello y cabeza con ojos.
def _busto(rgb_rol, pelo=True):
    formas = [
        _elipse((18, 168, 238, 340), rgb_rol),
        _rect((108, 140, 148, 184), 10, _PIEL_SOMBRA, borde=False),
        _elipse((74, 36, 182, 168), _PIEL),
    ]
    if pelo:
        formas.insert(2, _elipse((68, 24, 188, 120), _PELO))
        formas.append(_elipse((74, 52, 182, 112), _PELO, borde=False))
        formas.append(_elipse((82, 76, 174, 168), _PIEL, borde=False))
    formas += [
        _elipse((104, 98, 116, 114), estilo.TINTA, borde=False),
        _elipse((140, 98, 152, 114), estilo.TINTA, borde=False),
        _linea([(112, 134), (128, 142), (144, 134)], estilo.TINTA, 5, borde=False),
    ]
    return formas


def _formas_retrato(rol):
    color_rol = estilo.COLORES_ROL_PROPUESTOS[rol]
    if rol == "ciudadano":   # gorra
        return _busto(color_rol) + [
            _elipse((72, 28, 184, 104), (230, 90, 70)),
            _rect((120, 86, 230, 106), 10, (230, 90, 70)),
        ]
    if rol == "periodista":   # libreta
        return _busto(color_rol) + [
            _rect((150, 176, 238, 256), 8, estilo.PAPEL),
            _linea([(164, 198), (224, 198)], estilo.TINTA, 5, borde=False),
            _linea([(164, 218), (224, 218)], estilo.TINTA, 5, borde=False),
            _linea([(164, 238), (204, 238)], estilo.TINTA, 5, borde=False),
        ]
    if rol == "influencer":   # teléfono para el selfie
        return _busto(color_rol) + [
            _rect((176, 112, 238, 214), 12, estilo.TINTA),
            _rect((184, 124, 230, 194), 6, estilo.ACENTO_SECUNDARIO, borde=False),
        ]
    # candidato: banda cruzada y corbatín
    return _busto(color_rol) + [
        _poligono([(40, 190), (84, 176), (228, 320), (190, 340)], estilo.ACENTO_PRIMARIO),
        _poligono([(128, 186), (96, 170), (96, 202)], _ROJO_CORBATIN),
        _poligono([(128, 186), (160, 170), (160, 202)], _ROJO_CORBATIN),
        _elipse((120, 178, 136, 194), _ROJO_CORBATIN),
    ]


# Formas (datos) del icono `nombre`; KeyError si no existe.
def formas_icono(nombre):
    return _FORMAS_ICONO[nombre]()


# Formas (datos) del retrato de `rol`; KeyError si no existe.
def formas_retrato(rol):
    return _formas_retrato(rol)


# Dibuja una forma en una máscara «L» de 256x256.
def _mascara(forma):
    mascara = Image.new("L", (LADO_BASE, LADO_BASE), 0)
    pincel = ImageDraw.Draw(mascara)
    tipo, geometria = forma[0], forma[1]
    if tipo == "rect":
        pincel.rounded_rectangle(geometria[:4], radius=geometria[4], fill=255)
    elif tipo == "elipse":
        pincel.ellipse(geometria, fill=255)
    elif tipo == "poligono":
        pincel.polygon(list(geometria), fill=255)
    elif tipo == "linea":
        grosor = forma[4]
        pincel.line(list(geometria), fill=255, width=grosor, joint="curve")
        for x, y in (geometria[0], geometria[-1]):   # puntas redondeadas
            pincel.ellipse((x - grosor / 2, y - grosor / 2, x + grosor / 2, y + grosor / 2), fill=255)
    else:
        raise ValueError(f"forma desconocida: {tipo}")
    return mascara


# Compone las formas sobre un lienzo transparente de 256 px.
def _componer(formas):
    lienzo = Image.new("RGBA", (LADO_BASE, LADO_BASE), (0, 0, 0, 0))
    tinta = Image.new("RGBA", lienzo.size, (*estilo.TINTA, 255))
    for forma in formas:
        mascara = _mascara(forma)
        if forma[3]:
            borde = mascara.filter(ImageFilter.MaxFilter(2 * BORDE_PX + 1))
            lienzo.paste(tinta, (0, 0), borde)
        lienzo.paste(Image.new("RGBA", lienzo.size, (*forma[2], 255)), (0, 0), mascara)
    return lienzo


def _reducir(imagen, lado):
    return imagen.resize((lado, lado), Image.LANCZOS)


# Icono `nombre` del HUD como imagen RGBA de lado x lado (por defecto 64).
def dibujar_icono(nombre, lado=LADO_ICONO):
    return _reducir(_componer(formas_icono(nombre)), lado)


# Retrato de `rol` como imagen RGBA; con gris=True, en escala de grises (rol tomado).
def dibujar_retrato(rol, lado=LADO_RETRATO, gris=False):
    imagen = _reducir(_componer(formas_retrato(rol)), lado)
    if gris:
        alfa = imagen.getchannel("A")
        imagen = Image.merge("RGBA", (*(imagen.convert("L").point(lambda v: int(v * 0.6)),) * 3, alfa))
    return imagen


_CACHE_TEXTURAS = {}


def _textura(clave, hacer_imagen):
    if clave not in _CACHE_TEXTURAS:
        from ursina import Texture
        textura = Texture(hacer_imagen())
        textura.filtering = "bilinear"
        _CACHE_TEXTURAS[clave] = textura
    return _CACHE_TEXTURAS[clave]


# Textura Ursina (en caché) del icono `nombre`.
def textura_icono(nombre):
    return _textura(("icono", nombre), lambda: dibujar_icono(nombre))


# Textura Ursina (en caché) del retrato de `rol`.
def textura_retrato(rol, gris=False):
    return _textura(("retrato", rol, bool(gris)), lambda: dibujar_retrato(rol, gris=gris))

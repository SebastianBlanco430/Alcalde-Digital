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
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

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


# `borde`: True = contorno de tinta de BORDE_PX; un número = contorno redondeado de ese grosor (px a 256);
# False = sin contorno. `recorte` (opcional): forma ("elipse"|"poligono"|"rect", geometría) que limita dónde se dibuja.
def _rect(caja, radio, relleno, borde=True, recorte=None):
    return _con_recorte(("rect", (*caja, radio), relleno, borde), recorte)


def _elipse(caja, relleno, borde=True, recorte=None):
    return _con_recorte(("elipse", caja, relleno, borde), recorte)


def _poligono(puntos, relleno, borde=True, recorte=None):
    return _con_recorte(("poligono", tuple(puntos), relleno, borde), recorte)


def _linea(puntos, relleno, grosor, borde=True):
    return ("linea", tuple(puntos), relleno, borde, grosor)


def _con_recorte(forma, recorte):
    return forma if recorte is None else forma + (recorte,)


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


# -- Retratos de rol: cara de cómic con contorno grueso de tinta (mismo lenguaje que las caras 3D) --
# Se dibujan a 256 px dejando un margen interno de >= 20 px por arriba y por los lados, para que ni el borde
# de tinta ni el recorte superior de la tarjeta (escena_seleccion_rol.RECORTE_RETRATO) corten el dibujo.

_TINTA = estilo.TINTA
_GRUESO = 7           # px (a 256) del contorno grueso del retrato: 3,5 px en el retrato final
_BLANCO_OJO = (252, 250, 244)
_ROSA_MEJILLA = (240, 132, 120)
_CABEZA = (64, 48, 192, 210)      # elipse de la cabeza


# Puntos de un óvalo (para trazar aros de gafas con una polilínea cerrada).
def _puntos_ovalo(cx, cy, rx, ry, n=22, desde=0.0, hasta=360.0):
    puntos = []
    for i in range(n + 1):
        a = math.radians(desde + (hasta - desde) * i / n)
        puntos.append((round(cx + rx * math.cos(a), 1), round(cy + ry * math.sin(a), 1)))
    return puntos


def _tono(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


# Cabeza común: orejas, cabeza con media luna de sombra (banda de luz de 2 tonos), cuello y mejillas.
def _cabeza_comic(piel, rubor=True):
    sombra = _tono(piel, 0.82)
    cabeza = ("elipse", _CABEZA)
    formas = [
        _rect((106, 186, 150, 246), 12, sombra, _GRUESO),                       # cuello
        _elipse((52, 114, 78, 160), _tono(piel, 0.93), _GRUESO),               # orejas
        _elipse((178, 114, 204, 160), _tono(piel, 0.93), _GRUESO),
        _elipse(_CABEZA, sombra, _GRUESO),                                      # cabeza en sombra...
        _elipse((60, 44, 176, 198), piel, False, cabeza),                      # ...con la cara en luz (clip)
    ]
    if rubor:
        formas += [_elipse((72, 160, 100, 180), _ROSA_MEJILLA, False, cabeza),
                   _elipse((156, 160, 184, 180), _ROSA_MEJILLA, False, cabeza)]
    return formas


# Ojos grandes con esclerótica, iris, pupila y brillo. `guino` cierra el ojo derecho del dibujo con un arco.
def _ojos_comic(iris, guino=False, mirada=(0, 0)):
    formas = []
    for lado, (x0, x1) in enumerate(((86, 122), (134, 170))):
        if guino and lado == 1:
            formas.append(_linea(_puntos_ovalo(152, 140, 18, 12, 10, 200, 340), _TINTA, 9, borde=False))
            continue
        formas.append(_elipse((x0, 112, x1, 150), _BLANCO_OJO, _GRUESO - 2))
        cx = (x0 + x1) // 2 + mirada[0]
        formas.append(_elipse((cx - 11, 122 + mirada[1], cx + 11, 148 + mirada[1]), iris, False,
                              ("elipse", (x0, 112, x1, 150))))
        formas.append(_elipse((cx - 6, 128 + mirada[1], cx + 6, 144 + mirada[1]), (20, 18, 26), False))
        formas.append(_elipse((cx - 8, 126 + mirada[1], cx - 1, 133 + mirada[1]), (255, 255, 255), False))
        formas.append(_linea([(x0 - 2, 126), (x0 + 12, 112), ((x0 + x1) // 2 + 4, 108), (x1 + 2, 118)],
                             _TINTA, 8, borde=False))                           # párpado superior: mirada de cómic
    return formas


def _cejas_comic(color, izq=(-6, 0), der=(0, -6), grosor=13):
    # Dos cejas gruesas de tinta (`izq`/`der`: elevación en px del extremo exterior/interior de cada una).
    return [
        _linea([(80, 100 + izq[0]), (104, 94 + izq[1] // 2), (126, 96 + izq[1])], color, grosor, borde=False),
        _linea([(130, 96 + der[1]), (152, 94 + der[1] // 2), (176, 100 + der[0])], color, grosor, borde=False),
    ]


# Nariz con sombra y arrugas de trazo de la sonrisa.
def _nariz_comic(piel, trazos=True):
    formas = [
        _elipse((111, 150, 145, 172), _tono(piel, 0.85), False, ("elipse", _CABEZA)),
        _linea([(130, 130), (124, 154), (136, 156)], _TINTA, 6, borde=False),
    ]
    if trazos:
        formas += [_linea([(94, 166), (98, 178)], _TINTA, 4, borde=False),
                   _linea([(162, 166), (158, 178)], _TINTA, 4, borde=False)]
    return formas


# Boca: "sonrisa" (arco), "grande" (boca abierta con dientes y lengua) o "ladeada" (sonrisa torcida).
def _boca_comic(tipo, color_labio=(150, 44, 52)):
    if tipo == "grande":
        boca = [(96, 168), (160, 168), (152, 196), (128, 204), (104, 196)]
        return [
            _poligono(boca, (255, 252, 246), _GRUESO - 2),
            _poligono([(112, 190), (144, 190), (136, 202), (120, 202)], (232, 96, 104), False, ("poligono", tuple(boca))),
            _linea([(100, 177), (156, 177)], (205, 200, 190), 4, borde=False),
        ]
    if tipo == "ladeada":
        return [_linea([(104, 182), (122, 188), (146, 182), (166, 166)], _TINTA, 9, borde=False),
                _linea([(166, 166), (172, 160)], _TINTA, 6, borde=False)]
    return [_linea([(100, 172), (112, 186), (128, 190), (144, 186), (156, 172)], _TINTA, 9, borde=False)]


def _trazos_comic(izquierda=True):
    # Líneas de trazo de las mejillas y la frente: aspecto dibujado a mano.
    return [_linea([(70, 186), (80, 192)], _TINTA, 4, borde=False),
            _linea([(76, 178), (86, 186)], _TINTA, 4, borde=False),
            _linea([(186, 186), (176, 192)], _TINTA, 4, borde=False)]


def _cuerpo_comic(rgb_rol, cuello_en_v=True):
    return [_elipse((14, 214, 242, 392), rgb_rol, _GRUESO),
            _linea([(104, 226), (128, 252), (152, 226)], _TINTA, 6, borde=False)] if cuello_en_v else [
        _elipse((14, 214, 242, 392), rgb_rol, _GRUESO)]


def _formas_retrato_periodista(rgb_rol):
    piel, pelo = (236, 188, 140), (112, 66, 36)
    gafas = (24, 26, 40)
    return (_cuerpo_comic(rgb_rol) + [
                _elipse((196, 120, 214, 156), pelo, _GRUESO - 2),
            ] + _cabeza_comic(piel) + [
                _elipse((56, 30, 200, 112), pelo, _GRUESO),                      # pelo con volumen y flequillo
                _poligono([(76, 100), (60, 66), (120, 50), (186, 64), (196, 100), (170, 72), (120, 80)], pelo, False),
                _elipse((84, 34, 150, 62), (160, 98, 56), False, ("elipse", (56, 30, 200, 112))),   # luz del pelo
                _linea([(94, 44), (130, 40)], (190, 128, 80), 6, borde=False),
            ] + _ojos_comic((40, 110, 96), mirada=(2, 0)) + _cejas_comic(pelo, izq=(0, 2), der=(2, -10), grosor=14)
            + _nariz_comic(piel) + _boca_comic("ladeada") + [
                _linea(_puntos_ovalo(104, 131, 23, 23, 20), gafas, 7, borde=False),   # gafas redondas de montura gruesa
                _linea(_puntos_ovalo(152, 131, 23, 23, 20), gafas, 7, borde=False),
                _linea([(127, 127), (129, 127)], gafas, 6, borde=False),
                _linea([(81, 127), (62, 122)], gafas, 6, borde=False),
                _poligono([(34, 108), (50, 96), (56, 106), (40, 120)], (250, 204, 40), _GRUESO - 3),   # lápiz tras la oreja
                _poligono([(34, 108), (28, 120), (40, 120)], (250, 160, 170), False),
            ] + _trazos_comic() + [
                _rect((150, 190, 244, 270), 8, estilo.PAPEL, _GRUESO - 2),
                _linea([(164, 212), (228, 212)], _TINTA, 5, borde=False),
                _linea([(164, 230), (228, 230)], _TINTA, 5, borde=False),
                _linea([(164, 248), (206, 248)], _TINTA, 5, borde=False),
            ])


# Influencer = la brasileña del modelo 3D: piel oscura, afro rizado grande, camiseta corta verde con la bandera
# de Brasil (rombo amarillo y círculo azul), aros y collar dorados y sonrisa.
def _formas_retrato_influencer(rgb_rol):
    piel, pelo, pelo_luz = (120, 76, 52), (34, 24, 22), (88, 62, 46)
    verde, verde_osc, oro = (0, 156, 82), (0, 112, 60), (250, 206, 60)
    afro = [  # nube de rizos: una masa grande y bolas de pelo alrededor (detrás de cabeza y hombros)
        _elipse((26, 30, 230, 196), pelo, _GRUESO),
    ] + [_elipse(c, pelo, _GRUESO) for c in (
        (16, 66, 80, 134), (176, 66, 240, 134), (14, 120, 76, 186), (180, 120, 242, 186),
        (30, 30, 98, 84), (158, 30, 226, 84), (78, 22, 178, 66), (26, 164, 70, 204), (186, 164, 230, 204))]
    luces = [_elipse(c, pelo_luz, False) for c in ((56, 40, 96, 66), (150, 42, 190, 66), (38, 88, 62, 116))]
    cuerpo = [
        _elipse((14, 214, 242, 392), verde, _GRUESO),                                 # camiseta corta verde
        _elipse((14, 214, 130, 300), verde_osc, False, ("elipse", (14, 214, 242, 392))),   # media luna de sombra
        _poligono([(96, 226), (128, 262), (160, 226), (160, 256), (96, 256)], _tono(piel, 0.82), False),   # escote
        _linea([(96, 226), (128, 262), (160, 226)], oro, 6, borde=False),            # ribete dorado del cuello
        _poligono([(190, 226), (232, 246), (190, 268), (148, 246)], oro, _GRUESO - 3,
                  ("elipse", (14, 214, 242, 392))),                                  # rombo de la bandera (en el hombro)
        _elipse((177, 234, 203, 258), (40, 80, 190), False,
                ("elipse", (14, 214, 242, 392))),                                    # círculo azul
    ]
    collar = [_linea(_puntos_ovalo(128, 214, 30, 40, 12, 20, 160), oro, 5, borde=False),
              _elipse((122, 250, 134, 262), oro, _GRUESO - 4)]
    aros = [_linea(_puntos_ovalo(60, 176, 10, 16, 14), oro, 6, borde=False),
            _linea(_puntos_ovalo(196, 176, 10, 16, 14), oro, 6, borde=False)]
    flequillo = [_elipse((62, 38, 130, 96), pelo, _GRUESO - 3), _elipse((112, 34, 192, 94), pelo, _GRUESO - 3),
                 _elipse((70, 44, 100, 64), pelo_luz, False), _elipse((142, 46, 172, 64), pelo_luz, False)]
    return (afro + luces + cuerpo + _cabeza_comic(piel) + collar + flequillo
            + _ojos_comic((70, 40, 24)) + _cejas_comic(pelo, izq=(-2, 2), der=(-2, 2), grosor=11)
            + _nariz_comic(piel) + _boca_comic("sonrisa", (150, 44, 52)) + aros + _trazos_comic())


# Ciudadano = el modelo 3D nuevo: hombre delgado sin camisa (trazos de tinta en el torso, clavículas), pelo corto
# negro. El pantalón corto azul queda fuera del busto.
def _formas_retrato_ciudadano(rgb_rol):
    piel, pelo, pelo_luz = (150, 102, 70), (26, 20, 20), (70, 54, 48)
    sombra = _tono(piel, 0.8)
    torso = [
        _elipse((14, 214, 242, 392), piel, _GRUESO),                                  # hombros y pecho al descubierto
        _elipse((14, 214, 120, 330), sombra, False, ("elipse", (14, 214, 242, 392))),     # media luna de sombra
        _linea([(60, 236), (100, 230), (122, 238)], _TINTA, 5, borde=False),         # clavículas
        _linea([(134, 238), (156, 230), (196, 236)], _TINTA, 5, borde=False),
        _linea([(128, 252), (128, 256)], _TINTA, 5, borde=False),                    # hueco del esternón
        _linea([(92, 250), (104, 256)], _TINTA, 4, borde=False),                     # trazos de tinta del torso
        _linea([(164, 250), (152, 256)], _TINTA, 4, borde=False),
    ]
    pelo_corto = [
        _elipse((58, 30, 198, 104), pelo, _GRUESO),                                   # pelo corto negro
        _elipse((72, 38, 130, 62), pelo_luz, False, ("elipse", (58, 30, 198, 104))),
        _poligono([(64, 110), (60, 84), (76, 90), (78, 112)], pelo, False),          # patillas
        _poligono([(192, 110), (196, 84), (180, 90), (178, 112)], pelo, False),
        _poligono([(78, 96), (128, 84), (178, 96), (170, 80), (128, 70), (86, 80)], pelo, False),   # flequillo corto
    ]
    return (torso + _cabeza_comic(piel) + pelo_corto
            + _ojos_comic((60, 38, 26)) + _cejas_comic(pelo, izq=(0, 2), der=(0, 2), grosor=11)
            + _nariz_comic(piel) + _boca_comic("sonrisa") + _trazos_comic())


def _formas_retrato_candidato(rgb_rol):
    piel, pelo = (176, 118, 84), (28, 24, 32)
    return (_cuerpo_comic(rgb_rol, cuello_en_v=False) + [
                _poligono([(22, 240), (74, 224), (178, 262), (96, 262)], estilo.ACENTO_PRIMARIO, _GRUESO - 2),  # banda
            ] + _cabeza_comic(piel, rubor=False) + [
                _elipse((56, 34, 200, 112), pelo, _GRUESO),                       # pelo negro peinado hacia atrás
                _linea([(84, 52), (140, 40), (184, 54)], (110, 120, 150), 6, borde=False),
            ] + _ojos_comic((64, 40, 26)) + _cejas_comic(pelo, izq=(0, 4), der=(0, -4), grosor=15) + _nariz_comic(piel, trazos=False) + [
                _poligono([(96, 168), (112, 160), (128, 166), (144, 160), (160, 168), (144, 178), (128, 172), (112, 178)],
                          pelo, _GRUESO - 3),                                      # bigote
                _linea([(108, 190), (128, 196), (148, 190)], (60, 20, 24), 7, borde=False),
                _linea([(70, 128), (60, 122)], _TINTA, 4, borde=False),             # arrugas de carácter
                _linea([(70, 138), (60, 140)], _TINTA, 4, borde=False),
                _linea([(186, 128), (196, 122)], _TINTA, 4, borde=False),
                _linea([(186, 138), (196, 140)], _TINTA, 4, borde=False),
                _poligono([(128, 250), (96, 232), (96, 268)], _ROJO_CORBATIN, _GRUESO - 3),   # corbatín
                _poligono([(128, 250), (160, 232), (160, 268)], _ROJO_CORBATIN, _GRUESO - 3),
                _elipse((118, 240, 138, 260), _ROJO_CORBATIN, _GRUESO - 3),
            ])


_FORMAS_ROL = {
    "ciudadano": _formas_retrato_ciudadano,
    "periodista": _formas_retrato_periodista,
    "influencer": _formas_retrato_influencer,
    "candidato": _formas_retrato_candidato,
}


def _formas_retrato(rol):
    return _FORMAS_ROL[rol](estilo.COLORES_ROL_PROPUESTOS[rol])


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


# Forma que limita el dibujo de `forma` (su último elemento opcional), o None.
def _recorte_de(forma):
    posicion = 5 if forma[0] == "linea" else 4
    return forma[posicion] if len(forma) > posicion else None


# Engrosa una máscara `grosor` px en todas las direcciones con esquinas redondas.
def _dilatar_redondo(mascara, grosor):
    desenfocada = mascara.filter(ImageFilter.GaussianBlur(grosor / 2.0))
    return desenfocada.point(lambda v: 255 if v > 6 else 0)


# Compone las formas sobre un lienzo transparente de 256 px.
def _componer(formas):
    lienzo = Image.new("RGBA", (LADO_BASE, LADO_BASE), (0, 0, 0, 0))
    tinta = Image.new("RGBA", lienzo.size, (*estilo.TINTA, 255))
    for forma in formas:
        mascara = _mascara(forma)
        recorte = _recorte_de(forma)
        if recorte is not None:
            mascara = ImageChops.multiply(mascara, _mascara(recorte))
        if forma[3]:
            if forma[3] is True:
                borde = mascara.filter(ImageFilter.MaxFilter(2 * BORDE_PX + 1))
            else:                                     # contorno redondeado de `forma[3]` px (desenfoque + umbral)
                borde = _dilatar_redondo(mascara, int(forma[3]))
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

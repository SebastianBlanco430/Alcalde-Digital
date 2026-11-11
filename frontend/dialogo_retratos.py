# Retratos de los personajes de los casos, dibujados por código (sin arte externo ni disco), con 2-3 expresiones por
# personaje. Usa las mismas piezas de cómic que frontend/iconos.py (cabeza, ojos, cejas, nariz, cuerpo, contorno de
# tinta). El JSON del caso define a cada personaje en `retrato`:
#   {"piel": [r,g,b], "pelo": [r,g,b], "pelo_estilo": "corto|largo|calvo", "ropa": [r,g,b],
#    "accesorio": "ninguno|gafas|barba|corbata", "expresiones": ["neutral", ...]}
# y cada nodo nombra la `expresion` que usa. Un nombre desconocido cae a «neutral» (nunca rompe la escena).
#
# Capa pura: formas_retrato_caso (datos) y dibujar_retrato_caso (imagen Pillow). Capa Ursina: textura_retrato_caso
# (importa ursina solo al usarse; caché en memoria).

import json

from frontend import iconos
from frontend.iconos import (_TINTA, _GRUESO, _cabeza_comic, _cejas_comic, _cuerpo_comic, _elipse, _linea, _nariz_comic,
                             _ojos_comic, _poligono, _puntos_ovalo, _rect, _tono)

LADO_RETRATO_CASO = 192

# Cada expresión: elevación (px) de las cejas [exterior, interior] de cada lado, mirada de los ojos, boca y adorno.
EXPRESIONES = {
    "neutral": {"cejas": (0, 0), "mirada": (0, 0), "boca": "suave", "extra": None},
    "serio": {"cejas": (0, 3), "mirada": (0, 0), "boca": "recta", "extra": None},
    "nervioso": {"cejas": (4, -10), "mirada": (-5, 3), "boca": "ondulada", "extra": "sudor"},
    "enojado": {"cejas": (-6, 10), "mirada": (0, 1), "boca": "ceño", "extra": "vena"},
    "satisfecho": {"cejas": (-3, -2), "mirada": (0, 0), "boca": "sonrisa", "extra": None},
    "triste": {"cejas": (6, -8), "mirada": (0, 4), "boca": "triste", "extra": None},
    "sorprendido": {"cejas": (-12, -12), "mirada": (0, -2), "boca": "o", "extra": None},
}
EXPRESION_BASE = "neutral"
ESTILOS_PELO = ("corto", "largo", "calvo")
ACCESORIOS = ("ninguno", "gafas", "barba", "corbata")

_PIEL = (240, 200, 160)
_PELO = (60, 44, 40)
_ROPA = (90, 110, 170)
_IRIS = (60, 40, 26)
_ROJO = (214, 62, 62)


def _rgb(valor, defecto):
    try:
        r, g, b = (max(0, min(255, int(c))) for c in valor)
        return (r, g, b)
    except (TypeError, ValueError):
        return defecto


def expresion_o_base(nombre):
    return nombre if nombre in EXPRESIONES else EXPRESION_BASE


def _boca(tipo):
    if tipo == "suave":
        return [_linea([(106, 184), (128, 188), (150, 184)], _TINTA, 8, borde=False)]
    if tipo == "recta":
        return [_linea([(104, 185), (152, 185)], _TINTA, 9, borde=False)]
    if tipo == "ondulada":
        return [_linea([(100, 187), (112, 180), (124, 189), (136, 180), (148, 189), (156, 183)], _TINTA, 7, borde=False)]
    if tipo == "ceño":
        return [_linea(_puntos_ovalo(128, 206, 28, 16, 14, 200, 340), _TINTA, 10, borde=False)]
    if tipo == "triste":
        return [_linea(_puntos_ovalo(128, 202, 22, 12, 12, 205, 335), _TINTA, 8, borde=False)]
    if tipo == "o":
        return [_elipse((116, 174, 140, 202), (90, 30, 40), _GRUESO - 3)]
    return iconos._boca_comic("sonrisa")


def _extra(tipo):
    if tipo == "sudor":
        return [_poligono([(186, 56), (198, 82), (186, 96), (174, 82)], (120, 200, 250), _GRUESO - 3)]
    if tipo == "vena":
        return [_linea([(170, 60), (182, 72)], _ROJO, 7, borde=False), _linea([(182, 60), (170, 72)], _ROJO, 7, borde=False),
                _linea([(166, 66), (174, 66)], _ROJO, 5, borde=False), _linea([(178, 56), (178, 64)], _ROJO, 5, borde=False)]
    return []


def _pelo_detras(estilo_pelo, pelo):
    if estilo_pelo == "largo":
        return [_elipse((38, 40, 218, 236), pelo, _GRUESO), _rect((44, 150, 212, 252), 24, pelo, _GRUESO)]
    return []


def _pelo_delante(estilo_pelo, pelo):
    luz = _tono(pelo, 1.6)
    if estilo_pelo == "calvo":
        return [_elipse((60, 36, 196, 70), _tono(pelo, 1.0), False, ("elipse", (64, 48, 192, 210)))]
    base = [_elipse((56, 24, 200, 90), pelo, _GRUESO),
            _elipse((72, 32, 130, 54), luz, False, ("elipse", (56, 24, 200, 90))),
            _poligono([(78, 84), (128, 74), (178, 84), (170, 68), (128, 58), (86, 68)], pelo, False)]
    if estilo_pelo == "largo":
        base += [_poligono([(62, 108), (56, 170), (74, 176), (76, 112)], pelo, False),
                 _poligono([(194, 108), (200, 170), (182, 176), (180, 112)], pelo, False)]
    return base


def _accesorios(accesorio, pelo, ropa):
    if accesorio == "gafas":
        gafas = (24, 26, 40)
        return [_linea(_puntos_ovalo(104, 131, 23, 21, 20), gafas, 7, borde=False),
                _linea(_puntos_ovalo(152, 131, 23, 21, 20), gafas, 7, borde=False),
                _linea([(127, 127), (129, 127)], gafas, 6, borde=False)]
    if accesorio == "corbata":
        return [_poligono([(128, 244), (116, 258), (122, 330), (128, 340), (134, 330), (140, 258)], _ROJO, _GRUESO - 3)]
    return []


def _barba(accesorio, pelo):
    if accesorio != "barba":
        return []
    return [_poligono([(66, 150), (74, 198), (128, 226), (182, 198), (190, 150), (172, 178), (128, 184), (84, 178)],
                      _tono(pelo, 1.0), _GRUESO - 2)]


# Formas (datos) del retrato descrito por el dict `retrato` del JSON, con la `expresion` pedida.
def formas_retrato_caso(retrato, expresion):
    retrato = retrato if isinstance(retrato, dict) else {}
    expr = EXPRESIONES[expresion_o_base(expresion)]
    piel, pelo, ropa = (_rgb(retrato.get("piel"), _PIEL), _rgb(retrato.get("pelo"), _PELO),
                        _rgb(retrato.get("ropa"), _ROPA))
    estilo_pelo = retrato.get("pelo_estilo") if retrato.get("pelo_estilo") in ESTILOS_PELO else "corto"
    accesorio = retrato.get("accesorio") if retrato.get("accesorio") in ACCESORIOS else "ninguno"
    ceja_ext, ceja_int = expr["cejas"]
    barba = _barba(accesorio, pelo)
    return (_pelo_detras(estilo_pelo, pelo) + _cuerpo_comic(ropa) + _accesorios(
        "corbata" if accesorio == "corbata" else "ninguno", pelo, ropa)
        + _cabeza_comic(piel, rubor=expr["boca"] != "ceño") + _pelo_delante(estilo_pelo, pelo) + barba
        + _ojos_comic(_IRIS, mirada=expr["mirada"])
        + _cejas_comic(_TINTA, izq=(ceja_ext, ceja_int), der=(ceja_ext, ceja_int), grosor=12)
        + _nariz_comic(piel, trazos=False) + _boca(expr["boca"]) + _accesorios(
        "gafas" if accesorio == "gafas" else "ninguno", pelo, ropa) + _extra(expr["extra"]))


def dibujar_retrato_caso(retrato, expresion, lado=LADO_RETRATO_CASO):
    return iconos._reducir(iconos._componer(formas_retrato_caso(retrato, expresion)), lado)


_CACHE = {}


# Textura Ursina (en caché) del retrato; la clave incluye todo el dict del personaje, así dos personajes distintos
# nunca comparten dibujo.
def textura_retrato_caso(retrato, expresion):
    nombre = expresion_o_base(expresion)
    clave = (json.dumps(retrato, sort_keys=True, ensure_ascii=False), nombre)
    if clave not in _CACHE:
        from ursina import Texture
        textura = Texture(dibujar_retrato_caso(retrato, nombre))
        textura.filtering = "bilinear"
        _CACHE[clave] = textura
    return _CACHE[clave]


# Texto de apoyo para accesibilidad: la expresión como palabra (se muestra junto al nombre del personaje).
def descripcion_expresion(expresion):
    return expresion_o_base(expresion)

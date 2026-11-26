# Iconos de los botones del MANDO (texturas PIL con la piel BOTW: círculo de tinta con filo claro y letra de color) y el
# cartel que avisa al conectar o desconectar un mando. Los iconos solo se usan en el esquema del mando de Ajustes
# (frontend/mando_ajustes.py): las ayudas de las pantallas siguen nombrando las teclas.
#
# Lo llama frontend/mando.py al detectar que se conecta o se desconecta un mando: con el mando el juego se maneja con
# él (mando.py traduce sus botones a teclas); sin él, teclado y ratón como siempre. Aquí solo se avisa.
# BANDERA: ALCALDE_MANDO_ICONOS=0 quita el cartel (el esquema de Ajustes sigue).

import os
import sys


MANDO_ICONOS = True
VARIABLE = "ALCALDE_MANDO_ICONOS"
LADO_PX = 64
SEGUNDOS_CARTEL = 2.6

_estado = {"mando": False, "texturas": False, "cartel": None}
PREFIJO_ICONO = "mando_"
ICONOS = ("a", "b", "x", "y", "lb", "rb", "lt", "rt", "back", "start", "l3", "r3", "palo_izq", "palo_der",
          "dpad", "dpad_arriba", "dpad_abajo", "dpad_izq", "dpad_der")

# Color de la letra de cada botón (como los mandos de siempre) y el texto de los que llevan nombre.
_LETRAS = {"a": ("A", (96, 200, 92)), "b": ("B", (232, 84, 76)), "x": ("X", (76, 150, 240)), "y": ("Y", (255, 210, 60)),
           "l3": ("L", (237, 231, 255)), "r3": ("R", (237, 231, 255))}
_PASTILLAS = {"lb": "LB", "rb": "RB", "lt": "LT", "rt": "RT"}


def activo():
    valor = os.environ.get(VARIABLE, "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    return MANDO_ICONOS


def hay_mando():
    return _estado["mando"]


# -- Texturas --

def _fuente(px):
    from PIL import ImageFont
    from frontend import tipografia
    try:
        from ursina import application
        ruta = next(iter(application.asset_folder.glob(f"**/{tipografia.FUENTE_TITULO}")), None)
        if ruta is None:
            ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fuentes",
                                tipografia.FUENTE_TITULO)
        return ImageFont.truetype(str(ruta), px)
    except Exception:                            # noqa: BLE001
        return ImageFont.load_default()


def _dibujar(icono, s=4):
    """Imagen PIL (LADO_PX x LADO_PX, dibujada a `s` veces y reducida para que los bordes salgan suaves)."""
    from PIL import Image, ImageDraw
    from frontend import estilo
    n = LADO_PX * s
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tinta, filo, amarillo = (*estilo.BOTW_TINTA, 255), (*estilo.BOTW_FILO, 255), (*estilo.BOTW_ACENTO, 255)
    m, grosor = 3 * s, 4 * s

    def centrado(texto, px, tono):
        f = _fuente(px * s)
        caja = d.textbbox((0, 0), texto, font=f)
        d.text(((n - (caja[2] - caja[0])) / 2 - caja[0], (n - (caja[3] - caja[1])) / 2 - caja[1]), texto, font=f,
               fill=(*tono, 255))

    if icono in _LETRAS:
        letra, tono = _LETRAS[icono]
        d.ellipse((m, m, n - m, n - m), fill=tinta, outline=filo, width=grosor)
        if icono in ("l3", "r3"):                # palo pulsado: anillo interior
            d.ellipse((m + 9 * s, m + 9 * s, n - m - 9 * s, n - m - 9 * s), outline=(*tono, 160), width=2 * s)
        centrado(letra, 34, tono)
    elif icono in _PASTILLAS:
        arriba = icono in ("lt", "rt")           # gatillo: más alto y redondeado por arriba
        caja = (m, m + (6 if arriba else 12) * s, n - m, n - m - (6 if arriba else 12) * s)
        d.rounded_rectangle(caja, radius=(18 if arriba else 12) * s, fill=tinta, outline=filo, width=grosor)
        centrado(_PASTILLAS[icono], 24, estilo.BOTW_FILO)
    elif icono in ("start", "back"):
        d.ellipse((m, m, n - m, n - m), fill=tinta, outline=filo, width=grosor)
        c = n / 2
        if icono == "start":                     # tres rayas
            for dy in (-9, 0, 9):
                d.line((c - 12 * s, c + dy * s, c + 12 * s, c + dy * s), fill=filo, width=4 * s)
        else:                                    # dos ventanas
            d.rectangle((c - 13 * s, c - 11 * s, c + 3 * s, c + 3 * s), outline=filo, width=3 * s)
            d.rectangle((c - 3 * s, c - 3 * s, c + 13 * s, c + 11 * s), fill=tinta, outline=filo, width=3 * s)
    elif icono in ("palo_izq", "palo_der"):
        d.ellipse((m, m, n - m, n - m), fill=tinta, outline=filo, width=grosor)
        c, r = n / 2, 7 * s
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):   # puntas de las cuatro direcciones
            x, y = c + dx * 19 * s, c + dy * 19 * s
            d.polygon([(x + dy * r + dx * r, y + dx * r + dy * r), (x - dy * r * 0.8 - dx * r * 0.2, y - dx * r * 0.8 - dy * r * 0.2),
                       (x + dy * r * 0.8 - dx * r * 0.2, y + dx * r * 0.8 - dy * r * 0.2)], fill=filo)
        centrado("L" if icono == "palo_izq" else "R", 22, estilo.BOTW_FILO)
    else:                                        # cruceta; el brazo de la dirección en amarillo
        c, b, l = n / 2, 11 * s, n / 2 - m
        brazos = {"dpad_arriba": (c - b, c - l, c + b, c - b), "dpad_abajo": (c - b, c + b, c + b, c + l),
                  "dpad_izq": (c - l, c - b, c - b, c + b), "dpad_der": (c + b, c - b, c + l, c + b)}
        d.rectangle((c - b, c - l, c + b, c + l), fill=filo)
        d.rectangle((c - l, c - b, c + l, c + b), fill=filo)
        d.rectangle((c - b + grosor, c - l + grosor, c + b - grosor, c + l - grosor), fill=tinta)
        d.rectangle((c - l + grosor, c - b + grosor, c + l - grosor, c + b - grosor), fill=tinta)
        if icono in brazos:
            x0, y0, x1, y1 = brazos[icono]
            d.rectangle((x0 + grosor, y0 + grosor, x1 - grosor, y1 - grosor), fill=amarillo)
    return img.resize((LADO_PX, LADO_PX), Image.LANCZOS)


_texturas = {}


def textura(icono):
    """Textura de Ursina del icono (se dibuja una vez y se guarda)."""
    if icono not in _texturas:
        from ursina import Texture
        t = Texture(_dibujar(icono))
        t.filtering = "mipmap"
        _texturas[icono] = t
    return _texturas[icono]


# Entidad con el icono, hija de `padre` (lado en unidades del padre).
def icono_en(padre, icono, lado, posicion):
    from ursina import Entity
    return Entity(parent=padre, model="quad", texture=textura(icono), scale=(lado, lado), position=posicion)


# -- Cartel --

def _cartel(texto):
    from ursina import Entity, Func, Sequence, Text, Wait, camera, destroy
    from frontend import estilo, tipografia
    from frontend.componentes import escala_fuente, panel_piel, rgb
    viejo = _estado["cartel"]
    if viejo is not None and not viejo.is_empty():
        destroy(viejo)
    raiz = Entity(parent=camera.ui, z=-0.9, position=(0, -0.38), eternal=True)
    t = Text(texto, parent=raiz, origin=(0, 0), z=-0.01, scale=escala_fuente(20), font=tipografia.FUENTE_TITULO,
             color=rgb(estilo.BOTW_FILO))
    # el panel se ajusta al texto (más un margen) para que nunca se salga
    panel_piel(raiz, max(0.4, t.width * t.scale_x + 0.08), 0.075, z=0)
    _estado["cartel"] = raiz

    def quitar():
        if not raiz.is_empty():
            destroy(raiz)

    Sequence(Wait(SEGUNDOS_CARTEL), Func(quitar), auto_destroy=True, ignore_paused=True).start()


# -- API (frontend/mando.py) --

def fijar_mando(hay, aviso=False):
    """Recuerda si hay mando y, con `aviso`, enseña el cartel del cambio."""
    _estado["mando"] = bool(hay)
    if not aviso or not activo():
        return
    try:
        _cartel("Mando conectado · esquema en Ajustes > Mando" if hay else "Mando desconectado: teclado y ratón")
    except Exception as error:                   # noqa: BLE001
        print(f"[Mando] cartel: {type(error).__name__}: {error}", file=sys.stderr)

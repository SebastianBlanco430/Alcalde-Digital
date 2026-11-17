# Viñetas de historieta para «Ordenar la cadena de difusión» (frontend/minijuegos_visual/cronologia_visual.py).
# Python puro, sin ursina; tests en tests/test_cronologia_vinetas.py.
#
# Cada mensaje de la cadena se dibuja como una VIÑETA: el ESCENARIO sale del caso (la plaza del concierto, la terminal de
# los horarios, la escuela, la feria, la panadería o el barrio) y el PERSONAJE de quién lo dice y cómo (un aviso oficial,
# la radio, una cuenta anónima, un grupo que reenvía, alguien que sube una foto, alguien que duda o un testigo).
# `figuras(...)` devuelve primitivas listas para dibujar, en unidades del ALTO de la viñeta: x en ±ASPECTO/2, y en ±0,5.
#   {"f": "rect" | "circulo" | "tri", "x", "y", "w", "h", "c": (r, g, b), "rot"}   ·   {"f": "texto", "t", "x", "y", "tam", "c"}

ASPECTO = 1.75                     # ancho / alto de cada viñeta

ESCENARIOS = ("plaza", "terminal", "escuela", "feria", "panaderia", "barrio")
ACTORES = ("oficial", "radio", "anonimo", "grupo", "foto", "duda", "testigo")

_POR_CASO = {"k_concierto": "plaza", "k_rodoviaria": "terminal", "k_escuela": "escuela", "k_feira": "feria",
             "k_panaderia": "panaderia", "k_general": "barrio"}
_CLAVES_ESCENARIO = (("plaza", ("concierto", "plaza", "show")), ("terminal", ("terminal", "horario", "bus", "rodovi")),
                     ("escuela", ("escuela", "clase", "colegio")), ("feria", ("feria", "feira", "puesto")),
                     ("panaderia", ("panader", "oferta", "pan "))
                     )

CIELO = {"plaza": (255, 196, 140), "terminal": (150, 196, 235), "escuela": (140, 200, 240), "feria": (255, 220, 150),
         "panaderia": (250, 210, 170), "barrio": (170, 205, 240)}
SUELO = {"plaza": (190, 160, 130), "terminal": (120, 124, 136), "escuela": (110, 176, 100), "feria": (200, 170, 120),
         "panaderia": (180, 150, 120), "barrio": (120, 170, 110)}
TINTA = (24, 22, 30)
PAPEL = (252, 248, 232)
PIELES = ((236, 196, 160), (205, 150, 108), (150, 100, 66), (104, 66, 44))
ROPAS = ((214, 92, 80), (78, 150, 214), (96, 176, 110), (230, 170, 60), (160, 110, 200), (70, 190, 190))


def _hash(texto):
    return sum((i + 1) * ord(c) for i, c in enumerate(str(texto)))


def escenario_de(caso):
    """Escenario de la historieta según el caso (id conocido, o palabras del título); por defecto, el barrio."""
    caso = caso or {}
    if caso.get("id") in _POR_CASO:
        return _POR_CASO[caso["id"]]
    titulo = f" {caso.get('titulo', '')} {caso.get('intro', '')} ".lower()
    for escenario, claves in _CLAVES_ESCENARIO:
        if any(c in titulo for c in claves):
            return escenario
    return "barrio"


def actor_de(item):
    """Qué personaje protagoniza la viñeta de un mensaje (por quién lo dice y qué dice)."""
    quien = str((item or {}).get("quien", "")).lower()
    texto = str((item or {}).get("texto", "")).lower()
    if any(c in quien for c in ("anónim", "anonim", "sin firma", "sin foto", "sin autor", "sin nombre", "sin fecha",
                                "cuenta nueva")):
        return "anonimo"
    if "radio" in quien:
        return "radio"
    if any(c in quien for c in ("aviso", "tablero", "dirección", "direccion", "cartel", "municipal", "oficial",
                                "sellado", "prefeitura")):
        return "oficial"
    if any(c in quien for c in ("grupo", "chat", "mamás", "mamas", "cadena", "cuenta «", "cuenta \"")):
        return "grupo"
    if "foto" in texto:
        return "foto"
    if "?" in texto:
        return "duda"
    return "testigo"


def _r(x, y, w, h, c, rot=0.0):
    return {"f": "rect", "x": x, "y": y, "w": w, "h": h, "c": tuple(c), "rot": rot}


def _o(x, y, w, h, c):
    return {"f": "circulo", "x": x, "y": y, "w": w, "h": h, "c": tuple(c), "rot": 0.0}


def _t(x, y, w, h, c, rot=0.0):
    return {"f": "tri", "x": x, "y": y, "w": w, "h": h, "c": tuple(c), "rot": rot}


def _txt(t, x, y, tam, c=TINTA):
    return {"f": "texto", "t": t, "x": x, "y": y, "tam": tam, "c": tuple(c)}


def _fondo(escenario):
    fig = [_r(0, 0, ASPECTO, 1.0, CIELO[escenario]), _r(0, -0.36, ASPECTO, 0.28, SUELO[escenario])]
    if escenario == "plaza":
        fig += [_r(-0.5, -0.12, 0.62, 0.14, (90, 60, 120)), _r(-0.5, 0.18, 0.66, 0.05, (60, 40, 90)),
                _r(-0.79, 0.02, 0.04, 0.32, (60, 40, 90)), _r(-0.21, 0.02, 0.04, 0.32, (60, 40, 90)),
                _o(-0.62, 0.05, 0.08, 0.08, (255, 230, 120)), _o(-0.38, 0.05, 0.08, 0.08, (255, 230, 120)),
                _o(-0.02, -0.3, 0.26, 0.08, (90, 160, 220)), _r(-0.02, -0.22, 0.03, 0.12, (150, 210, 250))]
    elif escenario == "terminal":
        fig += [_r(-0.42, 0.05, 0.8, 0.5, (196, 200, 210)), _r(-0.42, 0.13, 0.52, 0.2, (30, 34, 44)),
                _r(-0.42, 0.19, 0.42, 0.025, (255, 210, 70)), _r(-0.42, 0.13, 0.42, 0.025, (255, 210, 70)),
                _r(-0.42, 0.07, 0.42, 0.025, (255, 210, 70)),
                _r(-0.36, -0.24, 0.66, 0.2, (240, 140, 50)), _r(-0.36, -0.2, 0.56, 0.07, (170, 220, 250)),
                _o(-0.58, -0.35, 0.09, 0.09, TINTA), _o(-0.14, -0.35, 0.09, 0.09, TINTA)]
    elif escenario == "escuela":
        fig += [_r(-0.42, -0.02, 0.74, 0.44, (200, 110, 90)), _t(-0.42, 0.3, 0.84, 0.18, (150, 70, 60)),
                _r(-0.42, -0.15, 0.12, 0.2, (90, 60, 40)), _r(-0.66, 0.04, 0.12, 0.1, (190, 230, 250)),
                _r(-0.18, 0.04, 0.12, 0.1, (190, 230, 250)), _r(0.04, 0.15, 0.015, 0.5, (90, 90, 100)),
                _r(0.12, 0.33, 0.15, 0.09, (60, 150, 90))]
    elif escenario == "feria":
        for i, (cx, tono) in enumerate(((-0.66, (220, 70, 70)), (-0.36, (70, 140, 220)), (-0.06, (240, 180, 50)))):
            fig += [_r(cx, -0.15, 0.26, 0.16, (170, 120, 80)), _r(cx, 0.03, 0.3, 0.07, tono),
                    _r(cx - 0.08, 0.03, 0.05, 0.07, PAPEL), _r(cx + 0.08, 0.03, 0.05, 0.07, PAPEL),
                    _o(cx - 0.06, -0.06, 0.06, 0.06, (240, 120, 40) if i != 1 else (120, 200, 80)),
                    _o(cx + 0.05, -0.06, 0.06, 0.06, (230, 60, 60) if i != 2 else (250, 220, 80))]
    elif escenario == "panaderia":
        fig += [_r(-0.4, -0.04, 0.8, 0.44, (240, 220, 190)), _r(-0.4, 0.22, 0.86, 0.08, (200, 80, 70)),
                _r(-0.56, -0.06, 0.34, 0.2, (190, 230, 250)), _o(-0.62, -0.1, 0.12, 0.06, (210, 150, 80)),
                _o(-0.5, -0.1, 0.12, 0.06, (200, 140, 70)), _r(-0.16, -0.12, 0.13, 0.24, (120, 80, 50)),
                _txt("PAN", -0.4, 0.22, 0.09, PAPEL)]
    else:  # barrio
        for cx, alto, tono in ((-0.68, 0.36, (230, 180, 90)), (-0.38, 0.46, (120, 170, 210)),
                               (-0.08, 0.32, (210, 120, 150))):
            fig += [_r(cx, -0.22 + alto / 2, 0.26, alto, tono), _t(cx, -0.22 + alto + 0.06, 0.3, 0.12, (150, 70, 60)),
                    _r(cx, -0.14, 0.07, 0.14, (90, 60, 40)), _r(cx, -0.22 + alto * 0.7, 0.08, 0.07, (190, 230, 250))]
    return fig                       # (tests/test_cronologia_vinetas.py comprueba que todo cabe en la viñeta)


def _persona(x, quien, extra=()):
    k = _hash(quien)
    ropa, piel = ROPAS[k % len(ROPAS)], PIELES[(k // 7) % len(PIELES)]
    pelo = ((40, 30, 28), (90, 56, 34), (200, 160, 80), (30, 30, 40))[(k // 3) % 4]
    return [_r(x, -0.2, 0.16, 0.24, ropa), _o(x, 0.0, 0.14, 0.14, piel), _o(x, 0.05, 0.15, 0.08, pelo),
            _o(x - 0.025, 0.0, 0.018, 0.022, TINTA), _o(x + 0.025, 0.0, 0.018, 0.022, TINTA), *extra]


def _bocadillo(x, y, signo, w=0.2, h=0.17):
    return [_o(x, y, w + 0.02, h + 0.02, TINTA), _o(x, y, w, h, PAPEL), _t(x - 0.05, y - h / 2 - 0.02, 0.06, 0.06,
                                                                            PAPEL, rot=180), _txt(signo, x, y, 0.13)]


def _actor(actor, quien):
    x = 0.5
    if actor == "oficial":
        return [_r(x, -0.2, 0.03, 0.34, (110, 90, 70)), _r(x, 0.08, 0.42, 0.3, TINTA), _r(x, 0.08, 0.39, 0.27, PAPEL),
                _r(x - 0.02, 0.15, 0.28, 0.025, (90, 90, 100)), _r(x - 0.02, 0.09, 0.28, 0.025, (90, 90, 100)),
                _r(x - 0.04, 0.03, 0.24, 0.025, (90, 90, 100)), _o(x + 0.13, 0.0, 0.08, 0.08, (210, 50, 50)),
                _txt("AVISO", x, 0.19 + 0.0, 0.06)]
    if actor == "radio":
        return [_r(x, -0.18, 0.34, 0.2, (150, 80, 60)), _o(x - 0.08, -0.18, 0.11, 0.11, (40, 40, 50)),
                _r(x + 0.08, -0.15, 0.1, 0.04, (240, 220, 160)), _r(x + 0.12, 0.0, 0.015, 0.22, (90, 90, 100), rot=20),
                _txt(")))", x + 0.25, 0.12, 0.12), _txt("(((", x - 0.22, 0.12, 0.12)]
    if actor == "anonimo":
        return [_r(x, -0.2, 0.18, 0.26, (60, 60, 70)), _o(x, 0.02, 0.18, 0.18, (50, 50, 60)),
                _o(x, 0.0, 0.11, 0.12, (20, 20, 26)), *_bocadillo(x - 0.24, 0.22, "?")]
    if actor == "grupo":
        fig = [_r(x, -0.02, 0.3, 0.56, TINTA), _r(x, -0.02, 0.26, 0.48, (230, 236, 244))]
        for i, y in enumerate((0.15, 0.03, -0.09)):
            fig += [_r(x - 0.03 + 0.04 * (i % 2), y, 0.18, 0.08, (130, 210, 130) if i % 2 else PAPEL),
                    _txt("»", x - 0.1 + 0.04 * (i % 2), y, 0.07)]
        for i in range(3):
            fig += [_o(x - 0.42 + 0.12 * i, -0.24, 0.09, 0.09, PIELES[i]), _r(x - 0.42 + 0.12 * i, -0.33, 0.1, 0.1,
                                                                            ROPAS[i + 2])]
        return fig
    if actor == "foto":
        return _persona(x, quien, [_r(x + 0.14, -0.08, 0.1, 0.16, TINTA), _o(x + 0.14, 0.06, 0.12, 0.12, (255, 240, 120)),
                                   _txt("*", x + 0.14, 0.06, 0.1)])
    if actor == "duda":
        return _persona(x, quien, _bocadillo(x - 0.24, 0.22, "?"))
    return _persona(x, quien, _bocadillo(x - 0.24, 0.22, "!"))


def figuras(escenario, actor, quien=""):
    """Todas las primitivas de una viñeta (fondo del escenario + el personaje), en orden de dibujo."""
    if escenario not in ESCENARIOS:
        escenario = "barrio"
    if actor not in ACTORES:
        actor = "testigo"
    return _fondo(escenario) + _actor(actor, quien)


def rotulo(item):
    """Cartela de la viñeta grande: la hora (o «sin hora») y quién lo dijo."""
    hora = (item or {}).get("hora") or "sin hora"
    return f"{hora} · {(item or {}).get('quien', '')}"

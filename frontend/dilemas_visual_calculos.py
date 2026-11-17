# Cálculos de los DILEMAS visuales (frontend/dilemas_visual.py). Python puro, sin ursina, con tests en
# tests/test_dilemas_visual.py.
#
#   - la viñeta de cómic con la que se presenta el dilema (formato de frontend/cinematica_final.crear_vinetas);
#   - el panel «mañana…» tras elegir y el recuerdo de lo elegido;
#   - cuándo un aviso del reloj es la consecuencia (del día siguiente) de un dilema recordado.

HORAS_MINIMAS_CONSECUENCIA = 6.0     # un aviso antes de esto es el efecto inmediato, no «al día siguiente»

FONDOS = ((120, 190, 235), (238, 180, 120), (170, 150, 220), (130, 200, 170))
EDIFICIOS = ((196, 120, 90), (90, 110, 160), (170, 150, 90), (120, 150, 110))


LARGO_CARTELA = 180          # caracteres que caben en la cartela de la viñeta (3 líneas)


def _recortar(texto, largo):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= largo else texto[:largo - 1].rsplit(" ", 1)[0] + "…"


def _indice(texto, n):
    return sum(ord(c) for c in str(texto)) % n


def vineta_de_dilema(contenido, color_jugador=(60, 70, 120)):
    """Una viñeta de cómic para el dilema (dict de crear_vinetas): el barrio, tú con el teléfono y alguien que espera."""
    k = _indice(contenido.get("id", contenido.get("titulo", "")), len(FONDOS))
    return {
        "fondo": list(FONDOS[k]),
        "titulo": contenido.get("titulo", "Un dilema"),
        "texto": _recortar(contenido.get("situacion", ""), LARGO_CARTELA),     # completo en el panel, después
        "figuras": [
            {"tipo": "suelo", "color": [96, 170, 110]},
            {"tipo": "edificio", "x": -0.52, "y": 0.0, "ancho": 0.26, "alto": 0.26, "color": list(EDIFICIOS[k])},
            {"tipo": "edificio", "x": 0.5, "y": 0.0, "ancho": 0.24, "alto": 0.22,
             "color": list(EDIFICIOS[(k + 1) % len(EDIFICIOS)])},
            {"tipo": "persona", "x": -0.12, "y": 0.0, "alto": 0.22, "color": list(color_jugador)},
            {"tipo": "nota", "x": -0.04, "y": 0.2},
            {"tipo": "persona", "x": 0.2, "y": 0.0, "alto": 0.2, "color": [214, 80, 70]},
        ],
    }


def posiciones_puntitos(desde, hasta, n=3):
    """Puntos (x, y) de la estela de burbujas de pensamiento entre el personaje y una opción (cada vez más grandes)."""
    (ax, ay), (bx, by) = desde, hasta
    return [(ax + (bx - ax) * (i + 1) / (n + 1), ay + (by - ay) * (i + 1) / (n + 1)) for i in range(n)]


def tamanos_puntitos(n=3, minimo=0.012, maximo=0.028):
    if n <= 1:
        return [maximo]
    return [minimo + (maximo - minimo) * i / (n - 1) for i in range(n)]


def clave_retardada(dilemas, dilema_id, opcion_id):
    """Clave del efecto retardado (el del día siguiente) de la opción elegida, sacada de los datos de dilemas
    (backend/datos/dilemas_loader). None si no se encuentra. OJO: no siempre empieza por el id del dilema."""
    for d in dilemas or ():
        if getattr(d, "id", None) != dilema_id:
            continue
        for o in getattr(d, "opciones", ()):
            if getattr(o, "id", None) == opcion_id:
                return getattr(getattr(o, "retardado", None), "clave", None)
    return None


def recuerdo(contenido, resultado, hora, clave=None):
    """Lo que se guarda al elegir: para enseñar la viñeta del día anterior cuando llegue la consecuencia."""
    opcion = next((o for o in contenido.get("opciones", ()) if o.get("id") == resultado.get("opcion")), {})
    return {"dilema": resultado.get("dilema") or contenido.get("id"), "titulo": contenido.get("titulo", ""),
            "eleccion": opcion.get("etiqueta", ""), "hora": hora, "clave": clave}


def recuerdo_de_aviso(aviso, recuerdos, hora_minima=HORAS_MINIMAS_CONSECUENCIA):
    """El recuerdo del dilema del que `aviso` es la consecuencia del día siguiente, o None.
    Se compara con la clave exacta guardada al elegir; si el recuerdo no la tiene, por el prefijo «dilema_<id>_».
    Un aviso que llega demasiado pronto es el efecto inmediato, no la consecuencia."""
    clave = str((aviso or {}).get("clave") or "")
    if not clave.startswith("dilema_"):
        return None
    hora = (aviso or {}).get("hora")
    exactos = [r for r in recuerdos if r.get("clave") and r["clave"] == clave]
    if exactos:
        r = exactos[-1]
    else:
        candidatos = [r for r in recuerdos if not r.get("clave") and r.get("dilema")
                      and clave.startswith(f"dilema_{r['dilema']}_")]
        if not candidatos:
            return None
        r = max(candidatos, key=lambda c: len(c["dilema"]))     # el id más largo que encaja (ids con «_»)
    if hora is not None and r.get("hora") is not None and hora - r["hora"] < hora_minima:
        return None
    return r


def texto_manana(eleccion):
    return "Mañana…" if not eleccion else f"Elegiste: «{eleccion}». Mañana…"


def texto_ayer(r):
    return f"Ayer: {r.get('titulo', '')}\nElegiste: «{r.get('eleccion', '')}»"

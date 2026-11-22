# Cálculos de la LLEGADA a una misión de verificar (frontend/llegada_visual.py). Python puro, sin ursina, con tests en
# tests/test_llegada_visual.py. Incluye el guion NUEVO del vistazo de cámara (no se toca guion_cinematicas.py).
#
#   - cuándo se anuncia una misión (una sola vez por misión) y el plan del vistazo de 1,5 s al destino;
#   - la columna de luz que marca la puerta (cuándo se ve y su pulso);
#   - qué postura adoptan los vecinos del destino según el tema del rumor y qué comentan en sus globos;
#   - el teléfono que se acerca a la cámara al pulsar E.

import math

# -- Guion del vistazo (tramos con su duración; DirectorCinematica los reproduce) --
VISTAZO = (("ir", 0.55), ("mirar", 0.5), ("volver", 0.45))
ALTURA_COLUMNA = 14.0
RADIO_VECINOS = 16.0          # m alrededor del destino en los que los vecinos comentan
DISTANCIA_JUGADOR = 22.0      # m: el jugador tiene que estar cerca para que los globos aparezcan
MAX_COMENTARIOS = 3
DUR_VIBRACION = 0.7
DUR_TELEFONO = 0.45

ESTADOS_COLUMNA = ("en_ruta", "en_radio")


def plan_vistazo(escala=1.0):
    return [(nombre, dur * escala) for nombre, dur in VISTAZO]


def duracion_vistazo():
    return sum(d for _, d in VISTAZO)


def debe_anunciar(mision, vistos):
    """¿Toca anunciar esta misión? Solo las de verificar, una vez por id (salir y volver al radio no la repite)."""
    if mision is None or getattr(mision, "tipo", "verificar") != "verificar":
        return False
    return getattr(mision, "id", None) not in vistos


def columna_visible(estado_mision):
    return estado_mision in ESTADOS_COLUMNA


def alfa_columna(t, reducir=False):
    if reducir:
        return 0.4
    return 0.32 + 0.18 * math.sin(t * 2.4)


# -- Vecinos del destino --

ENOJADO, CELULAR = "enojado", "celular"
POSTURA_POR_TEMA = {"politica": ENOJADO, "dinero": ENOJADO, "seguridad": ENOJADO, "estafa": ENOJADO,
                    "imagen": CELULAR, "datos": CELULAR, "salud": CELULAR, "evento": CELULAR, "general": CELULAR}


def postura_por_tema(tema):
    return POSTURA_POR_TEMA.get(tema, CELULAR)


def recortar(texto, largo=46):
    texto = " ".join(str(texto or "").split()).rstrip(".")
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


FRASES_POR_POSTURA = {
    ENOJADO: ("¡Esto no puede ser! ¿Viste lo de «{rumor}»?", "Ya lo mandé a todo el grupo, ¡qué rabia!"),
    CELULAR: ("Me llegó esto: «{rumor}»", "¿Alguien sabe si es verdad? Lo están reenviando mucho."),
}


def comentarios(rumor, pista, tema, n=MAX_COMENTARIOS):
    """Globos de los vecinos del destino: dos sobre el rumor (según el tema) y uno con la PISTA que se ve en el lugar."""
    postura = postura_por_tema(tema)
    salida = [f.format(rumor=recortar(rumor, 40)) for f in FRASES_POR_POSTURA[postura]]
    if pista:
        salida.append("Yo estuve aquí y vi otra cosa: " + recortar(pista, 60))
    return salida[:n]


def mas_cercanos(posiciones, centro, n=MAX_COMENTARIOS, radio=RADIO_VECINOS):
    """Índices de las `n` posiciones (x, z) más cercanas a `centro` dentro de `radio`."""
    cx, cz = centro
    con_d = sorted((math.hypot(p[0] - cx, p[1] - cz), i) for i, p in enumerate(posiciones) if p is not None)
    return [i for d, i in con_d if d <= radio][:n]


# -- Teléfono --

def temblor_telefono(t, amplitud=0.012, reducir=False):
    """Desplazamiento x del teléfono en pantalla mientras vibra."""
    if reducir or t < 0 or t >= DUR_VIBRACION:
        return 0.0
    return amplitud * (1 - t / DUR_VIBRACION) * math.sin(t * 70)


def acercar_telefono(t, reducir=False):
    """0..1: cuánto se ha acercado el teléfono a la cámara al pulsar E (1 = ocupa la pantalla)."""
    if reducir:
        return 1.0 if t > 0 else 0.0
    k = max(0.0, min(1.0, t / DUR_TELEFONO))
    return k * k * (3 - 2 * k)


# -- Cierre (punto 3, ALCALDE_GLOBOS_SIN_HUD): los globos de los vecinos son del MUNDO (billboard sobre la cabeza) y el HUD
# se pinta encima: con el vecino arriba en pantalla, «Me llegó esto…» quedaba encimado bajo el panel de misión. Con la
# bandera, cada cuadro se proyecta el globo a camera.ui y, si toca un bloque de arriba del HUD (misión, franja, minimapa y
# su etiqueta), se BAJA lo justo para quedar debajo con aire; si así se saldría de la zona segura, se oculta. =0 antes.
GLOBOS_SIN_HUD = True
BLOQUES_ARRIBA = ("mision", "franja", "minimapa", "lugar")
MAX_BAJADA_M = 2.5            # m: más abajo taparía al vecino entero: entonces el globo se oculta
MARGEN_INCLINACION = 1.15     # bajar en vertical del mundo con la cámara inclinada (~22°) rinde ~cos(22°) en pantalla


def globos_sin_hud_activo(entorno=None):
    import os
    valor = (os.environ if entorno is None else entorno).get("ALCALDE_GLOBOS_SIN_HUD", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(GLOBOS_SIN_HUD)


def obstaculos_hud(ancho_px, alto_px):
    """Rects (unidades de camera.ui) de los bloques de arriba del HUD que un globo no debe pisar."""
    from frontend import hud_esquinas_calculos as he
    rects = he.layout_esquinas(ancho_px, alto_px)
    return [rects[n] for n in BLOQUES_ARRIBA if n in rects]


def bajada_globo(rect, obstaculos, piso, holgura=None):
    """Cuánto (unidades de camera.ui, ≥ 0) hay que bajar el globo `rect` para que no toque ningún obstáculo.

    Baja por debajo de cada obstáculo que toque, repitiendo hasta que no toque ninguno. None si así su borde de abajo
    quedaría bajo `piso` (fuera de la zona segura): entonces el globo se oculta."""
    from frontend import hud_esquinas_calculos as he
    holgura = he.PASO if holgura is None else holgura
    dy = 0.0
    for _ in range(len(obstaculos) + 1):
        actual = he.Rect(rect.x0, rect.y0 - dy, rect.x1, rect.y1 - dy)
        tocados = [o for o in obstaculos if actual.se_solapa(o, holgura)]
        if not tocados:
            return dy if actual.y0 >= piso else None
        dy = max(dy, max(actual.y1 - o.y0 + holgura for o in tocados) + dy)
    return None


def metros_por_unidad_ui(profundidad, fov_vertical_grados):
    """m del mundo (a `profundidad` m de la cámara) que ocupa una unidad de camera.ui (= el alto de la pantalla)."""
    return 2.0 * max(profundidad, 0.0) * math.tan(math.radians(fov_vertical_grados) / 2.0)


def rect_desde_film(puntos_film, aspecto):
    """Rect en camera.ui que encierra puntos proyectados por la lente (coordenadas de film -1..1)."""
    from frontend import hud_esquinas_calculos as he
    xs = [p[0] * aspecto / 2 for p in puntos_film]
    ys = [p[1] * 0.5 for p in puntos_film]
    return he.Rect(min(xs), min(ys), max(xs), max(ys))

# Agregador de las «misiones visuales» (plan: misiones más dinámicas, visuales y llamativas). Es la ÚNICA línea que se añade
# a frontend/extensiones.py::MODULOS; aquí dentro se registra cada pieza nueva, cada una en su propio try/except: si una
# falla al instalarse, avisa una vez por stderr y las demás (y el juego) siguen como siempre.
#
# Piezas (cada una con su bandera ALCALDE_*, =0 la apaga):
#   - Ajustes › Movimiento: interruptor «Reducir movimiento» (frontend/movimiento_ajustes.py).
#   - Capa común de los minijuegos: la pide la escena de minijuegos al selector (frontend/minijuegos_visual), no hace falta
#     registrarla aquí. ALCALDE_EFECTOS_UI=0 la apaga.
#   - Interrogatorio de novela visual: lo elige la escena del mundo digital (frontend/interrogatorio_vn.py).
#   - Rectificar: teléfono con la publicación viva junto a la bandeja de Civitas (frontend/rectificar_visual.py).
#   - Llegada a la misión: vibración, vistazo al destino, columna de luz y vecinos que comentan (frontend/llegada_visual.py).
#   - Dilemas: escena de cómic, burbujas de pensamiento, «mañana…» y la viñeta del día anterior (frontend/dilemas_visual.py).
#   - Bandeja de Civitas: notificación, pegatinas, monedas, lupa del desconocido y feed que oscurece (frontend/civitas_visual.py).
#   - Tutorial breve de la primera vez de cada tipo de misión (frontend/registro_tutorial_mision.py, ALCALDE_TUTORIAL_MISION).
#   - Trabajos: fila y paciencia, PC que se repara, comida que se cocina, saludo, claxon, estela y «+R$» (frontend/trabajos_visual.py).
#
# APAGADO TOTAL: ALCALDE_MISIONES_VISUALES=0 no registra nada de lo de aquí.

from frontend import banderas_visuales as bv


def _instalar(nombre, funcion, *args):
    try:
        funcion(*args)
    except Exception as error:          # noqa: BLE001  una pieza rota no impide las demás
        bv.avisar_una_vez(f"registro_{nombre}", error)


def _movimiento():
    from frontend import movimiento_ajustes
    movimiento_ajustes.registrar()


def _rectificar(gestor, conexion, escena_mundo):
    from frontend import rectificar_visual
    rectificar_visual.registrar(gestor, conexion, escena_mundo)


def _llegada(gestor, conexion, escena_mundo):
    from frontend import llegada_visual
    llegada_visual.registrar(gestor, conexion, escena_mundo)


def _dilemas(gestor, conexion, escena_mundo):
    from frontend import dilemas_visual
    dilemas_visual.registrar(gestor, conexion, escena_mundo)


def _civitas(gestor, conexion, escena_mundo):
    from frontend import civitas_visual
    civitas_visual.registrar(gestor, conexion, escena_mundo)


def _trabajos(gestor, conexion, escena_mundo):
    from frontend import trabajos_visual
    trabajos_visual.registrar(gestor, conexion, escena_mundo)


def _tutorial_mision(gestor, conexion, escena_mundo):
    from frontend import registro_tutorial_mision
    registro_tutorial_mision.registrar(gestor, conexion, escena_mundo)


# (nombre, función(gestor, conexion, escena_mundo)). Los pasos siguientes añaden sus piezas a esta lista.
PIEZAS = [
    ("movimiento", lambda gestor, conexion, escena_mundo: _movimiento()),
    ("rectificar", _rectificar),            # ALCALDE_RECTIFICAR_VISUAL
    ("civitas", _civitas),                  # ALCALDE_CIVITAS_VISUAL (envuelve a la de rectificar: va DESPUÉS)
    ("llegada", _llegada),                  # ALCALDE_LLEGADA_VISUAL
    ("dilemas", _dilemas),                  # ALCALDE_DILEMAS_VISUAL
    ("trabajos", _trabajos),                # ALCALDE_TRABAJOS_VISUAL
    ("tutorial_mision", _tutorial_mision),  # ALCALDE_TUTORIAL_MISION (sección «Tutoriales» de Ajustes)
]


def registrar(gestor, conexion, escena_mundo):
    if not bv.maestra():
        return
    for nombre, funcion in PIEZAS:
        _instalar(nombre, funcion, gestor, conexion, escena_mundo)

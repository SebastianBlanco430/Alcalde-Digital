# Enganches del tutorial breve de la primera vez de cada tipo de misión (plan: tutorial_mision). Lo instala
# frontend/registro_misiones_visuales.py (con su propio try/except); no se toca frontend/extensiones.py.
#
#   - abrir_si_toca(...): lo llama la escena del tipo de misión JUSTO ANTES de que empiece (no al recibir la notificación). Devuelve
#     el tutorial abierto, o None si no toca (bandera apagada, ya visto, sin guion) o si falló al construirse (se avisa una vez
#     por stderr, se marca como visto y la misión sigue como hoy).
#   - Lo visto vive en ajustes.json (clave extra «tutoriales_vistos», entero de bits; ver backend/logica/tutorial_mision.py).
#   - Ajustes › Tutoriales: «Volver a mostrar todos los tutoriales» (escena_ajustes.registrar_seccion, sin editar esa escena).
#
# Hoy hay tutorial para los minijuegos que tienen adaptador (frontend/tutorial_mision_minijuegos.ADAPTADORES) Y guion en
# backend/datos/tutoriales_mision.json; los demás tipos de misión siguen igual que antes.

from backend.logica import tutorial_mision as logica
from frontend import banderas_visuales as bv

NOMBRE_SECCION = "Tutoriales"
DESCRIPCION = ("La primera vez que juegas cada tipo de misión ves un tutorial corto. Aquí puedes volver a verlos todos.")

_guiones = {"datos": None, "fallo": False}


def guiones():
    """El guion validado (cacheado). {} si no se puede leer: sin guion no hay tutoriales y el juego sigue como hoy."""
    if _guiones["datos"] is None and not _guiones["fallo"]:
        try:
            _guiones["datos"] = logica.cargar()
        except Exception as error:               # noqa: BLE001
            _guiones["fallo"] = True
            bv.avisar_una_vez("tutorial_guion", error)
    return _guiones["datos"] or {}


def olvidar_guiones():
    """Solo para pruebas."""
    _guiones.update(datos=None, fallo=False)


# ---------------------------------------------------------------- lo visto (ajustes.json)

def _gestor():
    from backend.logica import ajustes
    return ajustes.obtener()


def mascara_guardada():
    try:
        return _gestor().actual.extras.get(logica.CLAVE_AJUSTE, 0)
    except Exception:                            # noqa: BLE001  sin ajustes legibles: nada visto (y no pasa nada por repetirlo)
        return 0


def vistos():
    return logica.vistos_desde_mascara(mascara_guardada())


def guardar_mascara(mascara):
    try:
        gestor = _gestor()
        gestor.cambiar(**{logica.CLAVE_AJUSTE: int(mascara)})
        gestor.guardar()
    except Exception as error:                   # noqa: BLE001  si no se puede guardar, solo se repetirá el tutorial
        bv.avisar_una_vez("tutorial_guardar", error)


def marcar_visto(id_):
    guardar_mascara(logica.marcar_visto(mascara_guardada(), id_))


def olvidar_todos():
    """«Volver a mostrar todos los tutoriales»."""
    guardar_mascara(0)


# ---------------------------------------------------------------- consulta

def adaptadores():
    """Todos los adaptadores: los de los minijuegos y los de las demás misiones (cada módulo se carga por separado)."""
    from frontend import tutorial_mision_minijuegos as mini
    todos = dict(mini.ADAPTADORES)
    for nombre in ("tutorial_mision_mundo", "tutorial_mision_bandeja", "tutorial_mision_trabajo",
                   "tutorial_mision_ruta"):
        try:
            modulo = __import__(f"frontend.{nombre}", fromlist=["ADAPTADORES"])
            todos.update(modulo.ADAPTADORES)
        except Exception as error:               # noqa: BLE001  sin ese módulo, solo los demás
            bv.avisar_una_vez(nombre, error)
    return todos


def hay_tutorial(id_):
    """¿Existe tutorial para `id_` (bandera encendida, guion y adaptador)? No mira si ya se vio."""
    return logica.activo() and id_ in guiones() and id_ in adaptadores()


def toca(id_, forzar_ver=False):
    return hay_tutorial(id_) and logica.necesita_tutorial(id_, vistos(), logica.forzar() or forzar_ver)


# ---------------------------------------------------------------- apertura

def abrir_si_toca(padre, id_, al_terminar, forzar_ver=False, contexto=None):
    """Abre el tutorial `id_` como hijo de `padre` si toca. `al_terminar(saltado, fallo)` se llama UNA vez al cerrarse (se haya
    acabado, saltado o roto); quien lo pidió sigue entonces con la pantalla previa o el arranque. Nunca lanza."""
    try:
        if not toca(id_, forzar_ver):
            return None
        from frontend.tutorial_mision_vista import TutorialMision

        def cerrado(saltado, fallo):
            marcar_visto(id_)                    # visto al terminar, al saltar o si el guardián lo cierra
            al_terminar(saltado, fallo)

        guion = guiones()[id_]
        adaptador = adaptadores()[id_](id_, guion, contexto) if contexto is not None else adaptadores()[id_](id_, guion)
        return TutorialMision(id_, guion, adaptador, cerrado, parent=padre)
    except Exception as error:                   # noqa: BLE001  guardián: la misión sigue como hoy
        bv.avisar_una_vez(f"tutorial_{id_}", error)
        try:
            marcar_visto(id_)
        except Exception:                        # noqa: BLE001
            pass
        return None


# ---------------------------------------------------------------- Ajustes › Tutoriales

def construir_seccion(s):
    """`s` = escena_ajustes.Seccion."""
    s.anadir_texto(DESCRIPCION, alto=0.11)
    s.anadir_boton("Tutoriales", "Volver a mostrar todos", olvidar_todos)


def registrar(gestor=None, conexion=None, escena_mundo=None):
    if not logica.activo():                      # bandera apagada: ni la sección de Ajustes (idéntico a hoy)
        return
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
    if conexion is not None and escena_mundo is not None:       # bandeja de Civitas, rectificar y dilemas (teclas L y K)
        try:
            from frontend import tutorial_mision_bandeja
            tutorial_mision_bandeja.instalar(conexion, escena_mundo)
        except Exception as error:               # noqa: BLE001
            bv.avisar_una_vez("tutorial_bandeja", error)

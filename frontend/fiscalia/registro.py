# Registro de la Fiscalía v2 (lo carga frontend/extensiones.py; bandera ALCALDE_FISCALIA_V2, encendida por defecto).
# Con la bandera apagada no hace NADA (el mundo queda como en 0b7e148: PC suelto, sala digital, novela visual).
#
# Con la bandera: rotula la casa de la Fiscalía (cartel, minimapa), registra la escena FISCALIA, pone la E en su puerta
# (Protocol Interaccion de la economía) y engancha `escena_mundo.punto_de_mision` para que la baliza y la línea del GPS
# de las misiones de investigación lleven a esa puerta. El PC suelto de la calle lo retira registro_mundo_digital.py.
# En línea o sin GameState la puerta avisa «no disponible».
#
# Para el arnés: `_estado` guarda la escena, el edificio y las fábricas (se pueden sustituir por una sesión falsa).

import sys

from backend.logica import fiscalia_bandera as fb
from frontend.fiscalia import flujo_calculos as fc

FISCALIA = "fiscalia"

_estado = {"escena": None, "edificio": None, "sitio": None, "catalogo": None, "fabrica": None}


def cargar_catalogo():
    """{id: CasoV2} de los casos v2 válidos ({} si el cargador aún no existe o falla)."""
    if _estado.get("catalogo") is not None:
        return _estado["catalogo"]()
    try:
        from backend.datos import casos_loader
        cargar = getattr(casos_loader, "cargar_catalogo_v2", None)
        catalogo = dict(cargar()) if cargar is not None else _catalogo_directo()
    except Exception as error:          # noqa: BLE001
        print(f"[fiscalia] casos v2 no cargados: {type(error).__name__}: {error}", file=sys.stderr)
        return {}
    # «Cuentas fantasma» (el caso de la Fiscalía de siempre) primero; los demás en el orden del cargador
    return dict(sorted(catalogo.items(), key=lambda kv: kv[0] != "cuentas_fantasma"))


def _dia_actual(flujo):
    """Día de la partida (1-7) o None si no hay reparto por días. Nunca lanza."""
    try:
        resumen = flujo.resumen_dia() if callable(getattr(flujo, "resumen_dia", None)) else None
        return (resumen or {}).get("dia")
    except Exception:                   # noqa: BLE001
        return None


def _dia_del_caso(caso):
    mision = getattr(caso, "mision", None)
    return mision.get("dia") if isinstance(mision, dict) else None


def _catalogo_directo():
    """Puente mientras el cargador no exponga cargar_catalogo_v2: los caso_*.json con «formato»: 2 válidos."""
    import json
    from pathlib import Path
    from backend.logica.casos_v2 import CasoV2
    carpeta = Path(__file__).resolve().parents[2] / "backend" / "datos" / "casos"
    salida = {}
    for ruta in sorted(carpeta.glob("caso_*.json")):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if isinstance(datos, dict) and datos.get("formato") == 2:
                caso = CasoV2.desde_dict(datos)
                salida[caso.id] = caso
        except Exception as error:      # noqa: BLE001
            print(f"[fiscalia] {ruta.name}: {error}", file=sys.stderr)
    return salida


def crear_sesion(caso, game_state):
    if _estado.get("fabrica") is not None:
        return _estado["fabrica"](caso, game_state)
    from backend.logica import casos_v2
    return casos_v2.SesionCasoV2(caso, game_state)


def terminado(game_state, caso_id):
    """¿El caso ya tiene un final registrado en esta partida? (mismo rastro que el caso v1: casos.resultado_de)."""
    try:
        from backend.logica import casos_v2
        consulta = getattr(casos_v2, "resultado_de", None)
        if consulta is not None:
            return consulta(game_state, caso_id) is not None
    except Exception:                   # noqa: BLE001
        pass
    try:
        from backend.logica import casos
        return casos.resultado_de(game_state, caso_id) is not None
    except Exception:                   # noqa: BLE001
        return False


def registrar(gestor, conexion, escena_mundo):
    if not fb.activa():
        return None
    # Catálogo v2 ya en la carga inicial (la 1.ª validación tarda ~1,8 s; luego sale de caché). Sin ningún caso v2 válido
    # las misiones vuelven a las tres de siempre y se queda el PC de la calle (registro_mundo_digital): aquí no se hace nada.
    if not cargar_catalogo():
        print("[fiscalia] sin casos v2 válidos: se queda el flujo v1 (PC de la calle).", file=sys.stderr)
        return None
    from frontend.fiscalia import edificio
    from frontend.fiscalia.escena_fiscalia import EscenaFiscalia
    sitio = edificio.sitio_en(escena_mundo._mundo)
    if sitio is None:
        print("[fiscalia] no hay casas decorativas en este mundo: sin Fiscalía.", file=sys.stderr)
        return None
    glitch = None
    try:
        from frontend.mundo_digital_glitch import GlitchOverlay
        glitch = GlitchOverlay()
    except Exception as error:          # noqa: BLE001
        print(f"[fiscalia] sin glitch del terminal ({error})", file=sys.stderr)
    escena = EscenaFiscalia(gestor, conexion, escena_mundo, sitio, crear_sesion, glitch=glitch)
    gestor.registrar(FISCALIA, escena)
    _estado.update(escena=escena, sitio=sitio)

    def abrir(jugador):
        """E en la puerta: abre el caso (None) o devuelve el aviso a mostrar."""
        flujo = escena_mundo.flujo
        gs = getattr(flujo, "game_state", None)
        if flujo is None or gs is None:
            return fc.NO_DISPONIBLE
        if conexion._transicion_en_curso() or getattr(escena_mundo, "_cinematica", False):
            return None
        catalogo = cargar_catalogo()
        dia = _dia_actual(flujo)
        caso_id = fc.elegir_caso(flujo.mision_actual(), list(catalogo), lambda c: terminado(gs, c),
                                 lambda c: fc.caso_abierto(_dia_del_caso(catalogo.get(c)), dia))
        if caso_id is None:
            return fc.SIN_CASOS
        escena.catalogo = catalogo
        escena_mundo._cinematica = True               # el mundo queda quieto durante el fundido (al volver se suelta)
        escena_mundo._sincronizar_raton()

        def entrar():
            gestor.cambiar_a(FISCALIA, flujo=flujo, caso_id=caso_id)

        conexion._con_transicion_lugar(entrar, texto=fb.NOMBRE_FISCALIA)
        return None

    economia = escena_mundo.economia
    if economia is None:
        print("[fiscalia] ALCALDE_ECONOMIA=0: sin registro de interacciones; la puerta de la Fiscalía no responde a E.",
              file=sys.stderr)
    else:
        _estado["edificio"] = economia.registrar(edificio.EdificioFiscalia(escena_mundo, sitio, abrir))
        economia.registrar(edificio.GuiaFiscalia(escena_mundo, sitio))

    # Baliza y GPS: las misiones de investigación (casos de la Fiscalía) van a la puerta de la casa, no a la plaza.
    previo = escena_mundo.punto_de_mision

    def punto_de_mision(mision):
        if mision is not None and getattr(mision, "tipo", None) == "investigacion":
            return sitio.fuera
        return previo(mision) if previo is not None else None

    escena_mundo.punto_de_mision = punto_de_mision
    conexion.fiscalia = escena
    return escena

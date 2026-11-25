# Modo feria en el juego real (docs/MODO_FERIA.md; lógica en backend/logica/modo_feria.py y flujo_tiempo.py). main.py lo
# carga con extensiones.aplicar(..., modulos=MODULOS_HILO), después de frontend/registro_reloj.py.
#
# En una partida de feria (flujo.ritmo_feria no es None) el chip «Día N · hh:mm» NO se ve: la hora no corre con el tiempo
# real, solo el ciclo día-noche avanza con cada misión cerrada (el cielo sigue a ambiente_vivo.hora(), que lee el reloj).
# Se consigue envolviendo el método chip() de la vista del vigía del reloj (conexion.vigia_reloj.vista), sin editar
# registro_reloj.py: el resto del vigía (avance, avisos y pantalla final) sigue igual. En modo normal no cambia nada.
#
# BANDERA: ALCALDE_FERIA (la pone el menú de inicio); el envoltorio se instala siempre y mira la partida en cada frame.

import sys


def _es_feria(escena_mundo):
    return getattr(getattr(escena_mundo, "flujo", None), "ritmo_feria", None) is not None


def instalar_sin_chip(vista, escena_mundo):
    """Envuelve vista.chip(texto, icono, fraccion, visible): en feria siempre invisible. Devuelve True si lo instaló."""
    original = getattr(vista, "chip", None)
    if not callable(original):
        return False

    def chip(texto, icono, fraccion, visible):
        return original(texto, icono, fraccion, bool(visible) and not _es_feria(escena_mundo))

    vista.chip = chip
    return True


def instalar_sin_avisos_fin(control, escena_mundo):
    """«Último día» / «Quedan 2 horas» hablan de horas de reloj: en feria no se dicen (control.fin.revisar -> [])."""
    fin = getattr(control, "fin", None)
    original = getattr(fin, "revisar", None)
    if not callable(original):
        return False
    fin.revisar = lambda horas: [] if _es_feria(escena_mundo) else original(horas)
    return True


def registrar(gestor, conexion, escena_mundo):
    vigia = getattr(conexion, "vigia_reloj", None)
    vista = getattr(vigia, "vista", None)
    if vista is None:
        return None
    try:
        instalar_sin_avisos_fin(getattr(vigia, "control", None), escena_mundo)
        return instalar_sin_chip(vista, escena_mundo)
    except Exception as error:
        print(f"[feria] chip del reloj sin ocultar ({type(error).__name__}: {error})", file=sys.stderr)
        return None

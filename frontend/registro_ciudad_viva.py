# Ciudad viva (punto 5 del plan final): frontend/extensiones.py llama a registrar(); no se edita main.py ni escena_mundo.py.
# Un controlador cuelga de la EscenaMundo (solo corre con el mundo a la vista), lee el Ambiente suavizado de
# frontend/ambiente_vivo.py y hace que la ciudad se vea según los indicadores: luz, cielo y niebla (atmósfera) y objetos
# pequeños que aparecen y desaparecen (basura, grafitis, flores, guirnaldas, faroles, bancos y corros). Detalle en
# frontend/ciudad_viva.py y en backend/logica/ciudad_viva_calculos.py.
#
# Banderas (la variable de entorno manda sobre la constante):
#   CIUDAD_VIVA            / ALCALDE_CIUDAD_VIVA=0            nada de esto: la ciudad queda exactamente como antes
#   CIUDAD_VIVA_ATMOSFERA  / ALCALDE_CIUDAD_VIVA_ATMOSFERA=0  sin cambios de luz, cielo ni niebla
#   CIUDAD_VIVA_CAPAS      / ALCALDE_CIUDAD_VIVA_CAPAS=0      sin objetos que aparecen y desaparecen
import os
import sys

CIUDAD_VIVA = True
CIUDAD_VIVA_ATMOSFERA = True
CIUDAD_VIVA_CAPAS = True


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_CIUDAD_VIVA", CIUDAD_VIVA)


def atmosfera_activa():
    return _bandera("ALCALDE_CIUDAD_VIVA_ATMOSFERA", CIUDAD_VIVA_ATMOSFERA)


def capas_activas():
    return _bandera("ALCALDE_CIUDAD_VIVA_CAPAS", CIUDAD_VIVA_CAPAS)


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    con_atm, con_capas = atmosfera_activa(), capas_activas()
    if not (con_atm or con_capas):
        return None
    try:
        from frontend.ciudad_viva import crear_controlador
        controlador = crear_controlador(escena_mundo, atmosfera=con_atm, capas=con_capas)
        conexion.ciudad_viva = controlador
        return controlador
    except Exception as error:
        print(f"[ciudad_viva] no instalado ({type(error).__name__}: {error}); la ciudad sigue como antes", file=sys.stderr)
        return None

# M1.3 (D7) Cableado de la prioridad entre textos flotantes del mundo (frontend/textos_mundo_visual.py). Lo llama
# frontend/extensiones.py (después de registro_ambiente_npc, que crea los globos). Funciona también con los globos
# apagados (ALCALDE_NPC_GLOBOS=0): entonces solo cuentan cartel de puerta > cartel de puesto.
# M1.4 (D9): el mismo controlador funde los carteles ilegibles (letra de menos de ~10 px en pantalla).
# Banderas independientes: ALCALDE_TEXTOS_PRIORIDAD (solapes) y ALCALDE_LETREROS_MINIMO (ilegibles). Con las dos en 0
# no se instala nada; los carteles quedan exactamente como antes.

import sys

from frontend import textos_mundo_calculos as tm


def _aviso(texto):
    print(f"[textos_mundo] {texto}", file=sys.stderr)


# [(clave, prioridad, nodos, es_globo)] de los textos del mundo en este momento. Los carteles de puerta llevan su
# glosa (ciudad_3d._letrero la guarda en texto.glosa); los de puesto los guarda comercios_mundo.instalar.
def fuentes_de(escena, conexion):
    textos = []
    ambiente = getattr(conexion, "ambiente_npc", None)
    globos = getattr(ambiente, "globos", None)
    for globo in getattr(globos, "_globos", ()):
        textos.append((id(globo), tm.PRIORIDAD_GLOBO, (globo,), True))
    ciudad = getattr(escena, "ciudad", None)
    for texto in (getattr(ciudad, "letreros", None) or {}).values():
        glosa = getattr(texto, "glosa", None)
        textos.append((id(texto), tm.PRIORIDAD_PUERTA, (texto,) if glosa is None else (texto, glosa), False))
    for texto in getattr(ciudad, "carteles_texto", None) or ():     # carteles pintados de la favela y secretos
        textos.append((id(texto), tm.PRIORIDAD_PUESTO, (texto,), False))
    economia = getattr(escena, "economia", None)
    for texto in getattr(economia, "letreros_puestos", None) or ():
        if texto is not None:
            textos.append((id(texto), tm.PRIORIDAD_PUESTO, (texto,), False))
    return textos


def _activo(escena):
    return (getattr(escena, "flujo", None) is not None and not getattr(escena, "en_pausa", False)
            and not getattr(escena, "_cinematica", None))


def registrar(gestor, conexion, escena_mundo):
    prioridad, minimo = tm.textos_prioridad_activa(), tm.letreros_minimo_activa()
    if not (prioridad or minimo):
        return None
    try:
        from frontend.textos_mundo_visual import PrioridadTextos
        conexion.textos_mundo = PrioridadTextos(lambda: fuentes_de(escena_mundo, conexion),
                                                activo=lambda: _activo(escena_mundo), prioridad=prioridad,
                                                minimo=minimo, parent=escena_mundo)
        return conexion.textos_mundo
    except Exception as error:
        _aviso(f"no instalado ({type(error).__name__}: {error}); los carteles quedan como antes")
        return None

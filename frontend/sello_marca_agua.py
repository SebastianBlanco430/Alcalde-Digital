# Marca de agua del sello de la Tradición en las imágenes de los minijuegos «Señales de edición» y «Comparar» (hilo
# conductor: desde el día 1, muy tenue, y más marcada cada capa; docs/HILO_CONDUCTOR.md). Solo si el rumor de la misión
# lleva sello (backend/logica/sello_rumores.py). La ponen frontend/minijuegos_3d/senales_3d.py y comparar_3d.py sobre su
# papel, y frontend/escenas/escena_minijuego.py sobre la vista 2D cuando no hay 3D. No cambia la lógica ni el resultado.
# Bandera: ALCALDE_HILO_SELLO (ver sello_rumores). Nunca lanza: un fallo deja la imagen sin marca.
#
#   alfa_para(mision)                              -> alfa de la marca o None (sin marca)
#   poner_en_papel(hoja, mision, escala=0.55)      -> Entity o None (hoja = pivote de papel_3d.papel)
#   poner_en_2d(padre, mision, posicion, lado)     -> Entity o None

import sys

MINIJUEGOS_CON_MARCA = ("senales", "comparar")


def alfa_para(mision):
    try:
        from backend.logica import sello_rumores
        from frontend import ambiente_vivo
        from frontend import sello_tradicion_calculos as stc
        capa = sello_rumores.capa_de(getattr(mision, "id", None), ambiente_vivo.dia() or 1)
        return None if capa is None else stc.alfa_marca_agua(capa)
    except Exception as error:
        print(f"[sello] marca de agua omitida ({type(error).__name__}: {error})", file=sys.stderr)
        return None


def _poner(padre, lado, alfa, posicion):
    try:
        from frontend import sello_tradicion
        return sello_tradicion.crear_sello(padre, lado, alfa, posicion)
    except Exception as error:
        print(f"[sello] marca de agua omitida ({type(error).__name__}: {error})", file=sys.stderr)
        return None


def poner_en_papel(hoja, mision, escala=0.55):
    alfa = alfa_para(mision)
    if alfa is None or hoja is None:
        return None
    lado = min(getattr(hoja, "ancho", 0.2), getattr(hoja, "alto", 0.2)) * escala
    return _poner(getattr(hoja, "contenido", hoja), lado, alfa, (0.0, 0.0, -0.0009))


def poner_en_2d(padre, mision, posicion, lado):
    alfa = alfa_para(mision)
    if alfa is None or padre is None:
        return None
    return _poner(padre, lado, alfa, posicion)

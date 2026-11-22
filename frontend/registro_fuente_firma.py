# Firma «la fuente» (M4): frontend/extensiones.py llama a registrar(); no se edita main.py ni escena_mundo.py.
# Un controlador cuelga de la EscenaMundo y hace que la fuente de la Praça da Sé muestre la salud de la ciudad (chorro, color
# del agua, flores, fuente seca con basura y cartel de «sin conexión»). Detalle en frontend/fuente_firma.py y en
# frontend/fuente_firma_calculos.py.
#
# Bandera (la variable de entorno manda sobre la constante):
#   FIRMA_FUENTE / ALCALDE_FIRMA_FUENTE=0   la fuente queda exactamente como antes (agua en la malla del decorado) y la
#                                            ciudad viva no prioriza la basura y las flores junto a la puerta del destino
import sys

from frontend import fuente_firma_calculos

# La constante vive en fuente_firma_calculos.FIRMA_FUENTE (una sola): props_mundo la lee al armar el decorado y tiene que
# coincidir con la de aquí (si no, la fuente saldría sin agua o con el agua dos veces).
def activo():
    return fuente_firma_calculos.activo()


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    try:
        from frontend.fuente_firma import crear_controlador
        controlador = crear_controlador(escena_mundo)
        conexion.fuente_firma = controlador
        return controlador
    except Exception as error:
        print(f"[fuente_firma] no instalada ({type(error).__name__}: {error}); la fuente queda sin agua", file=sys.stderr)
        return None

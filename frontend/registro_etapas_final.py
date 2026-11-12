# Finales por etapas (docs/PLAN_FINALES_HISTORIA.md): frontend/extensiones.py llama a registrar(); no se edita main.py ni
# escena_mundo.py. Un controlador cuelga del HUD de la EscenaMundo (solo corre con el mundo a la vista), lee el índice de la
# partida y lo convierte en una etapa de -3 a +3 que cambia lo que se ve y se oye: fuego / rodadores / fiesta en la ciudad
# viva, NPC de etapa, tinte de cámara, música y el medidor «Confianza de Ciudad Nova». Detalle en
# frontend/etapas_final_vista.py y backend/logica/etapas_final.py. La cinemática del final la lanza frontend/registro_reloj.py.
#
# Bandera (la variable de entorno manda sobre la constante de backend/logica/etapas_final.py):
#   ETAPAS_FINAL / ALCALDE_ETAPAS_FINAL=0     nada de esto: el juego queda exactamente como antes
import sys

from backend.logica import etapas_final


def activo():
    return etapas_final.activo()


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    try:
        from frontend.etapas_final_vista import crear_controlador
        controlador = crear_controlador(escena_mundo, conexion)
        conexion.etapas_final = controlador
        return controlador
    except Exception as error:
        print(f"[etapas_final] no instalado ({type(error).__name__}: {error}); el juego sigue como antes", file=sys.stderr)
        return None

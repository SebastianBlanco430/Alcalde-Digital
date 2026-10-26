# Transporte del mapa grande (Ursina): instala el viaje rápido en la economía de la escena del mundo. Lo llama
# IntegracionEconomia._instalar_modulos (como comercios_mundo, vendedor_calle y trabajo_mundo) con la bandera
# economia_config.TRANSPORTE. Con el mundo chico no hace nada (sin paradas, sin estaciones, sin cable): el juego es idéntico.
#
#   frontend/viaje_rapido.py     director de los viajes (cobro, fundido, reubicación, trayecto animado, online)
#   frontend/mototaxi.py         las tres paradas con conductor y el menú de destinos
#   frontend/teleferico_vista.py cable, torres, cabinas decorativas y los dos postes de embarque

from backend.logica import viaje_rapido as vr
from frontend import mundo_config


def instalar(economia, crear_npc=None):
    """Devuelve el ViajeRapido, o None si el mundo no es el grande."""
    escena = economia.escena
    mundo = escena._mundo
    if not (mundo_config.es_mundo_grande(mundo) and vr.disponible(mundo)):
        return None
    from frontend import mototaxi, teleferico_vista
    from frontend.viaje_rapido import ViajeRapido
    viaje = ViajeRapido(escena, economia)
    panel = mototaxi.crear_panel(economia)
    mototaxi.instalar(economia, viaje, panel, crear_npc)
    teleferico_vista.instalar(economia, viaje, panel)
    economia.viaje_rapido = viaje
    return viaje

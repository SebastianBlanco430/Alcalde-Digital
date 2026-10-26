# FlujoConEconomia (modelo puro): envuelve un FlujoPartida y añade la economía sin tocarlo. Al completar una
# misión paga al jugador que la cerró (se captura ANTES de delegar, porque completar_mision pasa el turno) y
# todos los jugadores descansan un poco (-30 de fatiga). Lo demás se delega con __getattr__.

from backend.logica import dinero
from backend.logica.perfil_economia import perfil_de


class FlujoConEconomia:

    def __init__(self, flujo, catalogo=None):
        self._flujo = flujo
        self._catalogo = catalogo

    def completar_mision(self, resultado):
        jugador = self._flujo.jugador_activo()
        mision = self._flujo.mision_actual()
        siguiente = self._flujo.completar_mision(resultado)     # si falla, no se paga nada
        if jugador is not None and mision is not None:
            perfil = perfil_de(jugador, self._catalogo)
            dinero.pagar_mision(perfil, mision)
            perfil.turnos += 1
        for j in self._flujo.sesion.jugadores():
            dinero.recuperar_fatiga(perfil_de(j, self._catalogo))
        return siguiente

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre == "_flujo":
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)

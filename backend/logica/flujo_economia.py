# FlujoConEconomia (modelo puro): envuelve un FlujoPartida y añade la economía sin tocarlo. Al completar una
# misión paga al jugador que la cerró (se captura ANTES de delegar, porque completar_mision pasa el turno) y
# todos los jugadores descansan un poco (-30 de fatiga). Lo demás se delega con __getattr__.

from backend.logica import dinero
from backend.logica.perfil_economia import perfil_de


class FlujoConEconomia:

    def __init__(self, flujo, catalogo=None):
        self._flujo = flujo
        self._catalogo = catalogo
        # Resultado (inventario.Resultado) del último pago de misión, o None si no hubo pago.
        # La vista lo lee para avisar «+R$» solo si ok, o el motivo (p. ej. billetera llena).
        self.ultimo_pago = None
        # TODOS los pagos desde la última vez que la vista los vació, en orden. Cuando varias misiones se cierran en
        # cadena (cierre inmediato de las digitales) `ultimo_pago` se pisa; la vista recorre esta lista para avisar «+R$»
        # de cada una y llama a vaciar_pagos_recientes().
        self.pagos_recientes = []

    # Entrega los pagos acumulados (lista de Resultado) y la deja vacía. `ultimo_pago` no se toca.
    def vaciar_pagos_recientes(self):
        pagos, self.pagos_recientes = self.pagos_recientes, []
        return pagos

    def completar_mision(self, resultado):
        self.ultimo_pago = None
        jugador, mision = self._flujo.jugador_activo(), self._flujo.mision_actual()
        siguiente = self._flujo.completar_mision(resultado)     # si falla, no se paga nada
        self._cobrar(jugador, mision)
        return siguiente

    # Misiones digitales: si la señal del GameState se cumplió, cierra la misión igual que completar_mision (pago,
    # turno y fatiga) y deja el pago en `ultimo_pago`. True si cerró una misión; si no, no toca nada (ni `ultimo_pago`).
    def revisar_misiones_digitales(self, game_state):
        jugador, mision = self._flujo.jugador_activo(), self._flujo.mision_actual()
        if not self._flujo.revisar_misiones_digitales(game_state):
            return False
        self.ultimo_pago = None
        self._cobrar(jugador, mision)
        return True

    # Paga al jugador que cerró la misión (capturados ANTES de cerrar: cerrar pasa el turno) y descansa a todos.
    def _cobrar(self, jugador, mision):
        if jugador is not None and mision is not None:
            perfil = perfil_de(jugador, self._catalogo)
            self.ultimo_pago = dinero.pagar_mision(perfil, mision)
            self.pagos_recientes.append(self.ultimo_pago)
            if self.ultimo_pago.ok:        # sin pago (billetera llena...) no se cuenta el turno
                perfil.turnos += 1
        for j in self._flujo.sesion.jugadores():
            dinero.recuperar_fatiga(perfil_de(j, self._catalogo))

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre == "_flujo":
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)

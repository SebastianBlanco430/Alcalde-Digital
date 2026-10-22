# Lote de decisiones de una misión (modelo puro, sin ursina). Reúne la regla que antes
# vivía en la escena de juego: cuántas decisiones lleva el jugador, qué deltas acumulan
# los indicadores, cuándo termina el lote (cantidad de noticias de la misión o mazo
# agotado) y cómo se propagó cada decisión por el grafo social.
#
# La escena solo llama registrar() / terminada() / resultado() y pinta lo que devuelven.
# El resultado es un dict JSON-serializable que entrega SistemaMisiones.completar().

import logging

from backend.logica.estado_partida import NOMBRES_INDICADORES
from backend.logica.propagacion import calcular_propagacion

_registro = logging.getLogger(__name__)


class LoteMision:

    # mision: Mision (da id y cantidad_noticias). grafo_social (opcional): activa la
    # propagación de cada decisión. rol: id del rol del jugador (decide el origen).
    def __init__(self, mision, grafo_social=None, rol=None):
        self._mision = mision
        self._grafo_social = grafo_social
        self._rol = rol
        self.decisiones = 0
        self.deltas_acumulados = {nombre: 0 for nombre in NOMBRES_INDICADORES}
        self.propagaciones = []
        # Las mismas propagaciones pero COMPLETAS (con "niveles"), en orden. Aditivo: sirve a
        # la pantalla de resultado para colorear el grafo; resultado() no la incluye.
        self.propagaciones_completas = []
        self._sin_noticias = False

    # Anota una decisión ("compartir" / "reportar") con los `deltas` que aplicó el estado
    # (None = no se aplicó nada: no cuenta). `quedan_noticias` False marca el lote como
    # terminado aunque no se llegue a la cantidad pedida (mazo agotado). Devuelve la
    # propagación completa (con "niveles", para animarla) o None si no hubo.
    def registrar(self, decision, deltas, quedan_noticias=True):
        if deltas is not None:
            self.decisiones += 1
            for nombre in NOMBRES_INDICADORES:
                self.deltas_acumulados[nombre] += deltas.get(nombre, 0)
        if not quedan_noticias:
            self._sin_noticias = True
        if deltas is None:
            return None
        return self._propagar(decision)

    def terminada(self):
        return self.decisiones >= self._mision.cantidad_noticias or self._sin_noticias

    # Dict que recibe SistemaMisiones.completar(); contiene copias, no el estado vivo.
    def resultado(self):
        return {
            "mision": self._mision.id,
            "decisiones": self.decisiones,
            "deltas": dict(self.deltas_acumulados),
            "propagaciones": [dict(p) for p in self.propagaciones],
            "alcance_total": sum(p["alcance"] for p in self.propagaciones),
        }

    # Copia de las propagaciones con "niveles" (para pintar el estado final del grafo).
    def propagaciones_con_niveles(self):
        return [dict(p, niveles=[list(n) for n in p["niveles"]]) for p in self.propagaciones_completas]

    # Sin grafo no hay propagación. Un rol sin ciudadano (u otra entrada inválida) no
    # propaga, pero ya no se oculta: queda en el registro como advertencia.
    def _propagar(self, decision):
        if self._grafo_social is None:
            return None
        try:
            propagacion = calcular_propagacion(self._grafo_social, self._rol, decision)
        except ValueError as error:
            _registro.warning(
                "Sin propagación para la misión %r (rol=%r, decisión=%r): %s",
                self._mision.id, self._rol, decision, error,
            )
            return None
        self.propagaciones.append({
            "origen": propagacion["origen"],
            "accion": propagacion["accion"],
            "alcance": propagacion["alcance"],
        })
        self.propagaciones_completas.append({
            "origen": propagacion["origen"],
            "accion": propagacion["accion"],
            "niveles": [list(nivel) for nivel in propagacion["niveles"]],
            "alcance": propagacion["alcance"],
        })
        return propagacion

# Lote de decisiones de una misión (modelo puro, sin ursina). Reúne la regla que antes
# vivía en la escena de juego: cuántas decisiones lleva el jugador, qué deltas acumulan
# los indicadores, cuándo termina el lote (cantidad de noticias de la misión o mazo
# agotado) y cómo se propagó cada decisión por el grafo social.
#
# La escena solo llama registrar() / terminada() / resultado() y pinta lo que devuelven.
# El resultado es un dict JSON-serializable que entrega SistemaMisiones.completar().
#
# CARTA DE MISIÓN (A2d): si se le pasa el `estado` (EstadoPartida) y este trae `cartas_mision` (el par de árboles de
# misión del mapa, backend/datos/noticias_mision.py), UNA de las cartas del lote es el rumor de la misión y las demás
# salen del mazo. El lote elige en qué puesto sale (al azar) y la pone en mesa con EstadoPartida.forzar_noticia; la escena
# sigue haciendo lo de siempre (estado.decidir(tipo) y luego lote.registrar(tipo, deltas, estado.hay_noticia())). La vista
# pregunta es_carta_de_mision() para distinguirla y pista() para mostrar lo que se ve al llegar. La decisión sobre esa
# carta queda en `decision_mision` y da el veredicto (confianza_misiones.veredicto): pasada o fallada. Sin `estado` o sin
# cartas (en línea, sin GameState, consecuencias apagadas) el lote es exactamente el de antes.

import logging
import random

from backend.logica import confianza_misiones
from backend.logica.estado_partida import NOMBRES_INDICADORES
from backend.logica.propagacion import calcular_propagacion

_registro = logging.getLogger(__name__)


class LoteMision:

    # mision: Mision (da id y cantidad_noticias). grafo_social (opcional): activa la
    # propagación de cada decisión. rol: id del rol del jugador (decide el origen).
    # estado (opcional): el EstadoPartida donde se deciden las cartas; si trae cartas_mision
    # y la misión tiene carta, el lote la fuerza en un puesto al azar. azar (opcional):
    # objeto con randrange(n), para pruebas deterministas.
    def __init__(self, mision, grafo_social=None, rol=None, estado=None, azar=None):
        self._mision = mision
        self._grafo_social = grafo_social
        self._rol = rol
        self.decisiones = 0
        self.deltas_acumulados = {nombre: 0 for nombre in NOMBRES_INDICADORES}
        self.propagaciones = []
        # Las mismas propagaciones pero COMPLETAS (con "niveles"), en orden. Aditivo: sirve a
        # la pantalla de resultado para colorear el grafo; resultado() no la incluye.
        self.propagaciones_completas = []
        # Decisiones sin deltas (p. ej. isomorfismo roto): no cuentan como decisiones, pero agotan
        # el lote para que la misión no quede atascada repitiendo noticias inservibles.
        self.descartadas = 0
        # Veces que cerrar_lote (minijuegos) llamó a estado.decidir sobre este lote, haya o no alcanzado a registrarse: si decidir
        # falla tras mutar el estado, `decisiones` sigue en 0 y esto avisa de que el estado ya se tocó (no repetir la misión).
        self.intentos_decidir = 0
        self._sin_noticias = False
        # Carta de misión: decisión tomada sobre ella ("compartir" / "reportar") o None si aún no se decidió (o no hay).
        self.decision_mision = None
        self._estado = estado
        self._cartas = None
        self._puesto_carta = None       # índice (0..cantidad-1) en el que sale la carta de misión; None = sin carta
        self._carta_en_mesa = False     # la carta de misión es la que está ahora en mesa
        self._carta_jugada = False      # ya salió (decidida o descartada)
        self._preparar_carta(azar if azar is not None else random)

    # -- Carta de misión --

    # ¿Este lote lleva carta de misión? (hay estado con cartas y la misión tiene la suya).
    def tiene_carta_de_mision(self):
        return self._puesto_carta is not None

    # ¿La noticia que está AHORA en mesa es la carta de misión? La vista la marca distinta.
    def es_carta_de_mision(self):
        return self._carta_en_mesa

    # Lo que el jugador ve al llegar (Mision.pista); "" si el lote no lleva carta de misión.
    def pista(self):
        return self._mision.pista if self.tiene_carta_de_mision() else ""

    # "pasada" / "fallada" según la decisión sobre la carta de misión; None si no hay carta o no se decidió.
    def veredicto(self):
        if not self.tiene_carta_de_mision():
            return None
        return confianza_misiones.veredicto(self._mision, self.decision_mision)

    def _preparar_carta(self, azar):
        estado = self._estado
        cartas = getattr(estado, "cartas_mision", None)
        if estado is None or cartas is None:
            return
        if estado.noticia_forzada():            # un lote anterior se abandonó con su carta en mesa
            estado.retirar_noticia_forzada()
        cantidad = self._mision.cantidad_noticias
        if cantidad < 1 or not cartas.tiene(self._mision.id):
            return
        self._cartas = cartas
        # Sin noticias en el mazo la carta de misión sale la primera (si no, el lote no podría empezar).
        self._puesto_carta = azar.randrange(cantidad) if estado.hay_noticia() else 0
        self._poner_carta_si_toca()

    # Pone la carta de misión en mesa si es su puesto (o ya, con `ahora`). True si la puso.
    def _poner_carta_si_toca(self, ahora=False):
        if self._carta_jugada or self._carta_en_mesa or self._puesto_carta is None:
            return False
        if not ahora and self.decisiones + self.descartadas != self._puesto_carta:
            return False
        nodo, camino = self._cartas.carta(self._mision.id)
        self._estado.forzar_noticia(nodo, camino, self._cartas.arbol_stats)
        self._carta_en_mesa = True
        return True

    # -- Decisiones --

    # Anota una decisión ("compartir" / "reportar") con los `deltas` que aplicó el estado
    # (None = no se aplicó nada: no cuenta). `quedan_noticias` False marca el lote como
    # terminado aunque no se llegue a la cantidad pedida (mazo agotado). Devuelve la
    # propagación completa (con "niveles", para animarla) o None si no hubo.
    def registrar(self, decision, deltas, quedan_noticias=True):
        if self._carta_en_mesa:                 # la decisión que llega es la de la carta de misión
            self._carta_en_mesa = False
            self._carta_jugada = True
            if deltas is not None:
                self.decision_mision = decision
        if deltas is None:
            self.descartadas += 1
        else:
            self.decisiones += 1
            for nombre in NOMBRES_INDICADORES:
                self.deltas_acumulados[nombre] += deltas.get(nombre, 0)
        completo = self.decisiones + self.descartadas >= self._mision.cantidad_noticias
        # La carta de misión sale en su puesto; y si el mazo se agotó antes, sale ya (todo lote de verificar la trae).
        if not completo and self._poner_carta_si_toca(ahora=not quedan_noticias):
            quedan_noticias = True
        if not quedan_noticias:
            self._sin_noticias = True
        if deltas is None:
            return None
        return self._propagar(decision)

    def terminada(self):
        return (self.decisiones + self.descartadas >= self._mision.cantidad_noticias
                or self._sin_noticias)

    # Dict que recibe SistemaMisiones.completar(); contiene copias, no el estado vivo. Con carta de misión añade
    # "decision_mision" y "veredicto" (los leen SistemaMisiones y FlujoConGameState); sin ella es el de siempre.
    def resultado(self):
        resultado = {
            "mision": self._mision.id,
            "decisiones": self.decisiones,
            "deltas": dict(self.deltas_acumulados),
            "propagaciones": [dict(p) for p in self.propagaciones],
            "alcance_total": sum(p["alcance"] for p in self.propagaciones),
        }
        if self.tiene_carta_de_mision():
            resultado["decision_mision"] = self.decision_mision
            resultado["veredicto"] = self.veredicto()
        return resultado

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

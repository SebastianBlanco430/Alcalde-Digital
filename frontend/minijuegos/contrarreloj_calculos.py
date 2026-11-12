# Minijuego «Contrarreloj» (lógica pura, sin ursina): llegan noticias al chat una tras otra y cada una se propaga sola en `ritmo`
# segundos. Para cada una hay que decidir a tiempo: FRENAR (si es falsa) o DEJAR PASAR (si es verdadera). Una noticia que se
# propaga sin que el jugador decida NO suma (no se juzgó). La del rumor de la misión se mezcla con las del caso.

import random

from backend.logica.minijuegos import CONTRARRELOJ, ResultadoMinijuego

INTERVALO_APARICION = 3.0       # s entre una noticia y la siguiente
UMBRAL_CONTRARRELOJ = 0.7       # hay que acertar la mayoría con margen (dejarlo todo pasar no basta)

PENDIENTE, FRENADA, LIBERADA, PROPAGADA = "pendiente", "frenada", "liberada", "propagada"


class PartidaContrarreloj:

    def __init__(self, caso, mision_texto, mision_veraz, azar=None):
        azar = azar if azar is not None else random.Random()
        self.caso = caso
        cartas = [dict(c) for c in caso["cartas"]]
        propia = {"texto": mision_texto, "veraz": bool(mision_veraz), "ritmo": 11, "es_mision": True}
        cartas.insert(azar.randrange(len(cartas) + 1), propia)
        self.cartas = []
        for i, c in enumerate(cartas):
            self.cartas.append({"texto": c["texto"], "veraz": bool(c["veraz"]), "ritmo": float(c["ritmo"]),
                                "es_mision": bool(c.get("es_mision")), "aparece": i * INTERVALO_APARICION,
                                "estado": PENDIENTE})
        self.t = 0.0

    @property
    def duracion(self):
        return max(c["aparece"] + c["ritmo"] for c in self.cartas)

    @property
    def terminada(self):
        return all(c["estado"] != PENDIENTE for c in self.cartas)

    def visible(self, i):
        return self.t >= self.cartas[i]["aparece"]

    def propagacion(self, i):
        """0..1: cuánto se ha propagado la noticia i (1 = ya se difundió)."""
        c = self.cartas[i]
        if not self.visible(i):
            return 0.0
        if c["estado"] == FRENADA:
            return 0.0
        return max(0.0, min(1.0, (self.t - c["aparece"]) / c["ritmo"]))

    def avanzar(self, dt):
        self.t += dt
        for i, c in enumerate(self.cartas):
            if c["estado"] == PENDIENTE and self.visible(i) and self.t - c["aparece"] >= c["ritmo"]:
                c["estado"] = PROPAGADA

    def _decidir(self, i, estado):
        if not 0 <= i < len(self.cartas) or not self.visible(i) or self.cartas[i]["estado"] != PENDIENTE:
            return False
        self.cartas[i]["estado"] = estado
        return True

    def frenar(self, i):
        return self._decidir(i, FRENADA)

    def dejar_pasar(self, i):
        return self._decidir(i, LIBERADA)

    def acierta(self, i):
        c = self.cartas[i]
        return (c["estado"] == FRENADA and not c["veraz"]) or (c["estado"] == LIBERADA and c["veraz"])

    def resultado(self):
        total = float(len(self.cartas))
        aciertos = float(sum(1 for i in range(len(self.cartas)) if self.acierta(i)))
        frenadas_mal = sum(1 for c in self.cartas if c["estado"] == FRENADA and c["veraz"])
        propagadas = sum(1 for c in self.cartas if c["estado"] == PROPAGADA)
        if aciertos == total:
            detalle = "Frenaste lo falso y dejaste pasar lo cierto."
        elif propagadas:
            detalle = "Algunas noticias se propagaron antes de que las juzgaras."
        elif frenadas_mal:
            detalle = "Frenaste una noticia que era cierta."
        else:
            detalle = "Dejaste pasar una noticia falsa."
        return ResultadoMinijuego(CONTRARRELOJ, aciertos, total, self.terminada, detalle, umbral=UMBRAL_CONTRARRELOJ)

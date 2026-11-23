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
        detalle = detalle_resultado(self.cartas, [self.acierta(i) for i in range(len(self.cartas))])
        return ResultadoMinijuego(CONTRARRELOJ, aciertos, total, self.terminada, detalle, umbral=UMBRAL_CONTRARRELOJ)


# -- Lo que se enseña al terminar (puro): la etiqueta de cada papel y la frase del resultado salen de la MISMA fuente de
# verdad (`veraz` de cada carta; la del rumor es mision.es_verdadera) y no se contradicen (retoques 2026-11-22, M3). --

def etiqueta_final(carta, acierto):
    """«BIEN: era cierta», «MAL: era falsa»... de un papel al terminar."""
    return ("BIEN" if acierto else "MAL") + (": era cierta" if carta["veraz"] else ": era falsa")


def _noticias(n, singular, plural):
    return singular if n == 1 else plural.format(n=n)


def detalle_resultado(cartas, aciertos):
    """Frase del resultado. Si el rumor de la misión salió mal, habla de él; si salió bien y el fallo está en OTRAS
    noticias, lo dice («Con el rumor acertaste, pero…»): así no parece que la frase hable del rumor."""
    if all(aciertos):
        return "Frenaste lo falso y dejaste pasar lo cierto."
    i_mision = next((i for i, c in enumerate(cartas) if c.get("es_mision")), None)
    if i_mision is not None and not aciertos[i_mision]:
        c = cartas[i_mision]
        if c["estado"] == PROPAGADA:
            return "El rumor se difundió antes de que lo juzgaras."
        if c["estado"] == FRENADA:
            return "Frenaste el rumor y era cierto."
        return "Dejaste pasar el rumor y era falso."
    fallos = [c for i, c in enumerate(cartas) if not aciertos[i] and i != i_mision]
    propagadas = sum(1 for c in fallos if c["estado"] == PROPAGADA)
    frenadas = sum(1 for c in fallos if c["estado"] == FRENADA)
    liberadas = len(fallos) - propagadas - frenadas
    if propagadas:
        parte = _noticias(propagadas, "otra noticia se difundió antes de que la juzgaras",
                          "{n} noticias se difundieron antes de que las juzgaras")
    elif frenadas:
        parte = _noticias(frenadas, "frenaste otra noticia que era cierta", "frenaste {n} noticias que eran ciertas")
    else:
        parte = _noticias(liberadas, "dejaste pasar otra noticia falsa", "dejaste pasar {n} noticias falsas")
    if i_mision is None:
        parte = parte.replace("otra noticia", "una noticia")
        return parte[0].upper() + parte[1:] + "."
    return "Con el rumor acertaste, pero " + parte + "."


def sello_con_rumor(partida, texto):
    """El sello del veredicto (`texto`) solo si el papel del rumor de la misión quedó bien; si no, None."""
    if partida is None:
        return texto
    i = next((k for k, c in enumerate(partida.cartas) if c.get("es_mision")), None)
    return None if i is not None and not partida.acierta(i) else texto

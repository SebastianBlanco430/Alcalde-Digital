# Minijuego «Señales de edición» (lógica pura, sin ursina): una captura con varias zonas; el jugador marca las que delatan
# edición o engaño (máximo `max_marcas`). Con una captura auténtica (rumor verdadero) no hay señales y lo correcto es decirlo.

from backend.logica.minijuegos import SENALES, ResultadoMinijuego

PENALIZACION_MARCA_DE_MAS = 0.5


class PartidaSenales:

    def __init__(self, caso):
        self.caso = caso
        autentica = bool(caso.get("es_verdadera", False))
        self.zonas = [{"id": z["id"], "texto": z.get("texto_ok", z["texto"]) if autentica else z["texto"],
                       "lupa": z["lupa"], "falla": bool(z["falla"]) and not autentica, "explica": z["explica"]}
                      for z in caso["zonas"]]
        self.max_marcas = int(caso.get("max_marcas", 3))
        self.marcadas = set()
        self.sin_senales = False
        self.confirmada = False

    @property
    def terminada(self):
        return self.confirmada

    def fallas(self):
        return {i for i, z in enumerate(self.zonas) if z["falla"]}

    def marcar(self, i):
        """Alterna la marca de la zona i (hasta max_marcas). Devuelve True si quedó marcada."""
        if self.confirmada or not 0 <= i < len(self.zonas):
            return False
        self.sin_senales = False
        if i in self.marcadas:
            self.marcadas.discard(i)
            return False
        if len(self.marcadas) >= self.max_marcas:
            return False
        self.marcadas.add(i)
        return True

    def marcas_libres(self):
        return self.max_marcas - len(self.marcadas)

    def declarar_sin_senales(self):
        if self.confirmada:
            return
        self.marcadas.clear()
        self.sin_senales = True
        self.confirmada = True

    def confirmar(self):
        self.confirmada = True

    def resultado(self):
        reales = self.fallas()
        if not reales:
            ok = self.sin_senales and not self.marcadas
            return ResultadoMinijuego(SENALES, 1.0 if ok else 0.0, 1.0, self.confirmada,
                                      "Viste que la captura parecía auténtica." if ok else "La captura era auténtica.")
        halladas = len(self.marcadas & reales)
        de_mas = len(self.marcadas - reales)
        puntos = max(0.0, halladas - PENALIZACION_MARCA_DE_MAS * de_mas)
        detalle = f"Encontraste {halladas} de {len(reales)} señales."
        if de_mas:
            detalle += " Sospechaste de algo que estaba bien."
        return ResultadoMinijuego(SENALES, puntos, float(len(reales)), self.confirmada, detalle)

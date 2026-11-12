# Minijuego «Comparar dos versiones» (lógica pura, sin ursina): a la izquierda lo que dice el ORIGINAL (el cartel, la foto, el
# audio) y a la derecha la COPIA que circula. El jugador marca las líneas de la copia que fueron alteradas. Si el rumor era
# verdadero la copia es idéntica y lo correcto es decir «no veo diferencias». Cada marca de más resta medio acierto.

from backend.logica.minijuegos import COMPARAR, ResultadoMinijuego

PENALIZACION_MARCA_DE_MAS = 0.5


class PartidaComparar:

    def __init__(self, caso):
        self.caso = caso
        self.lineas = []
        for linea in caso["lineas"]:
            alterada = "c" in linea and not caso.get("es_verdadera", False)
            self.lineas.append({"etiqueta": linea["e"], "original": linea["o"],
                                "copia": linea["c"] if alterada else linea["o"], "alterada": alterada})
        self.marcadas = set()
        self.sin_diferencias = False
        self.confirmada = False

    @property
    def terminada(self):
        return self.confirmada

    def alteradas(self):
        return {i for i, linea in enumerate(self.lineas) if linea["alterada"]}

    def marcar(self, i):
        """Alterna la marca de la línea i. Devuelve True si quedó marcada."""
        if self.confirmada or not 0 <= i < len(self.lineas):
            return False
        self.sin_diferencias = False
        if i in self.marcadas:
            self.marcadas.discard(i)
            return False
        self.marcadas.add(i)
        return True

    def declarar_sin_diferencias(self):
        if self.confirmada:
            return
        self.marcadas.clear()
        self.sin_diferencias = True
        self.confirmada = True

    def confirmar(self):
        self.confirmada = True

    def resultado(self):
        reales = self.alteradas()
        if not reales:                       # copia idéntica: lo correcto es no marcar nada y decirlo
            ok = self.sin_diferencias and not self.marcadas
            return ResultadoMinijuego(COMPARAR, 1.0 if ok else 0.0, 1.0, self.confirmada,
                                      "Viste que las dos versiones coinciden." if ok else "Las dos versiones coincidían.")
        encontradas = len(self.marcadas & reales)
        de_mas = len(self.marcadas - reales)
        puntos = max(0.0, encontradas - PENALIZACION_MARCA_DE_MAS * de_mas)
        detalle = f"Encontraste {encontradas} de {len(reales)} alteraciones."
        if de_mas:
            detalle += " Marcaste algo que no estaba alterado."
        return ResultadoMinijuego(COMPARAR, puntos, float(len(reales)), self.confirmada, detalle)

# Fundido REAL de un bloque de la UI entero (M3.6). Ursina pone setColorScaleOff() en el modelo de cada Entity (para
# que no herede el color del padre), así que un setAlphaScale en la raíz del bloque no llega a los hijos y el bloque
# «aparecía de golpe». Aquí se aplica el alfa pieza a pieza:
#   - Entity con modelo: model.setColorScale(color de la Entity con su alfa * alfa del bloque);
#   - Text: el alfa en el color de cada TextNode (el shader de texto de Ursina ignora la escala de color).
# La lista de piezas se recoge al empezar un fundido y se olvida al terminar (alfa 1 restaura los colores exactos de
# Ursina) o cuando el bloque se rehace (invalidar()). Solo trabaja si el alfa cambió: un bloque quieto no cuesta nada.
# La lógica de tiempos (Fundido, TIEMPOS) es pura: frontend/hud_contextual_calculos.py.

from ursina import Text


class FundidoArbol:

    def __init__(self, raiz):
        self.raiz = raiz
        self._piezas = None
        self.alfa = None
        self._color_texto = {}           # id(NodePath del TextNode) -> color original (durante un fundido)

    def invalidar(self):
        """El bloque se rehízo (otros hijos): se recogen de nuevo en la próxima aplicación."""
        self._piezas = None
        if self.alfa is not None and self.alfa < 1.0:
            self.alfa = None             # que la próxima aplicación vuelva a pintar todo

    def _recoger(self):
        piezas, pendientes = [], [self.raiz]
        while pendientes:
            entidad = pendientes.pop()
            if isinstance(entidad, Text):
                piezas.append((True, entidad))
            elif getattr(entidad, "model", None) is not None:
                piezas.append((False, entidad))
            pendientes.extend(getattr(entidad, "children", ()) or ())
        return piezas

    def aplicar(self, alfa):
        alfa = max(0.0, min(1.0, round(float(alfa), 3)))
        if alfa == self.alfa and (self._piezas is not None or alfa >= 1.0):
            return
        if self._piezas is None:
            self._piezas = self._recoger()
        for es_texto, pieza in self._piezas:
            try:
                if pieza.isEmpty():
                    continue
                if es_texto:
                    # El shader de texto de Ursina no usa la escala de color: el alfa va en el color de cada TextNode
                    # (el original se recuerda al empezar el fundido y se repone tal cual en alfa 1).
                    for nodo in getattr(pieza, "text_nodes", ()) or ():
                        tn = nodo.node()
                        original = self._color_texto.setdefault(id(nodo), tuple(tn.getTextColor()))   # copia; clave = NodePath vivo
                        tn.setTextColor(original[0], original[1], original[2], original[3] * alfa)
                    for imagen in getattr(pieza, "images", ()) or ():
                        c = imagen.color
                        imagen.model.setColorScale(c[0], c[1], c[2], c[3] * alfa)
                else:
                    c = pieza.color
                    pieza.model.setColorScale(c[0], c[1], c[2], c[3] * alfa)
            except Exception:            # pieza destruida a medias: se ignora
                continue
        self.alfa = alfa
        if alfa >= 1.0:
            self._piezas = None          # colores exactos restaurados: nada que recordar hasta el próximo fundido
            self._color_texto = {}

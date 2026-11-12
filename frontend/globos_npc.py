# Globos de texto sobre los NPC (Ursina). La lógica (qué frase, cuándo, sin repetir) es backend/logica/globos.py; aquí
# solo se dibuja una PISCINA FIJA de globos (globos.RANURAS) que se prestan al NPC que habla y se devuelven.
#
# Sin fugas: los Text y sus fondos se crean UNA vez en __init__ (y las anclas de cabeza las pide quien instala, también
# una vez); después solo se cambia el texto, el padre y la opacidad. Nada se crea ni se destruye por frame.
#
# Cada globo es piezas.etiqueta (billboard: siempre mira a la cámara) colgado del ancla de la cabeza del NPC
# (npc_postura.ancla_cabeza), con el tamaño aparente acotado de cerca (piezas.limitar_etiqueta) y un fundido de entrada
# y de salida (escala de color del nodo: no toca los colores del texto).

from ursina import Entity, color

from backend.logica import globos
from frontend import npc_postura
from frontend.piezas import etiqueta, limitar_etiqueta, silenciar

ESCALA_TEXTO = 7.0               # como los carteles de nombre de los NPC clave (8)
AJUSTE_LINEA = 26                # caracteres por línea (la frase más larga, 90, son 4 líneas)
ALTURA = 0.32                    # m sobre el ancla de la cabeza
COLOR_TEXTO = (28, 30, 40)
COLOR_FONDO = (250, 248, 238, 235)
RELLENO = (0.045, 0.028)         # relleno del fondo, en unidades del texto


class GlobosNPC:

    def __init__(self, parent, planificador):
        self.plan = planificador
        self.reserva = Entity(parent=parent, enabled=True)       # donde descansan los globos libres
        self._globos, self._series, self._duenos = [], [], []
        for _ in planificador.ranuras:
            texto = etiqueta("…", parent=self.reserva, scale=ESCALA_TEXTO, color=color.rgb32(*COLOR_TEXTO),
                             wordwrap=AJUSTE_LINEA, y=ALTURA)
            texto.background_entity.color = color.rgba32(*COLOR_FONDO)
            texto.setTransparency(True)
            texto.enabled = False
            silenciar(texto)
            self._globos.append(texto)
            self._series.append(0)
            self._duenos.append(None)
        self.mostrados = 0

    def _ajustar_fondo(self, texto):
        fondo = texto.background_entity
        fondo.scale = (texto.width + RELLENO[0], texto.height + RELLENO[1])

    def _soltar(self, k):
        texto = self._globos[k]
        if texto.enabled:
            texto.enabled = False
            texto.parent = self.reserva
        self._duenos[k] = None

    def actualizar(self, dt, candidatos=(), nivel=None, hora=None, dia=None):
        """`candidatos`: [(clave, estado, distancia, peso, npc)] ya filtrados (cerca y a la vista). El npc es la Entity
        del personaje (se usa su ancla de cabeza)."""
        plan = self.plan
        cuerpos = {c[0]: c[4] for c in candidatos}
        plan.avanzar(dt, candidatos, nivel, hora, dia)
        for k, ranura in enumerate(plan.ranuras):
            texto = self._globos[k]
            if ranura.clave is None:
                if texto.enabled:
                    self._soltar(k)
                continue
            cuerpo = cuerpos.get(ranura.clave)
            if ranura.serie != self._series[k]:                  # globo nuevo en esta ranura
                self._series[k] = ranura.serie
                if cuerpo is None:
                    ranura.clave = None
                    self._soltar(k)
                    continue
                texto.text = ranura.texto
                self._ajustar_fondo(texto)
                texto.parent = npc_postura.ancla_cabeza(cuerpo)
                texto.position = (0, ALTURA, 0)
                texto.enabled = True
                self._duenos[k] = cuerpo
                self.mostrados += 1
            elif cuerpo is not None and cuerpo is not self._duenos[k]:
                ranura.clave = None                              # el actor se prestó a otro agente: el globo no lo hereda
                self._soltar(k)
                continue
            texto.setColorScale(1, 1, 1, plan.alfa(k))
            limitar_etiqueta(texto)

    def ocultar(self):
        self.plan.vaciar()
        for k in range(len(self._globos)):
            self._soltar(k)

    def visibles(self):
        return sum(1 for g in self._globos if g.enabled)

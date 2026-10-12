# Panel "Alcance en Civitas" (Ursina, en camera.ui): dibuja el grafo social pequeño y
# anima por saltos cómo se propaga una publicación tras "Compartir" (o cómo se frena
# tras "Reportar"). Todo lo que decide (posiciones, estados por tiempo, textos) está en
# frontend/grafo_social_vista.py (Python puro, con tests); aquí solo se dibuja.
#
# El panel no tiene update(): quien lo posee (EscenaJuego) llama a avanzar(dt) en su
# update(), así una escena desactivada no gasta nada y las pruebas pueden avanzar a mano.
# Solo muestra el alcance: NO modifica indicadores.

from panda3d.core import TextNode
from ursina import Entity, Text, destroy

from frontend import estilo, grafo_social_vista as vista, hud_calculos
from frontend.componentes import escala_fuente, modelo_redondeado, rgb
from frontend.texto import envolver_texto

# Colores de los nodos por estado / salto (RGB 0-255), misma paleta que el HUD.
COLOR_ORIGEN = (255, 220, 60)                  # amarillo: quien publica
COLORES_SALTO = {1: (70, 220, 255), 2: (80, 190, 110)}   # cian, verde
COLOR_SALTO_LEJANO = (235, 140, 60)            # saltos 3 o más
COLOR_PENDIENTE = estilo.COLOR_BARRA_FONDO
COLOR_FRENADO = estilo.COLOR_BARRA_BAJO
COLOR_ARISTA_INACTIVA = (70, 74, 100)
COLOR_FONDO_PANEL = estilo.COLOR_PANEL
COLOR_TEXTO_OSCURO = (24, 26, 38)


def _color_del_salto(salto):
    if salto <= 0:
        return COLOR_ORIGEN
    return COLORES_SALTO.get(salto, COLOR_SALTO_LEJANO)


class PanelPropagacion(Entity):

    ANCHO, ALTO = 0.28, 0.46
    TITULO = "Alcance en Civitas"
    MEDIO_ANCHO_GRAFO = 0.11     # los nodos usan x en [-1, 1] -> [-0.105, 0.105]
    MEDIO_ALTO_GRAFO = 0.125
    CENTRO_GRAFO_Y = 0.025
    DIAMETRO_NODO = 0.042
    GROSOR_ARISTA = 0.004
    GROSOR_ARISTA_ACTIVA = 0.007

    def __init__(self, grafo_social=None, **opciones):
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        Entity(parent=self, model=modelo_redondeado(self.ANCHO, self.ALTO, 10),
               scale=(self.ANCHO, self.ALTO), color=rgb(COLOR_FONDO_PANEL), z=0.001)
        Text(self.TITULO, parent=self, origin=(0, 0), position=(0, self.ALTO / 2 - 0.028, -0.001),
             scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO))
        self.texto_resultado = Text(
            "", parent=self, origin=(0, 0), position=(0, -self.ALTO / 2 + 0.042, -0.001),
            scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.texto_resultado.line_height = 1.25
        self._capa_aristas = Entity(parent=self, z=-0.001)
        self._capa_nodos = Entity(parent=self, z=-0.002)
        self._medir = self._crear_medidor()

        self._grafo = None
        self._aristas = []          # [(a, b)]
        self._cuadros = {}          # (a, b) -> cuadro de la arista
        self._nodos = {}            # nombre -> (círculo, letra)
        self.propagacion = None
        self.tiempo = 0.0
        self.cadena_resultado = ""   # el texto sin saltos de línea de la envoltura
        self._firma = None
        if grafo_social is not None:
            self.fijar_grafo(grafo_social)

    def _crear_medidor(self):
        nodo = TextNode("medida_propagacion")
        nodo.setFont(self.texto_resultado.font)
        factor = self.texto_resultado.size * self.texto_resultado.scale_x
        return lambda cadena: nodo.calcWidth(cadena) * factor

    # -- Construcción --

    # Crea los nodos y aristas del grafo social (se llama una vez al inyectar el grafo).
    def fijar_grafo(self, grafo_social):
        if grafo_social is self._grafo:
            return
        for hijo in list(self._capa_aristas.children) + list(self._capa_nodos.children):
            destroy(hijo)
        self._grafo = grafo_social
        self._cuadros, self._nodos = {}, {}
        pos = vista.posiciones(grafo_social)
        self._puntos = {
            n: (x * self.MEDIO_ANCHO_GRAFO, y * self.MEDIO_ALTO_GRAFO + self.CENTRO_GRAFO_Y)
            for n, (x, y) in pos.items()
        }
        self._aristas = vista.aristas(grafo_social)
        for a, b in self._aristas:
            cu, cv, largo, rotacion = hud_calculos.segmento_a_cuadro(self._puntos[a], self._puntos[b])
            cuadro = Entity(parent=self._capa_aristas, model="quad", position=(cu, cv),
                            rotation_z=rotacion, scale=(largo, self.GROSOR_ARISTA),
                            color=rgb(COLOR_ARISTA_INACTIVA))
            self._cuadros[(a, b)] = cuadro
        for nombre, (px, py) in self._puntos.items():
            contenedor = Entity(parent=self._capa_nodos, position=(px, py))
            circulo = Entity(parent=contenedor, model="circle", scale=self.DIAMETRO_NODO,
                             color=rgb(COLOR_PENDIENTE))
            letra = Text(nombre[0], parent=contenedor, origin=(0, 0), position=(0, 0, -0.001),
                         scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self._nodos[nombre] = (circulo, letra)

    # -- Control --

    # Muestra el panel y arranca la animación de `propagacion` desde t = 0 (un nuevo
    # clic reinicia). Sin grafo inyectado no hace nada.
    def mostrar(self, propagacion):
        if self._grafo is None:
            return
        self.propagacion = propagacion
        self.tiempo = 0.0
        self._firma = None
        self.enabled = True
        self._dibujar()

    def ocultar(self):
        self.propagacion = None
        self.tiempo = 0.0
        self.enabled = False

    # Un paso de `dt` segundos: avanza el reloj de la animación (se detiene sola al
    # terminar los saltos) y redibuja si cambió algo. Sin propagación no hace nada.
    def avanzar(self, dt):
        if self.propagacion is None:
            return
        tope = vista.duracion_total(self.propagacion)
        self.tiempo = min(self.tiempo + dt, tope)
        self._dibujar()

    # -- Consultas (las usan las pruebas) --

    def animacion_terminada(self):
        return self.propagacion is not None and vista.terminada(self.propagacion, self.tiempo)

    def estados_nodos(self):
        if self.propagacion is None:
            return {}
        return vista.estado_nodos(self.propagacion, self._grafo.ciudadanos(), self.tiempo)

    def salto(self):
        return 0 if self.propagacion is None else vista.salto_actual(self.propagacion, self.tiempo)

    # -- Dibujo --

    def _dibujar(self):
        propagacion = self.propagacion
        salto = vista.salto_actual(propagacion, self.tiempo)
        if (propagacion["accion"], salto) == self._firma:
            return
        self._firma = (propagacion["accion"], salto)

        estados = vista.estado_nodos(propagacion, self._grafo.ciudadanos(), self.tiempo)
        saltos = vista.saltos_por_ciudadano(propagacion)
        for nombre, (circulo, letra) in self._nodos.items():
            estado = estados[nombre]
            if estado == vista.ORIGEN:
                tono, tinta = COLOR_ORIGEN, COLOR_TEXTO_OSCURO
            elif estado == vista.ALCANZADO:
                tono, tinta = _color_del_salto(saltos[nombre]), COLOR_TEXTO_OSCURO
            elif estado == vista.FRENADO:
                tono, tinta = COLOR_FRENADO, estilo.COLOR_TEXTO
            else:
                tono, tinta = COLOR_PENDIENTE, estilo.COLOR_TEXTO_TENUE
            circulo.color = rgb(tono)
            letra.color = rgb(tinta)

        activas = vista.estado_aristas(propagacion, self._aristas, self.tiempo)
        for arista, cuadro in self._cuadros.items():
            if activas[arista]:
                a, b = arista
                cuadro.color = rgb(_color_del_salto(max(saltos[a], saltos[b])))
                cuadro.scale_y = self.GROSOR_ARISTA_ACTIVA
            else:
                cuadro.color = rgb(COLOR_ARISTA_INACTIVA)
                cuadro.scale_y = self.GROSOR_ARISTA

        cadena = vista.texto_resultado(propagacion, self._grafo.numero_ciudadanos(), self.tiempo)
        self.cadena_resultado = cadena
        lineas = envolver_texto(cadena, self._medir, self.ANCHO - 0.03) or [""]
        self.texto_resultado.text = "\n".join(lineas)

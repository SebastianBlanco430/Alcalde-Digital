# Pantalla previa de un minijuego de verificar (Ursina): «Antes de empezar». La enseña EscenaMinijuego entre el clic en la
# puerta y el minijuego, para que el jugador no caiga de golpe en una mecánica que no conoce. Dice:
#   - qué minijuego es y qué rumor se verifica (el mismo encabezado que verá después);
#   - el objetivo en una o dos frases;
#   - CÓMO SE JUEGA (tres pasos) y LO QUE PRACTICAS EN REDES (el hábito de uso adecuado de las redes sociales), en dos
#     tarjetas iguales lado a lado;
#   - las teclas (la AYUDA de la vista) y el botón «Empezar» (Enter, Espacio o clic).
# Los textos viven en backend/datos/minijuegos_instrucciones.py. Esta vista no sabe nada del flujo: solo llama a `al_empezar`.
#
# Zonas (camera.ui, mismas que frontend/minijuegos/base.py): encabezado arriba, tarjetas en el centro, botón en y -0,37.

from ursina import Entity, Text

from frontend import estilo
from frontend.componentes import a_unidades, escala_fuente, rgb
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Y_ENCABEZADO

SEPARACION = 0.04               # entre las dos tarjetas (y margen vertical entre bloques)
Y_BOTON = -0.37
PX_TARJETA = 17


class PantallaPrevia(Entity):

    def __init__(self, titulo, rumor, instrucciones, ayuda, al_empezar, corta=False, al_ver_tutorial=None, **opciones):
        super().__init__(**opciones)
        self.al_empezar = al_empezar
        self.al_ver_tutorial = al_ver_tutorial
        x0 = -ANCHO_UTIL / 2
        y = Y_ENCABEZADO
        ui.texto(self, "ANTES DE EMPEZAR", 14, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE, (x0, y), negrita=True)
        y -= a_unidades(24)
        cabeza = ui.texto(self, titulo, 30, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, y), negrita=True)
        y -= cabeza.alto + a_unidades(4)
        linea_rumor = ui.texto(self, "Rumor a verificar: «" + rumor + "»", 17, ANCHO_UTIL, estilo.COLOR_ACENTO, (x0, y))
        y -= linea_rumor.alto + a_unidades(14)
        objetivo = ui.texto(self, instrucciones["objetivo"], 20, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, y))
        y -= objetivo.alto + a_unidades(16)

        # Dos tarjetas del MISMO alto (el de la más larga) y el mismo ancho: la pantalla queda simétrica.
        # Versión CORTA (tras el tutorial: los pasos ya se vieron): una sola tarjeta con el hábito de redes, a todo el ancho.
        ancho = ANCHO_UTIL if corta else (ANCHO_UTIL - SEPARACION) / 2
        # Una línea en blanco entre pasos: sin sangría colgante, los pasos de dos líneas se leían como un solo bloque.
        pasos = "\n\n".join(f"{i}. {p}" for i, p in enumerate(instrucciones["pasos"], start=1))
        redes = instrucciones["redes"]
        alto = ui.Tarjeta.alto_necesario(redes, ancho, PX_TARJETA, "x", 14, margen_px=14)
        if not corta:
            alto = max(alto, ui.Tarjeta.alto_necesario(pasos, ancho, PX_TARJETA, "x", 14, margen_px=14))
        self.tarjetas = []
        contenidos = ((("LO QUE PRACTICAS EN REDES", redes),) if corta
                      else (("CÓMO SE JUEGA", pasos), ("LO QUE PRACTICAS EN REDES", redes)))
        for i, (rotulo, cuerpo) in enumerate(contenidos):
            t = ui.Tarjeta(ancho, alto, cuerpo, rotulo, PX_TARJETA, 14, parent=self, margen_px=14,
                           position=(x0 + ancho / 2 + i * (ancho + SEPARACION), y - alto / 2))
            t.golpe.collider = None            # informativas: no se eligen
            self.tarjetas.append(t)
        # La tarjeta de redes lleva el borde del color de información: es la idea que hay que llevarse.
        self.tarjetas[-1].borde.color = rgb(estilo.ESTADO_INFO)
        y -= alto + a_unidades(14)
        ui.texto(self, "Teclas: " + ayuda, 14, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE, (x0, y))

        self.boton = ui.Boton("Empezar", self._empezar, 0.36, 0.08, 22, primario=True, parent=self, position=(0, Y_BOTON))
        self.boton.fijar_foco(True)
        if al_ver_tutorial is not None:         # pequeño, a la izquierda: volver a ver el tutorial de este minijuego
            self.boton_tutorial = ui.Boton("Ver tutorial", self._ver_tutorial, 0.24, 0.05, 15, parent=self,
                                           position=(-ANCHO_UTIL / 2 + 0.12, Y_BOTON))
        Text("Enter o Espacio", parent=self, origin=(0, 0.5), position=(0, Y_BOTON - 0.055, ui.Z_TEXTO),
             scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO_TENUE))

    def _empezar(self):
        callback, self.al_empezar = self.al_empezar, None      # una sola vez
        if callback is not None:
            callback()

    def _ver_tutorial(self):
        callback, self.al_ver_tutorial = self.al_ver_tutorial, None      # una sola vez
        if callback is not None:
            callback()

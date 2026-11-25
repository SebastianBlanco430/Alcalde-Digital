# Marco de «teléfono de Civitas» para cualquier panel de las misiones visuales (Ursina, camera.ui): un borde oscuro de
# carcasa alrededor del panel, la barra de estado con la hora, la cobertura y la batería, y el nombre de la app.
# Por qué: las misiones de redes ocurren en el teléfono; verlas dentro de uno conecta el minijuego con Civitas.
# Lo usan frontend/minijuegos_visual/chat_visual.py (y los pasos de Civitas y rectificar).
#
# Solo dibuja (no tiene update). batería(f) permite que una pantalla la baje (tiempo de pantalla).
# Los textos de hora salen de frontend/minijuegos_visual/chat_visual_calculos.hora_texto (puro, con tests).
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

import datetime

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos_visual.chat_visual_calculos import hora_texto

CARCASA = (24, 26, 34)
GROSOR = 0.014


class MarcoTelefono(Entity):
    """Carcasa alrededor de un panel de `ancho` x `alto` centrado en `centro`. La barra de estado va dentro, arriba a la derecha."""

    def __init__(self, ancho, alto, centro, app="Civitas", minutos=None, **opciones):
        super().__init__(**opciones)
        cx, cy = centro
        self.ancho, self.alto = ancho, alto
        ui.rect(self, ancho + 2 * GROSOR, alto + 2 * GROSOR, CARCASA, (cx, cy), z=0.008, radio_px=16)
        ui.rect(self, ancho + 2 * GROSOR + 0.006, alto + 2 * GROSOR + 0.006, estilo.TINTA, (cx, cy), z=0.009, radio_px=18)
        if minutos is None:
            ahora = datetime.datetime.now()
            minutos = ahora.hour * 60 + ahora.minute
        y = cy + alto / 2 - 0.016
        x_der = cx + ancho / 2 - 0.012
        self.hora = Text(hora_texto(minutos), parent=self, origin=(0.5, 0), position=(x_der - 0.075, y, -0.03),
                         scale=escala_fuente(12), font=tipografia.fuente_piel(titulo=True), color=color.rgba32(*estilo.COLOR_TEXTO, 230))
        # Batería: contorno + relleno.
        self._bateria_borde = ui.rect(self, 0.04, 0.016, estilo.COLOR_TEXTO_TENUE, (x_der - 0.024, y), z=-0.028, radio_px=3)
        self._bateria = Entity(parent=self, model="quad", origin=(-0.5, 0), color=color.rgba32(88, 214, 141, 255),
                               position=(x_der - 0.042, y, -0.031), scale=(0.036, 0.011))
        for i in range(3):
            Entity(parent=self, model="quad", color=color.rgba32(*estilo.COLOR_TEXTO_TENUE, 230),
                   position=(x_der - 0.158 + i * 0.008, y - 0.005 + i * 0.0025, -0.03), scale=(0.005, 0.006 + i * 0.005))
        self.app = Text(app, parent=self, origin=(0.5, 0), position=(x_der - 0.175, y, -0.03), scale=escala_fuente(11),
                        color=color.rgba32(*estilo.COLOR_ACENTO, 220))

    def bateria(self, fraccion):
        f = max(0.0, min(1.0, fraccion))
        self._bateria.scale_x = max(0.001, 0.036 * f)
        tono = (88, 214, 141) if f > 0.4 else ((240, 160, 60) if f > 0.15 else (235, 87, 87))
        self._bateria.color = color.rgba32(*tono, 255)

    def fijar_minutos(self, minutos):
        self.hora.text = hora_texto(minutos)

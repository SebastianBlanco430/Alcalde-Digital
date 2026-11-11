# Caja de diálogo de los NPC clave (Ursina, camera.ui): retrato con la expresión que pide la actitud (usa
# frontend/dialogo_retratos.py), nombre, rol + tono/actitud como TEXTO (no solo la cara) y el diálogo por páginas.
# Cumple el contrato de «modal» de frontend/economia_mundo.py (enabled, abrir, cerrar, tecla, actualizar): la abre
# economia.abrir_modal, que congela los controles y esconde el HUD mientras dura.
#
# Qué dice y con qué cara lo decide backend/logica/dialogos.py (Respuesta); aquí solo se dibuja. Avanzar: E, Intro,
# Espacio o clic; Esc cierra. Una guarda corta ignora la pulsación que abrió la caja (la misma E no salta la primera
# página). `al_final` se llama UNA vez, al mostrarse la última página (ahí se entrega la ayuda).

import time

from ursina import Entity, Text

from backend.logica.dialogos import Paginador
from frontend import diseno_adaptable, dialogo_retratos, estilo, tipografia
from frontend.componentes import escala_fuente, panel_tinta, rgb

ANCHO, ALTO = 1.30, 0.34
POS = (0.0, -0.31)
LADO_RETRATO = 0.27
TECLAS_AVANCE = ("e", "enter", "space", "left mouse down")
GUARDA_S = 0.25
TEXTO_AVANZAR = "E / Intro: continuar    Esc: salir"
TEXTO_CERRAR = "E / Intro: cerrar"


class CajaDialogo(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self.z = -0.05
        self.marco = panel_tinta(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL, position=(*POS, 0))
        retrato_marco = panel_tinta(self.marco, LADO_RETRATO + 0.02, LADO_RETRATO + 0.02, tono=estilo.COLOR_FONDO,
                                    position=(-ANCHO / 2 + LADO_RETRATO / 2 + 0.03, 0, -0.01))
        self.retrato = Entity(parent=retrato_marco, model="quad", scale=(LADO_RETRATO, LADO_RETRATO), z=-0.01)
        x0 = -ANCHO / 2 + LADO_RETRATO + 0.07
        self.nombre = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.025, -0.02),
                           scale=escala_fuente(21), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
        self.rol = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.065, -0.02),
                        scale=escala_fuente(14), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._base_texto = escala_fuente(19)
        self.texto = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.1, -0.02),
                          scale=self._base_texto, color=rgb(estilo.COLOR_TEXTO))
        self.pista = Text(TEXTO_AVANZAR, parent=self.marco, origin=(0.5, -0.5),
                          position=(ANCHO / 2 - 0.03, -ALTO / 2 + 0.02, -0.02), scale=escala_fuente(13),
                          color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.ancho_texto = ANCHO - LADO_RETRATO - 0.12
        self._respuesta = None
        self._retrato_json = None
        self._rol = ""
        self._paginador = None
        self._al_final = None
        self._avisado_final = False
        self._t_abierta = 0.0
        diseno_adaptable.ajustar_escala(self)

    # Contenido de la próxima apertura. `retrato_json`: dict de dialogo_retratos; `rol`: texto bajo el nombre.
    def preparar(self, respuesta, retrato_json, rol="", al_final=None):
        self._respuesta, self._retrato_json, self._rol = respuesta, retrato_json, rol
        self._paginador = Paginador(respuesta.lineas)
        self._al_final = al_final
        self._avisado_final = False

    # -- Contrato de modal --

    def abrir(self, control=None):
        if self._paginador is None:
            return
        self.enabled = True
        self._t_abierta = time.monotonic()
        self._mostrar()

    def cerrar(self):
        self.enabled = False

    def tecla(self, key):
        if key == "escape":
            return "cerrar"
        if key not in TECLAS_AVANCE or time.monotonic() - self._t_abierta < GUARDA_S or self._paginador is None:
            return None
        if self._paginador.avanzar():
            self._mostrar()
            return None
        return "cerrar"

    def actualizar(self):
        pass

    # -- Dibujo --

    def _mostrar(self):
        r = self._respuesta
        self.nombre.text = r.nombre
        etiqueta = r.actitud or r.tono
        self.rol.text = f"{self._rol}  ·  {etiqueta}" if self._rol else etiqueta
        if self._retrato_json:
            self.retrato.enabled = True
            self.retrato.texture = dialogo_retratos.textura_retrato_caso(self._retrato_json, r.expresion)
        else:
            self.retrato.enabled = False
        cadena = self._paginador.actual
        plan = diseno_adaptable.ajustar_texto(self.texto, self.ancho_texto, escala_base=self._base_texto,
                                              escala_min=0.75, max_lineas=5, cadena=cadena)
        if plan is None:
            self.texto.text = cadena
        ultima = self._paginador.es_ultima
        self.pista.text = TEXTO_CERRAR if ultima else TEXTO_AVANZAR
        if ultima and not self._avisado_final:
            self._avisado_final = True
            if self._al_final is not None:
                self._al_final()

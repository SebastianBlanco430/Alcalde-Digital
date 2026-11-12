# Dilemas jugables en el juego real (punto 7 del plan del dueño). frontend/extensiones.py llama a registrar(); no se edita
# main.py más allá de envolver el flujo (backend/logica/dilemas.envolver).
#
#   ENTRADA. Cuando toca, el flujo manda un mensaje al teléfono («La foto del cumple: tienes un mensaje sin responder. Pulsa K
#   para leerlo.») y aparece un chip «K · Mensaje sin responder» sobre el reloj. NADA se abre solo ni bloquea al jugador:
#   lo abre con K cuando quiera. Si no contesta en PLAZO_HORAS horas de juego cuenta como «ignorar» y tiene su consecuencia.
#   PANEL. K abre un panel modal (como el Archivo de casos: es un «bloqueador» de EscenaMundo, así que el reloj se detiene
#   por el vigía de registro_reloj, el jugador no se mueve y Escape lo cierra): título, situación y 2-3 opciones, cada una con
#   su pista en lenguaje natural (SIN números). 1-3 o clic eligen; Esc lo cierra SIN decidir (el mensaje sigue pendiente).
#   Al elegir, el mismo panel cuenta en palabras lo que pasó ya; el resto llega 24-48 h después como aviso de causa-efecto.
#   EN LÍNEA o sin flujo con dilemas (ALCALDE_DILEMAS=0, sin reloj): no hace nada y K queda libre.
#
# La lógica va en ControlDilemas (sin ursina; se prueba con escenas falsas, tests/test_registro_dilemas.py).
# API: conexion.dilemas_ui = ControlDilemas.

import sys

from backend.logica import dilemas as logica
from frontend import dilemas_calculos as dc
from frontend import teclas

TECLAS_CLIC = ("left mouse down",)
TECLAS_CONTINUAR = ("e", "enter", "space")
GUARDA_S = 0.25                       # la pulsación que abrió el panel no puede cerrarlo ni elegir


class ControlDilemas:
    """Estado del panel sin ursina. `escena`: lo que usa de EscenaMundo (flujo, online, en_pausa, _cinematica, hud,
    controles_bloqueados(), _sincronizar_raton()). `vista`: pinta (mostrar_dilema(contenido), mostrar_resultado(contenido),
    ocultar(), chip(texto, visible))."""

    def __init__(self, escena, vista, tecla=teclas.TECLA_DILEMAS):
        self.escena, self.vista, self.tecla_abrir = escena, vista, tecla
        self.fase = None                  # None (cerrado) | "decidiendo" | "resultado"
        self._contenido = None
        self.ultimo_resultado = None

    # -- Consulta --

    def abierto(self):
        return self.fase is not None

    def _flujo(self):
        flujo = self.escena.flujo
        if flujo is None or getattr(self.escena, "online", None) is not None or not callable(getattr(flujo, "dilema_pendiente", None)):
            return None
        return flujo

    def pendiente(self):
        flujo = self._flujo()
        return None if flujo is None else flujo.dilema_pendiente()

    def puede_abrir(self):
        escena = self.escena
        flujo = self._flujo()
        if flujo is None or not escena.enabled or escena.controles_bloqueados() or flujo.partida_terminada():
            return False
        try:
            if flujo.jugador_activo().telefono.bloquea_movimiento():
                return False
        except (AttributeError, TypeError):
            pass
        return self.pendiente() is not None

    # -- Abrir / cerrar --

    def abrir(self):
        oferta = self.pendiente()
        if oferta is None:
            return False
        self._contenido = dc.contenido_dilema(oferta)
        self.fase = "decidiendo"
        self.vista.mostrar_dilema(self._contenido)
        self.escena._sincronizar_raton()
        return True

    def cerrar(self):
        """Cierra sin decidir (Esc, salir del mundo, fin de la semana). El mensaje sigue pendiente."""
        if self.fase is None:
            return
        self.fase = None
        self._contenido = None
        self.vista.ocultar()
        self.escena._sincronizar_raton()

    # -- Entrada --

    def elegir(self, numero):
        """Elige la opción n.º `numero` (1-3) de las presentadas. False si no hay panel de decisión o no existe."""
        if self.fase != "decidiendo" or not self._contenido:
            return False
        opciones = self._contenido["opciones"]
        if not 1 <= numero <= len(opciones):
            return False
        flujo = self._flujo()
        resultado = None if flujo is None else flujo.responder_dilema(opciones[numero - 1]["id"])
        if resultado is None:             # la oferta ya no existe (terminó la semana, otro jugador): se cierra
            self.cerrar()
            return False
        self.ultimo_resultado = resultado
        self.fase = "resultado"
        self.vista.mostrar_resultado(dc.contenido_resultado(resultado))
        return True

    def tecla(self, key, desde_apertura_s=None):
        """Una pulsación. Devuelve True si el panel la consumió. `desde_apertura_s`: segundos desde que se abrió (guarda)."""
        if self.fase is None:
            if key == self.tecla_abrir and self.puede_abrir():
                self.abrir()
                return True
            return False
        if key == "escape" or key == self.tecla_abrir:
            self.cerrar()
            return True
        if desde_apertura_s is not None and desde_apertura_s < GUARDA_S:
            return True
        if self.fase == "decidiendo":
            numero = key.replace("numpad ", "", 1)      # teclado numérico: «numpad 1»
            if numero.isdigit():
                self.elegir(int(numero))
            return True
        if key in TECLAS_CONTINUAR or key in TECLAS_CLIC:
            self.cerrar()
        return True

    def clic(self, numero):
        if self.fase == "decidiendo":
            self.elegir(numero)
        elif self.fase == "resultado":
            self.cerrar()

    # -- Frame --

    def avanzar(self):
        """Pinta el chip de «mensaje sin responder» y cierra el panel si la partida ya no lo admite."""
        flujo = self._flujo()
        if flujo is None:
            self.vista.chip("", False)
            return
        if self.abierto() and (flujo.partida_terminada() or (self.fase == "decidiendo" and self.pendiente() is None)):
            self.cerrar()
        escena = self.escena
        visible = bool(not self.abierto() and self.pendiente() is not None and escena.enabled
                       and not escena.en_pausa and not getattr(escena, "_cinematica", False)
                       and not escena.hud.mapa_grande_abierto() and not escena.controles_bloqueados()
                       and not flujo.partida_terminada())
        self.vista.chip(dc.CHIP_PENDIENTE, visible)


def _crear_vigia(escena_mundo):
    import time

    from ursina import Entity, Text, camera, color

    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import BotonSecundario, escala_fuente, panel_tinta, rgb
    from frontend.registro_reloj import ALTO_CHIP, MARGEN

    ANCHO, ALTO = 1.30, 0.86
    ANCHO_TEXTO = ANCHO - 0.12
    MAX_OPCIONES = 3

    class PanelDilema(Entity):

        def __init__(self, control, **opciones):
            opciones.setdefault("parent", camera.ui)
            super().__init__(enabled=False, **opciones)
            self.z = -0.06
            self.fondo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 225), z=0.02)
            self.marco = panel_tinta(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL, position=(0, 0, 0))
            x0 = -ANCHO / 2 + 0.06
            self.titulo = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.045, -0.02),
                               scale=escala_fuente(26), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
            self._base_situacion = escala_fuente(19)
            self.situacion = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.125, -0.02),
                                  scale=self._base_situacion, color=rgb(estilo.COLOR_TEXTO))
            self.botones, self.pistas = [], []
            for i in range(MAX_OPCIONES):
                y = 0.04 - i * 0.2
                boton = BotonSecundario("", al_clic=lambda n=i + 1: control.clic(n), ancho=ANCHO_TEXTO, alto=0.075,
                                        tamano_fuente_px=20, parent=self.marco)
                boton.position = (0, y, -0.02)
                pista = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, y - 0.05, -0.02),
                             scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
                self.botones.append(boton)
                self.pistas.append(pista)
            self.aviso = Text("", parent=self.marco, origin=(-0.5, -0.5), position=(x0, -ALTO / 2 + 0.07, -0.02),
                              scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self.pie = Text("", parent=self.marco, origin=(0.5, -0.5), position=(ANCHO / 2 - 0.04, -ALTO / 2 + 0.03, -0.02),
                            scale=escala_fuente(14), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self.texto_resultado = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, 0.2, -0.02),
                                        scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO))
            self._t_abierta = 0.0
            diseno_adaptable.ajustar_escala(self)

        def _ajustar(self, texto, cadena, base, lineas):
            plan = diseno_adaptable.ajustar_texto(texto, ANCHO_TEXTO, escala_base=base, escala_min=0.75,
                                                  max_lineas=lineas, cadena=cadena)
            if plan is None:
                texto.text = cadena
            return plan

        def mostrar_dilema(self, contenido):
            self.enabled = True
            self._t_abierta = time.monotonic()
            self.titulo.text = contenido["titulo"]
            self.plan_situacion = self._ajustar(self.situacion, contenido["situacion"], self._base_situacion, 6) or {}
            self.situacion.enabled = True
            self.texto_resultado.enabled = False
            for i in range(MAX_OPCIONES):
                hay = i < len(contenido["opciones"])
                self.botones[i].enabled = hay
                self.pistas[i].enabled = hay
                if hay:
                    opcion = contenido["opciones"][i]
                    self.botones[i].text = f"{opcion['tecla']}   {opcion['etiqueta']}"
                    self._ajustar(self.pistas[i], opcion["pista"], escala_fuente(15), 2)
            self.aviso.text = contenido["aviso"]
            self.aviso.enabled = True
            self.pie.text = contenido["pie"]

        def mostrar_resultado(self, contenido):
            self.titulo.text = contenido["titulo"]
            self.situacion.enabled = False
            for i in range(MAX_OPCIONES):
                self.botones[i].enabled = False
                self.pistas[i].enabled = False
            self.aviso.enabled = False
            self.texto_resultado.enabled = True
            self.plan_resultado = self._ajustar(self.texto_resultado, contenido["texto"], escala_fuente(22), 4) or {}
            self.pie.text = contenido["pie"]
            self._t_abierta = time.monotonic()

        def ocultar(self):
            self.enabled = False

        def segundos_abierto(self):
            return time.monotonic() - self._t_abierta

    class VistaDilema:

        def __init__(self, control):
            self.panel = PanelDilema(control)
            self.chip_entidad = Entity(parent=escena_mundo.hud, enabled=False)
            ancho = 0.34
            self.chip_entidad.fondo = panel_tinta(self.chip_entidad, ancho, ALTO_CHIP, tono=estilo.COLOR_FONDO,
                                                  radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            self.chip_texto = Text("", parent=self.chip_entidad, origin=(0, 0), position=(0, 0.004, -0.01),
                                   scale=escala_fuente(13), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
            apilar = 0.0 if getattr(escena_mundo, "economia", None) is None else ALTO_CHIP + 0.012
            # Sobre el chip del reloj (que va sobre el del dinero).
            self.chip_entidad.position = (-diseno_adaptable.aspecto() / 2 + MARGEN + ancho / 2,
                                          -0.5 + MARGEN + ALTO_CHIP / 2 + apilar + ALTO_CHIP + 0.012)
            diseno_adaptable.anclar(self.chip_entidad, "izquierda")

        def mostrar_dilema(self, contenido):
            self.panel.mostrar_dilema(contenido)

        def mostrar_resultado(self, contenido):
            self.panel.mostrar_resultado(contenido)

        def ocultar(self):
            self.panel.ocultar()

        def chip(self, texto, visible):
            self.chip_entidad.enabled = bool(visible)
            if visible and self.chip_texto.text != texto:
                self.chip_texto.text = texto

    class VigiaDilemas(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.control = ControlDilemas(escena_mundo, None)
            self.vista = VistaDilema(self.control)
            self.control.vista = self.vista

        def input(self, key):
            if key == "escape":         # lo cierra EscenaMundo (registrar_bloqueador): si lo cerráramos aquí, abriría la pausa
                return
            if self.control.abierto() or key == self.control.tecla_abrir:
                self.control.tecla(key, self.vista.panel.segundos_abierto() if self.control.abierto() else None)

        def update(self):
            self.control.avanzar()

    return VigiaDilemas(parent=escena_mundo.hud)


def registrar(gestor, conexion, escena_mundo):
    if not logica.activo():
        return None
    try:
        vigia = _crear_vigia(escena_mundo)
        control = vigia.control
        escena_mundo.registrar_bloqueador(control.abierto, control.cerrar)
        # El inventario (I) no mira controles_bloqueados: no se le deja abrirse encima del panel.
        economia = getattr(escena_mundo, "economia", None)
        if economia is not None:
            puede_abrir_original = economia.puede_abrir
            economia.puede_abrir = lambda: puede_abrir_original() and not control.abierto()
        conexion.dilemas_ui = control
        return vigia
    except Exception as error:
        print(f"[dilemas] no instalado ({type(error).__name__}: {error})", file=sys.stderr)
        return None

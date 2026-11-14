# Bandeja de Civitas en el juego real (estafas, publicar y tiempo de pantalla: backend/logica/habitos_digitales.py).
# frontend/extensiones.py llama a registrar(); main.py solo envuelve el flujo (habitos_digitales.envolver).
#
#   ENTRADA. Cuando llega un mensaje, el teléfono avisa («Civitas: ¡Ganaste el sorteo del barrio! Pulsa L…») y aparece un chip
#   «L · Civitas: mensaje nuevo» sobre el reloj. Nada se abre solo: el jugador pulsa L cuando quiere. Sin mensajes, L abre el
#   FEED (si ALCALDE_TIEMPO_PANTALLA no lo apagó): Espacio desliza y cada publicación cuesta minutos de la semana.
#   PANEL. Modal como el de dilemas (un «bloqueador» de EscenaMundo: el reloj no corre, el jugador no se mueve, Esc lo cierra).
#   Fases: MARCAR (1-n o clic marcan / desmarcan cada elemento; Intro sigue) -> DECIDIR (1-3 o clic; Retroceso vuelve) ->
#   REVISIÓN (lo que pasó y, por cada elemento, si lo juzgaste bien y por qué). Esc antes de decidir no decide: el mensaje
#   sigue en la bandeja hasta su plazo.
#   EN LÍNEA o sin flujo con hábitos: no hace nada y L queda libre.
#
# La lógica va en ControlHabitos (sin ursina; se prueba con escenas falsas, tests/test_habitos_digitales.py).
# API: conexion.habitos_ui = ControlHabitos.

import sys

from backend.logica import habitos_digitales as logica
from frontend import habitos_calculos as hc
from frontend import teclas

TECLAS_CLIC = ("left mouse down",)
TECLAS_CONTINUAR = ("e", "enter", "space")
TECLAS_SIGUIENTE = ("space", "down arrow", "s")
GUARDA_S = 0.25                       # la pulsación que abrió el panel no puede cerrarlo ni elegir


class ControlHabitos:
    """Estado del panel sin ursina. `escena`: lo que usa de EscenaMundo (flujo, online, en_pausa, _cinematica, hud,
    controles_bloqueados(), _sincronizar_raton()). `vista`: pinta (mostrar(contenido), ocultar(), chip(texto, visible))."""

    def __init__(self, escena, vista, tecla=teclas.TECLA_HABITOS):
        self.escena, self.vista, self.tecla_abrir = escena, vista, tecla
        self.fase = None                  # None | "marcar" | "decidir" | "revision" | "feed"
        self._evento = None
        self.marcas = set()
        self.ultimo_resultado = None

    # -- Consulta --

    def abierto(self):
        return self.fase is not None

    def _flujo(self):
        flujo = self.escena.flujo
        if flujo is None or getattr(self.escena, "online", None) is not None or not callable(getattr(flujo, "evento_pendiente", None)):
            return None
        return flujo

    def pendiente(self):
        flujo = self._flujo()
        return None if flujo is None else flujo.evento_pendiente()

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
        return self.pendiente() is not None or logica.tiempo_pantalla_activo()

    # -- Abrir / cerrar --

    def abrir(self):
        evento = self.pendiente()
        if evento is not None:
            self._evento = evento
            self.marcas = set()
            self.fase = "marcar"
            self.vista.mostrar(hc.contenido_marcar(evento, self.marcas))
        elif logica.tiempo_pantalla_activo():
            self.fase = "feed"
            self.vista.mostrar(hc.contenido_feed(None, self._flujo().tiempo_pantalla_hoy()))
        else:
            return False
        self.escena._sincronizar_raton()
        return True

    def cerrar(self):
        """Cierra (Esc, salir del mundo, fin de la semana). Sin haber decidido, el mensaje sigue pendiente."""
        if self.fase is None:
            return
        self.fase = None
        self._evento = None
        self.marcas = set()
        self.vista.ocultar()
        self.escena._sincronizar_raton()

    # -- Entrada --

    def marcar(self, numero):
        if self.fase != "marcar" or not self._evento:
            return False
        elementos = self._evento["elementos"][:hc.MAX_ELEMENTOS]
        if not 1 <= numero <= len(elementos):
            return False
        ident = elementos[numero - 1]["id"]
        self.marcas.symmetric_difference_update({ident})
        self.vista.mostrar(hc.contenido_marcar(self._evento, self.marcas))
        return True

    def pasar_a_decidir(self):
        if self.fase != "marcar":
            return False
        self.fase = "decidir"
        self.vista.mostrar(hc.contenido_decidir(self._evento, self.marcas))
        return True

    def volver_a_marcar(self):
        if self.fase != "decidir":
            return False
        self.fase = "marcar"
        self.vista.mostrar(hc.contenido_marcar(self._evento, self.marcas))
        return True

    def elegir(self, numero):
        if self.fase != "decidir" or not self._evento:
            return False
        opciones = self._evento["opciones"]
        if not 1 <= numero <= len(opciones):
            return False
        flujo = self._flujo()
        resultado = None if flujo is None else flujo.responder_evento(sorted(self.marcas), opciones[numero - 1]["id"])
        if resultado is None:             # el mensaje ya venció o terminó la semana: se cierra
            self.cerrar()
            return False
        self.ultimo_resultado = resultado
        self.fase = "revision"
        self.vista.mostrar(hc.contenido_revision(resultado))
        return True

    def deslizar(self):
        if self.fase != "feed":
            return False
        flujo = self._flujo()
        publicacion = None if flujo is None else flujo.deslizar_feed()
        if publicacion is None:
            self.cerrar()
            return False
        self.vista.mostrar(hc.contenido_feed(publicacion))
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
        numero = key.replace("numpad ", "", 1)      # teclado numérico: «numpad 1»
        if self.fase == "marcar":
            if numero.isdigit():
                self.marcar(int(numero))
            elif key == "enter":
                self.pasar_a_decidir()
        elif self.fase == "decidir":
            if numero.isdigit():
                self.elegir(int(numero))
            elif key == "backspace":
                self.volver_a_marcar()
        elif self.fase == "feed":
            if key in TECLAS_SIGUIENTE:
                self.deslizar()
        elif key in TECLAS_CONTINUAR or key in TECLAS_CLIC:
            self.cerrar()
        return True

    def clic(self, numero):
        if self.fase == "marcar":
            self.marcar(numero)
        elif self.fase == "decidir":
            self.elegir(numero)
        elif self.fase == "revision":
            self.cerrar()
        elif self.fase == "feed":
            self.deslizar()

    # -- Frame --

    def avanzar(self):
        """Pinta el chip de «mensaje nuevo» y cierra el panel si el mensaje venció o la semana terminó."""
        flujo = self._flujo()
        if flujo is None:
            self.vista.chip("", False)
            return
        if self.abierto() and (flujo.partida_terminada()
                               or (self.fase in ("marcar", "decidir") and self.pendiente() is None)):
            self.cerrar()
        escena = self.escena
        visible = bool(not self.abierto() and self.pendiente() is not None and escena.enabled
                       and not escena.en_pausa and not getattr(escena, "_cinematica", False)
                       and not escena.hud.mapa_grande_abierto() and not escena.controles_bloqueados()
                       and not flujo.partida_terminada())
        self.vista.chip(hc.CHIP_PENDIENTE, visible)


def _crear_vigia(escena_mundo):
    import time

    from ursina import Entity, Text, camera, color

    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import BotonSecundario, escala_fuente, panel_tinta, rgb
    from frontend.registro_reloj import ALTO_CHIP, MARGEN

    ANCHO, ALTO = 1.30, 0.86
    ANCHO_TEXTO = ANCHO - 0.12
    MAX_OPCIONES = 3
    Y_FILAS, PASO_FILA, ALTO_FILA = 0.075, 0.066, 0.056

    class PanelHabitos(Entity):

        def __init__(self, control, **opciones):
            opciones.setdefault("parent", camera.ui)
            super().__init__(enabled=False, **opciones)
            self.z = -0.06
            self.fondo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 225), z=0.02)
            self.marco = panel_tinta(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL, position=(0, 0, 0))
            x0 = -ANCHO / 2 + 0.06
            self.titulo = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.045, -0.02),
                               scale=escala_fuente(26), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
            self.remitente = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.105, -0.02),
                                  scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self._base_texto = escala_fuente(19)
            self.texto = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.145, -0.02),
                              scale=self._base_texto, color=rgb(estilo.COLOR_TEXTO))
            self.instruccion = Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, 0.135, -0.02),
                                    scale=escala_fuente(17), color=rgb(estilo.COLOR_ACENTO))
            # Filas: en MARCAR son botones que se alternan; en DECIDIR, las opciones. En REVISIÓN, líneas de texto.
            self.filas = []
            for i in range(hc.MAX_ELEMENTOS):
                # con texto vacío Ursina no crea text_entity: se arranca con un espacio para poder alinearlo a la izquierda
                boton = BotonSecundario(" ", al_clic=lambda n=i + 1: control.clic(n), ancho=ANCHO_TEXTO, alto=ALTO_FILA,
                                        tamano_fuente_px=17, parent=self.marco)
                boton.position = (0, Y_FILAS - i * PASO_FILA, -0.02)
                boton.text_entity.origin = (-0.5, 0)
                boton.text_entity.x = -0.47
                self.filas.append(boton)
            self.lineas = [Text("", parent=self.marco, origin=(-0.5, 0.5), position=(x0, Y_FILAS + 0.025 - i * PASO_FILA, -0.02),
                                scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO)) for i in range(hc.MAX_ELEMENTOS)]
            self.aviso = Text("", parent=self.marco, origin=(-0.5, -0.5), position=(x0, -ALTO / 2 + 0.07, -0.02),
                              scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self.pie = Text("", parent=self.marco, origin=(0.5, -0.5), position=(ANCHO / 2 - 0.04, -ALTO / 2 + 0.03, -0.02),
                            scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self._t_abierta = 0.0
            diseno_adaptable.ajustar_escala(self)

        def _ajustar(self, texto, cadena, base, lineas, ancho=ANCHO_TEXTO):
            plan = diseno_adaptable.ajustar_texto(texto, ancho, escala_base=base, escala_min=0.75,
                                                  max_lineas=lineas, cadena=cadena)
            if plan is None:
                texto.text = cadena
            return plan

        def mostrar(self, contenido):
            if not self.enabled:
                self._t_abierta = time.monotonic()
            self.enabled = True
            fase = contenido["fase"]
            self.titulo.text = contenido["titulo"]
            self.remitente.text = contenido.get("remitente", contenido.get("contador", ""))
            # en el feed la publicación es lo único que hay: letra más grande
            base = escala_fuente(24) if fase == "feed" else self._base_texto
            self._ajustar(self.texto, contenido["texto"] or " ", base, 4 if fase != "feed" else 6)
            self._ajustar(self.instruccion, contenido.get("instruccion") or contenido.get("resumen") or " ",
                          escala_fuente(17), 1)
            self.instruccion.enabled = fase != "feed"
            if fase == "marcar":
                botones = [(f["texto"], f["marcado"]) for f in contenido["filas"]]
            elif fase == "decidir":
                botones = [(o["texto"], False) for o in contenido["opciones"]]
            else:
                botones = []
            for i, boton in enumerate(self.filas):
                hay = i < len(botones)
                boton.enabled = hay
                if hay:
                    boton.text = botones[i][0]
                    # marcado: letra de acento ADEMÁS de «[x]» (nunca solo color; el fondo no cambia y el contraste se mantiene)
                    tono = rgb(estilo.ACENTO_PRIMARIO if botones[i][1] else estilo.COLOR_BOTON_TEXTO)
                    boton.text_color = tono
                    boton.highlight_text_color = tono
            filas_texto = contenido.get("filas", []) if fase == "revision" else []
            for i, linea in enumerate(self.lineas):
                hay = i < len(filas_texto)
                linea.enabled = hay
                if hay:
                    tono = estilo.ESTADO_EXITO if filas_texto[i]["acertado"] else estilo.ESTADO_AVISO
                    linea.color = rgb(tono)
                    # se parte en dos líneas antes que encoger: la explicación es lo que se aprende
                    plan = diseno_adaptable.ajustar_texto(linea, ANCHO_TEXTO, escala_base=escala_fuente(15), escala_min=0.95,
                                                          max_lineas=2, cadena=filas_texto[i]["texto"])
                    if plan is None:
                        linea.text = filas_texto[i]["texto"]
            self.aviso.text = contenido.get("aviso") or contenido.get("hasta") or ""
            self._ajustar(self.pie, contenido["pie"], escala_fuente(16), 1, ANCHO - 0.08)

        def ocultar(self):
            self.enabled = False

        def segundos_abierto(self):
            return time.monotonic() - self._t_abierta

    class VistaHabitos:

        def __init__(self, control):
            self.panel = PanelHabitos(control)
            self.chip_entidad = Entity(parent=escena_mundo.hud, enabled=False)
            ancho = 0.40
            self.chip_entidad.fondo = panel_tinta(self.chip_entidad, ancho, ALTO_CHIP, tono=estilo.COLOR_FONDO,
                                                  radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            self.chip_texto = Text("", parent=self.chip_entidad, origin=(0, 0), position=(0, 0.004, -0.01),
                                   scale=escala_fuente(13), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
            apilar = 0.0 if getattr(escena_mundo, "economia", None) is None else ALTO_CHIP + 0.012
            # Sobre el chip de dilemas (que va sobre el del reloj y el del dinero).
            self.chip_entidad.position = (-diseno_adaptable.aspecto() / 2 + MARGEN + ancho / 2,
                                          -0.5 + MARGEN + ALTO_CHIP / 2 + apilar + 2 * (ALTO_CHIP + 0.012))
            diseno_adaptable.anclar(self.chip_entidad, "izquierda")

        def mostrar(self, contenido):
            self.panel.mostrar(contenido)

        def ocultar(self):
            self.panel.ocultar()

        def chip(self, texto, visible):
            self.chip_entidad.enabled = bool(visible)
            if visible and self.chip_texto.text != texto:
                self.chip_texto.text = texto

    class VigiaHabitos(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.control = ControlHabitos(escena_mundo, None)
            self.vista = VistaHabitos(self.control)
            self.control.vista = self.vista

        def input(self, key):
            if key == "escape":         # lo cierra EscenaMundo (registrar_bloqueador): si lo cerráramos aquí, abriría la pausa
                return
            if self.control.abierto() or key == self.control.tecla_abrir:
                self.control.tecla(key, self.vista.panel.segundos_abierto() if self.control.abierto() else None)

        def update(self):
            self.control.avanzar()

    return VigiaHabitos(parent=escena_mundo.hud)


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
        conexion.habitos_ui = control
        return vigia
    except Exception as error:
        print(f"[habitos] no instalado ({type(error).__name__}: {error})", file=sys.stderr)
        return None

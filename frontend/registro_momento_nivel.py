# Momento de cambio de nivel (M1 del plan ambiente y pulseras; ALCALDE_MOMENTO_NIVEL=0 lo apaga). frontend/extensiones.py
# llama a registrar(). Un controlador cuelga de la EscenaMundo (solo corre con el mundo a la vista) y, una vez por frame,
# mira si frontend/ambiente_vivo.py registró un cruce de nivel (ultimo_evento). Si lo hay:
#   - titular de 2,5 s arriba al centro, bajo la franja «Confianza de Ciudad Nova» (texto de backend/datos/titulares_nivel.json);
#   - stinger corto (nivel_sube / nivel_baja, sintetizados) por debajo de la música.
# La aceleración de la atmósfera (M1.3) ya la hace ambiente_vivo al detectar el cruce. Cálculos en momento_nivel_calculos.
import sys

from frontend import ambiente_vivo


def activo():
    activo_vivo = getattr(ambiente_vivo, "momento_activo", None)
    return bool(activo_vivo and activo_vivo())


def _crear_controlador(escena_mundo):
    from panda3d.core import TransparencyAttrib
    from ursina import Entity, Text, time

    from backend.logica import momento_nivel
    from frontend import diseno_adaptable, estilo, tipografia
    from frontend import momento_nivel_calculos as mn
    from frontend.componentes import escala_fuente, panel_tinta, rgb

    textos = momento_nivel.cargar_titulares()

    class ControladorMomentoNivel(Entity):

        def __init__(self, escena):
            super().__init__(parent=escena)
            self.escena = escena
            self._visto, _ = ambiente_vivo.ultimo_evento()
            self._t = None
            self.titular = None

        def _construir(self):
            padre = getattr(self.escena, "hud", None) or self.escena
            r = mn.rect_titular(round(diseno_adaptable.aspecto() * 720), 720)
            caja = Entity(parent=padre, position=(0, r.centro[1], -0.05))
            caja.fondo = panel_tinta(caja, mn.ANCHO_TITULAR, mn.ALTO_TITULAR, tono=estilo.COLOR_FONDO,
                                     radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            caja.franja = Entity(parent=caja, model="quad", scale=(0.012, mn.ALTO_TITULAR - 0.014),
                                 position=(-mn.ANCHO_TITULAR / 2 + 0.016, 0, -0.01))
            caja.texto = Text("", parent=caja, origin=(0, 0), position=(0.012, 0.002, -0.01),
                              scale=escala_fuente(mn.PX_TITULAR), color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
            caja.setTransparency(TransparencyAttrib.MAlpha)
            caja.enabled = False
            self.titular = caja

        def _mostrar(self, evento):
            texto = momento_nivel.titular(evento.desde, evento.hacia, textos)
            if texto:
                if self.titular is None:
                    self._construir()
                self.titular.texto.text = texto
                self.titular.franja.color = rgb(mn.color_nivel(evento.hacia))
                self.titular.enabled = True
                self.titular.setColorScale(1, 1, 1, 0)
                self._t = 0.0
            nombre = mn.stinger_de(evento.direccion)
            if nombre:
                try:
                    from frontend import audio as audio_modulo
                    audio_modulo.obtener().efecto(nombre, volumen=mn.VOLUMEN_STINGER)
                except Exception as error:      # el audio nunca tira el juego
                    print(f"[momento_nivel] sin stinger ({type(error).__name__}: {error})", file=sys.stderr)

        def update(self):
            contador, evento = ambiente_vivo.ultimo_evento()
            if contador != self._visto:
                self._visto = contador
                if evento is not None:
                    self._mostrar(evento)
            if self._t is not None and self.titular is not None:
                self._t += time.dt
                alfa = mn.alfa_titular(self._t)
                self.titular.setColorScale(1, 1, 1, alfa)
                if self._t >= mn.DURACION_TITULAR:
                    self._t = None
                    self.titular.enabled = False

    return ControladorMomentoNivel(escena_mundo)


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    try:
        controlador = _crear_controlador(escena_mundo)
        conexion.momento_nivel = controlador
        return controlador
    except Exception as error:
        print(f"[momento_nivel] no instalado ({type(error).__name__}: {error}); el juego sigue como antes", file=sys.stderr)
        return None

# Reloj de 7 días en el juego real (punto 1 del plan final). frontend/extensiones.py llama a registrar(); no se edita main.py.
# Un vigía cuelga del HUD del mundo (solo corre con el mundo a la vista) y, en cada frame:
#
#   1. CHIP «Día N · hh:mm» (sol / luna + barra fina de la semana) abajo a la izquierda, encima del chip de dinero.
#      Oculto con el mapa grande, un panel modal (inventario, tienda, diálogos, Archivo de casos), la pausa o la partida
#      terminada.
#   2. ENGANCHE: llama a flujo.avanzar_tiempo(dt) UNA vez por frame, solo cuando reloj_calculos.motivo_de_pausa dice que
#      el tiempo corre (regla única, documentada allí y en docs/PLAN_FINAL.md §9). Sin reloj (ALCALDE_RELOJ=0), en línea o con
#      ALCALDE_RELOJ_HUD=0 no hace nada. Interiores, minijuego, trabajo, mundo digital, parkour y ajustes son OTRAS
#      escenas: el HUD del mundo está apagado, este vigía no corre y no gastan semana.
#   3. AVISOS: «Último día» y «Quedan 2 horas» (AvisosFin) y los avisos de causa-efecto de los efectos retardados
#      (flujo.vaciar_avisos_retardados -> texto_efecto), de uno en uno en un AvisoGenerico propio (ColaAvisosCausa).
#   4. FIN: al terminar el día 7 cierra en orden lo que quedara abierto (vehículo, paneles, mapa, teléfono), refresca la
#      escena EN ESE MISMO FRAME y pinta PanelFinalSemana (escena_mundo.pintar_final). No se guarda tras terminar
#      (guardado.se_puede_guardar ya lo impide; registro_guardado borra el guardado).
#
# Partida nueva: crear_flujo da un FlujoConTiempo con reloj nuevo (día 1, 08:00). «Continuar»: guardado.restaurar vuelve a
# poner día, hora y cola de efectos; el vigía reconoce el flujo (o el reloj) nuevo y reinicia avisos y colas.

import os
import sys

from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from frontend import reloj_calculos as rc

RELOJ_HUD = True                # False (o ALCALDE_RELOJ_HUD=0): ni chip ni enganche; el reloj queda parado en el día 1
Y_AVISO = 0.12                  # borde inferior (centro de una línea) del aviso en camera.ui; el de veredicto/pagos está en 0,30
ANCHO_CHIP, ALTO_CHIP = 0.27, 0.052
MARGEN = 0.02


def activo():
    valor = os.environ.get("ALCALDE_RELOJ_HUD", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(RELOJ_HUD)


class ControlReloj:
    """Lógica del vigía sin ursina (se prueba con escenas falsas). `escena`: lo que usa de EscenaMundo (flujo, online,
    en_pausa, _cinematica, hud, economia, _bloqueado_por_paneles(), vehiculos, refrescar(), _sincronizar_raton()).
    `vista`: pinta (chip(texto, icono, fraccion, visible), aviso(texto|None), avanzar_aviso(dt), final_oculto()).
    `conexion`: opcional, solo para saber si hay un fundido en curso."""

    def __init__(self, escena, vista, conexion=None):
        self.escena, self.vista, self.conexion = escena, vista, conexion
        # Con las notificaciones del teléfono (ALCALDE_NOTIF_TELEFONO) los avisos de «último día», causa-efecto y cambio de
        # etapa salen por el teléfono del jugador activo: la cola no deja nada que pintar en el centro.
        from frontend import notificaciones
        self.cola = notificaciones.ColaAlTelefono(escena) if notificaciones.activo() else rc.ColaAvisosCausa()
        self.fin = rc.AvisosFin()
        self.motivo = rc.SIN_RELOJ
        self.cierres = 0
        self._clave = None
        self._terminada_vista = False

    # -- Estado de la escena --

    def _con_reloj(self, flujo):
        return flujo is not None and getattr(flujo, "reloj", None) is not None and callable(getattr(flujo, "avanzar_tiempo", None))

    def _panel_abierto(self):
        escena = self.escena
        economia = getattr(escena, "economia", None)
        return bool(escena._bloqueado_por_paneles() or (economia is not None and economia.bloquea_controles()))

    def _mapa_abierto(self):
        hud = self.escena.hud
        return bool(hud.mapa_grande_abierto())

    def _telefono_abierto(self, flujo):
        try:
            return bool(flujo.jugador_activo().telefono.bloquea_movimiento())
        except (AttributeError, TypeError):
            return False

    def _transicion(self):
        en_curso = getattr(self.conexion, "_transicion_en_curso", None)
        return bool(en_curso()) if callable(en_curso) else False

    def motivo_de_pausa(self, flujo):
        escena = self.escena
        return rc.motivo_de_pausa(
            con_reloj=self._con_reloj(flujo), en_linea=getattr(escena, "online", None) is not None,
            terminada=bool(flujo is not None and flujo.partida_terminada()), en_pausa=bool(escena.en_pausa),
            cinematica=bool(escena._cinematica), mapa_abierto=self._mapa_abierto(), panel_abierto=self._panel_abierto(),
            telefono_abierto=self._telefono_abierto(flujo) if flujo is not None else False,
            mision_ocupada=bool(flujo is not None and flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA)),
            transicion=self._transicion())

    # -- Frame --

    def avanzar(self, dt):
        """Un frame con el mundo activo. Devuelve el motivo por el que el tiempo no corrió (None = corrió)."""
        flujo = self.escena.flujo
        if not self._con_reloj(flujo) or getattr(self.escena, "online", None) is not None:
            self._clave = None
            self.motivo = rc.SIN_RELOJ if not self._con_reloj(flujo) else rc.EN_LINEA
            self.vista.chip("", "sol", 0.0, False)
            self.vista.aviso(None)
            return self.motivo
        clave = (id(flujo), id(flujo.reloj))
        if clave != self._clave:
            self._nuevo_flujo(flujo, clave)
        reloj = flujo.reloj
        self.motivo = self.motivo_de_pausa(flujo)
        if self.motivo is None:
            flujo.avanzar_tiempo(dt)
            for texto in self.fin.revisar(reloj.horas_restantes()):
                self.cola.agregar(texto)
        for aviso in flujo.vaciar_avisos_retardados():
            self.cola.agregar(rc.texto_efecto(aviso))
        if flujo.partida_terminada():
            self._al_terminar(flujo)
        else:
            self._terminada_vista = False
            self.vista.final_oculto()
        self._pintar(flujo, dt)
        return self.motivo

    def _nuevo_flujo(self, flujo, clave):
        """Otra partida (o «Continuar»): nada de la anterior se arrastra y los umbrales ya pasados no se repiten."""
        self._clave = clave
        self.cola.vaciar()
        self.fin.reiniciar(flujo.reloj.horas_restantes())
        flujo.vaciar_avisos_retardados()
        self._terminada_vista = False

    def _al_terminar(self, flujo):
        if self._terminada_vista:
            return
        self._terminada_vista = True
        self.cola.vaciar()
        self.cerrar_todo()
        self.escena.refrescar()                    # mismo frame: panel de turno, baliza y pantalla final

    def cerrar_todo(self):
        """Cierre ordenado al terminar la semana: vehículo, paneles modales, mapa grande, bloqueadores y teléfono."""
        escena = self.escena
        self.cierres += 1
        vehiculos = getattr(escena, "vehiculos", None)
        if vehiculos is not None:
            vehiculos.bajar()
        economia = getattr(escena, "economia", None)
        if economia is not None:
            economia.cerrar_paneles()
        escena.hud.cerrar_mapa_grande()
        escena._cerrar_bloqueadores()
        flujo = escena.flujo
        try:
            telefono = flujo.jugador_activo().telefono
            if telefono.bloquea_movimiento():
                telefono.cerrar()
        except (AttributeError, TypeError):
            pass
        escena._sincronizar_raton()

    def _pintar(self, flujo, dt):
        reloj = flujo.reloj
        oculto = (flujo.partida_terminada() or self.motivo in (rc.PAUSA, rc.MAPA, rc.PANEL))
        if oculto and self.motivo == rc.PANEL and not flujo.partida_terminada():
            from frontend import registro_tutorial      # el tutorial señala el chip: se queda a la vista
            oculto = not registro_tutorial.senalando_hud()
        self.vista.chip(rc.texto_chip(reloj), rc.icono_de(reloj.hora()), rc.fraccion_semana(reloj), not oculto)
        if oculto or getattr(self.escena, "_cinematica", False):
            if oculto:
                self.vista.aviso(None)
            return                                  # que termine la cinemática; el aviso espera
        self.vista.aviso(self.cola.avanzar(dt))
        self.vista.avanzar_aviso(dt)


# Cinemática del final (finales por etapas, frontend/cinematica_final.py): se muestra UNA vez por partida, antes de la
# pantalla final, si el final es bueno o malo. «sesion» identifica la partida: otra sesión (Partida nueva) reinicia la marca.
SEGUNDOS_VINETA_FINAL = None    # None = lo que diga cinematica_final (≈ 4 s); los scripts de humo lo bajan
_cine_final = {"sesion": None, "vista": False, "entidad": None}


def _cinematica_del_final(escena_mundo, panel, resumen):
    """True mientras la cinemática del final esté en pantalla (el panel final espera). Nunca lanza: si algo falla, se
    marca como vista y sale el panel de siempre."""
    try:
        from backend.logica import etapas_final
        if not etapas_final.activo():
            return False
        sesion = escena_mundo._sesion
        if _cine_final["sesion"] is not sesion:
            _cine_final.update(sesion=sesion, vista=False, entidad=None)
        if _cine_final["vista"] or resumen.get("final") not in ("bueno", "malo") or not escena_mundo.flujo.partida_terminada():
            return False
        if _cine_final["entidad"] is None:
            from frontend.cinematica_final import crear_cinematica

            def al_terminar():
                _cine_final["vista"] = True
                _cine_final["entidad"] = None
                escena_mundo.refrescar()               # ahora sí: la pantalla final de siempre

            def guardia():                             # Escape salta la cinemática: que no deje la pausa abierta debajo
                if getattr(escena_mundo, "en_pausa", False):
                    escena_mundo.alternar_pausa(False)

            opciones = {} if SEGUNDOS_VINETA_FINAL is None else {"segundos": SEGUNDOS_VINETA_FINAL}
            _cine_final["entidad"] = crear_cinematica(resumen["final"], al_terminar, guardia=guardia, parent=escena_mundo.hud,
                                                      **opciones)
        panel.ocultar()
        return True
    except Exception as error:
        _cine_final["vista"] = True
        _cine_final["entidad"] = None
        print(f"[reloj] cinemática del final omitida ({type(error).__name__}: {error})", file=sys.stderr)
        return False


def pintar_final_de(escena_mundo, panel):
    """Gancho de EscenaMundo.refrescar (pintar_final): pinta la pantalla final de la semana si el flujo tiene reloj.
    Devuelve True si pintó (la escena no usa entonces sus paneles de siempre)."""
    flujo = escena_mundo.flujo
    if flujo is None or getattr(flujo, "reloj", None) is None or not callable(getattr(flujo, "resumen_final", None)):
        return False
    resumen = flujo.resumen_final()
    if _cinematica_del_final(escena_mundo, panel, resumen):
        return True
    indicadores = escena_mundo._sesion.estado_partida.indicadores() if escena_mundo._sesion is not None else None
    # Sin nivel del ambiente: el Ambiente suavizado va con retraso (τ = 30 s) y al saltar al final podía decir «sana»
    # junto a un final malo. El final ya dice cómo quedó la ciudad.
    panel.mostrar(rc.contenido_final_semana(resumen, indicadores))
    return True


def _crear_vigia(escena_mundo, conexion):
    from ursina import Entity, Text, time

    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import escala_fuente, panel_tinta, rgb
    from frontend.hud import AvisoGenerico
    from frontend.panel_final_semana import PanelFinalSemana

    class AvisoCausa(AvisoGenerico):
        """Las frases de causa-efecto son largas (hasta ~180 caracteres con los cambios): más ancho y hasta 4 líneas."""
        ANCHO_MAX = 0.90
        MAX_LINEAS = 4
        PX = 20

    class VistaReloj:
        """Pinta el chip, el aviso y (aparte) la pantalla final."""

        def __init__(self, escena):
            self.chip_entidad = Entity(parent=escena.hud)
            self.chip_entidad.fondo = panel_tinta(self.chip_entidad, ANCHO_CHIP, ALTO_CHIP, tono=estilo.COLOR_FONDO,
                                                  radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            self.texto = Text("", parent=self.chip_entidad, origin=(0, 0), position=(0.02, 0.004, -0.01),
                              scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
            x_icono = -ANCHO_CHIP / 2 + 0.032
            self.disco = Entity(parent=self.chip_entidad, model="circle", scale=0.026, position=(x_icono, 0.004, -0.01),
                                color=rgb(estilo.ESTADO_AVISO))
            self.mordida = Entity(parent=self.chip_entidad, model="circle", scale=0.021, position=(x_icono + 0.0085, 0.0085, -0.011),
                                  color=rgb(estilo.COLOR_FONDO), enabled=False)
            self.ancho_barra = ANCHO_CHIP - 0.06
            self.barra_fondo = Entity(parent=self.chip_entidad, model="quad", scale=(self.ancho_barra, 0.006),
                                      position=(0, -ALTO_CHIP / 2 + 0.011, -0.01), color=rgb(estilo.COLOR_BARRA_FONDO))
            self.barra = Entity(parent=self.chip_entidad, model="quad", origin=(-0.5, 0), scale=(0.0001, 0.006),
                                position=(-self.ancho_barra / 2, -ALTO_CHIP / 2 + 0.011, -0.011),
                                color=rgb(estilo.ACENTO_SECUNDARIO))
            apilar = 0.0 if getattr(escena, "economia", None) is None else ALTO_CHIP + 0.012     # sobre el chip de dinero
            self.chip_entidad.position = (-diseno_adaptable.aspecto() / 2 + MARGEN + ANCHO_CHIP / 2,
                                          -0.5 + MARGEN + ALTO_CHIP / 2 + apilar)
            diseno_adaptable.anclar(self.chip_entidad, "izquierda")
            self.chip_entidad.enabled = False
            self.aviso_entidad = AvisoCausa(parent=escena.hud)
            self.aviso_entidad.y_base = Y_AVISO
            self.panel_final = PanelFinalSemana(escena._ir_al_menu, parent=escena.hud)
            self._icono = None
            self._texto_aviso = None

        def chip(self, texto, icono, fraccion, visible):
            self.chip_entidad.enabled = bool(visible)
            if not visible:
                return
            if self.texto.text != texto:
                self.texto.text = texto
            if icono != self._icono:
                self._icono = icono
                luna = icono == "luna"
                self.disco.color = rgb((205, 215, 235) if luna else estilo.ESTADO_AVISO)
                self.mordida.enabled = luna
            self.barra.scale_x = max(0.0001, self.ancho_barra * fraccion)

        def aviso(self, texto):
            if texto is None:
                if self._texto_aviso is not None:
                    self._texto_aviso = None
                    self.aviso_entidad.ocultar()
            elif texto != self._texto_aviso:
                self._texto_aviso = texto
                self.aviso_entidad.mostrar(texto)

        def avanzar_aviso(self, dt):
            self.aviso_entidad.avanzar(dt)

        def final_oculto(self):
            if self.panel_final.enabled:
                self.panel_final.ocultar()

    class VigiaReloj(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.vista = VistaReloj(escena_mundo)
            self.control = ControlReloj(escena_mundo, self.vista, conexion)

        def update(self):
            self.control.avanzar(time.dt)

    return VigiaReloj(parent=escena_mundo.hud)


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    try:
        vigia = _crear_vigia(escena_mundo, conexion)
        conexion.vigia_reloj = vigia
        escena_mundo.pintar_final = lambda flujo: pintar_final_de(escena_mundo, vigia.vista.panel_final)
        return vigia
    except Exception as error:
        print(f"[reloj] no instalado ({type(error).__name__}: {error})", file=sys.stderr)
        return None

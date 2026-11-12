# Escena de los minijuegos de verificar (Ursina). Se abre en el MISMO punto donde hoy se abre la escena de juego
# (frontend/conexion_flujo.py) y recibe los mismos datos (jugador, estado, mision, al_terminar, grafo_social, marco, lugar).
# Elige el minijuego de la misión (backend/datos/minijuegos_asignacion.py), lo juega y, al terminar, traduce el «bien / mal» a las
# decisiones de siempre (backend/logica/minijuegos.cerrar_lote) y entrega a `al_terminar` el MISMO resultado del lote que entrega
# EscenaJuego: de ahí en adelante pago, confianza por grupo, efectos retardados, GameState y guardado no cambian.
#
# RESPALDO. Si algo falla al abrir o durante el juego (vista que no carga, excepción en una tecla...), la escena llama a
# `al_respaldo()` (que pone ConexionFlujo: reabre la misión en la escena de juego de siempre) y no vuelve a intervenir. Un error
# nunca deja la misión atascada.
#
# Marco de monitor y «caber» en la ventana: igual que EscenaJuego (MarcoPC, ESCALA_JUEGO, diseno_adaptable).
# Reloj: la misión sigue EN_MINIJUEGO mientras se juega, así que la pausa del reloj de 7 días que ya existe se mantiene.

import logging
import random

from ursina import Entity, Text, color, time

from backend.datos import minijuegos_asignacion as asignacion
from backend.datos import minijuegos_casos
from backend.datos.nombres_visibles import glosar_texto
from backend.logica import minijuegos as mj
from backend.logica.lote_mision import LoteMision
from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import BotonPrimario, a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb
from frontend.escenas.escena_base import Escena
from frontend.marco_pc import ESCALA_JUEGO, MarcoPC
from frontend.minijuegos import clase_de, ui
from frontend.panel_resultado_grafo import PanelResultadoGrafo

_registro = logging.getLogger(__name__)

ASPECTO = 16 / 9
DEMORA_CONTINUAR = 0.5          # s antes de aceptar Enter/Espacio en el banner (evita pulsaciones sueltas)
Y_BANNER = -0.365
ALTO_BANNER = 0.17
ANCHO_BANNER = 1.66


class EscenaMinijuego(Escena):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.marco = MarcoPC(parent=self.parent)
        diseno_adaptable.suscribir(self._al_cambiar_aspecto)
        self.fondo = Entity(parent=self, model="quad", color=rgb(estilo.COLOR_FONDO), scale=(ASPECTO, 1), z=0.2)
        self.contenido = None
        self.minijuego = None
        self.banner = None
        self.panel_resultado = PanelResultadoGrafo(parent=self, z=-0.3)
        self.usados = {}                 # ids de casos ya jugados por minijuego (para no repetir en la partida)
        self._reiniciar()

    # -- Estado de una entrada --

    def _reiniciar(self):
        self._intento = getattr(self, "_intento", 0) + 1
        self.jugador = {}
        self.estado = None
        self.mision = None
        self.grafo_social = None
        self._al_terminar = None
        self._al_respaldo = None
        self.resultado = None
        self.cerrado = False
        self.en_respaldo = False
        self.minijuego_id = None
        self.lote = None
        self.t_banner = None
        self.t_panel = None

    def _limpiar_vista(self):
        if self.minijuego is not None:
            try:
                destruir_arbol(self.minijuego)
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self.minijuego = None
        if self.contenido is not None:           # el contenedor vacío de la vista: sin esto queda una entidad suelta por apertura
            try:
                destruir_arbol(self.contenido)
            except Exception:                    # noqa: BLE001
                pass
            self.contenido = None
        if self.banner is not None:
            try:
                destruir_arbol(self.banner)
            except Exception:                    # noqa: BLE001
                pass
            self.banner = None
        self.panel_resultado.ocultar()

    # -- Marco y escala (igual que EscenaJuego) --

    _escala_base = 1
    _ajuste = 1.0

    def _poner_marco(self, activo, lugar):
        if activo:
            self.marco.mostrar(self._rol_visible(), lugar)
            self._escala_base = ESCALA_JUEGO
        else:
            self.marco.ocultar()
            self._escala_base = 1
        self.scale = self._escala_base * self._ajuste

    def _al_cambiar_aspecto(self, aspecto, factor):
        self._ajuste = factor
        self.scale = self._escala_base * self._ajuste

    def _rol_id(self):
        if isinstance(self.jugador, dict):
            return self.jugador.get("rol")
        return getattr(self.jugador, "rol", None)

    def _rol_visible(self):
        from backend.logica.roles import ROLES
        rol = self._rol_id()
        return ROLES[rol].nombre if rol in ROLES else (rol or "")

    # -- Ciclo de vida --

    def al_entrar(self, jugador=None, estado=None, mision=None, al_terminar=None, grafo_social=None, marco=False,
                  lugar="", al_respaldo=None, **datos):
        self._limpiar_vista()
        self._reiniciar()
        self.jugador = jugador or {}
        self.estado, self.mision, self.grafo_social = estado, mision, grafo_social
        self._al_terminar, self._al_respaldo = al_terminar, al_respaldo
        self._poner_marco(marco, lugar)
        try:
            self._abrir_minijuego()
        except Exception as error:               # noqa: BLE001  cualquier fallo: se vuelve al minijuego de siempre
            self._respaldo(error)

    def al_salir(self):
        self._intento += 1
        self._limpiar_vista()
        self._poner_marco(False, "")

    def _abrir_minijuego(self):
        self.minijuego_id = asignacion.asignar(self.mision, habilitados=minijuegos_casos.CASOS)
        if self.minijuego_id == mj.ACTUAL or self.estado is None or self.mision is None:
            raise RuntimeError("misión sin minijuego asignado")
        casos = minijuegos_casos.CASOS[self.minijuego_id]
        usados = self.usados.setdefault(self.minijuego_id, set())
        semilla = random.randrange(1 << 30)
        azar = random.Random(semilla)
        caso = mj.elegir_caso(casos, self.mision, asignacion.tema_de(self.mision), usados, azar)
        caso = mj.preparar_caso(caso, self.mision)
        self.contenido = Entity(parent=self)
        self.minijuego = clase_de(self.minijuego_id)(parent=self.contenido)
        self.minijuego.empezar({"caso": caso, "mision": self.mision, "azar": azar,
                                "al_terminar": self._minijuego_terminado})

    # -- Fin del minijuego: banner y «Continuar» --

    def _minijuego_terminado(self, resultado):
        self.resultado = resultado
        self.t_banner = 0.0
        self._pintar_banner(resultado)

    def _pintar_banner(self, resultado):
        bien = resultado.bien
        self.banner = Entity(parent=self, z=-0.1)
        panel_tinta(self.banner, ANCHO_BANNER, ALTO_BANNER, tono=estilo.COLOR_PANEL, position=(0, Y_BANNER, 0))
        titulo = "Verificaste bien" if bien else "Se te escapó algo"
        tono = estilo.ESTADO_EXITO if bien else estilo.ESTADO_AVISO
        x0 = -ANCHO_BANNER / 2 + a_unidades(18)
        marca = "[OK] " if bien else "[!] "
        ui.texto(self.banner, marca + titulo, 24, 1.0, tono, (x0, Y_BANNER + ALTO_BANNER / 2 - a_unidades(12)), negrita=True)
        veredicto = "cierto" if getattr(self.mision, "es_verdadera", False) else "falso"
        lineas = [resultado.detalle, f"El rumor era {veredicto}. En {glosar_texto(self.mision.destino)} se veía: {self.mision.pista}"]
        ui.texto(self.banner, "\n".join(lineas), 15, 1.18, estilo.COLOR_TEXTO,
                 (x0, Y_BANNER + ALTO_BANNER / 2 - a_unidades(46)))
        self.boton = BotonPrimario("Continuar", al_clic=self.continuar, ancho=0.3, alto=0.075, parent=self.banner,
                                   position=(ANCHO_BANNER / 2 - 0.2, Y_BANNER + 0.01, -0.01), tamano_fuente_px=22)
        Text("Enter o Espacio", parent=self.banner, origin=(0.5, 0), position=(ANCHO_BANNER / 2 - 0.2, Y_BANNER - 0.045, -0.01),
             scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO_TENUE))

    def continuar(self):
        """«Continuar»: traduce el resultado a decisiones y cierra la misión (o enseña el grafo social antes)."""
        if self.cerrado or self.resultado is None or self.en_respaldo:
            return
        if self.t_banner is not None and self.t_banner < DEMORA_CONTINUAR:
            return
        self.cerrado = True
        try:
            self.lote = LoteMision(self.mision, self.grafo_social, rol=self._rol_id(), estado=self.estado)
            entrega = mj.cerrar_lote(self.estado, self.lote, self.mision, self.resultado.bien)
        except Exception as error:               # noqa: BLE001
            if self._lote_toco_el_estado():
                # Ya se aplicaron decisiones sobre el estado: reabrir la misión en la escena de siempre las repetiría.
                # Se cierra con lo que el lote alcanzó a registrar.
                _registro.error("Minijuego %r: falló al cerrar el lote tras aplicar decisiones (%s); se entrega lo registrado.",
                                self.minijuego_id, error)
                entrega = self.lote.resultado()
            else:
                self.cerrado = False
                self._respaldo(error)
                return
        self._entrega = entrega
        if self.grafo_social is not None:
            self._mostrar_grafo_o_entregar()
        else:
            self._entregar()

    # ¿El lote ya aplicó (o intentó aplicar) decisiones sobre el estado? Entonces reabrir la misión las repetiría.
    def _lote_toco_el_estado(self):
        lote = self.lote
        return lote is not None and (lote.decisiones + lote.descartadas + getattr(lote, "intentos_decidir", 0)) > 0

    # El resultado ya está aplicado: si enseñar el grafo falla (panel, propagaciones, indicadores) NO se pasa por el respaldo
    # (repetiría decisiones); se registra el error y se entrega el resultado directamente. Igual por clic que por teclado.
    def _mostrar_grafo_o_entregar(self):
        try:
            self._mostrar_grafo()
        except Exception as error:               # noqa: BLE001
            _registro.error("Minijuego %r: falló al enseñar el grafo social (%s); se entrega el resultado sin él.",
                            self.minijuego_id, error)
            self.t_panel = None
            try:
                self.panel_resultado.ocultar()
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self._entregar()

    def _mostrar_grafo(self):
        intento = self._intento
        if self.banner is not None:
            self.banner.enabled = False
        self.minijuego.enabled = False
        self.t_panel = 0.0
        self.panel_resultado.mostrar(
            self.grafo_social, self.lote.propagaciones_con_niveles(), self.lote.deltas_acumulados,
            titulo=glosar_texto(self.mision.titulo), indicadores=self.estado.indicadores(),
            al_continuar=lambda: self._entregar(intento))

    def _entregar(self, intento=None):
        if intento is not None and intento != self._intento:
            return
        callback, self._al_terminar = self._al_terminar, None      # una sola vez
        if callback is not None:
            callback(self._entrega)

    # -- Respaldo --

    def _respaldo(self, error):
        if self.cerrado and self._lote_toco_el_estado():
            # La misión ya se cerró con decisiones aplicadas: reabrirla en la escena de siempre las repetiría. Solo se registra.
            _registro.error("Minijuego %r falló (%s) con el lote ya aplicado; no se abre el respaldo.", self.minijuego_id, error)
            return
        _registro.warning("Minijuego %r falló (%s): se usa el minijuego de siempre.", self.minijuego_id, error)
        self.en_respaldo = True
        callback, self._al_respaldo = self._al_respaldo, None
        if callback is None:
            raise error                       # sin respaldo no se puede ocultar el fallo
        callback()

    # -- Entrada y tiempo (Ursina los llama solo con la escena activa) --

    def input(self, key):
        if self.en_respaldo or self.cerrado and self.t_panel is not None:
            return
        try:
            if self.resultado is not None and not self.cerrado:
                if key in ("enter", "space", "return"):
                    self.continuar()
                return
            if self.minijuego is not None and self.resultado is None:
                self.minijuego.tecla(key)
        except Exception as error:               # noqa: BLE001
            self._respaldo(error)

    def update(self):
        if self.en_respaldo:
            return
        dt = time.dt
        try:
            if self.t_banner is not None:
                self.t_banner += dt
            if self.t_panel is not None:
                self.panel_resultado.avanzar(dt)
            if self.minijuego is not None and self.resultado is None:
                self.minijuego.avanzar(dt)
        except Exception as error:               # noqa: BLE001
            self._respaldo(error)

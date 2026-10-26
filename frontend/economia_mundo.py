# Integración de la economía con la escena del mundo (Ursina). Se crea en EscenaMundo solo si ECONOMIA está
# activa (frontend/economia_config.py). Pone: tecla I (inventario), chip de dinero abajo a la izquierda, la
# tecla E ENCADENADA con la de los vehículos, el registro de interacciones económicas (tiendas, vendedor,
# puestos de trabajo, objetos del suelo) y el panel modal.
#
# Orden de la E (alternar_e): 1) conduciendo -> delega (bajar); 2) si hay misión que atender (puede_mision) ->
# delega; 3) interacción económica cercana -> la consume; 4) si no -> delega (montar un vehículo).
# Los módulos de comercios, vendedor y trabajos se importan de forma perezosa y tolerante a fallos.

import importlib
import math
import sys
from typing import Protocol

from ursina import Entity, Text, color

from backend.datos.items_semilla import CATALOGO_ITEMS
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from backend.logica.perfil_economia import perfil_de
from frontend import diseno_adaptable, economia_config as cfg, estilo, inventario_calculos as calc, tipografia
from frontend.componentes import a_unidades, escala_fuente, panel_tinta, rgb
from frontend.inventario_calculos import ControlInventario
from frontend.inventario_ui import PanelInventario

RADIO_SUELO = 1.6
ANCHO_CHIP, ALTO_CHIP = 0.27, 0.052
MARGEN = 0.02


class Interaccion(Protocol):
    prioridad: int

    def aviso(self, jugador, x, z) -> str | None: ...
    def usar(self, jugador, economia) -> bool: ...
    def actualizar(self, dt) -> None: ...


def catalogo_activo():
    if cfg.ITEMS_SENSIBLES:
        return CATALOGO_ITEMS
    return {k: v for k, v in CATALOGO_ITEMS.items() if not v.sensible}


# Objeto tirado en el suelo: se ve como un cubito y se recoge con E.
class ObjetoSuelo:
    prioridad = 5

    def __init__(self, economia, pila, x, z):
        self.economia, self.pila, self.x, self.z = economia, pila, x, z
        self.defitem = economia.catalogo[pila.item_id]
        escena = economia.escena
        y = escena._mundo.altura(x, z) + 0.06
        self.entidad = Entity(parent=escena, model="cube", scale=0.14, position=(x, y, z), color=rgb((235, 200, 90)))

    def aviso(self, jugador, x, z):
        if math.hypot(self.x - x, self.z - z) > RADIO_SUELO:
            return None
        return f"E: recoger {self.defitem.nombre}"

    def usar(self, jugador, economia):
        perfil = perfil_de(jugador, economia.catalogo)
        res = perfil.inventario.guardar(self.pila.item_id, self.pila.cantidad, datos=self.pila.datos)
        if not res.ok:
            economia.escena.hud.mostrar_aviso(res.mensaje)
            return True
        economia.quitar(self)
        return True

    def actualizar(self, dt):
        pass

    def destruir(self):
        from frontend.componentes import destruir_arbol
        destruir_arbol(self.entidad)


class IntegracionEconomia(Entity):

    def __init__(self, escena, catalogo=None):
        super().__init__(parent=escena)
        self.escena = escena
        self.catalogo = catalogo if catalogo is not None else catalogo_activo()
        self.interacciones = []
        self._controles = {}                 # nombre del jugador -> ControlInventario
        self._jugador_panel = None
        self._texto_aviso = None
        self._chip_saldo = None
        self._anterior = None
        self._mio = self.alternar_e
        self._encadenar()
        self.panel = PanelInventario(None, nombre_fn=self._nombre_panel, parent=escena.hud)
        self._crear_chip()
        self.cargas = []
        self.modales = []                    # paneles modales de otros módulos (tienda): .enabled, .abrir(), .cerrar(), .tecla(key)
        self._jugador_modal = None
        self._instalar_modulos()

    # -- Encadenado de la E --

    def _encadenar(self):
        ctrl = self.escena.controlador
        actual = ctrl.gancho_e
        if actual is not None and getattr(actual, "__self__", None) is self:
            return
        self._anterior = actual
        ctrl.gancho_e = self._mio

    def _delegar(self, puede_mision):
        anterior = self._anterior
        if anterior is None:
            return False
        duenio = getattr(anterior, "__self__", None)
        if duenio is not None and getattr(duenio, "_activo", True) is False:   # online_vehiculos ya cerró
            vehiculos = self.escena.vehiculos
            anterior = vehiculos.alternar_e if vehiculos is not None else None
            self._anterior = anterior
            if anterior is None:
                return False
        return bool(anterior(puede_mision))

    def alternar_e(self, puede_mision):
        flujo = self.escena.flujo
        vehiculos = self.escena.vehiculos
        if vehiculos is not None and vehiculos.conduciendo:
            return self._delegar(puede_mision)
        if puede_mision or flujo is None or flujo.partida_terminada():
            return self._delegar(puede_mision)
        activo = flujo.jugador_activo()
        if activo.telefono.bloquea_movimiento() or self.panel.enabled or self.modal_abierto() is not None:
            return self._delegar(puede_mision)
        mejor = self._cercana(activo)
        if mejor is not None:
            return bool(mejor[1].usar(activo, self)) or self._delegar(puede_mision)
        return self._delegar(puede_mision)

    def _cercana(self, activo):
        mejor = None
        for inter in self.interacciones:
            texto = inter.aviso(activo, activo.x, activo.z)
            if texto and (mejor is None or inter.prioridad > mejor[1].prioridad):
                mejor = (texto, inter)
        return mejor

    # -- Registro --

    def registrar(self, interaccion):
        self.interacciones.append(interaccion)
        return interaccion

    def quitar(self, interaccion):
        if interaccion in self.interacciones:
            self.interacciones.remove(interaccion)
        destruir = getattr(interaccion, "destruir", None)
        if callable(destruir):
            destruir()

    def _instalar_modulos(self):
        for bandera, nombre in ((cfg.COMERCIOS, "comercios_mundo"), (cfg.VENDEDOR_CALLE, "vendedor_calle"),
                                (cfg.TRABAJOS, "trabajo_mundo"), (getattr(cfg, "TRANSPORTE", False), "transporte_mundo")):
            if not bandera:
                continue
            try:
                modulo = importlib.import_module(f"frontend.{nombre}")
                modulo.instalar(self)
                self.cargas.append(nombre)
            except Exception as error:
                print(f"[economia] no se pudo instalar {nombre}: {error}", file=sys.stderr)

    # -- Perfil y panel --

    def jugador(self):
        flujo = self.escena.flujo
        return None if flujo is None else flujo.jugador_activo()

    def perfil(self, jugador=None):
        jugador = jugador or self.jugador()
        return None if jugador is None else perfil_de(jugador, self.catalogo)

    def _control_de(self, jugador):
        ctrl = self._controles.get(jugador.nombre)
        perfil = self.perfil(jugador)
        if ctrl is None or ctrl.perfil is not perfil:
            ctrl = ControlInventario(perfil, al_soltar=lambda pila, j=jugador: self._soltar(j, pila))
            self._controles[jugador.nombre] = ctrl
        return ctrl

    def _nombre_panel(self):
        j = self._jugador_panel
        return "" if j is None else j.nombre

    def _soltar(self, jugador, pila):
        avatar = self.escena.avatar_de(jugador)
        rumbo = math.radians(getattr(avatar, "rumbo", 0.0) or 0.0)
        x, z = jugador.x + math.sin(rumbo) * 0.8, jugador.z + math.cos(rumbo) * 0.8
        self.registrar(ObjetoSuelo(self, pila, x, z))
        return True

    def puede_abrir(self):
        escena, flujo = self.escena, self.escena.flujo
        if flujo is None or flujo.partida_terminada() or escena.en_pausa or escena._cinematica:
            return False
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return False
        v = escena.vehiculos
        return not (v is not None and v.conduciendo)

    def abrir_panel(self):
        if not self.puede_abrir():
            return False
        jugador = self.jugador()
        if jugador.telefono.bloquea_movimiento():
            jugador.telefono.cerrar()
        self._jugador_panel = jugador
        self.panel.establecer_control(self._control_de(jugador))
        self._ocultar_hud()
        self.panel.abrir()
        self.escena._sincronizar_raton()
        return True

    # El panel es modal: mientras está abierto se esconden el minimapa, el panel de turno y el teléfono para
    # que nada choque con él en ninguna proporción de ventana (4:3, 16:10, 16:9).
    def _ocultar_hud(self):
        hud = self.escena.hud
        self._ocultos = [(e, e.visible) for e in (hud.minimapa, hud.panel_turno, hud.telefono_ui)]
        for e, _ in self._ocultos:
            e.visible = False        # `visible` y no `enabled`: TelefonoUI se reactiva sola cada frame

    def _restaurar_hud(self):
        for e, previo in getattr(self, "_ocultos", []):
            e.visible = previo
        self._ocultos = []

    # -- Modales de otros módulos (la tienda de comercios_mundo) --

    def modal_abierto(self):
        return next((m for m in self.modales if m.enabled), None)

    def abrir_modal(self, panel, control=None):
        if self.panel.enabled or self.modal_abierto() is not None or not self.puede_abrir():
            return False
        jugador = self.jugador()
        if jugador.telefono.bloquea_movimiento():
            jugador.telefono.cerrar()
        if panel not in self.modales:
            self.modales.append(panel)
        self._jugador_modal = jugador
        self._ocultar_hud()
        panel.abrir(control)
        self.escena._sincronizar_raton()
        return True

    def cerrar_modales(self):
        modal = self.modal_abierto()
        if modal is None:
            return
        for m in self.modales:
            if m.enabled:
                m.cerrar()
        self._jugador_modal = None
        self._restaurar_hud()
        if self.escena.flujo is not None and self.escena._sesion is not None:
            self.escena._sincronizar_raton()

    def cerrar_paneles(self):
        self.cerrar_modales()
        if self.panel.enabled:
            self.panel.cerrar()
            self._jugador_panel = None
            self._restaurar_hud()
            if self.escena.flujo is not None and self.escena._sesion is not None:
                self.escena._sincronizar_raton()

    def bloquea_controles(self):
        return bool(self.panel.enabled) or self.modal_abierto() is not None

    # Escape (lo llama EscenaMundo.alternar_pausa): True si lo consumió el panel.
    def escape(self):
        modal = self.modal_abierto()
        if modal is not None:
            if modal.tecla("escape") == "cerrar":
                self.cerrar_modales()
            return True
        if not self.panel.enabled:
            return False
        if self.panel.control.tecla("escape") == "cerrar":
            self.cerrar_paneles()
        return True

    def input(self, key):
        modal = self.modal_abierto()
        if modal is not None:
            if key != "escape" and modal.tecla(key) == "cerrar":
                self.cerrar_modales()
            return
        if key == "i":
            if self.panel.enabled:
                self.cerrar_paneles()
            else:
                self.abrir_panel()
            return
        if not self.panel.enabled or key == "escape":
            return
        if self.panel.control.tecla(key) == "cerrar":
            self.cerrar_paneles()

    # -- Chip de dinero --

    def _crear_chip(self):
        self.chip = Entity(parent=self.escena.hud)
        self.chip.fondo = panel_tinta(self.chip, ANCHO_CHIP, ALTO_CHIP, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                      borde_px=estilo.GROSOR_BORDE_DENSO_PX)
        self.chip.texto = Text("", parent=self.chip, origin=(0, 0), position=(0, 0, -0.01), scale=escala_fuente(17),
                               color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
        self.chip.position = (-diseno_adaptable.aspecto() / 2 + MARGEN + ANCHO_CHIP / 2, -0.5 + MARGEN + ALTO_CHIP / 2)
        diseno_adaptable.anclar(self.chip, "izquierda")
        self._actualizar_chip(force=True)

    def _actualizar_chip(self, force=False):
        perfil = self.perfil()
        saldo = None if perfil is None else perfil.inventario.saldo()
        if saldo == self._chip_saldo and not force:
            return
        self._chip_saldo = saldo
        self.chip.texto.text = calc.texto_chip(saldo or 0)
        self.chip.enabled = saldo is not None

    # -- Frame --

    def actualizar(self, dt):
        flujo = self.escena.flujo
        if flujo is None or self.escena._sesion is None:
            return
        self._encadenar_si_hace_falta()
        jugador = flujo.jugador_activo()
        if self.panel.enabled and (jugador is not self._jugador_panel or not self.puede_abrir()):
            self.cerrar_paneles()
        self.panel.actualizar()
        modal = self.modal_abierto()
        if modal is not None:
            if jugador is not self._jugador_modal or not self.puede_abrir():
                self.cerrar_modales()
            else:
                modal.actualizar()
        self._actualizar_chip()
        self.chip.enabled = self.chip.enabled and not self.escena._cinematica
        for inter in list(self.interacciones):
            inter.actualizar(dt)
        self._actualizar_aviso(flujo, jugador)

    # online_vehiculos puede haber puesto su gancho encima del mío: se vuelve a encadenar.
    def _encadenar_si_hace_falta(self):
        ctrl = self.escena.controlador
        actual = ctrl.gancho_e
        if actual is None or getattr(actual, "__self__", None) is not self:
            self._encadenar()

    def _actualizar_aviso(self, flujo, jugador):
        texto = None
        v = self.escena.vehiculos
        libre = (not self.panel.enabled and self.modal_abierto() is None and not self.escena.en_pausa and not self.escena._cinematica
                 and not jugador.telefono.bloquea_movimiento() and not flujo.puede_interactuar()
                 and not (v is not None and (v.conduciendo or v._texto is not None)))
        if libre:
            mejor = self._cercana(jugador)
            texto = None if mejor is None else mejor[0]
        if texto != self._texto_aviso:
            self._texto_aviso = texto
            if texto:
                self.escena.hud.mostrar_aviso(texto)
            else:
                self.escena.hud.ocultar_aviso()

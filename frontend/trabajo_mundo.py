# Puestos de trabajo en el mundo: cada comercio de tipo «puesto_trabajo» (o con `trabajo_id`) es una Interacción
# «E: Trabajar en <nombre>» registrada en la economía (frontend/economia_mundo.py). E abre un menú pequeño
# «Trabajar (turno de N s, paga R$ a–b) / Cancelar»; «Trabajar» llama a `economia.al_trabajar(puesto)`, que
# main.py conecta con ConexionFlujo.iniciar_trabajo (escena de trabajo). Con fatiga >= 100 (bandera CANSANCIO)
# no se puede trabajar y el aviso lo dice. En línea: «Trabajar aún no está disponible en línea» salvo que
# TRABAJO_ONLINE sea True.
#
# Los comercios que además son tiendas (panadería, bar...) tienen su propia E de compra; para no pisarse, el
# puesto de trabajo de una tienda va 2,8 m al lado (el primer lado transitable) con un cartel «TRABAJO».
# Sin cambios en economia_mundo.py: el menú engancha bloquea_controles / escape / cerrar_paneles de la instancia.

import math
import sys
from dataclasses import dataclass

from ursina import Entity, Text, time

from backend.datos.comercios_semilla import CATALOGO_COMERCIOS
from backend.datos.trabajos_semilla import CATALOGO_TRABAJOS
from backend.logica.comercios import RADIO_COMERCIO, ancla_de, resolver_ancla
from backend.logica.perfil_economia import FATIGA_MAX
from backend.logica.trabajos import MENSAJE_AGOTADO, puede_trabajar
from frontend import economia_config as cfg, estilo, tipografia
from frontend.componentes import BotonPrimario, BotonSecundario, escala_fuente, panel_tinta, rgb

PRIORIDAD = 6
DESPLAZAMIENTO_TIENDA = 2.8        # m al lado de la tienda
RADIO_DESPLAZADO = 1.4
SEGUNDOS_AVISO = 3.0
MENSAJE_EN_LINEA = "Trabajar aún no está disponible en línea"
ANCHO_MENU, ALTO_MENU = 0.78, 0.36


# Lo que recibe `economia.al_trabajar` y `ConexionFlujo.iniciar_trabajo`: el puesto elegido.
@dataclass(frozen=True)
class Puesto:
    comercio: object
    trabajo: object

    @property
    def nombre(self):
        return self.comercio.nombre


def texto_turno(trabajo):
    return f"Turno de {int(trabajo.duracion_s)} s, paga R$ {trabajo.pago_base} a {trabajo.pago_max}"


# Sitio del puesto: (x, z, radio, desplazado). Una tienda deja libre su punto y el trabajo va a un lado.
def sitio_del_puesto(mundo, comercio, x, z, rumbo):
    if comercio.tipo != "tienda":
        return x, z, RADIO_COMERCIO, False
    r = math.radians(rumbo)
    lateral = (math.cos(r), -math.sin(r))
    transitable = getattr(mundo, "es_transitable", None)
    for signo in (1, -1):
        px, pz = x + signo * lateral[0] * DESPLAZAMIENTO_TIENDA, z + signo * lateral[1] * DESPLAZAMIENTO_TIENDA
        if transitable is None or transitable(px, pz):
            return px, pz, RADIO_DESPLAZADO, True
    return x, z, RADIO_COMERCIO, False


# Pide un turno: o dice por qué no se puede (en línea, agotado, sin conexión al flujo) o abre el menú. True = E consumida.
def pedir_turno(economia, menu, puesto, jugador):
    perfil = economia.perfil(jugador)
    if getattr(economia.escena, "online", None) is not None and not cfg.TRABAJO_ONLINE:
        menu.decir(MENSAJE_EN_LINEA)
    elif cfg.CANSANCIO and perfil is not None and not puede_trabajar(perfil):
        menu.decir(MENSAJE_AGOTADO)
    elif getattr(economia, "al_trabajar", None) is None:
        menu.decir("Trabajar no está disponible ahora")
    else:
        menu.abrir(puesto, jugador)
    return True


class PuestoTrabajo:

    def __init__(self, economia, menu, puesto, x, z, radio, desplazado):
        self.economia, self.menu, self.puesto = economia, menu, puesto
        self.x, self.z, self.radio = float(x), float(z), radio
        self.prioridad = PRIORIDAD if desplazado else PRIORIDAD - 3     # sin sitio propio, cede ante la tienda
        self.cartel = self._crear_cartel(economia.escena) if desplazado else None

    def _crear_cartel(self, escena):
        from frontend.piezas import etiqueta, silenciar
        y = escena._mundo.altura(self.x, self.z)
        cartel = Entity(parent=escena, position=(self.x, y, self.z))
        Entity(parent=cartel, model="cube", color=rgb(estilo.COLOR_ACENTO), scale=(0.07, 1.7, 0.07), y=0.85)
        etiqueta("TRABAJO", parent=cartel, y=2.0, scale=1.6)
        return silenciar(cartel)

    def _cerca(self, x, z):
        return math.hypot(x - self.x, z - self.z) <= self.radio

    def _agotado(self, jugador):
        perfil = self.economia.perfil(jugador)
        return cfg.CANSANCIO and perfil is not None and not puede_trabajar(perfil)

    def aviso(self, jugador, x, z):
        if not self._cerca(x, z) or self.menu.enabled:
            return None
        if self._en_linea() and not cfg.TRABAJO_ONLINE:
            return MENSAJE_EN_LINEA
        if self._agotado(jugador):
            return MENSAJE_AGOTADO
        return f"E: Trabajar en {self.puesto.nombre}"

    def _en_linea(self):
        return getattr(self.economia.escena, "online", None) is not None

    def usar(self, jugador, economia=None):
        if not self._cerca(jugador.x, jugador.z) or self.menu.enabled:
            return False
        return pedir_turno(self.economia, self.menu, self.puesto, jugador)

    def actualizar(self, dt):
        pass

    def destruir(self):
        if self.cartel is not None:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self.cartel)
            self.cartel = None


# Menú modal pequeño, centrado, en el HUD: Enter trabaja, Esc cancela (o los botones con el ratón).
class MenuTrabajo(Entity):

    def __init__(self, economia, **opciones):
        super().__init__(parent=economia.escena.hud, enabled=False, z=-0.05, **opciones)
        self.economia = economia
        self.puesto = None
        self.jugador = None
        self._edad = 0
        self.panel = panel_tinta(self, ANCHO_MENU, ALTO_MENU, z=-0.01)
        self.titulo = Text("", parent=self.panel, origin=(0, 0), position=(0, 0.115, -0.02), scale=escala_fuente(26),
                           color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
        self.detalle = Text("", parent=self.panel, origin=(0, 0), position=(0, 0.05, -0.02), scale=escala_fuente(17),
                            color=rgb(estilo.COLOR_TEXTO))
        self.cansancio = Text("", parent=self.panel, origin=(0, 0), position=(0, 0.01, -0.02), scale=escala_fuente(15),
                              color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.boton_trabajar = BotonPrimario("Trabajar (Enter)", al_clic=self.aceptar, ancho=0.33, alto=0.07,
                                            tamano_fuente_px=20, parent=self.panel, position=(-0.18, -0.09, -0.02))
        self.boton_cancelar = BotonSecundario("Cancelar (Esc)", al_clic=self.cerrar, ancho=0.3, alto=0.07,
                                              tamano_fuente_px=20, parent=self.panel, position=(0.19, -0.09, -0.02))

    def decir(self, texto):
        aviso_temporal(self.economia, texto)

    def abrir(self, puesto, jugador):
        self.puesto, self.jugador, self._edad = puesto, jugador, 0
        self.titulo.text = f"Trabajar en {puesto.nombre}".replace("<", "(")
        self.detalle.text = texto_turno(puesto.trabajo)
        perfil = self.economia.perfil(jugador)
        self.cansancio.text = (f"Cansancio: {perfil.fatiga}/{FATIGA_MAX} · este turno +{puesto.trabajo.fatiga}"
                               if perfil is not None else "")
        self.enabled = True
        self.economia.escena._sincronizar_raton()

    def cerrar(self):
        if not self.enabled:
            return
        self.enabled = False
        self.puesto = self.jugador = None
        escena = self.economia.escena
        if escena.flujo is not None and getattr(escena, "_sesion", None) is not None:
            escena._sincronizar_raton()

    def aceptar(self):
        puesto, jugador = self.puesto, self.jugador
        if puesto is None:
            return
        activo = self.economia.jugador()
        self.cerrar()
        if activo is not jugador:
            return                          # cambió el turno mientras el menú estaba abierto
        callback = getattr(self.economia, "al_trabajar", None)
        if callback is not None:
            callback(puesto)

    def update(self):
        self._edad += 1
        if self.enabled and self.economia.jugador() is not self.jugador:
            self.cerrar()

    def input(self, key):
        if not self.enabled or self._edad == 0:         # la E que abrió el menú no lo acepta
            return
        if key in ("enter", "return"):
            self.aceptar()
        elif key == "escape":
            self.cerrar()


# Aviso breve «+R$ 17»: el aviso del HUD no se apaga solo, así que un temporizador lo retira y hace que la
# economía vuelva a decidir qué aviso toca (puede seguir siendo «E: Trabajar en...»).
class _Temporizador(Entity):

    def __init__(self, economia):
        super().__init__(parent=economia)
        self.economia = economia
        self.restante = 0.0
        self.texto = None
        self.enabled = False

    def poner(self, texto, segundos):
        self.texto, self.restante, self.enabled = texto, segundos, True

    def update(self):
        self.restante -= time.dt
        if self.restante > 0:
            return
        self.enabled = False
        hud = self.economia.escena.hud
        if getattr(hud.aviso_generico, "cadena", None) == self.texto:
            hud.ocultar_aviso()
        self.economia._texto_aviso = None          # que _actualizar_aviso decida de nuevo


def aviso_temporal(economia, texto, segundos=SEGUNDOS_AVISO):
    temporizador = getattr(economia, "_temporizador_aviso", None)
    if temporizador is None:
        temporizador = economia._temporizador_aviso = _Temporizador(economia)
    economia.escena.hud.mostrar_aviso(texto)
    # La economía cree que ya se muestra su propio aviso (el de ahora): así no pisa el mío hasta que cambie.
    jugador = economia.jugador()
    mejor = None if jugador is None else economia._cercana(jugador)
    economia._texto_aviso = None if mejor is None else mejor[0]
    temporizador.poner(texto, segundos)


def _enganchar_menu(economia, menu):
    bloquea, escape, cerrar = economia.bloquea_controles, economia.escape, economia.cerrar_paneles

    def bloquea_controles():
        return bool(bloquea() or menu.enabled)

    def escape_():
        if menu.enabled:
            menu.cerrar()
            return True
        return escape()

    def cerrar_paneles():
        menu.cerrar()
        cerrar()

    economia.bloquea_controles, economia.escape, economia.cerrar_paneles = bloquea_controles, escape_, cerrar_paneles


# Crea el menú y un puesto por cada comercio con trabajo. Devuelve la lista de PuestoTrabajo.
def instalar(economia, comercios=None, trabajos=None):
    comercios = CATALOGO_COMERCIOS if comercios is None else comercios
    trabajos = CATALOGO_TRABAJOS if trabajos is None else trabajos
    escena = economia.escena
    menu = MenuTrabajo(economia)
    _enganchar_menu(economia, menu)
    economia.menu_trabajo = menu
    economia.aviso_temporal = lambda texto, segundos=SEGUNDOS_AVISO: aviso_temporal(economia, texto, segundos)
    puestos = []
    for comercio in comercios:
        if comercio.tipo != "puesto_trabajo" and not comercio.trabajo_id:
            continue
        trabajo = trabajos.get(comercio.trabajo_id)
        if trabajo is None:
            print(f"[trabajo] {comercio.id}: trabajo desconocido {comercio.trabajo_id!r}", file=sys.stderr)
            continue
        try:
            x, z, rumbo = resolver_ancla(escena._mundo, ancla_de(escena._mundo, comercio))
        except ValueError as error:
            print(f"[trabajo] {comercio.id}: ancla inválida ({error})", file=sys.stderr)
            continue
        sx, sz, radio, desplazado = sitio_del_puesto(escena._mundo, comercio, x, z, rumbo)
        puesto = PuestoTrabajo(economia, menu, Puesto(comercio, trabajo), sx, sz, radio, desplazado)
        economia.registrar(puesto)
        puestos.append(puesto)
    economia.puestos_trabajo = puestos
    return puestos


# Conecta `economia.al_trabajar` con `iniciar(puesto)` (main.py: ConexionFlujo.iniciar_trabajo). Acepta dos formas:
#   al_trabajar(puesto)                -> el jugador ya confirmó en el menú: empieza el turno.
#   al_trabajar(jugador, trabajo_id)   -> lo llama comercios_mundo.ComercioMundo (puesto_trabajo): abre el menú.
def conectar(economia, iniciar):
    def al_trabajar(*args):
        if len(args) == 1:
            return iniciar(args[0])
        jugador, trabajo_id = args[0], args[1]
        puesto = next((p.puesto for p in getattr(economia, "puestos_trabajo", ())
                       if p.puesto.trabajo.id == trabajo_id), None)
        menu = getattr(economia, "menu_trabajo", None)
        if puesto is None or menu is None:
            aviso_temporal(economia, "Aquí aún no hay turnos disponibles.")
            return False
        return pedir_turno(economia, menu, puesto, jugador)
    economia.al_trabajar = al_trabajar

# Vendedor de la calle (Seu Zé): un NPC quieto que vende bolsitas de bicarbonato a R$ 5 en el borde del mercadito.
# Es un artículo de venta del juego de ficción; el aviso y los mensajes no dicen nada más del producto.
#
# Cumple el Protocol Interaccion de frontend/economia_mundo.py (prioridad, aviso, usar, actualizar). Al pulsar E
# valida y COBRA en el acto (backend/logica/dinero.comprar es atómica: dinero, espacio y peso); si falla solo
# hay mensaje y ninguna animación. Si pasa, TraspasoMano anima la entrega (1,65 s, controles congelados): es
# solo presentación, saltarla no duplica ni pierde nada. `instalar(economia)` lo crea y lo registra.

import math

from backend.datos.comercios_semilla import CATALOGO_COMERCIOS
from backend.datos.items_semilla import CATALOGO_ITEMS
from backend.logica import dinero
from backend.logica.comercios import RADIO_COMERCIO, ancla_de, resolver_ancla
from backend.logica.perfil_economia import perfil_de

from frontend.traspaso_mano import TraspasoMano, crear_bolsita

ITEM = "bicarbonato"
INDICE_NPC = 100                 # plan_npc(100 + ...): los vendedores van detrás de los peatones 0-11
NOMBRE = "Seu Zé"
SEGUNDOS_MENSAJE = 2.5
PRIORIDAD = 10
TEXTO_CARTEL = "Bicarbonato de sódio — cozinha e limpeza"     # nombre completo del producto, sin apodos ni jerga
LATERAL_CARTEL = 1.1             # m al lado de Seu Zé (dentro de los 1,4 m que se le reservan)
ANCHO_CARTEL = 1.25


class VendedorCalle:

    prioridad = PRIORIDAD

    def __init__(self, escena, comercio, x, z, rumbo=0.0, crear_npc=None):
        self._escena = escena
        self.comercio = comercio
        self.x, self.z = float(x), float(z)
        self.nombre = comercio.npc or NOMBRE
        self.precio = CATALOGO_ITEMS[ITEM].precio
        self.npc = self._crear_npc(escena, rumbo, crear_npc)
        self.bolsita = crear_bolsita(escena)
        self.traspaso = None
        self._mensaje = None
        self._t_mensaje = 0.0

    def _crear_npc(self, escena, rumbo, crear_npc):
        from frontend.npc_modelo import crear_npc as fabrica
        from frontend.peatones import ROPA, SEMILLA
        from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
        fabrica = crear_npc or fabrica
        npc = fabrica(INDICE_NPC, SEMILLA, aspecto_peaton(INDICE_NPC, SEMILLA), rasgos_peaton(INDICE_NPC, SEMILLA),
                      ROPA[INDICE_NPC % len(ROPA)], parent=escena)
        npc.aro.enabled = False
        self._poner_nombre(npc)
        npc.suelo = escena._mundo.altura
        npc.colocar(self.x, self.z)
        npc.fijar_rumbo(rumbo)
        return npc

    def _poner_nombre(self, npc):
        from frontend.componentes import destruir_arbol
        from frontend.piezas import etiqueta, silenciar
        npc.nombre = self.nombre
        try:
            y = npc.etiqueta.y
            destruir_arbol(npc.etiqueta)
            npc.etiqueta = silenciar(etiqueta(self.nombre, parent=npc, y=y, scale=8))
        except Exception as error:
            print(f"[assets] vendedor: no se pudo poner el nombre ({error})")

    # -- Protocol Interaccion --

    def _cerca(self, x, z):
        return math.hypot(x - self.x, z - self.z) <= RADIO_COMERCIO

    @property
    def ocupado(self):
        return self.traspaso is not None and self.traspaso.activo

    def aviso(self, jugador, x, z):
        if self.ocupado:
            return None
        if self._mensaje and self._cerca(x, z):
            return self._mensaje
        if self._cerca(x, z):
            return f"E: comprar bicarbonato de sodio (R$ {self.precio})"
        return None

    def usar(self, jugador, economia=None):
        if self.ocupado or not self._cerca(jugador.x, jugador.z):
            return False
        resultado = dinero.comprar(perfil_de(jugador), self.comercio, ITEM)
        if not resultado.ok:
            self._decir(resultado.mensaje)          # sin dinero / sin espacio / mucho peso: solo mensaje
            return True
        self._decir("Bolsita de bicarbonato guardada")
        self.traspaso = TraspasoMano(self._escena, self, jugador, self._al_terminar)
        if not self.traspaso.iniciar():
            self.traspaso = None                    # sin avatar: la compra vale igual, sin animación
        return True

    def actualizar(self, dt):
        if self.traspaso is not None:
            if self.traspaso.activo:
                self.traspaso.avanzar(dt)
            else:
                self.traspaso = None
        if self._mensaje:
            self._t_mensaje -= dt
            if self._t_mensaje <= 0:
                self._mensaje = None
        camara = getattr(self._escena, "camara", None)
        ignorar = getattr(camara, "ignorar", None)
        if isinstance(ignorar, list) and self.npc not in ignorar:
            ignorar.append(self.npc)                # la cámara no se acerca al vendedor

    # -- Ayudas --

    def bloquea_controles(self):
        return self.ocupado

    def saltar(self):
        if self.ocupado:
            self.traspaso.saltar()

    def _al_terminar(self):
        self.traspaso = None

    def _decir(self, texto):
        self._mensaje = texto
        self._t_mensaje = SEGUNDOS_MENSAJE


def _comercio_vendedor():
    return next(c for c in CATALOGO_COMERCIOS if c.tipo == "vendedor_calle" and ITEM in c.stock)


# Crea a Seu Zé en su ancla del mundo y lo registra en la economía. Congela los controles mientras dura el
# traspaso (envuelve controles_bloqueados de la escena una sola vez; es inofensivo si la economía ya lo hace).
def instalar(economia):
    escena = economia.escena
    comercio = _comercio_vendedor()
    x, z, rumbo = resolver_ancla(escena._mundo, ancla_de(escena._mundo, comercio))
    vendedor = VendedorCalle(escena, comercio, x, z, rumbo)
    vendedor.cartel = poner_cartel(escena, x, z, rumbo)
    _bloquear_durante_traspaso(escena, vendedor)
    economia.registrar(vendedor)
    return vendedor


# Cartel legible junto al puesto de Seu Zé: tablero fino sobre un poste y una sola línea de Text (sin colisión, sin
# update). Nunca lanza: si falla, el puesto sigue sin cartel.
def poner_cartel(escena, x, z, rumbo):
    try:
        from ursina import Text
        from frontend.componentes import rgb
        from frontend.piezas import pieza, silenciar
        r = math.radians(rumbo)
        fx, fz = math.sin(r), math.cos(r)               # hacia el cliente
        px = x + math.cos(r) * LATERAL_CARTEL + fx * 0.1
        pz = z - math.sin(r) * LATERAL_CARTEL + fz * 0.1
        suelo = escena._mundo.altura(px, pz)
        raiz = pieza(parent=escena, position=(px, suelo, pz), rotation_y=rumbo + 180, name="cartel_bicarbonato")
        pieza(parent=raiz, model="cube", color=rgb((120, 84, 52)), scale=(0.06, 1.0, 0.06), position=(0, 0.5, 0))
        pieza(parent=raiz, model="cube", color=rgb((250, 244, 226)), scale=(ANCHO_CARTEL, 0.34, 0.04),
              position=(0, 1.05, 0))
        texto = Text(TEXTO_CARTEL, parent=raiz, origin=(0, 0), position=(0, 1.05, -0.03), scale=2.3,
                     color=rgb((40, 40, 48)))
        texto.rotation_y = 0
        silenciar(raiz)
        return raiz
    except Exception as error:
        print(f"[assets] vendedor: no se pudo poner el cartel ({error})")
        return None


def _bloquear_durante_traspaso(escena, vendedor):
    original = getattr(escena, "controles_bloqueados", None)
    if not callable(original):
        return
    escena.controles_bloqueados = lambda: bool(original()) or vendedor.bloquea_controles()

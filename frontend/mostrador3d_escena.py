# Mostrador 3D en PRIMERA PERSONA (Ursina; dentro de EscenaTrabajo) para los trabajos ATENDER: panadería, supermercado,
# feria y bar. Bandera ALCALDE_MOSTRADOR3D (=0: el ATENDER 2D de siempre). Lógica: backend/logica/mostrador3d_turno.py;
# productos, precios y colores de cada local: backend/datos/mostrador3d_locales.json.
#   - El jugador está DETRÁS del puesto: mostrador con 4 cajones de producto (con su precio), repisa con más género, la
#     caja registradora con billetes y monedas (frontend/mostrador3d_caja.py) y, de fondo, el de su local
#     (frontend/mostrador3d_fondos.py: calle de la feria, panadería, supermercado o bar).
#   - Llega un cliente (NPC 3D del juego), pide (globo sobre la cabeza), el jugador le da los productos (clic o 1-4), el
#     cliente paga con billetes/monedas y el jugador le devuelve el cambio con la caja (clic + Enter).
#   - Cambio correcto: «¡Gracias!» y se va contento. Mal: se enoja (sacude el cuerpo, globo rojo) y baja la
#     convivencia del barrio (la escena lo aplica con frontend/mostrador3d_convivencia.py, solo partida local).
# Lo 2D que se queda: tiempo, aciertos y errores (arriba), el cartel con pedido/total/pago/cambio, los avisos y el
# resultado. El set vive en `scene` (el mundo está desactivado durante el turno); cerrar_3d() lo deshace todo.

import math
import os

from ursina import Entity, Text, color, scene
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader, unlit_shader

from backend.logica import mostrador3d_dinero as dinero
from backend.logica import mostrador3d_turno as mt
from frontend import diseno_adaptable, estilo
from frontend import mostrador3d_fondos as mf
from frontend import mostrador3d_productos as mp
from frontend.componentes import BotonPrimario, BotonSecundario, destruir_arbol, escala_fuente, panel_tinta, rgb
from frontend.mostrador3d_caja import Caja
from frontend.props_mundo import caja, prisma
from frontend.taller3d_escena import devolver_fondo, esconder_fondo
from frontend.trabajo_dibujos import _seguro, _texto

MOSTRADOR3D = True
ALTO_MOSTRADOR = 0.95
TOMA = {"position": (0.1, 1.64, -1.32), "target": (0.1, 1.44, 0.8), "fov": 84}
X_CAJONES = (-0.98, -0.7, -0.42, -0.14)
Z_CAJONES = 0.04
CAJA = (0.6, ALTO_MOSTRADOR, -0.04)
BANDEJA = (0.42, ALTO_MOSTRADOR + 0.005, 0.34)
PAGO = (0.02, ALTO_MOSTRADOR + 0.005, 0.36)
ENTREGADOS = (-0.66, ALTO_MOSTRADOR, 0.3)
# Cliente: entra por la derecha, se para frente al mostrador y se va por la izquierda.
X_ENTRADA, X_MOSTRADOR, X_SALIDA, Z_CLIENTE = 3.4, 0.06, -3.4, 1.0
# NPC distintos que se turnan (se crean una vez al empezar)
N_CLIENTES = 3
# primer índice de peatón (aspecto y ropa deterministas de peatones_calculos)
INDICE_NPC = 40
ESPERA_ENOJADO, ESPERA_CONTENTO = 0.9, 0.5
DURACION_VUELO = 0.32
ESCALA_GLOBO = 1.8
# el globo, a la izquierda de la cabeza del cliente (a la derecha va el cartel)
DX_GLOBO = -0.62
ANCHO_CARTEL = 0.34
MADERA, MADERA_OSCURA = (150, 104, 64), (104, 70, 44)
VERDE_GLOBO, ROJO_GLOBO = (90, 200, 110), (230, 80, 70)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_MOSTRADOR3D", MOSTRADOR3D)


def _suave(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def pose_cliente(estado, t, reaccion=None):
    """(x, z, rumbo, velocidad, temblor 0..1) del cliente a los `t` s de entrar en `estado` (TurnoMostrador)."""
    if estado == mt.LLEGANDO:
        k = t / mt.LLEGADA_S
        x = X_ENTRADA + (X_MOSTRADOR - X_ENTRADA) * _suave(k)
        return x, Z_CLIENTE, (-90.0 if k < 0.85 else 180.0), (1.5 if k < 1 else 0.0), 0.0
    if estado == mt.SALIENDO:
        espera = ESPERA_ENOJADO if reaccion == "enojado" else ESPERA_CONTENTO
        if t < espera:
            return X_MOSTRADOR, Z_CLIENTE, 180.0, 0.0, (1.0 if reaccion == "enojado" else 0.0)
        k = (t - espera) / max(0.1, mt.SALIDA_S - espera)
        x = X_MOSTRADOR + (X_SALIDA - X_MOSTRADOR) * _suave(k)
        return x, Z_CLIENTE, -90.0, (2.2 if reaccion == "enojado" else 1.5), 0.0
    return X_MOSTRADOR, Z_CLIENTE, 180.0, 0.0, 0.0


def texto_globo(turno):
    """(texto, color) del globo del cliente, o (None, None) sin globo."""
    if turno.estado == mt.PEDIDO:
        return f"Quiero {turno.pedido_texto()}", estilo.PAPEL
    if turno.estado == mt.CAMBIO:
        pagado = turno.pagado()
        if sum(pagado) == turno.total():
            return f"Te pago justo: {dinero.formatear(sum(pagado))}", estilo.PAPEL
        return f"Te pago con {dinero.formatear(sum(pagado))}", estilo.PAPEL
    if turno.estado == mt.SALIENDO and turno.reaccion == "enojado":
        return "¡Me diste mal el cambio!", ROJO_GLOBO
    if turno.estado == mt.SALIENDO and turno.reaccion == "contento":
        return "¡Gracias, vuelvo mañana!", VERDE_GLOBO
    return None, None


def _set_local(local):
    """Fondo del local (frontend/mostrador3d_fondos.py) y el puesto del jugador: UNA malla."""
    nombre = mf.nombre_fondo(local)
    m = mf.malla_fondo(nombre, local)
    _puesto(m, local, mf.exterior(nombre))
    return m


def _puesto(m, local, exterior=True):
    """Mostrador del local y repisa; en la calle además postes y toldo de rayas (en los interiores ya hay techo)."""
    toldo = tuple(local.get("toldo", (200, 80, 60)))
    tablero = tuple(local.get("mostrador", MADERA))
    m.agregar(caja(), (0, ALTO_MOSTRADOR - 0.025, 0.05), (2.6, 0.05, 0.84), 0, tablero, (0.85, 1.05), 0.06)
    m.agregar(caja(), (0, ALTO_MOSTRADOR / 2, 0.46), (2.6, ALTO_MOSTRADOR - 0.05, 0.04), 0, tablero, (0.75, 0.95), 0.06)
    # repisa a la izquierda, con más género (decorado)
    for k in range(3):
        m.agregar(caja(), (-1.55, 0.6 + 0.45 * k, -0.4), (0.4, 0.03, 1.0), 0, MADERA)
    m.agregar(caja(), (-1.75, 1.05, -0.4), (0.03, 1.2, 1.0), 0, MADERA_OSCURA)
    if not exterior:
        # interior: un letrero con el color del local sobre el mostrador, colgado del techo
        m.agregar(caja(), (0, 2.55, 0.5), (1.6, 0.3, 0.04), 0, toldo, (0.95, 1.05))
        return
    for x in (-1.3, 1.3):
        m.agregar(caja(), (x, 1.2, 0.48), (0.07, 2.4, 0.07), 0, MADERA_OSCURA)
        m.agregar(caja(), (x, 1.2, -1.2), (0.07, 2.4, 0.07), 0, MADERA_OSCURA)
    # toldo de rayas del color del local, con el faldón de picos hacia la calle
    for j in range(8):
        tono = toldo if j % 2 == 0 else (244, 240, 230)
        m.agregar(caja(), (-1.4 + j * 0.4 + 0.2, 2.45, -0.35), (0.4, 0.03, 1.9), 0, tono, (1, 1), 0, -10)
        m.agregar(prisma(3, 0.5, 0.0), (-1.2 + j * 0.4, 2.32, 0.6), (0.4, 0.18, 0.02), 0, tono, (1, 1), 0, 180)


def _repisa(raiz, local):
    """Productos repetidos en la repisa de la izquierda (decorado, sin clic)."""
    for k, producto in enumerate(local["productos"]):
        malla = mp.malla_producto(producto)
        for j in range(3):
            fila = k % 3
            Entity(parent=raiz, model=malla.mesh(), shader=lit_with_shadows_shader,
                   position=(-1.55 + 0.05 * (j - 1), 0.62 + 0.45 * fila, -0.75 + 0.25 * (k // 3) + 0.14 * j + 0.3 * (k % 2)),
                   scale=1.0)


def _cliente(indice, parent):
    from frontend.npc_modelo import crear_npc
    from frontend.peatones import ROPA, SEMILLA
    from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
    npc = crear_npc(indice, SEMILLA, aspecto_peaton(indice, SEMILLA), rasgos_peaton(indice, SEMILLA),
                    ROPA[indice % len(ROPA)], parent=parent)
    npc.automatico = False
    for parte in ("aro", "etiqueta"):
        if getattr(npc, parte, None) is not None:
            getattr(npc, parte).enabled = False
    npc.enabled = False
    return npc


class JuegoMostrador:

    # padre: Entity del juego (EscenaTrabajo.juego, camera.ui). turno: TurnoMostrador (solo se LEE). escena: la
    # EscenaTrabajo. al_accion(nombre, *args): la escena (controlador) aplica la acción al turno; la vista no escribe
    # en el modelo. Sin al_accion (pruebas sueltas) llama al turno directamente.
    def __init__(self, padre, turno, jugador=None, escena=None, al_accion=None):
        self.padre, self.turno, self.escena = padre, turno, escena
        self.al_accion = al_accion
        self.raiz = Entity(parent=padre)
        self.set = None
        self._luces, self._camara = [], None
        self._ocultos, self._bandas = [], []
        self._clientes, self._cliente_actual = [], None
        self._entregados, self._vuelos = [], []
        self._firma = None
        self._firma_entregado = None
        self._rojo = {}
        self._t = 0.0
        try:
            self._construir()
        except Exception:
            self.cerrar_3d()
            raise

    # -- Construcción --

    def _construir(self):
        from frontend.minijuegos_3d.camaras import CamaraMinijuego
        from frontend.piezas import encender_luz, silenciar
        # la ayuda y el aviso de abajo se esconden (van en el cartel): así nada tapa los cajones ni la caja
        pie = list(getattr(self.escena, "_pie", [])) + [getattr(self.escena, "_t_feedback", None)]
        self._ocultos, self._bandas = esconder_fondo(self.escena, ((0.43, 0.185),), pie)
        local = self.turno.local
        raiz = self.set = Entity(parent=scene, name="set_mostrador3d")
        fondo = mf.nombre_fondo(local)
        cielo, luz_ambiente, luz_sol = mf.luz(fondo)
        Entity(parent=raiz, model="quad", color=rgb(cielo), scale=(80, 30), position=(0, 8, 24), shader=unlit_shader)
        silenciar(Entity(parent=raiz, model=_set_local(local).mesh(), shader=lit_with_shadows_shader))
        mf.carteles(raiz, fondo, local)
        _repisa(raiz, local)
        sol = DirectionalLight(parent=raiz, shadows=True, shadow_map_resolution=(1024, 1024))
        sol.look_at((-0.4, -1.3, 0.7))
        sol.color = color.rgba32(*luz_sol, 255)
        ambiente = AmbientLight(parent=raiz, color=color.rgba32(*luz_ambiente, 255))
        self._luces = [sol, ambiente]
        for luz in self._luces:
            encender_luz(luz, True)
        self._cajones = [self._cajon(raiz, i, p) for i, p in enumerate(local["productos"])]
        self.caja = Caja(raiz, CAJA, self._agregar, self._quitar, bandeja=BANDEJA, pago=PAGO)
        self._clientes = [_cliente(INDICE_NPC + k * 7, raiz) for k in range(N_CLIENTES)]
        self.globo = Entity(parent=raiz, billboard=True, position=(X_MOSTRADOR + DX_GLOBO, 1.5, Z_CLIENTE), enabled=False)
        self._fondo_globo = Entity(parent=self.globo, model="quad", color=rgb(estilo.PAPEL), shader=unlit_shader,
                                   scale=(1.0, 0.11), z=0.002)
        self._texto_globo = Text(parent=self.globo, text="", scale=ESCALA_GLOBO, origin=(0, 0), color=rgb(estilo.TINTA))
        self._camara = CamaraMinijuego()
        self._camara.tomar(TOMA)
        self._construir_cartel()

    def _cajon(self, raiz, i, producto):
        x = X_CAJONES[i]
        grupo = Entity(parent=raiz, position=(x, ALTO_MOSTRADOR, Z_CAJONES))
        Entity(parent=grupo, model=mp.malla_cajon().mesh(), shader=lit_with_shadows_shader)
        malla = mp.malla_producto(producto)
        for k, (dx, dz) in enumerate(((-0.07, -0.05), (0.07, -0.04), (0.0, 0.05), (-0.08, 0.06), (0.08, 0.05))):
            Entity(parent=grupo, model=malla.mesh(), shader=lit_with_shadows_shader, position=(dx, 0.012, dz),
                   rotation_y=37 * k)
        # cartel del precio (con el número de la tecla) clavado en el borde del cajón que da al jugador
        Entity(parent=grupo, model="cube", color=rgb(MADERA_OSCURA), shader=lit_with_shadows_shader,
               position=(0.1, 0.12, 0.1), scale=(0.012, 0.24, 0.012))
        Entity(parent=grupo, model="cube", color=rgb(estilo.PAPEL), shader=unlit_shader, position=(0, 0.25, 0.1),
               scale=(0.24, 0.085, 0.006))
        Text(parent=grupo, text=f"{i + 1}  {producto['nombre']}", scale=0.95, origin=(0, 0), color=rgb(estilo.TINTA),
             position=(0, 0.267, 0.094))
        Text(parent=grupo, text=dinero.formatear(producto["precio"]), scale=1.05, origin=(0, 0),
             color=rgb((170, 40, 36)), position=(0, 0.234, 0.094))
        zona = Entity(parent=grupo, model="cube", collider="box", color=color.rgba32(255, 255, 255, 0),
                      shader=unlit_shader, position=(0, 0.13, 0.02), scale=(0.27, 0.28, 0.26))
        zona.on_click = lambda n=i: self._entregar(n)
        zona.on_mouse_enter = lambda z=zona: setattr(z, "color", color.rgba32(255, 230, 120, 60))
        zona.on_mouse_exit = lambda z=zona: setattr(z, "color", color.rgba32(255, 255, 255, 0))
        return {"grupo": grupo, "zona": zona, "malla": malla}

    def _construir_cartel(self):
        """Cartel 2D a la derecha: cliente, pedido, lo entregado, total, pago y el cambio que llevas."""
        ancho, alto = ANCHO_CARTEL, 0.4
        c = self.cartel = panel_tinta(self.raiz, ancho, alto, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX,
                                      position=(0.39, -0.03), z=-0.005)
        izq = -ancho / 2 + 0.02
        self.t_cliente = _texto(c, "", 12, estilo.COLOR_TEXTO_TENUE, (izq, 0.175), (-0.5, 0), z=-0.01)
        self.t_pide = _texto(c, "", 16, estilo.COLOR_ACENTO, (izq, 0.14), (-0.5, 0), negrita=True, z=-0.01)
        self.t_dado = _texto(c, "", 13, estilo.COLOR_TEXTO, (izq, 0.103), (-0.5, 0), z=-0.01)
        self.t_total = _texto(c, "", 16, estilo.COLOR_TEXTO, (izq, 0.06), (-0.5, 0), negrita=True, z=-0.01)
        self.t_paga = _texto(c, "", 16, estilo.COLOR_TEXTO, (izq, 0.025), (-0.5, 0), negrita=True, z=-0.01)
        self.t_cambio = _texto(c, "", 18, estilo.COLOR_ACENTO, (izq, -0.015), (-0.5, 0), negrita=True, z=-0.01)
        self.t_aviso = _texto(c, "", 14, estilo.COLOR_TEXTO, (0, -0.045), negrita=True, z=-0.01)
        self.boton_dar = BotonPrimario("Dar cambio (Enter)", al_clic=self._dar_cambio, ancho=0.3, alto=0.055,
                                       tamano_fuente_px=17, parent=c, position=(0, -0.095, -0.02))
        self.boton_quitar = BotonSecundario("Quitar el último (Retroceso)", al_clic=lambda: self._quitar(-1), ancho=0.3,
                                            alto=0.045, tamano_fuente_px=13, parent=c, position=(0, -0.147, -0.02))
        ayuda = _texto(c, "Productos: clic o 1-4.  Cambio: clic en la caja.  Esc: salir", 11, estilo.COLOR_TEXTO_TENUE,
                       (0, -0.178), z=-0.01)
        diseno_adaptable.ajustar_texto(ayuda, ancho - 0.03, escala_min=0.6)

    # -- Acciones --

    def entrada(self, key):
        teclas = {str(n): n - 1 for n in range(1, 5)} | {f"numpad {n}": n - 1 for n in range(1, 5)}
        if key in teclas:
            self._entregar(teclas[key])
            return True
        if key in ("enter", "return", "space"):
            self._dar_cambio()
            return True
        if key == "backspace":
            self._quitar(-1)
            return True
        return False

    def _entregar(self, indice):
        if self.turno.estado != mt.PEDIDO:
            return False
        ok = self._accion("entregar", indice)
        if ok:
            self._vuelo(indice)
            self._sonar("aterrizaje", 0.7, 1.5)
        else:
            self._rojo[indice] = 0.3
            self._sonar("clic_ui", 0.9, 0.55)
        return ok

    def _agregar(self, valor):
        if self._accion("agregar", valor):
            self._sonar("clic_ui", 0.6, 1.6 if not dinero.es_billete(valor) else 1.1)

    def _quitar(self, indice):
        if self._accion("quitar", indice):
            self._sonar("clic_ui", 0.5, 0.9)

    def _dar_cambio(self):
        if self.turno.estado == mt.CAMBIO:
            self._accion("dar_cambio")

    def _accion(self, nombre, *args):
        if self.al_accion is not None:
            return self.al_accion(nombre, *args)
        return getattr(self.turno, nombre)(*args)

    @staticmethod
    def _sonar(nombre, volumen, pitch):
        try:
            from frontend import audio
            audio.obtener().efecto(nombre, volumen, pitch)
        except Exception:                        # noqa: BLE001
            pass

    # -- Eventos del turno (los llama EscenaTrabajo) --

    def eventos(self, eventos, convivencia_bajo=False):
        """Pinta los eventos de TurnoMostrador.sacar_eventos(). `convivencia_bajo`: la escena ya bajó la convivencia por
        un cambio mal dado. Devuelve (texto, bueno) del último aviso o None."""
        aviso = None
        for tipo, _ in eventos:
            if tipo == mt.LLEGANDO:
                self._nuevo_cliente()
            elif tipo == mt.CAMBIO:
                self.caja.poner_pago(self.turno.pagado())
                self._gesto("dar")
                aviso = ("Te paga: mira cuánto y devuelve el cambio con la caja", True)
            elif tipo == mt.SALIENDO:
                self.caja.poner_pago([])
                self._gesto("recibir" if self.turno.reaccion == "contento" else None)
            elif tipo == "acierto":
                aviso = (f"Cambio correcto: {dinero.formatear(self.turno.cambio_esperado())}", True)
                self._sonar("aterrizaje", 0.9, 1.9)
            elif tipo == "error" and self.turno.reaccion == "enojado":
                aviso = (f"Cambio mal dado: era {dinero.formatear(self.turno.cambio_esperado())}. El cliente se enoja",
                         False)
                self._sonar("mision_fallo", 0.8, 1.0)
            elif tipo == "error":
                aviso = ("Ese producto no lo pidió (o ya tiene suficientes)", False)
            elif tipo == "castigo" and convivencia_bajo:
                aviso = ("El cliente se va enojado: baja la convivencia del barrio", False)
        return aviso

    def _nuevo_cliente(self):
        if self._cliente_actual is not None:
            self._cliente_actual.enabled = False
        self._cliente_actual = self._clientes[self.turno.cliente % len(self._clientes)] if self._clientes else None
        if self._cliente_actual is not None:
            self._cliente_actual.enabled = True
            self._cliente_actual.fijar_gesto(None)
        for e in self._entregados:
            destruir_arbol(e)
        self._entregados = []
        self._firma_entregado = None

    def _gesto(self, nombre):
        npc = self._cliente_actual
        if npc is not None and hasattr(npc, "fijar_gesto"):
            try:
                npc.fijar_gesto(nombre)
            except Exception:                    # noqa: BLE001
                pass

    # -- Cada fotograma --

    def _vuelo(self, indice):
        """El producto vuela del cajón al mostrador, delante del cliente."""
        n = len(self._entregados) + len(self._vuelos)
        destino = (ENTREGADOS[0] + 0.13 * (n % 5), ENTREGADOS[1], ENTREGADOS[2] + 0.1 * (n // 5))
        origen = (X_CAJONES[indice], ALTO_MOSTRADOR + 0.08, Z_CAJONES)
        e = Entity(parent=self.set, model=self._cajones[indice]["malla"].mesh(), shader=lit_with_shadows_shader,
                   position=origen)
        self._vuelos.append([e, origen, destino, 0.0])

    def animar(self, dt):
        self._t += dt
        npc = self._cliente_actual
        if npc is not None:
            x, z, rumbo, velocidad, temblor = pose_cliente(self.turno.estado, self.turno.tiempo_en_estado(),
                                                           self.turno.reaccion)
            npc.colocar(x, z)
            npc.fijar_rumbo(rumbo + (14 * math.sin(self._t * 22) if temblor else 0.0))
            npc.animar_caminar(velocidad, dt)
            npc.y = 0.06 * abs(math.sin(self._t * 11)) if temblor else 0.0
            # el globo acompaña al cliente también cuando se va
            self.globo.x = x + DX_GLOBO
        for vuelo in list(self._vuelos):
            e, origen, destino, t = vuelo
            vuelo[3] = t + dt
            k = min(1.0, vuelo[3] / DURACION_VUELO)
            e.position = tuple(origen[i] + (destino[i] - origen[i]) * k for i in range(3))
            e.y += 0.18 * 4 * k * (1 - k)
            if k >= 1.0:
                self._vuelos.remove(vuelo)
                self._entregados.append(e)
        for indice in list(self._rojo):
            self._rojo[indice] -= dt
            zona = self._cajones[indice]["zona"]
            zona.color = color.rgba32(230, 60, 50, 110) if self._rojo[indice] > 0 else color.rgba32(255, 255, 255, 0)
            if self._rojo[indice] <= 0:
                del self._rojo[indice]

    def refrescar(self):
        t = self.turno
        self._refrescar_aviso()
        texto, tono = texto_globo(t)
        self.globo.enabled = texto is not None
        if texto is not None and self._texto_globo.text != texto:
            self._texto_globo.text = _seguro(texto)
            self._fondo_globo.scale = (self._texto_globo.width * ESCALA_GLOBO + 0.08, 0.11)
            self._fondo_globo.color = rgb(tono)
        en_cambio = t.estado == mt.CAMBIO
        self.caja.activa = en_cambio
        self.caja.mostrar_total(t.total() if t.estado in (mt.CAMBIO, mt.SALIENDO) else None)
        firma = (t.cliente, t.estado, tuple(t.bandeja()), tuple(sorted(t.entregado().items())))
        if firma == self._firma:
            return
        self._firma = firma
        self.caja.poner_bandeja(t.bandeja())
        pedido, dado = t.pedido(), t.entregado()
        self._poner(self.t_cliente, f"CLIENTE {t.cliente + 1}")
        self._poner(self.t_pide, f"Pide: {t.pedido_texto()}" if t.estado != mt.LLEGANDO else "Llega un cliente...", 16)
        partes = [f"{p} {dado.get(p, 0)}/{n}" for p, n in pedido.items()]
        self._poner(self.t_dado, "Dado: " + " · ".join(partes) if t.estado == mt.PEDIDO else "", 13)
        con_pago = t.estado in (mt.CAMBIO, mt.SALIENDO)
        self._poner(self.t_total, f"Total: {dinero.formatear(t.total())}" if t.estado != mt.LLEGANDO else "")
        self._poner(self.t_paga, f"Te paga: {dinero.formatear(sum(t.pagado()))}" if con_pago else "")
        self._poner(self.t_cambio, f"Tu cambio: {dinero.formatear(t.suma_bandeja())}" if en_cambio else "")
        self.boton_dar.enabled = self.boton_quitar.enabled = en_cambio

    def _refrescar_aviso(self):
        """El aviso de la escena (bien / error), dentro del cartel en vez de abajo."""
        texto, ok, resta = getattr(self.escena, "_feedback", ("", True, 0.0))
        cadena = texto if resta > 0 else ""
        if self.t_aviso.text != cadena:
            self.t_aviso.text = _seguro(cadena)
            diseno_adaptable.ajustar_texto(self.t_aviso, ANCHO_CARTEL - 0.03, escala_base=escala_fuente(14),
                                           escala_min=0.75, max_lineas=2)
        self.t_aviso.color = rgb(estilo.ESTADO_EXITO if ok else estilo.ESTADO_ERROR)

    @staticmethod
    def _poner(texto, cadena, px=None):
        """Cambia el texto solo si cambió. Con `px` (su tamaño de letra) lo encoge para que quepa en el cartel."""
        if texto.text != cadena:
            texto.text = _seguro(cadena)
            if px is not None and cadena:
                diseno_adaptable.ajustar_texto(texto, ANCHO_CARTEL - 0.03, escala_base=escala_fuente(px), escala_min=0.6)

    # -- Cierre --

    def cerrar_3d(self):
        """Deshace todo lo 3D (luces, set con NPC y cámara) y devuelve el fondo 2D. Idempotente."""
        from frontend.piezas import encender_luz
        for luz in self._luces:
            try:
                encender_luz(luz, False)
            except Exception:                    # noqa: BLE001
                pass
        self._luces = []
        if self.set is not None:
            destruir_arbol(self.set)
            self.set = None
        self._clientes, self._cliente_actual, self._entregados, self._vuelos = [], None, [], []
        if self._camara is not None:
            self._camara.soltar()
            self._camara = None
        devolver_fondo(self._ocultos, self._bandas)
        self._ocultos, self._bandas = [], []

    def destruir(self):
        self.cerrar_3d()
        destruir_arbol(self.raiz)


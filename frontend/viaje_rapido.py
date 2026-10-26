# Viaje rápido del mapa grande (Ursina): el director de un viaje en mototáxi o en teleférico. Lo pide el menú de destinos
# (frontend/mototaxi.py, frontend/teleferico_vista.py) con `pedir(destino, jugador, perfil)`; las reglas (origen válido,
# destino de la lista fija, precio, cobro) son las de backend/logica/viaje_rapido.py, las mismas que usa el anfitrión.
#
#   Mototáxi:   cobrar -> fundido a negro con «Viajando en mototáxi…» (8-15 s según la distancia; Espacio lo salta) ->
#               con la pantalla negra se reubica al jugador (y se construye el barrio de alrededor) -> el fundido aclara.
#   Teleférico: cobrar -> fundido corto con «Subiendo al teleférico…» -> con la pantalla negra el jugador queda en la otra
#               estación y la cámara sube a una cabina del cable en el origen -> TRAYECTO ANIMADO (~40 s, cámara que gira
#               alrededor de la cabina sobre el barrio; flechas o A/D para mirar, Espacio para bajar ya) -> fundido corto y
#               la cámara vuelve al jugador. Mientras tanto el barrio se carga alrededor de la cabina (foco de los chunks).
#
# Online: no se mueve a nadie por su cuenta. Se manda `viaje{destino}`; el anfitrión valida el ORIGEN con su posición
# autorizada y reubica con ValidadorMovimiento.colocar(); su `viaje_ok{x,z,y}` (o `viaje_no{motivo}`) llega por
# flujo.tomar_eventos_viaje(). El cobro es local (online no sincroniza dinero): se cobra al pedir y se devuelve si el
# anfitrión rechaza o no contesta (si el ok llega tarde, el viaje se hace igual: el anfitrión ya lo concedió).
# Durante un viaje la escena está en modo «cinemática» (controles congelados, ratón libre, sin pausa).

import math
from dataclasses import dataclass

from ursina import Entity, Text, camera, color, held_keys, time

from backend.datos import teleferico as td
from backend.logica import viaje_rapido as vr
from frontend import camara_calculos as cc, estilo, geometria_mundo, viaje_calculos as vc
from frontend.componentes import escala_fuente, rgb
from frontend.teleferico_vista import Y_CENTRO_CABINA
from frontend.transicion import Transicion

SALIDA_S = 0.7               # s de fundido a negro al empezar
ENTRADA_S = 0.9              # s de fundido de vuelta
NEGRO_TELEFERICO_S = 1.6     # s de negro antes de subir a la cabina (el trayecto es la parte larga)
NEGRO_ATERRIZAJE_S = 0.25    # s de negro al bajar del teleférico
ESPERA_ANFITRION_S = 6.0     # s esperando viaje_ok / viaje_no antes de devolver el dinero
TEXTO_MOTO = "Viajando en mototáxi…"
TEXTO_TELEFERICO = "Subiendo al teleférico…"
TEXTO_AYUDA_NEGRO = "Espacio para saltar"
TEXTO_AYUDA_TRAYECTO = "Teleférico · flechas o A/D para mirar · Espacio para bajar"
Z_AYUDA = -103


@dataclass
class _Viaje:
    destino: str
    tipo: str
    x: float
    z: float
    y: float
    origen: tuple            # (x, z) de donde sale el jugador
    precio: int = 0
    gratis: bool = False     # un ok tardío: el dinero ya se devolvió


class ViajeRapido(Entity):
    """Director de los viajes rápidos de una EscenaMundo. Hijo de la escena: update()/input() solo corren con ella activa."""

    def __init__(self, escena, economia, transicion=None, **opciones):
        opciones.setdefault("parent", escena)
        super().__init__(**opciones)
        self.escena = escena
        self.economia = economia
        self.teleferico = None                 # TelefericoVista (la pone teleferico_vista.instalar)
        self.trans = transicion if transicion is not None else Transicion(SALIDA_S, ENTRADA_S, 0.0)
        self.fase = None                       # None | "esperando" | "fundido" | "trayecto" | "aterrizando"
        self._viaje = None
        self._perfil = None
        self._t_espera = 0.0
        self._t = 0.0
        self._reubicado = False
        self._saltar = False
        self._giro = 0.0
        self._incl = 0.0
        self._sube = True
        self._foco_xz = (0.0, 0.0)
        self._foco_previo = None
        self._ocultos = []
        self.ayuda = Text("", parent=camera.ui, origin=(0, 0), position=(0, -0.42, Z_AYUDA), scale=escala_fuente(18),
                          color=rgb(estilo.COLOR_TEXTO), enabled=False)
        self.ayuda.render_queue = 102
        self._texto_ayuda = None
        self.viajes_hechos = 0

    # Pone el texto de ayuda (con su fondo oscuro) solo si cambió.
    def _poner_ayuda(self, texto, visible):
        if texto != self._texto_ayuda:
            self._texto_ayuda = texto
            self.ayuda.text = texto
            self.ayuda.create_background(padding=(0.03, 0.015), radius=0.3, color=color.rgba32(10, 12, 20, 190))
        self.ayuda.enabled = bool(visible)

    # -- Consulta --

    def ocupado(self):
        return self.fase is not None

    def _cliente_online(self):
        escena = self.escena
        if getattr(escena, "online", None) is None:
            return None
        cliente = getattr(escena.flujo, "cliente", None)
        return cliente if callable(getattr(cliente, "enviar_viaje", None)) else None

    # -- Petición (desde el menú) --

    def pedir(self, destino, jugador, perfil):
        """(ok, mensaje). ok = el viaje arrancó (el menú se cierra); si no, el mensaje explica por qué."""
        if self.ocupado():
            return False, vc.TEXTO_OCUPADO
        mundo = self.escena._mundo
        res = vr.resolver_viaje(mundo, destino, jugador.x, jugador.z)
        if not res.ok:
            return False, vc.TEXTOS_MOTIVO.get(res.motivo, "No se puede viajar.")
        cobro = vr.cobrar_viaje(perfil, destino, res.precio)
        if not cobro.ok:
            return False, vc.MENSAJES_COBRO.get(cobro.codigo, cobro.mensaje)
        viaje = _Viaje(destino, res.tipo, res.x, res.z, res.y, (jugador.x, jugador.z), res.precio)
        self._viaje, self._perfil = viaje, perfil
        cliente = self._cliente_online()
        if cliente is None:
            self._arrancar(viaje)
            return True, ""
        if not cliente.enviar_viaje(destino):
            vr.reembolsar_viaje(perfil, destino, res.precio)
            self._viaje = self._perfil = None
            return False, vc.TEXTOS_MOTIVO["desconectado"]
        self.fase = "esperando"
        self._t_espera = 0.0
        return True, ""

    # -- Online: respuestas del anfitrión --

    def _procesar_eventos(self):
        flujo = self.escena.flujo
        tomar = getattr(flujo, "tomar_eventos_viaje", None)
        if not callable(tomar):
            return
        for ev in tomar():
            if ev.get("t") == "viaje_ok":
                self._ok_del_anfitrion(ev)
            elif ev.get("t") == "viaje_no":
                self._no_del_anfitrion(ev)

    def _ok_del_anfitrion(self, ev):
        destino = ev["destino"]
        if destino not in vr.DESTINOS or self.fase in ("fundido", "trayecto", "aterrizando"):
            return
        previo = self._viaje if self.fase == "esperando" else None
        origen = previo.origen if previo is not None else self._posicion_del_jugador()
        viaje = _Viaje(destino, vr.DESTINOS[destino].tipo, float(ev["x"]), float(ev["z"]), float(ev["y"]), origen,
                       previo.precio if previo is not None else 0, gratis=previo is None)
        self._viaje = viaje
        self._arrancar(viaje)

    def _no_del_anfitrion(self, ev):
        if self.fase != "esperando":
            return
        viaje = self._viaje
        if viaje is not None and self._perfil is not None:
            vr.reembolsar_viaje(self._perfil, viaje.destino, viaje.precio)
        self.fase = None
        self._viaje = self._perfil = None
        self.escena.hud.mostrar_aviso(vc.TEXTOS_MOTIVO.get(ev.get("motivo"), "No se pudo viajar."))

    def _posicion_del_jugador(self):
        j = self.escena.flujo.jugador_activo()
        return (j.x, j.z)

    # -- Arranque --

    def _arrancar(self, viaje):
        escena = self.escena
        self.economia.cerrar_modales()
        escena._cinematica = True
        escena._sincronizar_raton()
        self.fase = "fundido"
        self._reubicado = False
        self._saltar = False
        if viaje.tipo == vr.TIPO_TELEFERICO and self.teleferico is not None:
            negro, texto = NEGRO_TELEFERICO_S, TEXTO_TELEFERICO
        else:
            negro = vr.duracion_negro(math.hypot(viaje.x - viaje.origen[0], viaje.z - viaje.origen[1]))
            texto = TEXTO_MOTO
        self.trans.fundido.sostener = negro
        self.trans.ejecutar(lambda: self._en_negro(viaje), texto=texto)

    # Con la pantalla negra: mototáxi = reubicar; teleférico = reubicar y subir a la cabina.
    def _en_negro(self, viaje):
        if viaje.tipo == vr.TIPO_TELEFERICO and self.teleferico is not None:
            self._subir_a_la_cabina(viaje)
        else:
            self._reubicar(viaje.x, viaje.z, viaje.destino)
        self._reubicado = True
        self.viajes_hechos += 1

    def _reubicar(self, x, z, destino, construir=True):
        escena = self.escena
        flujo = escena.flujo
        jugador = flujo.jugador_activo()
        avatar = escena.avatar_de(jugador)
        flujo.actualizar_posicion(x, z)
        if avatar is not None:
            avatar.colocar(x, z)
        reiniciar = getattr(escena.controlador, "_reiniciar_vertical", None)
        if callable(reiniciar):
            reiniciar(jugador)
        if construir and getattr(escena, "_grande", False):
            escena.ciudad.preparar_anillo((x, z), con_barra=False)         # el barrio de alrededor, con la pantalla negra
        escena.camara.yaw = self._yaw_hacia(destino, x, z)
        escena.camara.colocar_ya()
        escena.refrescar()

    def _yaw_hacia(self, destino, x, z):
        lugar = vr.DESTINOS[destino].llegada["lugar"]
        try:
            px, pz = self.escena._mundo.punto_interaccion(lugar)
        except ValueError:
            return self.escena.camara.yaw
        if math.hypot(px - x, pz - z) < 0.5:
            return self.escena.camara.yaw
        return geometria_mundo.rumbo_de(px - x, pz - z)

    # -- Teleférico: subir, trayecto, bajar --

    def _subir_a_la_cabina(self, viaje):
        escena, tele = self.escena, self.teleferico
        self._sube = viaje.destino == "tele_alta"
        ox, oz = viaje.origen
        escena.camara.tomar_control()
        if getattr(escena, "_grande", False):
            escena.ciudad.preparar_anillo((ox, oz), con_barra=False)        # el barrio alrededor del origen (donde arranca la cabina)
            gestor = escena.ciudad.gestor
            self._foco_previo = gestor.fuente_foco
            self._foco_xz = (ox, oz)
            gestor.fuente_foco = lambda: self._foco_xz
        self._reubicar(viaje.x, viaje.z, viaje.destino, construir=False)    # el jugador ya queda en la estación de llegada
        escena.camara.tomar_control()                                        # refrescar()/colocar_ya no la sueltan, por si acaso
        tele.en_trayecto = True
        self._t, self._giro, self._incl = 0.0, 0.0, 0.0
        self._ocultar_hud()
        self._poner_ayuda(TEXTO_AYUDA_TRAYECTO, False)    # se muestra al aclarar el fundido (en avanzar)
        self._poner_camara_trayecto(0.0)
        self.fase = "trayecto_pendiente"

    def _u(self, t):
        a = td.avance(t)
        return a if self._sube else 1.0 - a

    def _poner_camara_trayecto(self, dt):
        tele = self.teleferico
        u = self._u(self._t)
        tele.colocar(tele.cabinas[0], u)
        tele.colocar(tele.cabinas[1], 1.0 - u)
        (x, y, z), rumbo = tele.posicion_de_cabina(u)
        heading = rumbo if self._sube else rumbo + 180.0
        if dt > 0:
            self._giro += (held_keys["left arrow"] + held_keys["a"] - held_keys["right arrow"] - held_keys["d"]) * vc.VEL_GIRO * dt
            self._incl += (held_keys["up arrow"] - held_keys["down arrow"]) * vc.VEL_INCLINAR * dt
        yaw, pitch, distancia = vc.camara_trayecto(self._t, heading, self._giro, self._incl)
        pivote = (x, y + Y_CENTRO_CABINA, z)
        camera.position = cc.posicion_orbital(pivote, yaw, pitch, distancia)
        camera.rotation = (pitch, yaw, 0)
        self._foco_xz = (x, z)

    def _aterrizar(self):
        self.fase = "aterrizando"
        self.ayuda.enabled = False
        self.trans.fundido.sostener = NEGRO_ATERRIZAJE_S
        self.trans.ejecutar(self._llegada, texto=None)

    # Con la pantalla negra tras el trayecto: todo vuelve a la normalidad con el jugador en la estación de llegada.
    def _llegada(self):
        escena, tele = self.escena, self.teleferico
        viaje = self._viaje
        tele.en_trayecto = False
        if getattr(escena, "_grande", False):
            gestor = escena.ciudad.gestor
            gestor.fuente_foco = self._foco_previo
            self._foco_previo = None
        self._restaurar_hud()
        escena.camara.soltar_control()
        if viaje is not None:
            self._reubicar(viaje.x, viaje.z, viaje.destino)

    def _ocultar_hud(self):
        hud = self.escena.hud
        self._ocultos = [(e, e.visible) for e in (hud.minimapa, hud.panel_turno, hud.telefono_ui)]
        for e, _ in self._ocultos:
            e.visible = False

    def _restaurar_hud(self):
        for e, previo in self._ocultos:
            e.visible = previo
        self._ocultos = []

    # -- Frame --

    def update(self):
        self.avanzar(time.dt)

    def avanzar(self, dt):
        """Un paso de `dt` segundos (los scripts lo llaman a mano con dt fijos)."""
        if self.escena.flujo is None:
            return
        self._procesar_eventos()
        fase = self.fase
        if fase is None:
            return
        if fase == "esperando":
            self._t_espera += dt
            if self._t_espera > ESPERA_ANFITRION_S:
                self._sin_respuesta()
            return
        if fase == "fundido":
            self._poner_ayuda(TEXTO_AYUDA_NEGRO, self._reubicado and self.trans.fundido.texto is not None)
            if not self.trans.ocupada:
                self._terminar()
            return
        if fase == "trayecto_pendiente":         # esperando a que el fundido de entrada aclare
            self.ayuda.enabled = not self.trans.ocupada
            if not self.trans.ocupada:
                self.fase = "trayecto"
            self._poner_camara_trayecto(0.0)
            return
        if fase == "trayecto":
            self.ayuda.enabled = True
            self._t += dt
            self._poner_camara_trayecto(dt)
            if self._t >= td.TRAYECTO_S or self._saltar:
                self._aterrizar()
            return
        if fase == "aterrizando" and not self.trans.ocupada:
            self._terminar()

    def _sin_respuesta(self):
        viaje = self._viaje
        if viaje is not None and self._perfil is not None:
            vr.reembolsar_viaje(self._perfil, viaje.destino, viaje.precio)
        self.fase = None
        self._viaje = self._perfil = None
        self.escena.hud.mostrar_aviso(vc.TEXTO_SIN_RESPUESTA)

    def _terminar(self):
        escena = self.escena
        self.fase = None
        self._viaje = self._perfil = None
        self.ayuda.enabled = False
        escena._cinematica = False
        escena._sincronizar_raton()

    def input(self, key):
        if key != "space" or self.fase is None:
            return
        if self.fase == "fundido" and self._reubicado and self.trans.ocupada:
            self.trans.saltar()
        elif self.fase in ("trayecto", "trayecto_pendiente"):
            self._saltar = True
            if self.fase == "trayecto_pendiente":
                self.trans.saltar()
                self.fase = "trayecto"

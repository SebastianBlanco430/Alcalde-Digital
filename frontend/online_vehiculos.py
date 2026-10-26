# Vehículos en el modo ONLINE (T9): envuelve la IntegracionVehiculos local (frontend/vehiculo_mundo.py) SIN
# reescribirla. La escena la crea IntegracionOnline solo si VEHICULOS_ONLINE y hay un FlujoEnLinea.
#
# Qué cambia respecto al juego local:
#   - E cerca de un vehículo libre: NO se monta al instante; se pide al anfitrión (`montar{veh}`) y se espera su
#     `monta_ok` (se monta entonces) o `monta_no` (se queda a pie y un aviso dice por qué). Si no contesta en
#     TIMEOUT_MONTAR s se da por perdida (y si el ok llega tarde se devuelve el vehículo con `bajar`).
#   - Un vehículo ocupado por otro jugador (o con una petición mía en vuelo) no muestra el aviso «E: montar»: se
#     filtra en MundoVehiculos.vehiculo_cercano (atributo de instancia, se quita al cerrar).
#   - Al bajar (E, minijuego, cinemática, edificio, reconexión) se avisa al anfitrión con `bajar`; una bajada
#     forzosa del anfitrión (`desmontado`) baja localmente sin avisar de vuelta.
#   - La fuente de posición del bucle de red manda la posición/rumbo/velocidad del VEHÍCULO mientras se conduce
#     (el avatar está oculto y quieto): se envuelve nucleo.fuente_pos, así funciona venga de donde venga.
#   - Corrección del anfitrión al local que conduce: se difumina (TAU 0,18 s) y, si es grande (> 6 m), coloca el
#     vehículo de golpe pero NUNCA lo baja.
#   - Los vehículos aparcados se colocan donde diga el snapshot (`veh`); los conducidos por REMOTOS se dibujan como
#     el vehículo con su piloto (piloto_glb.crear_piloto_skin: la skin del jugador) con lean, manubrio, ruedas y pedales derivados de
#     la velocidad (online_vehiculos_calculos.AnimadorRemoto). El vehículo número i es el mismo en todos los equipos
#     (puntos_de_aparcamiento es determinista y el mundo se verifica por huella).

from ursina import destroy

from backend.logica.roles import ROLES
from backend.red import protocolo
from backend.red.saneado import sanear_texto_visible
from frontend import online_vehiculos_calculos as ovc
from frontend import vehiculo_calculos as vc
from frontend.componentes import destruir_arbol
from frontend.rostro_calculos import ROSTRO_PROCEDURAL_POR_ROL
from frontend.piloto_glb import crear_piloto_skin

TEXTOS_RECHAZO = {
    "ocupado": "Ese vehículo ya está ocupado",
    "lejos": "Estás demasiado lejos del vehículo",
    "ya_montado": "Ya vas montado",
    "no_existe": "Ese vehículo no existe",
    "fase": "No se puede montar ahora",
    "dentro": "No se puede montar dentro de un edificio",
    "desactivado": "Los vehículos están desactivados en esta sala",
    "desconectado": "Sin conexión con el anfitrión",
    "bajada": "El anfitrión te bajó del vehículo",
}
TEXTO_SIN_RESPUESTA = "El anfitrión no contestó: no se pudo montar"


class _Remoto:
    # Un jugador remoto montado: su vehículo (índice), el piloto sentado y el animador.
    def __init__(self, vid, vehiculo, piloto, animador):
        self.vid = vid
        self.vehiculo = vehiculo
        self.piloto = piloto
        self.animador = animador


class VehiculosOnline:

    # escena: EscenaMundo con .vehiculos (IntegracionVehiculos). flujo: FlujoEnLinea. avisar: callable(texto).
    # obtener_bucle: callable() -> BucleRed | None. reloj: callable() -> s.
    def __init__(self, escena, flujo, avisar=None, obtener_bucle=None, reloj=None):
        import time as time_real
        self.escena = escena
        self.integ = escena.vehiculos
        self.mundo = self.integ.mundo
        self.mundo.recortar(protocolo.N_VEHICULOS_MAX)     # tope del protocolo v4: 24 (el grande los usa todos; el chico tiene 8)
        self.flujo = flujo
        self._avisar = avisar or (lambda texto: None)
        self._obtener_bucle = obtener_bucle or (lambda: None)
        self._reloj = reloj or time_real.monotonic
        self._pendiente = None            # (indice, instante) de un montar sin contestar
        self._confirmado = False          # el anfitrión me concedió el vehículo que conduzco
        self._ocupados = {}               # id vehículo -> id piloto remoto
        self._remotos = {}                # id jugador remoto -> _Remoto
        self._vistos = {}                 # id vehículo -> (x, z, r) con que se dibujó aparcado
        self._vid_propio = None           # índice del vehículo que conduzco
        self._bajado = {}                 # id vehículo -> instante en que lo dejé (se ignora el snapshot un rato)
        self._objetivo = None             # (x, z): corrección del anfitrión por aplicar al vehículo conducido
        self._fuente_original = None
        self._fuente_envuelta = None
        self._activo = True
        # Ganchos (se quitan en cerrar()).
        self.mundo.vehiculo_cercano = self._cercano_libre
        self._gancho_original = escena.controlador.gancho_e
        escena.controlador.gancho_e = self.alternar_e
        self.integ.tipo_confirmado = None

    # -- Consultas --
    @property
    def conduciendo(self):
        return self.integ.conduciendo

    @property
    def tipo_confirmado(self):
        return getattr(self.integ, "tipo_confirmado", None)

    # Vehículo (objeto VehiculoAparcado) libre más cercano: sin los ocupados por remotos ni el de mi petición en vuelo.
    def _cercano_libre(self, x, z):
        if self.mundo.conduciendo:
            return None
        from frontend import vehiculo_calculos as vc
        pendiente = None if self._pendiente is None else self._pendiente[0]
        libres = [v for i, v in enumerate(self.mundo.vehiculos) if i not in self._ocupados and i != pendiente]
        i = vc.indice_cercano([(v.estado.x, v.estado.z) for v in libres], x, z)
        return None if i is None else libres[i]

    def dibuja_a(self, id_jugador):
        return id_jugador in self._remotos

    # -- Tecla E --
    def alternar_e(self, puede_mision):
        flujo = self.integ._flujo_activo()
        if flujo is None:
            return False
        activo = flujo.jugador_activo()
        if self.conduciendo:
            self._bajar_local(avisar=True)
            return True
        if puede_mision or activo.telefono.bloquea_movimiento():
            return False
        if self._pendiente is not None:
            return True                                   # esperando al anfitrión: la E no hace nada más
        cercano = self._cercano_libre(activo.x, activo.z)
        if cercano is None:
            return False
        enviar = getattr(flujo.cliente, "enviar_montar", None)
        if not callable(enviar):
            return False
        indice = self.mundo.vehiculos.index(cercano)
        if enviar(indice):
            self._pendiente = (indice, self._reloj())
        return True

    # -- Frame --
    def actualizar(self, dt):
        if not self._activo:
            return
        flujo = self.flujo
        for ev in flujo.tomar_eventos_vehiculo():
            self._evento(ev)
        if self._pendiente is not None and self._reloj() - self._pendiente[1] > ovc.TIMEOUT_MONTAR:
            self._pendiente = None
            self._avisar(TEXTO_SIN_RESPUESTA)
        if self._confirmado and not self.conduciendo:
            self._dejado()
            self._confirmado = False                      # la integración local bajó sola (minijuego, cinemática...)
            self.integ.tipo_confirmado = None
            self._enviar_bajar()
        if self._confirmado and getattr(flujo, "reconectando", False):
            self._bajar_local(avisar=False)               # sin conexión el anfitrión ya te liberó
        self._envolver_fuente()
        self._sincronizar(dt)
        self._aplicar_objetivo(dt)

    def _evento(self, ev):
        t = ev.get("t")
        if t == "monta_ok":
            self._monta_ok(ev["veh"])
        elif t == "monta_no":
            self._pendiente = None
            self._avisar(TEXTOS_RECHAZO.get(ev.get("motivo"), "No se pudo montar"))
        elif t == "desmontado":
            if self.conduciendo:
                self._bajar_local(avisar=False)
                self._avisar(TEXTOS_RECHAZO.get(ev.get("motivo"), "Te bajaron del vehículo"))

    def _monta_ok(self, indice):
        pendiente, self._pendiente = self._pendiente, None
        integ, flujo = self.integ, self.flujo
        puede = (pendiente is not None and pendiente[0] == indice and 0 <= indice < len(self.mundo.vehiculos)
                 and not self.conduciendo and integ._flujo_activo() is not None and not self.escena._cinematica)
        if puede:
            from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
            puede = flujo.estado_mision() not in (EN_MINIJUEGO, COMPLETADA)
        if not puede:
            self._enviar_bajar()                          # concedido pero ya no lo quiero: se devuelve
            return
        vehiculo = self.mundo.vehiculos[indice]
        self._confirmado = True
        self._vid_propio = indice
        integ.tipo_confirmado = vehiculo.tipo
        integ.montar(vehiculo, flujo.jugador)
        self._objetivo = None

    def _dejado(self):
        if self._vid_propio is not None:
            self._bajado[self._vid_propio] = self._reloj()
            self._vid_propio = None

    def _bajar_local(self, avisar):
        self._dejado()
        self._confirmado = False
        self.integ.tipo_confirmado = None
        self._objetivo = None
        self.integ.bajar()
        if avisar:
            self._enviar_bajar()

    def _enviar_bajar(self):
        enviar = getattr(self.flujo.cliente, "enviar_bajar", None)
        if callable(enviar):
            enviar()

    # -- Posición enviada --
    def _envolver_fuente(self):
        bucle = self._obtener_bucle()
        nucleo = getattr(bucle, "nucleo", None)
        if nucleo is None or nucleo.fuente_pos is None or nucleo.fuente_pos is self._fuente_envuelta:
            return
        original = nucleo.fuente_pos

        def fuente():
            datos = original()
            c = self.mundo.conducido
            if datos is None or c is None or not self._confirmado:
                return datos
            e = c.estado
            mundo = self.escena._mundo
            suelo = getattr(mundo, "altura_con_escaleras", None) or getattr(mundo, "altura", None)
            y = float(suelo(e.x, e.z)) if suelo is not None else float(datos[2])
            return ovc.datos_con_vehiculo(datos, e.x, e.z, y, e.rumbo, e.velocidad, c.tipo,
                                          caballito=e.caballito > vc.ANGULO_MINIMO_CABALLITO)
        self._fuente_original = original
        self._fuente_envuelta = fuente
        nucleo.fuente_pos = fuente

    # -- Corrección del anfitrión al que conduce --
    def recibir_correccion(self, x, z):
        if self.conduciendo:
            self._objetivo = (x, z)

    def _aplicar_objetivo(self, dt):
        if self._objetivo is None or not self.conduciendo:
            self._objetivo = None
            return
        e = self.mundo.conducido.estado
        ox, oz = self._objetivo
        nx, nz, brusca = ovc.paso_correccion(e.x, e.z, ox, oz, dt)
        e.x, e.z = nx, nz
        if brusca:
            e.velocidad *= ovc.FACTOR_VELOCIDAD_BRUSCA
            self._objetivo = None
        elif abs(ox - nx) < 0.02 and abs(oz - nz) < 0.02:
            self._objetivo = None

    # -- Vehículos aparcados y remotos montados --
    def _sincronizar(self, dt):
        flujo = self.flujo
        lista = flujo.vehiculos_snap
        self._ocupados = ovc.ocupados_por_remotos(lista, flujo.tu_id)
        altura = self.escena._mundo.altura
        vehiculos = self.mundo.vehiculos
        for entrada in lista:
            vid = entrada["i"]
            if vid >= len(vehiculos) or vehiculos[vid].tipo != entrada["k"]:
                continue                                   # no coincide con lo local: se ignora (no se puede cambiar de modelo)
            v = vehiculos[vid]
            if v is self.mundo.conducido or vid in self._ocupados:
                continue
            if self._reloj() - self._bajado.get(vid, -1e9) < ovc.IGNORAR_SNAP_TRAS_BAJAR:
                continue                                   # snapshots viejos: aún dicen que sigo montado
            marca = (entrada["x"], entrada["z"], entrada["r"])
            if self._vistos.get(vid) != marca:
                self._vistos[vid] = marca
                v.estado.x, v.estado.z, v.estado.rumbo = marca[0], marca[1], marca[2]
                v.estado.velocidad = 0.0
                v.modelo.aplicar_estado(v.estado, 0.0, altura)
                v.modelo.aparcar()
        activos = set()
        for vid, pid in self._ocupados.items():
            if vid >= len(vehiculos) or vehiculos[vid].tipo != self._tipo_en_lista(lista, vid):
                continue
            activos.add(pid)
            self._dibujar_remoto(pid, vid, dt)
        for pid in [p for p in self._remotos if p not in activos]:
            self._soltar(pid)

    @staticmethod
    def _tipo_en_lista(lista, vid):
        for entrada in lista:
            if entrada["i"] == vid:
                return entrada["k"]
        return None

    def _dibujar_remoto(self, pid, vid, dt):
        flujo = self.flujo
        remoto = self._remotos.get(pid)
        if remoto is not None and remoto.vid != vid:
            self._soltar(pid)
            remoto = None
        if remoto is None:
            remoto = self._subir(pid, vid)
            if remoto is None:
                return
        muestra = flujo.muestra_de(pid)
        caballito = False
        if muestra is not None:
            x, z, rumbo, vel = muestra.x, muestra.z, muestra.r, muestra.v
            caballito = bool(muestra.f & ovc.BIT_CABALLITO)
        else:
            entrada = next(e for e in flujo.vehiculos_snap if e["i"] == vid)
            x, z, rumbo, vel = entrada["x"], entrada["z"], entrada["r"], 0.0
        estado = remoto.animador.avanzar(x, z, rumbo, vel, dt, caballito)
        remoto.vehiculo.modelo.aplicar_estado(estado, min(dt, 0.05), self.escena._mundo.altura,
                                              remoto.animador.acelerando)

    def _subir(self, pid, vid):
        flujo = self.flujo
        jugador = flujo.jugador_por_id(pid)
        if jugador is None:
            return None
        vehiculo = self.mundo.vehiculos[vid]
        rasgos = jugador.rol if jugador.rol in ROSTRO_PROCEDURAL_POR_ROL else "ciudadano"
        avatar = self.escena.avatares.get(jugador.nombre)
        piloto = crear_piloto_skin(sanear_texto_visible(jugador.nombre), ROLES[jugador.rol].color, rasgos, avatar, jugador.rol)
        vehiculo.modelo.montar_piloto(piloto)
        if avatar is not None:
            avatar.enabled = False
        animador = ovc.AnimadorRemoto(vehiculo.tipo, self.escena._mundo.altura)
        animador.colocar(vehiculo.estado.x, vehiculo.estado.z, vehiculo.estado.rumbo)
        remoto = _Remoto(vid, vehiculo, piloto, animador)
        self._remotos[pid] = remoto
        return remoto

    def _soltar(self, pid):
        remoto = self._remotos.pop(pid, None)
        if remoto is None:
            return
        modelo = remoto.vehiculo.modelo
        piloto = modelo.bajar_piloto()
        if piloto is not None:
            piloto.parent = None
            destruir_arbol(piloto)                           # con sus hijos (aro, sombra, etiqueta): sin fugas
        e = remoto.animador.estado
        remoto.vehiculo.estado.x, remoto.vehiculo.estado.z, remoto.vehiculo.estado.rumbo = e.x, e.z, e.rumbo
        remoto.vehiculo.estado.velocidad = 0.0
        modelo.aplicar_estado(remoto.vehiculo.estado, 0.0, self.escena._mundo.altura)
        modelo.aparcar()
        self._vistos.pop(remoto.vid, None)
        jugador = self.flujo.jugador_por_id(pid)
        avatar = None if jugador is None else self.escena.avatares.get(jugador.nombre)
        if avatar is not None:
            avatar.enabled = True

    # -- Cierre --
    def cerrar(self):
        if not self._activo:
            return
        self._activo = False
        for pid in list(self._remotos):
            self._soltar(pid)
        if self.conduciendo:
            self._bajar_local(avisar=True)
        try:
            del self.mundo.vehiculo_cercano                 # vuelve al método de la clase
        except AttributeError:
            pass
        if self.escena.controlador.gancho_e == self.alternar_e:
            self.escena.controlador.gancho_e = self._gancho_original
        bucle = self._obtener_bucle()
        nucleo = getattr(bucle, "nucleo", None)
        if nucleo is not None and nucleo.fuente_pos is self._fuente_envuelta and self._fuente_original is not None:
            nucleo.fuente_pos = self._fuente_original
        self.integ.tipo_confirmado = None

# Vehículos en el mundo: aparcados (unos 8, deterministas, en calles anchas y plazas), aviso de interacción y el
# ControladorVehiculo que conduce al montarse. Pegamento entre vehiculo_calculos (dinámica pura) y vehiculo_modelo
# (Entity). NO toca controlador_jugador, escena_mundo ni hud: la fase de integración los conecta con esta API.
#
# Controles (decisión): RELATIVOS AL VEHÍCULO. W/S = acelerar/frenar (S parado = marcha atrás), A/D = dirección,
# Shift (mantenido) = caballito, Ctrl = turbo, Espacio = freno de mano (derrape; NO salta). Decisión 2026-10-23:
# Shift era el turbo; el caballito lo necesitaba (es la tecla «de truco» y la misma con que se corre a pie) y el
# turbo pasó a Ctrl, que el juego no usaba. Con vc.CABALLITOS = False, Shift vuelve a ser el turbo y no hay
# caballito. Con la cámara orbital el movimiento relativo a la
# cámara (como al caminar) obliga a dar vueltas con inercia y la bici se "retuerce"; el relativo al vehículo
# se comporta como una bici/moto y la cámara se coloca sola detrás (seguir_rumbo_camara) si no se toca el ratón.
#
# API para la integración (ver el informe): MundoVehiculos(mundo, parent) -> .vehiculo_cercano(x, z),
# .aviso(x, z), .montar(vehiculo, avatar|None, nombre, color_rol, rasgos), .avanzar(h, v, dt, turbo, freno_mano,
# camara=None) -> (x, z), .desmontar() -> (x, z), .conduciendo, .efectos_camara().

import math

from ursina import Entity, camera, color, held_keys, mouse, time

from frontend import geometria_mundo
from frontend import vehiculo_calculos as vc
from frontend.piezas import silenciar
from frontend.piloto_glb import crear_piloto_skin
from frontend.vehiculo_modelo import ELEVACION_SUELO, VehiculoModelo

TEXTO_MONTAR = "E: montar {nombre}"
TEXTO_BAJAR = "E: bajar de la {nombre}"
SEGUNDOS_RATON = 1.5           # tras mover el ratón la cámara no se recoloca sola durante este tiempo


# Indicador flotante sobre un vehículo (rombo amarillo que sube y baja y gira): marca el que se puede montar.
class MarcadorAviso(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.rombo = Entity(parent=self, model="cube", scale=0.22, rotation=(45, 0, 45), color=color.rgb32(255, 220, 60),
                            shader=None)
        silenciar(self.rombo)
        self.enabled = False
        self._t = 0.0

    def poner(self, vehiculo):
        if vehiculo is None:
            self.enabled = False
            return
        self.enabled = True
        self.position = (vehiculo.x, vehiculo.y + 1.7, vehiculo.z)

    def update(self):
        if self.enabled:
            self._t += time.dt
            self.rombo.y = math.sin(self._t * 3.0) * 0.08
            self.rombo.rotation_y = self._t * 90.0


class VehiculoAparcado:
    # Un vehículo aparcado o conducido: su modelo y su estado.
    def __init__(self, modelo, estado):
        self.modelo = modelo
        self.estado = estado
        self.perfil = modelo.perfil

    @property
    def tipo(self):
        return self.modelo.tipo


class MundoVehiculos(Entity):

    def __init__(self, mundo, n=8, semilla=7, **opciones):
        super().__init__(**opciones)
        self.mundo = mundo
        self.vehiculos = []
        self.conducido = None
        self.piloto = None
        self.avatar = None               # avatar original oculto mientras se conduce
        self._t_raton = 99.0
        self.marcador = MarcadorAviso(parent=self)
        self._cercano = None
        self.acelerando = False
        self._reutilizado = False
        for p in vc.puntos_de_aparcamiento(mundo, n=n, semilla=semilla):
            self.colocar(p)

    def colocar(self, aparcado):
        modelo = VehiculoModelo(aparcado.tipo, aparcado.indice, parent=self)
        estado = vc.estado_inicial(aparcado.x, aparcado.z, aparcado.rumbo)
        modelo.aplicar_estado(estado, 0.0, self.mundo.altura)
        modelo.aparcar()
        v = VehiculoAparcado(modelo, estado)
        self.vehiculos.append(v)
        return v

    @property
    def conduciendo(self):
        return self.conducido is not None

    # Vehículo aparcado al alcance (el más cercano a menos de RADIO_AVISO) o None. Mientras se conduce, no hay.
    def vehiculo_cercano(self, x, z):
        if self.conduciendo:
            return None
        libres = [v for v in self.vehiculos]
        i = vc.indice_cercano([(v.estado.x, v.estado.z) for v in libres], x, z)
        return None if i is None else libres[i]

    # Texto del aviso para el HUD ("E: montar bicicleta") o, conduciendo, "E: bajar de la moto"; None si no aplica.
    # Actualiza además el rombo flotante sobre el vehículo.
    def aviso(self, x, z):
        if self.conduciendo:
            self.marcador.poner(None)
            return TEXTO_BAJAR.format(nombre=self.conducido.perfil.nombre)
        cercano = self.vehiculo_cercano(x, z)
        if cercano is not self._cercano:
            self._cercano = cercano
        self.marcador.poner(cercano.modelo if cercano is not None else None)
        return None if cercano is None else TEXTO_MONTAR.format(nombre=cercano.perfil.nombre)

    # Monta: `avatar` (Personaje procedural activo) pasa a ser el piloto; si es nulo o es un modelo .glb (sin
    # pivotes) se crea otra copia del MISMO modelo (piloto_glb.crear_piloto_skin; con SKIN_EN_VEHICULO = False o si
    # falla, un maniquí articulado con el color del rol). El avatar solo se oculta. Devuelve el vehículo.
    def montar(self, vehiculo, avatar=None, nombre="Piloto", color_rol=(120, 120, 120), rasgos="ciudadano", reutilizar=False,
               rol=None):
        if self.conduciendo:
            return self.conducido
        self.avatar = avatar
        if reutilizar and avatar is not None and getattr(avatar, "pivotes", None):
            self.piloto = avatar
            self._reutilizado = True
        else:
            self.piloto = crear_piloto_skin(nombre, color_rol, rasgos, avatar, rol)
            self._reutilizado = False
            if avatar is not None:
                avatar.hide()
        vehiculo.modelo.montar_piloto(self.piloto)
        vehiculo.estado.velocidad = 0.0
        vehiculo.estado.inclinacion = vehiculo.modelo.inclinable.rotation_z * math.pi / 180
        self.conducido = vehiculo
        self.marcador.poner(None)
        return vehiculo

    # Baja: devuelve la posición (x, z) donde queda el piloto a pie (junto al vehículo, en suelo transitable).
    # El vehículo queda aparcado donde está; el maniquí se destruye y el avatar original reaparece.
    def desmontar(self):
        v = self.conducido
        if v is None:
            return None
        v.estado.velocidad = 0.0
        x, z = vc.punto_para_bajar(self.mundo, v.estado.x, v.estado.z, v.estado.rumbo)
        piloto = v.modelo.bajar_piloto()
        if piloto is not None and not self._reutilizado:
            piloto.parent = None
            from frontend.componentes import destruir_arbol      # con sus hijos (aro, sombra, etiqueta): sin fugas
            destruir_arbol(piloto)
        elif piloto is not None:
            piloto.parent = self.parent
        if self.avatar is not None:
            self.avatar.show()
        v.estado.volante = 0.0
        v.modelo.aplicar_estado(v.estado, 0.0, self.mundo.altura)
        v.modelo.aparcar()
        self.conducido = None
        self.piloto = None
        self.avatar = None
        return (x, z)

    # Un paso de conducción con la entrada (h, v) en [-1, 1]. Devuelve (x, z) del vehículo; actualiza el modelo.
    # `camara` (opcional): CamaraTerceraPersona; se le recoloca el yaw detrás del vehículo y, si tiene los atributos
    # `fov_extra` / `distancia_extra` / `altura_extra`, se le pasan los efectos de velocidad (ver informe).
    def avanzar(self, h, v, dt, turbo=False, freno_mano=False, camara=None, caballito=False):
        c = self.conducido
        if c is None:
            return None
        entrada = vc.EntradaVehiculo(acelerar=v, direccion=h, turbo=turbo, freno_mano=freno_mano, caballito=caballito)
        vc.paso_vehiculo(c.estado, self.mundo, entrada, c.perfil, dt)
        self.acelerando = v > 0.05
        c.modelo.aplicar_estado(c.estado, min(dt, vc.DT_MAXIMO), self.mundo.altura, self.acelerando)
        if camara is not None:
            self._camara(camara, c, dt)
        return (c.estado.x, c.estado.z)

    def _camara(self, camara, c, dt):
        if mouse.velocity[0] or mouse.velocity[1]:
            self._t_raton = 0.0
        else:
            self._t_raton += dt
        camara.yaw = vc.seguir_rumbo_camara(camara.yaw, c.estado.rumbo, c.estado.velocidad, c.perfil, dt,
                                            raton_activo=self._t_raton < SEGUNDOS_RATON)
        self._poner_efectos(camara, self.efectos_camara(), dt)

    # Pone los efectos en la cámara suavizados (la cámara se abre en ~0.4 s, sin tirones).
    def _poner_efectos(self, camara, meta, dt):
        k = 1.0 - math.exp(-3.5 * dt)
        for atributo, valor in zip(("distancia_extra", "fov_extra", "altura_extra"), meta):
            if hasattr(camara, atributo):
                actual = getattr(camara, atributo)
                setattr(camara, atributo, actual + (valor - actual) * k)

    # A pie: los efectos vuelven a 0 con suavidad (se llama cada frame mientras no se conduce).
    def relajar_camara(self, camara, dt):
        self._poner_efectos(camara, (0.0, 0.0, 0.0), dt)

    # (metros extra de distancia, grados extra de FOV, metros extra de altura) de la cámara; ceros a pie.
    def efectos_camara(self):
        if self.conducido is None:
            return (0.0, 0.0, 0.0)
        estado = self.conducido.estado
        return vc.efectos_de_camara(estado.velocidad, self.conducido.perfil, estado.caballito)

    def posicion(self):
        c = self.conducido
        return None if c is None else (c.estado.x, c.estado.z)

    def velocidad(self):
        return 0.0 if self.conducido is None else self.conducido.estado.velocidad

    # Lee el teclado (WASD/flechas, Shift, Ctrl, Espacio) y conduce. Para quien quiera usar el controlador solo.
    def avanzar_con_teclado(self, camara=None):
        h, v = geometria_mundo.ejes_de_teclas(held_keys)
        turbo, caballito = teclas_turbo_caballito(bool(held_keys["left shift"] or held_keys["right shift"]))
        return self.avanzar(h, v, time.dt, turbo, bool(held_keys["space"]), camara, caballito)


# (turbo, caballito) según la tecla Shift (`shift`) y Ctrl (se lee aquí). Con vc.CABALLITOS: Shift = caballito y
# Ctrl = turbo; sin él, Shift = turbo (lo de antes).
def teclas_turbo_caballito(shift):
    if not vc.CABALLITOS:
        return shift, False
    return bool(held_keys["left control"] or held_keys["right control"]), shift



# Integración con la escena del mundo (fase 2): conecta MundoVehiculos con ControladorJugador (gancho `modo_vehiculo`
# y `gancho_e`), la cámara y el HUD. Se crea en EscenaMundo solo si VEHICULOS está activo.
#   - actualizar(dt): aviso «E: montar ...», baja solo si hay minijuego, cinemática, otro turno o fin de partida.
#   - alternar_e(puede_mision): la E monta (si no hay una misión que atender) o baja (siempre).
#   - avanzar(controlador, h, v, dt, correr): lo llama ControladorJugador.avanzar mientras se conduce.
class IntegracionVehiculos:

    def __init__(self, escena, n=8):
        self.escena = escena
        self.mundo = MundoVehiculos(escena._mundo, n=n, parent=escena)
        self.jugador = None
        self._texto = None
        self.escena.controlador.gancho_e = self.alternar_e

    @property
    def conduciendo(self):
        return self.mundo.conduciendo

    def _flujo_activo(self):
        flujo = self.escena.flujo
        return flujo if flujo is not None and not flujo.partida_terminada() else None

    # Aviso (cada frame) y bajada forzosa.
    def actualizar(self, dt):
        flujo = self._flujo_activo()
        camara = self.escena.camara
        if self.conduciendo:
            from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
            if (flujo is None or flujo.jugador_activo() is not self.jugador or self.escena._cinematica
                    or flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA)):
                self.bajar()
                return
        else:
            self.mundo.relajar_camara(camara, dt)
        texto = None
        if flujo is not None and not self.escena.en_pausa and not self.escena._cinematica:
            activo = flujo.jugador_activo()
            if not activo.telefono.bloquea_movimiento():
                pos = (activo.x, activo.z)
                texto = self.mundo.aviso(*pos)
                if texto is not None and not self.conduciendo and flujo.puede_interactuar():
                    texto = None                     # un destino a la mano manda: su aviso es el de siempre
        if texto != self._texto:
            self._texto = texto
            hud = self.escena.hud
            if texto:
                hud.mostrar_aviso(texto)
            else:
                hud.ocultar_aviso()

    # Tecla E (gancho del controlador). Devuelve True si la consumió.
    def alternar_e(self, puede_mision):
        flujo = self._flujo_activo()
        if flujo is None:
            return False
        activo = flujo.jugador_activo()
        if self.conduciendo:
            self.bajar()
            return True
        if puede_mision or activo.telefono.bloquea_movimiento():
            return False
        cercano = self.mundo.vehiculo_cercano(activo.x, activo.z)
        if cercano is None:
            return False
        self.montar(cercano, activo)
        return True

    def montar(self, vehiculo, jugador):
        from frontend.rostro_calculos import ROSTRO_PROCEDURAL_POR_ROL
        from backend.logica.roles import ROLES
        avatar = self.escena.avatar_de(jugador)
        rasgos = jugador.rol if jugador.rol in ROSTRO_PROCEDURAL_POR_ROL else "ciudadano"
        self.jugador = jugador
        self.mundo.montar(vehiculo, avatar, jugador.nombre, ROLES[jugador.rol].color, rasgos, rol=jugador.rol)
        # Se monta con el vehículo mirando al rumbo en que estaba aparcado; el avatar sigue donde está (oculto).
        jugador.x, jugador.z = vehiculo.estado.x, vehiculo.estado.z
        # Si se monta en pleno salto, el estado vertical y la sombra vuelven al suelo (sin destello al bajar).
        self.escena.controlador._reiniciar_vertical(jugador)
        self.escena.controlador._poner_sombra_en_el_suelo(avatar, 0)
        self.escena.controlador.modo_vehiculo = self
        self.escena.camara.ignorar = list(self.escena.camara.ignorar)
        self._texto = None

    def bajar(self):
        if not self.conduciendo:
            return
        jugador = self.jugador
        pos = self.mundo.desmontar()
        self.escena.controlador.modo_vehiculo = None
        self.jugador = None
        self._texto = None
        if pos is not None and jugador is not None:
            flujo = self.escena.flujo
            if flujo is not None:
                jugador.x, jugador.z = pos
                flujo.actualizar_posicion(*pos)
            avatar = self.escena.avatar_de(jugador)
            if avatar is not None:
                avatar.colocar(*pos)
        self.escena.hud.ocultar_aviso()

    # Gancho `modo_vehiculo.avanzar` del ControladorJugador: un paso de conducción. Espacio = freno de mano,
    # Shift (`correr`) = caballito y Ctrl = turbo (sin vc.CABALLITOS, Shift = turbo). Devuelve (x, z) del vehículo.
    def avanzar(self, controlador, h, v, dt, correr):
        flujo = self.escena.flujo
        jugador = self.jugador
        if jugador is None or flujo is None:
            return None
        if jugador.telefono.bloquea_movimiento():
            h = v = 0
        freno = bool(held_keys["space"])
        turbo, caballito = teclas_turbo_caballito(bool(correr))
        x, z = self.mundo.avanzar(h, v, dt, turbo, freno, camara=self.escena.camara, caballito=caballito)
        jugador.x, jugador.z = x, z
        flujo.actualizar_posicion(x, z)
        return (x, z)


# Nombre pedido en la tarea: el controlador es el mismo objeto (conduce, monta y baja).
ControladorVehiculo = MundoVehiculos

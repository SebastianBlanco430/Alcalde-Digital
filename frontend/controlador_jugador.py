# Controlador del jugador activo en el mundo (Controlador del MVC): lee el teclado,
# llama a las funciones puras de backend/logica/navegacion.py (modelo) y mueve el
# avatar (vista). Es hijo de EscenaMundo, así que Ursina NO le entrega update() ni
# input() mientras la escena está desactivada (p. ej. durante el minijuego).
#
# Teclas: WASD / flechas = mover (Shift = correr, si se configuró), Tab = teléfono, E =
# interactuar (solo si el modelo dice puede_interactuar(), es decir EN_RADIO del destino),
# Escape = pausa (solo si la escena la ofrece: `alternar_pausa()`). Espacio/Enter saltan las
# cinemáticas, pero eso es global (main.py) porque hay que poder saltar también en el interior.
#
# Mundo 3D: `obtener_yaw` devuelve el yaw ACTUAL de la cámara orbital y `velocidad_correr`
# activa Shift. La escena puede congelar los controles
# (`controles_bloqueados()`: pausa, cinemática). Tras las colisiones, la velocidad REAL
# (metros recorridos / dt) se le pasa al personaje (`fijar_velocidad`) para animar el
# caminar/correr/reposo.
#
# SALTO (Espacio): física vertical en backend/logica/salto_calculos.py (gravedad, impulso, coyote y buffer).
# Solo salta con la escena activa y los controles libres: no con el teléfono abierto, la pausa, una
# cinemática ni el minijuego. Espacio sigue saltando las cinemáticas (main.py, global): durante una
# cinemática los controles están congelados, así que no hay salto. En el aire el movimiento horizontal se
# conserva. El avatar recibe `fijar_estado_aire(en_aire, vel_vertical)` y, en las escaleras,
# `fijar_subiendo_escalera(bool)` (si los tiene: getattr). La sombra de contacto y el aro se quedan en el
# suelo mientras el avatar vuela, salvo que el avatar declare `sombra_sigue_suelo_sola = True`.
#
# ESCALERAS: la altura que pisa el jugador es `mapa.altura_con_escaleras` (peldaños cuantizados) y la
# altura visual lo persigue con un suavizado corto: sube escalón a escalón, sin deslizar. Subir una escalera
# es algo más lento (escaleras_calculos.FACTOR_SUBIDA).
#
# VEHÍCULOS (enganche): si el controlador tiene un atributo `modo_vehiculo` (no None) con un método
# `avanzar(controlador, h, v, dt, correr)`, `avanzar()` le delega todo el movimiento y devuelve lo
# que él devuelva ((x, z) o None); mientras exista, Espacio no salta (lo decide el modo de conducción).
#
# El modelo manda: la posición vive en Jugador.x/z (FlujoPartida.actualizar_posicion);
# el avatar solo se coloca a partir de ella.
#
# Yaw de la cámara: se pasa tal cual (sin invertir el signo). Con la fórmula del backend,
# dx = h·cosθ + v·sinθ, dz = -h·sinθ + v·cosθ, eso da W = hacia donde mira la cámara y
# D = su derecha (lo fija scripts/prueba_mundo.py con la cámara real y 5 yaw distintos).

import math

from ursina import Entity, held_keys, time

from backend.logica import escaleras_calculos, navegacion, salto_calculos
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from frontend import geometria_mundo

VELOCIDAD = 7.0     # unidades de mundo por segundo
DISTANCIA_PENDIENTE = 0.5  # m adelante en que se mide el desnivel para frenar en subida
DT_MAXIMO = 0.05   # tope por frame: un tirón no atraviesa paredes ni salta la cámara


class ControladorJugador(Entity):

    # escena: EscenaMundo (da `flujo` y `avatar_de(jugador)`). mapa: MapaCiudad.
    # al_interactuar: callback sin argumentos que dispara la tecla E.
    def __init__(self, escena, mapa, al_interactuar, velocidad=VELOCIDAD, obtener_yaw=lambda: 0.0,
                 velocidad_correr=None):
        super().__init__(parent=escena)
        self._escena = escena
        self._mapa = mapa
        self._al_interactuar = al_interactuar
        self.velocidad = velocidad
        self.velocidad_correr = velocidad_correr
        self._obtener_yaw = obtener_yaw
        self.modo_vehiculo = None          # enganche de conducción (ver arriba); None = a pie
        # VEHÍCULOS: callable(puede_mision) -> bool; True = consumió la E (montar/bajar)
        self.gancho_e = None
        self._verticales = {}              # nombre del jugador -> EstadoVertical (salto y peldaños)
        self._salto_pedido = False         # hubo Espacio desde el último avanzar()
        self._congelado_previo = False     # ¿estaba congelado en el frame anterior? (ver input)
        self._sombra_base = {}             # id(avatar) -> (aro.y, sombra.y) sin compensar

    # Hay partida en curso: flujo creado y alguna misión por jugar.
    def activo(self):
        flujo = self._escena.flujo
        return flujo is not None and not flujo.partida_terminada()

    # La escena puede congelar los controles (menú de pausa, cinemática en curso).
    def _congelado(self):
        pregunta = getattr(self._escena, "controles_bloqueados", None)
        return bool(pregunta()) if callable(pregunta) else False

    def update(self):
        self._congelado_previo = self._congelado()
        h, v = geometria_mundo.ejes_de_teclas(held_keys)
        correr = bool(held_keys["left shift"] or held_keys["right shift"])
        self.avanzar(h, v, time.dt, correr)

    # Un paso de movimiento con la entrada (h, v) durante dt segundos. Devuelve la
    # posición (x, z) del jugador activo, o None si el controlador está inactivo.
    def avanzar(self, h, v, dt, correr=False):
        if not self.activo():
            return None
        flujo = self._escena.flujo
        jugador = flujo.jugador_activo()
        avatar = self._escena.avatar_de(jugador)
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA) or self._congelado():
            self._informar_velocidad(avatar, 0.0)
            self._salto_pedido = False
            self._reiniciar_vertical(jugador)     # una cinemática o el minijuego dejan al avatar en el suelo
            return None                    # fundido, pausa o cinemática: nadie se mueve
        modo = self.modo_vehiculo
        if modo is not None and callable(getattr(modo, "avanzar", None)):
            self._salto_pedido = False
            return modo.avanzar(self, h, v, dt, correr)     # conducción: el modo manda
        telefono_abierto = jugador.telefono.bloquea_movimiento()
        if telefono_abierto:
            h = v = 0                      # con el teléfono abierto no se camina
        dt = min(dt, DT_MAXIMO)
        velocidad = self.velocidad_correr if (correr and self.velocidad_correr) else self.velocidad
        dx, dz = navegacion.mover_isometrico(h, v, self._obtener_yaw(), velocidad, dt)
        x0, z0 = jugador.x, jugador.z
        x, z = x0, z0
        sube_escalera = False
        if dx != 0 or dz != 0:
            # Cuesta: se mide el desnivel 0.5 m adelante y se frena/acelera (corriendo también).
            # El mapa 2D no tiene `altura`; el mundo plano devuelve 0 -> factor 1.
            altura = getattr(self._mapa, "altura", None)
            if altura is not None:
                largo = math.hypot(dx, dz)
                desnivel = altura(x0 + dx / largo * DISTANCIA_PENDIENTE,
                                  z0 + dz / largo * DISTANCIA_PENDIENTE) - altura(x0, z0)
                factor = navegacion.factor_pendiente(desnivel, DISTANCIA_PENDIENTE)
                # Escalera: subir cuesta un poco más (bajar, no). Solo si el mundo tiene perfiles de peldaños.
                sube_escalera = self._sube_escalera(x0, z0, dx / largo, dz / largo)
                if sube_escalera:
                    factor *= escaleras_calculos.factor_subida(True, True)
                dx, dz = dx * factor, dz * factor
            x, z = navegacion.mover_con_colisiones(self._mapa, x, z, dx, dz)
        # Se notifica siempre (también quieto): mantiene al día EN_RUTA / EN_RADIO.
        flujo.actualizar_posicion(x, z)

        if avatar is not None:
            avatar.colocar(x, z)
            if dx != 0 or dz != 0:
                avatar.mirar_hacia(geometria_mundo.rumbo_de(dx, dz))
            real = ((x - x0) ** 2 + (z - z0) ** 2) ** 0.5 / dt if dt > 0 else 0.0
            self._informar_velocidad(avatar, real)
            self._avanzar_vertical(avatar, jugador, x, z, dt, not telefono_abierto, sube_escalera and real > 0.05)
        self._salto_pedido = False
        return (x, z)

    # Pide un salto (lo hace Espacio; público para los scripts y las pruebas). Se atiende en el
    # próximo avanzar() si los controles están libres; si no, se descarta.
    def saltar(self):
        self._salto_pedido = True

    # Estado vertical (salto y peldaños) del jugador.
    def estado_vertical(self, jugador):
        return self._verticales.setdefault(jugador.nombre, salto_calculos.EstadoVertical())

    def _reiniciar_vertical(self, jugador):
        estado = self._verticales.get(jugador.nombre)
        if estado is not None:
            estado.reiniciar()
            estado.listo = False

    # ¿Se sube una escalera yendo desde (x, z) en la dirección unitaria (ux, uz)? Solo con un mundo que
    # ofrezca perfiles de peldaños (MundoCiudad con terreno); si no, nunca.
    def _sube_escalera(self, x, z, ux, uz):
        perfil_en = getattr(self._mapa, "perfil_escalera_en", None)
        if perfil_en is None or not escaleras_calculos.ESCALERAS_PELDANOS:
            return False
        perfil = perfil_en(x, z)
        if perfil is None:
            return False
        return perfil.sube_hacia(x, z, x + ux * DISTANCIA_PENDIENTE, z + uz * DISTANCIA_PENDIENTE)

    # Altura del suelo que pisa el jugador en (x, z): con escaleras en peldaños; si el mapa no sabe, la del
    # terreno; sin terreno (mapa 2D), None (no hay vertical que simular).
    def _suelo_en(self, x, z):
        con_escaleras = getattr(self._mapa, "altura_con_escaleras", None)
        if con_escaleras is not None:
            return con_escaleras(x, z)
        altura = getattr(self._mapa, "altura", None)
        return altura(x, z) if altura is not None else None

    # Sigue el suelo escalón a escalón y resuelve el salto; deja `avatar.y` en la altura visual.
    def _avanzar_vertical(self, avatar, jugador, x, z, dt, puede_saltar, subiendo):
        objetivo = self._suelo_en(x, z)
        if objetivo is None:
            return
        estado = self.estado_vertical(jugador)
        # Se suaviza solo sobre peldaños o mientras aún no alcanza al suelo (al bajar de una escalera);
        # en terreno suave la altura va pegada al suelo, como siempre.
        perfil_en = getattr(self._mapa, "perfil_escalera_en", None)
        en_escalera = perfil_en is not None and perfil_en(x, z) is not None
        if en_escalera:
            estado.suave = True              # se mantiene hasta alcanzar el suelo al bajar de la escalera
        salto, aterrizo = estado.avanzar(objetivo, dt, self._salto_pedido, puede_saltar, suavizar=estado.suave)
        if estado.suave and not en_escalera and not estado.en_aire and abs(estado.y - objetivo) < 2e-3:
            estado.suave = False
        # Despegado del suelo (en el aire) o sobre peldaños: la altura visual manda; en terreno suave coincide
        # con la que puso avatar.colocar() y no se toca (el comportamiento de siempre).
        if abs(estado.y - avatar.y) > 1e-6:
            avatar.y = estado.y
        elevacion = estado.elevacion(objetivo)
        self._poner_sombra_en_el_suelo(avatar, elevacion if estado.en_aire else 0.0)
        informar_aire = getattr(avatar, "fijar_estado_aire", None)
        if callable(informar_aire):
            informar_aire(estado.en_aire, estado.vy)
        informar_escalera = getattr(avatar, "fijar_subiendo_escalera", None)
        if callable(informar_escalera):
            informar_escalera(bool(subiendo) and not estado.en_aire)

    # La sombra de contacto y el aro cuelgan del avatar: al saltar se bajan lo mismo que sube el
    # avatar para que se queden sobre el suelo. Guarda sus alturas originales y las restaura al aterrizar.
    def _poner_sombra_en_el_suelo(self, avatar, elevacion):
        if getattr(avatar, "sombra_sigue_suelo_sola", False):
            return
        partes = [getattr(avatar, nombre, None) for nombre in ("aro", "sombra")]
        clave = id(avatar)
        if elevacion > 1e-6:
            if clave not in self._sombra_base:
                self._sombra_base[clave] = tuple(p.y if p is not None else 0.0 for p in partes)
            for parte, base in zip(partes, self._sombra_base[clave]):
                if parte is not None:
                    parte.y = base - elevacion
        elif clave in self._sombra_base:
            for parte, base in zip(partes, self._sombra_base.pop(clave)):
                if parte is not None:
                    parte.y = base

    @staticmethod
    def _informar_velocidad(avatar, velocidad):
        informar = getattr(avatar, "fijar_velocidad", None)
        if callable(informar):
            informar(velocidad)

    def input(self, key):
        if not self.activo():
            return
        flujo = self._escena.flujo
        jugador = flujo.jugador_activo()
        # Pausa y saltar cinemática las ofrece la escena 3D .
        if key == "escape" and hasattr(self._escena, "alternar_pausa"):
            self._escena.alternar_pausa()
            return
        # Durante el fundido hacia/desde el minijuego nadie interactúa (igual que el movimiento).
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA) or self._congelado():
            return
        if key == "space":
            # Salto: solo con los controles libres en el frame anterior (así el mismo Espacio que acaba de
            # saltar una cinemática no salta además), sin teléfono abierto y a pie.
            if (not self._congelado_previo and self.modo_vehiculo is None
                    and not jugador.telefono.bloquea_movimiento()):
                self.saltar()
            return
        if key == "tab":
            jugador.telefono.alternar()
        elif key == "e":
            # Con el teléfono abierto no se interactúa (tampoco se camina).
            puede = flujo.puede_interactuar() and not jugador.telefono.bloquea_movimiento()
            if self.gancho_e is not None and self.gancho_e(puede):
                return                     # montar/bajar de un vehículo (si conduce, bajar va antes que la misión)
            if puede:
                self._al_interactuar()

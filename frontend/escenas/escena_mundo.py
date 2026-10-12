# Escena del mundo (Ursina): la ciudad isométrica jugable (Fase 3 del Overworld).
#
# Se dibuja con primitivas: suelo, calles (cubos planos sobre cada segmento del
# mapa), plazas (círculos), un edificio placeholder por lugar FUERA de la zona
# transitable (ver geometria_mundo.ubicar_edificio), el nombre de cada lugar, un
# avatar por jugador y un computador en la plaza del destino de la misión activa.
# El HUD 2D va en un Entity aparte hijo de camera.ui, que se habilita/deshabilita
# junto con la escena (desactivar un padre de `scene` no oculta a camera.ui).
#
# Cámara: ortográfica isométrica (la de demos/ciudad_ursina.py) que sigue
# suavemente al jugador activo. al_entrar guarda el estado previo de la cámara
# (parent, orthographic, fov, planos, posición, rotación) y al_salir lo restaura
# exacto: las escenas de camera.ui no notan el cambio.
#
# El mundo se DESACTIVA (no se destruye) al ir al minijuego. Una Entity con un
# ancestro desactivado no recibe input() ni update() (Ursina las salta), por eso
# el ControladorJugador (hijo de esta escena) solo reacciona mientras está activa.
# La posición vive en el modelo (Jugador.x/z); aquí solo se dibuja.
# Escape no hace nada por ahora (decisión de Sam pendiente).
# Partida terminada: el controlador no mueve a nadie ni responde a la E, y el HUD muestra el
# panel con los indicadores finales y el botón que vuelve al menú (callback al_menu).

from ursina import AmbientLight, DirectionalLight, camera, color, destroy, scene, time

from backend.logica.roles import ROLES
from frontend import estilo, geometria_mundo
from frontend.componentes import rgb
from frontend.controlador_jugador import ControladorJugador
from frontend.escenas.escena_base import Escena
from frontend.hud import HudMundo, RutaMundo
from frontend.objetos_mundo import AvatarJugador, ComputadorMision, etiqueta, pieza

# Colores del mundo (RGB 0-255).
COLOR_SUELO = (52, 72, 58)
COLOR_CALLE = (92, 94, 104)
COLOR_ACERA = (150, 152, 162)       # aro claro alrededor de cada plaza
COLOR_PLAZA = (118, 120, 132)
PALETA_EDIFICIOS = (
    (66, 133, 244), (225, 225, 230), (245, 140, 50), (240, 130, 170),
    (90, 190, 110), (240, 200, 60), (160, 110, 220),
)
ALTURAS_EDIFICIOS = (3.2, 2.0, 2.8, 3.6, 2.4, 1.8, 2.4)

# Alturas (y) de las capas planas: evitan z-fighting (la separación mínima es 0.01).
Y_CALLE = 0.02        # cubo de 0.04 de alto centrado aquí: tapa en y = 0.04
Y_ACERA = 0.05
Y_PLAZA = 0.07
Y_PAD = 0.09

# Cámara.
FOV_SEGUIMIENTO = 18        # alto del encuadre ortográfico (unidades de mundo)
DISTANCIA_CAMARA = 40       # no cambia el tamaño en ortográfica; solo el recorte
PLANO_CERCANO = 1
PLANO_LEJANO = 200
RAPIDEZ_CAMARA = 4.0        # suavizado exponencial (~1 s para cubrir casi todo)


class EscenaMundo(Escena):

    TEXTO_SIN_MISION = "Sin misiones nuevas por ahora"

    # mapa: MapaCiudad (se inyecta). al_interactuar: callback de la tecla E. al_menu: callback
    # del botón "Volver al menú" del panel de fin de partida.
    def __init__(self, al_interactuar, mapa, al_menu=None, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self._mapa = mapa
        self._al_interactuar = al_interactuar
        self.flujo = None
        self._sesion = None
        self.avatares = {}           # nombre del jugador -> AvatarJugador
        self._camara_guardada = None
        self._foco = None            # (x, z) que mira la cámara (suavizado)

        self.edificios = {}          # lugar -> (x, z, lado) (ver geometria_mundo)
        self.entidades_edificios = {}
        self.plazas = {}
        self._construir_ciudad()
        self.computador = ComputadorMision(parent=self, enabled=False)

        # Luces del mundo: el sombreado distingue las caras de los cubos.
        DirectionalLight(parent=self, rotation=(50, -30, 0), shadows=False)
        AmbientLight(parent=self, color=color.rgba32(130, 130, 130, 255))

        self.controlador = ControladorJugador(self, mapa, al_interactuar)

        # Ruta BFS resaltada sobre las calles (en `scene`, hija de esta escena).
        self.ruta_mundo = RutaMundo(mapa, parent=self)

        # HUD 2D (camera.ui): hermano de la escena, no hijo (la escena no cuelga de
        # camera.ui). Contiene panel de turno, minimapa, teléfono y aviso de la E.
        self.hud = HudMundo(mapa, lambda: self.flujo, al_menu=al_menu)
        self.texto_turno = self.hud.panel_turno.texto_turno
        self.texto_mision = self.hud.panel_turno.texto_mision

    # -- Construcción de la ciudad --

    def _construir_ciudad(self):
        mapa = self._mapa
        xmin, xmax, zmin, zmax = mapa.limites()
        pieza(parent=self, model="plane", color=rgb(COLOR_SUELO),
              position=((xmin + xmax) / 2, 0, (zmin + zmax) / 2),
              scale=(xmax - xmin + 40, 1, zmax - zmin + 40))   # grande: no se ve el vacío al seguir al jugador

        for a, b in mapa.segmentos():
            (xa, za), (xb, zb) = mapa.coordenada(a), mapa.coordenada(b)
            largo = ((xb - xa) ** 2 + (zb - za) ** 2) ** 0.5
            pieza(parent=self, model="cube", color=rgb(COLOR_CALLE),
                  position=((xa + xb) / 2, Y_CALLE, (za + zb) / 2),
                  scale=(mapa.ancho_calle, 0.04, largo),
                  rotation_y=geometria_mundo.rumbo_de(xb - xa, zb - za))

        self.edificios = geometria_mundo.ubicar_edificios(mapa, geometria_mundo.yaw_de_camara())
        for i, lugar in enumerate(mapa.lugares()):
            cx, cz = mapa.coordenada(lugar)
            tono = rgb(PALETA_EDIFICIOS[i % len(PALETA_EDIFICIOS)])
            diametro = 2 * mapa.radio_plaza
            pieza(parent=self, model="circle", rotation_x=90, position=(cx, Y_ACERA, cz),
                  scale=diametro + 0.4, color=rgb(COLOR_ACERA))
            self.plazas[lugar] = pieza(parent=self, model="circle", rotation_x=90,
                                       position=(cx, Y_PLAZA, cz), scale=diametro,
                                       color=rgb(COLOR_PLAZA))
            # Disco del color del edificio: enlaza visualmente plaza y edificio.
            pieza(parent=self, model="circle", rotation_x=90, position=(cx, Y_PAD, cz),
                  scale=1.4, color=tono)

            if lugar not in self.edificios:
                etiqueta(lugar, parent=self, position=(cx, 1.5, cz))
                continue
            x, z, lado = self.edificios[lugar]
            alto = ALTURAS_EDIFICIOS[i % len(ALTURAS_EDIFICIOS)]
            self.entidades_edificios[lugar] = pieza(
                parent=self, model="cube", color=tono, position=(x, alto / 2, z),
                scale=(lado, alto, lado))
            etiqueta(lugar, parent=self, position=(x, alto + 0.9, z))

    # -- Ciclo de vida --

    # `flujo`: FlujoPartida. Si su sesión cambió se reconstruyen los avatares; si es
    # la misma (se vuelve del minijuego) solo se refrescan posiciones y textos.
    def al_entrar(self, flujo=None, **datos):
        if flujo is not None:
            self.flujo = flujo
        self.hud.enabled = True
        self._guardar_y_poner_camara()
        if self.flujo is None:
            return
        if self.flujo.sesion is not self._sesion:
            self._sesion = self.flujo.sesion
            self._foco = None        # partida nueva: la cámara aparece sobre el jugador
            self._reconstruir_avatares()
        self.refrescar()
        if self._foco is None:
            activo = self.flujo.jugador_activo()
            self._foco = (activo.x, activo.z)
        self._mover_camara()

    def al_salir(self):
        self.hud.enabled = False
        self._restaurar_camara()

    # Cámara: sigue al jugador activo con un suavizado exponencial. Al cambiar de
    # turno el foco (que se conserva entre entradas) se desliza al nuevo jugador.
    def update(self):
        if self.flujo is None or self._foco is None:
            return
        activo = self.flujo.jugador_activo()
        fx, fz = self._foco
        self._foco = (
            geometria_mundo.suavizar(fx, activo.x, RAPIDEZ_CAMARA, time.dt),
            geometria_mundo.suavizar(fz, activo.z, RAPIDEZ_CAMARA, time.dt),
        )
        self._mover_camara()
        self.avanzar_hud(time.dt)

    # Un paso del HUD con `dt` segundos (los tests lo llaman a mano con dt fijos):
    # ruta del GPS, minimapa, teléfono, aviso de la E y ruta resaltada en el mundo.
    def avanzar_hud(self, dt):
        if self.flujo is None or self._sesion is None:
            return
        self.hud.actualizar(dt, self._sesion)
        activo = self.flujo.jugador_activo()
        self.ruta_mundo.actualizar(activo.x, activo.z, self.hud.guia.ruta)

    # Las teclas (E, Tab, WASD) las atiende el ControladorJugador.

    # -- Vista --

    def avatar_de(self, jugador):
        return self.avatares.get(jugador.nombre)

    def _reconstruir_avatares(self):
        for avatar in self.avatares.values():
            destroy(avatar)
        self.avatares = {}
        for jugador in self._sesion.jugadores():
            self.avatares[jugador.nombre] = AvatarJugador(
                jugador.nombre, ROLES[jugador.rol].color, parent=self)

    # Vuelca el modelo (posiciones, turno, misión) a avatares, computador y HUD.
    def refrescar(self):
        activo = self.flujo.jugador_activo()
        for jugador in self._sesion.jugadores():
            avatar = self.avatares[jugador.nombre]
            avatar.colocar(jugador.x, jugador.z)
            avatar.resaltar(jugador is activo)

        mision = self.flujo.mision_actual()
        self.hud.panel_turno.fijar(
            f"Turno de {activo.nombre} ({ROLES[activo.rol].nombre})",
            f"Misión: {mision.titulo}" if mision is not None else self.TEXTO_SIN_MISION)
        # El computador va en el centro de la plaza del destino; sin misión se oculta.
        if mision is None:
            self.computador.enabled = False
        else:
            cx, cz = self._mapa.coordenada(mision.destino)
            self.computador.position = (cx, 0, cz)
            self.computador.enabled = True
        # Fin del catálogo: nadie tiene misiones pendientes -> panel "Partida terminada".
        if self.flujo.partida_terminada():
            self.hud.panel_fin.mostrar(self._sesion.estado_partida.indicadores())
        else:
            self.hud.panel_fin.ocultar()
        self.avanzar_hud(0)

    # -- Cámara --

    def _mover_camara(self):
        fx, fz = self._foco
        camera.position = geometria_mundo.posicion_camara(
            (fx, 0, fz), geometria_mundo.ROTACION_CAMARA[0], geometria_mundo.yaw_de_camara(),
            DISTANCIA_CAMARA)

    # Guarda el estado previo UNA vez (si ya hay uno, es el de las escenas 2D) y
    # pone la cámara isométrica.
    def _guardar_y_poner_camara(self):
        if self._camara_guardada is None:
            self._camara_guardada = {
                "parent": camera.parent, "orthographic": camera.orthographic,
                "fov": camera.fov, "position": camera.position, "rotation": camera.rotation,
                "near": camera.clip_plane_near, "far": camera.clip_plane_far,
            }
        camera.parent = scene
        camera.orthographic = True
        camera.fov = FOV_SEGUIMIENTO
        camera.clip_plane_near = PLANO_CERCANO
        camera.clip_plane_far = PLANO_LEJANO
        camera.rotation = geometria_mundo.ROTACION_CAMARA
        if self._foco is not None:
            self._mover_camara()

    # Orden: padre, tipo de lente, fov (depende del tipo), planos, pose.
    def _restaurar_camara(self):
        guardada = self._camara_guardada
        if guardada is None:
            return
        camera.parent = guardada["parent"]
        camera.orthographic = guardada["orthographic"]
        camera.fov = guardada["fov"]
        camera.clip_plane_near = guardada["near"]
        camera.clip_plane_far = guardada["far"]
        camera.position = guardada["position"]
        camera.rotation = guardada["rotation"]
        self._camara_guardada = None

# Escena del mundo 3D real (Ursina): Ciudad Nova en tercera persona.
#
# Piezas: la ciudad (frontend/ciudad_3d.py, construida desde el MundoCiudad del backend), un
# Personaje articulado por jugador, la cámara orbital (frontend/camara_tercera_persona.py), el
# controlador del jugador activo, el HUD de siempre (teléfono, minimapa que gira con la
# cámara, aviso "Presiona E para entrar a <lugar>"), la baliza sobre la puerta destino, la
# ruta del GPS en el piso y el menú de pausa (Escape).
#
# La posición vive en el modelo (Jugador.x/z); aquí solo se dibuja. El mundo se DESACTIVA (no
# se destruye) al ir al minijuego: una Entity con un ancestro desactivado no recibe input() ni
# update() (Ursina las salta), así que controlador, cámara y personajes solo reaccionan
# mientras la escena está activa. El HUD (camera.ui) es hermano de la escena y se habilita /
# deshabilita junto con ella.
#
# Ratón: se bloquea (cursor oculto, la cámara gira con él) mientras se camina y se libera con
# el teléfono abierto (Tab), la pausa (Escape), el panel de fin de partida y el minijuego.
# Partida terminada: el controlador no mueve a nadie ni responde a la E, y el HUD muestra el
# panel con los indicadores finales y el botón que vuelve al menú (callback al_menu).
#
# Cinemáticas (DirectorCinematica + frontend/guion_cinematicas.py):
#   reproducir_entrada(jugador, lugar, al_terminar): la cámara deja la órbita y toma la fachada
#     en 3/4, el personaje camina al punto de entrada y gira hacia la puerta, la abre (-100° sobre su
#     bisagra) y entra; al terminar se llama `al_terminar` (ConexionFlujo sigue con el fundido).
#   al_entrar(salida={"jugador", "lugar"}): el que salía del edificio aparece en el vano, sale, la
#     puerta se cierra y la cámara vuelve a la órbita detrás de él; luego, como el turno ya pasó, el
#     seguimiento de la cámara la desliza al jugador activo.
# Durante ambas los controles están congelados y el ratón libre; Espacio/Enter salta el tramo
# actual y dos seguidas toda la cinemática. `escala_tiempo` = 0 las vuelve instantáneas (scripts).

import math

from ursina import application, camera, mouse, scene, time

from backend.logica import navegacion
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from backend.logica.roles import ROLES
from frontend import camara_calculos as cc
from frontend import geometria_mundo, poses
from frontend.componentes import destruir_arbol
from frontend import guion_cinematicas as guion
from frontend.camara_tercera_persona import CamaraTerceraPersona
from frontend.cinematica import ease_in_out, lerp, lerp_angulo, lerp_vec3
from frontend.ciudad_3d import SOMBRAS, Ciudad3D
from frontend.controlador_jugador import ControladorJugador
from frontend.director_cinematica import DirectorCinematica
from frontend.escenas.escena_base import Escena
from frontend.hud import HudMundo
from frontend.marcadores_mundo import Baliza, RutaPiso
from frontend.menu_pausa import MenuPausa
from frontend.peatones import Peatones
from frontend.personaje import Personaje

VELOCIDAD_CAMINAR = 4.8     # m/s: ~25 s de punta a punta de la ciudad
VELOCIDAD_CORRER = 8.5      # m/s con Shift: ~14 s


class EscenaMundo(Escena):

    TEXTO_SIN_MISION = "Sin misiones nuevas por ahora"

    # mundo: MundoCiudad (se inyecta). al_interactuar: callback de la tecla E. al_menu: callback
    # de "Volver al menú" (pausa y panel de fin de partida).
    def __init__(self, al_interactuar, mundo, al_menu=None, sombras=SOMBRAS, escala_tiempo=1.0, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self._mundo = mundo
        self._al_interactuar = al_interactuar
        self._al_menu = al_menu
        self.flujo = None
        self._sesion = None
        self.avatares = {}               # nombre del jugador -> Personaje
        self.en_pausa = False
        self.escala_tiempo = escala_tiempo       # 0 = cinemáticas instantáneas
        self._cinematica = False                 # ¿hay una cinemática en curso?

        self.ciudad = Ciudad3D(mundo, sombras=sombras, parent=self)
        self.camara = CamaraTerceraPersona(self.ciudad.raiz_colisiones, suelo=mundo.altura, parent=self)
        self.camara.objetivo = self._posicion_del_activo
        self.controlador = ControladorJugador(
            self, mundo, al_interactuar, velocidad=VELOCIDAD_CAMINAR, velocidad_correr=VELOCIDAD_CORRER,
            obtener_yaw=lambda: self.camara.yaw)
        self.director = DirectorCinematica(parent=self)
        self.peatones = Peatones(mundo, parent=self)      # gente que pasea (decoración)
        self.baliza = Baliza(parent=self, enabled=False)
        self.ruta_piso = RutaPiso(suelo=mundo.altura, parent=self)

        # HUD 2D (camera.ui): hermano de la escena, no hijo (la escena cuelga de `scene`).
        self.hud = HudMundo(mundo, lambda: self.flujo, al_menu=al_menu, rotacion_libre=True)
        self.texto_turno = self.hud.panel_turno.texto_turno
        self.texto_mision = self.hud.panel_turno.texto_mision
        self.menu_pausa = MenuPausa(
            al_reanudar=lambda: self.alternar_pausa(False), al_menu=self._ir_al_menu,
            al_salir=application.quit, parent=self.hud)

    # -- Ciclo de vida --

    # `flujo`: FlujoPartida. Si su sesión cambió se reconstruyen los personajes; si es la
    # misma (se vuelve del minijuego) solo se refrescan posiciones y textos.
    # `salida`: {"jugador", "lugar"} si se vuelve de un edificio (cinemática de salir por la puerta).
    def al_entrar(self, flujo=None, salida=None, **datos):
        if flujo is not None:
            self.flujo = flujo
        self.hud.enabled = True
        self.ciudad.encender_luces(True)
        self.camara.preparar_camara()
        self._restablecer_tras_cinematica()
        self._cinematica = salida is not None     # al salir de un edificio hay cinemática (y panel de fin oculto)
        if self.flujo is None:
            self._cinematica = False
            return
        nueva_partida = self.flujo.sesion is not self._sesion
        if nueva_partida:
            self._sesion = self.flujo.sesion
            self._reconstruir_personajes()
        self.refrescar()
        if nueva_partida:
            self.camara.yaw = self._yaw_hacia_el_destino()
            self.camara.colocar_ya()
        else:
            self.camara.actualizar(0)
        self._sincronizar_raton()
        if salida is not None:
            self._reproducir_salida(salida["jugador"], salida["lugar"])

    def al_salir(self):
        self.director.cancelar()
        self._cinematica = False
        self.alternar_pausa(False)
        self.hud.enabled = False
        mouse.locked = False
        self.ciudad.encender_luces(False)
        self.camara.restaurar_camara()

    # -- Frame --

    def update(self):
        if self.flujo is None or self._sesion is None:
            return
        self._sincronizar_raton()
        self.avanzar_hud(time.dt)

    # Un paso del HUD con `dt` segundos (los tests lo llaman a mano con dt fijos): ruta del GPS,
    # minimapa (gira con la cámara), teléfono, aviso de la E, y ruta + baliza en el mundo.
    def avanzar_hud(self, dt):
        if self.flujo is None or self._sesion is None:
            return
        self.hud.actualizar(dt, self._sesion, yaw_grados=self.camara.yaw)
        self._actualizar_ruta_piso()

    # -- Estado de controles --

    # Pausa y cinemáticas congelan al jugador (ver ControladorJugador).
    def controles_bloqueados(self):
        return self.en_pausa or self._cinematica

    def alternar_pausa(self, abierta=None):
        if self._cinematica:
            return                                # durante una cinemática no hay pausa (Escape no hace nada)
        if abierta is None:
            abierta = not self.en_pausa
        if abierta == self.en_pausa:
            return
        self.en_pausa = abierta
        self.menu_pausa.enabled = abierta
        self._sincronizar_raton()

    def _ir_al_menu(self):
        self.alternar_pausa(False)
        if self._al_menu is not None:
            self._al_menu()

    # ¿El ratón debe estar capturado (cámara orbitando)? No con pausa, teléfono abierto,
    # partida terminada ni durante el minijuego.
    def raton_capturado(self):
        flujo = self.flujo
        if flujo is None or self.en_pausa or self._cinematica or flujo.partida_terminada():
            return False
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return False
        return not flujo.jugador_activo().telefono.bloquea_movimiento()

    def _sincronizar_raton(self):
        deseado = self.raton_capturado()
        if mouse.locked != deseado:
            mouse.locked = deseado
        self.camara.bloquear(not deseado)

    # -- Vista --

    def avatar_de(self, jugador):
        return self.avatares.get(jugador.nombre)

    def _posicion_del_activo(self):
        activo = self.flujo.jugador_activo()
        return (activo.x, activo.z)

    def _reconstruir_personajes(self):
        for avatar in self.avatares.values():
            destruir_arbol(avatar)
        self.avatares = {}
        for jugador in self._sesion.jugadores():
            avatar = Personaje(jugador.nombre, ROLES[jugador.rol].color, parent=self)
            avatar.suelo = self._mundo.altura
            self.avatares[jugador.nombre] = avatar
        self.camara.ignorar = list(self.avatares.values())

    # Rumbo (yaw) que mira desde el jugador activo hacia la puerta de su misión (o 0).
    def _yaw_hacia_el_destino(self):
        mision = self.flujo.mision_actual()
        if mision is None:
            return 0.0
        activo = self.flujo.jugador_activo()
        px, pz = self._mundo.punto_interaccion(mision.destino)
        return geometria_mundo.rumbo_de(px - activo.x, pz - activo.z)

    # Vuelca el modelo (posiciones, turno, misión) a personajes, baliza y HUD.
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
        # Baliza sobre la puerta del destino; sin misión se oculta.
        if mision is None:
            self.baliza.enabled = False
        else:
            px, pz = self._mundo.punto_interaccion(mision.destino)
            self.baliza.colocar(px, pz, self._mundo.edificio_de(mision.destino).alto + 2.2,
                                suelo=self._mundo.altura(px, pz))
            self.baliza.enabled = True
        # Fin del catálogo: nadie tiene misiones pendientes -> panel "Partida terminada".
        if self.flujo.partida_terminada() and not self._cinematica:
            self.hud.panel_fin.mostrar(self._sesion.estado_partida.indicadores())
        else:
            self.hud.panel_fin.ocultar()
        self.avanzar_hud(0)

    # Línea del GPS en el piso: del jugador por las esquinas y hasta la puerta.
    def _actualizar_ruta_piso(self):
        activo = self.flujo.jugador_activo()
        mision = self.flujo.mision_actual()
        if mision is None or self.flujo.partida_terminada():
            self.ruta_piso.actualizar([])
            return
        puntos = navegacion.ruta_gps_hasta_puerta(self._mundo, activo.x, activo.z, mision.destino)
        self.ruta_piso.actualizar([(activo.x, activo.z)] + puntos)

    # -- Cinemáticas --

    def saltar_cinematica(self):
        return self.director.saltar()

    # Deja todo como en el juego normal: puertas cerradas, todos visibles y animándose solos,
    # cámara de nuevo en órbita (por si una cinemática se interrumpió o falló a medias).
    def _restablecer_tras_cinematica(self):
        self.director.cancelar()
        self._cinematica = False
        self.ciudad.cerrar_puertas()
        for avatar in self.avatares.values():
            avatar.enabled = True
            avatar.automatico = True
            avatar.etiqueta.enabled = True
        self.camara.soltar_control()

    def _terminar_salida(self, jugador, entrada):
        avatar = self.avatar_de(jugador)
        self.ciudad.cerrar_puertas()
        if avatar is not None:
            avatar.automatico = True
            avatar.etiqueta.enabled = True
        self.camara._pivote = tuple(entrada)       # la órbita arranca en quien salió; luego se desliza al activo
        self.camara.soltar_control()
        self._cinematica = False
        self.refrescar()
        self._sincronizar_raton()

    # Entrada: encuadre -> acercarse -> abrir_puerta -> entrar. `al_terminar()` se llama al final
    # (el personaje ya desapareció tras la puerta abierta; los controles siguen congelados).
    def reproducir_entrada(self, jugador, lugar, al_terminar):
        edificio = self._mundo.edificio_de(lugar)
        puerta = self.ciudad.puertas[lugar]
        avatar = self.avatar_de(jugador)
        entrada = edificio.punto_entrada()
        inicio = (jugador.x, jugador.z)
        toma = guion.toma_fachada(edificio)
        camara0 = (tuple(camera.position), camera.rotation_x, camera.rotation_y)
        rumbo0, rumbo_puerta = avatar.rumbo, edificio.rumbo_puerta()
        distancia = math.dist(inicio, entrada)
        plan = guion.plan_entrada(distancia)
        duracion_acercarse = dict(plan)["acercarse"]
        dentro = self._mas_alla_de_la_puerta(edificio, 1.3)

        self._cinematica = True
        self.camara.tomar_control()
        avatar.automatico = False
        avatar.etiqueta.enabled = False                # sin carteles de nombre durante la cinemática
        self._sincronizar_raton()

        def encuadre(t):
            k = ease_in_out(t)
            camera.position = lerp_vec3(camara0[0], toma["position"], k)
            camera.rotation = (lerp(camara0[1], toma["pitch"], k), lerp_angulo(camara0[2], toma["yaw"], k), 0)

        def acercarse(t):
            k = ease_in_out(t)
            avatar.colocar(lerp(inicio[0], entrada[0], k), lerp(inicio[1], entrada[1], k))
            avatar.fijar_rumbo(lerp_angulo(rumbo0, rumbo_puerta, k))
            camina = distancia > 0.3 and t < 1.0
            avatar.aplicar_pose(poses.pose_caminar(
                poses.fase_siguiente(0, 4.8, t * duracion_acercarse), 0.55 if camina else 0))
            if t >= 1.0:
                jugador.x, jugador.z = entrada          # el modelo queda donde terminó de caminar

        def abrir_puerta(t):
            puerta.abrir(ease_in_out(t))
            avatar.aplicar_pose(poses.POSE_PARADO)

        def entrar(t):
            k = ease_in_out(t)
            avatar.colocar(lerp(entrada[0], dentro[0], k), lerp(entrada[1], dentro[1], k))
            avatar.aplicar_pose(poses.pose_caminar(poses.fase_siguiente(0, 4.8, t * guion.ENTRADA_ENTRAR), 0.55))
            if t >= 1.0:
                avatar.enabled = False                  # desapareció en la oscuridad del vano

        self.director.reproducir(
            plan, {"encuadre": encuadre, "acercarse": acercarse, "abrir_puerta": abrir_puerta, "entrar": entrar},
            al_terminar=al_terminar, escala=self.escala_tiempo)

    # Salida: aparecer (en el vano, puerta abierta) -> salir -> cerrar_puerta -> camara (a la órbita).
    def _reproducir_salida(self, jugador, lugar):
        edificio = self._mundo.edificio_de(lugar)
        puerta = self.ciudad.puertas[lugar]
        avatar = self.avatar_de(jugador)
        entrada = edificio.punto_entrada()
        toma = guion.toma_fachada(edificio)
        dentro = self._mas_alla_de_la_puerta(edificio, 1.3)
        yaw, pitch = self.camara.yaw, self.camara.pitch
        orbita = cc.posicion_orbital(cc.pivote_del_jugador(*entrada, suelo=edificio.y), yaw, pitch,
                                     self.camara.distancia)

        self._cinematica = True
        self.camara.tomar_control()
        self._sincronizar_raton()
        avatar.enabled = True
        avatar.automatico = False
        avatar.etiqueta.enabled = False
        avatar.colocar(*dentro)
        avatar.fijar_rumbo(edificio.rumbo_puerta() + 180)      # mira hacia la calle
        puerta.abrir(1)
        camera.position = toma["position"]
        camera.rotation = (toma["pitch"], toma["yaw"], 0)

        def aparecer(t):
            puerta.abrir(1)
            avatar.colocar(*dentro)
            avatar.aplicar_pose(poses.POSE_PARADO)

        def salir(t):
            k = ease_in_out(t)
            avatar.colocar(lerp(dentro[0], entrada[0], k), lerp(dentro[1], entrada[1], k))
            avatar.aplicar_pose(poses.pose_caminar(poses.fase_siguiente(0, 4.8, t * guion.SAL_SALIR), 0.55))
            if t >= 1.0:
                jugador.x, jugador.z = entrada

        def cerrar_puerta(t):
            puerta.abrir(1 - ease_in_out(t))
            avatar.aplicar_pose(poses.POSE_PARADO)

        def volver_camara(t):
            k = ease_in_out(t)
            camera.position = lerp_vec3(toma["position"], orbita, k)
            camera.rotation = (lerp(toma["pitch"], pitch, k), lerp_angulo(toma["yaw"], yaw, k), 0)

        self.director.reproducir(
            guion.plan_salida(),
            {"aparecer": aparecer, "salir": salir, "cerrar_puerta": cerrar_puerta, "camara": volver_camara},
            al_terminar=lambda: self._terminar_salida(jugador, entrada), escala=self.escala_tiempo)

    # Punto `metros` DENTRO del edificio, pasando la puerta (en la dirección de entrada).
    @staticmethod
    def _mas_alla_de_la_puerta(edificio, metros):
        px, pz = edificio.puerta()
        r = math.radians(edificio.rumbo_puerta())
        return (px + math.sin(r) * metros, pz + math.cos(r) * metros)

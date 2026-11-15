# Computador interactuable del mundo (Ursina): un escritorio con monitor y silla en el ancla `terminal` del caso (JSON).
# Cumple el Protocol Interaccion de frontend/economia_mundo.py (prioridad, aviso, usar, actualizar): con E cerca,
# el avatar camina a la silla, SE SIENTA, la cámara se acerca al monitor y un GLITCH (colores GLITCH_A/B) lleva a la
# escena digital. Es una interacción NUEVA: no toca la misión que usa el PC para el minijuego de noticias.
#
# Estado intacto: el modelo (Jugador.x/z, misión, turno) no se toca; solo se mueve el avatar visual, y al volver
# EscenaMundo.al_entrar lo recoloca y suelta la cámara. Sin GameState (partida en línea o GAMESTATE=0) avisa
# «no disponible» y no hace nada más.

import math

from ursina import Entity, camera

from frontend import materiales as mat
from frontend import mundo_digital_calculos as calc
from frontend import poses
from frontend import camara_calculos as cc
from frontend.cinematica import ease_in_out, lerp, lerp_angulo, lerp_vec3
from frontend.componentes import rgb
from frontend.director_cinematica import DirectorCinematica
from frontend.piezas import etiqueta, malla_unida, pieza, silenciar

RADIO_USO = 2.2
PRIORIDAD = 8
SEGUNDOS_MENSAJE = 3.0
FOV_MONITOR = 40
PANTALLA = (0.0, 1.07, -0.25)         # local: centro del monitor
ASIENTO = 0.66                        # local z de la pelvis sentada
APROXIMACION = 1.4                    # local z desde donde se camina hacia la silla
HOMBRO = (0.9, 1.5, 1.7)
VIA = (0.75, 1.25, 0.45)
FIN_CAMARA = (0.0, 1.07, 0.23)
NO_DISPONIBLE = "Computador no disponible en esta partida"


def _cubo(color_rgb, pos, escala):
    return {"model": "cube", "color": rgb(color_rgb), "position": pos, "scale": escala}


class Computador:

    prioridad = PRIORIDAD

    # abrir(caso): callable que cambia a la escena digital (lo pone registro_mundo_digital).
    def __init__(self, escena, caso, x, z, rumbo, abrir, glitch):
        self._escena, self.caso, self._abrir, self._glitch = escena, caso, abrir, glitch
        self.x, self.z, self.rumbo = float(x), float(z), float(rumbo)
        self._mensaje, self._t_mensaje = None, 0.0
        self._jugador = None
        self.pista_mision = None          # callable() -> texto extra del aviso (lo pone registro_mundo_digital) o None
        self._director = DirectorCinematica(parent=escena)
        self.raiz = self._construir()

    def _construir(self):
        suelo = self._escena._mundo.altura(self.x, self.z)
        raiz = pieza(parent=self._escena, position=(self.x, suelo, self.z), rotation_y=self.rumbo, name="computador_caso",
                     shader=None)
        madera, metal, silla = (150, 104, 66), (62, 64, 74), (52, 56, 74)
        malla_unida(raiz, [
            _cubo(madera, (0, 0.75, -0.1), (1.4, 0.06, 0.7)), _cubo((96, 66, 44), (-0.65, 0.36, -0.1), (0.06, 0.72, 0.6)),
            _cubo((96, 66, 44), (0.65, 0.36, -0.1), (0.06, 0.72, 0.6)), _cubo(metal, (0, 1.07, -0.3), (0.72, 0.45, 0.05)),
            _cubo(metal, (0, 0.86, -0.3), (0.06, 0.2, 0.05)), _cubo((40, 42, 52), (0, 0.79, 0.12), (0.46, 0.02, 0.15)),
            _cubo(silla, (0, 0.45, ASIENTO), (0.5, 0.07, 0.5)), _cubo(silla, (0, 0.78, ASIENTO + 0.23), (0.46, 0.55, 0.06)),
            _cubo(metal, (0, 0.22, ASIENTO), (0.06, 0.4, 0.06)), _cubo(metal, (0, 0.03, ASIENTO), (0.5, 0.05, 0.5)),
        ])
        # pantalla encendida (neón cian) que mira a la silla; sin sombreado
        pieza(parent=raiz, model="quad", color=rgb(mat.neon_atenuado(mat.NEON_CIAN, 0.55)), shader=None,
              position=(PANTALLA[0], PANTALLA[1], PANTALLA[2] - 0.0) , scale=(0.64, 0.37), rotation_y=180)
        try:
            cartel = etiqueta((self.caso.terminal or {}).get("nombre", "Terminal"), parent=raiz, y=1.65, scale=3)
            silenciar(cartel)
        except Exception as error:
            print(f"[mundo digital] sin cartel del computador ({error})")
        silenciar(raiz)
        return raiz

    # -- Protocol Interaccion --

    @property
    def ocupado(self):
        return self._director.activa

    def _cerca(self, x, z):
        return math.hypot(x - self.x, z - self.z) <= RADIO_USO

    def aviso(self, jugador, x, z):
        if self.ocupado or not self._cerca(x, z):
            return None
        if self._mensaje:
            return self._mensaje
        pista = self.pista_mision() if callable(self.pista_mision) else None
        return f"E: usar el computador ({(self.caso.terminal or {}).get('nombre', 'terminal')})" + (f" · {pista}" if pista else "")

    def usar(self, jugador, economia=None):
        if self.ocupado or not self._cerca(jugador.x, jugador.z):
            return False
        escena = self._escena
        if getattr(escena.flujo, "game_state", None) is None:
            self.decir(NO_DISPONIBLE)
            return True
        avatar = escena.avatar_de(jugador)
        if avatar is None or escena._cinematica:
            return False
        self._jugador = jugador
        self._empezar(jugador, avatar)
        return True

    def actualizar(self, dt):
        if self._mensaje:
            self._t_mensaje -= dt
            if self._t_mensaje <= 0:
                self._mensaje = None

    def decir(self, texto):
        self._mensaje, self._t_mensaje = texto, SEGUNDOS_MENSAJE

    def saltar(self):
        return self._director.saltar() if self.ocupado else False

    def destruir(self):
        from frontend.componentes import destruir_arbol
        destruir_arbol(self.raiz)

    # -- Animación --

    def _local(self, lx, ly, lz):
        x, z = calc.local_a_mundo(self.x, self.z, self.rumbo, lx, lz)
        return (x, self.raiz.y + ly, z)

    def _empezar(self, jugador, avatar):
        from frontend import entrada_terminal_calculos as etc
        if etc.activa():                      # entrada suave (ALCALDE_ENTRADA_TERMINAL_SUAVE=0 vuelve a la de siempre)
            return self._empezar_suave(jugador, avatar)
        escena = self._escena
        escena._cinematica = True
        escena.camara.tomar_control()
        avatar.automatico = False
        avatar.etiqueta.enabled = False
        escena._sincronizar_raton()
        inicio = (jugador.x, jugador.z)
        puerta = calc.local_a_mundo(self.x, self.z, self.rumbo, 0, APROXIMACION)
        silla = calc.local_a_mundo(self.x, self.z, self.rumbo, 0, ASIENTO)
        rumbo_sentado = self.rumbo + 180
        cam0 = (tuple(camera.position), camera.rotation_x, camera.rotation_y)
        objetivo = self._local(*PANTALLA)
        hombro, via, fin = self._local(*HOMBRO), self._local(*VIA), self._local(*FIN_CAMARA)
        rumbo_ir = math.degrees(math.atan2(puerta[0] - inicio[0], puerta[1] - inicio[1]))

        def caminar(t):
            k = ease_in_out(t)
            avatar.colocar(lerp(inicio[0], puerta[0], k), lerp(inicio[1], puerta[1], k))
            avatar.fijar_rumbo(rumbo_ir)
            avatar.aplicar_pose(poses.pose_caminar(poses.fase_siguiente(0, 3.0, t * calc.DURACION_CAMINAR), 0.45))

        def sentarse(t):
            k = ease_in_out(t)
            avatar.colocar(lerp(puerta[0], silla[0], k), lerp(puerta[1], silla[1], k))
            avatar.fijar_rumbo(lerp_angulo(rumbo_ir, rumbo_sentado, k))
            avatar.aplicar_pose(poses.interpolar_pose(poses.POSE_PARADO, poses.POSE_SENTADO, k))
            camera.position = lerp_vec3(cam0[0], hombro, k)
            pitch, yaw = cc.rotacion_mirando(camera.position, objetivo)
            camera.rotation = (lerp(cam0[1], pitch, k), lerp_angulo(cam0[2], yaw, k), 0)

        def acercar(t):
            k = ease_in_out(t)
            avatar.aplicar_pose(poses.pose_teclear(t * 2 * math.pi))
            pos = tuple((1 - k) ** 2 * hombro[i] + 2 * (1 - k) * k * via[i] + k ** 2 * fin[i] for i in range(3))
            camera.position = pos
            camera.rotation = (*cc.rotacion_mirando(pos, objetivo), 0)
            camera.fov = lerp(65, FOV_MONITOR, k)

        def glitch(t):
            if self._glitch is not None:
                self._glitch.poner(t)

        self._director.reproducir(
            calc.plan_sentarse(), {"caminar": caminar, "sentarse": sentarse, "acercar": acercar, "glitch": glitch},
            al_terminar=self._entrar, escala=escena.escala_tiempo)

    # Entrada suave (frontend/entrada_terminal_calculos.py): giro previo, paseo a velocidad de marcha con las piernas
    # sincronizadas, una sola trayectoria de cámara con aceleración y frenado, mirada y FOV que cambian poco a poco,
    # poses fundidas entre tramos y glitch con curva y meseta.
    def _empezar_suave(self, jugador, avatar):
        from frontend import entrada_terminal_calculos as etc
        escena = self._escena
        fov0 = float(camera.fov)              # antes de tomar_control, que lo devuelve a 65 de golpe
        cam0 = tuple(camera.position)
        escena._cinematica = True
        escena.camara.tomar_control()
        camera.fov = fov0
        avatar.automatico = False
        avatar.etiqueta.enabled = False
        escena._sincronizar_raton()
        inicio = (jugador.x, jugador.z)
        puerta = calc.local_a_mundo(self.x, self.z, self.rumbo, 0, APROXIMACION)
        silla = calc.local_a_mundo(self.x, self.z, self.rumbo, 0, ASIENTO)
        rumbo_sentado = self.rumbo + 180
        distancia = math.hypot(puerta[0] - inicio[0], puerta[1] - inicio[1])
        rumbo_ir = (math.degrees(math.atan2(puerta[0] - inicio[0], puerta[1] - inicio[1])) if distancia > 1e-3
                    else rumbo_sentado)
        rumbo0 = float(getattr(avatar, "rumbo", rumbo_ir) or 0.0)
        giro = etc.diferencia_angular(rumbo0, rumbo_ir)
        plan = etc.plan(distancia, giro)
        dur = dict(plan)
        inicio_tramo, acumulado = {}, 0.0
        for nombre, segundos in plan:
            inicio_tramo[nombre] = acumulado
            acumulado += segundos
        duracion_camara = acumulado - dur["glitch"]
        objetivo = self._local(*PANTALLA)
        hombro, via, fin = self._local(*HOMBRO), self._local(*VIA), self._local(*FIN_CAMARA)
        y_suelo = self.raiz.y
        # Toma intermedia entre la de partida y el hombro, más alta: la cámara acompaña el paseo sin cruzar al avatar.
        acompanar = etc.punto_acompanar(cam0, hombro)
        # Cada toma a su tiempo: la intermedia al acabar el paseo, el hombro al acabar de sentarse, el monitor al final.
        fin_paseo = inicio_tramo["sentarse"]
        fin_sentarse = inicio_tramo["acercar"]
        camino = etc.TrayectoriaCamara(
            [cam0, acompanar, hombro, via, fin], duracion_camara,
            tiempos=[0.0, fin_paseo, fin_sentarse, fin_sentarse + 0.55 * dur["acercar"], duracion_camara])
        fase_fin = etc.fase_piernas(distancia)

        def cabeza():
            return (avatar.x, y_suelo + 1.45, avatar.z)

        def poner_camara(nombre, t):
            tiempo = inicio_tramo[nombre] + t * dur[nombre]
            pos = camino.posicion(tiempo)
            camera.position = pos
            camera.rotation = (*cc.rotacion_mirando(pos, camino.mirada(tiempo, cabeza(), objetivo)), 0)
            camera.fov = etc.fov(tiempo / duracion_camara, fov0, FOV_MONITOR)

        def girar(t):
            avatar.colocar(*inicio)
            avatar.fijar_rumbo(rumbo0 + giro * etc.suavizar(t))
            avatar.aplicar_pose(poses.pose_caminar(0.0, 0.0))
            poner_camara("girar", t)

        def caminar(t):
            k = etc.avance_paseo(t)
            avatar.colocar(lerp(inicio[0], puerta[0], k), lerp(inicio[1], puerta[1], k))
            avatar.fijar_rumbo(rumbo_ir)
            avatar.aplicar_pose(poses.pose_caminar(etc.fase_piernas(distancia * k), etc.intensidad_marcha(t)))
            poner_camara("caminar", t)

        def sentarse(t):
            k = etc.suavizar(t)
            avatar.colocar(lerp(puerta[0], silla[0], k), lerp(puerta[1], silla[1], k))
            avatar.fijar_rumbo(lerp_angulo(rumbo_ir, rumbo_sentado, k))
            avatar.aplicar_pose(poses.interpolar_pose(poses.pose_caminar(fase_fin, 0.0), poses.POSE_SENTADO, k))
            poner_camara("sentarse", t)

        def acercar(t):
            fundido = etc.suavizar(t / etc.FUNDIDO_POSE)
            avatar.aplicar_pose(poses.interpolar_pose(poses.POSE_SENTADO, poses.pose_teclear(t * 2 * math.pi), fundido))
            poner_camara("acercar", t)

        def glitch(t):
            camera.fov = FOV_MONITOR - 4.0 * etc.suavizar(t)          # la cámara «entra» en la pantalla
            if self._glitch is not None:
                self._glitch.poner(etc.intensidad_glitch(t))

        self._director.reproducir(
            plan, {"girar": girar, "caminar": caminar, "sentarse": sentarse, "acercar": acercar, "glitch": glitch},
            al_terminar=self._entrar, escala=escena.escala_tiempo)

    def _entrar(self):
        try:
            self._abrir(self.caso)
        except BaseException:
            if self._glitch is not None:
                self._glitch.cancelar()
            self._escena._restablecer_tras_cinematica()
            self._escena._sincronizar_raton()
            raise

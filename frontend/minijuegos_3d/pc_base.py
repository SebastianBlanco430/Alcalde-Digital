# Presentación 3D común de la familia PC (Chat del barrio y Contrarreloj). Sobre Minijuego3D (base.py, de infra-3d):
#
#   - la vista 2D de HOY en el monitor de la oficina (la pinta la base: textura + mouse redirigido);
#   - cuarto más rico (ventana, estante, afiche, taza, planta) y escritorio con un ratón CLARO que se mueve con el puntero y
#     un teclado claro que resalta la tecla pulsada (pc_escritorio.py);
#   - toma sobre el hombro propia (pc_calculos.toma_hombro): monitor a FRACCION_PC del alto (legibilidad), nuca y hombro
#     abajo a la izquierda sin tapar el contenido;
#   - entrada: la cámara sigue desde donde acabó la cinemática de sentarse (el monitor llenando la pantalla) y retrocede al
#     hombro; salida: se reclina un instante y se levanta; después, el banner de resultado de siempre.
# Nada de esto decide nada: la vista 2D recibe las mismas teclas y clics que hoy y da el mismo ResultadoMinijuego.

from frontend.minijuegos_3d import pc_calculos as calc
from frontend.minijuegos_3d import raton
from frontend.minijuegos_3d.base import ADELANTE_SENTADO, Minijuego3D
from frontend.minijuegos_3d.camaras import aspecto_ventana
from frontend.minijuegos_3d.poses_calculos import seguir

RAPIDEZ_RATON = 14.0              # 1/s: la misma que la mano (poses_3d.RAPIDEZ_MANO): ratón y mano van pegados
ALTURA_CADERA = 0.97              # m sobre el origen del cuerpo: pivote del reclinado (la pelvis del .glb de pie)
DURACION_A_SALIDA = 0.7           # s de la cámara hacia la toma de salida
FOV_ESTABLECIMIENTO = 54.0        # entrada animada (sesión B): la toma abierta de la salida, algo más cerrada
# Velo de entrada: el color del destello de la cinemática de sentarse (EscenaInterior.COLOR_DESTELLO) cubre los primeros
# frames del 3D (los huesos aún no se han dibujado y los brazos salen en la pose de la animación, no en el ratón y el
# teclado: visto en rework-3d/capturas/chat/flujo3/flujo_c_000.png) y se desvanece cuando la IK ya colocó las manos.
COLOR_VELO = (200, 245, 255)
FRAMES_VELO = 10
DURACION_VELO = 0.25


class MinijuegoPC(Minijuego3D):

    FAMILIA = "pc"
    FRACCION = calc.FRACCION_PC
    MOSTRAR_AYUDA = True

    def __init__(self, contexto):
        super().__init__(contexto)
        self.escritorio = None
        self._uv = (0.5, 0.5)
        self._raton_xz = (0.0, 0.0, 0.0)  # el ratón arranca en su casa (centro del monitor)
        self._dt = 1 / 60
        self._salida_t = None
        self._banner = None               # el banner de la escena mientras lo escondemos durante la salida
        self._asiento = None
        self._velo = None
        self._velo_frames = 0
        self._velo_alfa = 1.0

    # -- Tomas --

    def _monitor(self):
        return self.set.anclas["monitor"].datos_toma()

    def _rol(self):
        return getattr(self.set.personaje, "rol", None)

    def toma_juego(self):
        return calc.toma_hombro(self._monitor(), aspecto_ventana(), self.FRACCION, rol=self._rol())

    def toma_salida(self):
        return calc.toma_abierta(self._monitor(), aspecto_ventana(), calc.SALIDA_PC)

    def toma_establecimiento(self):
        """Entrada animada (sesión B): empieza en la toma ABIERTA de la salida (por detrás y a la derecha: el personaje
        entero, la silla y el escritorio), algo más cerrada, y se acerca al hombro. La del módulo (la toma de juego
        retrocedida, fov 34) es un teleobjetivo: el personaje pasaba pegado a la cámara (capturas m3_chat_per)."""
        abierta = self.toma_salida()
        return {"position": tuple(abierta["position"]), "target": tuple(abierta["target"]), "fov": FOV_ESTABLECIMIENTO}

    def toma_inicial(self):
        """El monitor llenando la pantalla en el eje de la toma de juego: la base hace el travelling recto hasta el hombro
        (CamaraMinijuego.ir_a, DURACION_ENTRADA) y al llegar marca listo."""
        return calc.toma_entrada(self._monitor(), aspecto_ventana(), rol=self._rol())

    # -- Construcción --

    def construir(self):
        from frontend.minijuegos_3d.pc_escritorio import Escritorio
        self.escritorio = Escritorio(self.set.raiz, self.set.nueva)
        self._velo = self._crear_velo()
        if self.set.asiento is not None:
            x, z, rumbo = self.set.asiento
            self._asiento = (x, z + ADELANTE_SENTADO, rumbo)
        self.construir_pc()

    @staticmethod
    def _crear_velo():
        from ursina import Entity, camera, color
        return Entity(parent=camera.ui, model="quad", color=color.rgba32(*COLOR_VELO, 255), scale=(4, 4), z=-85)

    def _avanzar_velo(self, dt):
        velo = self._velo
        if velo is None:
            return
        self._velo_frames += 1
        if self._velo_frames <= FRAMES_VELO:
            return
        self._velo_alfa -= dt / DURACION_VELO
        if self._velo_alfa <= 0:
            self._quitar_velo()
            return
        from ursina import color
        velo.color = color.rgba32(*COLOR_VELO, int(255 * self._velo_alfa))

    def _quitar_velo(self):
        velo, self._velo = self._velo, None
        if velo is not None:
            from frontend.componentes import destruir_arbol
            destruir_arbol(velo)

    def construir_pc(self):
        """Para las subclases (Chat, Contrarreloj): piezas propias. Por defecto nada."""

    # -- Cada frame --

    def avanzar(self, dt):
        self._dt = dt
        super().avanzar(dt)

    def imitar_pc(self):
        """La mano derecha mueve el ratón CLARO de la mesa con el puntero sobre el monitor (ratón y mano pegados)."""
        if self.escritorio is None or self._salida_t is not None:
            return
        ultimo = raton.ultimo()
        if ultimo is not None and ultimo[0] is self.superficie:
            self._uv = (ultimo[1][0], ultimo[1][1])          # fuera del monitor el ratón se queda donde estaba
        objetivo = calc.desplazamiento_raton(*self._uv)
        actual = seguir(self._raton_xz, (objetivo[0], 0.0, objetivo[1]), self._dt, RAPIDEZ_RATON)
        self._raton_xz = actual
        centro = self.escritorio.colocar_raton(actual[0], actual[2])
        mano = calc.posicion_mano(centro)
        self.poses.mano_a((mano[0], mano[1] - self.escritorio.hundido_clic(), mano[2]), lado="d")

    def avanzar_3d(self, dt):
        self._avanzar_velo(dt)
        if self.escritorio is not None:
            self.escritorio.avanzar(dt)
        if self._salida_t is not None:
            self._avanzar_salida(dt)
        self.avanzar_pc(dt)

    def avanzar_pc(self, dt):
        """Para las subclases."""

    def al_tecla(self, k):
        if self.escritorio is None or self._salida_t is not None or self.resultado_3d is not None:
            return
        if k == "left mouse down":
            self.escritorio.clic()
        else:
            self.escritorio.pulsar_tecla(k)

    # -- Entrada animada (sesión B, ALCALDE_ANIM_SILLA): las manos terminan donde las pone imitar_pc (sin salto) --

    def manos_entrada(self):
        if self.escritorio is None:
            return None
        manos = {"d": tuple(calc.posicion_mano(self.escritorio.centro))}
        teclado = self.set.anclas.get("teclado")
        if teclado is not None:
            manos["i"] = tuple(teclado.mundo(-0.14, 0.03, -0.05))
        return manos

    # -- Salida: se levanta (sesión B: saca la silla, se levanta y la empuja; hoy: se reclina y se levanta) y después
    #    el banner de siempre --

    def al_resultado(self, resultado):
        escena = getattr(self.ctx, "escena", None)
        banner = getattr(escena, "banner", None)
        if banner is not None:
            banner.enabled = False
            self._banner = banner
        if self.salida_silla(al_terminar=self._mostrar_banner, toma_final=self.toma_salida()):
            return
        self._salida_t = 0.0
        self.poses.soltar_mano("d")
        self.poses.soltar_mano("i")
        self.camara.ir_a(self.toma_salida(), DURACION_A_SALIDA)

    def _avanzar_salida(self, dt):
        self._salida_t += dt
        s = calc.salida(self._salida_t)
        p = self.set.personaje
        cuerpo = getattr(p, "cuerpo", None)
        if self._asiento is not None and cuerpo is not None and self.poses.sentado:
            x, z, rumbo = self._asiento
            giro = -s["reclinar"]                               # rotation_x positivo = hacia delante
            dy, dz = calc.compensar_pivote(giro, ALTURA_CADERA)
            cuerpo.rotation_x = giro
            cuerpo.position = (0, -0.45 + s["subida"] + dy, dz)
            p.colocar(x, z - s["retroceso"])
            if s["fase"] == "de_pie":
                cuerpo.rotation_x = 0
                self.poses.de_pie(x, z - s["retroceso"], rumbo)
        if s["banner"]:
            self._mostrar_banner()

    def al_rescatar_secuencia(self):
        super().al_rescatar_secuencia()
        self._mostrar_banner()           # la salida animada falló: el banner de siempre, ya

    def _mostrar_banner(self):
        banner, self._banner = self._banner, None
        if banner is not None:
            try:
                banner.enabled = True
            except Exception:            # noqa: BLE001  el banner ya no existe (la escena siguió): nada que enseñar
                pass

    def destruir(self):
        self._mostrar_banner()           # nunca se queda escondido el banner de siempre (respaldo, cierre a mitad)
        try:
            self._quitar_velo()          # ni el velo de entrada tapando el 2D
        except Exception:                # noqa: BLE001
            pass
        try:
            cuerpo = getattr(self.set.personaje, "cuerpo", None) if self.set is not None else None
            if cuerpo is not None:
                cuerpo.rotation_x = 0
        except Exception:                # noqa: BLE001
            pass
        self.destruir_pc()

    def destruir_pc(self):
        """Para las subclases."""

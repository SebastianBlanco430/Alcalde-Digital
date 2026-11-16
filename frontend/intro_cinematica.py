# Cinemática de la intro (Ursina): escenas 1-5 del guion de la bóveda (00-Proyecto/guion-cinematica-intro.md) con el motor
# del juego. La lanza frontend/registro_tutorial.py al empezar una partida LOCAL NUEVA (nunca al «Continuar» ni en línea);
# al terminar, el registro abre la escena 6 (el recorrido del HUD con las viñetas «foco» de siempre).
#
#   - Plan, tiempos y textos: frontend/intro_calculos.py (puro, con tests). Tomas de cámara: frontend/guion_cinematicas.py.
#     Lo ejecuta un DirectorCinematica: un tramo por globo, así Espacio / Enter / clic pasan al siguiente globo y Escape
#     salta TODA la cinemática (también el recorrido).
#   - Durante las escenas 1-5: escena._cinematica = True (reloj parado, sin pausa, controles congelados), el HUD
#     escondido (hud.visible = False: los vigías siguen corriendo), la cámara tomada y TODOS los avatares escondidos (si
#     el jugador eligió ciudadano o influencer no se ve un doble).
#   - LIMPIEZA: todo lo que se crea cuelga de dos raíces (raiz3d en `scene`, raizui en camera.ui); limpiar() las destruye
#     con sus hijos y restaurar() deja la escena como estaba. Se llama al terminar, al saltar y si algo falla; si falla,
#     `al_fallo(error)` deja al registro abrir las viñetas de antes (nunca pantalla negra ni controles bloqueados).

import sys

from ursina import Entity, Text, camera, color, destroy, scene, time

from backend.logica.roles import ROLES
from frontend import diseno_adaptable, estilo, guion_cinematicas as gc, intro_calculos as ic, modelo_calculos as mc, tipografia
from frontend.cinematica import ease_in_out, lerp_angulo
from frontend.componentes import destruir_arbol, escala_fuente, rgb
from frontend.director_cinematica import DirectorCinematica
from frontend.globo_dialogo import GloboDialogo

ROL_DE = {"Ciudadano": "ciudadano", "Influencer": "influencer"}
SUAVIZADO_CAMARA = 5.0          # 1/s: la cámara alcanza su toma (si Espacio adelanta un globo no hay salto)
PX_TITULO = 46
Y_TITULO = 0.06
Z_CAPA = -0.95                  # por delante de todo lo de camera.ui


def _aviso(texto):
    print(f"[intro] {texto}", file=sys.stderr)


class IntroCinematica(Entity):
    """`escena`: EscenaMundo. `guion`: intro_calculos.cargar_guion(). `al_terminar(saltada)`: una vez, ya limpio.
    `al_fallo(error)`: una vez, ya limpio, si algo lanzó. `escala`: multiplica las duraciones (0 = instantánea)."""

    def __init__(self, escena, guion, al_terminar, al_fallo=None, fase=ic.FASE_MINIMA, escala=1.0, **opciones):
        super().__init__(parent=camera.ui, **opciones)
        self.escena = escena
        self.guion = guion
        self._al_terminar = al_terminar
        self._al_fallo = al_fallo
        self.terminada = False
        self.saltada = False
        self._restaurado = True
        self._previo = None
        self.raiz3d = self.raizui = self.director = None
        self.actores = {}
        self._camara_meta = None
        self._camara_ya = False
        self._cola_guardia = 3
        self.pasos = ic.plan_intro(guion, fase)
        try:
            self._preparar()
            self._construir()
            self.director.reproducir(ic.plan_director(self.pasos), self._animaciones(), al_terminar=self._fin, escala=escala)
        except Exception:
            self.limpiar()
            destroy(self)                        # ni la entidad vacía queda: el registro abre las viñetas
            raise

    # -- Estado de la escena: se toma al empezar y se devuelve en restaurar() (idempotente) --------------------------

    def _preparar(self):
        escena = self.escena
        avatares = list(getattr(escena, "avatares", {}).values())
        self._previo = {"cinematica": bool(getattr(escena, "_cinematica", False)),
                        "hud": bool(getattr(escena.hud, "visible", True)),
                        "avatares": [(a, a.enabled) for a in avatares],
                        "fov": camera.fov}
        self._restaurado = False
        escena._cinematica = True
        escena.hud.visible = False
        for avatar, _ in self._previo["avatares"]:
            avatar.enabled = False
        escena.camara.tomar_control()
        self._sincronizar_raton()

    def restaurar(self):
        if self._restaurado or self._previo is None:
            return
        self._restaurado = True
        escena, previo = self.escena, self._previo
        pasos = (lambda: setattr(escena, "_cinematica", previo["cinematica"]),
                 lambda: setattr(escena.hud, "visible", previo["hud"]),
                 lambda: [setattr(a, "enabled", estaba) for a, estaba in previo["avatares"] if a and not a.is_empty()],
                 lambda: setattr(camera, "fov", previo["fov"]),
                 escena.camara.soltar_control,
                 escena.camara.colocar_ya,
                 self._sincronizar_raton)
        for paso in pasos:              # cada paso por separado: que uno falle no deja a medias los demás
            try:
                paso()
            except Exception as error:
                _aviso(f"restaurar: {type(error).__name__}: {error}")

    def _sincronizar_raton(self):
        try:
            self.escena._sincronizar_raton()
        except Exception:
            pass

    # -- Construcción -----------------------------------------------------------------------------------------------

    def _construir(self):
        mundo = self.escena._mundo
        centro = gc.centro_fuente(mundo)
        if centro is None:
            raise ValueError("el mundo no tiene la plaza de la fuente")
        self.tomas = gc.tomas_plaza(centro, mundo.altura)
        self.raiz3d = Entity(parent=scene)
        self.raizui = Entity(parent=camera.ui, z=Z_CAPA)
        self.telon = Entity(parent=self.raizui, model="quad", scale=(4.0, 2.0), z=0.02, color=color.rgba(0, 0, 0, 0))
        self.contenido = Entity(parent=self.raizui)              # lo que escala con la ventana (títulos y globos)
        titulo = self.guion["_escenas"]["titulo"]["titulo"]
        self.titulo = Text(titulo, parent=self.contenido, origin=(0, 0), position=(0, Y_TITULO, -0.01),
                           scale=escala_fuente(PX_TITULO), color=color.rgba(1, 1, 1, 0), font=tipografia.FUENTE_TITULO)
        self.globo = GloboDialogo(parent=self.contenido)
        self.ayuda = Text(self.guion.get("ayuda", ""), parent=self.contenido, origin=(0.5, 0), position=(0.5 * diseno_adaptable.aspecto() - 0.03, -0.47, -0.01),
                          scale=escala_fuente(14), color=color.rgba(1, 1, 1, 0.75))
        diseno_adaptable.ajustar_escala(self.contenido)
        for hablante, (x, z, rumbo) in self.tomas["actores"].items():
            self.actores[hablante] = self._crear_actor(hablante, x, z, rumbo)
        camera.fov = self.tomas["fov"]
        self.director = DirectorCinematica(parent=self)

    def _crear_actor(self, hablante, x, z, rumbo):
        from frontend.personaje_modelo import crear_personaje
        rol = ROL_DE[hablante]
        actor = crear_personaje(hablante, rol, ROLES[rol].color, parent=self.raiz3d)
        actor.suelo = self.escena._mundo.altura
        actor.automatico = False
        actor.colocar(x, z)
        actor.fijar_rumbo(rumbo)
        actor.resaltar(False)
        if getattr(actor, "etiqueta", None) is not None:
            actor.etiqueta.enabled = False
        if getattr(actor, "aro", None) is not None:
            actor.aro.enabled = False
        self._clip(actor, mc.IDLE)
        return actor

    @staticmethod
    def _clip(actor, clip):
        poner = getattr(actor, "_poner_clip", None)        # el muñeco procedural (si falta el .glb) no tiene clips
        if callable(poner):
            poner(clip, 1.0)

    # -- Tramos -----------------------------------------------------------------------------------------------------

    def _animaciones(self):
        animaciones = {}
        for paso in self.pasos:
            animaciones[paso.nombre] = self._seguro(lambda t, p=paso: self._tramo(p, t))
        return animaciones

    def _seguro(self, fn):
        def envuelta(t):
            if self.terminada:
                return
            try:
                fn(t)
            except Exception as error:
                self._fallar(error)
        return envuelta

    def _tramo(self, paso, t):
        if paso.escena == "plaza":
            self._camara_meta = gc.camara_plaza(self.tomas, ic.progreso_escena(self.pasos, paso.nombre, t))
            if not self._camara_ya:              # primer fotograma: la cámara empieza YA en la toma alta
                self._camara_ya = True
                self._poner_camara(*self._camara_meta)
        if paso.tipo == "globo":
            self._tramo_globo(paso, t)
        elif paso.nombre == "plaza_fundido":
            self._telon(ease_in_out(t))
        elif paso.nombre == "titulo_entrada":
            self._telon(1.0)
            self._alfa_titulo(t)
        elif paso.nombre == "titulo_salida":
            self._alfa_titulo(1.0 - t)
        elif paso.nombre == "periodista_salida":
            if t <= 0.0:
                self._quitar_actores()
                self.restaurar()                 # el juego aparece debajo del negro, con el HUD, para el recorrido
            self._telon(1.0 - ease_in_out(t))
        elif paso.tipo == "pausa":
            self.globo.ocultar()

    def _tramo_globo(self, paso, t):
        globo = paso.globo
        if paso.escena in ("titulo", "periodista"):
            self._telon(1.0)
        if t >= 1.0:
            self.globo.ocultar()
            for actor in self.actores.values():
                self._clip(actor, mc.IDLE)
            return
        if self.globo.cadena != globo.texto or self.globo.hablante != globo.hablante:
            estilo_globo = "bajo_titulo" if paso.escena == "titulo" else "dialogo"
            self.globo.mostrar(globo.hablante, globo.texto, estilo_globo)
            for hablante, actor in self.actores.items():
                self._clip(actor, mc.HABLAR if hablante == globo.hablante else mc.IDLE)

    def _telon(self, alfa):
        self.telon.color = color.rgba(0, 0, 0, max(0.0, min(1.0, alfa)))

    def _alfa_titulo(self, alfa):
        self.titulo.color = color.rgba(1, 1, 1, max(0.0, min(1.0, alfa)))

    def _poner_camara(self, posicion, pitch, yaw):
        camera.position = posicion
        camera.rotation = (pitch, yaw, 0)

    def _quitar_actores(self):
        for actor in self.actores.values():
            destruir_arbol(actor)
        self.actores = {}

    # -- Frame y teclas ---------------------------------------------------------------------------------------------

    def update(self):
        if self.terminada:
            # Unos frames de guardia: el Escape que saltó la intro también llega a la escena y podría abrir la pausa.
            if self._cola_guardia > 0:
                self._cola_guardia -= 1
                if getattr(self.escena, "en_pausa", False):
                    self.escena.alternar_pausa(False)
            else:
                self.enabled = False
            return
        if self._camara_meta is None or self._restaurado:
            return
        posicion, pitch, yaw = self._camara_meta
        k = min(1.0, SUAVIZADO_CAMARA * min(time.dt, 0.1))
        actual = tuple(camera.position)
        nueva = tuple(a + (b - a) * k for a, b in zip(actual, posicion))
        camera.position = nueva
        camera.rotation = (camera.rotation_x + (pitch - camera.rotation_x) * k, lerp_angulo(camera.rotation_y, yaw, k), 0)

    def input(self, key):
        if self.terminada:
            return
        if key in ("space", "enter", "left mouse down"):
            self.siguiente()
        elif key == "escape":
            self.saltar_todo()

    def siguiente(self):
        if self.director is not None and not self.terminada:
            self.director.saltar_tramo()

    def saltar_todo(self):
        if self.terminada:
            return
        self.saltada = True
        self._cerrar(lambda: self._al_terminar(True))

    # -- Final ------------------------------------------------------------------------------------------------------

    def _fin(self):
        self._cerrar(lambda: self._al_terminar(False))

    def _fallar(self, error):
        _aviso(f"falló a mitad ({type(error).__name__}: {error}); se abren las viñetas de siempre")
        self._cerrar(lambda: self._al_fallo(error) if self._al_fallo is not None else self._al_terminar(True))

    def _cerrar(self, aviso):
        if self.terminada:
            return
        self.terminada = True
        self.limpiar()
        try:
            aviso()
        except Exception as error:
            _aviso(f"aviso final: {type(error).__name__}: {error}")

    def limpiar(self):
        """Destruye TODO lo creado (actores, telón, títulos, globo y director) y devuelve la escena. Idempotente."""
        if self.director is not None:
            self.director.cancelar()
        self.actores = {}
        for raiz in (self.raiz3d, self.raizui, self.director):
            if raiz is not None:
                try:
                    destruir_arbol(raiz)
                except Exception as error:
                    _aviso(f"limpiar: {type(error).__name__}: {error}")
        self.raiz3d = self.raizui = self.director = None
        self._camara_meta = None
        self.restaurar()


def crear_intro(escena, guion, al_terminar, al_fallo=None, fase=None, escala=1.0):
    """Crea y arranca la intro. Lanza si no se puede construir (ya limpio): el registro abre entonces las viñetas."""
    return IntroCinematica(escena, guion, al_terminar, al_fallo, fase=ic.fase_intro() if fase is None else fase, escala=escala)

# Animaciones por código de silla, corcho y pantalla (Ursina). Contrato: sesiones-24nov/animaciones/contrato-silla.md
# (la firma NO cambia; solo se añaden argumentos opcionales). La matemática (guiones t -> Estado, duraciones, cámara,
# regla de la versión rápida, bandera) está en frontend/cinematica_silla_calculos.py, con tests puros.
#
#   sec = sentarse_en(personaje, silla, mesa, toma_final=..., clave="pc", al_terminar=..., entidad_silla=ent)
#   sec.saltar() / sec.cancelar() / sec.soltar() / sec.poses / sec.fallo / sec.duracion / sec.activa / sec.terminada
#
# Cada frame la Secuencia aplica Estado(t): personaje (posición, rumbo, pelvis y pies por IK con
# PosesPersonaje.postura, manos con mano_directa), silla (world_x/world_z), cámara (camera de Ursina o `camara.poner`) y el
# velo (glitch de la pantalla / velo negro de reducir movimiento). Al terminar, saltar o fallar se aplica Estado final
# exacto y se llama `al_terminar` una sola vez. Ninguna excepción interna sale hacia Ursina (solo la de `al_terminar`).
#
# Argumentos opcionales añadidos al contrato (todos por nombre):
#   limites=(xmin, xmax, zmin, zmax[, ymin, ymax])  caja de la sala (cámara y retiro de la silla).
#   avanzar_poses=True   False si quien llama ya hace poses.avanzar(dt) cada frame (Minijuego3D.avanzar lo hace).
#   aspecto=None         aspecto de la ventana para las tomas de pantalla (None = el de la ventana).
#   toma_inicial="establecimiento"   la toma de establecimiento del guion (toma_final retrocedida), en el primer frame.
#   toma_final= en entrar_a_pantalla: la toma «pantalla llena» (None = calculada de `pantalla`, fov 40).

import math

from frontend import cinematica_silla_calculos as calc
from frontend.cinematica_silla_calculos import Corcho, Mesa, Silla  # noqa: F401  (reexportados por comodidad)

_activas = []                        # secuencias en curso (la última es la más reciente)
_duenos = {}                         # id(poses) -> Secuencia que sostiene esa pose
_cuerpos = {}                        # rol -> calc.Cuerpo medido del esqueleto (por proceso)
_glitch = {"overlay": None}
_velo = {"entidad": None}


# -- Ayudas públicas -------------------------------------------------------------------------------------------------

def activa():
    """¿ALCALDE_ANIM_SILLA encendida? (se lee en cada llamada)."""
    return calc.activa()


def punto_de_partida(silla):
    return calc.punto_de_partida(silla)


def en_curso():
    return any(s.activa for s in _activas)


def saltar_activa():
    """Salta la secuencia en curso más reciente. True si había una."""
    for sec in reversed(list(_activas)):
        if sec.activa:
            return sec.saltar()
    return False


def crear_silla(parent, silla, color=(52, 56, 74)):
    """Silla estándar (asiento, respaldo, patas) suelta, con el origen en el suelo bajo el centro del asiento, ya colocada
    en `silla.posicion` y girada a `silla.rumbo`. Devuelve la Entity (se mueve con world_x/world_z)."""
    from ursina import Entity
    from ursina.shaders import lit_with_shadows_shader

    from frontend.componentes import rgb
    from frontend.piezas import pieza, silenciar
    raiz = Entity(parent=parent, shader=lit_with_shadows_shader, name="silla_cinematica")
    a = float(silla.altura_asiento)
    r = float(silla.altura_respaldo)
    ancho, prof, grosor = calc.ANCHO_ASIENTO, calc.PROF_ASIENTO, 0.05
    oscuro = tuple(max(0, int(c * 0.7)) for c in color)
    pieza(parent=raiz, model="cube", color=rgb(color), position=(0, a - grosor / 2, 0), scale=(ancho, grosor, prof))
    alto_resp = max(0.1, r - a - 0.12)
    pieza(parent=raiz, model="cube", color=rgb(color), position=(0, r - alto_resp / 2, -calc.RESPALDO_ATRAS),
          scale=(ancho, alto_resp, 0.04))
    for dx in (-ancho / 2 + 0.03, ancho / 2 - 0.03):
        pieza(parent=raiz, model="cube", color=rgb(oscuro), position=(dx, (r - a) / 2 + a, -calc.RESPALDO_ATRAS),
              scale=(0.03, r - a, 0.03))
        for dz in (-prof / 2 + 0.03, prof / 2 - 0.03):
            pieza(parent=raiz, model="cube", color=rgb(oscuro), position=(dx, (a - grosor) / 2, dz),
                  scale=(0.03, a - grosor, 0.03))
    raiz.combine()
    silenciar(raiz)
    raiz.world_rotation_y = float(silla.rumbo)
    raiz.world_position = (float(silla.posicion[0]), float(silla.suelo_y), float(silla.posicion[1]))
    return raiz


# -- Funciones del contrato ----------------------------------------------------------------------------------------

def sentarse_en(personaje, silla, mesa=None, *, toma_final, clave="silla", **op):
    mesa = mesa or Mesa()

    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_sentarse(silla, mesa, desde=desde, toma_final=toma_final, toma_inicial=inicial,
                                   rapida=rapida, cuerpo=cuerpo, limites=op.get("limites"))
    return _lanzar("sentarse_en", personaje, fabrica, clave, op, silla=silla)


def entrar_a_pantalla(personaje, silla, mesa, pantalla, *, clave="pantalla", **op):
    mesa = mesa or Mesa()
    llena = op.pop("toma_final", None)

    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_sentarse(silla, mesa, desde=desde, toma_final=None, toma_inicial=inicial, rapida=rapida,
                                   cuerpo=cuerpo, limites=op.get("limites"), secuencia="entrar_a_pantalla",
                                   pantalla=pantalla, aspecto=aspecto, rol=getattr(personaje, "rol", None),
                                   toma_llena=llena)
    return _lanzar("entrar_a_pantalla", personaje, fabrica, clave, op, silla=silla, glitch=True)


def salir_de_pantalla(personaje, silla, mesa, pantalla, *, toma_final, clave="pantalla", **op):
    mesa = mesa or Mesa()
    llena = op.pop("toma_llena", None)

    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_salir_pantalla(silla, mesa, pantalla, toma_final=toma_final, rapida=rapida, cuerpo=cuerpo,
                                         aspecto=aspecto, toma_llena=llena, limites=op.get("limites"))
    return _lanzar("salir_de_pantalla", personaje, fabrica, calc.clave_salida(clave), op, silla=silla, glitch=True,
                   recalcular=False)


def levantarse_de(personaje, silla, mesa=None, *, toma_final=None, hacia=None, clave="silla", **op):
    mesa = mesa or Mesa()

    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_levantarse(silla, mesa, desde_camara=inicial, toma_final=toma_final, hacia=hacia,
                                     rapida=rapida, cuerpo=cuerpo, limites=op.get("limites"))
    return _lanzar("levantarse_de", personaje, fabrica, calc.clave_salida(clave), op, silla=silla, recalcular=False)


def acercarse_a_corcho(personaje, corcho, *, toma_final, clave="corcho", **op):
    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_corcho(corcho, desde=desde, toma_final=toma_final, toma_inicial=inicial, rapida=rapida,
                                 cuerpo=cuerpo, limites=op.get("limites"), suelo_y=_suelo(personaje))
    return _lanzar("acercarse_a_corcho", personaje, fabrica, clave, op, recalcular=False)


def dejar_corcho(personaje, corcho, *, toma_final=None, hacia=None, clave="corcho", **op):
    def fabrica(cuerpo, rapida, desde, inicial, aspecto):
        return calc.guion_dejar_corcho(corcho, desde=desde, desde_camara=inicial, toma_final=toma_final, hacia=hacia,
                                       rapida=rapida, cuerpo=cuerpo, limites=op.get("limites"),
                                       suelo_y=_suelo(personaje))
    return _lanzar("dejar_corcho", personaje, fabrica, calc.clave_salida(clave), op, recalcular=False)


# -- Lanzamiento -----------------------------------------------------------------------------------------------------

_OPCIONES = {"toma_inicial", "rapida", "al_terminar", "entidad_silla", "poses", "camara", "auto", "limites",
             "avanzar_poses", "aspecto"}


def _suelo(personaje):
    try:
        return float(personaje.world_position[1])
    except Exception:                    # noqa: BLE001
        return 0.0


def _lanzar(nombre, personaje, fabrica, clave, op, silla=None, glitch=False, recalcular=True):
    desconocidas = set(op) - _OPCIONES
    if desconocidas:
        raise TypeError(f"{nombre}: argumentos desconocidos {sorted(desconocidas)}")
    rapida = calc.decidir_rapida(clave, op.get("rapida"))
    sec = Secuencia(nombre, personaje, fabrica, rapida=rapida, clave=clave, silla=silla, glitch=glitch,
                    recalcular=recalcular, **{k: v for k, v in op.items() if k not in ("rapida", "limites", "aspecto")},
                    aspecto=op.get("aspecto"))
    sec._arrancar()
    return sec


# -- Velos en camera.ui ----------------------------------------------------------------------------------------------

def _overlay_glitch():
    o = _glitch["overlay"]
    if o is not None:
        try:
            if not o.is_empty():
                return o
        except Exception:                # noqa: BLE001
            pass
    from frontend.mundo_digital_glitch import GlitchOverlay
    o = GlitchOverlay()
    _glitch["overlay"] = o
    return o


def _velo_negro():
    v = _velo["entidad"]
    if v is not None:
        try:
            if not v.is_empty():
                return v
        except Exception:                # noqa: BLE001
            pass
    from ursina import Entity, camera, color
    v = Entity(parent=camera.ui, model="quad", scale=(4, 4), z=-96, color=color.rgba32(0, 0, 0, 0), enabled=False)
    _velo["entidad"] = v
    return v


def _poner_velo_negro(alfa):
    from ursina import color
    v = _velo_negro()
    alfa = max(0.0, min(1.0, alfa))
    v.color = color.rgba32(0, 0, 0, int(round(255 * alfa)))
    v.enabled = alfa > 0.0


def _reducir_movimiento():
    try:
        from frontend.banderas_visuales import reducir_movimiento
        return bool(reducir_movimiento())
    except Exception:                    # noqa: BLE001
        return False


def _aspecto():
    try:
        from ursina import window
        return float(window.aspect_ratio)
    except Exception:                    # noqa: BLE001
        return 16 / 9


# -- Secuencia -------------------------------------------------------------------------------------------------------

class Secuencia:
    """Una animación en curso (ver contrato §3). Se crea con las funciones del módulo, no a mano."""

    def __init__(self, nombre, personaje, fabrica, *, rapida=False, clave="", silla=None, glitch=False, recalcular=True,
                 toma_inicial=None, al_terminar=None, entidad_silla=None, poses=None, camara=None, auto=True,
                 avanzar_poses=True, aspecto=None):
        self.nombre = nombre
        self.personaje = personaje
        self.clave = clave
        self.rapida = rapida
        self.activa = False
        self.terminada = False
        self.fallo = False
        self.duracion = 0.0
        self.t = 0.0
        self.guion = None
        self._fabrica = fabrica
        self._silla_desc = silla
        self._glitch = glitch
        self._recalcular = recalcular
        self._toma_inicial = toma_inicial
        self._al_terminar = al_terminar
        self._llamado = False
        self._entidad_silla = entidad_silla
        self.poses = poses
        self._camara = camara
        self.auto = auto
        self._avanzar_poses = avanzar_poses
        self._aspecto = aspecto
        self._motor = None
        self._cancelada = False
        self._sosteniendo = False
        self._reducido = False
        self._t_corte = None             # reducir movimiento: t en que se cortó al estado final (None = aún no)
        self._medido = False
        self._guardado_poses = None
        self._desde = None
        self._inicial = None
        self._manos_aplicadas = set()
        self.final = None

    # -- Arranque --

    def _arrancar(self):
        try:
            self._preparar()
        except Exception as error:       # noqa: BLE001  ni el guion se pudo construir: lo mínimo y al_terminar
            self.fallo = True
            self.error = error
            self._sin_guion()
            return
        if not calc.activa():
            self._terminar(forzado=True)
            return
        self._reducido = _reducir_movimiento()
        self.activa = True
        _activas.append(self)
        try:
            if self._reducido:
                self.duracion = sum(calc.VELO_REDUCIDO)
                if self._toma_inicial is not None:
                    # Bajo el fundido del llamador (toma_inicial): corte YA al estado final con el velo entero, y el velo
                    # solo se quita. Antes la cámara se quedaba en la toma vieja mientras subía el velo y se veía un
                    # instante al abrirse el fundido (sesión E, pendiente de B).
                    self._cortar_reducido(0.0)
                else:
                    _poner_velo_negro(0.0)
            else:
                self._aplicar(self.guion.estado(0.0), 0.0)
        except Exception as error:       # noqa: BLE001
            self._fallar(error)
            return
        if self.auto:
            self._crear_motor()

    def _preparar(self):
        if self.poses is None:
            from frontend.minijuegos_3d.poses_3d import PosesPersonaje
            self.poses = PosesPersonaje(self.personaje)
        anterior = _duenos.get(id(self.poses))
        if anterior is not None and anterior is not self:
            anterior._dejar_de_sostener()
        _duenos[id(self.poses)] = self
        self.poses._camino = None
        self._guardado_poses = (self.poses.__dict__.get("PASO_LATERAL", None), list(self.poses._planos),
                                getattr(self.poses, "tomar_continuo", False))
        self.poses.tomar_continuo = True         # tomar un brazo/pierna parte de su pose animada (sin chasquido)
        self.poses.PASO_LATERAL = False          # nada de pasos laterales propios mientras la secuencia manda
        self.poses._planos = []                  # las manos las acota el guion (los planos infinitos de la mesa no)
        self._desde = self._posicion_personaje()
        self._inicial = self._toma_de_partida()
        self._cuerpo = self._cuerpo_inicial()
        self._construir()

    def _construir(self):
        aspecto = self._aspecto or _aspecto()
        self.guion = self._fabrica(self._cuerpo, self.rapida, self._desde, self._inicial, aspecto)
        self.duracion = self.guion.duracion
        self.final = self.guion.final()

    def _posicion_personaje(self):
        p = self.personaje
        wp = p.world_position
        return (float(wp[0]), float(wp[2]), float(getattr(p, "rumbo", 0.0)))

    def _toma_de_partida(self):
        t = self._toma_inicial
        if isinstance(t, dict):
            return calc.copiar_toma(t)
        if t == "establecimiento" and self.nombre in ("sentarse_en", "entrar_a_pantalla", "acercarse_a_corcho"):
            return "establecimiento"
        return self._toma_actual()

    def _toma_actual(self):
        cam = self._camara
        actual = getattr(cam, "actual", None) if cam is not None else None
        if actual:
            return calc.copiar_toma(actual)
        from ursina import camera
        pos = camera.world_position
        fwd = camera.forward
        p = (float(pos[0]), float(pos[1]), float(pos[2]))
        f = (float(fwd[0]), float(fwd[1]), float(fwd[2]))
        if not (calc.finito(p) and calc.finito(f)) or calc._len(f) < 1e-6:
            f = (0.0, 0.0, 1.0)
        return calc.toma(p, calc._add(p, calc._mul(calc._unit(f), 3.0)), float(camera.fov))

    def _cuerpo_inicial(self):
        rol = getattr(self.personaje, "rol", None)
        medido = _cuerpos.get(rol)
        if medido is not None:
            self._medido = True
            return medido
        return calc.cuerpo_de_rol(rol)

    def _medir(self):
        """Primer frame con los huesos ya dibujados: mide brazo y hombro; si cambian la coreografía y aún se está a
        tiempo (primeros 0,15 s), reconstruye el guion con esas medidas."""
        if self._medido:
            return
        p = self.poses
        if not p.con_ik:
            self._medido = True
            return
        if not p._huesos_validos():
            return
        self._medido = True
        if p.sentado:                    # sentado el hombro no mide lo de pie: se queda con las medidas de partida
            return
        try:
            cad = p._cadenas["d"]
            alcance = p._alcance_de(cad)
            hombro = cad.pos(cad.nombres[0])[1] - p._base()[1]
            if not (math.isfinite(alcance) and math.isfinite(hombro)) or not (0.25 < alcance < 0.9) \
                    or not (0.9 < hombro < 1.8):
                return
            cuerpo = calc.Cuerpo(alcance=alcance, alto_hombro=hombro, alto_cabeza=hombro + 0.18,
                                 radio_cabeza=self._cuerpo.radio_cabeza)
            rol = getattr(self.personaje, "rol", None)
            if rol is not None:
                _cuerpos[rol] = cuerpo
            cambia = abs(cuerpo.alcance - self._cuerpo.alcance) > 0.02 or abs(cuerpo.alto_hombro -
                                                                                self._cuerpo.alto_hombro) > 0.03
            if cambia and self._recalcular and self.t <= 0.15 and not self._reducido:
                self._cuerpo = cuerpo
                self._construir()
        except Exception:                # noqa: BLE001  una medida rara no rompe nada: se queda con la de partida
            pass

    # -- Frame --

    def _crear_motor(self):
        from ursina import Entity, time

        sec = self

        class _Motor(Entity):
            def update(self):
                sec._tick(time.dt)
        self._motor = _Motor(name="cinematica_silla_motor")

    def _tick(self, dt):
        if self._cancelada:
            return
        if self.activa:
            self._paso(dt)
        elif self._sosteniendo and self._avanzar_poses:
            self._sostener(dt)

    def avanzar(self, dt):
        """auto=False: avanza la secuencia `dt` s (y, terminada, sostiene la pose)."""
        if self._cancelada:
            return
        if self.activa:
            self._paso(dt)
        elif self.terminada and self._avanzar_poses:
            self._sostener(dt)

    def _paso(self, dt):
        try:
            dt = float(dt)
            if not math.isfinite(dt) or dt < 0:
                dt = 0.0
            self.t += dt
            if self._reducido:
                sube, baja = calc.VELO_REDUCIDO
                if self._t_corte is None and self.t < sube:
                    _poner_velo_negro(self.t / sube)
                elif self._t_corte is None:
                    self._cortar_reducido(self.t)        # el frame del corte va con el velo entero
                else:
                    _poner_velo_negro(1.0 - (self.t - self._t_corte) / baja)
                if self._avanzar_poses:
                    self.poses.avanzar(dt)
            else:
                self._medir()
                if self.t >= self.duracion:
                    self._aplicar_final()
                else:
                    self._aplicar(self.guion.estado(self.t), dt)
                if self._avanzar_poses:
                    self.poses.avanzar(dt)
        except Exception as error:       # noqa: BLE001
            self._fallar(error)
            return
        if self.t >= self.duracion:
            self._terminar()

    def _cortar_reducido(self, t):
        """Reducir movimiento: estado final de golpe con el velo negro a 1 en ese mismo frame; el velo se quita en
        VELO_REDUCIDO[1] s desde aquí."""
        self._t_corte = t
        self.duracion = t + calc.VELO_REDUCIDO[1]
        _poner_velo_negro(1.0)
        self._aplicar_final()

    def _sostener(self, dt):
        if _duenos.get(id(self.poses)) is not self:
            self._sosteniendo = False
            return
        try:
            self.poses.avanzar(dt)
        except Exception:                # noqa: BLE001  sostener nunca rompe el bucle
            self._sosteniendo = False

    # -- Aplicar un Estado --

    def _aplicar(self, e, dt):
        p = self.personaje
        if not calc.finito((e.x, e.z, e.rumbo, e.bajada)):
            raise ValueError("estado no finito")
        if e.sentado:
            try:
                p.animar_caminar(0.0, dt)
            except Exception:            # noqa: BLE001
                pass
            self.poses.postura(e.x, e.z, e.rumbo, e.bajada, e.pies)
        else:
            self.poses.postura(e.x, e.z, e.rumbo, 0.0)
            try:
                p.animar_caminar(e.velocidad, dt)
            except Exception:            # noqa: BLE001
                pass
        self._aplicar_manos(e.manos, e)
        self._mirar(e.mirar)
        if self._entidad_silla is not None and e.silla is not None:
            if not calc.finito(e.silla):
                raise ValueError("silla no finita")
            self._entidad_silla.world_x = float(e.silla[0])
            self._entidad_silla.world_z = float(e.silla[1])
        if e.camara is not None:
            self._poner_camara(e.camara)
        if self._glitch:
            self._poner_glitch(e.velo)

    def _mirar(self, grados):
        mirar = getattr(self.poses, "mirar_arriba", None)
        if mirar is not None and (grados > 0 or getattr(self.poses, "_mirar", 0.0) > 0):
            mirar(grados)

    def _aplicar_manos(self, manos, e=None):
        """Manos del Estado. A mitad de secuencia, una mano ya tomada que el guion deja «libre» no se suelta (soltar y
        volver a tomar el brazo da un chasquido): va a su punto de reposo junto al costado. Se sueltan en el estado final
        (e=None)."""
        for lado in ("i", "d"):
            punto = manos.get(lado)
            if punto is not None and calc.finito(punto):
                self.poses.mano_directa(punto, lado)
                self._manos_aplicadas.add(lado)
            elif lado in self._manos_aplicadas and e is not None:
                reposo = self._reposo(lado, e)
                if reposo is not None:
                    self.poses.mano_a(reposo, lado)
            elif lado in self._manos_aplicadas or lado in manos:
                self.poses.soltar_mano(lado)
                self._manos_aplicadas.discard(lado)

    def _reposo(self, lado, e):
        try:
            p = self.poses.mano_reposo(lado)
        except Exception:                # noqa: BLE001
            p = None
        if p is None or not calc.finito(p):
            p = calc.mano_colgando(e.x, e.z, e.rumbo, lado, self._cuerpo, -e.bajada)
        return p

    def _poner_camara(self, toma):
        if not (calc.finito(toma["position"]) and calc.finito(toma["target"]) and math.isfinite(toma["fov"])):
            raise ValueError("toma no finita")
        cam = self._camara
        if cam is not None:
            poner = getattr(cam, "poner", None)
            if poner is not None:
                poner(toma)
                return
            cam.tomar(toma)
            return
        from ursina import camera

        from frontend.minijuegos_3d.camaras_calculos import rotacion_mirando
        camera.position = tuple(toma["position"])
        pitch, yaw = rotacion_mirando(toma["position"], toma["target"])
        camera.rotation = (pitch, yaw, 0)
        camera.fov = toma["fov"]

    def _poner_glitch(self, intensidad):
        try:
            o = _overlay_glitch()
            if intensidad > 0 or o.enabled:
                o.poner(intensidad)
        except Exception:                # noqa: BLE001  sin glitch: sigue sin él
            pass

    def _aplicar_final(self):
        """Estado final exacto. Cada parte por separado: si una falla (entidad destruida...) las demás se ponen igual."""
        e = self.final
        if e is None:
            return
        pasos = (lambda: self._aplicar_cuerpo_final(e),
                 lambda: self._aplicar_manos(e.manos),
                 lambda: self._mirar(e.mirar),
                 lambda: self._silla_final(e),
                 lambda: e.camara is not None and self._poner_camara(e.camara),
                 lambda: self._glitch and not self._reducido and self._poner_glitch(e.velo))
        for paso in pasos:
            try:
                paso()
            except Exception:            # noqa: BLE001  una parte rota (entidad destruida...) no impide las demás
                self.fallo = True

    def _aplicar_cuerpo_final(self, e):
        p = self.personaje
        if e.sentado:
            try:
                p.animar_caminar(0.0, 0.0)
            except Exception:            # noqa: BLE001
                pass
            self.poses.postura(e.x, e.z, e.rumbo, e.bajada, e.pies)
        else:
            self.poses.postura(e.x, e.z, e.rumbo, 0.0)
            try:
                p.animar_caminar(0.0, 0.0)
            except Exception:            # noqa: BLE001
                pass

    def _silla_final(self, e):
        if self._entidad_silla is not None and e.silla is not None:
            self._entidad_silla.world_x = float(e.silla[0])
            self._entidad_silla.world_z = float(e.silla[1])

    # -- Fin --

    def _terminar(self, forzado=False):
        """Estado final exacto, se deja de animar (sigue sosteniendo la pose) y al_terminar una vez."""
        if self.terminada and self._llamado:
            return
        self._aplicar_final()
        if self._reducido:
            try:
                _poner_velo_negro(0.0)
            except Exception:            # noqa: BLE001
                pass
        self.activa = False
        self.terminada = True
        self._sosteniendo = True
        self._restaurar_poses()
        if self in _activas:
            _activas.remove(self)
        if self.auto and self._motor is None and not self._cancelada:
            try:
                self._crear_motor()
            except Exception:            # noqa: BLE001
                pass
        self._llamar()

    def _llamar(self):
        if self._llamado:
            return
        self._llamado = True
        cb = self._al_terminar
        try:
            if cb is not None:
                cb()
        finally:
            if self._glitch and not self._reducido and self.final is not None and self.final.velo > 0:
                try:
                    _overlay_glitch().desvanecer(calc.GLITCH_DESVANECER)
                except Exception:        # noqa: BLE001
                    pass

    def _fallar(self, error=None):
        self.fallo = True
        self.error = error
        try:
            self._terminar()
        except Exception:
            raise                        # solo puede venir de al_terminar: sube (contrato §5.4)

    def _sin_guion(self):
        """Ni siquiera hay guion: cámara a la toma final si se conoce, y al_terminar."""
        self.activa = False
        self.terminada = True
        if self in _activas:
            _activas.remove(self)
        self._restaurar_poses()
        self._llamar()

    def _restaurar_poses(self):
        g = self._guardado_poses
        if g is None or self.poses is None:
            return
        self._guardado_poses = None
        paso, planos, continuo = g
        try:
            self.poses.tomar_continuo = continuo
            if paso is None:
                self.poses.__dict__.pop("PASO_LATERAL", None)
            else:
                self.poses.PASO_LATERAL = paso
            self.poses._planos = planos + [pl for pl in self.poses._planos if pl not in planos]
        except Exception:                # noqa: BLE001
            pass

    def _dejar_de_sostener(self):
        self._sosteniendo = False
        if not self.activa:
            self._destruir_motor()

    def _destruir_motor(self):
        m, self._motor = self._motor, None
        if m is not None:
            try:
                from ursina import destroy
                destroy(m)
            except Exception:            # noqa: BLE001
                pass

    # -- API pública --

    def saltar(self):
        """Termina todo al instante en el estado final y llama al_terminar. True si estaba activa."""
        if not self.activa or self._cancelada:
            return False
        self.t = self.duracion
        try:
            self._terminar()
        except Exception:
            raise
        return True

    def cancelar(self):
        """La detiene sin llamar al_terminar. No lanza."""
        try:
            self._cancelada = True
            self.activa = False
            self._sosteniendo = False
            if self in _activas:
                _activas.remove(self)
            self._restaurar_poses()
            if self._reducido:
                _poner_velo_negro(0.0)
            if self._glitch and not self.terminada:
                try:
                    _overlay_glitch().cancelar()
                except Exception:        # noqa: BLE001
                    pass
            self._destruir_motor()
            if _duenos.get(id(self.poses)) is self:
                del _duenos[id(self.poses)]
        except Exception:                # noqa: BLE001
            pass

    def soltar(self):
        """Devuelve el personaje a su animación normal (de pie, brazos libres). No lanza."""
        try:
            if self.activa:
                self.cancelar()
            self._sosteniendo = False
            self._destruir_motor()
            if _duenos.get(id(self.poses)) is self:
                del _duenos[id(self.poses)]
            if self.poses is not None:
                self.poses.soltar()
            try:
                self.personaje.animar_caminar(0.0, 0.0)
            except Exception:            # noqa: BLE001
                pass
        except Exception:                # noqa: BLE001
            pass

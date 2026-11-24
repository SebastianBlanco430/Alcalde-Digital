# Sentarse y levantarse en la Fiscalía, detrás de una sola puerta fácil de cambiar. Si existe frontend/cinematica_silla.py
# (sesión B, contrato sesiones-24nov/animaciones/contrato-silla.md) y su bandera ALCALDE_ANIM_SILLA está encendida, se
# usa su animación (saca la silla, se sienta, la acomoda; entra a la pantalla del terminal). Si no existe, está apagada o
# falla, la versión simple propia: la pose sentada de frontend/minijuegos_3d/poses_3d.PosesPersonaje (IK de piernas)
# puesta en el acto, que la escena tapa con su fundido o su corte.
#
# Todas las funciones aceptan `al_terminar` y lo llaman UNA vez (también si algo falla). Nunca lanzan.

import sys

_AVISADO = set()


def _avisar(clave, error):
    if clave in _AVISADO:
        return
    _AVISADO.add(clave)
    print(f"[fiscalia] sentarse: {clave}: {type(error).__name__}: {error}", file=sys.stderr)


def silla_de_b():
    """El módulo de B si está disponible y encendido; si no, None."""
    try:
        from frontend import cinematica_silla as cs
        return cs if cs.activa() else None
    except Exception:                    # noqa: BLE001  (no existe todavía o falla al importar)
        return None


class Postura:
    """Pose de un personaje (jugador o NPC) en la Fiscalía: sentado o de pie, sostenida cada frame con `avanzar(dt)`."""

    def __init__(self, personaje):
        self.personaje = personaje
        self.poses = None
        self.secuencia = None
        try:
            from frontend.minijuegos_3d.poses_3d import PosesPersonaje
            self.poses = PosesPersonaje(personaje)
        except Exception as error:      # noqa: BLE001
            _avisar("poses", error)

    def sentar_ya(self, asiento):
        """Sentado en el acto en `asiento` (x, z, rumbo)."""
        self._cancelar()
        try:
            if self.poses is not None:
                self.poses.sentar(asiento.x, asiento.z, asiento.rumbo)
                return
        except Exception as error:      # noqa: BLE001
            _avisar("sentar", error)
        self._de_pie_basico(asiento)

    def de_pie_ya(self, asiento):
        self._cancelar()
        try:
            if self.poses is not None:
                self.poses.de_pie(asiento.x, asiento.z, asiento.rumbo)
                return
        except Exception as error:      # noqa: BLE001
            _avisar("de_pie", error)
        self._de_pie_basico(asiento)

    def _de_pie_basico(self, asiento):
        try:
            self.personaje.colocar(asiento.x, asiento.z)
            self.personaje.fijar_rumbo(asiento.rumbo)
        except Exception as error:      # noqa: BLE001
            _avisar("colocar", error)

    @property
    def sentado(self):
        return bool(getattr(self.poses, "sentado", False))

    def avanzar(self, dt):
        if self.secuencia is not None:
            return                      # la secuencia de B sostiene la pose sola (auto=True), también al terminar
        try:
            if self.poses is not None:
                self.poses.avanzar(dt)
        except Exception as error:      # noqa: BLE001
            _avisar("avanzar", error)

    # -- Terminal del laboratorio --

    def entrar_a_pantalla(self, silla, mesa, pantalla, toma_final, al_terminar):
        """Se sienta al terminal y la cámara entra en el monitor. Con el módulo de B, su secuencia; si no, False (la escena
        hace la versión simple). `silla`/`mesa`: dicts de salas_calculos (se traducen a los tipos de B aquí)."""
        return self._con_b("entrar_a_pantalla", silla, mesa, pantalla=pantalla, toma_final=toma_final,
                           al_terminar=al_terminar)

    def salir_de_pantalla(self, silla, mesa, pantalla, toma_final, al_terminar):
        """Al volver del terminal: la cámara sale del monitor hasta `toma_final` (sigue sentado). False sin B."""
        return self._con_b("salir_de_pantalla", silla, mesa, pantalla=pantalla, toma_final=toma_final,
                           al_terminar=al_terminar)

    def levantarse(self, silla, mesa, hacia, al_terminar):
        """Se levanta, empuja la silla y se aparta hacia `hacia` (x, z). False sin B."""
        return self._con_b("levantarse_de", silla, mesa, hacia=hacia, al_terminar=al_terminar)

    def _con_b(self, nombre, silla, mesa, **op):
        cs = silla_de_b()
        if cs is None:
            return False
        try:
            from frontend.cinematica_silla_calculos import Mesa, Silla
            s = Silla(posicion=tuple(silla["posicion"]), rumbo=float(silla["rumbo"]),
                      altura_asiento=silla.get("altura", 0.47))
            m = Mesa(altura=mesa["altura"], borde=mesa["borde"])
            extra = {"entidad_silla": silla.get("entidad"), "poses": self.poses}
            if mesa.get("limites") is not None:
                extra["limites"] = mesa["limites"]
            previa = self.secuencia
            self.secuencia = None
            funcion = getattr(cs, nombre)
            if nombre == "levantarse_de":
                sec = funcion(self.personaje, s, m, clave="fiscalia_lab", **op, **extra)
            else:
                pantalla = op.pop("pantalla")
                sec = funcion(self.personaje, s, m, pantalla, clave="fiscalia_lab", **op, **extra)
            if previa is not None and previa is not sec:
                try:
                    previa.cancelar()
                except Exception:       # noqa: BLE001
                    pass
            self.secuencia = sec
            self.poses = getattr(sec, "poses", None) or self.poses
            return True
        except Exception as error:      # noqa: BLE001
            _avisar(nombre, error)
            return False

    def soltar_secuencia(self):
        """Deja de usar la secuencia de B y devuelve el personaje a su animación normal (de pie, brazos libres)."""
        sec, self.secuencia = self.secuencia, None
        if sec is None:
            return
        for metodo in ("cancelar", "soltar"):
            try:
                getattr(sec, metodo)()
            except Exception:           # noqa: BLE001
                pass
        try:
            if self.poses is not None:
                self.poses.sentado = True        # que de_pie suelte también las piernas que dejó la secuencia
                self.poses._levantar()
            self.personaje.cuerpo.position = (0, 0, 0)
        except Exception as error:      # noqa: BLE001
            _avisar("soltar_secuencia", error)

    def saltar(self):
        sec = self.secuencia
        try:
            return bool(sec is not None and sec.saltar())
        except Exception:               # noqa: BLE001
            return False

    def _cancelar(self):
        sec, self.secuencia = self.secuencia, None
        if sec is None:
            return
        try:
            sec.cancelar()
        except Exception:               # noqa: BLE001
            pass

    def soltar(self):
        self._cancelar()
        try:
            if self.poses is not None:
                self.poses.soltar()
        except Exception as error:      # noqa: BLE001
            _avisar("soltar", error)

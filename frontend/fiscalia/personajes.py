# Personajes 3D de la Fiscalía (Ursina): los del caso (el fiscal, los interrogados) con su .glb, sus colores y su cara
# expresiva —la MISMA receta que el interrogatorio de novela visual (frontend/interrogatorio_vn.py, EscenarioVN._crear;
# frontend/interrogatorio_vn_calculos.py)— y el protagonista del jugador (frontend/personaje_modelo.crear_personaje).
#
# Cada ActorCaso no se congela nunca: respira con su clip (Idle / Hablar mientras sale el texto), parpadea y mira con el
# perfil de su `expresion` (rostro_expresivo), cambia de postura (npc_postura) con mezcla de 0,25 s, y la boca se abre con
# cada vocal del texto. Sentado o de pie con frontend/fiscalia/sentarse.Postura.
# GUARDIÁN: un personaje que no carga queda como None (la escena sigue sin él); un fallo en un frame avisa una vez.

from frontend import banderas_visuales as bv
from frontend import interrogatorio_vn_calculos as calc
from frontend import modelo_calculos as mc
from frontend.fiscalia.sentarse import Postura

ALTO_CABEZA = 0.13          # m de la coronilla al centro de la cabeza
HUESOS_CABEZA = ("DEF-spine.006", "spine.006", "DEF-head", "head", "Head")
SOBRE_HUESO_CABEZA = 0.09   # m del origen del hueso de la cabeza (base del cráneo) al centro de la cara


class ActorCaso:

    def __init__(self, pid, npc, rostro, semilla):
        self.pid = pid
        self.npc = npc
        self.rostro = rostro
        self.semilla = semilla
        self.postura = Postura(npc)
        self._perfil = calc.perfil_de("neutral")
        self._desde = calc.perfil_de("neutral")
        self._k = 1.0
        self._t = 0.0
        self.expresion = "neutral"

    # -- Pose --

    def sentar(self, asiento):
        self.npc.enabled = True
        self.postura.sentar_ya(asiento)

    def de_pie(self, asiento):
        self.npc.enabled = True
        self.postura.de_pie_ya(asiento)

    def esconder(self):
        self.npc.enabled = False

    def cabeza(self):
        """Centro de la cabeza en mundo (x, y, z): el hueso de la cabeza si el modelo lo tiene (sigue la postura y la
        cabeza gacha); si no, la coronilla del modelo menos ALTO_CABEZA y la bajada de la pose sentada."""
        hueso = self._hueso_cabeza()
        if hueso is not None:
            try:
                from ursina import scene
                p = hueso.getPos(scene)
                if p.length() > 1e-3:
                    return (float(p[0]), float(p[1]) + SOBRE_HUESO_CABEZA, float(p[2]))
            except Exception:           # noqa: BLE001
                pass
        try:
            from frontend import npc_postura
            p = self.npc.world_position
            coronilla = npc_postura.y_ancla_cabeza(self.npc) - npc_postura.MARGEN_ANCLA_CABEZA
            return (float(p[0]), float(p[1]) + coronilla - ALTO_CABEZA + float(self.npc.cuerpo.y), float(p[2]))
        except Exception:               # noqa: BLE001
            p = self.npc.world_position
            return (float(p[0]), float(p[1]) + 1.24, float(p[2]))

    def _hueso_cabeza(self):
        if getattr(self, "_hueso", False) is not False:
            return self._hueso
        self._hueso = None
        actor = getattr(self.npc, "actor", None)
        try:
            nombres = {j.getName() for j in actor.getJoints()}
            for n in HUESOS_CABEZA:
                if n in nombres:
                    self._hueso = actor.exposeJoint(None, "modelRoot", n)
                    break
        except Exception:               # noqa: BLE001
            self._hueso = None
        return self._hueso

    # -- Frame --

    def avanzar(self, dt, expresion=None, hablando=False, apertura=None, reducir=False):
        self._t += dt
        if expresion:
            self.expresion = expresion
        objetivo = calc.perfil_de(self.expresion)
        if objetivo != self._perfil:
            actual = calc.mezclar_perfiles(self._desde, self._perfil, calc.suave(self._k))
            self._desde, self._perfil, self._k = actual, objetivo, 0.0
        self._k = calc.avance_mezcla(self._k, dt, reducir=reducir)
        perfil = calc.mezclar_perfiles(self._desde, self._perfil, calc.suave(self._k))
        npc = self.npc
        try:
            if getattr(npc, "_postura_vn", None) != perfil["postura"] and hasattr(npc, "aplicar_postura"):
                npc._postura_vn = perfil["postura"]
                npc.aplicar_postura(perfil["postura"])
            if self.rostro is not None:
                self.rostro.perfil = perfil
                self.rostro.apertura_forzada = apertura if hablando else None
            npc._poner_clip(mc.HABLAR if hablando and not self.postura.sentado else mc.IDLE, 1.0)
            if not reducir and not self.postura.sentado:
                npc.cuerpo.rotation_y = npc.rumbo + calc.braceo(self._t, perfil["braceo"], hablando)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez(f"fiscalia_actor_{self.pid}", error)
        self.postura.avanzar(dt)
        return perfil

    def destruir(self):
        self.postura.soltar()
        from frontend.componentes import destruir_arbol
        destruir_arbol(self.npc)


def crear_actor_caso(pid, personaje, caso_id, parent, mapeo=None):
    """ActorCaso del personaje `pid` del caso (dict del JSON: nombre, modelo, retrato) o None si no carga.
    modelos-personajes: si el personaje está en la fuente única (backend/datos/personajes_fiscalia.json) sale con su
    receta, idéntico al del mundo; si su modelo no carga, con un cuerpo de respaldo visible (aviso por stderr)."""
    try:
        actor = _crear_receta(pid, personaje or {}, parent)
        if actor is not None:
            return actor
    except Exception as error:          # noqa: BLE001
        _avisar_stderr(pid, f"la receta falló ({error!r}); se usa el modelo del caso")
    try:
        return _crear(pid, personaje or {}, caso_id, parent, mapeo)
    except Exception as error:          # noqa: BLE001
        bv.avisar_una_vez(f"fiscalia_modelo_{pid}", error)
        _avisar_stderr(pid, f"el modelo del caso no carga ({error!r}); se usa el cuerpo de respaldo")
    try:
        return _crear(pid, dict(personaje or {}, modelo="npc_hombre_01.glb"), caso_id, parent, mapeo)
    except Exception as error:          # noqa: BLE001
        _avisar_stderr(pid, f"tampoco carga el respaldo ({error!r}); queda sin cuerpo")
        return None


def _avisar_stderr(pid, motivo):
    import sys
    print(f"[fiscalia] personaje {pid}: {motivo}", file=sys.stderr)


def _crear_receta(pid, personaje, parent):
    """ActorCaso con la receta de la fuente única (None si el personaje no está en ella o nada carga)."""
    from backend.datos import personajes_loader as pl
    from frontend import personajes_receta_calculos as prc
    from frontend import rostro_expresivo
    from frontend.npc_modelo import crear_desde_receta
    receta = pl.de_caso(pid, personaje)
    if receta is None:
        return None
    npc = crear_desde_receta(receta, parent=parent)
    if npc is None:
        return None
    npc.automatico = False
    for parte in ("etiqueta", "aro", "sombra"):
        pieza = getattr(npc, parte, None)
        if pieza is not None:
            pieza.enabled = False
    semilla = prc.semilla(receta)
    rostro = rostro_expresivo.instalar(npc, semilla)
    return ActorCaso(pid, npc, rostro, semilla)


def _crear(pid, personaje, caso_id, parent, mapeo):
    from frontend import npc_calculos as nc
    from frontend import npc_nuevos_modelo as nnm
    from frontend import rostro_expresivo
    from frontend.npc_modelo import PersonajeNPC
    retrato = personaje.get("retrato") or {}
    modelo = personaje.get("modelo")
    if modelo in calc.MODELOS:
        archivo, rol = modelo, calc.MODELOS[modelo]
    else:
        archivo, rol = calc.modelo_para(caso_id, pid, retrato, mapeo if mapeo is not None else calc.cargar_mapeo())
    aspecto = calc.aspecto_de(retrato)
    semilla = calc.semilla_de(pid)
    plan = nc.plan_npc(semilla, semilla, aspecto, modelo=(archivo, rol))
    if plan.get("nuevo") and not nnm.disponible(plan):
        # respaldo: otro cuerpo de NPC del mismo género (el periodista es un protagonista: solo si ninguno carga)
        otros = [m for m in (("npc_mujer_02.glb", "npc_mujer_01.glb") if calc.es_mujer(retrato) else
                             ("npc_hombre_01.glb", "npc_hombre_02.glb", "npc_hombre_03.glb")) if m != plan["archivo"]]
        archivo, rol = "periodista.glb", "periodista"
        for otro in otros:
            p = nc.plan_npc(semilla, semilla, aspecto, modelo=(otro, calc.MODELOS[otro]))
            if nnm.disponible(p):
                archivo, rol = otro, calc.MODELOS[otro]
                break
        _avisar_stderr(pid, f"{plan['archivo']} no carga; se usa {archivo}")
        plan = nc.plan_npc(semilla, semilla, aspecto, modelo=(archivo, rol))
    camiseta, pantalon = calc.colores_ropa(retrato, plan["archivo"])
    plan["colores"]["camiseta"] = camiseta
    plan["colores"]["pantalon"] = pantalon
    plan["mochila"] = None
    plan["escala"] = 1.0
    if plan["archivo"] == "ciudadano.glb":
        plan["camiseta_nueva"] = "manga"
    npc = PersonajeNPC(personaje.get("nombre", pid), plan, aspecto, calc.rasgos_de(retrato), parent=parent)
    npc.automatico = False
    for parte in ("etiqueta", "aro", "sombra"):
        pieza = getattr(npc, parte, None)
        if pieza is not None:
            pieza.enabled = False
    rostro = rostro_expresivo.instalar(npc, semilla)
    return ActorCaso(pid, npc, rostro, semilla)


class Protagonista:
    """El personaje del jugador (su rol) dentro de la Fiscalía."""

    def __init__(self, jugador, parent):
        from backend.logica.roles import ROLES
        from frontend.personaje_modelo import crear_personaje
        rol = getattr(jugador, "rol", None) or "ciudadano"
        nombre = getattr(jugador, "nombre", None) or "Jugador"
        color_rol = ROLES[rol].color if rol in ROLES else (200, 200, 200)
        self.rol = rol
        self.personaje = crear_personaje(nombre, rol, color_rol, parent=parent)
        self.personaje.automatico = False
        for parte in ("etiqueta", "aro"):
            pieza = getattr(self.personaje, parte, None)
            if pieza is not None:
                pieza.enabled = False
        self.postura = Postura(self.personaje)
        self.caminando = False

    def sentar(self, asiento):
        self.caminando = False
        self.personaje.automatico = False
        self.postura.sentar_ya(asiento)

    def de_pie(self, asiento):
        self.postura.de_pie_ya(asiento)

    def caminar(self, x, z, rumbo, velocidad):
        """Un paso de caminata libre (laboratorio): el clip lo elige la animación automática por la velocidad."""
        p = self.personaje
        if self.postura.sentado:
            from frontend.fiscalia.salas_calculos import Asiento
            self.postura.de_pie_ya(Asiento(x, z, rumbo))
        self.caminando = True
        p.automatico = True
        p.colocar(x, z)
        if velocidad > 0.05:
            p.mirar_hacia(rumbo)
        p.fijar_velocidad(velocidad)

    def soltar_poses(self):
        """Suelta toda pose sostenida (secuencia de B, IK de piernas y brazos) y empieza una postura limpia."""
        self.postura.soltar_secuencia()
        self.postura.soltar()
        try:
            self.personaje.cuerpo.position = (0, 0, 0)
        except Exception:               # noqa: BLE001
            pass
        self.postura = Postura(self.personaje)

    def quieto(self):
        if self.caminando:
            self.personaje.fijar_velocidad(0.0)

    def cabeza(self):
        """Centro de la cabeza: el hueso de la cabeza si el modelo lo tiene (como ActorCaso: sigue la pose sentada real);
        si no, el alto típico. Con el alto fijo la cabeza real quedaba más alta y adelantada que la estimada y el
        contraplano ponía la cámara pegada a la nuca (ocupaba un tercio del cuadro)."""
        hueso = ActorCaso._hueso_cabeza(self)
        if hueso is not None:
            try:
                from ursina import scene
                h = hueso.getPos(scene)
                if h.length() > 1e-3:
                    return (float(h[0]), float(h[1]) + SOBRE_HUESO_CABEZA, float(h[2]))
            except Exception:           # noqa: BLE001
                pass
        p = self.personaje.world_position
        alto = 1.24 if self.postura.sentado else 1.62
        return (float(p[0]), float(p[1]) + alto, float(p[2]))

    @property
    def npc(self):
        return self.personaje

    def avanzar(self, dt):
        if not self.caminando:
            self.postura.avanzar(dt)

    def destruir(self):
        self.postura.soltar()
        from frontend.componentes import destruir_arbol
        destruir_arbol(self.personaje)

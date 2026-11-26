# Actores del final animado (Ursina). Un POOL por final: cada id de puesta.py («prota:candidato», «arenas»,
# «npc:florista», «v3»...) es UN cuerpo que sale en todos los planos que lo piden (solo se ve un plano a la vez).
#
#   - Protagonistas y Octavio Ruedas: personaje_modelo.crear_personaje(nombre, rol, ...) (el .glb de cada rol).
#   - Tomás Arenas: un PersonajeNPC de la fábrica de siempre con un plan propio (traje azul marino, canas, gafas, bigote).
#   - Vecinos y NPC de oficio: npc_modelo.crear_npc con semilla fija (como los NPC de etapa de etapas_final_vista.py).
#   - Gestos: las poses de poses_final.py horneadas UNA vez por esqueleto (con el horneado de animacion_humana) y
#     enlazadas al Actor como controles propios; su peso se mezcla con el de la animación de siempre (Panda normaliza),
#     así el AnimadorHumano sigue en Idle/marcha y nada del personaje se toca.
#   - Props: pancarta, escoba, guitarra, tambor, maracas, maletín, canasta, bandeja, banda y corbata, con su casco de
#     tinta. Los de un plano solo se ven en ese plano.
# Ningún archivo de modelos se edita: esto solo consume las fábricas.

import math
import sys

from panda3d.core import CullFaceAttrib, PartGroup
from ursina import Entity, color
from ursina.shaders import unlit_shader

from backend.logica.roles import ROLES
from frontend import estilo
from frontend import tinta_calculos as _tinta
from frontend.contorno_calculos import inflar_escala, realzar_color
from frontend.final_animado import poses_final as pf, puesta as P
from frontend.final_animado.decorado import texto, _tono

PESO_POSES = 30.0                # peso de las poses propias frente al Idle de siempre (que queda en 1)
SEGUNDOS_MEZCLA = 0.22           # de una acción a otra
GROSOR = _tinta.grosor("etapa_prop")
SEMILLA_NPC_ETAPA = 5417         # la de etapas_final_vista (mismos florista, panadero, escobita y músico)

_bancos = {}                     # (clave de esqueleto, pose) -> AnimBundle horneado
_avisados = set()


def _aviso(texto_):
    if texto_ not in _avisados:
        _avisados.add(texto_)
        print(f"[final_animado] {texto_}", file=sys.stderr)


def pieza(padre, modelo, posicion, escala, tono, giro=(0, 0, 0), luz=1.0):
    """Primitiva de color plano con su casco de tinta (como etapas_final_vista.pieza)."""
    relleno = Entity(parent=padre, model=modelo, position=posicion, scale=escala, rotation=giro, shader=unlit_shader,
                     unlit=True, color=color.rgb32(*_tono(realzar_color(tono), luz)))
    casco = Entity(parent=padre, model=modelo, position=posicion, scale=inflar_escala(escala, GROSOR), rotation=giro,
                   shader=unlit_shader, unlit=True, color=color.rgb32(*estilo.TINTA))
    casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
    relleno.ignore = casco.ignore = True
    return relleno


# -- Gestos ------------------------------------------------------------------------------------------------------------

# Clave del horneado: antes solo el rol, así todos los NPC (sin rol: «?») y el protagonista v2 con el vecino v1 del
# mismo rol compartían las poses horneadas en el PRIMER esqueleto y salían torcidas en los demás. Con
# ALCALDE_FINALES_PULIDOS la clave lleva también el tipo de cuerpo y su archivo de modelo.
def _clave_esqueleto(personaje):
    from frontend.final_animado import final_pulido_calculos as pulido
    rol = getattr(personaje, "rol", "?")
    if not pulido.activo():
        return rol
    plan = getattr(personaje, "_plan", None)
    plan = plan if isinstance(plan, dict) else {}
    return (type(personaje).__name__, rol, str(plan.get("archivo")), str(plan.get("v2")))


class Gestos:
    """Poses propias enlazadas al Actor de un personaje, con su peso suavizado."""

    def __init__(self, personaje, poses):
        self.controles = {}
        self.pesos = {}
        self._parte = None
        actor = getattr(personaje, "actor", None)
        if actor is None or getattr(personaje, "_humano", None) is None or not poses:
            return
        try:
            parte = actor.getPartBundle("modelRoot")
            clave = _clave_esqueleto(personaje)
            flags = PartGroup.HMFOkPartExtra | PartGroup.HMFOkAnimExtra | PartGroup.HMFOkWrongRootName
            medidas = [None]

            def banco_de(nombre):
                banco = _bancos.get((clave, nombre))
                if banco is None:
                    from frontend import animacion_humana as ah
                    if medidas[0] is None:
                        esq = ah.Esqueleto(actor.find("**/+Character"))
                        medidas[0] = (esq, esq.medidas())
                    esq, m = medidas[0]
                    banco = ah._construir_clip(esq, "Fin_" + nombre, [pf.pose_de(nombre, m)])
                    _bancos[(clave, nombre)] = banco
                return banco

            for nombre in poses:
                control = parte.bindAnim(banco_de(nombre), flags)
                if control is None:
                    continue
                control.pose(0)
                parte.setControlEffect(control, 0.0)
                self.controles[nombre] = control
                self.pesos[nombre] = 0.0
            self._parte = parte
        except Exception as error:
            _aviso(f"gestos de {clave} sin hornear ({type(error).__name__}: {error})")
            self.controles = {}

    def aplicar(self, objetivo, dt, de_golpe=False):
        if self._parte is None:
            return
        k = 1.0 if de_golpe else min(1.0, dt / SEGUNDOS_MEZCLA)
        for nombre, control in self.controles.items():
            meta = objetivo.get(nombre, 0.0)
            actual = self.pesos[nombre]
            nuevo = actual + (meta - actual) * k
            if abs(nuevo - meta) < 0.01:
                nuevo = meta
            if nuevo != actual or de_golpe:
                self.pesos[nombre] = nuevo
                self._parte.setControlEffect(control, nuevo * PESO_POSES)


# -- Creación de los cuerpos -------------------------------------------------------------------------------------------

def _limpiar_marcas(actor):
    for nombre in ("etiqueta", "aro"):
        parte = getattr(actor, nombre, None)
        if parte is not None:
            parte.enabled = False
    try:
        actor.resaltar(False)
        actor.etiqueta.enabled = False
        actor.aro.enabled = False
    except Exception:
        pass


def _crear_arenas(raiz):
    from frontend import npc_nuevos_calculos as nn
    from frontend import npc_nuevos_modelo as nnm
    from frontend.npc_modelo import PersonajeNPC, crear_npc
    from frontend.peatones_calculos import rasgos_peaton
    v2 = _arenas_v2(raiz)         # elenco v2 (sesión F): su malla propia; sin ella (o sin la bandera), como siempre
    if v2 is not None:
        return v2
    aspecto = {"pantalon": (34, 38, 56), "piel": (226, 180, 140), "pelo": (206, 206, 210)}
    rasgos = dict(rasgos_peaton(3, P.SEMILLA_ARENAS), peinado="atras", gafas=True, bigote=True, barba=None, gorra=None,
                  arrugas=True)
    try:
        plan = nn.plan_nuevo(3, P.SEMILLA_ARENAS, aspecto, ("npc_hombre_01.glb", "npc_hombre_01"))
        if not nnm.disponible(plan):
            raise RuntimeError("modelo nuevo no disponible")
        traje = (0.13, 0.17, 0.32)
        plan["colores"].update(camiseta=traje, pantalon=traje, zapatos=(0.07, 0.07, 0.08), pelo=(0.82, 0.82, 0.84))
        plan["mochila"] = None
        plan["escala"] = 1.02
        return PersonajeNPC("Tomás Arenas", plan, aspecto, rasgos, parent=raiz)
    except Exception as error:
        _aviso(f"Arenas con el NPC de siempre ({type(error).__name__}: {error})")
        return crear_npc(3, P.SEMILLA_ARENAS, aspecto, rasgos, (34, 40, 70), parent=raiz, nombre="Tomás Arenas")


def _arenas_v2(raiz):
    """Arenas con v2/arenas.glb (personajes_fiscalia.json, id «arenas») si ALCALDE_ELENCO_V2 está activa; None si no."""
    try:
        from backend.datos import personajes_loader as pl
        from frontend.npc_modelo import crear_v2
        receta = pl.por_id("arenas")
        return crear_v2(receta, parent=raiz) if receta is not None else None
    except Exception as error:      # noqa: BLE001
        _aviso(f"Arenas v2 no disponible ({type(error).__name__}: {error})")
        return None


def _crear_npc_etapa(raiz, tipo):
    from backend.logica import etapas_final
    from frontend.etapas_final_vista import rasgos_para_prop
    from frontend.npc_modelo import crear_npc
    from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
    datos = etapas_final.cargar_textos().get("npc", {}).get(tipo, {})
    i = int(datos.get("modelo", 0))
    tono = tuple(datos.get("color", (120, 120, 120)))
    return crear_npc(i, SEMILLA_NPC_ETAPA, aspecto_peaton(i, SEMILLA_NPC_ETAPA),
                     rasgos_para_prop(rasgos_peaton(i, SEMILLA_NPC_ETAPA), datos.get("prop"), tono), tono, parent=raiz,
                     nombre=datos.get("nombre"))


def _crear_vecino(raiz, k):
    from frontend.npc_modelo import crear_npc
    # ALCALDE_FINALES_PULIDOS: la gente del barrio del elenco v2; sin ella, como siempre
    v2 = _vecino_v2(raiz, k)
    if v2 is not None:
        return v2
    from frontend.peatones import ROPA
    from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
    indice, semilla = P.reparto_vecino(k)
    aspecto = P.aspecto_vecino(aspecto_peaton(indice, semilla))
    return crear_npc(indice, semilla, aspecto, rasgos_peaton(indice, semilla), ROPA[indice % len(ROPA)], parent=raiz)


def _vecino_v2(raiz, k):
    """Vecino k con su cuerpo del elenco v2 (final_pulido_calculos.ELENCO_VECINOS); None sin pulido o si no carga."""
    from frontend.final_animado import final_pulido_calculos as pulido
    if not pulido.activo():
        return None
    try:
        from backend.datos import personajes_loader as pl
        from frontend.npc_modelo import crear_v2
        receta = pl.por_id(pulido.receta_vecino(k)) if pulido.receta_vecino(k) else None
        return crear_v2(receta, parent=raiz) if receta is not None else None
    except Exception as error:      # noqa: BLE001
        _aviso(f"vecino {k} v2 no disponible ({type(error).__name__}: {error})")
        return None


def crear_cuerpo(id_pool, raiz, mundo):
    """El cuerpo del actor `id_pool` (oculto), listo para colocarlo a mano."""
    from frontend.personaje_modelo import crear_personaje
    if id_pool.startswith("prota:"):
        rol = id_pool.split(":", 1)[1]
        nombre = "Octavio Ruedas" if rol == "candidato" else ROLES[rol].nombre
        cuerpo = crear_personaje(nombre, rol, ROLES[rol].color, parent=raiz)
    elif id_pool == P.ARENAS:
        cuerpo = _crear_arenas(raiz)
    elif id_pool.startswith("npc:"):
        cuerpo = _crear_npc_etapa(raiz, id_pool.split(":", 1)[1])
    elif id_pool.startswith("v"):
        cuerpo = _crear_vecino(raiz, int(id_pool[1:]))
    else:
        raise ValueError(f"actor desconocido: {id_pool}")
    cuerpo.suelo = mundo.altura
    cuerpo.automatico = False
    try:
        cuerpo.colocar(0.0, 0.0)              # una vez con suelo: los pies se elevan sobre las capas del suelo
    except Exception:
        pass
    _limpiar_marcas(cuerpo)
    cuerpo.enabled = False
    return cuerpo


def soporte(cuerpo):
    """Entity hija del cuerpo (gira con él) en metros reales, para colgar props."""
    base = Entity(parent=getattr(cuerpo, "cuerpo", cuerpo))
    base.world_scale = 1
    base.ignore = True
    return base


# -- Props ---------------------------------------------------------------------------------------------------------------

class Prop:
    """Un prop colgado del cuerpo; `animar(mezcla_b, segundos)` lo mueve con el gesto."""

    def __init__(self, raiz):
        self.raiz = raiz

    def animar(self, mezcla_b, segundos):
        pass


class Pancarta(Prop):
    # Manos (m, en el cuerpo) con la pancarta abajo y arriba (poses pancarta_abajo / pancarta_arriba).
    ABAJO = (1.28, 0.5)
    ARRIBA = (2.0, 0.12)

    def __init__(self, base, cadena, luz):
        super().__init__(Entity(parent=base))
        # ALCALDE_FINALES_PULIDOS: abajo, el cartel ya no tapa la cara; arriba, va por encima de la cabeza.
        from frontend.final_animado import final_pulido_calculos as pulido
        if pulido.activo():
            self.ABAJO, self.ARRIBA = pulido.PANCARTA_ABAJO, pulido.PANCARTA_ARRIBA
        pieza(self.raiz, "cube", (0, 0.35, 0), (0.045, 1.1, 0.045), (150, 104, 62), luz=luz)
        tabla = Entity(parent=self.raiz, y=0.95)
        pieza(tabla, "cube", (0, 0, 0), (1.15, 0.62, 0.03), (246, 242, 230), luz=luz)
        texto(tabla, cadena, (0, 0, 0.022), 0.17, _tono((196, 40, 40), max(0.75, luz)), ancho_max=1.02)
        self.animar(0.0, 0.0)

    def animar(self, mezcla_b, segundos):
        y = self.ABAJO[0] + (self.ARRIBA[0] - self.ABAJO[0]) * mezcla_b
        z = self.ABAJO[1] + (self.ARRIBA[1] - self.ABAJO[1]) * mezcla_b
        self.raiz.position = (0, y - 0.35, z)
        self.raiz.rotation_z = 4 * math.sin(segundos * 1.3)


class Escoba(Prop):
    def __init__(self, base, luz):
        super().__init__(Entity(parent=base, position=(0.0, 0.95, 0.34)))
        palo = Entity(parent=self.raiz, rotation_x=28)
        pieza(palo, "cube", (0, -0.25, 0), (0.04, 1.3, 0.04), (150, 104, 62), luz=luz)
        pieza(palo, "cube", (0, -0.92, 0), (0.34, 0.2, 0.09), (236, 200, 70), luz=luz)

    def animar(self, mezcla_b, segundos):
        self.raiz.rotation_y = -24 + 48 * mezcla_b


class Fijo(Prop):
    pass


def _maletin(base, cuerpo, luz):
    raiz = Entity(parent=base, position=(0.27, 0.0, 0.03))
    pieza(raiz, "cube", (0, 0.56, 0), (0.1, 0.32, 0.42), (92, 58, 36), luz=luz)
    pieza(raiz, "cube", (0, 0.76, 0), (0.03, 0.06, 0.16), (60, 40, 28), luz=luz)
    return Fijo(raiz)


def _tambor(base, luz):
    raiz = Entity(parent=base, position=(0, 0.98, 0.3))
    pieza(raiz, "sphere", (0, 0, 0), (0.42, 0.3, 0.42), (200, 60, 60), luz=luz)
    pieza(raiz, "cube", (0, 0.16, 0), (0.36, 0.02, 0.36), (246, 242, 230), luz=luz)
    pieza(raiz, "cube", (0.0, 0.28, -0.18), (0.04, 0.5, 0.02), (60, 50, 40), (0, 0, 35), luz=luz)
    return Fijo(raiz)


def _maracas(base, luz):
    raiz = Entity(parent=base)
    for sx in (-1, 1):
        m = Entity(parent=raiz, position=(sx * 0.2, 1.42, 0.42))
        pieza(m, "sphere", (0, 0.06, 0), (0.12, 0.15, 0.12), ((240, 140, 40), (60, 170, 90))[sx > 0], luz=luz)
        pieza(m, "cube", (0, -0.06, 0), (0.025, 0.14, 0.025), (150, 104, 62), luz=luz)

    class Maracas(Prop):
        def animar(self, mezcla_b, segundos):
            for k, m in enumerate(self.raiz.children):
                m.y = 1.36 + 0.1 * (mezcla_b if k else 1 - mezcla_b)
    return Maracas(raiz)


def _guitarra(base, luz):
    raiz = Entity(parent=base)
    pieza(raiz, "sphere", (0.06, 1.0, 0.26), (0.34, 0.42, 0.12), (170, 104, 56), luz=luz)
    pieza(raiz, "cube", (-0.24, 1.2, 0.26), (0.06, 0.52, 0.04), (90, 60, 40), (0, 0, 55), luz=luz)
    pieza(raiz, "sphere", (0.06, 1.0, 0.33), (0.12, 0.12, 0.02), (40, 30, 26), luz=luz)
    return Fijo(raiz)


def _canasta(base, luz):
    raiz = Entity(parent=base)
    pieza(raiz, "cube", (0.34, 0.88, 0.14), (0.34, 0.20, 0.26), (150, 104, 62), luz=luz)
    for k, flor in enumerate(((222, 64, 64), (248, 206, 56), (214, 70, 160))):
        pieza(raiz, "sphere", (0.24 + 0.10 * k, 1.03, 0.14), (0.13, 0.13, 0.13), flor, luz=luz)
    return Fijo(raiz)


def _bandeja(base, luz):
    raiz = Entity(parent=base)
    pieza(raiz, "cube", (0, 1.06, 0.36), (0.52, 0.04, 0.30), (120, 124, 136), luz=luz)
    for k in range(3):
        pieza(raiz, "sphere", (-0.15 + 0.15 * k, 1.12, 0.36), (0.13, 0.10, 0.20), (214, 160, 90), luz=luz)
    from frontend.final_animado import final_pulido_calculos as pulido
    if not pulido.activo() or pulido.GORRO_PANADERO:
        pieza(raiz, "cube", (0, 1.8, 0), (0.24, 0.14, 0.24), (240, 240, 232), luz=luz)
    return Fijo(raiz)


def crear_prop(tipo, cuerpo, base, luz, cadena=None):
    if tipo == "pancarta":
        return Pancarta(base, cadena or "", luz)
    if tipo == "escoba":
        return Escoba(base, luz)
    if tipo == "maletin":
        return _maletin(base, cuerpo, luz)
    if tipo == "tambor":
        return _tambor(base, luz)
    if tipo == "maracas":
        return _maracas(base, luz)
    if tipo == "guitarra":
        return _guitarra(base, luz)
    if tipo == "canasta":
        return _canasta(base, luz)
    if tipo == "bandeja":
        return _bandeja(base, luz)
    raise ValueError(f"prop desconocido: {tipo}")


def _anillo(rx, rz, ancho, n=36):
    """Cinta cerrada de sección elíptica (rx de lado, rz de fondo, `ancho` de alto) alrededor del eje y."""
    from ursina import Mesh
    vertices, triangulos = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, z = rx * math.cos(a), rz * math.sin(a)
        vertices += [(x, -ancho / 2, z), (x, ancho / 2, z)]
        i, j = 2 * k, 2 * ((k + 1) % n)
        triangulos += [(i, j, j + 1), (i, j + 1, i + 1)]
    return Mesh(vertices=vertices, triangles=triangulos, mode="triangle")


def _banda_candidato(base, b):
    """La banda de candidato: una cinta que RODEA el torso de un hombro a la cadera contraria (antes era un bloque que
    sobresalía del cuerpo como una tabla), con su contorno de tinta y la medalla delante."""
    giro = b["giro"]
    raiz = Entity(parent=base, position=b["pos"], rotation=giro)
    raiz.ignore = True
    rx, rz, ancho = b["anillo"]
    relleno = Entity(parent=raiz, model=_anillo(rx, rz, ancho), shader=unlit_shader, unlit=True, double_sided=True,
                     color=color.rgb32(*realzar_color((44, 138, 214))))
    casco = Entity(parent=raiz, model=_anillo(rx + GROSOR, rz + GROSOR, ancho + 2 * GROSOR), shader=unlit_shader,
                   unlit=True, double_sided=True, color=color.rgb32(*estilo.TINTA))
    relleno.ignore = casco.ignore = True
    # el casco va un pelo por fuera: se ve como filo arriba y abajo de la cinta
    casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
    pieza(raiz, "sphere", (0.0, 0.0, rz + 0.012), (0.085, 0.085, 0.03), estilo.ACENTO_PRIMARIO)
    return raiz


def vestir_fijo(id_pool, cuerpo, base):
    """Lo que el actor lleva SIEMPRE: la banda de Octavio y la corbata de Arenas."""
    from frontend.final_animado import final_pulido_calculos as pulido
    if id_pool == P.OCTAVIO and pulido.activo():
        # La banda rodea el smoking v2 en diagonal (antes asomaba como una tabla delante del cuerpo).
        _banda_candidato(base, pulido.BANDA)
    elif id_pool == P.OCTAVIO:
        pieza(base, "cube", (0, 1.24, 0.0), (0.5, 0.09, 0.3), (44, 138, 214), (0, 0, 38))
        pieza(base, "sphere", (0.13, 1.37, 0.15), (0.1, 0.1, 0.04), estilo.ACENTO_PRIMARIO)
    elif id_pool == P.ARENAS and not getattr(cuerpo, "_plan", {}).get("v2"):    # v2: la corbata va en la malla
        pieza(base, "cube", (0, 1.22, 0.15), (0.075, 0.34, 0.03), (150, 28, 40), (6, 0, 0))
        pieza(base, "cube", (0, 1.4, 0.15), (0.09, 0.06, 0.035), (150, 28, 40))
        pieza(base, "cube", (0, 1.41, 0.135), (0.22, 0.07, 0.02), (240, 240, 236))

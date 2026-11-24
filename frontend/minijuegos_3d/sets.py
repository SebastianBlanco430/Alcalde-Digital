# Sets base de los minijuegos 3D (Ursina): dónde se juega. Cada set es un SetMinijuego con una raíz en `scene`, sus luces,
# el protagonista del rol del jugador y ANCLAS con nombre que las familias llenan con sus piezas.
#
#   interior            la oficina del lugar de la misión (una copia propia de EscenaInterior, la MISMA geometría y tema
#                       que la cinemática de entrada) — PC; con corcho si el tema tiene pizarra o mapa de rutas.
#   sala_investigacion  set nuevo: paredes del tema, corcho vacío con marco de madera en la pared del fondo, ventana,
#                       archivador y lámpara de techo.
#   cuarto_mesa         set nuevo: mesa de madera en el centro, luz de techo APAGABLE (luz_techo(False)) y lámpara de
#                       escritorio sobre la mesa.
#   cuarto_pc           la oficina con un tema por defecto (lugar sin interior propio).
# La elección por misión está en frontend/minijuegos_3d/interiores.py.
#
# ANCLAS (Ancla): una Entity `entidad` cuyo plano local z = 0 ES la superficie, con +x a la derecha y +y hacia arriba de la
# superficie según la mira el jugador, y su cara visible hacia -z local (como un quad de Ursina). Las unidades locales son
# METROS (la entidad no está escalada). Una pieza hija en z = -0.004 queda 4 mm delante de la superficie.
#   "monitor"  la pantalla del PC (además `quad`: el quad de la pantalla, 16:9). ancho x alto en m.
#   "corcho"   el panel de corcho dentro del marco (ancho x alto útiles).
#   "mesa"     el tablero de la mesa (x a lo ancho, y hacia el fondo, -z hacia arriba).
#   "raton"    punto (sin superficie) del ratón sobre el escritorio; "teclado" igual.
# Puntos del personaje (tuplas en mundo): set.pie = (x, z, rumbo) de pie frente al corcho/mesa; set.asiento = (x, z, rumbo)
# sentado al PC; set.puerta = (x, z) por donde entra.

import math

from ursina import Entity, Text, color
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader

from frontend import guion_cinematicas as guion
from frontend.componentes import destruir_arbol, rgb
from frontend.minijuegos_3d import interiores
from frontend.personaje_modelo import crear_personaje
from frontend.piezas import MASCARA_LUZ, encender_luz, pieza, silenciar
from frontend.temas_interior import TEMAS

MADERA = (150, 104, 66)
MADERA_OSCURA = (96, 66, 44)
MADERA_CLARA = (186, 140, 92)
CORCHO = (196, 150, 98)
METAL = (62, 64, 74)
TEMA_POR_DEFECTO = (232, 214, 178), (120, 88, 64), (168, 92, 60)       # pared, piso, acento (paleta de la favela)
DISTANCIA_CORCHO = 0.62         # m del corcho a los pies del personaje de pie (llega al corcho con el brazo)
LATERAL_PIE = 0.42               # fracción del ancho: el personaje se pone a la izquierda (no tapa el centro)
MESA_PIE_BORDE = 0.22            # m del borde cercano de la mesa a los pies (sin inclinar el torso alcanza ~0,40 m de mesa)
OFFSET_SUPERFICIE = 0.004          # m: lo que se apoya en una superficie va 4 mm delante (sin z-fighting, sin flotar)


class Ancla:

    def __init__(self, nombre, entidad, ancho=0.0, alto=0.0, quad=None):
        self.nombre = nombre
        self.entidad = entidad
        self.ancho = ancho
        self.alto = alto
        self.quad = quad

    def mundo(self, x=0.0, y=0.0, z=0.0):
        """Punto local (m) de la superficie -> coordenadas de mundo (tupla)."""
        from ursina import scene
        p = scene.getRelativePoint(self.entidad, (x, y, z))
        return (p[0], p[1], p[2])

    def local(self, punto_mundo):
        from ursina import scene
        p = self.entidad.getRelativePoint(scene, punto_mundo)
        return (p[0], p[1], p[2])

    def datos_toma(self):
        """{"centro", "normal", "arriba", "frente", "ancho", "alto"} en mundo para camaras_calculos."""
        centro = self.mundo(0, 0, 0)
        normal = _resta(self.mundo(0, 0, -1), centro)
        arriba = _resta(self.mundo(0, 1, 0), centro)
        return {"centro": centro, "normal": normal, "arriba": arriba, "frente": tuple(-c for c in arriba),
                "ancho": self.ancho, "alto": self.alto}


def _resta(a, b):
    return tuple(a[i] - b[i] for i in range(3))


class SetMinijuego:

    def __init__(self, nombre, raiz, personaje, luces=(), interior=None):
        self.nombre = nombre                 # uno de interiores.SETS
        self.raiz = raiz
        self.personaje = personaje
        self.luces = list(luces)
        self.anclas = {}
        self.pie = None
        self.asiento = None
        self.puerta = None
        self.interior = interior             # la EscenaInterior (solo set «interior»/«cuarto_pc»)
        self.luz_techo_encendida = True
        self.techo = None                    # y del techo (m) en los sets nuevos; la oficina no tiene techo
        self._bombilla = None
        self._ambiente = None
        self._sol = None
        self._ocultos = []
        self.creadas = []                    # (interior) entidades propias colgadas de la EscenaInterior: se destruyen al cerrar
        # Entrada/salida animadas (sesión B, ALCALDE_ANIM_SILLA): los pone preparar_entrada() SOLO en el camino nuevo.
        self.silla = None                    # cinematica_silla_calculos.Silla
        self.mesa_silla = None               # cinematica_silla_calculos.Mesa
        self.entidad_silla = None            # Entity suelta de la silla (la oficina: EscenaInterior.silla)
        self.corcho_desc = None              # cinematica_silla_calculos.Corcho
        self.limites = None                  # (x0, x1, z0, z1) de la sala (entrada_calculos)

    def nueva(self, entidad):
        """Registra una entidad creada dentro del interior (se destruye con el set). Devuelve la entidad."""
        self.creadas.append(entidad)
        return entidad

    def encender(self, si):
        if self.interior is not None:
            self.interior._luces(si)
        for luz in self.luces:
            encender_luz(luz, si)

    def luz_techo(self, encendida):
        """Enciende/apaga la luz de techo (cuarto_mesa y sala_investigacion). En el interior no hay: no hace nada."""
        self.luz_techo_encendida = bool(encendida)
        if self._bombilla is None:
            return
        self._bombilla.color = rgb((255, 244, 200)) if encendida else rgb((70, 66, 58))
        if self._ambiente is not None:
            self._ambiente.color = color.rgba32(120, 120, 130, 255) if encendida else color.rgba32(46, 44, 60, 255)
        if self._sol is not None:
            self._sol.color = color.rgba32(255, 255, 255, 255) if encendida else color.rgba32(70, 70, 96, 255)

    def destruir(self):
        self.encender(False)
        for e in self._ocultos:
            try:
                e.enabled = True
            except Exception:                # noqa: BLE001
                pass
        if self.interior is not None:
            try:
                reponer = getattr(self.interior, "reponer_silla", None)
                if callable(reponer):
                    reponer()                # la silla suelta vuelve a su sitio de siempre (la deslizó la entrada)
            except Exception:                # noqa: BLE001
                pass
            try:
                for e in self.creadas:
                    destruir_arbol(e)
                self.interior._apagar_pantalla()
                self.interior.enabled = False
            except Exception:                # noqa: BLE001
                pass
        else:
            destruir_arbol(self.raiz)


# -- Construcción --

def crear(eleccion, jugador, lugar, fabrica_interior=None):
    """SetMinijuego para `eleccion` (interiores.Eleccion). `fabrica_interior()` devuelve una EscenaInterior (la pasa la
    escena: este paquete no importa escenas)."""
    if eleccion.set in (interiores.INTERIOR, interiores.CUARTO_PC):
        if fabrica_interior is None:
            raise RuntimeError("sin fábrica de interior")
        return _set_interior(fabrica_interior(), jugador, lugar if lugar in TEMAS else next(iter(TEMAS)), eleccion)
    if eleccion.set == interiores.SALA_INVESTIGACION:
        return _set_sala_investigacion(jugador, lugar)
    if eleccion.set == interiores.CUARTO_MESA:
        return _set_cuarto_mesa(jugador, lugar)
    raise ValueError(f"Set desconocido: {eleccion.set!r}")


def _personaje(jugador, parent):
    from backend.logica.roles import ROLES
    rol = getattr(jugador, "rol", None) or "ciudadano"
    nombre = getattr(jugador, "nombre", None) or "Jugador"
    color_rol = ROLES[rol].color if rol in ROLES else (200, 200, 200)
    p = crear_personaje(nombre, rol, color_rol, parent=parent)
    p.automatico = False
    p.etiqueta.enabled = False
    p.aro.enabled = False
    return p


def _set_interior(interior, jugador, lugar, eleccion):
    interior.enabled = True
    interior.aplicar_tema(lugar)
    interior._crear_personaje(jugador)
    interior.destello.poner(0)
    interior._apagar_pantalla()
    interior.pantalla_texto.text = ""
    s = SetMinijuego(eleccion.set, interior, interior.personaje, interior=interior)
    mx, my, mz = guion.POSICION_PANTALLA
    # monitor: el quad de la pantalla de la oficina (mira a -z, hacia la silla)
    plano = s.nueva(Entity(parent=interior, position=(mx, my, mz - 0.012)))
    s.anclas["monitor"] = Ancla("monitor", plano, guion.ANCHO_PANTALLA, guion.ALTO_PANTALLA, quad=interior.pantalla)
    s.anclas["raton"] = Ancla("raton", s.nueva(Entity(parent=interior, position=(mx + 0.4, 0.785, 1.8))))
    s.anclas["teclado"] = Ancla("teclado", s.nueva(Entity(parent=interior, position=(mx, 0.78, 1.78))))
    s.anclas["mesa"] = Ancla("mesa", s.nueva(Entity(parent=interior, position=(mx, 0.755, 2.0), rotation_x=90)), 1.8, 0.8)
    s.asiento = (guion.ASIENTO[0], guion.ASIENTO[1], 0.0)
    s.puerta = tuple(guion.PUERTA_SALA)
    if eleccion.indice_prop >= 0:
        # corcho en la pared del tablero: el prop se esconde y el corcho cuelga en su ancla
        tematico = getattr(interior, "_tematico", [])
        prop = tematico[2 + eleccion.indice_prop] if len(tematico) > 2 + eleccion.indice_prop else None
        if prop is not None:
            prop.enabled = False
            s._ocultos.append(prop)
        x, z, rot = _ANCLAS_INTERIOR[eleccion.pared]
        soporte = s.nueva(Entity(parent=interior, position=(x, 0, z), rotation_y=rot))
        plano = _corcho(soporte, ancho=1.7, alto=1.05, altura=1.5, separacion=0.06)
        s.anclas["corcho"] = Ancla("corcho", plano, 1.7, 1.05)
        s.pie = _pie_frente(s.anclas["corcho"], DISTANCIA_CORCHO, -LATERAL_PIE * 1.7)
    return s


# Copia de EscenaInterior.ANCLAS (x, z, rotation_y; +z local hacia la habitación): no se importa la escena (capa MVC).
_ANCLAS_INTERIOR = {
    "oeste": (-guion.SALA_ANCHO / 2, 0.4, 90),
    "norte": (-1.2, guion.SALA_FONDO / 2, 180),
    "este": (guion.SALA_ANCHO / 2, -0.4, -90),
}


def _pie_frente(ancla, distancia, lateral=0.0):
    """(x, z, rumbo) de pie a `distancia` m delante de la superficie vertical `ancla`, mirándola, desplazado `lateral` m a lo
    largo de ella (negativo = a la izquierda según se mira: el personaje no tapa el centro del corcho)."""
    c = ancla.mundo(lateral, 0, 0)
    n = ancla.mundo(lateral, 0, -distancia)
    rumbo = math.degrees(math.atan2(c[0] - n[0], c[2] - n[2]))
    return (n[0], n[2], rumbo)


def _corcho(soporte, ancho, alto, altura, separacion):
    """Corcho con marco de madera colgado de `soporte` (cuyo +z local apunta a la habitación). Devuelve el PLANO del
    corcho (Entity en la cara del corcho, mirando a la habitación)."""
    grupo = Entity(parent=soporte, shader=lit_with_shadows_shader)
    marco = 0.06
    fondo = 0.035
    z = separacion
    pieza(parent=grupo, model="cube", color=rgb(CORCHO), position=(0, altura, z), scale=(ancho, alto, fondo))
    for (x, y, sx, sy) in ((0, altura + alto / 2 + marco / 2, ancho + 2 * marco, marco),
                           (0, altura - alto / 2 - marco / 2, ancho + 2 * marco, marco),
                           (ancho / 2 + marco / 2, altura, marco, alto), (-ancho / 2 - marco / 2, altura, marco, alto)):
        pieza(parent=grupo, model="cube", color=rgb(MADERA), position=(x, y, z + 0.008), scale=(sx, sy, fondo + 0.02))
    grupo.combine()
    silenciar(grupo)
    # plano: en la cara del corcho que da a la habitación (+z del soporte), con la cara visible hacia la habitación
    return Entity(parent=soporte, position=(0, altura, z + fondo / 2), rotation_y=180)


def _colores(lugar):
    tema = TEMAS.get(lugar)
    if tema is None:
        return TEMA_POR_DEFECTO
    return tema.pared, tema.piso, tema.acento


def _habitacion(raiz, ancho, fondo, alto, lugar):
    """Cuarto cerrado con techo (fuera del mapa de sombras), puerta al sur, ventana al este y zócalo del color del acento."""
    pared, piso, acento = _colores(lugar)
    grupo = Entity(parent=raiz, shader=lit_with_shadows_shader)
    pieza(parent=grupo, model="cube", color=rgb(piso), position=(0, -0.05, 0), scale=(ancho, 0.1, fondo))
    for (x, z, sx, sz) in ((0, fondo / 2 + 0.05, ancho + 0.2, 0.1), (0, -fondo / 2 - 0.05, ancho + 0.2, 0.1),
                           (ancho / 2 + 0.05, 0, 0.1, fondo), (-ancho / 2 - 0.05, 0, 0.1, fondo)):
        pieza(parent=grupo, model="cube", color=rgb(pared), position=(x, alto / 2, z), scale=(sx, alto, sz))
    # zócalo (acento) y rodapié
    for (x, z, sx, sz) in ((0, fondo / 2 - 0.02, ancho, 0.02), (ancho / 2 - 0.02, 0, 0.02, fondo),
                           (-ancho / 2 + 0.02, 0, 0.02, fondo)):
        pieza(parent=grupo, model="cube", color=rgb(acento), position=(x, 1.0, z), scale=(sx, 0.08, sz))
        pieza(parent=grupo, model="cube", color=rgb((236, 236, 240)), position=(x, 0.08, z), scale=(sx, 0.16, sz))
    # puerta (sur) y ventana (este)
    pieza(parent=grupo, model="cube", color=rgb((30, 30, 38)), position=(-1.2, 1.15, -fondo / 2 + 0.015), scale=(1.14, 2.34, 0.03))
    pieza(parent=grupo, model="cube", color=rgb(MADERA_OSCURA), position=(-1.2, 1.1, -fondo / 2 + 0.04), scale=(1.0, 2.2, 0.03))
    x = ancho / 2
    pieza(parent=grupo, model="cube", color=rgb((230, 230, 236)), position=(x - 0.04, 1.6, -0.4), scale=(0.07, 1.24, 1.44))
    pieza(parent=grupo, model="cube", color=rgb((150, 205, 235)), position=(x - 0.08, 1.6, -0.4), scale=(0.05, 1.1, 1.3))
    pieza(parent=grupo, model="cube", color=rgb((230, 230, 236)), position=(x - 0.1, 1.6, -0.4), scale=(0.05, 1.1, 0.05))
    grupo.combine()
    silenciar(grupo)
    techo = pieza(parent=raiz, model="cube", color=rgb((240, 238, 232)), position=(0, alto + 0.05, 0), scale=(ancho, 0.1, fondo))
    techo.hide(MASCARA_LUZ)              # el techo no tapa el sol del mapa de sombras (si no, todo queda en sombra)
    silenciar(techo)
    return grupo


def _luces(raiz):
    sol = DirectionalLight(parent=raiz, shadows=True, shadow_map_resolution=(1024, 1024))
    sol.look_at((-0.6, -1.4, 0.8))
    ambiente = AmbientLight(parent=raiz, color=color.rgba32(120, 120, 130, 255))
    return sol, ambiente


def _lampara_techo(raiz, x, z, alto):
    pieza(parent=raiz, model="cube", color=rgb((40, 40, 46)), position=(x, alto - 0.25, z), scale=(0.015, 0.5, 0.015))
    pieza(parent=raiz, model="cube", color=rgb((60, 64, 74)), position=(x, alto - 0.52, z), scale=(0.42, 0.08, 0.42))
    return Entity(parent=raiz, model="sphere", color=rgb((255, 244, 200)), position=(x, alto - 0.59, z), scale=0.13,
                  shader=None)


def _set_base(nombre, jugador, lugar, ancho=5.0, fondo=4.6, alto=2.9):
    from ursina import scene
    raiz = Entity(parent=scene, name=f"set_{nombre}")
    _habitacion(raiz, ancho, fondo, alto, lugar)
    sol, ambiente = _luces(raiz)
    personaje = _personaje(jugador, raiz)
    s = SetMinijuego(nombre, raiz, personaje, luces=(sol, ambiente))
    s._sol, s._ambiente = sol, ambiente
    s.puerta = (-1.2, -fondo / 2 + 0.5)
    s.techo = alto
    s._bombilla = _lampara_techo(raiz, 0.0, 0.3, alto)
    return s, raiz, ancho, fondo, alto


def _set_sala_investigacion(jugador, lugar):
    s, raiz, ancho, fondo, alto = _set_base(interiores.SALA_INVESTIGACION, jugador, lugar)
    # corcho vacío con marco de madera en la pared del fondo (norte)
    soporte = Entity(parent=raiz, position=(0.2, 0, fondo / 2), rotation_y=180)
    # separacion 0,03: la cara del corcho queda DELANTE del zócalo de la pared (antes el zócalo, 1,25 cm delante del
    # corcho, cruzaba su franja de abajo; familia-corcho lo tapaba con una tira, que sigue siendo inocua)
    plano = _corcho(soporte, ancho=2.0, alto=1.2, altura=1.55, separacion=0.03)
    s.anclas["corcho"] = Ancla("corcho", plano, 2.0, 1.2)
    s.pie = _pie_frente(s.anclas["corcho"], DISTANCIA_CORCHO, -LATERAL_PIE * 2.0)
    # archivador y mesita con lámpara (ambiente)
    deco = Entity(parent=raiz, shader=lit_with_shadows_shader)
    pieza(parent=deco, model="cube", color=rgb((120, 126, 120)), position=(-2.1, 0.65, 1.6), scale=(0.5, 1.3, 0.6))
    for k in range(3):
        pieza(parent=deco, model="cube", color=rgb((150, 156, 150)), position=(-2.1, 0.3 + k * 0.4, 1.29), scale=(0.42, 0.3, 0.02))
    pieza(parent=deco, model="cube", color=rgb(MADERA), position=(1.9, 0.72, 1.6), scale=(0.9, 0.05, 0.6))
    for dx in (-0.4, 0.4):
        pieza(parent=deco, model="cube", color=rgb(MADERA_OSCURA), position=(1.9 + dx, 0.36, 1.6), scale=(0.05, 0.72, 0.55))
    deco.combine()
    silenciar(deco)
    s.luces[0].update_bounds(raiz)
    return s


def _set_cuarto_mesa(jugador, lugar):
    s, raiz, ancho, fondo, alto = _set_base(interiores.CUARTO_MESA, jugador, lugar)
    mesa_y, mesa_z = 0.78, 0.6
    tablero = (1.7, 1.0)
    grupo = Entity(parent=raiz, shader=lit_with_shadows_shader)
    pieza(parent=grupo, model="cube", color=rgb(MADERA_CLARA), position=(0, mesa_y - 0.025, mesa_z),
          scale=(tablero[0], 0.05, tablero[1]))
    for dx in (-0.78, 0.78):
        for dz in (-0.42, 0.42):
            pieza(parent=grupo, model="cube", color=rgb(MADERA_OSCURA), position=(dx, (mesa_y - 0.05) / 2, mesa_z + dz),
                  scale=(0.06, mesa_y - 0.05, 0.06))
    # lámpara de escritorio (base, brazo y pantalla) en la esquina izquierda del fondo
    pieza(parent=grupo, model="cube", color=rgb((44, 46, 54)), position=(-0.66, mesa_y + 0.012, mesa_z + 0.36), scale=(0.16, 0.025, 0.12))
    pieza(parent=grupo, model="cube", color=rgb((44, 46, 54)), position=(-0.66, mesa_y + 0.2, mesa_z + 0.38), scale=(0.02, 0.36, 0.02))
    pieza(parent=grupo, model="cube", color=rgb((44, 46, 54)), position=(-0.6, mesa_y + 0.37, mesa_z + 0.33), scale=(0.16, 0.06, 0.12))
    grupo.combine()
    silenciar(grupo)
    Entity(parent=raiz, model="sphere", color=rgb((255, 238, 170)), position=(-0.58, mesa_y + 0.33, mesa_z + 0.31),
           scale=0.05, shader=None)
    s.anclas["mesa"] = Ancla("mesa", Entity(parent=raiz, position=(0, mesa_y, mesa_z), rotation_x=90),
                             tablero[0], tablero[1])
    s.pie = (-LATERAL_PIE * tablero[0], mesa_z - tablero[1] / 2 - MESA_PIE_BORDE, 0.0)
    s.luces[0].update_bounds(raiz)
    return s


# -- Entrada/salida animadas (sesión B, ALCALDE_ANIM_SILLA). Solo las llama base.py en el camino nuevo: con la bandera en
#    0 (o si algo falla) el set queda EXACTAMENTE como lo deja crear(). --

def preparar_entrada(s, familia, minijuego_id, manos=None):
    """Pone en el set `s` los descriptores del contrato de cinematica_silla (Silla, Mesa, entidad de la silla; o Corcho) y,
    en el cuarto_mesa, la silla. `manos` = {"i", "d"} (mundo) donde terminan las manos en la familia PC (teclado y ratón).
    Devuelve True si quedó listo para la entrada nueva; False (y el set intacto) si esta familia/set no la tiene. Lanza si
    el módulo del contrato no se puede importar (lo captura base.py)."""
    from frontend import cinematica_silla_calculos as csc
    from frontend.minijuegos_3d import entrada_calculos as ec
    if familia == "pc":
        if s.asiento is None or s.interior is None or getattr(s.interior, "silla", None) is None:
            return False
        from frontend.minijuegos_3d.base import ADELANTE_SENTADO
        silla = ec.silla_pc(s.asiento, ADELANTE_SENTADO)
        mesa = ec.mesa_pc(silla, manos)
        s.limites = ec.OFICINA_LIMITES
        s.entidad_silla = s.interior.silla
        _poner_silla(s.entidad_silla, silla)
    elif familia == "mesa":
        silla = ec.silla_mesa(minijuego_id)
        if silla is None or s.nombre != interiores.CUARTO_MESA or minijuego_id not in ec.MESA_SENTADO:
            return False
        mesa = ec.mesa_cuarto(silla, minijuego_id)
        s.limites = ec.CUARTO_LIMITES
        s.entidad_silla = _silla_entidad(s.raiz, silla)
    elif familia == "corcho":
        ancla = s.anclas.get("corcho")
        if ancla is None:
            return False
        d = ancla.datos_toma()
        derecha = _resta(ancla.mundo(1, 0, 0), d["centro"])
        pie, nota = ec.corcho_pie_y_nota(d["centro"], d["normal"], derecha, ancla.ancho)
        s.corcho_desc = csc.Corcho(centro=tuple(d["centro"]), normal=tuple(d["normal"]), ancho=ancla.ancho,
                                   alto=ancla.alto, pie=pie, nota=nota)
        s.limites = ec.OFICINA_LIMITES if s.interior is not None else ec.CUARTO_LIMITES
        return True
    else:
        return False
    s.silla = csc.Silla(**silla)
    s.mesa_silla = csc.Mesa(**mesa)
    return True


def _poner_silla(entidad, silla):
    """La silla suelta en su sitio ACOMODADO (donde queda para jugar), mirando al rumbo del asiento."""
    x, z = silla["posicion"]
    entidad.world_position = (x, silla.get("suelo_y", 0.0), z)
    entidad.world_rotation_y = silla["rumbo"]


def _silla_entidad(padre, silla):
    """Silla estándar suelta (la misma forma y color que la de la oficina, una malla) con el origen en el suelo bajo el
    centro del asiento, ya acomodada en `silla` (contrato de cinematica_silla: entidad_silla)."""
    e = Entity(parent=padre, shader=lit_with_shadows_shader, name="silla_mesa")
    tela = rgb((52, 56, 74))
    pieza(parent=e, model="cube", color=tela, position=(0, 0.45, 0), scale=(0.48, 0.07, 0.48))
    pieza(parent=e, model="cube", color=tela, position=(0, 0.78, -0.22), scale=(0.46, 0.55, 0.06))
    pieza(parent=e, model="cube", color=rgb(METAL), position=(0, 0.22, 0), scale=(0.06, 0.4, 0.06))
    pieza(parent=e, model="cube", color=rgb(METAL), position=(0, 0.03, 0), scale=(0.5, 0.05, 0.5))
    e.combine()
    silenciar(e)
    _poner_silla(e, silla)
    return e


def deshacer_entrada(s):
    """Quita lo que puso preparar_entrada (el camino nuevo falló): el set queda como lo dejó crear(). Nunca lanza."""
    try:
        if s.interior is not None:
            reponer = getattr(s.interior, "reponer_silla", None)
            if callable(reponer):
                reponer()
        elif s.entidad_silla is not None:
            destruir_arbol(s.entidad_silla)
    except Exception:                    # noqa: BLE001
        pass
    s.silla = s.mesa_silla = s.entidad_silla = s.corcho_desc = None


def rotulo(ancla, texto, y_local=0.0, escala=1.0):
    """Texto de prueba sobre un ancla (para la demostración y el arnés)."""
    t = Text(texto, parent=ancla.entidad, origin=(0, 0), position=(0, y_local, -0.006), scale=escala, color=color.black)
    return t

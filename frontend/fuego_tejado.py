# Fuegos sobre los tejados: sitios, mallas y animación (Ursina/Panda). Cálculos en frontend/fuego_tejado_calculos.py.
# Lo usa frontend/ciudad_viva.py (capa «fuego» de las etapas malas) cuando fuego_tejado_calculos.activo().
#
# - Sitios: uno por casa decorativa, en el punto del tejado del piso de ARRIBA (se busca en la geometría del modelo tal
#   como lo carga el juego, una vez por modelo) llevado al mundo con la MISMA colocación que usa
#   casas_decorativas.construir_casas_favela (base en el punto más alto de su huella, pisos apilados, giro, escala).
# - Malla de la llama: tres láminas cruzadas; en cada una, capas de silueta redondeada (tinta, rojo, naranja, amarillo)
#   con degradado de color y transparencia en los colores de vértice; brasas en la base. Una malla por variante.
# - Humo: BOCANADAS_HUMO discos con degradado radial de alfa, hijos de cada fuego, siempre de cara a la cámara;
#   suben, crecen, derivan y se desvanecen (fuego_tejado_calculos.ciclo_humo). Creados una vez con la piscina.

import math

from frontend import fuego_tejado_calculos as ftc
from frontend.contorno_calculos import realzar_color
from frontend import estilo

ROJO = realzar_color(estilo.ESTADO_ERROR)
NARANJA = realzar_color((246, 128, 36))
AMARILLO = realzar_color((255, 214, 92))
NUCLEO = (255, 246, 200)
BRASA = realzar_color((255, 96, 28))
HUMO_OSCURO = (46, 45, 50)        # la gamma del juego aclara los colores sin luz: estos se ven gris humo
HUMO_CLARO = (128, 126, 134)
GIROS_LAMINAS = (0.0, 60.0, 120.0)
# (escala del ancho, escala del alto, color, separación de la lámina, alfa abajo) de cada capa, de fuera a dentro.
CAPAS_LLAMA = ((1.12, 1.06, estilo.TINTA, 0.0, 0.9), (1.0, 1.0, ROJO, 0.012, 0.92),
               (0.74, 0.78, NARANJA, 0.024, 0.95), (0.46, 0.52, AMARILLO, 0.036, 0.97), (0.22, 0.26, NUCLEO, 0.048, 1.0))

_puntos_tejado = {}              # nombre de modelo -> (x, y, z) local o None


def _color(rgb, alfa):
    return (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, alfa)


# -- Sitios --------------------------------------------------------------------------------------------------------------

def punto_tejado_local(nombre):
    """(x, y, z) del tejado del modelo `nombre` en su marco local (y arriba), o None. Cacheado por modelo."""
    if nombre in _puntos_tejado:
        return _puntos_tejado[nombre]
    punto = None
    try:
        from panda3d.core import NodePath
        from ursina import load_model
        from backend.datos.modelos_edificios import modelo_de
        from frontend.casas_decorativas import _triangulos_de
        modelo = load_model(modelo_de(nombre).archivo).copy_to(NodePath(f"tejado_{nombre}"))
        triangulos = [tuple(pos[v] for v in tri) for _n, _i, indices, pos in _triangulos_de(modelo) for tri in indices]
        lo, hi = modelo.get_tight_bounds()
        punto = ftc.punto_de_tejado(lambda x, z: ftc.superficie_en(triangulos, x, z), (lo.x, hi.x, lo.z, hi.z))
    except Exception as error:
        print(f"[fuego_tejado] {nombre}: no se pudo hallar el tejado ({error})")
    _puntos_tejado[nombre] = punto
    return punto


def sitios_fuego_tejado(mundo, sal):
    """[Punto] de los fuegos: uno por casa decorativa con tejado conocido. Determinista. `sal`: la de la capa fuego."""
    from panda3d.core import NodePath, Point3
    from backend.datos.modelos_edificios import modelo_de
    from backend.logica import ciudad_viva_calculos as cv
    from frontend.ciudad_viva import _punto
    from frontend.geometria_mundo import apoyo_de_caja
    sitios = []
    colocador = NodePath("colocador_fuego")
    casas = [o for o in mundo.obstaculos() if type(o).__name__ == "CasaDecorativa"]
    for indice, casa in enumerate(casas):
        local = punto_tejado_local(casa.modelo)
        if local is None:
            continue
        _, base = apoyo_de_caja(mundo.altura, casa.cx, casa.cz, casa.ancho, casa.fondo)
        alto_piso = modelo_de(casa.modelo).alto * casa.escala
        colocador.set_pos(casa.cx, base + (max(1, casa.pisos) - 1) * alto_piso, casa.cz)
        colocador.set_hpr(-casa.rumbo, 0, 0)
        colocador.set_scale(casa.escala, casa.escala, casa.escala * getattr(casa, "estiramiento", 1.0))
        p = colocador.get_mat().xform_point(Point3(*local))
        x, y, z = p.x, p.y - ftc.MARGEN_SOBRE_TEJADO, p.z
        sitios.append(_punto(x, z, cv.azar_sitio(x, z, sal), y, 360.0 * cv.azar_sitio(z, x, sal + 1.0), indice))
    return sitios


# -- Mallas --------------------------------------------------------------------------------------------------------------

def _lamina(vertices, colores, silueta, alto, giro, separacion, color, alfa_abajo, desplazar_x=0.0):
    """Abanico desde el centro de la silueta (en el plano de la lámina girada `giro`), separado `separacion` a cada lado."""
    seno, coseno = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    cy = alto * 0.33
    lados = (separacion, -separacion) if separacion else (0.0,)
    for d in lados:
        def poner(x, y):
            x += desplazar_x
            return (x * coseno + d * seno, y, -x * seno + d * coseno)
        centro = poner(0.0, cy)
        c_centro = _color(color, alfa_abajo)
        for (x1, y1), (x2, y2) in zip(silueta, silueta[1:] + silueta[:1]):
            for punto, col in ((centro, c_centro),
                               (poner(x1, y1), _color(color, ftc.alfa_llama(y1 / alto, alfa_abajo))),
                               (poner(x2, y2), _color(color, ftc.alfa_llama(y2 / alto, alfa_abajo)))):
                vertices.append(punto)
                colores.append(col)


def mesh_fuego_tejado(v):
    """Llama de formas suaves (variante `v`): láminas cruzadas con capas redondeadas y brasas. Base en y=0, ~1,5 m."""
    from ursina import Mesh
    from frontend.azar_fijo import azar_de
    vertices, colores = [], []
    for n, giro in enumerate(GIROS_LAMINAS):
        alto = 1.35 + 0.35 * azar_de(n, v + 0.7)
        ancho = 0.85 + 0.2 * azar_de(n + 3.0, v)
        curva = 0.35 * (azar_de(n + 5.0, v + 2.0) - 0.5)
        for ea, eh, color, sep, alfa in CAPAS_LLAMA:
            silueta = ftc.silueta_llama(ancho * ea, alto * eh, curva)
            _lamina(vertices, colores, silueta, alto * eh, giro + 17 * v, sep, color, alfa)
    for k in range(3):                                         # lenguas sueltas alrededor del centro
        a = 2 * math.pi * (k + 0.3 * v) / 3
        silueta = ftc.silueta_llama(0.42, 0.75 + 0.3 * azar_de(k, v + 9.0), 0.2)
        inicio = len(vertices)
        for ea, eh, color, sep, alfa in CAPAS_LLAMA[1:4]:
            sil = [(x * ea, y * eh) for x, y in silueta]
            _lamina(vertices, colores, sil, max(y for _x, y in sil), math.degrees(a) + 90, sep, color, alfa)
        dx, dz = 0.42 * math.cos(a), 0.42 * math.sin(a)
        for i in range(inicio, len(vertices)):
            x, y, z = vertices[i]
            vertices[i] = (x + dx, y, z + dz)
    segmentos = 12                                             # brasas: disco plano en la base
    for k in range(segmentos):
        a1, a2 = 2 * math.pi * k / segmentos, 2 * math.pi * (k + 1) / segmentos
        for punto, alfa in (((0.0, 0.03, 0.0), 1.0), ((0.75 * math.cos(a1), 0.03, 0.75 * math.sin(a1)), 0.0),
                            ((0.75 * math.cos(a2), 0.03, 0.75 * math.sin(a2)), 0.0)):
            vertices.append(punto)
            colores.append(_color(BRASA, alfa))
    return Mesh(vertices=vertices, triangles=[], colors=colores)


def mesh_bocanada(segmentos=16):
    """Disco de humo de diámetro 1 (plano x-y, mira a +z): núcleo opaco hasta el 55 % del radio y borde que se
    desvanece (con la gamma del juego un degradado lineal desde el centro dejaba el humo casi invisible)."""
    from ursina import Mesh
    vertices, colores = [], []
    anillos = ((0.0, 1.0), (0.28, 0.95), (0.5, 0.0))           # (radio, alfa)
    for k in range(segmentos):
        a1, a2 = 2 * math.pi * k / segmentos, 2 * math.pi * (k + 1) / segmentos
        for (r1, f1), (r2, f2) in zip(anillos, anillos[1:]):
            p11, p12 = (r1 * math.cos(a1), r1 * math.sin(a1), 0.0), (r1 * math.cos(a2), r1 * math.sin(a2), 0.0)
            p21, p22 = (r2 * math.cos(a1), r2 * math.sin(a1), 0.0), (r2 * math.cos(a2), r2 * math.sin(a2), 0.0)
            vertices += [p11, p21, p22, p11, p22, p12]
            colores += [(1, 1, 1, f1), (1, 1, 1, f2), (1, 1, 1, f2), (1, 1, 1, f1), (1, 1, 1, f2), (1, 1, 1, f1)]
    return Mesh(vertices=vertices, triangles=[], colors=colores)


# -- Entidades y animación ------------------------------------------------------------------------------------------------

def preparar_grupo(grupo):
    """Transparencia y doble cara para las llamas de la piscina `grupo`, y sus bocanadas de humo (una vez)."""
    from panda3d.core import ColorWriteAttrib, TransparencyAttrib
    from ursina import Entity
    from ursina.shaders import unlit_shader
    for k, e in enumerate(grupo.entidades):
        e.setTransparency(TransparencyAttrib.M_alpha)     # una sola pasada (M_dual son dos llamadas de dibujo)
        e.setTwoSided(True)
        e.setDepthWrite(False)
        e.humo = []
        for j in range(ftc.BOCANADAS_HUMO):
            # una malla por bocanada: un Mesh es un nodo y solo puede colgar de una entidad
            b = Entity(parent=e, model=mesh_bocanada(), shader=unlit_shader, unlit=True, billboard=True,
                       name=f"humo_{grupo.nombre}_{k}_{j}")
            b.ignore = True
            b.setTransparency(TransparencyAttrib.M_alpha)
            b.setDepthWrite(False)
            # solo RGB: si el humo escribe su alfa en el framebuffer, la composición final lo hace desaparecer
            b.setAttrib(ColorWriteAttrib.make(ColorWriteAttrib.C_rgb))
            b.setTwoSided(True)
            e.humo.append(b)


TONOS_HUMO = tuple(tuple((HUMO_OSCURO[i] + (HUMO_CLARO[i] - HUMO_OSCURO[i]) * k / 15) / 255 for i in range(3))
                   for k in range(16))              # tono por fase, precalculado (nada de listas por frame)


def animar(e, t, u, ancho, alto, giro, color):
    """Un frame del fuego `e`: parpadeo de la llama (ancho/alto de ciudad_viva_calculos.parpadeo_fuego) a la escala del
    tejado, y el humo (compensando la escala del padre para que no parpadee con la llama). Métodos de NodePath directos:
    los setters de Ursina cuestan varias veces más y esto corre por cada fuego visible en cada frame."""
    k = ftc.ESCALA_FUEGO_TEJADO
    sx, sy = max(1e-4, ancho * k), max(1e-4, alto * k)
    e.setScale(sx, sy, sx)
    e.setH(-giro)
    # Ursina bloquea en el nodo del MODELO la escala de color heredada (Entity.color hace model.setColorScaleOff):
    # el tinte va al modelo, no a la entidad.
    e.model.setColorScale(color[0], color[1], color[2], 1.0)
    fundido = min(1.0, max(0.0, ancho / 0.6))             # el humo aparece y se va con el fundido del fuego
    for j, b in enumerate(getattr(e, "humo", ())):
        dx, dy, dz, diametro, alfa, fase = ftc.ciclo_humo(t, u, j)
        b.setPos(dx / sx, dy / sy, dz / sx)                # m del mundo / escala del padre
        b.setScale(diametro / sx, diametro / sy, diametro / sx)
        tono = TONOS_HUMO[min(15, int(fase * 16))]
        b.model.setColorScale(tono[0], tono[1], tono[2], alfa * fundido)

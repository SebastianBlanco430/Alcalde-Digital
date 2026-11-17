# «Satélite»: una foto de la ciudad vista desde arriba, hecha con el propio mundo 3D (techos, calles, plazas y árboles tal como
# se ven en el juego), para usarla de fondo del minimapa y del mapa de la ciudad (estilo GTA).
#
# CÓMO. Una cámara ORTOGRÁFICA mira hacia abajo y renderiza UNA vez el mundo a una textura en memoria (Panda3D: buffer de
# textura con `toRam`). La textura final es una imagen normal (sin buffer vivo), así que sobrevive a cambiar de pantalla
# completa. Solo se dibuja la ciudad estática: la cámara tiene como escena la raíz de la ciudad (`Camera.set_scene`), por lo
# que no salen peatones, jugadores, vehículos ni balizas, y la niebla se apaga durante la captura.
#
# ORIENTACIÓN. Para no equivocarse de espejo o de giro, la posición de la foto en el mundo no se supone: se pregunta a la
# propia lente (`uv_de(x, z)` proyecta un punto del mundo a coordenadas de la textura). Así el minimapa y el mapa grande
# colocan la foto con la misma geometría que ya usan para las calles y las plazas.
#
# BANDERA. SATELITE = False o ALCALDE_SATELITE=0: nada de esto se usa (el minimapa vectorial de siempre).
# GUARDIÁN. Si la captura falla (sin GPU, buffer imposible…) devuelve None y avisa UNA vez por stderr; el mapa sigue como hoy.
#
# Lo puro (tamaño de la imagen, márgenes, validación) está al principio y se prueba sin ventana.

import math
import os
import sys

SATELITE = True
PX_POR_METRO = 10.0          # resolución de la foto
LADO_MIN = 512
LADO_MAX = 2048              # tope de la textura (una GPU modesta lo admite de sobra)
MARGEN_M = 4.0               # metros de más alrededor de los límites del mundo
ALTURA_CAMARA = 400.0
COLOR_FONDO = (0.10, 0.11, 0.15, 1.0)

_avisados = set()


def activo():
    valor = os.environ.get("ALCALDE_SATELITE", "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "on"):
        return True
    return SATELITE


def _avisar_una_vez(clave, error):
    if clave in _avisados:
        return
    _avisados.add(clave)
    try:
        print(f"[Satélite] {clave}: {type(error).__name__}: {error} (se usa el minimapa de siempre)", file=sys.stderr)
    except Exception:                                  # noqa: BLE001
        pass


# -- Lo puro -------------------------------------------------------------------

def area_con_margen(limites, margen=MARGEN_M):
    """(xmin, xmax, zmin, zmax) de `limites()` ampliado `margen` metros por cada lado. ValueError si no es un rectángulo."""
    xmin, xmax, zmin, zmax = (float(v) for v in limites)
    if not all(math.isfinite(v) for v in (xmin, xmax, zmin, zmax)) or xmax <= xmin or zmax <= zmin:
        raise ValueError(f"límites no válidos: {limites!r}")
    return (xmin - margen, xmax + margen, zmin - margen, zmax + margen)


def tamano_imagen(ancho_m, alto_m, px_por_metro=PX_POR_METRO, lado_min=LADO_MIN, lado_max=LADO_MAX):
    """(ancho_px, alto_px) con la proporción del mundo: el lado largo a px_por_metro, entre lado_min y lado_max."""
    if ancho_m <= 0 or alto_m <= 0:
        raise ValueError("el área del mundo no tiene tamaño")
    largo = max(ancho_m, alto_m)
    lado = max(lado_min, min(lado_max, int(round(largo * px_por_metro))))
    escala = lado / largo
    return (max(16, int(round(ancho_m * escala))), max(16, int(round(alto_m * escala))))


class Satelite:
    """La foto: `textura` (panda3d Texture), `area` (xmin, xmax, zmin, zmax en metros) y `uv_de(x, z)` -> (u, v) en [0, 1]."""

    def __init__(self, textura, area, uv_de, tamano):
        self.textura = textura
        self.area = area
        self.uv_de = uv_de
        self.tamano = tamano

    def esquinas(self):
        """Las 4 esquinas del área en el mundo, en orden (xmin,zmin) (xmax,zmin) (xmax,zmax) (xmin,zmax)."""
        xmin, xmax, zmin, zmax = self.area
        return [(xmin, zmin), (xmax, zmin), (xmax, zmax), (xmin, zmax)]


# -- La captura -------------------------------------------------------------------

def capturar(raiz, limites, px_por_metro=PX_POR_METRO, margen=MARGEN_M, ocultar=()):
    """Renderiza la ciudad `raiz` (NodePath/Entity) desde arriba y devuelve un Satelite, o None si no se pudo (avisa una vez).
    `ocultar`: nodos que tapan la vista desde arriba (el cielo) y se esconden solo durante la captura."""
    if not activo():
        return None
    try:
        return _capturar(raiz, limites, px_por_metro, margen, ocultar)
    except Exception as error:                         # noqa: BLE001
        _avisar_una_vez("captura", error)
        return None


def _capturar(raiz, limites, px_por_metro, margen, ocultar=()):
    from panda3d.core import (Camera, NodePath, OrthographicLens, Point2, Point3, PNMImage, Texture, Vec3, Vec4)
    from ursina import application

    base = application.base
    xmin, xmax, zmin, zmax = area_con_margen(limites, margen)
    ancho_px, alto_px = tamano_imagen(xmax - xmin, zmax - zmin, px_por_metro)

    lente = OrthographicLens()
    lente.set_film_size(xmax - xmin, zmax - zmin)
    lente.set_near_far(1.0, ALTURA_CAMARA * 3)
    camara = Camera("satelite")
    camara.set_lens(lente)
    nodo = NodePath(camara)
    nodo.reparent_to(base.render)
    cx, cz = (xmin + xmax) / 2, (zmin + zmax) / 2
    nodo.set_pos(cx, ALTURA_CAMARA, cz)
    nodo.look_at(Point3(cx, 0.0, cz), Vec3(0.0, 0.0, 1.0))      # mira hacia abajo con +Z como «arriba» de la foto
    raiz_np = raiz if isinstance(raiz, NodePath) else raiz
    camara.set_scene(raiz_np)                                    # solo la ciudad estática

    textura = Texture("satelite_ram")
    buffer = base.win.make_texture_buffer("satelite", ancho_px, alto_px, textura, True)
    if buffer is None:
        nodo.remove_node()
        raise RuntimeError("no se pudo crear el buffer de textura")
    niebla = _apagar_niebla()
    escondidos = [n for n in ocultar if n is not None and not n.is_hidden()]
    for n in escondidos:
        n.hide()
    try:
        buffer.set_clear_color(Vec4(*COLOR_FONDO))
        buffer.set_clear_color_active(True)
        buffer.set_one_shot(True)
        region = buffer.make_display_region()
        region.set_camera(nodo)
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        imagen = PNMImage()
        if not textura.store(imagen) or imagen.get_x_size() < 8:
            raise RuntimeError("la textura quedó vacía")
        final = Texture("satelite")
        final.load(imagen)
        final.set_minfilter(Texture.FT_linear_mipmap_linear)
        final.set_magfilter(Texture.FT_linear)
        final.set_wrap_u(Texture.WM_clamp)
        final.set_wrap_v(Texture.WM_clamp)

        # La foto es una proyección ortográfica: u y v son AFINES en (x, z). Se miden con la lente mientras la cámara existe.
        def proyectar(x, z):
            p = Point2()
            lente.project(nodo.get_relative_point(base.render, Point3(float(x), 0.0, float(z))), p)
            return ((p.x + 1.0) / 2.0, (p.y + 1.0) / 2.0)

        o, a, b = proyectar(xmin, zmin), proyectar(xmax, zmin), proyectar(xmin, zmax)
        ax, az = xmax - xmin, zmax - zmin

        def uv_de(x, z):
            fx, fz = (x - xmin) / ax, (z - zmin) / az
            return (o[0] + fx * (a[0] - o[0]) + fz * (b[0] - o[0]), o[1] + fx * (a[1] - o[1]) + fz * (b[1] - o[1]))

        resultado = Satelite(final, (xmin, xmax, zmin, zmax), uv_de, (ancho_px, alto_px))
    finally:
        for n in escondidos:
            n.show()
        _restaurar_niebla(niebla)
        try:
            base.graphics_engine.remove_window(buffer)
        except Exception:                              # noqa: BLE001
            pass
        nodo.remove_node()
    return resultado


def _apagar_niebla():
    """La niebla es global (shaders): se apaga durante la captura (densidad 0 y color transparente, como niebla.desactivar_niebla:
    con alfa 0 los shaders no mezclan nada) y se devuelve lo que había."""
    from ursina import scene
    antes = (scene.fog_color, scene.fog_density)
    try:
        from frontend import niebla
        niebla.desactivar_niebla()
    except Exception:                                  # noqa: BLE001
        pass
    return antes


def _restaurar_niebla(antes):
    from ursina import scene
    try:
        scene.fog_color, scene.fog_density = antes
    except Exception:                                  # noqa: BLE001
        pass

# Piezas 3D comunes de la familia CORCHO (Ursina): notas de papel con cabecera, sellos de goma, aspa roja, hilo/cordel de
# cinta, polaroid «TÚ», círculos. Todo cuelga del plano local de un ancla (metros, +x derecha, +y arriba, cara visible -z)
# o de un papel de papel_3d (su pivote, también en metros). Capas en z (m, negativas = delante): ver papel_3d.
# Solo presentación: el contenido (textos, horas, estados) lo pasan rastrear_3d / cronologia_3d leyendo la vista 2D viva.

from ursina import Entity, Mesh
from ursina.shaders import lit_with_shadows_shader

from frontend import estilo
from frontend.componentes import a_unidades, destruir_arbol, rgb
from frontend.minijuegos import ui as ui_2d
from frontend.minijuegos_3d import corcho_calculos as cc
from frontend.minijuegos_3d import papel_3d

TINTA = getattr(estilo, "TINTA", (18, 20, 32))
PAPEL = papel_3d.PAPEL
ROJO = getattr(estilo, "ESTADO_ERROR", (214, 62, 62))
ROJO_OSCURO = (150, 34, 40)
VERDE = getattr(estilo, "ESTADO_EXITO", (80, 190, 110))
AMARILLO = (255, 220, 60)
GRIS_PAPEL = (196, 186, 168)
GRIS_TINTA = (96, 90, 96)
BLANCO = (250, 250, 246)
HILO = (206, 30, 38)
Z_HILO = -0.014
GROSOR_HILO = 0.0045


def lineas(cadena, alto_linea, ancho, negrita=False):
    """Nº de líneas que ocupará `cadena` con texto_en_papel (mismo ajuste: ui.lineas_de a PX_REFERENCIA)."""
    k = alto_linea / a_unidades(papel_3d.PX_REFERENCIA)
    return len(ui_2d.lineas_de(str(cadena), papel_3d.PX_REFERENCIA, ancho / k, negrita))


def recortar_lineas(cadena, alto_linea, ancho, maximo, negrita=False):
    """`cadena` recortada (con «…») hasta que quepa en `maximo` líneas (como el rótulo de las viñetas 2D)."""
    cadena = str(cadena)
    while lineas(cadena, alto_linea, ancho, negrita) > maximo and len(cadena) > 4:
        cadena = cadena.rstrip("…")[:-1].rstrip(" «(·") + "…"
    return cadena


def ancho_texto(cadena, alto_linea, ancho, negrita=False):
    """Ancho (m) de la línea más larga de `cadena` envuelta como texto_en_papel."""
    k = alto_linea / a_unidades(papel_3d.PX_REFERENCIA)
    partes = ui_2d.lineas_de(str(cadena), papel_3d.PX_REFERENCIA, ancho / k, negrita)
    return max((ui_2d.medir(p, papel_3d.PX_REFERENCIA, negrita) for p in partes), default=0.0) * k


def ancho_sello(cadena, alto_linea):
    return len(cadena) * alto_linea * 0.62 + alto_linea * 1.2


def alto_texto(n, alto_linea):
    return n * alto_linea * ui_2d.LINEA


def texto(hoja, cadena, alto_linea, ancho=None, tono=TINTA, posicion=None, negrita=False, centrado=False):
    t = papel_3d.texto_en_papel(hoja, cadena, alto_linea=alto_linea, ancho=ancho, tono=tono, posicion=posicion,
                                negrita=negrita, centrado=centrado)
    t.ignore = True
    return t


def texto_centrado(hoja, cadena, alto_linea, ancho, y=0.0, tono=TINTA, negrita=True, x=0.0):
    """Texto centrado en (x, y) del papel (vertical y horizontalmente)."""
    n = lineas(cadena, alto_linea, ancho, negrita)
    t = texto(hoja, cadena, alto_linea, ancho, tono, (0.0, y + alto_texto(n, alto_linea) / 2), negrita, centrado=True)
    t.x = x
    return t


def circulo(padre, posicion, diametro, tono, z=-0.002, iluminado=False):
    return Entity(parent=padre, model="circle", color=rgb(tono), scale=diametro, position=(posicion[0], posicion[1], z),
                  shader=lit_with_shadows_shader if iluminado else None, ignore=True)


def rect(padre, posicion, escala, tono, z=-0.002, giro=0.0, iluminado=True):
    return Entity(parent=padre, model="quad", color=rgb(tono), scale=escala, position=(posicion[0], posicion[1], z),
                  rotation_z=giro, shader=lit_with_shadows_shader if iluminado else None, ignore=True)


def sello(padre, cadena, posicion, tono, alto_linea, giro=-6.0, capa=2, ancho=None):
    """Sello de goma: marco del color y papel dentro, con el texto en ese color (como piezas_papel.sello_goma)."""
    tono = estilo.tono_legible(tono, PAPEL)
    ancho = ancho or ancho_sello(cadena, alto_linea)
    alto = alto_linea * 1.75
    marco = papel_3d.papel(padre, ancho, alto, posicion=posicion, giro=giro, tono=tono, capa=capa)
    dentro = papel_3d.papel(marco, ancho - alto_linea * 0.28, alto - alto_linea * 0.28, tono=PAPEL, capa=0)
    texto_centrado(dentro, cadena, alto_linea, ancho * 1.5, 0.0, tono, negrita=True)
    return marco


def aspa(padre, ancho, alto, tono=ROJO, grosor=0.018, z=-0.016):
    """X roja sobre un papel (intento perdido)."""
    import math
    raiz = Entity(parent=padre, z=z, ignore=True)
    largo = math.hypot(ancho, alto) * 0.78
    ang = math.degrees(math.atan2(alto, ancho))
    for g in (ang, -ang):
        rect(raiz, (0, 0), (largo, grosor), tono, z=0.0, giro=g, iluminado=False)
    return raiz


class Cinta(Entity):
    """Hilo rojo / cordel: cinta plana que pasa por puntos (x, y) del plano del padre, en z fijo. fijar(puntos)."""

    def __init__(self, padre, tono=HILO, grosor=GROSOR_HILO, z=Z_HILO, iluminado=False):
        super().__init__(parent=padre, z=z, ignore=True)
        self.grosor = grosor
        self.malla = None
        self.tono = tono
        self.iluminado = iluminado

    def fijar(self, puntos):
        v, t = cc.cinta(puntos, self.grosor)
        if not v:
            self.enabled = False
            return
        self.enabled = True
        if self.malla is None:
            self.malla = Mesh(vertices=v, triangles=t, mode="triangle")
            self.model = self.malla
            self.color = rgb(self.tono)
            self.double_sided = True
            self.shader = lit_with_shadows_shader if self.iluminado else None
        else:
            self.malla.vertices = v
            self.malla.triangles = t
            self.malla.generate()


def polaroid_tu(padre, disp, giro=2.0):
    """Polaroid «TÚ» (retrato sencillo como piezas_papel.polaroid_retrato) con chincheta verde."""
    s = disp["s"]
    cx, cy, w, h = disp["polaroid"]
    pol = papel_3d.papel(padre, w, h, posicion=(cx, cy), giro=giro, tono=BLANCO)
    fx, fy, fw, fh = disp["foto"]
    foto = papel_3d.papel(pol, fw, fh, posicion=(fx, fy), tono=(176, 214, 236), capa=0)
    camisa = (70, 120, 170)
    rect(foto, (0, -fh / 2 + 0.03 * s), (0.13 * s, 0.06 * s), camisa, z=-0.0015)
    circulo(foto, (0, 0.022 * s), 0.096 * s, (52, 38, 34), z=-0.002)
    circulo(foto, (0, 0.006 * s), 0.08 * s, (224, 172, 132), z=-0.0028)
    for dx in (-0.016, 0.016):
        circulo(foto, (dx * s, 0.01 * s), 0.008 * s, TINTA, z=-0.0034, iluminado=False)
    texto_centrado(pol, "TÚ", cc.LINEA_RUMOR * s * 1.1, w, -h / 2 + 0.05 * s, TINTA, negrita=True)
    papel_3d.chincheta(padre, disp["pin_tu"], VERDE).ignore = True
    return pol


def destruir(e):
    if e is not None:
        try:
            destruir_arbol(e)
        except Exception:                # noqa: BLE001
            pass


def vivo(e):
    try:
        return e is not None and not e.is_empty()
    except Exception:                    # noqa: BLE001
        return False

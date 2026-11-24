# Decorados 3D de las tres salas de la Fiscalía (Ursina). Los planos (dónde va cada cosa) están en
# frontend/fiscalia/salas_calculos.py; aquí solo se arman con piezas (frontend/piezas.py: lit_with_shadows) del estilo de
# los interiores de los minijuegos 3D, y lo estático de cada sala se combina en una malla (pocas llamadas de dibujo).
# La tinta del cómic la pone el pase final de pantalla (frontend/pase_final.py) igual que en el resto del juego.
#
#   oficina      escritorio con lámpara, papeles y placa; sillón del fiscal; librería, bandera y diplomas al norte;
#                ventana con persiana al este; alfombra; planta.
#   laboratorio  dos terminales (mesa, monitor encendido, teclado, silla SUELTA para animarla) con su rótulo; racks de
#                servidores con luces; mesa de pruebas; franja de neón; puerta a la sala.
#   sala         mesa metálica, dos sillas, lámpara colgante, vidrio espejado en la pared oeste con la sala de
#                observación detrás (el fiscal mira desde ahí), puerta metálica, cámara en la esquina.

import math

from ursina import Entity, Text, color
from ursina.shaders import lit_with_shadows_shader

from frontend import materiales as mat
from frontend.componentes import rgb
from frontend.fiscalia import salas_calculos as sc
from frontend.piezas import MASCARA_LUZ, pieza, silenciar, texto_sin_tinta

MADERA = (150, 104, 66)
MADERA_OSCURA = (92, 62, 42)
MADERA_CLARA = (186, 140, 92)
METAL = (62, 64, 74)
METAL_CLARO = (128, 132, 144)
TELA = (52, 56, 74)
CUERO = (78, 40, 36)
BLANCO = (236, 236, 240)


def _p(padre, color_rgb, pos, escala, modelo="cube", **o):
    return pieza(parent=padre, model=modelo, color=rgb(color_rgb), position=pos, scale=escala, **o)


def _texto(padre, cadena, pos, escala, tono=(240, 240, 245), rotation_y=180):
    t = Text(cadena, parent=padre, origin=(0, 0), position=pos, scale=escala, color=rgb(tono), rotation_y=rotation_y)
    texto_sin_tinta(t)
    return t


def _cuarto(raiz, plano, pared, piso, zocalo, acento, hueco_oeste=None, sin_sur=False):
    """Piso, cuatro paredes (con un hueco en la oeste si se pide: (z_centro, ancho, y0, y1)), zócalo, rodapié y franja.
    sin_sur: corte (la pared sur no se dibuja: la cámara del laboratorio mira desde ahí)."""
    ox, oz = plano.origen
    w, d, h = plano.ancho, plano.fondo, plano.alto
    g = Entity(parent=raiz, shader=lit_with_shadows_shader)
    _p(g, piso, (ox, -0.05, oz), (w, 0.1, d))
    _p(g, pared, (ox, h / 2, oz + d / 2 + 0.05), (w + 0.2, h, 0.1))            # norte
    if not sin_sur:
        _p(g, pared, (ox, h / 2, oz - d / 2 - 0.05), (w + 0.2, h, 0.1))        # sur
    _p(g, pared, (ox + w / 2 + 0.05, h / 2, oz), (0.1, h, d))                  # este
    x_o = ox - w / 2 - 0.05
    if hueco_oeste is None:
        _p(g, pared, (x_o, h / 2, oz), (0.1, h, d))
    else:
        zc, ancho, y0, y1 = hueco_oeste
        z0, z1 = zc - ancho / 2, zc + ancho / 2
        _p(g, pared, (x_o, h / 2, (oz - d / 2 + z0) / 2), (0.1, h, z0 - (oz - d / 2)))
        _p(g, pared, (x_o, h / 2, (z1 + oz + d / 2) / 2), (0.1, h, oz + d / 2 - z1))
        _p(g, pared, (x_o, y0 / 2, zc), (0.1, y0, ancho))
        _p(g, pared, (x_o, (y1 + h) / 2, zc), (0.1, h - y1, ancho))
    # zócalo (hasta 1 m), franja de acento y rodapié en las cuatro paredes
    for (x, z, sx, sz) in ((ox, oz + d / 2 - 0.02, w, 0.03), (ox, oz - d / 2 + 0.02, w, 0.03),
                           (ox + w / 2 - 0.02, oz, 0.03, d), (ox - w / 2 + 0.02, oz, 0.03, d)):
        if (hueco_oeste is not None and x < ox - w / 2 + 0.1) or (sin_sur and z < oz - d / 2 + 0.1):
            continue
        _p(g, zocalo, (x, 0.5, z), (sx, 1.0, sz))
        _p(g, acento, (x, 1.02, z), (sx + 0.01, 0.06, sz + 0.01))
        _p(g, BLANCO, (x, 0.06, z), (sx + 0.015, 0.12, sz + 0.015))
    return g


def _aclarar(tono, k):
    return tuple(max(0, min(255, int(c * k))) for c in tono)


def _silla(padre, asiento, tono=TELA, suelta=False):
    """Silla de oficina en `asiento` (mira a su rumbo): asiento con canto, respaldo con marco y acolchado más claro
    (1,5 cm por delante, con costura), unido al asiento por un tubo; pie central y base en cruz. Suelta = Entity propia
    con el origen en el suelo bajo el asiento (contrato de cinematica_silla: entidad_silla).
    Antes el respaldo era una losa lisa de un tono (0,46 × 0,55 × 0,06): en pecho se leía como un rectángulo plano."""
    raiz = Entity(parent=padre, position=(asiento.x, 0, asiento.z), rotation_y=asiento.rumbo,
                  shader=lit_with_shadows_shader, name="silla_fiscalia")
    a = sc.ALTURA_ASIENTO
    claro, oscuro = _aclarar(tono, 1.45), _aclarar(tono, 0.7)
    _p(raiz, oscuro, (0, a - 0.05, 0), (0.48, 0.05, 0.48))                     # bastidor del asiento
    _p(raiz, tono, (0, a - 0.01, 0.01), (0.44, 0.04, 0.44))                     # cojín del asiento
    _p(raiz, METAL, (0, a + 0.1, -0.235), (0.05, 0.22, 0.03))                   # tubo asiento → respaldo
    _p(raiz, oscuro, (0, a + 0.4, -0.235), (0.44, 0.4, 0.05))                   # marco del respaldo
    _p(raiz, claro, (0, a + 0.4, -0.2), (0.36, 0.32, 0.02))                     # acolchado (1,5 cm delante)
    _p(raiz, oscuro, (0, a + 0.4, -0.188), (0.36, 0.012, 0.006))                # costura
    _p(raiz, METAL, (0, 0.22, 0), (0.06, 0.4, 0.06))                            # pie
    for k, rot in enumerate((45, -45)):                                         # base en cruz (2 mm de desfase: sin
        _p(raiz, METAL, (0, 0.03 + 0.002 * k, 0), (0.56, 0.04, 0.06), rotation_y=rot)   # caras coplanares)
    raiz.combine()
    if not suelta:
        silenciar(raiz)
    return raiz


def _silla_metalica(padre, asiento, tono=METAL_CLARO, suelta=False):
    """Silla de la sala de interrogatorio: estructura de tubo de acero (patas que siguen hasta el respaldo, travesaño
    arriba y reposapiés), respaldo de chapa con grosor sobre dos travesaños con hueco entre ellos (la pared se ve por el
    hueco: la tinta dibuja su contorno) y asiento con canto. Ninguna cara comparte plano con otra.
    Antes era la misma losa plana de la silla de oficina: un rectángulo gris detrás de cada interrogado."""
    raiz = Entity(parent=padre, position=(asiento.x, 0, asiento.z), rotation_y=asiento.rumbo,
                  shader=lit_with_shadows_shader, name="silla_fiscalia")
    a = sc.ALTURA_ASIENTO
    tubo, t = METAL, 0.035
    chapa, chapa_canto = tono, _aclarar(tono, 0.78)
    _p(raiz, chapa_canto, (0, a - 0.035, 0), (0.46, 0.04, 0.44))               # canto del asiento
    _p(raiz, chapa, (0, a - 0.005, 0.005), (0.42, 0.02, 0.4))                   # asiento
    for sx in (-1, 1):
        x = sx * 0.21
        _p(raiz, tubo, (x, (a - 0.055) / 2, 0.19), (t, a - 0.055, t))           # pata delantera
        _p(raiz, tubo, (x, (a + 0.56) / 2, -0.2), (t, a + 0.56, t))             # pata trasera hasta el respaldo
        _p(raiz, tubo, (x, 0.14, -0.005), (t * 0.7, t * 0.7, 0.36))             # travesaño lateral bajo
    _p(raiz, tubo, (0, 0.14, 0.19), (0.39, t * 0.7, t * 0.7))                  # reposapiés
    _p(raiz, tubo, (0, a + 0.56, -0.2), (0.47, 0.045, 0.045))                  # travesaño de arriba
    _p(raiz, chapa_canto, (0, a + 0.4, -0.205), (0.39, 0.24, 0.035))            # respaldo (chapa con grosor)
    _p(raiz, chapa, (0, a + 0.4, -0.184), (0.33, 0.18, 0.01))                   # cara del respaldo, 0,35 cm delante
    for y in (a + 0.13, a + 0.21):                                               # travesaños con hueco
        _p(raiz, tubo, (0, y, -0.2), (0.39, 0.03, 0.025))
    raiz.combine()
    if not suelta:
        silenciar(raiz)
    return raiz


CUERO_CLARO = (112, 62, 50)
CUERO_COSTURA = (58, 30, 28)


def _sillon(padre, asiento):
    """Sillón del fiscal: respaldo con marco, acolchado más claro con costuras y remate arriba, brazos, pie de metal.
    Antes era una losa lisa de 0,46 × 0,85 de un solo tono: detrás de la cabeza, en pecho, se leía como un rectángulo
    marrón plano recortado contra la pared (sin volumen ni tinta por dentro)."""
    raiz = Entity(parent=padre, position=(asiento.x, 0, asiento.z), rotation_y=asiento.rumbo,
                  shader=lit_with_shadows_shader, name="sillon_fiscal")
    a = sc.ALTURA_ASIENTO
    _p(raiz, CUERO, (0, a - 0.04, 0.0), (0.54, 0.1, 0.5))                       # asiento
    _p(raiz, CUERO, (0, a + 0.38, -0.27), (0.52, 0.72, 0.08))                   # marco del respaldo
    _p(raiz, CUERO_CLARO, (0, a + 0.36, -0.222), (0.4, 0.58, 0.02))             # acolchado (1,5 cm delante)
    for dy in (0.18, 0.36, 0.54):                                                # costuras del acolchado
        _p(raiz, CUERO_COSTURA, (0, a + dy, -0.209), (0.4, 0.014, 0.008))
    _p(raiz, CUERO_CLARO, (0, a + 0.76, -0.27), (0.58, 0.13, 0.14), modelo="sphere")   # remate: rollo redondo
    for s in (-1, 1):
        _p(raiz, CUERO, (s * 0.3, a + 0.2, -0.02), (0.06, 0.05, 0.42))          # brazo
        _p(raiz, METAL, (s * 0.3, a + 0.08, 0.1), (0.035, 0.2, 0.035))
    _p(raiz, METAL, (0, 0.22, 0), (0.06, 0.4, 0.06))
    _p(raiz, METAL, (0, 0.03, 0), (0.5, 0.05, 0.5))
    raiz.combine()
    silenciar(raiz)
    return raiz


def _lampara_colgante(padre, x, z, alto, largo=0.7):
    _p(padre, (40, 40, 46), (x, alto - largo / 2, z), (0.015, largo, 0.015))
    _p(padre, (52, 58, 70), (x, alto - largo - 0.05, z), (0.5, 0.1, 0.5))


def _bombilla(padre, x, y, z, tono=(255, 238, 176), escala=0.14):
    return Entity(parent=padre, model="sphere", color=rgb(tono), position=(x, y, z), scale=escala, shader=None)


# ---------------------------------------------------------------------------------------------------------- oficina

def construir_oficina(padre, plano, nombre_fiscal="Fiscal Rojas"):
    raiz = Entity(parent=padre, name="sala_oficina")
    ox, oz = plano.origen
    w, d, h = plano.ancho, plano.fondo, plano.alto
    g = _cuarto(raiz, plano, pared=(214, 198, 168), piso=(132, 92, 60), zocalo=MADERA_OSCURA, acento=(178, 54, 58))
    mx, mz, mw, md, my = plano.mesas[0]
    # alfombra
    _p(g, (120, 40, 48), (ox, 0.006, oz + 0.3), (3.4, 0.012, 3.0))
    _p(g, (196, 150, 70), (ox, 0.008, oz + 0.3), (3.0, 0.012, 2.6))
    _p(g, (120, 40, 48), (ox, 0.01, oz + 0.3), (2.8, 0.012, 2.4))
    # escritorio: tablero, faldón al lado del visitante, cajoneras
    _p(g, MADERA, (mx, my - 0.03, mz), (mw, 0.06, md))
    _p(g, MADERA_OSCURA, (mx, (my - 0.06) / 2, mz - md / 2 + 0.03), (mw - 0.04, my - 0.06, 0.04))
    for dx in (-mw / 2 + 0.25, mw / 2 - 0.25):
        _p(g, MADERA_OSCURA, (mx + dx, (my - 0.06) / 2, mz), (0.46, my - 0.06, md - 0.08))
    # sobre la mesa: lámpara de banquero, carpeta, papeles, teléfono, placa
    _p(g, (196, 160, 60), (mx - 0.7, my + 0.012, mz + 0.18), (0.16, 0.025, 0.12))
    _p(g, (196, 160, 60), (mx - 0.7, my + 0.16, mz + 0.2), (0.02, 0.28, 0.02))
    _p(g, (36, 110, 70), (mx - 0.7, my + 0.31, mz + 0.16), (0.36, 0.07, 0.14))
    _p(g, (204, 70, 60), (mx + 0.25, my + 0.012, mz - 0.05), (0.34, 0.02, 0.26))
    _p(g, (244, 240, 228), (mx - 0.15, my + 0.006, mz - 0.1), (0.24, 0.012, 0.32), rotation_y=8)
    _p(g, (244, 240, 228), (mx - 0.22, my + 0.009, mz - 0.06), (0.24, 0.012, 0.32), rotation_y=-14)
    _p(g, (30, 30, 36), (mx + 0.7, my + 0.03, mz + 0.15), (0.2, 0.06, 0.16))
    _p(g, MADERA_OSCURA, (mx, my + 0.05, mz - md / 2 + 0.12), (0.5, 0.1, 0.04), rotation_x=-20)
    # sillón del fiscal (respaldo alto, cuero) y silla del visitante
    a_f, a_j = plano.asientos["hablante"], plano.asientos["jugador"]
    _sillon(raiz, a_f)
    silla_jugador = _silla(raiz, a_j, tono=TELA, suelta=True)
    # librería (pared norte), bandera, diplomas
    # Mueble HUECO (fondo, costados, techo y zócalo) con baldas y libros dentro, cada cara en su propio plano. Antes era
    # una caja maciza con los libros y las baldas DENTRO y sus frentes en el mismo plano que el del mueble (z-fighting:
    # rayas de colores que parpadeaban en los planos de pecho del fiscal) y la fila de arriba asomaba por el techo.
    lib_z = oz + d / 2 - 0.2
    lx, l_ancho, l_alto, l_fondo = ox - 1.6, 2.0, 2.2, 0.36
    _p(g, MADERA_OSCURA, (lx, l_alto / 2, lib_z + l_fondo / 2 - 0.02), (l_ancho, l_alto, 0.04))          # fondo
    for s in (-1, 1):
        _p(g, MADERA_OSCURA, (lx + s * (l_ancho / 2 - 0.02), l_alto / 2, lib_z), (0.04, l_alto, l_fondo))  # costados
    _p(g, MADERA_OSCURA, (lx, l_alto - 0.02, lib_z), (l_ancho - 0.07, 0.04, l_fondo))                         # techo
    _p(g, MADERA_OSCURA, (lx, 0.05, lib_z), (l_ancho - 0.07, 0.1, l_fondo))                                   # zócalo
    tonos = ((190, 70, 70), (70, 110, 190), (230, 190, 80), (90, 160, 100), (150, 90, 170), (230, 140, 70))
    for fila in range(4):
        y_balda = 0.3 + fila * 0.5
        _p(g, MADERA, (lx, y_balda, lib_z - 0.005), (l_ancho - 0.07, 0.03, l_fondo - 0.03))              # 1 cm atrás
        libre = (0.5 if fila < 3 else l_alto - 0.04 - y_balda) - 0.04                     # hasta la balda de arriba
        for k in range(9):
            alto = min(0.3 + 0.08 * ((k * 7 + fila * 3) % 3), libre)
            _p(g, tonos[(k + fila * 2) % len(tonos)], (ox - 2.45 + k * 0.2, y_balda + 0.015 + alto / 2, lib_z - 0.02),
               (0.13, alto, 0.22))                                                                     # 4 cm atrás
    _p(g, (200, 200, 205), (ox + 2.75, 1.2, oz + d / 2 - 0.35), (0.04, 2.4, 0.04))
    _p(g, (40, 92, 170), (ox + 2.5, 1.95, oz + d / 2 - 0.35), (0.42, 0.5, 0.02))
    _p(g, (255, 220, 60), (ox + 2.5, 1.95, oz + d / 2 - 0.36), (0.16, 0.16, 0.02))
    for k, x in enumerate((ox + 0.35, ox + 0.95)):
        _p(g, MADERA_OSCURA, (x, 1.85 - 0.1 * k, oz + d / 2 - 0.02), (0.44, 0.34, 0.03))
        _p(g, (246, 242, 226), (x, 1.85 - 0.1 * k, oz + d / 2 - 0.04), (0.36, 0.26, 0.02))
    # ventana con persiana (este)
    wx = ox + w / 2 - 0.04
    _p(g, BLANCO, (wx, 1.65, oz + 0.2), (0.06, 1.3, 1.6))
    _p(g, (150, 205, 235), (wx - 0.03, 1.65, oz + 0.2), (0.04, 1.16, 1.46))
    for k in range(8):
        _p(g, (226, 222, 210), (wx - 0.07, 1.15 + k * 0.14, oz + 0.2), (0.02, 0.05, 1.44))
    # puerta (sur) y planta
    px, pz = plano.puerta
    _p(g, (30, 30, 38), (px, 1.15, pz + 0.015), (1.14, 2.34, 0.03))
    _p(g, MADERA_OSCURA, (px, 1.1, pz + 0.04), (1.0, 2.2, 0.03))
    _p(g, (220, 200, 120), (px + 0.36, 1.05, pz + 0.08), (0.08, 0.08, 0.08), modelo="sphere")
    _p(g, (160, 100, 70), (ox + 2.6, 0.25, oz - 2.1), (0.4, 0.5, 0.4))
    _p(g, (60, 140, 70), (ox + 2.6, 0.95, oz - 2.1), (0.8, 0.9, 0.8), modelo="sphere")
    g.combine()
    silenciar(g)
    # rótulo de la placa y escudo (texto aparte: no se combina)
    _texto(raiz, nombre_fiscal, (mx, my + 0.06, mz - md / 2 + 0.095), 0.9, tono=(250, 226, 150), rotation_y=0)
    _bombilla(raiz, mx - 0.7, my + 0.27, mz + 0.16, escala=0.08)
    silenciar(raiz)
    return raiz, {"silla_jugador": silla_jugador}


# ------------------------------------------------------------------------------------------------------ laboratorio

class PantallaTerminal:
    """El monitor de un terminal: quad sin luz con el nombre del servidor y su estado."""

    def __init__(self, padre, terminal, nombre):
        c = terminal.pantalla["centro"]
        self.quad = Entity(parent=padre, model="quad", position=c, scale=(terminal.pantalla["ancho"],
                                                                          terminal.pantalla["alto"]),
                           color=rgb((14, 40, 66)), shader=None)
        self.titulo = Text(nombre.upper(), parent=padre, origin=(0, 0), position=(c[0], c[1] + 0.08, c[2] - 0.004),
                           scale=0.75, color=rgb(mat.NEON_CIAN))
        self.estado = Text("", parent=padre, origin=(0, 0), position=(c[0], c[1] - 0.06, c[2] - 0.004), scale=0.6,
                           color=rgb((200, 230, 255)))
        for t in (self.titulo, self.estado):
            texto_sin_tinta(t)
        self.fijar(False)

    def fijar(self, completado):
        self.estado.text = "PRUEBA EXTRAÍDA" if completado else "SIN REVISAR"
        self.estado.color = rgb(mat.NEON_VERDE if completado else (200, 230, 255))


def construir_laboratorio(padre, plano, nombres=None):
    raiz = Entity(parent=padre, name="sala_laboratorio")
    ox, oz = plano.origen
    w, d, h = plano.ancho, plano.fondo, plano.alto
    g = _cuarto(raiz, plano, pared=(84, 96, 122), piso=(58, 64, 80), zocalo=(48, 54, 70), acento=(40, 46, 60),
                sin_sur=True)
    # baldosas (rejilla)
    for k in range(-3, 4):
        _p(g, (70, 78, 96), (ox + k * 1.0, 0.003, oz), (0.02, 0.006, d))
    for k in range(-3, 4):
        _p(g, (70, 78, 96), (ox, 0.003, oz + k * 1.0), (w, 0.006, 0.02))
    sillas, pantallas = {}, {}
    for t in plano.terminales:
        mx, mz, mw, md = t.mesa
        _p(g, (196, 200, 210), (mx, sc.ALTURA_MESA - 0.03, mz), (mw, 0.05, md))
        for dx in (-mw / 2 + 0.06, mw / 2 - 0.06):
            _p(g, METAL, (mx + dx, (sc.ALTURA_MESA - 0.05) / 2, mz), (0.05, sc.ALTURA_MESA - 0.05, md - 0.06))
        c = t.pantalla["centro"]
        _p(g, METAL, (c[0], c[1], c[2] + 0.035), (t.pantalla["ancho"] + 0.06, t.pantalla["alto"] + 0.06, 0.05))
        _p(g, METAL, (c[0], 0.88, c[2] + 0.06), (0.06, 0.22, 0.05))
        _p(g, METAL, (c[0], sc.ALTURA_MESA + 0.01, c[2] + 0.05), (0.3, 0.02, 0.2))
        _p(g, (40, 42, 52), (c[0], sc.ALTURA_MESA + 0.012, mz - 0.18), (0.48, 0.02, 0.16))
        _p(g, (40, 42, 52), (c[0] + 0.38, sc.ALTURA_MESA + 0.014, mz - 0.18), (0.07, 0.025, 0.11))
        # torre del equipo incautado, con precinto rojo
        _p(g, (30, 32, 40), (mx - mw / 2 + 0.25, 0.3, mz + 0.05), (0.22, 0.56, 0.5))
        _p(g, (220, 50, 60), (mx - mw / 2 + 0.25, 0.42, mz - 0.205), (0.23, 0.05, 0.01))
        # franja de neón y rótulo sobre el terminal
        _p(g, (24, 28, 40), (c[0], 2.1, oz + d / 2 - 0.03), (1.5, 0.34, 0.03))
        sillas[t.nivel] = _silla(raiz, t.asiento, suelta=True)
        nombre = (nombres or {}).get(t.nivel, t.nivel)
        pantallas[t.nivel] = PantallaTerminal(raiz, t, nombre)
        _texto(raiz, nombre, (c[0], 2.1, oz + d / 2 - 0.05), 1.3, tono=mat.NEON_CIAN, rotation_y=0)
    # racks de servidores (este) con luces
    for k in range(3):
        _p(g, (28, 30, 38), (ox + w / 2 - 0.4, 0.95, oz - 0.85 + k * 0.85), (0.6, 1.9, 0.8))
        for f in range(6):
            _p(g, (52, 56, 68), (ox + w / 2 - 0.71, 0.4 + f * 0.25, oz - 0.85 + k * 0.85), (0.01, 0.16, 0.72))
    # mesa de pruebas (oeste) con cajas y bolsas de evidencia
    _p(g, METAL_CLARO, (ox - 2.4, sc.ALTURA_MESA - 0.03, oz + 0.2), (1.5, 0.05, 0.8))
    for dx in (-0.68, 0.68):
        _p(g, METAL, (ox - 2.4 + dx, (sc.ALTURA_MESA - 0.05) / 2, oz + 0.2), (0.05, sc.ALTURA_MESA - 0.05, 0.74))
    _p(g, (196, 160, 110), (ox - 2.7, sc.ALTURA_MESA + 0.12, oz + 0.3), (0.4, 0.24, 0.3))
    _p(g, (196, 160, 110), (ox - 2.2, sc.ALTURA_MESA + 0.08, oz + 0.1), (0.3, 0.16, 0.26))
    _p(g, (230, 236, 240), (ox - 2.0, sc.ALTURA_MESA + 0.01, oz + 0.35), (0.22, 0.02, 0.3))
    # puerta (pared oeste) con rótulo
    px, pz = plano.puerta
    _p(g, (30, 30, 38), (px + 0.015, 1.15, pz), (0.03, 2.34, 1.14))
    _p(g, (120, 128, 140), (px + 0.04, 1.1, pz), (0.03, 2.2, 1.0))
    _p(g, (220, 200, 120), (px + 0.08, 1.05, pz + 0.36), (0.08, 0.08, 0.08), modelo="sphere")
    _p(g, (24, 28, 40), (px + 0.04, 2.5, pz), (0.03, 0.26, 1.6))
    g.combine()
    silenciar(g)
    # neón (sin luz): franja a media pared y LEDs de los racks
    neon = Entity(parent=raiz)
    for (x, z, sx, sz) in ((ox, oz + d / 2 - 0.05, w - 0.2, 0.02), (ox - w / 2 + 0.05, oz + 1.0, 0.02, d - 2.6)):
        _p(neon, mat.NEON_CIAN, (x, 2.45, z), (sx, 0.035, sz), shader=None)
    for k in range(3):
        for f in range(6):
            tono = mat.NEON_VERDE if (k + f) % 3 else mat.NEON_MAGENTA
            _p(neon, tono, (ox + w / 2 - 0.72, 0.44 + f * 0.25, oz - 1.1 + k * 0.85), (0.012, 0.025, 0.04),
               shader=None)
    neon.combine()
    silenciar(neon)
    _texto(raiz, "SALA DE INTERROGATORIO", (px + 0.06, 2.5, pz), 1.1, tono=(255, 220, 60), rotation_y=-90)
    silenciar(raiz)
    return raiz, {"sillas": sillas, "pantallas": pantallas}


# ------------------------------------------------------------------------------------------------------------ sala

def construir_sala(padre, plano):
    raiz = Entity(parent=padre, name="sala_interrogatorio")
    ox, oz = plano.origen
    w, d, h = plano.ancho, plano.fondo, plano.alto
    hueco = (oz - 0.1, 2.4, 0.95, 2.15)              # vidrio espejado en la pared oeste
    g = _cuarto(raiz, plano, pared=(150, 160, 172), piso=(92, 96, 108), zocalo=(104, 112, 124),
                acento=(64, 72, 90), hueco_oeste=hueco)
    mx, mz, mw, md, my = plano.mesas[0]
    _p(g, METAL_CLARO, (mx, my - 0.025, mz), (mw, 0.05, md))
    for dx in (-mw / 2 + 0.05, mw / 2 - 0.05):
        for dz in (-md / 2 + 0.05, md / 2 - 0.05):
            _p(g, METAL, (mx + dx, (my - 0.05) / 2, mz + dz), (0.05, my - 0.05, 0.05))
    _p(g, (120, 126, 136), (mx + 0.45, my + 0.012, mz + 0.18), (0.08, 0.02, 0.04))      # argolla
    _p(g, (244, 240, 228), (mx - 0.3, my + 0.006, mz - 0.12), (0.22, 0.01, 0.3), rotation_y=6)
    _p(g, (30, 30, 36), (mx + 0.2, my + 0.02, mz - 0.2), (0.14, 0.04, 0.08))          # grabadora
    a_h, a_j = plano.asientos["hablante"], plano.asientos["jugador"]
    _silla_metalica(raiz, a_h)
    silla_jugador = _silla_metalica(raiz, a_j, suelta=True)
    # marco del vidrio y sala de observación detrás (oscura)
    zc, ancho, y0, y1 = hueco
    x_o = ox - w / 2
    for (y, sy) in ((y0 - 0.03, 0.06), (y1 + 0.03, 0.06)):
        _p(g, METAL, (x_o + 0.02, y, zc), (0.08, sy, ancho + 0.12))
    for z in (zc - ancho / 2 - 0.03, zc + ancho / 2 + 0.03):
        _p(g, METAL, (x_o + 0.02, (y0 + y1) / 2, z), (0.08, y1 - y0 + 0.12, 0.06))
    _p(g, (34, 36, 46), (x_o - 1.5, -0.05, zc), (2.9, 0.1, 3.0))
    _p(g, (34, 36, 46), (x_o - 3.0, h / 2, zc), (0.1, h, 3.0))
    _p(g, (34, 36, 46), (x_o - 1.5, h / 2, zc - 1.5), (2.9, h, 0.1))
    _p(g, (34, 36, 46), (x_o - 1.5, h / 2, zc + 1.5), (2.9, h, 0.1))
    _p(g, (24, 26, 34), (x_o - 1.0, 0.9, zc), (0.6, 0.05, 1.6))                        # pupitre de observación
    # puerta metálica (este), cámara en la esquina, reloj
    px, pz = plano.puerta
    _p(g, (30, 30, 38), (px - 0.015, 1.1, pz), (0.03, 2.2, 1.04))
    _p(g, (96, 104, 116), (px - 0.04, 1.05, pz), (0.03, 2.1, 0.94))
    _p(g, (40, 44, 52), (px - 0.07, 1.6, pz), (0.02, 0.3, 0.4))
    _p(g, (40, 42, 50), (ox + w / 2 - 0.2, h - 0.25, oz + d / 2 - 0.2), (0.22, 0.14, 0.3))
    _p(g, BLANCO, (ox, 2.3, oz + d / 2 - 0.03), (0.4, 0.4, 0.03), modelo="circle", rotation_y=180)
    _p(g, (30, 30, 40), (ox, 2.34, oz + d / 2 - 0.05), (0.02, 0.16, 0.01))
    _p(g, (30, 30, 40), (ox + 0.05, 2.3, oz + d / 2 - 0.05), (0.12, 0.02, 0.01))
    g.combine()
    lampara = Entity(parent=raiz, shader=lit_with_shadows_shader)
    _lampara_colgante(lampara, mx, mz, h, 0.8)
    lampara.combine()
    lampara.hide(MASCARA_LUZ)            # sin sombra: su franja vertical cruzaba la pared del fondo
    silenciar(lampara)
    silenciar(g)
    _bombilla(raiz, mx, h - 0.92, mz, escala=0.16)
    _p(raiz, (220, 40, 40), (ox + w / 2 - 0.2, h - 0.25, oz + d / 2 - 0.36), (0.03, 0.03, 0.03), modelo="sphere",
       shader=None)
    # vidrio espejado: oscuro, algo translúcido (se intuye al fiscal detrás) y con reflejos en diagonal
    vidrio = Entity(parent=raiz, model="quad", position=(x_o + 0.03, (y0 + y1) / 2, zc), rotation_y=-90,
                    scale=(ancho, y1 - y0), color=color.rgba32(30, 40, 58, 205), shader=None)
    vidrio.setTransparency(True)
    vidrio.setDepthWrite(False)
    for k, (dz, ancho_r) in enumerate(((-0.6, 0.18), (-0.35, 0.06), (0.55, 0.12))):
        r = Entity(parent=raiz, model="quad", position=(x_o + 0.035, (y0 + y1) / 2, zc + dz), rotation=(0, -90, 32),
                   scale=(ancho_r, (y1 - y0) * 1.1), color=color.rgba32(200, 220, 240, 34), shader=None)
        r.setTransparency(True)
        r.setDepthWrite(False)
    silenciar(raiz)
    return raiz, {"silla_jugador": silla_jugador, "vidrio": vidrio}


def construir(padre, planos, nombre_fiscal="Fiscal Rojas", nombres_terminal=None):
    """{escena: (raiz, extras)} de las tres salas (desactivadas)."""
    salas = {
        sc.OFICINA: construir_oficina(padre, planos[sc.OFICINA], nombre_fiscal),
        sc.LABORATORIO: construir_laboratorio(padre, planos[sc.LABORATORIO], nombres_terminal),
        sc.SALA: construir_sala(padre, planos[sc.SALA]),
    }
    for raiz, _ in salas.values():
        _bias_de_sombra(raiz)
        raiz.enabled = False
    return salas


# Acné de sombra: con la luz ajustada a una sala pequeña (luz.update_bounds), el shadow_bias global de piezas.py
# (-0,0008, pensado para la ciudad) se queda corto y los planos casi paralelos a la luz se rayaban (respaldo de la silla
# del jugador, zócalos). Medido en ventana: -0,003 limpia; -0,008 ya raya las paredes.
SHADOW_BIAS_SALAS = -0.003


def _bias_de_sombra(raiz):
    for e in [raiz] + list(raiz.get_descendants()):
        if getattr(getattr(e, "shader", None), "name", "") == lit_with_shadows_shader.name:
            e.set_shader_input("shadow_bias", SHADOW_BIAS_SALAS)


def angulo(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))

# Firma «la fuente» (M4), la vista: la fuente de la Praça da Sé muestra la salud de la ciudad. Lo que se ve lo decide
# frontend/fuente_firma_calculos.py (puro, con pruebas); este módulo solo lo dibuja. Lo instala
# frontend/registro_fuente_firma.py (por frontend/extensiones.py) y cuelga de la EscenaMundo: solo corre con el mundo a la vista.
#
# Con la bandera encendida, props_mundo.fuente deja en la malla única del decorado SOLO la piedra; aquí van, como entidades
# pequeñas aparte (sin reconstruir la ciudad):
#   agua de la pila   (con luz, como antes)  se vacía bajando su altura y su opacidad
#   agua de la taza   (con luz)              un disco sobre la taza que encoge al secarse, con las gotas
#   chorro            (sin luz)              cono de alto variable desde la taza
#   corona            (sin luz)              la espuma de arriba del chorro, sigue su altura
#   flores            (sin luz)              un anillo de matas con flores sobre el borde, brota hacia arriba (florece)
#   basura            (sin luz)              bolsas, papeles, una caja y una lata en la pila seca (apagado)
#   cartel            (sin luz)              el cartelito torcido de «sin conexión» de ciudad_viva, pequeño (apagado)
# Lo apagado (fundido 0) queda con enabled = False: no cuesta llamadas de dibujo. Se actualiza cada ~0,1 s y solo toca las
# entidades si el estado cambió (en reposo: cero trabajo).

import math
import sys

from frontend import ambiente_vivo
from frontend import fuente_firma_calculos as ffc
from frontend.azar_fijo import azar_de
from frontend.props_mundo import PLAZA_DE_LA_FUENTE, Malla, caja, icosfera, prisma

BLANCO = (255, 255, 255)
TINTE_OBJETOS = 0.88             # como ciudad_viva: lo que va sin luz se baja un poco para casar con la ciudad
ESCALA_CARTEL = 0.55
VERDE_MATA = (58, 128, 56)
FLORES = ((222, 64, 64), (248, 206, 56), (240, 240, 232), (214, 70, 160), (250, 140, 60), (150, 112, 204))


def _aviso(texto):
    print(f"[fuente_firma] {texto}", file=sys.stderr)


def pie_de_fuente(mundo):
    """(x, y, z) del pie de la fuente como la pone props_mundo.colocar_props, o None si el mundo no tiene esa plaza."""
    try:
        if PLAZA_DE_LA_FUENTE not in set(mundo.lugares()):
            return None
        x, z = mundo.coordenada(PLAZA_DE_LA_FUENTE)
        return float(x), round(mundo.altura(x, z) + 0.16, 3), float(z)
    except Exception:
        return None


# -- Mallas (origen en el punto que se escala) -------------------------------------------------------------------------


def mesh_pila(s):
    m = Malla()                                   # altura 1: la entidad la escala a 0,46 m (llena) o menos
    m.agregar(prisma(14, 0.5, 0.5), (0, 0, 0), (3.35 * s, 1.0, 3.35 * s), 0, BLANCO, (0.86, 1.0))
    return m.mesh()


def mesh_taza(s):
    m = Malla()
    m.agregar(prisma(14, 0.5, 0.5), (0, 0, 0), (1.62 * s, 0.03 * s, 1.62 * s), 0, BLANCO, (1.0, 1.0))
    for k in range(6):                            # gotas que caen a la taza (las de antes)
        a = k * math.pi / 3
        m.agregar(icosfera(0), (0.5 * s * math.cos(a), (0.16 - 0.1 * (k % 2)) * s, 0.5 * s * math.sin(a)), 0.13 * s, 0,
                  BLANCO, (1.0, 1.0))
    return m.mesh()


def mesh_chorro(s):
    m = Malla()                                   # alto 1: la entidad lo escala al alto del chorro
    m.agregar(prisma(8, 0.5, 0.18), (0, 0, 0), (0.3 * s, 1.0, 0.3 * s), 0, BLANCO, (0.92, 1.0))
    return m.mesh()


def mesh_corona(s):
    m = Malla()
    m.agregar(icosfera(1), (0, 0, 0), (0.46 * s, 0.42 * s, 0.46 * s), 0, BLANCO, (0.95, 1.0))
    for k in range(5):                            # la espuma que se abre arriba
        a = k * 2 * math.pi / 5 + 0.4
        m.agregar(icosfera(0), (0.3 * s * math.cos(a), -0.12 * s, 0.3 * s * math.sin(a)), 0.16 * s, 0, BLANCO, (0.95, 1.0))
    return m.mesh()


def mesh_flores(s, n=12):
    """Anillo de matas con flores sobre el borde de piedra (radio medio 1,84 m); origen en la altura del borde."""
    m = Malla()
    for k in range(n):
        a = 2 * math.pi * k / n + 0.13
        r = 1.84 * s
        x, z = r * math.cos(a), r * math.sin(a)
        m.agregar(icosfera(1), (x, 0.06 * s, z), (0.36 * s, 0.26 * s, 0.32 * s), k * 33, VERDE_MATA, (0.7, 1.1), 0.1)
        for j in range(3):
            b = a + (j - 1) * 0.09
            rr = r + (azar_de(k, j) - 0.5) * 0.14 * s
            m.agregar(icosfera(0), (rr * math.cos(b), (0.26 + 0.08 * azar_de(j, k)) * s, rr * math.sin(b)), 0.15 * s, 0,
                      FLORES[(k + j * 2) % len(FLORES)], (0.95, 1.1))
    return m.mesh()


def mesh_basura(s):
    """Bolsas, papeles, una caja y una lata en el fondo de la pila seca; origen en el fondo (losa de 0,12 m)."""
    m = Malla()
    bolsas = ((0.95, 30, (28, 32, 36)), (1.25, 140, (46, 84, 58)), (1.05, 250, (60, 60, 112)))
    for r, ang, c in bolsas:
        a = math.radians(ang)
        x, z = r * s * math.cos(a), r * s * math.sin(a)
        m.agregar(icosfera(1), (x, 0.14 * s, z), (0.5 * s, 0.4 * s, 0.44 * s), ang, c, (0.7, 1.1), 0.1)
        m.agregar(icosfera(0), (x + 0.04 * s, 0.32 * s, z), (0.16 * s, 0.14 * s, 0.16 * s), 0, tuple(min(255, int(v * 1.25)) for v in c),
                  (0.9, 1.1))
    for k, (r, ang, c) in enumerate(((0.8, 95, (238, 234, 222)), (1.35, 200, (214, 210, 196)), (0.9, 320, (244, 206, 120)),
                                     (1.4, 60, (226, 224, 214)))):
        a = math.radians(ang)
        m.agregar(caja(), (r * s * math.cos(a), 0.01, r * s * math.sin(a)), (0.36 * s, 0.02, 0.26 * s), 40 * k + ang, c, (0.9, 1.05))
    a = math.radians(175)
    m.agregar(caja(), (1.15 * s * math.cos(a), 0.0, 1.15 * s * math.sin(a)), (0.5 * s, 0.34 * s, 0.4 * s), 25, (180, 138, 88),
              (0.8, 1.05), 0.08)
    a = math.radians(290)
    m.agregar(prisma(8, 0.5, 0.42), (1.4 * s * math.cos(a), 0.0, 1.4 * s * math.sin(a)), (0.16 * s, 0.24 * s, 0.16 * s), 0,
              (216, 62, 52), (0.8, 1.1))
    return m.mesh()


# -- Controlador -------------------------------------------------------------------------------------------------------


def crear_controlador(escena):
    from panda3d.core import TransparencyAttrib
    from ursina import Color, Entity, time
    from ursina.shaders import unlit_shader
    from frontend.ciudad_viva import mesh_cartel
    from frontend.piezas import MASCARA_LUZ, pieza

    pie = pie_de_fuente(escena._mundo)
    if pie is None:
        _aviso("el mundo no tiene la Praça da Sé: la fuente queda como está")
        return None
    x0, y0, z0 = pie
    s = 1.0

    class ControladorFuenteFirma(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.ignore = False
            self._t = 0.0
            self.estado = None            # Estado actual (ffc), el que está dibujado
            self.raiz = Entity(parent=self, position=(x0, y0, z0), name="fuente_firma")
            self.raiz.ignore = True

            opaca = ffc.fuente_opaca_activa()          # R3b/c: chorro y corona opacos, agua con profundidad
            self._opaca = opaca

            def parte(nombre, modelo, con_luz, transparente, profundidad=False, **pos):
                e = (pieza(parent=self.raiz, model=modelo, name=f"fuente_{nombre}", **pos) if con_luz else
                     Entity(parent=self.raiz, model=modelo, shader=unlit_shader, unlit=True, name=f"fuente_{nombre}", **pos))
                e.ignore = True
                e.hide(MASCARA_LUZ)       # cambia con el estado: fuera del mapa de sombras
                if transparente:
                    e.setTransparency(TransparencyAttrib.MAlpha)
                    e.setDepthWrite(profundidad)
                return e

            self.pila = parte("pila", mesh_pila(s), True, True, opaca, y=0.04 * s)
            self.taza = parte("taza", mesh_taza(s), True, True, opaca, y=1.395 * s)
            self.chorro = parte("chorro", mesh_chorro(s), False, not opaca, y=1.39 * s)
            self.corona = parte("corona", mesh_corona(s), False, not opaca)
            self.flores = parte("flores", mesh_flores(s), False, False, y=0.66 * s)
            self.basura = parte("basura", mesh_basura(s), False, False, y=0.12 * s)
            a = math.radians(215)
            self.cartel = parte("cartel", mesh_cartel(1), False, False, position=(1.2 * s * math.cos(a), 0.12 * s, 1.2 * s * math.sin(a)),
                                rotation_y=200)     # de frente a quien llega desde el sur de la plaza
            gris = Color(TINTE_OBJETOS, TINTE_OBJETOS, TINTE_OBJETOS, 1.0)
            for e in (self.flores, self.basura, self.cartel):
                e.color = gris
                e.enabled = False
            self.avanzar(10.0)            # arranca ya en el estado del Ambiente, sin transición

        def update(self):
            self._t -= min(time.dt, 0.25)
            if self._t <= 0:
                dt = ffc.PERIODO - self._t
                self._t = ffc.PERIODO
                self.avanzar(dt)

        def avanzar(self, dt):
            amb = ambiente_vivo.obtener()
            meta = ffc.objetivo(getattr(amb, "salud", 0.5), getattr(amb, "nivel", None))
            nuevo = ffc.avanzar(self.estado, meta, dt)
            if self.estado is not None and ffc.iguales(nuevo, self.estado):
                return
            self.estado = nuevo
            self._dibujar(nuevo)

        def _dibujar(self, e):
            r, g, b = (c / 255 for c in e.color)
            agua = max(0.0, min(1.0, e.agua))
            con_agua = agua > 0.0
            for ent in (self.pila, self.taza):
                ent.enabled = con_agua
            if con_agua:
                self.pila.color = Color(r, g, b, e.alfa * min(1.0, 0.25 + agua))
                self.pila.scale_y = max(0.001, 0.46 * s * agua)
                self.taza.color = Color(r, g, b, e.alfa)
                ancho = max(0.001, math.sqrt(agua))
                self.taza.scale = (ancho, max(0.001, agua), ancho)
            alto = ffc.alto_visible_chorro(e) * s
            hay_chorro = alto > 0.02
            self.chorro.enabled = self.corona.enabled = hay_chorro
            if hay_chorro:
                c_chorro, c_corona = ffc.colores_chorro(e.color, e.alfa, self._opaca)
                self.chorro.color = Color(*c_chorro)
                self.chorro.scale_y = alto
                self.corona.y = 1.39 * s + alto
                k = min(1.0, alto / (0.8 * s))
                self.corona.scale = max(0.001, 0.55 + 0.45 * k)
                self.corona.color = Color(*c_corona)
            for ent, f, uniforme in ((self.flores, e.flores, False), (self.basura, e.basura, False),
                                     (self.cartel, e.cartel, True)):
                es = ffc.escala_extra(f)
                ent.enabled = es > 0.0
                if es > 0.0:
                    ent.scale = ESCALA_CARTEL * s * es if uniforme else (1.0, max(0.001, es), 1.0)

        def estadisticas(self):
            return {"estado": self.estado, "visibles": [e.name for e in self.raiz.children if e.enabled]}

    return ControladorFuenteFirma(parent=escena)

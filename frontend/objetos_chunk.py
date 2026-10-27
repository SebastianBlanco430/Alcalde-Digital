# Todo lo que no es terreno ni casa de un chunk del mapa grande, en mallas con color por vértice:
# árboles y arbustos de baja poligonización (arboles_lowpoly), palmeras, farolas, bancos, bases de las casas (zócalo o
# pilotes), tanques de agua, antenas, ropa tendida, escaleras con peldaños, muros de contención y el detalle de la favela
# (murales, objetos de la calle, balcones, pasadizos, banderines, cancha y mercadito).
#
# Es el mismo contenido que Ciudad3D arma con cientos de Entity (y combine()), pero escrito directo en CINCO acumuladores
# (ObjetosChunk): lit (con luz), pintura (murales, no proyecta sombra), manchas (translúcidas, sin luz), banderines (sin luz,
# doble cara) y luces (focos, sin sombreado), más los segmentos de los cables. Cada pieza pertenece al chunk donde está su
# centro (no se repite en el vecino) aunque dibuje fuera de él. Generador: cede el control entre pieza y pieza.
#
# Qué NO se dibuja en el mapa grande (documentado en la bóveda, nota «F5»): los carteles con LETRAS de las fachadas (un Text
# por cartel: su base pintada sí sale) y los contornos de tinta de los árboles de parque. Las antenas no inclinan el plato.

import math

from frontend import favela_calculos as fc
from frontend import favela_detalles as fd
from frontend.arboles_lowpoly import arbol_bajo, arbusto_bajo
from frontend.azar_fijo import azar_de
from frontend.detalles_calculos import (ALTO_PRENDA, esquina_del_tanque, indices_con_antena, posicion_antena,
                                        prendas, tendederos, vertices_cuerda)
from frontend.geom_directa import Acumulador, icosfera_suave, prisma_suave
from frontend.geometria_mundo import ENTIERRO_BASE, medidas_losa, medidas_zocalo
from frontend.props_mundo import Malla, caja, icosfera

from backend.logica import escaleras_calculos

# Constantes de ciudad_3d que se repiten (no se importa ciudad_3d aquí para poder probar sin ventana).
COLOR_ZOCALO = (150, 146, 138)
DESNIVEL_MINIMO_BASE = 0.05
DESNIVEL_MAXIMO_ZOCALO = 1.5
LADO_PILOTE = 0.3
RETRANQUEO_PILOTE = 0.2
PILOTE_MINIMO = 0.1
COLOR_TANQUE = (40, 96, 190)
PROPORCION_TANQUES = 0.45
COLOR_BARANDA = (60, 62, 70)
PALETAS_ESCALERA = (((250, 200, 60), (70, 190, 200)), ((240, 110, 150), (250, 240, 220)), ((120, 200, 90), (250, 160, 60)),
                    ((90, 140, 240), (250, 230, 110)), ((200, 110, 220), (250, 240, 220)))
PALETA_MUROS = ((236, 170, 90), (230, 120, 150), (92, 192, 190), (240, 220, 160), (150, 200, 100), (120, 150, 230))
GROSOR_MURO, GROSOR_TAPA, SOBRESALE_TAPA, ACLARAR_TAPA = 0.35, 0.08, 0.1, 14
ALTURA_CABLE = 4.0
DISTANCIA_CABLE = 20.0
DISTANCIA_CABLE_CASA = 15.0
ALTURA_CABLE_CASA_MAX = 9.0
CABLES_POR_TRAMO = 3
PROPORCION_CABLE_CASA = 0.8
COLOR_ANTENA = (205, 205, 210)
MASTIL = (0.05, 0.6, 0.05)
PLATO = (0.7, 0.16, 0.7)
PRENDA = (0.35, ALTO_PRENDA, 0.03)
HALO_DETALLES = 8.0               # m de casas vecinas que hacen falta para decidir paredes de callejón, ropa y banderines

_PLANTILLAS = {}


def _plantilla(nombre, fabrica):
    p = _PLANTILLAS.get(nombre)
    if p is None:
        p = _PLANTILLAS[nombre] = fabrica()
    return p


class ObjetosChunk:
    """Los acumuladores de un chunk y los vértices de sus cables (pares de puntos)."""

    def __init__(self):
        self.lit = Acumulador()
        self.pintura = Acumulador()
        self.manchas = Acumulador()
        self.banderines = Acumulador()
        self.luces = Acumulador()
        self.cables = []

    def vertices(self):
        return sum(len(a) for a in (self.lit, self.pintura, self.manchas, self.banderines, self.luces)) + len(self.cables)


class ContextoObjetos:
    """Datos del mundo que los chunks comparten: perfil e índice de cada escalera."""

    def __init__(self, mundo):
        self.mundo = mundo
        self.perfil_de = {}
        for k, perfil in enumerate(mundo.perfiles_escaleras()):
            self.perfil_de[perfil.escalera] = (k, perfil)


def _en_chunk(mundo, clave, x, z):
    return mundo.chunk_de(x, z) == clave


class FachadaVista:
    """Lo que franjas_prohibidas y favela_detalles piden a un mundo, servido por un VistaChunk (duck typing)."""

    def __init__(self, vista):
        self._v = vista
        self.mundo = vista.mundo
        self.ancho_calle = vista.mundo.ancho_calle
        self.altura = vista.mundo.altura

    def segmentos(self):
        return [(a, b) for a, b, _, _ in self._v.segmentos]

    def coordenada(self, lugar):
        return self.mundo.coordenada(lugar)

    def edificios(self):
        return self._v.edificios

    def escaleras(self):
        return self._v.escaleras

    def obstaculos(self):
        return self._v.obstaculos

    def zonas(self):
        return self._v.zonas


# -- Piezas sueltas ---------------------------------------------------------------------------------------------------


def base_de_casa(acum, c, bajo, alto):
    """Zócalo macizo o losa sobre pilotes bajo la planta baja (ciudad_3d._base_de_casa)."""
    desnivel = alto - bajo
    if desnivel <= DESNIVEL_MINIMO_BASE:
        return
    if desnivel <= DESNIVEL_MAXIMO_ZOCALO:
        pie, tope, holgura = medidas_zocalo(bajo, alto, c.hondo_umbral)
        acum.caja(c.cx, (pie + tope) / 2, c.cz, c.ancho + holgura, tope - pie, c.fondo + holgura, 0.0, COLOR_ZOCALO)
        return
    pie, tope, holgura = medidas_losa(alto, c.hondo_umbral)
    acum.caja(c.cx, (pie + tope) / 2, c.cz, c.ancho + holgura, tope - pie, c.fondo + holgura, 0.0, COLOR_ZOCALO)


def pilotes_de_casa(acum, c, bajo, alto, suelo):
    if alto - bajo <= DESNIVEL_MAXIMO_ZOCALO:
        return
    pie, _, _ = medidas_losa(alto, c.hondo_umbral)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = c.cx + sx * (c.ancho / 2 - RETRANQUEO_PILOTE)
            z = c.cz + sz * (c.fondo / 2 - RETRANQUEO_PILOTE)
            base = suelo(x, z) - ENTIERRO_BASE
            if pie - base < PILOTE_MINIMO:
                continue
            acum.caja(x, (base + pie) / 2, z, LADO_PILOTE, pie - base, LADO_PILOTE, 0.0, COLOR_ZOCALO)


def tanque_de_agua(acum, casa, y_planta):
    if azar_de(casa.cx, casa.cz) >= PROPORCION_TANQUES:
        return
    techo = y_planta + casa.alto_total
    esquina = esquina_del_tanque(casa)
    x, z = casa.cx + esquina * casa.ancho / 4, casa.cz + casa.fondo / 4
    cil = _plantilla("cil12", lambda: prisma_suave(12, 0.5, 0.5))
    acum.solido(cil, (x, techo - 0.15, z), (1.1, 1.0, 1.1), 0.0, COLOR_TANQUE, (0.9, 1.0))
    acum.caja(x, techo + 0.9, z, 0.9, 0.08, 0.9, 0.0, tuple(c + 30 for c in COLOR_TANQUE))


def antenas(malla, casas, altos):
    for i in indices_con_antena(casas):
        casa = casas[i]
        x, z = posicion_antena(casa)
        techo = altos[i] + casa.alto_total
        giro = int(azar_de(casa.cx * 3.1, casa.cz * 1.7) * 4) * 90
        malla.agregar(caja(), (x, techo + MASTIL[1] / 2, z), MASTIL, 0, COLOR_ANTENA, (0.8, 1.0))
        malla.agregar(icosfera(0), (x, techo + MASTIL[1] + 0.05, z), PLATO, giro, COLOR_ANTENA, (0.8, 1.05), inclinacion=35)


def farola(obj, o, suelo):
    y = suelo(o.cx, o.cz) - 0.1
    obj.lit.caja(o.cx, y + 2.1, o.cz, 0.14, 4.2, 0.14, 0.0, (70, 72, 82))
    obj.luces.solido(_plantilla("foco", lambda: icosfera_suave(0)), (o.cx, y + 4.35, o.cz), 0.5, 0.0, (255, 238, 170), (1.0, 1.0))


def banco(acum, o, suelo, y_plaza=0.14):
    madera, hierro = (140, 96, 60), (60, 62, 72)
    y = suelo(o.cx, o.cz) + y_plaza
    acum.caja(o.cx, y + 0.46, o.cz, o.ancho, 0.1, o.fondo, 0.0, madera)
    acum.caja(o.cx, y + 0.82, o.cz + o.fondo / 2 - 0.04, o.ancho, 0.5, 0.08, 0.0, madera)
    for dx in (-o.ancho / 2 + 0.15, o.ancho / 2 - 0.15):
        acum.caja(o.cx + dx, y + 0.22, o.cz, 0.1, 0.44, o.fondo - 0.1, 0.0, hierro)


def escalera_con_peldanos(obj, ctx, escalera):
    """Peldaños y baranda de una escalera (ciudad_3d._construir_escaleras_peldanos)."""
    k, perfil = ctx.perfil_de[escalera]
    suelo = ctx.mundo.altura
    e = perfil.escalera
    ux, uz = (e.bx - e.ax) / e.largo, (e.bz - e.az) / e.largo
    rumbo = math.degrees(math.atan2(ux, uz))
    par = PALETAS_ESCALERA[k % len(PALETAS_ESCALERA)]
    for n, (s0, s1, altura) in enumerate(perfil.tramos):
        if s1 - s0 < 1e-3:
            continue
        s = (s0 + s1) / 2
        x, z = e.ax + ux * s, e.az + uz * s
        tapa = altura + escaleras_calculos.TAPA_SOBRE_SUELO
        muestras = max(2, int((s1 - s0) / 0.5) + 1)
        fondo = min(suelo(e.ax + ux * (s0 + (s1 - s0) * i / (muestras - 1)), e.az + uz * (s0 + (s1 - s0) * i / (muestras - 1)))
                    for i in range(muestras)) - 0.3
        fondo = min(fondo, tapa - 0.15)
        obj.lit.caja(x, (tapa + fondo) / 2, z, e.ancho, tapa - fondo, (s1 - s0) + 0.02, rumbo, par[n % 2])
    dx, dz = uz * (e.ancho / 2 - 0.05), -ux * (e.ancho / 2 - 0.05)
    postes = max(2, math.ceil(e.largo / 2) + 1)
    puntos = []
    m = Malla()
    for n in range(postes):
        s = e.largo * n / (postes - 1)
        x, z = e.ax + ux * s + dx, e.az + uz * s + dz
        y = perfil.altura_en_s(s) + escaleras_calculos.TAPA_SOBRE_SUELO
        puntos.append((x, y + 0.9, z))
        obj.lit.caja(x, y + 0.45, z, 0.06, 0.9, 0.06, 0.0, COLOR_BARANDA)
    for p, q in zip(puntos, puntos[1:]):
        horizontal = math.dist((p[0], p[2]), (q[0], q[2]))
        m.agregar(caja(), tuple((p[i] + q[i]) / 2 for i in range(3)), (0.05, 0.05, math.hypot(horizontal, q[1] - p[1])),
                  rumbo, COLOR_BARANDA, (0.9, 1.0), inclinacion=-math.degrees(math.atan2(q[1] - p[1], horizontal)))
    obj.lit.malla(m)


def muro(acum, m):
    tono = PALETA_MUROS[int(azar_de(m.cx * 0.37, m.cz * 0.61) * len(PALETA_MUROS)) % len(PALETA_MUROS)]
    alto = m.y_tope - m.y_base
    acum.caja(m.cx, (m.y_base + m.y_tope) / 2, m.cz, GROSOR_MURO, alto, m.largo, m.rumbo, tono)
    acum.caja(m.cx, m.y_tope + GROSOR_TAPA / 2, m.cz, GROSOR_MURO + SOBRESALE_TAPA, GROSOR_TAPA, m.largo, m.rumbo,
              tuple(min(255, c + ACLARAR_TAPA) for c in tono))


def cables_de(farolas, casas, altos, suelo):
    """Vértices (pares) de los cables de luz: farola a farola y farola al techo de la casa más cercana."""
    def punta(o):
        return (o.cx, suelo(o.cx, o.cz) - 0.1 + ALTURA_CABLE, o.cz)

    tramos = []
    for f, g in zip(farolas, farolas[1:]):
        if math.dist((f.cx, f.cz), (g.cx, g.cz)) <= DISTANCIA_CABLE:
            tramos.append((punta(f), punta(g)))
    for f in farolas:
        cerca = [(c, y) for c, y in zip(casas, altos) if math.dist((f.cx, f.cz), (c.cx, c.cz)) <= DISTANCIA_CABLE_CASA]
        if cerca:
            c, y = min(cerca, key=lambda cy: math.dist((f.cx, f.cz), (cy[0].cx, cy[0].cz)))
            tramos.append((punta(f), (c.cx, y + min(c.alto_total * PROPORCION_CABLE_CASA, ALTURA_CABLE_CASA_MAX), c.cz)))
    vertices = []
    for p, q in tramos:
        for k in range(CABLES_POR_TRAMO):
            caida = (0.25 + 0.04 * math.dist(p, q)) * (1 + 0.3 * k)
            desvio = 0.14 * k * (1 if k % 2 else -1)
            a = (p[0] + desvio, p[1] - 0.12 * k, p[2] - desvio)
            b = (q[0] - desvio, q[1] - 0.1 * k, q[2] + desvio)
            puntos = [tuple(a[i] + (b[i] - a[i]) * j / 10 for i in range(3)) for j in range(11)]
            puntos = [(x, y - caida * 4 * (j / 10) * (1 - j / 10), z) for j, (x, y, z) in enumerate(puntos)]
            for u, v in zip(puntos, puntos[1:]):
                vertices += [u, v]
    return vertices


# -- Detalle de la favela (favela_detalles.construir_favela_detalles, restringido a un chunk) ---------------------------


def detalles_favela(obj, vista, casas, bases, propias, clave):
    """Generador: murales, objetos del piso, balcones, pasadizos, banderines, palmeras y zonas del chunk. `casas`/`bases` =
    las del chunk con halo; `propias` = índices (en `casas`) de las que son del chunk. Los carteles con letras no se dibujan."""
    mundo = vista.mundo
    objetos, pintura, tinta = Malla(), Malla(), Malla()
    cuerdas = []
    if casas:
        caras = fc.caras_de_casas(casas)
        yield
        n = 0
        calcos = fc.calcomanias(casas, caras)
        yield
        for cal in calcos:
            if cal.casa not in propias:
                continue
            fd.dibujar_calcomania(objetos if cal.tipo == "balcon" else pintura, tinta, cal, bases[cal.casa])
            n += 1
            if n % 8 == 0:
                yield
        yield
        redondos = [o for o in vista.obstaculos if o.es_circulo]
        n = 0
        en_calle = fc.objetos_de_calle(casas, caras)
        yield
        for o in en_calle:
            if o.casa not in propias:
                continue
            if any(math.hypot(o.x - r.cx, o.z - r.cz) < r.radio + 0.9 for r in redondos):
                continue
            fd.dibujar_objeto(objetos, o, mundo.altura)
            n += 1
            if n % 4 == 0:
                yield
        yield
        cuerdas = [c for c in fc.banderines_de_callejones(casas, caras, bases)
                   if _en_chunk(mundo, clave, (c.a[0] + c.b[0]) / 2, (c.a[2] + c.b[2]) / 2)]
        for p in fc.pasadizos_de_callejones(casas, caras, bases):
            if _en_chunk(mundo, clave, p.cx, p.cz):
                fd.pasadizo(objetos, p)
        yield
    n = 0
    for o in vista.obstaculos:
        if o.tipo not in ("palmera", "bananero") or not _en_chunk(mundo, clave, o.cx, o.cz):
            continue
        y = mundo.altura(o.cx, o.cz) - 0.1
        s = (1.0 + 0.25 * azar_de(o.cx, o.cz)) if o.tipo == "palmera" else (1.0 + 0.2 * azar_de(o.cx, o.cz))
        v = int(azar_de(o.cz, o.cx) * 3)
        (fd.palmera if o.tipo == "palmera" else fd.bananero)(objetos, o.cx, y, o.cz, s, v)
        n += 1
        if n % 4 == 0:
            yield
    for zona in vista.zonas:
        if not _en_chunk(mundo, clave, zona.cx, zona.cz):
            continue
        h = mundo.altura(zona.cx, zona.cz)
        if zona.tipo == "cancha":
            fd.cancha(objetos, zona, h)
        elif zona.tipo == "mercado":
            fd.mercadito(objetos, zona, h)
        elif zona.tipo == "puesto_talco":
            fd.puesto_talco(objetos, zona, h, fd.rumbo_secreto(zona, mundo))
        elif zona.tipo == "armeria_juguete":
            fd.armeria_juguete(objetos, zona, h, fd.rumbo_secreto(zona, mundo))
        yield
    obj.lit.malla(objetos)
    obj.pintura.malla(pintura)
    obj.manchas.malla(tinta)
    if cuerdas:
        bv, bt, bc = fd.datos_banderines(cuerdas)
        i0 = len(obj.banderines)
        obj.banderines.vertices.extend(bv)
        obj.banderines.normales.extend([(0.0, 1.0, 0.0)] * len(bv))
        obj.banderines.colores.extend(bc)
        obj.banderines.triangulos.extend((a + i0, b + i0, c + i0) for a, b, c in bt)


# -- Construcción de un chunk --------------------------------------------------------------------------------------------


def construir_objetos(ctx, vista_halo, clave, casas_h, bases_h, propias, lejano=False):
    """Generador: llena y devuelve un ObjetosChunk con todo lo del chunk `clave`. `vista_halo` = VistaChunk con halo >=
    HALO_DETALLES; `casas_h`/`bases_h` = casas del halo y la y de su planta baja; `propias` = índices de las del chunk."""
    mundo = ctx.mundo
    suelo = mundo.altura
    obj = ObjetosChunk()
    apoyos_propios = [(i, casas_h[i], bases_h[i]) for i in sorted(propias)]
    # -- casas: bases, tanques --
    for i, c, (bajo, alto) in ((i, c, ab) for i, c, ab in apoyos_propios):
        base_de_casa(obj.lit, c, bajo, alto)
        pilotes_de_casa(obj.lit, c, bajo, alto, suelo)
        tanque_de_agua(obj.lit, c, alto)
        if i % 4 == 3:
            yield
    yield
    # -- vegetación y mobiliario del backend --
    for o in vista_halo.obstaculos:
        if not _en_chunk(mundo, clave, o.cx, o.cz):
            continue
        if o.tipo == "arbol":
            arbol_bajo(obj.lit, o.cx, suelo(o.cx, o.cz), o.cz)
        elif o.tipo == "arbusto":
            arbusto_bajo(obj.lit, o.cx, suelo(o.cx, o.cz), o.cz)
        elif o.tipo == "farola":
            farola(obj, o, suelo)
        elif o.tipo == "banco":
            banco(obj.lit, o, suelo)
    yield
    # -- escaleras (cada una en el chunk de su punto medio) y muros --
    for e in vista_halo.escaleras:
        if _en_chunk(mundo, clave, (e.ax + e.bx) / 2, (e.az + e.bz) / 2) and e in ctx.perfil_de:
            escalera_con_peldanos(obj, ctx, e)
            yield
    muros = vista_halo.muros                 # se calculan al primer acceso (~7 ms): paso aparte
    yield
    for m in muros:
        if _en_chunk(mundo, clave, m.cx, m.cz):
            muro(obj.lit, m)
    yield
    # -- cables, antenas, ropa --
    farolas = [o for o in vista_halo.obstaculos if o.tipo == "farola" and _en_chunk(mundo, clave, o.cx, o.cz)]
    obj.cables = cables_de(farolas, casas_h, [a for _, a in bases_h], suelo)
    m = Malla()
    antenas_h = [c for i, c in enumerate(casas_h) if i in propias]
    antenas(m, antenas_h, [bases_h[i][1] for i in sorted(propias)])
    obj.lit.malla(m)
    yield
    if not lejano:
        fachada = FachadaVista(vista_halo)
        from frontend.detalles_calculos import franjas_prohibidas
        apoyos = list(bases_h)
        for t in tendederos(casas_h, apoyos, prohibidos=franjas_prohibidas(fachada), suelo=suelo):
            if not _en_chunk(mundo, clave, (t.ax + t.bx) / 2, (t.az + t.bz) / 2):
                continue
            obj.cables += vertices_cuerda(t)
            mm = Malla()
            for prenda in prendas(t):
                mm.agregar(caja(), (prenda.x, prenda.y, prenda.z), PRENDA, prenda.rumbo, prenda.color, (0.9, 1.0))
            obj.lit.malla(mm)
        yield
        yield from detalles_favela(obj, vista_halo, casas_h, [a for _, a in bases_h], propias, clave)
        yield
    return obj

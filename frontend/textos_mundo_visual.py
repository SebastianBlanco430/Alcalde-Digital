# M1.3 (D7) Vista: prioridad entre textos flotantes del mundo (globo de NPC > cartel de puerta > cartel de puesto).
# UN solo controlador (Entity) para todos los textos: los carteles están silenciados (sin update propio).
#
#   - Cada PERIODO_SOLAPES s proyecta a pantalla los textos a menos de RADIO m y delante de la cámara, y decide quién
#     se oculta (frontend/textos_mundo_calculos.py: rectángulos, prioridad y reglas de empate / cadena).
#   - Cada frame solo avanza el fundido (0.15 s) de los carteles que están cambiando: setAlphaScale en el nodo (el
#     título y su glosa juntos); a alfa 0 el nodo se esconde (hide) para no dibujarlo.
#   - Los globos NUNCA se tocan (GlobosNPC ya maneja su opacidad); solo se leen.
#
# M1.4 (D9, letreros ilegibles): cada cartel (no los globos) cuyo tamaño de letra en pantalla (em de la fuente x escala,
# a la profundidad de su centro, penalizado si se ve de lado) baja de ALTO_OCULTAR_PX se funde igual y vuelve por encima
# de ALTO_MOSTRAR_PX (histéresis); entre ALTO_OCULTAR_PX y ALTO_PLENO_PX su opacidad sigue al tamaño (M5, retoques). Carteles: de puerta (+ glosa), de puesto, pintados de la favela y secretos.
# Hay ~280 carteles (los pintados de la favela son la mayoría): se repasan por tandas, VUELTA_FRAMES frames por vuelta
# completa (~0.1 s), así ningún frame paga la lista entera. La misma tanda apunta qué carteles están cerca (`_v_cerca`):
# los solapes (cada PERIODO_SOLAPES s) solo miran globos + carteles cercanos y legibles. Solo se funden las letras: el
# tablero de los carteles de puerta es otra pieza (fundida con la puerta) y queda.
# Banderas independientes: prioridad (ALCALDE_TEXTOS_PRIORIDAD) y minimo (ALCALDE_LETREROS_MINIMO).
#
# Fuentes: `fuentes()` (lo da frontend/registro_textos_mundo.py) devuelve [(clave, prioridad, nodos, es_globo)]. Los
# de prioridad PRIORIDAD_PUESTO se tratan como fijos (no se mueven nunca: su centro y esquinas se guardan en el mundo).

import time as _reloj

from panda3d.core import Point2, Point3, TransparencyAttrib, Vec3
from ursina import Entity, application, time, window

from frontend import textos_mundo_calculos as tm

PERIODO_FUENTES = 10            # pasadas de solapes entre dos relecturas de la lista de textos (carteles nuevos)
ALFA_GLOBO_MIN = 0.05           # un globo más transparente que esto no tapa a nadie
VUELTA_FRAMES = 6               # frames para repasar todos los carteles (legibilidad y cercanía)
HOLGURA_CERCA = 3.0             # m más allá de RADIO que aún cuentan como «cerca» (la tanda va con retraso)


class PrioridadTextos(Entity):

    def __init__(self, fuentes, activo=lambda: True, prioridad=True, minimo=True, **opciones):
        super().__init__(**opciones)
        self._fuentes = fuentes
        self._activo = activo
        self.prioridad = prioridad      # M1.3: ALCALDE_TEXTOS_PRIORIDAD
        self.minimo = minimo            # M1.4: ALCALDE_LETREROS_MINIMO
        self._lista = []                # [(clave, prioridad, nodos, es_globo)]
        self._carteles = []             # los de _lista que no son globos
        self._globos = []
        self._info = {}                 # clave -> (prioridad, nodos, es_globo)
        self._n = 0
        self._t = tm.PERIODO_SOLAPES
        self._cursor = 0
        self._legible = {}              # clave -> ¿legible? (con histéresis)
        self._alfa_tamano = {}          # clave -> opacidad por tamaño en pantalla (M5: 0 a ALTO_OCULTAR_PX, 1 desde ALTO_PLENO_PX)
        self._v_centros, self._v_altos, self._v_legibles, self._v_cerca = [], [], [], []   # paralelos a _carteles
        self._v_normales, self._v_altos_px = [], []
        self._normales = {}             # clave -> normal unitaria del cartel en el mundo
        self._ocultos_solape = set()
        self._altos = {}                # clave -> alto de las letras del título en el mundo (m)
        self._centros = {}              # clave -> (x, y, z) del centro del cartel en el mundo
        self._nodos = {}                # clave -> nodos de los carteles alguna vez fundidos
        self._alfa = {}                 # clave -> alfa actual (falta = 1, intacto)
        self._objetivo = {}             # clave -> 0.0 / 1.0
        self._fundiendo = set()
        self._esquinas = {}             # clave -> esquinas del cartel (locales, o en el mundo si es fijo)
        self._medidas_globo = {}        # clave -> (texto, (dx, dy, ax, ay)) en unidades locales del globo
        self.ms_total = 0.0
        self.ms_max = 0.0
        self.frames = 0
        self.ocultos = set()

    # -- Frame --

    def update(self):
        t0 = _reloj.perf_counter()
        dt = min(time.dt, 0.1)
        self._t += dt
        solapes = self._t >= tm.PERIODO_SOLAPES or not self._lista
        if solapes:
            self._t = 0.0
            self._leer_fuentes()
        activo = self._activo()
        if activo:
            self._tanda()
        if solapes:
            self._solapes(activo)
        if self._fundiendo:
            self._fundir(dt)
        ms = (_reloj.perf_counter() - t0) * 1000.0
        self.ms_total += ms
        self.ms_max = max(self.ms_max, ms)
        self.frames += 1

    def _fundir(self, dt):
        for clave in list(self._fundiendo):
            objetivo = self._objetivo.get(clave, 1.0)
            alfa = tm.paso_alfa(self._alfa.get(clave, 1.0), objetivo, dt)
            self._alfa[clave] = alfa
            for nodo in self._nodos[clave]:
                if alfa <= 0.0:
                    nodo.hide()
                else:
                    if nodo.isHidden():
                        nodo.show()
                    nodo.setAlphaScale(alfa)
            if alfa == objetivo:
                self._fundiendo.discard(clave)

    # Objetivo del cartel: 0 si lo tapa un texto de más prioridad o si es ilegible; si cambia, empieza a fundirse.
    def _fijar(self, clave):
        objetivo = 0.0 if (clave in self._ocultos_solape or not self._legible.get(clave, True)) \
            else self._alfa_tamano.get(clave, 1.0)
        if objetivo == self._objetivo.get(clave, 1.0):
            return
        self._objetivo[clave] = objetivo
        if clave not in self._nodos:
            nodos = self._info[clave][1]
            self._nodos[clave] = nodos
            for nodo in nodos:
                nodo.setTransparency(TransparencyAttrib.M_alpha)
        self._fundiendo.add(clave)

    def _leer_fuentes(self):
        if self._n % PERIODO_FUENTES == 0 or not self._lista:
            cerca_antes = dict(zip((t[0] for t in self._carteles), self._v_cerca))
            try:
                self._lista = list(self._fuentes())
            except Exception:
                self._lista = []
            self._carteles = [t for t in self._lista if not t[3]]
            self._globos = [t for t in self._lista if t[3]]
            self._info = {t[0]: (t[1], t[2], t[3]) for t in self._lista}
            # Arreglos paralelos a _carteles para tm.repasar_carteles (centro y alto se miden una vez por cartel).
            self._v_centros = [self._centro_mundo(t[0], t[2][0]) for t in self._carteles]
            self._v_altos = [self._alto_mundo(t[0], t[2][0]) for t in self._carteles]
            self._v_normales = [self._normal_mundo(t[0], t[2][0]) for t in self._carteles]
            self._v_altos_px = [None] * len(self._carteles)     # último alto efectivo medido (diagnóstico)
            self._v_legibles = [self._legible.get(t[0], True) for t in self._carteles]
            self._v_cerca = [cerca_antes.get(t[0], False) for t in self._carteles]
            self._cursor = 0
        self._n += 1

    # Un tramo de los carteles por frame (un solo bucle puro): cercanía y (M1.4) legibilidad.
    def _tanda(self):
        n = len(self._carteles)
        if not n:
            return
        cam = application.base.cam
        m = application.base.render.getMat(cam)
        matriz = tuple(tuple(m.getRow(i)) for i in range(4))
        factor = tm.factor_px(cam.node().getLens().getFov()[1], application.base.win.getYSize())
        fin = min(self._cursor + -(-n // VUELTA_FRAMES), n)
        for k in tm.repasar_carteles(self._v_centros, self._v_altos, self._v_legibles, self._v_cerca, matriz, factor,
                                     self._cursor, fin, radio=tm.RADIO + HOLGURA_CERCA, minimo=self.minimo,
                                     normales=self._v_normales, diagnostico=self._v_altos_px):
            clave = self._carteles[k][0]
            self._legible[clave] = self._v_legibles[k]
            self._fijar(clave)
        if self.minimo:                 # M5: opacidad por tamaño entre ALTO_OCULTAR_PX y ALTO_PLENO_PX
            for k in range(self._cursor, fin):
                px = self._v_altos_px[k]
                if px is None:
                    continue
                clave = self._carteles[k][0]
                alfa = tm.alfa_por_tamano(px)
                if abs(alfa - self._alfa_tamano.get(clave, 1.0)) > 0.02 or (alfa == 1.0) != (self._alfa_tamano.get(clave, 1.0) == 1.0):
                    self._alfa_tamano[clave] = alfa
                    self._fijar(clave)
        self._cursor = 0 if fin >= n else fin

    # Normal (unitaria) del plano del cartel en el mundo, una vez: para penalizar los carteles vistos de lado.
    def _normal_mundo(self, clave, principal):
        if clave not in self._normales:
            try:
                n = application.base.render.getRelativeVector(principal, Vec3(0, 0, 1))
                largo = n.length()
                self._normales[clave] = (n.x / largo, n.y / largo, n.z / largo) if largo > 1e-9 else None
            except Exception:
                self._normales[clave] = None
        return self._normales[clave]

    # Centro del cartel en el mundo, una vez (los carteles no se mueven; las puertas solo durante las cinemáticas).
    def _centro_mundo(self, clave, principal):
        if clave not in self._centros:
            try:
                p = application.base.render.getRelativePoint(principal, Point3(0, 0, 0))
                self._centros[clave] = (p.x, p.y, p.z)
            except Exception:
                self._centros[clave] = None
        return self._centros[clave]

    # Solapes (M1.3): globos + carteles cercanos y legibles; sin escena activa (pausa, cinemática) nadie tapa a nadie.
    def _solapes(self, activo):
        ocultos = set()
        if self.prioridad and activo:
            cam = application.base.cam
            lente = cam.node().getLens()
            aspecto = window.aspect_ratio
            a_camara = application.base.render.getMat(cam)
            items = []
            candidatos = self._globos + [t for t, cerca, ver in zip(self._carteles, self._v_cerca, self._v_legibles)
                                         if cerca and ver]
            for clave, prioridad, nodos, es_globo in candidatos:
                centro = self._centro_de(clave, prioridad, nodos[0], cam, a_camara, es_globo)
                if centro is None or not tm.cerca_y_delante(centro.x, centro.y, centro.z):
                    continue
                fijo = prioridad == tm.PRIORIDAD_PUESTO and not es_globo
                rect = self._rect(clave, nodos, es_globo, centro, cam, lente, aspecto, a_camara if fijo else None)
                if rect is not None:
                    items.append((clave, prioridad, rect, centro.z))     # z = profundidad (delante de la cámara)
            ocultos = tm.resolver_ocultos(items)
        cambiados = ocultos ^ self._ocultos_solape
        self._ocultos_solape = ocultos
        for clave in cambiados:
            info = self._info.get(clave)
            if info is not None and not info[2]:
                self._fijar(clave)
        self.ocultos = ocultos | {c for c, ver in self._legible.items() if not ver}

    def _centro_de(self, clave, prioridad, principal, cam, a_camara, es_globo=False):
        if prioridad == tm.PRIORIDAD_PUESTO and not es_globo:
            return self._centro_fijo(clave, principal, a_camara)
        return self._centro(principal, es_globo, cam)

    # Centro del texto en espacio de cámara (x derecha, y arriba, z delante), o None si no cuenta ahora.
    def _centro(self, principal, es_globo, cam):
        try:
            if principal.isEmpty() or not principal.enabled:
                return None
            if es_globo and principal.getColorScale()[3] < ALFA_GLOBO_MIN:
                return None
            return cam.getRelativePoint(principal, Point3(0, 0, 0))
        except Exception:
            return None

    # Carteles que nunca se mueven (puestos, pintados): su centro en el mundo se guarda una vez y cada pasada solo se
    # transforma con la matriz de la cámara (mucho más barato que getRelativePoint con ~250 carteles).
    def _centro_fijo(self, clave, principal, a_camara):
        try:
            if principal.isEmpty() or not principal.enabled:
                return None
            mundo = self._centro_mundo(clave, principal)
            return None if mundo is None else a_camara.xformPoint(Point3(*mundo))
        except Exception:
            return None

    # Tamaño de letra del título en el mundo (m): el «em» de la fuente (Text.size x scale_override, en unidades locales:
    # Ursina escala así el nodo del texto) por la escala del Text en el mundo. No depende de qué letras lleve (las tildes
    # y la cedilla inflaban la caja ajustada) ni del tablero ni de la glosa. Estático: una vez por cartel.
    def _alto_mundo(self, clave, principal):
        if clave in self._altos:
            return self._altos[clave]
        try:
            em = float(getattr(principal, "size", 0.025)) * float(getattr(principal, "scale_override", 1.0) or 1.0)
            alto = em * abs(principal.getScale(application.base.render).y)
        except Exception:
            alto = None
        self._altos[clave] = alto
        return alto

    def _rect(self, clave, nodos, es_globo, centro, cam, lente, aspecto, a_camara=None):
        try:
            return self._rect_y_tamano(clave, nodos, es_globo, centro, cam, lente, aspecto, a_camara)
        except Exception:
            return None

    # Rectángulo en pantalla (unidades de Ursina) del texto (con su glosa), o None si no se puede proyectar.
    def _rect_y_tamano(self, clave, nodos, es_globo, centro, cam, lente, aspecto, a_camara=None):
        principal = nodos[0]
        if es_globo:
            esquinas = self._esquinas_globo(clave, principal, centro)
        elif a_camara is not None:                       # fijo: esquinas en el mundo, guardadas una vez
            mundo = self._esquinas.get(clave)
            if mundo is None:
                render = application.base.render
                mundo = self._esquinas[clave] = [render.getRelativePoint(principal, p)
                                                 for p in _esquinas_locales(principal, nodos)]
            esquinas = [a_camara.xformPoint(p) for p in mundo]
        else:
            locales = self._esquinas.get(clave)
            if locales is None:
                locales = self._esquinas[clave] = _esquinas_locales(principal, nodos)
            esquinas = [cam.getRelativePoint(principal, p) for p in locales]
        puntos = []
        p2 = Point2()
        for p in esquinas:
            if p.z > 0.05 and lente.project(p, p2):
                puntos.append(tm.a_pantalla(p2.x, p2.y, aspecto))
        if len(puntos) < 2:
            return None
        return tm.rect_de_puntos(puntos)

    # El globo es billboard (mira siempre a la cámara): su rectángulo es su caja local, escalada, alrededor del centro
    # en espacio de cámara (ejes «y-up-left» de Ursina: x derecha, y arriba, z delante). La caja: una vez por frase.
    def _esquinas_globo(self, clave, globo, centro):
        texto = globo.text
        medida = self._medidas_globo.get(clave)
        if medida is None or medida[0] != texto:
            mn, mx = globo.getTightBounds(globo)
            medida = (texto, ((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, (mx.x - mn.x) / 2, (mx.y - mn.y) / 2))
            self._medidas_globo[clave] = medida
        dx, dy, ax, ay = medida[1]
        escala = globo.getScale(application.base.render)
        sx, sy = abs(escala.x), abs(escala.y)
        cx, cy, z = centro.x + dx * sx, centro.y + dy * sy, centro.z
        ax, ay = ax * sx, ay * sy
        return [Point3(cx - ax, cy - ay, z), Point3(cx + ax, cy + ay, z),
                Point3(cx - ax, cy + ay, z), Point3(cx + ax, cy - ay, z)]

    def estadisticas(self):
        return {"ms_por_frame": self.ms_total / self.frames if self.frames else 0.0, "ms_max": self.ms_max,
                "frames": self.frames,
                "ocultos": len(self.ocultos), "fundiendo": len(self._fundiendo), "textos": len(self._lista)}


# Esquinas (en el plano del cartel) de la caja de todos sus nodos, en coordenadas locales del principal.
def _esquinas_locales(principal, nodos):
    mn_x = mn_y = float("inf")
    mx_x = mx_y = float("-inf")
    zs = []
    for nodo in nodos:
        caja = nodo.getTightBounds(principal)
        if not caja:
            continue
        mn, mx = caja
        mn_x, mn_y = min(mn_x, mn.x), min(mn_y, mn.y)
        mx_x, mx_y = max(mx_x, mx.x), max(mx_y, mx.y)
        zs.append((mn.z + mx.z) / 2)
    if not zs:
        return []
    z = sum(zs) / len(zs)
    return [Point3(mn_x, mn_y, z), Point3(mx_x, mx_y, z), Point3(mn_x, mx_y, z), Point3(mx_x, mn_y, z)]

# Globos de texto sobre los NPC (Ursina). La lógica (qué frase, cuándo, sin repetir, una ranura por NPC) es
# backend/logica/globos.py; los cálculos de pantalla, frontend/globos_npc_calculos.py.
#
# Retoques 23-nov (Módulo 3): los globos ya NO son textos del mundo. Eran billboards en `scene` con prueba de
# profundidad: cables, postes y fachadas se pintaban encima (y, con la tinta, sin escribir profundidad, lo opaco dibujado
# después los tapaba aunque estuviera detrás), la niebla y el pase final los teñían, de cerca crecían sin tope, el texto
# no se partía en líneas (Text.text no reaplica el wordwrap) y dos sistemas (este pool y llegada_visual) colgaban dos
# globos de la misma cabeza. Ahora:
#
#   CapaGlobos (una por escena del mundo, colgada del HUD en camera.ui, detrás de sus bloques): dibuja TODOS los globos
#   de NPC del mundo. Cada fuente (el pool de aquí, los vecinos de llegada_visual) le pasa en cada cuadro
#   fijar(fuente, [(cuerpo, texto, alfa, prioridad)]); la capa:
#     - da UN globo por NPC (si dos fuentes piden para el mismo, gana la de más prioridad) y, si el texto cambia, apaga
#       el anterior en 0,15 s antes de poner el nuevo (EstadoGlobo): nunca dos textos superpuestos;
#     - proyecta la cabeza a pantalla y pone el globo encima, con su colita, con un alto de letra entre un mínimo
#       legible y un tope (alto_linea), sin pisar a otros globos (se apilan) ni al HUD (ALCALDE_GLOBOS_SIN_HUD);
#       el que no cabe ESPERA (`bloqueados`: el pool no lo envejece);
#     - no pone globo a un NPC tapado por un edificio o el terreno (IndiceOclusores; en caché unos cuadros);
#     - fondo de papel OPACO con contorno de tinta y texto oscuro: al estar en camera.ui no lo tocan la niebla
#       (R2, ALCALDE_UI_SIN_NIEBLA), el pase final ni la tinta de pantalla, y se dibuja después de todo el mundo.
#   GlobosNPC: el pool de siempre (piscina fija de globos.RANURAS) hecho fuente de la capa.
#
# Sin fugas: las piezas de la capa se crean UNA vez (RANURAS_PANTALLA globos); por frame solo se mueven y se recolorean
# (el modelo redondeado del fondo se rehace al cambiar de frase, no por frame). Nunca lanza dentro del juego: un fallo
# se avisa una vez y la capa se esconde.

import math
import sys

from ursina import Entity, Text, camera, color, time, window
from ursina.models.procedural.quad import Quad

from backend.logica import globos
from frontend import estilo
from frontend import globos_npc_calculos as gc
from frontend import npc_postura
from frontend.piezas import silenciar

# Las importa también frontend/etapas_final_vista.py (sus NPC de etapa siguen siendo textos del mundo): no cambian.
ESCALA_TEXTO = 7.0               # como los carteles de nombre de los NPC clave (8)
AJUSTE_LINEA = gc.AJUSTE_LINEA   # caracteres por línea (la frase más larga, 90, son 4 líneas)
ALTURA = 0.32                    # m sobre el ancla de la cabeza
COLOR_TEXTO = (28, 30, 40)
COLOR_FONDO = (250, 248, 238, 235)
RELLENO = (0.045, 0.028)         # relleno del fondo, en unidades del texto

# M3.4 (ALCALDE_HUD_TAMANOS): globos más grandes y con fondo OPACO (también los de llegada_visual, que leen estas).
from frontend import hud_tamanos_calculos as _ht  # noqa: E402
if _ht.activo():
    ESCALA_TEXTO, COLOR_FONDO = _ht.ESCALA_GLOBO_NPC, _ht.FONDO_GLOBO_NPC

COLOR_BORDE = estilo.TINTA
RANURAS_PANTALLA = 8             # globos de pantalla: las ranuras del pool (4) + los vecinos de llegada (3) + 1
Z_CAPA = 0.5                     # en camera.ui, detrás de los bloques del HUD (z mayor = más lejos)
PRIORIDAD_POOL = 0
PRIORIDAD_LLEGADA = 10           # los vecinos que comentan el rumor de la misión mandan sobre la charla de siempre
PERIODO_OCLUSION = 5             # cuadros entre dos rayos del mismo NPC
BLOQUES_HUD = ("mision", "franja", "minimapa", "lugar", "telefono", "pila0", "pila1")
# Segunda pasada (D5): bloques que solo están a veces (chip «RECTA FINAL», avisos «K · …» y «L · …» de la pila). Se leen
# sus rectángulos REALES cuando están a la vista; si no se encuentra la pieza, se esquiva su sitio del mapa de esquinas.
BLOQUES_A_VECES = ("recta_final", "pila2", "pila3", "pulseras")   # pulseras = el brazalete (sale a ratos, HUD contextual)
PERIODO_HUD_VIVO = 15            # cuadros entre dos lecturas de los rectángulos reales de esos bloques
GROSOR_GUIA = 0.004              # línea de tinta del globo a su cabeza cuando la colita no llega (apilado o apartado)
Z_GUIAS = 0.3                    # detrás de todos los globos
BAJADA_CENTRO_CABEZA = 0.12      # m de la coronilla al centro de la cabeza (rayo de oclusión)
MARGEN_FUERA = 0.15              # una cabeza más allá de este margen fuera de pantalla no tiene globo


def _aviso(texto):
    print(f"[globos_npc] {texto}", file=sys.stderr)


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(round(max(0.0, min(1.0, alfa)) * 255)))


class _GloboPantalla:
    """Un globo de camera.ui: contorno, fondo, colita y texto, en un nodo `raiz` cuya escala = alto de una línea."""

    def __init__(self, padre, k):
        # La escala de la raíz NO toca z (ver colocar): las capas del globo quedan separadas en unidades de camera.ui
        # reales (su lente va de -1000 a 1000: con 24 bits de profundidad, un paso es ~1,2e-4).
        self.raiz = Entity(parent=padre, z=k * 0.02, enabled=False)
        self.cola_borde = Entity(parent=self.raiz, model="quad", rotation_z=45, z=0.008)
        self.borde = Entity(parent=self.raiz, model="quad", z=0.006)
        self.cola = Entity(parent=self.raiz, model="quad", rotation_z=45, z=0.004)
        self.fondo = Entity(parent=self.raiz, model="quad", z=0.002)
        self.texto = Text("", parent=self.raiz, origin=(0, 0), scale=1 / Text.size, z=0.0)
        self.guia = Entity(parent=padre, model="quad", z=Z_GUIAS + k * 0.001, enabled=False)
        silenciar(self.guia)
        self._con_guia = False
        self.rect = None
        for pieza in (self.cola_borde, self.borde, self.cola, self.fondo, self.texto, self.guia):
            pieza.setTransparency(True)
        silenciar(self.raiz)
        self.dueno = None            # id del cuerpo del NPC
        self.cuerpo = None
        self.inicio = 0
        self.prioridad = 0
        self.estado = gc.EstadoGlobo()
        self.medida = (0.0, 1)       # (ancho del texto en líneas, líneas)
        self._alfa = None
        self.alfa = 0.0

    def poner_texto(self, texto):
        self.texto.text = gc.envolver(texto)
        n = max(1, len(self.texto.text.split("\n")))
        ancho = self.texto.width / Text.size
        self.medida = (ancho, n)
        w = ancho + 2 * gc.RELLENO_X
        h = n + 2 * gc.RELLENO_Y
        b = gc.BORDE
        self.fondo.model = Quad(radius=round(min(0.45, 0.55 / h), 3), aspect=round(w / h, 2))
        self.fondo.scale = (w, h)
        self.borde.model = Quad(radius=round(min(0.45, (0.55 + b) / (h + 2 * b)), 3), aspect=round((w + 2 * b) / (h + 2 * b), 2))
        self.borde.scale = (w + 2 * b, h + 2 * b)
        lado = gc.COLA * 1.4142
        self.cola.scale = (lado, lado)
        self.cola_borde.scale = (lado + 2.4 * b, lado + 2.4 * b)
        self._alfa = None            # repintar colores (los modelos nuevos traen los suyos)

    def pintar(self, alfa):
        if self._alfa is not None and abs(alfa - self._alfa) < 0.01 and alfa not in (0.0, 1.0):
            return
        if self._alfa == alfa:
            return
        self._alfa = alfa
        fondo = _rgba(COLOR_FONDO, alfa)
        # El contorno es un quad lleno DEBAJO del fondo: a medio fundido se vería a través del papel (globo gris). Se
        # apaga antes (alfa^4): en el fundido el globo pasa limpio de papel a nada.
        borde = _rgba(COLOR_BORDE, alfa ** 4)
        self.fondo.color = fondo
        self.cola.color = fondo
        self.borde.color = borde
        self.cola_borde.color = borde
        self.guia.color = _rgba(COLOR_BORDE, alfa)
        self.texto.color = _rgba(COLOR_TEXTO, alfa)

    def colocar(self, rect, linea, px, cola_visible, py=None):
        self.rect = rect                 # (camera.ui) para pruebas y el arnés
        x0, y0, x1, y1 = rect
        _, alto_cuerpo, alto_cola = gc.medidas_globo(*self.medida, linea)
        self.raiz.position = ((x0 + x1) / 2, y0 + alto_cola + alto_cuerpo / 2, self.raiz.z)
        self.raiz.scale = (linea, linea, 1)
        if cola_visible:
            h = self.medida[1] + 2 * gc.RELLENO_Y
            w = self.medida[0] + 2 * gc.RELLENO_X
            dx = max(-w / 2 + 0.9, min(w / 2 - 0.9, (px - (x0 + x1) / 2) / linea))
            self.cola.position = (dx, -h / 2, self.cola.z)
            self.cola_borde.position = (dx, -h / 2 - gc.BORDE * 0.6, self.cola_borde.z)
        self.cola.enabled = self.cola_borde.enabled = cola_visible
        # Segunda pasada (D6): sin colita (globo apilado o apartado), una línea de tinta lleva a la cabeza.
        segmento = None if cola_visible or py is None else gc.guia(rect, px, py)
        self._con_guia = segmento is not None
        if segmento is not None:
            (ax, ay), (bx, by) = segmento
            largo = math.hypot(bx - ax, by - ay)
            self.guia.position = ((ax + bx) / 2, (ay + by) / 2, self.guia.z)
            self.guia.scale = (largo, GROSOR_GUIA)
            self.guia.rotation_z = -math.degrees(math.atan2(by - ay, bx - ax))

    def mostrar(self, visible):
        self.raiz.enabled = visible
        self.guia.enabled = visible and self._con_guia

    def ocultar(self):
        self.alfa = 0.0
        self.mostrar(False)

    def soltar(self):
        self.dueno = self.cuerpo = None
        self.estado = gc.EstadoGlobo()
        self.ocultar()


class CapaGlobos(Entity):
    """Todos los globos de NPC del mundo, en pantalla. Ver la cabecera."""

    def __init__(self, escena, **opciones):
        padre = getattr(escena, "hud", None) or camera.ui
        super().__init__(parent=padre, z=Z_CAPA, **opciones)
        self.escena = escena
        self._fuentes = {}
        self._globos = [_GloboPantalla(self, k) for k in range(RANURAS_PANTALLA)]
        self._por_dueno = {}
        self.bloqueados = set()      # ids de cuerpo cuyo globo no cupo en el último cuadro
        self._tapados = {}           # id de cuerpo -> (cuadro, tapado)
        self._indice = None
        self._frame = 0
        self._hud = (None, (), None, {})
        self._hud_vivo = []          # rects reales de BLOQUES_A_VECES a la vista (se relee cada PERIODO_HUD_VIVO)
        self._frame_hud_vivo = -PERIODO_HUD_VIVO
        self.oculta = False          # D3: hay un panel abierto (ningún globo)
        self.roto = False

    # -- API de las fuentes --

    def fijar(self, fuente, pedidos):
        """pedidos: [(cuerpo, texto, alfa, prioridad)] de esta fuente en este cuadro (lo de antes se olvida)."""
        self._fuentes[fuente] = list(pedidos)

    def soltar_fuente(self, fuente):
        self._fuentes.pop(fuente, None)

    def visible(self, cuerpo):
        """¿Se le puede poner globo a este NPC (no lo tapa un edificio ni el terreno)? En caché PERIODO_OCLUSION
        cuadros. Nunca lanza (ante un error, True)."""
        try:
            clave = id(cuerpo)
            visto = self._tapados.get(clave)
            if visto is not None and self._frame - visto[0] < PERIODO_OCLUSION:
                return not visto[1]
            tapado = self._tapado(cuerpo)
            self._tapados[clave] = (self._frame, tapado)
            if len(self._tapados) > 64:
                self._tapados = {k: v for k, v in self._tapados.items() if self._frame - v[0] < 60}
            return not tapado
        except Exception:      # noqa: BLE001
            return True

    def estado(self):
        """[(id del dueño, texto en una línea, alfa, Text)] de los globos que se ven (alfa > 0.01). Pruebas y arnés."""
        return [(g.dueno, g.texto.text.replace("\n", " ")[:40], round(g.alfa, 3), g.texto)
                for g in self._globos if g.dueno is not None and g.raiz.enabled and g.alfa > 0.01]

    def textos(self):
        return [g.texto for g in self._globos if g.raiz.enabled]

    # -- Oclusión --

    def _oclusores(self):
        if self._indice is None:
            mundo = getattr(self.escena, "_mundo", None)
            cajas = []
            altura = getattr(mundo, "altura", None)
            if mundo is not None:
                for e in mundo.edificios():
                    x0, x1, z0, z1 = e.caja()
                    suelo = altura(e.cx, e.cz) if altura else 0.0
                    cajas.append((x0, x1, min(suelo, e.y) - 0.5, e.y + e.alto, z0, z1))
                for o in mundo.obstaculos():
                    alto = getattr(o, "alto_total", None)
                    if alto is None or not o.es_caja:
                        continue
                    suelo = altura(o.cx, o.cz) if altura else 0.0
                    cajas.append((o.cx - o.ancho / 2, o.cx + o.ancho / 2, suelo - 0.5, suelo + alto,
                                  o.cz - o.fondo / 2, o.cz + o.fondo / 2))
                for o in mundo.obstaculos():                   # D6: copas de los árboles del mundo (ciudad_3d._arbol)
                    if o.tipo == "arbol" and o.es_circulo:
                        cajas.append(gc.caja_arbol(o.cx, o.cz, (altura(o.cx, o.cz) if altura else 0.0) - 0.15))
            self._indice = gc.IndiceOclusores(cajas, altura=altura)
        return self._indice

    def _tapado(self, cuerpo):
        from ursina import application
        base = application.base
        ancla = npc_postura.ancla_cabeza(cuerpo)
        p = ancla.getPos(base.render)
        ojo = base.cam.getPos(base.render)
        # D6: el rayo va al CENTRO de la cabeza, no al ancla (que está MARGEN_ANCLA_CABEZA m por encima de la coronilla):
        # con el ancla, una cabeza escondida tras la del jugador (o tras un alero) seguía contando como «a la vista».
        y = p[1] - getattr(npc_postura, "MARGEN_ANCLA_CABEZA", 0.24) - BAJADA_CENTRO_CABEZA
        return self._oclusores().tapado((ojo[0], ojo[1], ojo[2]), (p[0], y, p[2]), extras=self._caja_jugador())

    def _caja_jugador(self):
        """D6: el personaje del jugador tapa a un NPC que está justo detrás de él (su globo parecería del jugador)."""
        try:
            jugador = self.escena.flujo.jugador_activo()
            mundo = self.escena._mundo
            return (gc.caja_jugador(jugador.x, jugador.z, mundo.altura(jugador.x, jugador.z)),)
        except Exception:      # noqa: BLE001
            return ()

    # -- Cuadro --

    def update(self):
        if self.roto:
            return
        try:
            self._cuadro(min(time.dt, 0.1))
        except Exception as error:      # noqa: BLE001
            self.roto = True
            _aviso(f"globos apagados ({type(error).__name__}: {error})")
            for g in self._globos:
                g.soltar()

    def _obstaculos(self, ancho_px, alto_px):
        clave = (ancho_px, alto_px)
        if self._hud[0] != clave:
            from frontend import hud_esquinas_calculos as he
            from frontend import llegada_visual_calculos as lv
            rects = he.layout_esquinas(ancho_px, alto_px) if lv.globos_sin_hud_activo() else {}
            self._hud = (clave, [rects[n] for n in BLOQUES_HUD if n in rects], he.zona_segura(ancho_px, alto_px),
                         {n: rects[n] for n in BLOQUES_A_VECES if n in rects})
            self._frame_hud_vivo = -PERIODO_HUD_VIVO
        if not self._hud[3]:
            return self._hud[1], self._hud[2]
        if self._frame - self._frame_hud_vivo >= PERIODO_HUD_VIVO:
            self._frame_hud_vivo = self._frame
            self._hud_vivo = self._leer_hud_vivo(self._hud[3])
        return list(self._hud[1]) + self._hud_vivo, self._hud[2]

    def _piezas_a_veces(self):
        """{bloque: Entity | None | "sin"}: las piezas reales del chip «RECTA FINAL» y de los avisos K (dilemas) y L
        (Civitas). None = no se encontró (se esquiva su sitio del mapa de esquinas); "sin" = no está instalado."""
        piezas = {}
        try:
            from frontend import recta_final_vista
            vigia = recta_final_vista._instalado.get("vigia")
            piezas["recta_final"] = "sin" if vigia is None else getattr(vigia, "chip", None)
        except Exception:      # noqa: BLE001
            piezas["recta_final"] = None
        conexion = getattr(self.escena, "_conexion_globos", None)
        for nombre, atributo in (("pila2", "dilemas_ui"), ("pila3", "habitos_ui")):
            control = getattr(conexion, atributo, None) if conexion is not None else None
            piezas[nombre] = gc.buscar_atributo(control, "chip_entidad") if control is not None else None
        vigia = getattr(conexion, "vigia_manillas", None) if conexion is not None else None
        if conexion is not None and vigia is None:
            piezas["pulseras"] = "sin"                   # manillas apagadas (ALCALDE_MANILLAS=0): no hay brazalete
        else:
            piezas["pulseras"] = getattr(getattr(vigia, "vista", None), "chip", None)
        return piezas

    def _leer_hud_vivo(self, sitios):
        rects = []
        try:
            piezas = self._piezas_a_veces()
        except Exception:      # noqa: BLE001
            piezas = {}
        for nombre, sitio in sitios.items():
            pieza = piezas.get(nombre)
            if isinstance(pieza, str):                 # el módulo no está instalado: no hay pieza que esquivar
                continue
            if pieza is None:
                rects.append(sitio)
                continue
            try:
                if not pieza.enabled or pieza.has_disabled_ancestor():
                    continue
                caja = pieza.getTightBounds(camera.ui)
                if caja:
                    mn, mx = caja
                    rects.append((mn[0], mn[1], mx[0], mx[1]))
            except Exception:      # noqa: BLE001
                rects.append(sitio)
        return rects

    def _oculta(self):
        """D3: ¿hay que esconder todos los globos? Mismo criterio que congela al jugador (EscenaMundo.controles_bloqueados:
        pausa, cinemática, mapa grande, mochila, paneles registrados, trabajo, vendedor...) más el teléfono abierto y
        la leyenda de las pulseras (B), que no bloquean pero tapan."""
        escena = self.escena
        bloqueados = telefono = False
        otros = []
        try:
            bloqueados = bool(escena.controles_bloqueados())
        except Exception:      # noqa: BLE001
            pass
        try:
            telefono = bool(escena.flujo.jugador_activo().telefono.bloquea_movimiento())
        except Exception:      # noqa: BLE001
            pass
        try:
            conexion = getattr(escena, "_conexion_globos", None)
            vigia = getattr(conexion, "vigia_manillas", None) if conexion is not None else None
            vista = getattr(vigia, "vista", None)
            if vista is not None:
                otros.append(bool(vista.leyenda_abierta()))
        except Exception:      # noqa: BLE001
            pass
        return gc.globos_ocultos(getattr(escena, "en_pausa", False), getattr(escena, "_cinematica", False),
                                 getattr(escena, "enabled", True), bloqueados, telefono, otros)

    def _pedidos(self):
        """{id cuerpo: (cuerpo, texto, alfa, prioridad)}: por NPC, el pedido de más prioridad de todas las fuentes."""
        juntos = {}
        for pedidos in self._fuentes.values():
            for cuerpo, texto, alfa, prioridad in pedidos:
                if cuerpo is None or not texto:
                    continue
                previo = juntos.get(id(cuerpo))
                if previo is None or (prioridad, alfa) > (previo[3], previo[2]):
                    juntos[id(cuerpo)] = (cuerpo, texto, alfa, prioridad)
        return juntos

    def _cuadro(self, dt):
        from panda3d.core import LVecBase4f
        from ursina import application
        self._frame += 1
        self.oculta = self._oculta()
        if self.oculta:                                   # D3: un panel abierto: ningún globo, ya (sin fundido)
            for g in self._globos:
                if g.dueno is not None:
                    g.soltar()
            self.bloqueados = set()
            return
        pedidos = self._pedidos()
        # 1. Un globo por NPC: los que ya tenían globo siguen con el suyo; los nuevos toman uno libre (por prioridad).
        for g in self._globos:
            if g.dueno is not None and g.dueno not in pedidos and g.alfa <= 0.0 and g.estado.texto is None:
                g.soltar()
        libres = [g for g in self._globos if g.dueno is None]
        for clave, (cuerpo, texto, alfa, prioridad) in sorted(pedidos.items(), key=lambda kv: -kv[1][3]):
            g = next((x for x in self._globos if x.dueno == clave), None)
            if g is None:
                if not libres:
                    continue
                g = libres.pop(0)
                g.dueno, g.cuerpo, g.inicio = clave, cuerpo, self._frame
            g.prioridad = prioridad
        # 2. Texto y alfa de cada globo (cambio de frase con fundido; NPC tapado = se apaga).
        activos = []
        for g in self._globos:
            if g.dueno is None:
                continue
            pedido = pedidos.get(g.dueno)
            texto, alfa = (pedido[1], pedido[2]) if pedido is not None else (None, 0.0)
            if texto and not self.visible(g.cuerpo):
                alfa = 0.0
            mostrado, a, cambio = g.estado.paso(dt, texto, alfa)
            if cambio and mostrado:
                g.poner_texto(mostrado)
            g.alfa = a
            if mostrado is None and a <= 0.0:
                g.soltar()
                continue
            activos.append(g)
        # 3. Sitio en pantalla: proyección de la cabeza, alto de letra por distancia, sin pisarse ni pisar el HUD.
        self.bloqueados = set()
        if not activos:
            return
        base = application.base
        ancho_px, alto_px = (int(v) for v in window.size)
        if alto_px <= 0:
            return
        aspecto = ancho_px / alto_px
        obstaculos, zona = self._obstaculos(ancho_px, alto_px)
        matriz = camera.lens.getProjectionMat()
        ojo = base.cam.getPos(base.render)
        lista = []
        for g in activos:
            ancla = npc_postura.ancla_cabeza(g.cuerpo)
            punto = base.render.getRelativePoint(ancla, (0, ALTURA, 0))
            c = base.cam.getRelativePoint(base.render, punto)
            v = matriz.xform(LVecBase4f(c[0], c[1], c[2], 1.0))
            if c[2] <= 0.05 or v[3] <= 1e-6:              # detrás de la cámara (y-up-left: z = profundidad)
                g.ocultar()
                continue
            px, py = gc.film_a_ui(v[0] / v[3], v[1] / v[3], aspecto)
            if abs(px) > aspecto / 2 + MARGEN_FUERA or py < -0.5 - MARGEN_FUERA:
                g.ocultar()
                continue
            distancia = (punto - ojo).length()
            linea = gc.alto_linea(distancia)
            ancho, alto, cola = gc.medidas_globo(*g.medida, linea)
            lista.append((g, px, py, linea, ancho, alto + cola))
        lista.sort(key=lambda t: (-t[0].prioridad, t[0].inicio))
        cabezas = {id(t[0]): gc.rect_cabeza(t[1], t[2]) for t in lista} if len(lista) > 1 else None
        sitios = gc.colocar([(id(t[0]), t[1], t[2], t[4], t[5]) for t in lista], obstaculos, zona, cabezas=cabezas)
        for g, px, py, linea, ancho, alto in lista:
            rect = sitios.get(id(g))
            if rect is None:
                g.ocultar()
                g.estado.alfa = 0.0             # cuando quepa, vuelve a entrar con su fundido
                self.bloqueados.add(g.dueno)
                continue
            g.colocar(rect, linea, px, cola_visible=abs(rect[1] - py) < 0.01 and rect[0] + 0.02 < px < rect[2] - 0.02,
                      py=py)
            g.pintar(g.alfa)
            g.mostrar(g.alfa > 0.0)

    def ocultar(self):
        self._fuentes.clear()
        for g in self._globos:
            g.soltar()


def registrar_conexion(escena, conexion):
    """La conexión del juego (para leer los avisos K/L, la leyenda de pulseras...). La llama registro_ambiente_npc."""
    escena._conexion_globos = conexion


def capa_de(escena):
    """La CapaGlobos de la escena del mundo (se crea la primera vez)."""
    capa = getattr(escena, "_capa_globos", None)
    if capa is None:
        capa = CapaGlobos(escena)
        escena._capa_globos = capa
    return capa


class GlobosNPC:
    """El pool de globos del mundo chico (backend/logica/globos.PlanificadorGlobos), dibujado por la CapaGlobos."""

    FUENTE = "pool"

    def __init__(self, parent, planificador, escena=None):
        self.plan = planificador
        self.capa = capa_de(escena if escena is not None else parent)
        n = len(planificador.ranuras)
        self._series, self._duenos = [0] * n, [None] * n
        self._globos = []            # registro_textos_mundo los leía como textos del mundo: ya no lo son
        self.mostrados = 0

    def actualizar(self, dt, candidatos=(), nivel=None, hora=None, dia=None):
        """`candidatos`: [(clave, estado, distancia, peso, npc)] ya filtrados (cerca y en el cono de la cámara). Aquí se
        quitan los que tapa un edificio; el npc es la Entity del personaje (se usa su ancla de cabeza)."""
        plan, capa = self.plan, self.capa
        candidatos = [c for c in candidatos if capa.visible(c[4])]
        cuerpos = {c[0]: c[4] for c in candidatos}
        retenidas = {c[0] for c in candidatos if id(c[4]) in capa.bloqueados} if capa.bloqueados else ()
        plan.avanzar(dt, candidatos, nivel, hora, dia, retenidas)
        pedidos = []
        for k, ranura in enumerate(plan.ranuras):
            if ranura.clave is None:
                self._duenos[k] = None
                continue
            cuerpo = cuerpos.get(ranura.clave)
            if ranura.serie != self._series[k]:                  # frase nueva en esta ranura
                self._series[k] = ranura.serie
                if cuerpo is None:
                    ranura.clave = ranura.pendiente = None
                    self._duenos[k] = None
                    continue
                self._duenos[k] = cuerpo
                self.mostrados += 1
            elif cuerpo is not None and cuerpo is not self._duenos[k]:
                ranura.clave = ranura.pendiente = None           # el actor se prestó a otro agente: no lo hereda
                self._duenos[k] = None
                continue
            if self._duenos[k] is not None:
                pedidos.append((self._duenos[k], ranura.texto, plan.alfa(k), PRIORIDAD_POOL))
        capa.fijar(self.FUENTE, pedidos)

    def ocultar(self):
        self.plan.vaciar()
        self._duenos = [None] * len(self._duenos)
        self.capa.fijar(self.FUENTE, ())

    def visibles(self):
        return sum(1 for g in self.capa._globos if g.dueno is not None and g.raiz.enabled
                   and any(g.cuerpo is d for d in self._duenos))

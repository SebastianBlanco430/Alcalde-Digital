# CiudadGrande: la ciudad 3D del mapa grande (~900 x 650 m, 4600 casas), con la MISMA interfaz que Ciudad3D para EscenaMundo
# (raiz_colisiones, puertas, letreros, banderas, encender_luces, cerrar_puertas, cielo, luz) pero construida por CHUNKS de 64 m
# que van apareciendo y desapareciendo alrededor del jugador (GestorChunks). Ciudad3D no se toca: el mundo chico sigue siendo él.
#
# Qué es global (se construye una vez, al crear la ciudad): cielo y luces, los 21 edificios jugables con sus puertas, letreros y
# banderas, los discos pintados de las 24 plazas y el FONDO de terreno (una malla de todo el mapa a 8 m, 0,6 m más baja).
# Qué es por chunk:
#   LOD0 (< ~110-140 m)  terreno a 1 m, calles (arena y asfalto), casas completas fundidas por textura, contornos de tinta,
#                        árboles, farolas, escaleras, muros, tanques, antenas, ropa, murales, banderines, cancha y mercadito
#   LOD1 (< ~300 m)      terreno a 4 m y una caja de color por casa (+ árboles de 33 vértices)
#   más lejos            solo el fondo
# Cada chunk son 3-4 Entity (raíz + luz/sin luz/unlit) con mallas de Panda3D sueltas colgando: ~40 llamadas de dibujo en LOD0 y 2-3 en LOD1.
#
# Streaming: GestorChunks (un Entity) reparte PRESUPUESTO_MS ms por frame entre generadores de construcción; la planificación
# (chunks_calculos.planificar) ordena por distancia al jugador y a donde irá en SEGUNDOS_DE_ADELANTO s. Al entrar a jugar,
# el anillo de arranque (RADIO_ARRANQUE) se construye de golpe con una barra de progreso (barra_carga.py).
#
# Sombras (plan B de la fase F5): el mapa grande no hornea sombras globales. El mapa de sombras de la luz se deja VACÍO (todo
# iluminado, sin manchas ni acné) y la fase F6 (sombras locales) lo llenará con la zona alrededor del jugador.
#
# Cámara: no hay un collider por casa (serían 4600). La cámara usa su colisión analítica con las cajas de las casas de los chunks
# LOD0 cercanos (obstaculos_camara, una lista que este gestor mantiene) y el raycast solo contra los edificios jugables.

import math
import time as reloj

from panda3d.core import NodePath, TransparencyAttrib, CullFaceAttrib
from ursina import Entity, Text, camera, destroy, scene, time
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader, unlit_shader

from backend.logica.vista_chunk import VistaChunk
from frontend import camara_calculos as cc
from frontend import estilo, mundo_config, rendimiento
from frontend import chunks_calculos as calc
from frontend.arboles_lowpoly import arbol_bajo, arbusto_bajo
from frontend.banderas import crear_banderas
from frontend.calles_chunk import calles_del_chunk, plazas_globales
from frontend.casas_chunk import FabricaCasas, cajas_lod1, lote_de_casas
from frontend.cielo import DIRECCION_SOL, CieloDegradado
from frontend.ciudad_3d import (COLOR_LUZ_AMBIENTE, COLOR_LUZ_SOL, RESOLUCION_SOMBRAS, SOMBRAS, CONTORNO_TINTA, Ciudad3D,
                                rgb_luz)
from frontend.componentes import rgb
from frontend.favela_detalles import letreros_secretos
from frontend.geom_directa import Acumulador, escribir_geom
from frontend.geometria_mundo import apoyo_de_caja
from frontend.objetos_chunk import HALO_DETALLES, ContextoObjetos, construir_objetos
from frontend.piezas import MASCARA_LUZ, encender_luz, lineas_sueltas, silenciar
from frontend.sombras_locales import SombrasLocales, es_shader_de_luz, shader_de_ciudad
from frontend.suelo_favela import textura_del_camino, textura_del_grano
from frontend.terreno_lod import CampoSuelo, malla_fondo, malla_lod0, malla_lod1

MAX_SOLTAR_POR_FRAME = 2          # chunks (niveles) que se destruyen por frame
CADA_N_FRAMES_PLAN = 8            # cada cuántos frames se replanifica (si no se movió antes)
MOVIMIENTO_REPLAN = 6.0           # m que obligan a replanificar
RADIO_CAMARA = 48.0               # m: la cámara solo choca con casas de chunks LOD0 a esta distancia del jugador


MUESTRAS_SOMBRA = 1               # el shader promedia muestras x muestras del mapa de sombras (4 x 4 = 16 lecturas por pixel);
                                  # con el mapa vacío (plan B) una sola basta y el pixel cuesta ~la mitad. F6 puede subirlo.


def _aplicar_niebla(entidad):
    """Las Entity nuevas nacen sin la niebla de la escena (scene.fog_* solo recorre las que ya existían): se la damos."""
    entidad.set_shader_input("shadow_samples", MUESTRAS_SOMBRA)
    entidad.set_shader_input("fog_color", scene.fog_color)
    d = scene.fog_density
    if isinstance(d, tuple):
        entidad.set_shader_input("fog_start", d[0])
        entidad.set_shader_input("fog_end", d[1])


class NivelChunk:
    """Un chunk a un nivel de detalle: sus Entity y sus datos (cajas de cámara, conteos)."""

    def __init__(self, clave, nivel, raiz, entidades, cajas_camara, draws, vertices):
        self.clave, self.nivel = clave, nivel
        self.raiz = raiz
        self.entidades = entidades
        self.cajas_camara = cajas_camara
        self.draws = draws
        self.vertices = vertices

    def destruir(self):
        for e in self.entidades:
            destroy(e)
        destroy(self.raiz)
        self.entidades = []


def _contar(nodos):
    """Llamadas de dibujo (geoms) de las mallas dadas. (Contar vértices con SceneGraphAnalyzer costaba ~6 ms por chunk.)"""
    draws = 0
    for np_ in nodos:
        for g in np_.find_all_matches("**/+GeomNode"):
            draws += g.node().get_num_geoms()
        if np_.node().is_geom_node():
            draws += np_.node().get_num_geoms()
    return draws, 0


class GestorChunks(Entity):

    def __init__(self, ciudad, mundo, campo, fabrica, ctx, **opciones):
        super().__init__(parent=ciudad, name="gestor_chunks", **opciones)
        self.ciudad, self.mundo, self.campo, self.fabrica, self.ctx = ciudad, mundo, campo, fabrica, ctx
        self.fuente_foco = None                 # callable -> (x, z) del jugador; None = la cámara
        self.pausado = False
        self.niveles = {}                       # clave -> {0: NivelChunk, 1: NivelChunk}
        self.limites = {(ci, cj): mundo.limites_de_chunk(ci, cj)
                        for cj in range(mundo.chunks_z) for ci in range(mundo.chunks_x)}
        self.obstaculos_camara = []             # cajas de cámara (camara_calculos) de la zona activa; la lista no se reemplaza
        self.cajas_fijas = []                   # edificios jugables
        self._cola = []                         # [(prioridad, clave, nivel)]
        self._tarea = None                      # (clave, nivel, generador)
        self._por_soltar = []                   # [(clave, nivel)]
        self._degradar = set()                  # claves con LOD0 que se sueltan al terminar su LOD1
        self._foco = None
        self._foco_plan = None
        self._frames = 0
        self._velocidad = (0.0, 0.0)
        self._sucio_camara = True
        self.radio_lod0 = mundo_config.RADIO_LOD0
        self.radio_lod1 = mundo_config.RADIO_LOD1
        self.tiempos = {0: [], 1: []}           # s de CPU gastados por chunk construido (estadísticas)
        self._t_tarea = 0.0
        self.construidos = {0: 0, 1: 0}
        self.max_paso_ms = 0.0
        self.peor_paso = None                   # (ms, clave, nivel, (archivo, función, línea)) del paso más largo
        self.diagnostico = True
        self.ignore_paused = True

    # -- Foco --

    def _leer_foco(self):
        if self.fuente_foco is not None:
            try:
                f = self.fuente_foco()
                if f is not None:
                    return (float(f[0]), float(f[1]))
            except Exception:                    # noqa: BLE001 — sin jugador todavía: la cámara
                pass
        return (camera.world_position[0], camera.world_position[2])

    # -- Planificación --

    def _actual(self):
        return {k: (0 if 0 in v else 1) for k, v in self.niveles.items() if v}

    def planificar(self, focos, radio0=None, radio1=None):
        construir, soltar, degradar = calc.planificar(
            self.limites, focos, self._actual(), radio0 or self.radio_lod0, radio1 or self.radio_lod1,
            mundo_config.HISTERESIS, mundo_config.ADELANTO)
        return construir, soltar, degradar

    def _replanificar(self, foco):
        vx, vz = self._velocidad
        focos = [foco]
        if abs(vx) + abs(vz) > 0.5:
            focos.append(calc.foco_adelantado(foco[0], foco[1], vx, vz, mundo_config.SEGUNDOS_DE_ADELANTO))
        construir, soltar, degradar = self.planificar(focos)
        deseados = {(c, n) for _, c, n in construir}
        if self._tarea is not None and (self._tarea[0], self._tarea[1]) not in deseados:
            self._tarea[2].close()
            self._tarea = None
        self._cola = construir
        for clave in soltar:
            for nivel in tuple(self.niveles.get(clave, {})):
                self._por_soltar.append((clave, nivel))
        self._degradar = set(degradar)
        self._foco_plan = foco
        self._sucio_camara = True

    # -- Construcción: generadores --

    def _tarea_nueva(self, clave, nivel):
        return self._lod0(clave) if nivel == 0 else self._lod1(clave)

    def _grillas(self, clave):
        ci, cj = clave
        t = self.mundo.terreno
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                c = (ci + di, cj + dj)
                if 0 <= c[0] < self.mundo.chunks_x and 0 <= c[1] < self.mundo.chunks_z:
                    t.grilla_de_chunk(*c)
                    yield

    def _lod0(self, clave):
        mundo, (ci, cj) = self.mundo, clave
        yield from self._grillas(clave)
        vista = VistaChunk(mundo, ci, cj, HALO_DETALLES)
        casas_h = vista.casas
        apoyos = []
        for n, c in enumerate(casas_h):
            apoyos.append(apoyo_de_caja(mundo.altura, c.cx, c.cz, c.ancho, c.fondo))
            if n % 10 == 9:
                yield
        propias = {i for i, c in enumerate(casas_h) if mundo.chunk_de(c.cx, c.cz) == clave}
        orden = sorted(propias)
        yield
        datos = yield from malla_lod0(mundo.terreno, self.campo, ci, cj)
        g_terreno = yield from escribir_geom("terreno", datos.vertices, datos.normales, datos.colores, datos.triangulos, datos.uvs)
        arena, asfalto = Acumulador(), Acumulador()
        arena.uvs = []
        yield from calles_del_chunk(mundo, self.campo, vista, clave, arena, asfalto)
        g_arena = yield from arena.volcar_a_geom("calles_arena")
        g_asfalto = yield from asfalto.volcar_a_geom("asfalto")
        lote, tinta = yield from lote_de_casas(self.fabrica, [casas_h[i] for i in orden], [apoyos[i][1] for i in orden],
                                               contorno=CONTORNO_TINTA)
        obj = yield from construir_objetos(self.ctx, vista, clave, casas_h, apoyos, propias)
        g_lit = yield from obj.lit.volcar_a_geom("objetos")
        g_pintura = yield from obj.pintura.volcar_a_geom("pintura")
        g_manchas = yield from obj.manchas.volcar_a_geom("manchas")
        g_banderines = yield from obj.banderines.volcar_a_geom("banderines")
        g_luces = yield from obj.luces.volcar_a_geom("luces")
        cables = lineas_sueltas(obj.cables) if obj.cables else None
        yield
        lit, plano, unlit = [], [], []
        if g_terreno is not None:
            n = NodePath(g_terreno)
            n.set_texture(self.ciudad.textura_grano._texture)
            n.set_two_sided(True)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        if g_arena is not None:
            n = NodePath(g_arena)
            n.set_texture(self.ciudad.textura_camino._texture)
            n.set_two_sided(True)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        if g_asfalto is not None:
            n = NodePath(g_asfalto)
            n.set_two_sided(True)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        if g_lit is not None:
            lit.append(NodePath(g_lit))
        if g_pintura is not None:
            n = NodePath(g_pintura)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        lit.append(lote)
        if tinta is not None:
            n = tinta
            n.hide(MASCARA_LUZ)
            plano.append(n)
        if g_luces is not None:
            n = NodePath(g_luces)
            n.hide(MASCARA_LUZ)
            plano.append(n)
        if cables is not None:
            cables.set_render_mode_thickness(2)
            cables.set_color(22 / 255, 22 / 255, 26 / 255, 1)
            cables.hide(MASCARA_LUZ)
            plano.append(cables)
        if g_manchas is not None:
            n = NodePath(g_manchas)
            n.set_two_sided(True)
            n.set_transparency(TransparencyAttrib.M_alpha)
            n.set_depth_write(False)
            n.hide(MASCARA_LUZ)
            unlit.append(n)
        if g_banderines is not None:
            n = NodePath(g_banderines)
            n.set_two_sided(True)
            n.hide(MASCARA_LUZ)
            unlit.append(n)
        cajas = [cc.obstaculo_caja(c.cx, c.cz, c.ancho, c.fondo, apoyos[i][0], apoyos[i][1] + c.alto_total)
                 for i, c in ((i, casas_h[i]) for i in orden)]
        return (yield from self._instalar(clave, 0, lit, plano, unlit, cajas))

    def _lod1(self, clave):
        mundo, (ci, cj) = self.mundo, clave
        yield from self._grillas(clave)
        vista = VistaChunk(mundo, ci, cj, 0.0)
        propias = [c for c in vista.casas if mundo.chunk_de(c.cx, c.cz) == clave]
        apoyos = []
        for n, c in enumerate(propias):
            apoyos.append(apoyo_de_caja(mundo.altura, c.cx, c.cz, c.ancho, c.fondo))
            if n % 10 == 9:
                yield
        datos = yield from malla_lod1(mundo.terreno, self.campo, ci, cj)
        g_terreno = yield from escribir_geom("terreno1", datos.vertices, datos.normales, datos.colores, datos.triangulos, datos.uvs)
        acum = Acumulador()
        cajas_lod1(acum, propias, apoyos)
        for o in vista.obstaculos:
            if mundo.chunk_de(o.cx, o.cz) != clave:
                continue
            if o.tipo == "arbol":
                arbol_bajo(acum, o.cx, mundo.altura(o.cx, o.cz), o.cz, lejano=True)
            elif o.tipo == "arbusto":
                arbusto_bajo(acum, o.cx, mundo.altura(o.cx, o.cz), o.cz, lejano=True)
        g_cajas = yield from acum.volcar_a_geom("cajas")
        lit = []
        if g_terreno is not None:
            n = NodePath(g_terreno)
            n.set_texture(self.ciudad.textura_grano._texture)
            n.set_two_sided(True)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        if g_cajas is not None:
            n = NodePath(g_cajas)
            n.hide(MASCARA_LUZ)
            lit.append(n)
        return (yield from self._instalar(clave, 1, lit, [], [], []))

    def _instalar(self, clave, nivel, lit, plano, unlit, cajas):
        """Generador: crea las Entity del chunk y cuelga las mallas (en pasos cortos). Devuelve el NivelChunk."""
        raiz = Entity(parent=self, name="chunk_%d_%d_L%d" % (clave[0], clave[1], nivel))
        entidades = []
        yield
        if lit:
            e = Entity(parent=raiz, shader=shader_de_ciudad())
            _aplicar_niebla(e)
            for n in lit:
                n.reparent_to(e)
            entidades.append(e)
        if plano:
            e = Entity(parent=raiz, shader=None)
            for n in plano:
                n.reparent_to(e)
            e.set_light_off()
            entidades.append(e)
        if unlit:
            e = Entity(parent=raiz, shader=unlit_shader)
            for n in unlit:
                n.reparent_to(e)
            entidades.append(e)
        for e in entidades + [raiz]:
            e.ignore = True
        yield
        draws, vertices = _contar(lit + plano + unlit)
        yield
        if mundo_config.PRECARGAR_CHUNKS:           # sube las mallas a la GPU malla por malla (todo junto eran ~8 ms)
            for n in lit + plano + unlit:
                rendimiento.precargar(n)
                yield
        return NivelChunk(clave, nivel, raiz, entidades, cajas, draws, vertices)

    # -- Ciclo --

    def _avanzar(self):
        """Un paso de la tarea actual. False si no hay nada que hacer."""
        if self._tarea is None:
            while self._cola:
                _, clave, nivel = self._cola.pop(0)
                if nivel in self.niveles.get(clave, {}):
                    continue
                self._tarea = (clave, nivel, self._tarea_nueva(clave, nivel))
                self._t_tarea = 0.0
                break
            else:
                return False
        clave, nivel, gen = self._tarea
        antes = self._donde(gen) if self.diagnostico else None
        t0 = reloj.perf_counter()
        try:
            next(gen)
            fin = None
        except StopIteration as e:
            fin = e
        dt = reloj.perf_counter() - t0
        self._t_tarea += dt
        if dt * 1000 > self.max_paso_ms:
            self.max_paso_ms = dt * 1000
            self.peor_paso = (round(dt * 1000, 1), clave, nivel, antes)
        if fin is not None:
            self._tarea = None
            self._terminar(clave, nivel, fin.value)
        return True

    # (archivo, función, línea) donde está detenido el generador más interno: dónde empieza el próximo paso (diagnóstico).
    @staticmethod
    def _donde(gen):
        while getattr(gen, "gi_yieldfrom", None) is not None and hasattr(gen.gi_yieldfrom, "gi_frame"):
            gen = gen.gi_yieldfrom
        f = getattr(gen, "gi_frame", None)
        return (f.f_code.co_filename.rsplit("/", 1)[-1], f.f_code.co_name, f.f_lineno) if f is not None else None

    def _terminar(self, clave, nivel, resultado):
        self.tiempos[nivel].append(self._t_tarea)
        self.construidos[nivel] += 1
        self.niveles.setdefault(clave, {})[nivel] = resultado
        if nivel == 0 and 1 in self.niveles[clave]:
            self._por_soltar.append((clave, 1))             # el LOD0 ya tapa al LOD1
        if nivel == 1 and clave in self._degradar:
            self._degradar.discard(clave)
            if 0 in self.niveles[clave]:
                self._por_soltar.append((clave, 0))
        self._sucio_camara = True

    def _soltar(self, maximo=MAX_SOLTAR_POR_FRAME):
        for _ in range(min(maximo, len(self._por_soltar))):
            clave, nivel = self._por_soltar.pop(0)
            n = self.niveles.get(clave, {}).pop(nivel, None)
            if n is not None:
                n.destruir()
            if not self.niveles.get(clave):
                self.niveles.pop(clave, None)
            self._sucio_camara = True

    def _actualizar_camara(self, foco):
        cajas = list(self.cajas_fijas)
        for clave, v in self.niveles.items():
            n = v.get(0)
            if n is None:
                continue
            caja = self.limites[clave]
            if calc.distancia_a_caja(foco[0], foco[1], caja) <= RADIO_CAMARA:
                cajas.extend(n.cajas_camara)
        self.obstaculos_camara[:] = cajas
        self._sucio_camara = False

    def update(self):
        if self.pausado:
            return
        foco = self._leer_foco()
        dt = max(1e-4, time.dt)
        if self._foco is not None:
            vx, vz = (foco[0] - self._foco[0]) / dt, (foco[1] - self._foco[1]) / dt
            k = min(1.0, 4.0 * dt)
            self._velocidad = (self._velocidad[0] + (vx - self._velocidad[0]) * k, self._velocidad[1] + (vz - self._velocidad[1]) * k)
        self._foco = foco
        self._frames += 1
        if (self._foco_plan is None or self._frames % CADA_N_FRAMES_PLAN == 0
                or math.hypot(foco[0] - self._foco_plan[0], foco[1] - self._foco_plan[1]) > MOVIMIENTO_REPLAN):
            self._replanificar(foco)
        self._soltar()
        t0 = reloj.perf_counter()
        presupuesto = self._presupuesto() / 1000.0
        while reloj.perf_counter() - t0 < presupuesto:
            if not self._avanzar():
                break
        if self._sucio_camara:
            self._actualizar_camara(foco)

    # ms de este frame para construir: PRESUPUESTO_MS normal; PRESUPUESTO_URGENTE_MS si falta un chunk LOD0 pegado al jugador
    # (un hueco bajo los pies es peor que un frame de 9 ms) o la cola se acumula.
    def _presupuesto(self):
        if self._cola:
            primero = self._cola[0]
            if primero[2] == 0 and primero[0] < mundo_config.RADIO_URGENTE:
                return mundo_config.PRESUPUESTO_URGENTE_MS
        elif self._tarea is not None and self._tarea[1] == 0:
            d = calc.distancia_a_caja(self._foco[0], self._foco[1], self.limites[self._tarea[0]]) if self._foco else 1e9
            if d < mundo_config.RADIO_URGENTE:
                return mundo_config.PRESUPUESTO_URGENTE_MS
        if len(self._cola) > mundo_config.COLA_LARGA:
            return mundo_config.PRESUPUESTO_URGENTE_MS
        return mundo_config.PRESUPUESTO_MS

    # -- Construcción síncrona (arranque, pruebas) --

    def pendientes(self):
        return len(self._cola) + (1 if self._tarea is not None else 0)

    def construir_anillo(self, foco, radio0, radio1=None, progreso=None):
        """Construye YA (sin presupuesto) los chunks LOD0 a menos de `radio0` m y los LOD1 hasta `radio1` (None = solo LOD0).
        `progreso(fraccion, texto)` se llama tras cada chunk. Devuelve cuántos construyó."""
        self._foco = foco
        r1 = radio1 if radio1 is not None else radio0
        construir, _, _ = self.planificar([foco], radio0, r1)
        # el adelanto de carga ya se cuenta en el plan: aquí queremos el radio pedido, así que se filtra por distancia
        cola = [(p, c, n) for p, c, n in construir
                if (n == 0 and calc.distancia_a_caja(foco[0], foco[1], self.limites[c]) <= radio0)
                or (n == 1 and radio1 is not None)]
        total = len(cola)
        for k, (_, clave, nivel) in enumerate(cola):
            if nivel in self.niveles.get(clave, {}):
                continue
            gen = self._tarea_nueva(clave, nivel)
            self._t_tarea = 0.0
            try:
                while True:
                    t0 = reloj.perf_counter()
                    next(gen)
                    self._t_tarea += reloj.perf_counter() - t0
            except StopIteration as fin:
                self._t_tarea += reloj.perf_counter() - t0
                self._terminar(clave, nivel, fin.value)
            if progreso is not None:
                progreso((k + 1) / total, "Chunk %d de %d" % (k + 1, total))
        self._soltar(10 ** 6)
        self._actualizar_camara(foco)
        return total

    def estadisticas(self):
        n0 = sum(1 for v in self.niveles.values() if 0 in v)
        n1 = sum(1 for v in self.niveles.values() if 1 in v)
        draws = sum(n.draws for v in self.niveles.values() for n in v.values())
        vertices = sum(n.vertices for v in self.niveles.values() for n in v.values())
        return {"lod0": n0, "lod1": n1, "pendientes": self.pendientes(), "draws": draws, "vertices": vertices,
                "construidos": dict(self.construidos), "max_paso_ms": round(self.max_paso_ms, 2), "peor_paso": self.peor_paso}

    def liberar_todo(self):
        self._tarea = None
        self._cola = []
        for v in self.niveles.values():
            for n in v.values():
                n.destruir()
        self.niveles.clear()
        self._por_soltar.clear()
        self.obstaculos_camara[:] = list(self.cajas_fijas)


# -- La ciudad ----------------------------------------------------------------------------------------------------------


FACHADAS_COMERCIO = True        # fachadas de los edificios de comercio (frontend/fachadas_comercio.py); False = las de siempre


class CiudadGrande(Entity):

    # Los métodos de Ciudad3D que sirven tal cual (edificios jugables con modelo, puertas, letreros): se reutilizan sin copiarlos.
    _construir_edificios = Ciudad3D._construir_edificios
    _modelo_del_edificio = Ciudad3D._modelo_del_edificio
    _contorno_de_edificio = Ciudad3D._contorno_de_edificio
    _collider_camara = Ciudad3D._collider_camara
    _letrero = Ciudad3D._letrero
    cerrar_puertas = Ciudad3D.cerrar_puertas

    fin_niebla = mundo_config.FIN_NIEBLA_GRANDE
    plano_lejano = mundo_config.PLANO_LEJANO_GRANDE

    def __init__(self, mundo, sombras=SOMBRAS, progreso=None, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self._mundo = mundo
        self._suelo = mundo.altura
        self._sombras = sombras
        self._hornear_sombras = False
        self.sombras_locales = None
        self._puertas_horneadas = None
        self.puertas = {}
        self.letreros = {}
        self.banderas = {}
        self._contornos = []
        self.raiz_colisiones = Entity(parent=self)
        self._modelos = Entity(parent=self)
        self._raiz_edificios = self._modelos
        self._grupos = {}
        self.obstaculos_camara = []
        self._progreso = progreso or (lambda f, t: None)
        self._paso = 0.0

        self._avance(0.00, "Cielo y luces")
        self.cielo = CieloDegradado(parent=self)
        self.luz = DirectionalLight(parent=self, shadows=False, shadow_map_resolution=RESOLUCION_SOMBRAS,
                                    color=rgb_luz(COLOR_LUZ_SOL))
        self.luz.look_at(DIRECCION_SOL)
        self.ambiente = AmbientLight(parent=self, color=rgb_luz(COLOR_LUZ_AMBIENTE))

        self._avance(0.05, "Suelo")
        self.campo = CampoSuelo(mundo)
        self.textura_grano = textura_del_grano()
        self.textura_camino = textura_del_camino()
        self._fondo()
        self._avance(0.25, "Plazas")
        self._plazas()
        self._avance(0.40, "Edificios")
        if any(not e.modelo for e in mundo.edificios()):
            raise ValueError("CiudadGrande: todos los edificios jugables deben tener modelo 3D.")
        self._construir_edificios()
        for cartel, posicion, giro, escala in letreros_secretos(mundo):
            silenciar(Text(cartel, parent=self, origin=(0, 0), position=posicion, rotation_y=giro, scale=escala,
                           color=rgb(estilo.TINTA)))
        for hijo in self.children:
            if hijo is not self.cielo:
                silenciar(hijo)
        for contorno in self._contornos:
            contorno.hide(MASCARA_LUZ)
        self.banderas = crear_banderas(mundo.edificios(), self)
        self.fachadas = None
        if FACHADAS_COMERCIO:                      # F9: toldos, postes y cruces fundidos en UNA malla (frontend/fachadas_comercio.py)
            try:
                from frontend import fachadas_comercio
                self.fachadas = fachadas_comercio.instalar(self, mundo)
            except Exception as error:             # decoración: nunca impide abrir el mundo
                print(f"[fachadas] no se pudieron instalar: {error}")
        self._avance(0.55, "Texturas de las casas")
        self.fabrica = FabricaCasas()
        n_tex = 0
        for _ in self.fabrica.precalentar():
            n_tex += 1
            self._avance(0.55 + 0.15 * min(1.0, n_tex / 30), "Texturas de las casas")
        self._avance(0.72, "Escaleras")
        self.ctx = ContextoObjetos(mundo)
        self.gestor = GestorChunks(self, mundo, self.campo, self.fabrica, self.ctx)
        self.gestor.cajas_fijas = [cc.obstaculo_caja(e.cx, e.cz, e.ancho, e.fondo, e.y, e.y + e.alto) for e in mundo.edificios()]
        self.gestor.obstaculos_camara = self.obstaculos_camara
        self.obstaculos_camara[:] = list(self.gestor.cajas_fijas)
        self._avance(0.80, "Listo")
        for e in scene.entities:                       # las Entity con luz de la ciudad (edificios, fondo, plazas): sin 16 lecturas
            if es_shader_de_luz(e.shader) and e.has_ancestor(self):
                if e.shader is lit_with_shadows_shader:        # los edificios jugables nacen con el de Ursina: F6 les da el local
                    e.shader = shader_de_ciudad()
                e.set_shader_input("shadow_samples", MUESTRAS_SOMBRA)
        if sombras:
            self._sombras_vacias()
        self.encender_luces(False)

    def _avance(self, fraccion, texto):
        self._progreso(fraccion, texto)

    # El fondo de terreno de todo el mapa (una malla a 8 m, 0,6 m bajo el terreno real).
    def _fondo(self):
        gen = malla_fondo(self._mundo.terreno, self.campo)
        try:
            while True:
                next(gen)
        except StopIteration as fin:
            datos = fin.value
        nodo = None
        g = escribir_geom("fondo", datos.vertices, datos.normales, datos.colores, datos.triangulos, datos.uvs, tanda=10 ** 9)
        try:
            while True:
                next(g)
        except StopIteration as fin:
            nodo = fin.value
        self.fondo = Entity(parent=self, shader=shader_de_ciudad(), name="fondo_terreno")
        n = NodePath(nodo)
        n.set_texture(self.textura_grano._texture)
        n.set_two_sided(True)
        n.hide(MASCARA_LUZ)
        n.reparent_to(self.fondo)
        silenciar(self.fondo)

    def _plazas(self):
        acum = Acumulador()
        for _ in plazas_globales(acum, self._mundo):
            pass
        g = acum.volcar_a_geom("plazas", tanda=10 ** 9)
        try:
            while True:
                next(g)
        except StopIteration as fin:
            nodo = fin.value
        self.plazas = Entity(parent=self, shader=shader_de_ciudad(), name="plazas")
        n = NodePath(nodo)
        n.hide(MASCARA_LUZ)
        n.reparent_to(self.plazas)
        silenciar(self.plazas)

    # Sombras (plan B de F5): el mapa de sombras queda vacío, así todo se ve iluminado. F6 lo llenará con las sombras locales.
    def _sombras_vacias(self):
        vacio = NodePath("sin_sombras")
        self.luz.shadows = True
        self.luz.update_bounds(self.fondo)
        self.luz._light.set_scene(vacio)
        rendimiento.agregar_raiz(vacio)
        self.sombras_locales = SombrasLocales(self)           # F6: si el shader local existe, llena el mapa alrededor del jugador

    def encender_luces(self, encendidas):
        encender_luz(self.luz, encendidas)
        encender_luz(self.ambiente, encendidas)
        self._hornear_sombras = encendidas and self._sombras
        if self.sombras_locales is not None:
            self.sombras_locales.apagar()                      # al encender o apagar: se vuelve a hornear desde cero
        self.gestor.pausado = not encendidas

    def update(self):
        self.cielo.world_position = camera.world_position       # el domo acompaña a la cámara (el mapa mide ~900 m)
        for bandera in self.banderas.values():
            bandera.animar(time.dt)
        if not self._sombras:
            return
        if self.sombras_locales is not None and self.sombras_locales.activas:
            self.sombras_locales.actualizar(self.gestor._leer_foco())
            return
        if self._hornear_sombras:
            buffer = self.luz._light.get_shadow_buffer(__import__("ursina").application.base.win.gsg)
            if buffer is not None:
                buffer.set_one_shot(True)
                self._hornear_sombras = False

    # -- Interfaz con la escena --

    def enlazar_escena(self, escena):
        """La escena da el foco (posición del jugador activo) y recibe la lista de cajas de cámara."""
        self.gestor.fuente_foco = escena._posicion_del_activo
        escena.camara.obstaculos = self.obstaculos_camara

    def preparar_anillo(self, foco=None, radio=None, con_barra=True):
        """Construye el anillo de arranque alrededor del foco con barra de progreso. Devuelve los chunks construidos."""
        if foco is None:
            foco = self.gestor._leer_foco()
        radio = mundo_config.RADIO_ARRANQUE if radio is None else radio
        barra = None
        progreso = None
        if con_barra:
            from frontend.barra_carga import BarraCarga
            barra = BarraCarga("Cargando el barrio...")
            progreso = barra.actualizar
        try:
            return self.gestor.construir_anillo(foco, radio, None, progreso)
        finally:
            if barra is not None:
                barra.cerrar()


def crear_ciudad_grande(mundo, sombras=SOMBRAS, con_barra=True, **opciones):
    """CiudadGrande con barra de progreso durante su construcción (la ciudad es lo que más tarda al arrancar)."""
    barra = None
    progreso = None
    if con_barra:
        from frontend.barra_carga import BarraCarga
        barra = BarraCarga("Preparando el mapa grande...")
        progreso = barra.actualizar
    try:
        return CiudadGrande(mundo, sombras=sombras, progreso=progreso, **opciones)
    finally:
        if barra is not None:
            barra.cerrar()

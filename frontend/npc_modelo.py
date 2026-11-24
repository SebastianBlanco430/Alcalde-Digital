# NPC (peatones) con el mismo modelo que los personajes principales: cada uno es una copia de uno de los 4 .glb
# (periodista, smoking, brasileña, ciudadano) con otra ropa, otro tono de piel, su cara por código (rasgos del
# peatón), a veces una mochila, y su propia escala y fase de animación. Es un PersonajeModelo (misma API que
# Personaje), así que frontend/peatones.py lo mueve igual que antes.
#
# No hay Blender instalado: la ropa se cambia en Panda3D reescribiendo el color de vértice de las piezas de la
# copia del Actor (frontend/npc_color.py); el .glb original y los personajes principales no cambian. El casco
# de tinta, el pelo del modelo y las bandas de luz se conservan. Cada modelo se carga UNA vez (caché de
# personaje_modelo._bases) y cada NPC es una copia.
#
# Desde 2026-11 hay además cinco modelos nuevos (npc_hombre_01..03, npc_mujer_01..02): el plan los marca con "nuevo" y
# su carga y su recolor van en frontend/npc_nuevos_modelo.py. Todos los NPC tienen postura emocional y anclajes
# (aplicar_postura, ancla_cabeza, ancla_muneca; frontend/npc_postura.py).

import sys
import zlib

from ursina import camera, time
from panda3d.core import Mat4, Vec3, CS_zup_right, getDefaultCoordinateSystem

from frontend import casco_pantalla
from frontend import modelo_calculos as mc
from frontend import npc_calculos as nc
from frontend import npc_nuevos_calculos as nn
from frontend import npc_nuevos_modelo as nnm
from frontend import npc_postura
from frontend import rostro_calculos as rc
from frontend import toon_duro_calculos as tdc
from frontend.npc_color import agregar_camiseta, recolorear_actor
from frontend.personaje import Personaje
from frontend.personaje_modelo import PersonajeModelo, _cargar_actor
from frontend.rostro_modelo import _armar, colocar_rostro_animado_piezas

_avisados = set()


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[assets] NPC: {motivo}.", file=sys.stderr)


# Piezas de una mochila (ejes del glb crudo, centradas en el origen): cuerpo, solapa, bolsillo y dos tirantes.
def piezas_mochila(color):
    oscuro = tuple(c * 0.7 for c in color)
    c = rc.GROSOR_CONTORNO
    return [rc._pieza("mochila_cuerpo", "caja", (0.0, 0.0, 0.0), (0.105, 0.065, 0.15), color, contorno=c),
            rc._pieza("mochila_solapa", "caja", (0.0, 0.004, 0.115), (0.108, 0.068, 0.045), oscuro, contorno=c),
            rc._pieza("mochila_bolsillo", "caja", (0.0, 0.07, -0.05), (0.07, 0.022, 0.07), oscuro, contorno=c),
            rc._pieza("tirante_-1", "caja", (-0.075, -0.075, 0.03), (0.018, 0.012, 0.12), oscuro),
            rc._pieza("tirante_1", "caja", (0.075, -0.075, 0.03), (0.018, 0.012, 0.12), oscuro)]


class PersonajeNPC(PersonajeModelo):

    def __init__(self, nombre, plan, aspecto, rasgos, **opciones):
        # Estos datos los usan los ganchos que PersonajeModelo.__init__ llama; van antes de crear la Entity.
        self._plan = plan
        self._aspecto = aspecto
        self._rasgos = nc.rasgos_para_modelo(plan["archivo"], rasgos)
        super().__init__(nombre, plan["rol"], **opciones)
        self._poner_mochila()
        self._congelado = False       # cuerpo congelado por estar lejos de la cámara
        self._cerca = True            # ¿está lo bastante cerca de la cámara para animarle la cara?
        self._t_lod = plan["fase"] * nc.INTERVALO_LOD
        self._postura = npc_postura.instalar(self)    # posturas emocionales (None si el modelo no trae esas variantes)

    # Copia del Actor del rol con la ropa y la piel del plan.
    def _crear_actor(self, rol):
        if self._plan.get("nuevo"):       # npc_hombre_*/npc_mujer_*: carga, clips y recolor propios (npc_nuevos_modelo.py)
            actor = nnm.crear_actor(self._plan)
            self._poner_corbata(actor)    # antes del skinning en la GPU (toon duro): la corbata es parte de la malla
            return actor
        actor = npc_postura.cargar_actor_de_siempre(rol) or _cargar_actor(rol)     # con variantes de postura si se puede
        try:
            recolorear_actor(actor, nc.objetivos_recolor(self._plan))
            tipo = self._plan.get("camiseta_nueva")
            if tipo:
                agregar_camiseta(actor, self._plan["colores"]["camiseta"], nc.huesos_camiseta(tipo), nc.GROSOR_CAMISETA)
        except Exception as error:
            _avisar(f"no se pudo recolorear {self._plan['archivo']} ({error})")
        return actor

    # T5: toon duro solo en los modelos nuevos (color plano + bandas horneadas); las copias de los 4 .glb, no. Los .glb v2
    # del elenco entran por la misma ruta (color plano + bandas horneadas al cargar).
    def _toon_duro(self):
        return bool(self._plan.get("nuevo")) and (bool(self._plan.get("v2"))
                                                  or tdc.usa_toon_duro(self._plan.get("archivo")))

    # T2: casco de tinta de grosor ~constante en pantalla en los modelos nuevos (los únicos con casco inflado por normal).
    def _casco_pantalla(self):
        if self._plan.get("nuevo") and nnm.CONTORNO:
            casco_pantalla.aplicar_actor(self.actor, nn.GROSOR_CONTORNO)

    def _escala_modelo(self, rol):
        return self._plan.get("escala_base", mc.escala_para_rol(rol)) * self._plan["escala"]

    # Cara por código con los rasgos del peatón (peinado, gafas, gorra...), ajustada a la cabeza del modelo.
    def _poner_rostro(self, rol, nombre):
        rol = self._plan.get("rol_rostro", rol)       # los modelos nuevos usan la cabeza de un modelo conocido
        descriptor = rc.descriptor_peaton(self._rasgos, self._aspecto["piel"], self._aspecto["pelo"])
        piezas = rc.piezas_rostro(descriptor)
        if rol in rc.AJUSTE_ROSTRO_POR_ROL:
            piezas = rc.ajustar_piezas(piezas, *rc.AJUSTE_ROSTRO_POR_ROL[rol])
        if self._plan.get("ajuste_rostro"):          # elenco v2: encaje fino de la cara en una cabeza nueva (rostro_v2.ajuste)
            piezas = rc.ajustar_piezas(piezas, *self._plan["ajuste_rostro"])
        return colocar_rostro_animado_piezas(self.actor, rol, piezas, zlib.crc32(nombre.encode()))

    # Cada NPC arranca su ciclo en un punto distinto para no ir todos al compás.
    def _iniciar_loop(self, clip):
        self.actor.loop(clip)
        control = self.actor.getAnimControl(clip)
        if control is not None and control.getNumFrames() > 1:
            control.pose(int(self._plan["fase"] * control.getNumFrames()) % control.getNumFrames())
            control.loop(False)

    # Fase (0..1) con la que arranca el ciclo de marcha de la animación humana (distinta por NPC).
    def _fase_marcha_inicial(self):
        return self._plan["fase"]

    # Cada INTERVALO_LOD s mira la distancia a la cámara: lejos se apaga la cara y se congela el cuerpo.
    # Devuelve si la cara se anima este frame.
    def _animar_rostro(self):
        self._t_lod -= time.dt
        if self._t_lod <= 0:
            self._t_lod = nc.INTERVALO_LOD
            try:
                distancia = (camera.world_position - self.world_position).length()
            except Exception:
                distancia = 0.0
            self._cerca = nc.rostro_activo(distancia)
            self._ajustar_cuerpo(nc.cuerpo_congelado(distancia))
        return self._cerca

    # Congela (velocidad 0: el esqueleto no se recalcula) o reanuda la animación de los clips activos. Mientras está
    # congelado se repite cada revisión por si un cambio de clip la reanudó.
    def _ajustar_cuerpo(self, congelar):
        if self.actor is None or (not congelar and not self._congelado):
            return
        if self._humano is not None:      # animación humana: el animador lleva las tasas de sus clips
            self._humano.congelar(congelar)
            self._congelado = congelar
            return
        try:
            for clip in list(self._pesos):
                velocidad = 0.0 if congelar else ((self._rate or 1.0) if clip == self._clip else 1.0)
                self.actor.setPlayRate(velocidad, clip)
            self._congelado = congelar
        except Exception as error:
            _avisar(f"no se pudo ajustar la animación del cuerpo ({error})")

    # -- Ganchos para la conducta: postura emocional y anclajes (frontend/npc_postura.py) --

    # Cambia la postura del cuerpo: 'sociable', 'neutro', 'aislado' (encorvado, cabeza gacha), 'celular' (cabeza gacha
    # y antebrazos al frente) o 'enojado'. Devuelve False si este modelo no la puede mostrar (queda como estaba).
    def aplicar_postura(self, estado):
        return npc_postura.aplicar(self, estado)

    def postura(self):
        return npc_postura.estado_de(self)

    # Entity sobre la cabeza (para globos de texto) y nodo en la muñeca ("i"/"d", para una manilla; None si no hay hueso).
    def ancla_cabeza(self):
        return npc_postura.ancla_cabeza(self)

    def ancla_muneca(self, lado="i"):
        return npc_postura.ancla_muneca(self, lado)

    # El cambio de postura avanza con la mezcla de clips (también durante las cinemáticas).
    def _mezclar(self, dt):
        super()._mezclar(dt)
        if getattr(self, "_postura", None) is not None:
            self._postura.avanzar(dt)

    # El ancla de la cabeza sube con los pies (ver PersonajeModelo._elevar).
    def _elevar(self):
        super()._elevar()
        ancla = getattr(self, "_ancla_cabeza", None)
        if ancla is not None:
            ancla.y = npc_postura.y_ancla_cabeza(self)

    # Mochila colgada del hueso de la espalda (si el plan trae una). Nunca lanza.
    def _poner_mochila(self):
        color = self._plan.get("mochila")
        if color is None:
            return
        try:
            hueso_nombre, centro = nn.espalda(self._plan) if self._plan.get("nuevo") else nc.ESPALDA_POR_ROL[self._plan["rol"]]
            hueso = self.actor.exposeJoint(None, "modelRoot", hueso_nombre)
            if hueso is None:
                return
            raiz = self.actor.attachNewNode("mochila")
            raiz.setMat(Mat4.translateMat(Vec3(*centro)) * Mat4.convertMat(CS_zup_right, getDefaultCoordinateSystem()))
            _armar(raiz, piezas_mochila(color), False)
            raiz.wrtReparentTo(hueso)
        except Exception as error:
            _avisar(f"no se pudo poner la mochila ({error})")

    # Camisa y corbata (personajes con nombre cuya receta la trae): pegadas a la malla con sus mismos huesos, así se
    # deforman con el pecho sentado y de pie (frontend/personajes_receta_calculos.py, corbata_en_malla). Nunca lanza.
    def _poner_corbata(self, actor):
        color = self._plan.get("corbata")
        if color is None:
            return
        try:
            poner_camisa(actor)
        except Exception as error:
            _avisar(f"no se pudo poner la corbata ({error})")


# Camisa en el escote (S1, retoques-personajes): los 12 triángulos de piel en V del pecho pasan a tener filas de vértice
# PROPIAS (copias con el mismo esqueleto y los mismos pesos) pintadas de blanco, dentro de la misma Geom del cuerpo. Se
# deforma exactamente igual que el pecho (sentado, de pie, con el skinning en la GPU) y no hay piezas que se crucen.
# Los tres cuerpos de hombre comparten topología (prc.ESCOTE_TRIANGULOS). Lanza si la malla no es la esperada.
def poner_camisa(actor):
    from panda3d.core import Geom, GeomTriangles, GeomVertexWriter, Thread
    from frontend import personajes_receta_calculos as prc
    for nodo in actor.findAllMatches("**/+GeomNode"):
        geom_node = nodo.node()
        if geom_node.getNumGeoms() == 0:
            continue
        origen = geom_node.getGeom(0)
        if origen.getVertexData().getTransformBlendTable() is None:
            continue
        triangulos = _triangulos(origen)
        if len(triangulos) != prc.TRIANGULOS_CUERPO_HOMBRE:
            raise ValueError(f"la malla {nodo.getName()} tiene {len(triangulos)} triángulos")
        geom = geom_node.modifyGeom(0)
        datos = geom.modifyVertexData()                   # la copia de este actor (no altera a las demás)
        n0 = datos.getNumRows()
        escote = prc.ESCOTE_TRIANGULOS
        datos.setNumRows(n0 + 3 * len(escote))
        hilo = Thread.getCurrentThread()
        fila = n0
        nuevos = {}
        for k in escote:
            filas = []
            for r in triangulos[k]:
                datos.copyRowFrom(fila, datos, r, hilo)  # mismo vértice, mismos huesos y pesos
                filas.append(fila)
                fila += 1
            nuevos[k] = tuple(filas)
        colores = GeomVertexWriter(datos, "color")       # después de copiar: un escritor anterior quedaría viejo
        colores.setRow(n0)
        for _ in range(3 * len(escote)):
            colores.setData4(*prc.CAMISA, 1.0)
        tris = GeomTriangles(Geom.UHStatic)
        for k, tri in enumerate(triangulos):
            tris.addVertices(*nuevos.get(k, tri))
        tris.closePrimitive()
        geom.clearPrimitives()
        geom.addPrimitive(tris)
        return len(escote)
    raise ValueError("la malla no tiene esqueleto")


def _triangulos(geom):
    salida = []
    for primitiva in geom.getPrimitives():
        primitiva = primitiva.decompose()
        v = [primitiva.getVertex(i) for i in range(primitiva.getNumVertices())]
        salida += [tuple(v[t:t + 3]) for t in range(0, len(v) - 2, 3)]
    return salida


# Fábrica: PersonajeNPC del peatón `indice`; si algo falla devuelve el muñeco procedural de siempre.
# `color_ropa` solo lo usa el respaldo procedural.
# `nombre` (opcional): nombre visible del NPC; con NOMBRES_POR_GENERO su modelo pasa a ser de su género
# (frontend/npc_genero_calculos.py). None = como siempre.
def crear_npc(indice, semilla, aspecto, rasgos, color_ropa, nombre=None, personaje=None, **opciones):
    if rasgos and rasgos.get("capucha"):     # NPC de etapa con capucha: con el elenco v2, v2/etapa_capucha.glb
        npc = _crear_etapa_capucha(indice, semilla, aspecto, rasgos, nombre, **opciones)
        if npc is not None:
            return npc
    receta = _receta(personaje, nombre)
    if receta is not None:          # personaje con nombre: el mismo que en la Fiscalía (backend/datos/personajes_fiscalia.json)
        # solo_v2 (Arenas): sin su malla v2 sale como siempre (la fábrica de siempre, más abajo)
        npc = crear_v2(receta, **opciones) if receta.solo_v2 else crear_desde_receta(receta, **opciones)
        if npc is not None:
            return npc
    try:
        from frontend import npc_genero_calculos as ng
        plan = nc.plan_npc(indice, semilla, aspecto)
        if nombre:
            forzado = ng.modelo_para_nombre(indice, semilla, nombre, plan["archivo"])
            if forzado is not None:
                plan = nc.plan_npc(indice, semilla, aspecto, modelo=forzado)
        if plan.get("nuevo") and not nnm.disponible(plan):      # modelo nuevo que no carga: uno de los 4 de siempre
            plan = nc.plan_npc(indice, semilla, aspecto,
                               modelo=ng.modelo_de_respaldo(nc.modelo_npc(indice, semilla), indice, nc.MODELOS_NPC))
        return PersonajeNPC(ng.nombre_para_npc(indice, semilla, plan["archivo"]), plan, aspecto, rasgos, **opciones)
    except Exception as error:
        _avisar(f"peatón {indice}: no se pudo crear el modelo ({error}); se usa el muñeco procedural")
        return Personaje("", color_ropa, apariencia=dict(aspecto, rasgos=rasgos, piel_rgb=aspecto["piel"],
                                                          pelo_rgb=aspecto["pelo"]), **opciones)


def _receta(personaje, nombre):
    try:
        from backend.datos import personajes_loader as pl
        return pl.por_id(personaje) if personaje else pl.por_nombre(nombre)
    except Exception as error:      # noqa: BLE001  fuente rota: el NPC sale como antes
        _avisar(f"fuente de personajes: {error}")
        return None


# Elenco v2 (sesión F): PersonajeNPC con la malla propia del personaje (v2/<id>.glb), si ALCALDE_ELENCO_V2 está activa
# y el .glb existe y carga; si no, None (con un aviso UNA vez por stderr) y quien llama usa la receta de hoy.
def crear_v2(receta, **opciones):
    from backend.logica import modelos_v2 as mv2
    from frontend import personajes_receta_calculos as prc
    plan = prc.elegir_v2(receta)
    if plan is None:
        return None
    if not nnm.disponible(plan):
        mv2.avisar_una_vez(f"elenco:{receta.id}", f"{receta.nombre}: {receta.glb_v2} no carga; se usa su receta de hoy.")
        return None
    try:
        return PersonajeNPC(receta.nombre, plan, prc.aspecto_v2(receta), prc.rasgos_v2(receta), **opciones)
    except Exception as error:      # noqa: BLE001
        mv2.avisar_una_vez(f"elenco:{receta.id}", f"{receta.nombre}: no se pudo crear con {receta.glb_v2} ({error}); "
                                                  "se usa su receta de hoy.")
        return None


# NPC de etapa con capucha (Raponero, Jíbaro, Extorsionador) con v2/etapa_capucha.glb: la capucha va en la malla (sin los
# elipsoides de rostro_calculos.capucha) y solo su piel se recolorea. None = sin elenco v2 o sin el .glb (aviso UNA vez):
# sale de la fábrica de siempre con la capucha por código.
def _crear_etapa_capucha(indice, semilla, aspecto, rasgos, nombre, **opciones):
    from backend.logica import modelos_v2 as mv2
    from frontend import personajes_receta_calculos as prc
    try:
        plan = prc.plan_etapa_capucha(indice, semilla, aspecto)
        if plan is None:
            return None
        if not nnm.disponible(plan):
            mv2.avisar_una_vez("elenco:etapa_capucha", f"{prc.ETAPA_CAPUCHA} no carga; se usa la capucha por código.")
            return None
        return PersonajeNPC(nombre or "", plan, aspecto, prc.rasgos_etapa_capucha(rasgos), **opciones)
    except Exception as error:      # noqa: BLE001
        mv2.avisar_una_vez("elenco:etapa_capucha", f"NPC de etapa con capucha: {error}; se usa la capucha por código.")
        return None


# Carga (elenco v2): prepara una vez la base de v2/etapa_capucha.glb (la comparten los 3 NPC de etapa con capucha) para que
# no se prepare en un frame de juego. True si quedó lista; False sin elenco v2, sin el .glb o si no carga (avisa una vez).
def precargar_etapa_capucha():
    from frontend import personajes_receta_calculos as prc
    plan = prc.plan_etapa_capucha(0, 0, {"piel": (180, 130, 100), "pelo": (40, 30, 30), "pantalon": (40, 40, 50)})
    return plan is not None and nnm.disponible(plan)


# PersonajeNPC de un personaje con nombre hecho con su receta (fuente única). Con el elenco v2, su malla propia (crear_v2).
# Si no, o si no carga, su receta de hoy: si su cuerpo no carga prueba los otros de su género y, como último recurso, el
# cuerpo de emergencia (visible, con aviso por stderr). None si nada carga.
def crear_desde_receta(receta, **opciones):
    from frontend import personajes_receta_calculos as prc
    npc = crear_v2(receta, **opciones)
    if npc is not None:
        return npc
    rasgos = prc.rasgos(receta)
    aspecto = prc.aspecto(receta)
    cuerpos = [receta.cuerpo] + prc.respaldos(receta)
    for cuerpo in cuerpos:
        plan = prc.plan(receta, cuerpo)
        if not nnm.disponible(plan):
            continue
        try:
            if cuerpo != receta.cuerpo:
                _avisar(f"{receta.nombre}: {receta.cuerpo} no carga; se usa {cuerpo} (respaldo)")
            return PersonajeNPC(receta.nombre, plan, aspecto, rasgos, **opciones)
        except Exception as error:      # noqa: BLE001
            _avisar(f"{receta.nombre}: no se pudo crear con {cuerpo} ({error})")
    try:
        archivo, rol = prc.CUERPO_EMERGENCIA
        s = prc.semilla(receta)
        plan = nc.plan_npc(s, s, aspecto, modelo=(archivo, rol))
        hoy = prc.colores_hoy(receta)
        plan["colores"]["camiseta"] = tuple(c / 255 for c in hoy["camiseta"])
        plan["colores"]["pantalon"] = tuple(c / 255 for c in hoy["pantalon"])
        plan["mochila"] = None
        plan["escala"] = 1.0
        _avisar(f"{receta.nombre}: ningún cuerpo de NPC carga; se usa el de emergencia ({archivo})")
        return PersonajeNPC(receta.nombre, plan, aspecto, rasgos, **opciones)
    except Exception as error:          # noqa: BLE001
        _avisar(f"{receta.nombre}: tampoco carga el cuerpo de emergencia ({error})")
        return None


# Argumentos extra para pasar el nombre a una fábrica de NPC: solo la de siempre (crear_npc) lo acepta; una fábrica
# propia (pruebas) recibe la llamada de antes.
def con_nombre(fabrica, nombre):
    return {"nombre": nombre} if fabrica is crear_npc and nombre else {}

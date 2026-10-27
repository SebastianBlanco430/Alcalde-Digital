# Animación humana de los personajes con modelo .glb (parte Panda3D; la matemática está en
# frontend/animacion_humana_calculos.py).
#
# Por qué: los clips del .glb (Caminar 29 fotogramas, Correr 19) se reproducían a 2x para igualar la velocidad del
# juego (4.8 y 8.5 m/s, que son un trote y una carrera) y las piernas patinaban en una zancada diminuta.
# Qué hace: al cargar cada modelo HORNEA clips nuevos con la cinemática humana (marcha a 6 velocidades, subir
# escalón y poses de salto) como AnimBundle en memoria, sobre el MISMO esqueleto, y los añade al nodo antes de crear
# el Actor. Así Panda los reproduce y mezcla en C++ (cero coste por hueso en Python durante el juego):
#   - hornear_clips(): FK propia del esqueleto (Rigify "DEF-*" o tipo Mixamo) -> una tabla h,p,r,x,y,z por hueso;
#   - AnimadorHumano: elige y mezcla los clips cada frame según la velocidad REAL (cadencia = v / largo de ciclo,
#     por eso los pies no patinan), reposo con el clip Idle original, escalón y salto.
# Los clips originales (Idle, Saludar, Hablar) no se tocan. Si el esqueleto no se reconoce o algo falla, no se
# añade nada y el personaje se anima como antes (la bandera ANIMACION_HUMANA de personaje_modelo.py lo desactiva).

import math
import sys

from panda3d.core import (AnimBundle, AnimBundleNode, AnimChannelMatrixXfmTable, AnimGroup, CharacterJoint,
                          LMatrix3, LMatrix4, LVecBase3, PTA_stdfloat, decompose_matrix)

from frontend import animacion_humana_calculos as ac

FOTOGRAMAS = 24                  # fotogramas por ciclo de marcha
FPS = 30.0
PREFIJO_MARCHA = "HumMarcha"
CLIP_ESCALON = "HumEscalon"
CLIPS_SALTO = {"impulso": "HumImpulso", "ascenso": "HumAscenso", "caida": "HumCaida", "aterrizaje": "HumAterrizaje"}
CLIPS_GESTO = {"dar": "HumEntregar", "recibir": "HumRecibir"}     # poses de 1 fotograma (traspaso de mano a mano)
NOMBRES_MARCHA = tuple(f"{PREFIJO_MARCHA}{i}" for i in range(len(ac.VELS)))
TIEMPO_MEZCLA = 0.14             # s para cambiar de clip
TIEMPO_GESTO = 0.32              # s para entrar y SALIR de Saludar/Hablar (cambio de pose grande: más suave)
SUAVIZADO_VELOCIDAD = 8.0        # 1/s: la velocidad real (con ruido de colisiones) se suaviza antes de elegir clip

IDLE, CAMINAR, CORRER, SALUDAR, HABLAR = "Idle", "Caminar", "Correr", "Saludar", "Hablar"

_avisados = set()


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[assets] animación humana: {motivo}.", file=sys.stderr)


# -- Descripción de los dos tipos de esqueleto conocidos --

def _tipo_esqueleto(nombres):
    if "DEF-spine" in nombres and "DEF-thigh.L" in nombres:
        return {"zonas": {"pelvis": ["DEF-spine"], "lumbar": ["DEF-spine.001", "DEF-spine.002"],
                          "pecho": ["DEF-spine.003"], "cuello": ["DEF-spine.004", "DEF-spine.005"],
                          "cabeza": ["DEF-spine.006"]},
                "miembro": {"muslo": "DEF-thigh.%s", "pierna": "DEF-shin.%s", "pie": "DEF-foot.%s", "dedos": "DEF-toe.%s",
                            "brazo": "DEF-upper_arm.%s", "antebrazo": "DEF-forearm.%s", "mano": "DEF-hand.%s"},
                "virtual": {"muslo": "DEF-spine", "brazo": "DEF-shoulder.%s", "pelvis": "DEF-spine",
                            "pecho": "DEF-spine.003", "cabeza": "DEF-spine.006"}}
    if "Hips" in nombres and "thigh.L" in nombres:
        return {"zonas": {"pelvis": ["Hips"], "lumbar": ["Spine"], "pecho": ["Spine2", "Spine3"],
                          "cuello": ["Neck", "Neck2"], "cabeza": ["Head"]},
                "miembro": {"muslo": "thigh.%s", "pierna": "shin.%s", "pie": "foot.%s", "dedos": "toe.%s",
                            "brazo": "upper_arm.%s", "antebrazo": "forearm.%s", "mano": "hand.%s"},
                "virtual": {"muslo": "Hips", "brazo": "Spine3", "pelvis": "Hips", "pecho": "Spine3", "cabeza": "Head"}}
    return None


# -- Álgebra con matrices de Panda (convención de FILAS: mundo = local * mundo_padre) --

def _a_lmat3(r):
    # r: rotación 3x3 de columnas (v' = R v) -> LMatrix3 de filas (v' = v * M, M = R^T)
    return LMatrix3(r[0][0], r[1][0], r[2][0], r[0][1], r[1][1], r[2][1], r[0][2], r[1][2], r[2][2])


def _vec(v):
    return LVecBase3(v[0], v[1], v[2])


def _tup(v):
    return (v[0], v[1], v[2])


class Esqueleto:
    # Lee del Character del modelo las transformaciones por defecto (posición de reposo), el árbol de huesos y el
    # primer fotograma del clip Idle (dedos relajados), y mide la base del cuerpo.
    def __init__(self, personaje_np):
        self.cuerpo = personaje_np.node().getBundle(0)
        self.orden, self.padre, self.hijos = [], {}, {}
        self.local_rep, self.mundo_rep = {}, {}
        self._recorrer(self.cuerpo, None, None)
        self.tipo = _tipo_esqueleto(set(self.orden))
        self.local_idle = {}
        self._leer_idle(personaje_np)
        if self.tipo is None:
            raise ValueError("esqueleto no reconocido")
        self._medir()

    def _recorrer(self, grupo, nombre_padre, mundo_padre):
        for i in range(grupo.getNumChildren()):
            hijo = grupo.getChild(i)
            if not isinstance(hijo, CharacterJoint):
                self._recorrer(hijo, nombre_padre, mundo_padre)
                continue
            nombre = hijo.getName()
            local = LMatrix4(hijo.getDefaultValue())
            mundo = LMatrix4(local) if mundo_padre is None else local * mundo_padre
            self.orden.append(nombre)
            self.padre[nombre] = nombre_padre
            self.hijos.setdefault(nombre, [])
            if nombre_padre is not None:
                self.hijos[nombre_padre].append(nombre)
            self.local_rep[nombre] = local
            self.mundo_rep[nombre] = mundo
            self._recorrer(hijo, nombre, mundo)

    def _leer_idle(self, personaje_np):
        for nodo in personaje_np.findAllMatches("**/+AnimBundleNode"):
            banco = nodo.node().getBundle()
            if banco.getName() != IDLE:
                continue
            def rec(g):
                for i in range(g.getNumChildren()):
                    c = g.getChild(i)
                    if isinstance(c, AnimChannelMatrixXfmTable):
                        m = LMatrix4()
                        c.getValue(0, m)
                        self.local_idle[c.getName()] = m
                    rec(c)
            rec(banco)

    def pos_rep(self, nombre):
        return self.mundo_rep[nombre].getRow3(3)

    def _medir(self):
        miembro = self.tipo["miembro"]
        n = lambda clave, lado: miembro[clave] % lado
        cad_i, cad_d = self.pos_rep(n("muslo", "L")), self.pos_rep(n("muslo", "R"))
        rod_i, tob_i, dedos_i = self.pos_rep(n("pierna", "L")), self.pos_rep(n("pie", "L")), self.pos_rep(n("dedos", "L"))
        # arriba: de los tobillos a las caderas; izquierda: de la cadera derecha a la izquierda; adelante: tobillo -> dedos
        arriba = LVecBase3(cad_i + cad_d - tob_i - self.pos_rep(n("pie", "R")))
        arriba.normalize()
        izq = LVecBase3(cad_i - cad_d)
        izq -= arriba * izq.dot(arriba)
        izq.normalize()
        adel = LVecBase3(dedos_i - tob_i)
        adel -= arriba * adel.dot(arriba)
        adel -= izq * adel.dot(izq)
        adel.normalize()
        self.base = (_tup(adel), _tup(izq), _tup(arriba))          # columnas de M: cuerpo -> modelo
        pivote = self.pos_rep(self.tipo["zonas"]["pelvis"][0])
        self.origen = LVecBase3(pivote - arriba * pivote.dot(arriba))
        self.base_mat = tuple(tuple(self.base[j][i] for j in range(3)) for i in range(3))   # M[i][j] = base[j][i]

    # modelo -> cuerpo y cuerpo -> modelo
    def a_cuerpo(self, p):
        d = LVecBase3(p - self.origen)
        return tuple(d.dot(_vec(self.base[j])) for j in range(3))

    def vec_a_modelo(self, v):
        return tuple(sum(self.base[j][i] * v[j] for j in range(3)) for i in range(3))

    def rot_a_modelo(self, r):
        # R_modelo = M R M^T (columnas)
        m = self.base_mat
        mt = tuple(tuple(m[j][i] for j in range(3)) for i in range(3))
        return ac.mat_por_mat(m, ac.mat_por_mat(r, mt))

    def medidas(self):
        miembro = self.tipo["miembro"]
        n = lambda clave, lado: miembro[clave] % lado
        pivote = self.a_cuerpo(self.pos_rep(self.tipo["zonas"]["pelvis"][0]))
        cad_i, cad_d = (self.a_cuerpo(self.pos_rep(n("muslo", s))) for s in "LR")
        rod, tob = self.pos_rep(n("pierna", "L")), self.pos_rep(n("pie", "L"))
        ded = self.pos_rep(n("dedos", "L"))
        cad_pos = self.pos_rep(n("muslo", "L"))
        return ac.Medidas(pivote_pelvis=pivote, cadera_i=cad_i, cadera_d=cad_d,
                          largo_muslo=(rod - cad_pos).length(), largo_pierna=(tob - rod).length(),
                          altura_tobillo=self.a_cuerpo(tob)[2],
                          pie_adelante=max(0.05, (ded - tob).dot(_vec(self.base[0]))))


class Hornero:
    # Convierte una pose del cuerpo (ac.pose_*) en transformaciones locales de todos los huesos.
    def __init__(self, esq):
        self.e = esq
        t = esq.tipo
        self.zona_de = {}
        for zona, huesos in t["zonas"].items():
            for h in huesos:
                self.zona_de[h] = zona
        self.lados = {"L": "i", "R": "d"}
        self.explicito = {}      # hueso -> (clave, lado)
        for lado in "LR":
            for clave in ("muslo", "pierna", "pie", "dedos", "brazo", "antebrazo", "mano"):
                self.explicito[t["miembro"][clave] % lado] = (clave, lado)
        self.dir_rep = {}        # hueso -> dirección de reposo hacia su hijo (en el modelo)
        for lado in "LR":
            m = t["miembro"]
            for a, b in (("muslo", "pierna"), ("pierna", "pie"), ("brazo", "antebrazo"), ("antebrazo", "mano")):
                d = esq.pos_rep(m[b] % lado) - esq.pos_rep(m[a] % lado)
                d.normalize()
                self.dir_rep[m[a] % lado] = d
        self.rep_rot = {n: esq.mundo_rep[n].getUpper3() for n in esq.orden}
        self.rep_inv = {}
        for n in esq.orden:
            inv = LMatrix4()
            inv.invertFrom(esq.mundo_rep[n])
            self.rep_inv[n] = inv

    def _padre_virtual(self, nombre):
        t = self.e.tipo["virtual"]
        if nombre in self.explicito:
            clave, lado = self.explicito[nombre]
            if clave == "muslo":
                return t["muslo"]
            if clave == "brazo":
                return t["brazo"] % lado if "%s" in t["brazo"] else t["brazo"]
            return None
        low = nombre.lower()
        if "pelvis" in low:
            return t["pelvis"]
        if "breast" in low or "shoulder" in low:
            return t["pecho"]
        return t["cabeza"]

    def locales(self, pose):
        e = self.e
        t = e.tipo
        desp = e.vec_a_modelo(pose["desp_pelvis"])
        rot_zona = {z: _a_lmat3(e.rot_a_modelo(ac.mat_euler(*pose["rot"][z]))) for z in ac.ZONAS}
        # rotaciones absolutas objetivo de los huesos explícitos (columnas, en el modelo)
        objetivo = {}
        for lado, clave_p in (("L", "i"), ("R", "d")):
            pie = pose["pierna_" + clave_p]
            br = pose["brazo_" + clave_p]
            m = t["miembro"]
            dirs = {m["muslo"] % lado: pie["muslo"], m["pierna"] % lado: pie["pierna"],
                    m["brazo"] % lado: br["sup"], m["antebrazo"] % lado: br["inf"]}
            for hueso, d in dirs.items():
                objetivo[hueso] = _a_lmat3(ac.arco(_tup(self.dir_rep[hueso]), e.vec_a_modelo(d)))
            objetivo[m["mano"] % lado] = objetivo[m["antebrazo"] % lado]
            objetivo[m["pie"] % lado] = _a_lmat3(e.rot_a_modelo(ac.mat_eje((0, 1, 0), -pie["pie_pitch"])))
            objetivo[m["dedos"] % lado] = _a_lmat3(e.rot_a_modelo(ac.mat_eje((0, 1, 0), -pie["dedos_pitch"])))
        mundo = {}

        def calcular(nombre):
            if nombre in mundo:
                return mundo[nombre]
            rep = e.mundo_rep[nombre]
            padre = e.padre[nombre]
            zona = self.zona_de.get(nombre)
            if zona is not None or nombre in objetivo:
                rot = rot_zona[zona] if zona is not None else objetivo[nombre]
                nueva = rep.getUpper3() * rot
                if padre is None:
                    virtual = self._padre_virtual(nombre) if zona is None else None
                    if virtual is None:
                        pos = LVecBase3(rep.getRow3(3)) + (_vec(desp) if zona == "pelvis" else LVecBase3(0, 0, 0))
                    else:
                        pos = self._rigido(nombre, virtual, calcular).xformPoint(rep.getRow3(3))
                else:
                    pos = LVecBase3(calcular(padre).getRow3(3)) + calcular(padre).getUpper3().xform(
                        e.local_rep[nombre].getRow3(3))
                w = LMatrix4(nueva, pos)
            elif padre is None:
                w = self._rigido_mundo(nombre, calcular)
            else:
                base = e.local_idle.get(nombre, e.local_rep[nombre])
                w = base * calcular(padre)
            mundo[nombre] = w
            return w

        res = {}
        for nombre in e.orden:
            w = calcular(nombre)
            padre = e.padre[nombre]
            if padre is None:
                res[nombre] = LMatrix4(w)
            else:
                inv = LMatrix4()
                inv.invertFrom(mundo[padre])
                res[nombre] = w * inv
        return res

    def _rigido(self, nombre, virtual, calcular):
        # transformación rígida que lleva el reposo del padre virtual a su pose actual (aplicable a puntos)
        return self.rep_inv[virtual] * calcular(virtual)

    def _rigido_mundo(self, nombre, calcular):
        virtual = self._padre_virtual(nombre)
        return self.e.mundo_rep[nombre] * self._rigido(nombre, virtual, calcular)


def _constante(valores):
    return max(valores) - min(valores) < 1e-5


def _desenrollar(serie):
    # Ángulos continuos entre fotogramas (sin saltos de 360).
    salida = [serie[0]]
    for v in serie[1:]:
        previo = salida[-1]
        salida.append(v + 360.0 * round((previo - v) / 360.0))
    return salida


def _construir_clip(esq, nombre, poses):
    # poses: lista de poses (una por fotograma). Devuelve el AnimBundle.
    hornero = Hornero(esq)
    cuadros = [hornero.locales(p) for p in poses]
    banco = AnimBundle(nombre, FPS, len(poses))
    raiz = AnimGroup(banco, "<skeleton>")
    canales = {}
    escala, cizalla, hpr, pos = LVecBase3(), LVecBase3(), LVecBase3(), LVecBase3()

    def crear(nombre_hueso, padre_grupo):
        canal = AnimChannelMatrixXfmTable(padre_grupo, nombre_hueso)
        series = {k: [] for k in "hprxyz"}
        for c in cuadros:
            decompose_matrix(c[nombre_hueso], escala, cizalla, hpr, pos)
            for k, v in zip("hprxyz", (hpr[0], hpr[1], hpr[2], pos[0], pos[1], pos[2])):
                series[k].append(v)
        for k in "hpr":
            series[k] = _desenrollar(series[k])
        for k, valores in series.items():
            canal.setTable(k.encode(), PTA_stdfloat([valores[0]] if _constante(valores) else valores))
        for k in "ijk":
            canal.setTable(k.encode(), PTA_stdfloat([1.0]))
        canales[nombre_hueso] = canal
        for hijo in esq.hijos[nombre_hueso]:
            crear(hijo, canal)

    for nombre_hueso in esq.orden:
        if esq.padre[nombre_hueso] is None:
            crear(nombre_hueso, raiz)
    return banco


_cache_medidas = {}


# Añade al nodo del modelo (recién cargado con gltf.load_model, antes de crear el Actor) los clips humanos.
# Devuelve True si los añadió. Nunca lanza: ante cualquier fallo avisa y deja el modelo como estaba.
def hornear_clips(modelo_np, rol):
    try:
        personaje = modelo_np.find("**/+Character")
        if personaje.isEmpty():
            return False
        esq = Esqueleto(personaje)
        m = esq.medidas()
        _cache_medidas[rol] = m
        clips = []
        for i, v in enumerate(ac.VELS):
            clips.append((NOMBRES_MARCHA[i], [ac.pose_marcha(k / FOTOGRAMAS, v, m) for k in range(FOTOGRAMAS)]))
        clips.append((CLIP_ESCALON, [ac.pose_escalon(k / FOTOGRAMAS, m) for k in range(FOTOGRAMAS)]))
        for etapa, nombre in CLIPS_SALTO.items():
            clips.append((nombre, [ac.pose_salto(etapa, m)]))
        for gesto, nombre in CLIPS_GESTO.items():
            clips.append((nombre, [ac.pose_gesto(gesto, m)]))
        for nombre, poses in clips:
            banco = _construir_clip(esq, nombre, poses)
            personaje.attachNewNode(AnimBundleNode("rig", banco))
        return True
    except Exception as error:
        _avisar(f"{rol}: no se pudieron hornear los clips ({error})")
        return False


def _ganadores(pesos):
    return {c: w for c, w in pesos.items() if w > 1e-4}


class AnimadorHumano:
    # Elige y mezcla los clips reales de un PersonajeModelo. El personaje conserva su clip LÓGICO (`_clip`:
    # Idle, Caminar, Correr, Saludar, Hablar) para la cara y las poses; este objeto decide qué clips suenan.
    def __init__(self, personaje):
        self.p = personaje
        self.actor = personaje.actor
        self.pesos = {IDLE: 1.0}
        self.reproduciendo = {IDLE}
        self.tasas = {}
        self.v = 0.0
        self.t_aterrizaje = 0.0
        self.en_aire_previo = False
        self.congelado = False
        self.t_gesto = 0.0            # >0 mientras un gesto (Saludar/Hablar) suena o se acaba de ir
        # el Actor va escalado (0.92, 0.86, o la escala del NPC): la marcha se diseñó en unidades del modelo, así que
        # la velocidad que guía el ciclo es la real dividida por esa escala (si no, los pies patinan un 8 %)
        try:
            self.escala = max(0.3, abs(float(self.actor.getScale()[1])))
        except Exception:
            self.escala = 1.0
        self.fase_inicial = float(getattr(personaje, "_fase_marcha_inicial", lambda: 0.0)())
        self.actor.getPartBundle("modelRoot").setFrameBlendFlag(True)   # interpolar fotogramas: movimiento suave

    # -- Objetivo de pesos --

    def _objetivo(self, dt):
        p = self.p
        logico = p._clip
        if logico in (SALUDAR, HABLAR):
            self.t_gesto = TIEMPO_GESTO + 0.1
            return {logico: 1.0}, 0.0
        self.t_gesto = max(0.0, self.t_gesto - dt)
        objetivo_v = getattr(p, "_v_anim", 0.0) if logico in (CAMINAR, CORRER) else 0.0
        self.v += (objetivo_v - self.v) * (1 - math.exp(-SUAVIZADO_VELOCIDAD * dt))
        cadencia = 0.0
        if getattr(p, "_en_aire", False):
            self.t_aterrizaje = 0.0
            self.en_aire_previo = True
            imp, asc, cai = ac.pesos_salto(getattr(p, "_vel_vertical", 0.0))
            return {CLIPS_SALTO["impulso"]: imp, CLIPS_SALTO["ascenso"]: asc, CLIPS_SALTO["caida"]: cai}, 0.0
        if self.en_aire_previo:
            self.en_aire_previo = False
            self.t_aterrizaje = ac.DURACION_ATERRIZAJE
        suelo, cadencia = self._objetivo_suelo()
        if self.t_aterrizaje > 0:
            self.t_aterrizaje = max(0.0, self.t_aterrizaje - dt)
            k = ac._suave(self.t_aterrizaje / ac.DURACION_ATERRIZAJE)
            suelo = {c: w * (1 - k) for c, w in suelo.items()}
            suelo[CLIPS_SALTO["aterrizaje"]] = k
        g = getattr(p, "_gesto_peso", 0.0)
        if g > 0.0 and suelo == {IDLE: 1.0}:      # gesto de mano solo si está quieto; con g == 0 todo queda como antes
            clip = getattr(p, "_gesto_clip", None)
            if clip in CLIPS_GESTO.values():
                return {IDLE: 1 - g, clip: g}, 0.0
        return suelo, cadencia

    def _objetivo_suelo(self):
        v = self.v / self.escala
        g = ac.peso_marcha(v)
        if g <= 0.0:
            return {IDLE: 1.0}, 0.0
        if getattr(self.p, "_subiendo", False):
            return {IDLE: 1 - g, CLIP_ESCALON: g}, ac.cadencia_escalon(v)
        i, w, cadencia = ac.mezcla_marcha(v)
        return {IDLE: 1 - g, NOMBRES_MARCHA[i]: g * (1 - w), NOMBRES_MARCHA[i + 1]: g * w}, cadencia

    # -- Aplicar al Actor --

    def mezclar(self, dt):
        objetivo, cadencia = self._objetivo(dt)
        paso = dt / (TIEMPO_GESTO if self.t_gesto > 0 else TIEMPO_MEZCLA)
        actor = self.actor
        for clip in set(self.pesos) | set(objetivo):
            meta = objetivo.get(clip, 0.0)
            actual = self.pesos.get(clip, 0.0)
            if clip in (CLIP_ESCALON,) or clip in NOMBRES_MARCHA:
                nuevo = meta if abs(meta - actual) < 0.5 else (min(meta, actual + paso) if meta > actual else max(meta, actual - paso))
            else:
                nuevo = min(meta, actual + paso) if meta > actual else max(meta, actual - paso)
            if nuevo <= 0.0 and meta <= 0.0:
                actor.setControlEffect(clip, 0.0)   # sin esto queda el último peso (>0) contaminando la mezcla
                if clip in self.reproduciendo:
                    actor.stop(clip)
                    self.reproduciendo.discard(clip)
                self.pesos.pop(clip, None)
                self.tasas.pop(clip, None)
                continue
            if clip not in self.reproduciendo:
                self._arrancar(clip)
            self.pesos[clip] = nuevo
            es_marcha = clip in NOMBRES_MARCHA or clip == CLIP_ESCALON
            # los pesos de la marcha quedan lineales (la cadencia exacta depende de ellos); el resto se suaviza
            actor.setControlEffect(clip, nuevo if es_marcha else ac._suave(nuevo))
            self._tasa(clip, cadencia)

    def _arrancar(self, clip):
        actor = self.actor
        self.reproduciendo.add(clip)
        self.tasas.pop(clip, None)
        if clip in CLIPS_SALTO.values() or clip in CLIPS_GESTO.values():
            actor.pose(clip, 0)
            return
        if clip in NOMBRES_MARCHA or clip == CLIP_ESCALON:
            control = actor.getAnimControl(clip)
            otros = [c for c in self.reproduciendo if c != clip and (c in NOMBRES_MARCHA or c == CLIP_ESCALON)]
            if otros:
                cuadro = actor.getCurrentFrame(otros[0]) or 0
            else:
                cuadro = int(self.fase_inicial * FOTOGRAMAS) % FOTOGRAMAS
            if control is not None:
                control.pose(int(cuadro) % max(1, control.getNumFrames()))
                control.loop(False)
            else:
                actor.loop(clip)
            return
        self.p._iniciar_loop(clip)

    def _tasa(self, clip, cadencia):
        if clip in CLIPS_SALTO.values() or clip in CLIPS_GESTO.values():
            return
        if self.congelado:
            tasa = 0.0
        elif clip in NOMBRES_MARCHA or clip == CLIP_ESCALON:
            tasa = max(0.05, cadencia * FOTOGRAMAS / FPS)
        else:
            tasa = 1.0
        anterior = self.tasas.get(clip)
        if anterior is None or abs(tasa - anterior) > 0.01:
            self.actor.setPlayRate(tasa, clip)
            self.tasas[clip] = tasa

    def congelar(self, congelar):
        if congelar != self.congelado:
            self.congelado = congelar
            self.tasas.clear()


# Fábrica: el animador si el modelo trae los clips horneados; si no, None (animación de siempre).
def crear_animador(personaje):
    try:
        if NOMBRES_MARCHA[0] not in personaje.actor.getAnimNames():
            return None
        return AnimadorHumano(personaje)
    except Exception as error:
        _avisar(f"no se pudo crear el animador ({error})")
        return None

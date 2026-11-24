# Parkour del sector corrupto (cálculos puros, sin ursina): nivel como GRAFO de plataformas, simulación
# del jugador sobre ellas, Dijkstra de la ruta óptima, puntuación, medallas y recompensa de evidencia.
#
# Modelo (m y s; x derecha, z adelante, y arriba):
#   - Plataforma: caja de cara superior en (x, y, z) con `ancho` (x) y `fondo` (z). Tipos:
#       fija        siempre está.
#       movil       oscila alrededor de su posición base: movimiento = {"eje": [dx,dy,dz], "periodo": s, "fase": 0..1}
#                   (amplitud = el eje; posición = base + eje * sin(2π(t/periodo + fase))). Lleva al jugador.
#       desaparece  al pisarla avisa `aviso_s`, desaparece `oculta_s` y reaparece.
#       capa        (sesión E) se desliza en horizontal de un extremo al otro con reposo en cada extremo (onda trapezoidal
#                   suavizada): movimiento = {"eje": [dx,0,dz], "periodo", "fase", "reposo"}. Lleva al jugador.
#       cinta       quieta; su superficie arrastra al jugador apoyado: arrastre = (vx, vz) m/s. En el aire no arrastra.
#       ritmo       cambia de altura por pulsos: ritmo = {"pulso_s", "patron": [dy…], "fase", "transicion"}. Lo lleva en vertical.
#       clip        existe solo una parte de un ciclo fijo (sin pisarla): ciclo = {"periodo", "visible_s", "fase", "aviso_s"}.
#     `purgable` = la purga del nivel (campo `purga` de Nivel) la borra cuando el frente pasa por ella.
#     `requiere` = id de un interruptor: la plataforma solo existe mientras ese interruptor esté activo.
#     `checkpoint` = al pisarla se guarda como punto de reaparición.
#   - Interruptor: punto que se activa al acercarse (radio) y habilita plataformas; `duracion_s` None = permanente.
#   - Grafo del nivel: nodos = plataformas, aristas dirigidas = saltos posibles con `coste` (s estimados) y
#     `riesgo` (0 seguro; 1 o más = salto arriesgado, para la ruta difícil). Dijkstra da la ruta óptima; con
#     `max_riesgo=0` da la ruta segura (la fácil).
#   - Física vertical: EstadoVertical (salto_calculos) + UN salto en el aire (doble salto) añadido aquí, sin tocarlo.
#   - El tiempo NO entra en la confianza de GameState: solo en la puntuación del parkour.

import heapq
import math
import os
from dataclasses import dataclass, field

from backend.logica import evidencia
from backend.logica.salto_calculos import (GRAVEDAD, TIEMPO_COYOTE, VELOCIDAD_SALTO, EstadoVertical)

VELOCIDAD = 6.5               # m/s al andar y en el aire
RADIO_JUGADOR = 0.3           # m: cuánto puede asomar el cuerpo fuera del borde y seguir apoyado
TOLERANCIA_ESCALON = 0.35     # m: una cara superior hasta tanto sobre los pies aún sostiene (subir un borde)
COSTE_POR_METRO = 0.45        # s por metro de salto sin arista declarada (estimación)
COSTE_SALTO_SIN_ARISTA = 2.0  # s fijos extra de un salto que no está en el grafo (el jugador improvisó)
ALCANCE_INTERRUPTOR = 1.4     # m de altura sobre el interruptor dentro de los que se activa
TIPOS = ("fija", "movil", "desaparece", "capa", "cinta", "ritmo", "clip")
MOVILES = ("movil", "capa")        # tipos que llevan al jugador en horizontal
FRACCION_PURGA = 0.3               # la purga se come una plataforma al pasar 3/10 de su fondo
MEDALLAS = ("bronce", "plata", "oro")
CATEGORIAS = ("facil", "dificil")

# Resultado v2 del parkour (mensaje final de la ruta Dijkstra). Con la bandera:
#   - al reaparecer en un checkpoint la ruta se recorta hasta él: el intento fallido no cuenta como tramo de la ruta
#     (antes un salto fallido desde r1 dejaba la carrera como «Ruta arriesgada» y el salto de reaparición sumaba un
#     coste estimado de ~5 s; la caída ya se cobra en tiempo y en puntos);
#   - el panel enseña la ruta de REFERENCIA de la categoría (la segura si la carrera fue segura) con su coste, partida
#     en varias líneas para que quepa en el panel (la de 26 nodos medía ~160 caracteres y se salía).
# RESULTADO_PARKOUR_V2 = False (o ALCALDE_RESULTADO_PARKOUR_V2=0) deja el comportamiento anterior.
RESULTADO_PARKOUR_V2 = True
MAX_CARACTERES_RUTA = 62      # caracteres por línea de la ruta en el panel final (13 px en un panel de ~540 px)


def resultado_v2_activo():
    valor = os.environ.get("ALCALDE_RESULTADO_PARKOUR_V2", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(RESULTADO_PARKOUR_V2)


# -- Datos del nivel --

@dataclass(frozen=True)
class Plataforma:
    id: str
    x: float
    y: float
    z: float
    ancho: float
    fondo: float
    tipo: str = "fija"
    movimiento: dict | None = None
    aviso_s: float = 1.0
    oculta_s: float = 2.0
    requiere: str | None = None
    checkpoint: bool = False
    arrastre: tuple | None = None      # cinta: (vx, vz) m/s
    ritmo: dict | None = None          # ritmo: {"pulso_s", "patron", "fase", "transicion"}
    ciclo: dict | None = None          # clip: {"periodo", "visible_s", "fase", "aviso_s"}
    purgable: bool = False


@dataclass(frozen=True)
class Arista:
    desde: str
    hasta: str
    coste: float
    riesgo: int = 0


@dataclass(frozen=True)
class Interruptor:
    id: str
    x: float
    y: float
    z: float
    activa: tuple = ()
    radio: float = 0.9
    duracion_s: float | None = None


@dataclass(frozen=True)
class Nivel:
    id: str
    nombre: str
    tema: str
    inicio: str
    meta: str
    plataformas: dict
    aristas: tuple
    interruptores: dict = field(default_factory=dict)
    y_muerte: float = -8.0
    penalizacion_caida_s: float = 3.0
    puntuacion: dict = field(default_factory=dict)
    medallas: dict = field(default_factory=dict)
    recompensa: dict = field(default_factory=dict)
    descripcion: str = ""
    purga: dict | None = None          # {"activa_en", "z_inicio", "velocidad", "z_fin", "aviso_m"} (avanza en +z)


# -- Plataformas en el tiempo --

def _suave(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# Onda de la capa en [-1, 1]: con u = fracción del periodo, en cada medio periodo queda quieta en un extremo durante
# `reposo` (fracción del periodo) y el resto se desliza al otro extremo con smoothstep. Fase 0: quieta en +1.
def onda_capa(t, periodo, fase=0.0, reposo=0.25):
    u = (t / max(1e-6, periodo) + fase) % 1.0
    reposo = max(0.0, min(0.45, reposo))
    signo = 1.0 if u < 0.5 else -1.0
    resto = u if u < 0.5 else u - 0.5
    if resto < reposo:
        return signo
    return signo * (1 - 2 * _suave((resto - reposo) / (0.5 - reposo)))


# Ritmo: (índice del pulso dentro del patrón, fracción 0-1 del pulso) en el instante `t`.
def pulso_actual(p, t):
    r = p.ritmo or {}
    q = t / max(1e-6, float(r.get("pulso_s", 0.6))) + float(r.get("fase", 0.0))
    i = math.floor(q)
    return int(i % max(1, len(r.get("patron") or (0,)))), q - i


# Ritmo: desplazamiento vertical (m) sobre `y` en `t`. Al empezar un pulso viaja de la altura anterior a la nueva
# durante `transicion` (fracción del pulso, suavizado) y el resto del pulso queda quieta.
def desplazamiento_ritmo(p, t):
    r = p.ritmo or {}
    patron = r.get("patron") or (0.0,)
    i, f = pulso_actual(p, t)
    actual, previo = patron[i], patron[(i - 1) % len(patron)]
    transicion = float(r.get("transicion", 0.25))
    if f >= transicion:
        return float(actual)
    return previo + (actual - previo) * _suave(f / transicion)


# Clip: "solida" | "aviso" (aún sostiene, parpadea) | "oculta" en `t`, por su ciclo fijo.
def fase_clip(p, t):
    c = p.ciclo or {}
    periodo = max(1e-6, float(c.get("periodo", 4.0)))
    visible = float(c.get("visible_s", periodo))
    u = (t + float(c.get("fase", 0.0)) * periodo) % periodo
    if u < visible - float(c.get("aviso_s", 0.5)):
        return "solida"
    return "aviso" if u < visible else "oculta"


# Posición (x, y, z) de la cara superior de `p` en el instante `t`.
def posicion_plataforma(p, t):
    if p.tipo == "capa" and p.movimiento:
        m = p.movimiento
        onda = onda_capa(t, float(m.get("periodo", 4.0)), float(m.get("fase", 0.0)), float(m.get("reposo", 0.25)))
        ex, _, ez = m.get("eje", (0.0, 0.0, 0.0))
        return (p.x + ex * onda, p.y, p.z + ez * onda)
    if p.tipo == "ritmo" and p.ritmo:
        return (p.x, p.y + desplazamiento_ritmo(p, t), p.z)
    if p.tipo != "movil" or not p.movimiento:
        return (p.x, p.y, p.z)
    periodo = max(1e-6, float(p.movimiento.get("periodo", 4.0)))
    onda = math.sin(2 * math.pi * (t / periodo + float(p.movimiento.get("fase", 0.0))))
    ex, ey, ez = p.movimiento.get("eje", (0.0, 0.0, 0.0))
    return (p.x + ex * onda, p.y + ey * onda, p.z + ez * onda)


# Fase de una plataforma que desaparece: "solida" (sin pisar), "aviso" (pisada, aún sostiene), "oculta".
# `pisada_en` = instante en que se pisó (None = aún no). Pasado el ciclo completo vuelve a "solida".
def fase_desaparece(p, pisada_en, t):
    if pisada_en is None:
        return "solida"
    pasado = t - pisada_en
    if pasado < p.aviso_s:
        return "aviso"
    if pasado < p.aviso_s + p.oculta_s:
        return "oculta"
    return "solida"


# Alcance horizontal máximo (m) de un salto que parte y llega a alturas con diferencia `dh` (destino - origen),
# a VELOCIDAD, con o sin el doble salto (segundo impulso en el punto más alto). 0 si no llega a esa altura.
def alcance_de_salto(dh, doble=True, velocidad=VELOCIDAD):
    altura_unica = VELOCIDAD_SALTO ** 2 / (2 * GRAVEDAD)
    subida = VELOCIDAD_SALTO / GRAVEDAD
    if doble:
        techo, tiempo_previo = 2 * altura_unica, 2 * subida
    else:
        techo, tiempo_previo = altura_unica, subida
    if dh > techo:
        return 0.0
    return velocidad * (tiempo_previo + math.sqrt(2 * (techo - dh) / GRAVEDAD))


# Distancia horizontal mínima entre los bordes de dos plataformas (0 si se solapan), tomando la mejor
# posición de las que oscilan (se muestrea un periodo).
def separacion_minima(a, b, muestras=24):
    mejor = None
    for i in range(muestras if ({"movil", "capa", "ritmo"} & {a.tipo, b.tipo}) else 1):
        t = i / muestras * 8.0
        ax, ay, az = posicion_plataforma(a, t)
        bx, by, bz = posicion_plataforma(b, t)
        hueco_x = max(0.0, abs(ax - bx) - (a.ancho + b.ancho) / 2)
        hueco_z = max(0.0, abs(az - bz) - (a.fondo + b.fondo) / 2)
        d = math.hypot(hueco_x, hueco_z)
        mejor = d if mejor is None else min(mejor, d)
    return mejor


# -- Grafo y Dijkstra --

def _vecinos(nivel, max_riesgo):
    vecinos = {}
    for a in nivel.aristas:
        if max_riesgo is not None and a.riesgo > max_riesgo:
            continue
        vecinos.setdefault(a.desde, []).append(a)
    return vecinos


# Ruta de menor coste inicio -> meta por Dijkstra (cola de prioridad). Con `max_riesgo` solo usa aristas de riesgo
# <= ese valor (0 = ruta segura). Retorna (coste, [ids]) o (None, []) si no hay camino.
def ruta_optima(nivel, desde=None, hasta=None, max_riesgo=None):
    origen = desde or nivel.inicio
    destino = hasta or nivel.meta
    vecinos = _vecinos(nivel, max_riesgo)
    distancia = {origen: 0.0}
    anterior = {}
    cola = [(0.0, origen)]
    hechos = set()
    while cola:
        coste, nodo = heapq.heappop(cola)
        if nodo in hechos:
            continue
        hechos.add(nodo)
        if nodo == destino:
            break
        for a in vecinos.get(nodo, ()):
            nuevo = coste + a.coste
            if nuevo < distancia.get(a.hasta, math.inf):
                distancia[a.hasta] = nuevo
                anterior[a.hasta] = nodo
                heapq.heappush(cola, (nuevo, a.hasta))
    if destino not in hechos:
        return None, []
    camino = [destino]
    while camino[-1] != origen:
        camino.append(anterior[camino[-1]])
    camino.reverse()
    return round(distancia[destino], 4), camino


# Coste estimado de un salto entre plataformas SIN arista declarada (el jugador improvisó o reapareció).
def coste_estimado(nivel, a, b):
    pa, pb = nivel.plataformas[a], nivel.plataformas[b]
    d = math.dist((pa.x, pa.y, pa.z), (pb.x, pb.y, pb.z))
    return COSTE_SALTO_SIN_ARISTA + COSTE_POR_METRO * d


# Coste de recorrer `ruta` (ids consecutivos): la arista declarada más barata, o la estimación si no existe.
# Un tramo a la misma plataforma no cuesta.
def coste_de_ruta(nivel, ruta):
    mejores = {}
    for a in nivel.aristas:
        clave = (a.desde, a.hasta)
        mejores[clave] = min(a.coste, mejores.get(clave, math.inf))
    total = 0.0
    for a, b in zip(ruta, ruta[1:]):
        if a == b:
            continue
        total += mejores.get((a, b), coste_estimado(nivel, a, b))
    return round(total, 4)


# "dificil" si la ruta usa alguna arista de riesgo > 0; si no, "facil".
def categoria_de_ruta(nivel, ruta):
    riesgos = {}
    for a in nivel.aristas:
        riesgos[(a.desde, a.hasta)] = max(a.riesgo, riesgos.get((a.desde, a.hasta), 0))
    return "dificil" if any(riesgos.get(par, 0) > 0 for par in zip(ruta, ruta[1:])) else "facil"


# Compara la ruta real del jugador con la óptima de SU categoría (la difícil contra la óptima global, la fácil
# contra la óptima segura). Eficiencia 0-100 = coste óptimo / coste real. Retorna un dict; si la ruta real no
# llega a la meta o no hay camino, eficiencia 0.
def evaluar_eficiencia(nivel, ruta_real):
    optimo, ruta_opt = ruta_optima(nivel)
    seguro, ruta_seg = ruta_optima(nivel, max_riesgo=0)
    base = {"ruta_optima": ruta_opt, "coste_optimo": optimo, "ruta_segura": ruta_seg, "coste_seguro": seguro,
            "ruta_real": list(ruta_real), "coste_real": None, "categoria": "facil", "eficiencia": 0.0}
    if not ruta_real or ruta_real[-1] != nivel.meta or ruta_real[0] != nivel.inicio:
        return base
    real = coste_de_ruta(nivel, ruta_real)
    categoria = categoria_de_ruta(nivel, ruta_real)
    referencia = optimo if categoria == "dificil" else (seguro if seguro is not None else optimo)
    eficiencia = 0.0
    if referencia is not None and real > 0:
        eficiencia = max(0.0, min(100.0, 100.0 * referencia / real))
    base.update(coste_real=real, categoria=categoria, eficiencia=round(eficiencia, 1))
    return base


# -- Puntuación y medallas --

def _acotar(valor, minimo=0.0, maximo=1.0):
    return max(minimo, min(maximo, valor))


def _es_finito(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


# Puntos (entero >= 0) de una carrera. `tiempo_s` ya incluye las penalizaciones por caída en tiempo.
# Fórmula: maximo * (peso_tiempo * min(1, tiempo_ref / tiempo) + peso_eficiencia * eficiencia/100)
#          - caidas * penalizacion_caida + bono_ruta_dificil (solo si la categoría es "dificil").
# Datos ilegibles (NaN, infinito, None, texto: solo con datos corruptos) nunca premian ni revientan: un tiempo ilegible
# cuenta como el peor (0 puntos de tiempo), una eficiencia ilegible como 0 y unas caídas ilegibles dejan la carrera en 0.
def puntuar(nivel, tiempo_s, eficiencia, caidas, categoria="facil"):
    cfg = nivel.puntuacion
    if not _es_finito(caidas):
        return 0
    f_tiempo = _acotar(cfg["tiempo_referencia_s"] / max(tiempo_s, 1e-6)) if _es_finito(tiempo_s) else 0.0
    f_eficiencia = _acotar(eficiencia / 100.0) if _es_finito(eficiencia) else 0.0
    base = cfg["maximo"] * (cfg["peso_tiempo"] * f_tiempo + cfg["peso_eficiencia"] * f_eficiencia)
    base -= caidas * cfg.get("penalizacion_caida", 0)
    if categoria == "dificil":
        base += cfg.get("bono_ruta_dificil", 0)
    return max(0, int(round(base)))


# Mayor medalla ("bronce" < "plata" < "oro") cuyo umbral alcanzan los `puntos`; None si ninguna.
def medalla_de(nivel, puntos):
    obtenida = None
    for nombre in MEDALLAS:
        umbral = nivel.medallas.get(nombre)
        if umbral is not None and puntos >= umbral:
            obtenida = nombre
    return obtenida


# Medalla provisional del HUD: la MEJOR que aún se puede lograr con este tiempo y estas caídas (eficiencia
# perfecta, sin bono). Solo baja con el tiempo y las caídas; es una cota superior, no una promesa.
def medalla_alcanzable(nivel, tiempo_s, caidas):
    return medalla_de(nivel, puntuar(nivel, tiempo_s, 100.0, caidas))


# Resultado completo de una carrera terminada.
def resultado_del_nivel(nivel, tiempo_s, caidas, ruta_real):
    ev = evaluar_eficiencia(nivel, ruta_real)
    completado = bool(ruta_real) and ruta_real[-1] == nivel.meta
    puntos = puntuar(nivel, tiempo_s, ev["eficiencia"], caidas, ev["categoria"]) if completado else 0
    return {
        "nivel": nivel.id, "completado": completado, "tiempo_s": round(tiempo_s, 2) if _es_finito(tiempo_s) else 0.0,
        "caidas": caidas,
        "puntos": puntos, "medalla": medalla_de(nivel, puntos) if completado else None,
        **ev,
    }


# -- Recompensa --

# ¿Merece la recompensa? completado y, si el JSON pide medalla mínima, que la iguale o supere.
def merece_recompensa(nivel, resultado):
    if not resultado.get("completado"):
        return False
    pedida = nivel.recompensa.get("requiere_medalla")
    if pedida is None:
        return True
    obtenida = resultado.get("medalla")
    return obtenida is not None and MEDALLAS.index(obtenida) >= MEDALLAS.index(pedida)


# Otorga la evidencia del nivel en `game_state` (evidencia.otorgar, idempotente). Retorna True solo si es nueva.
# Sin game_state (None) o sin recompensa/mérito no hace nada: el parkour se juega igual, sin consecuencias.
def otorgar_recompensa(nivel, resultado, game_state):
    id_evidencia = nivel.recompensa.get("evidencia")
    if game_state is None or not id_evidencia or not merece_recompensa(nivel, resultado):
        return False
    datos = {"puntos": resultado.get("puntos"), "medalla": resultado.get("medalla"), "tiempo_s": resultado.get("tiempo_s")}
    # `recompensa.caso` (opcional en el JSON del nivel): el caso al que pertenece la evidencia. Con él, el Archivo de
    # casos la muestra también al filtrar por ese caso (el origen sigue siendo «parkour:<nivel>»).
    caso = nivel.recompensa.get("caso")
    if isinstance(caso, str) and caso.strip():
        datos["caso"] = caso.strip()
    return evidencia.otorgar(
        game_state, id_evidencia, origen=f"parkour:{nivel.id}", efectos=nivel.recompensa.get("efectos"), datos=datos)


# -- Datos para el minimapa (los dibuja otro módulo) --

# Altura de cada plataforma para el minimapa: {"minimo", "maximo", "plataformas": [{id, x, z, ancho, fondo, y,
# y_norm (0 = la más baja, 1 = la más alta), movil, checkpoint, meta, inicio}]}. Usa la posición base.
def alturas_para_minimapa(nivel):
    alturas = [p.y for p in nivel.plataformas.values()]
    minimo, maximo = min(alturas), max(alturas)
    rango = maximo - minimo
    lista = []
    for p in nivel.plataformas.values():
        lista.append({
            "id": p.id, "x": p.x, "z": p.z, "ancho": p.ancho, "fondo": p.fondo, "y": p.y,
            "y_norm": 0.0 if rango <= 0 else round((p.y - minimo) / rango, 4),
            "movil": p.tipo == "movil", "checkpoint": p.checkpoint, "tipo": p.tipo, "purgable": p.purgable,
            "meta": p.id == nivel.meta, "inicio": p.id == nivel.inicio,
        })
    return {"minimo": minimo, "maximo": maximo, "plataformas": lista}


# -- Simulación del jugador --

# Estado de una carrera. `paso()` avanza un instante con la entrada ya traducida a ejes del MUNDO.
# Eventos que devuelve paso(): "salto", "doble_salto", "aterrizo", "checkpoint:<id>", "interruptor:<id>",
# "interruptor_apagado:<id>", "caida", "meta", "purga_inicio", "purga_fin".
class Simulacion:

    def __init__(self, nivel):
        self.nivel = nivel
        self.t = 0.0
        self.caidas = 0
        self.terminado = False
        self.vertical = EstadoVertical()
        self.doble_usado = False
        self.pisada_desaparece = {}       # id -> instante en que se pisó
        self.interruptores = {}           # id -> instante en que se apaga (math.inf = permanente)
        self.sobre = None                 # id de la plataforma que sostiene al jugador
        self.checkpoint = nivel.inicio
        self.ruta = []
        self.purga_t0 = None              # instante en que se armó la purga (None = no corre)
        self.purga_acabada = False
        inicial = nivel.plataformas[nivel.inicio]
        self.x, y, self.z = posicion_plataforma(inicial, 0.0)
        self.vertical.reiniciar(y)
        self._registrar_nodo(nivel.inicio)

    @property
    def y(self):
        return self.vertical.y

    # ¿Existe (es sólida) la plataforma ahora?
    def activa(self, p):
        if p.requiere is not None and self.interruptores.get(p.requiere, -1.0) <= self.t:
            return False
        if p.purgable and self._fase_purga(p) == "oculta":
            return False
        if p.tipo == "desaparece":
            return fase_desaparece(p, self.pisada_desaparece.get(p.id), self.t) != "oculta"
        if p.tipo == "clip":
            return fase_clip(p, self.t) != "oculta"
        return True

    def interruptor_activo(self, id_interruptor):
        return self.interruptores.get(id_interruptor, -1.0) > self.t

    def fase(self, p):
        if p.tipo == "desaparece":
            propia = fase_desaparece(p, self.pisada_desaparece.get(p.id), self.t)
        elif p.tipo == "clip":
            propia = fase_clip(p, self.t)
        else:
            propia = "solida"
        if p.purgable and propia != "oculta":
            purga = self._fase_purga(p)
            if purga != "solida":
                return purga
        return propia

    # -- Purga: el frente avanza en +z desde que se pisa `activa_en` --

    def _frente(self):
        purga = self.nivel.purga
        if not purga or self.purga_t0 is None:
            return None
        return min(purga["z_fin"], purga["z_inicio"] + purga["velocidad"] * (self.t - self.purga_t0))

    def _fase_purga(self, p):
        frente = self._frente()
        if frente is None:
            return "solida"
        corte = p.z - p.fondo / 2 + FRACCION_PURGA * p.fondo
        if frente >= corte:
            return "oculta"
        return "aviso" if frente >= corte - self.nivel.purga.get("aviso_m", 3.0) else "solida"

    # z del frente de la purga mientras corre; None si no está armada o ya acabó.
    def purga_frente(self):
        return None if self.purga_acabada else self._frente()

    # Segundos que le quedan a la purga en curso (para la cuenta atrás del HUD); None si no corre.
    def purga_restante(self):
        frente = self.purga_frente()
        if frente is None:
            return None
        return max(0.0, (self.nivel.purga["z_fin"] - frente) / self.nivel.purga["velocidad"])

    def _registrar_nodo(self, id_plataforma):
        if not self.ruta or self.ruta[-1] != id_plataforma:
            self.ruta.append(id_plataforma)

    # Plataforma que sostiene los pies en (x, z) con altura `y`: la de cara superior más alta que no exceda
    # y + TOLERANCIA_ESCALON. Retorna (plataforma, y_superior) o (None, None).
    def _soporte(self, y):
        mejor, alto = None, None
        for p in self.nivel.plataformas.values():
            if not self.activa(p):
                continue
            px, py, pz = posicion_plataforma(p, self.t)
            if (abs(self.x - px) <= p.ancho / 2 + RADIO_JUGADOR and abs(self.z - pz) <= p.fondo / 2 + RADIO_JUGADOR
                    and py <= y + TOLERANCIA_ESCALON and (alto is None or py > alto)):
                mejor, alto = p, py
        return mejor, alto

    # Plataforma y altura de su cara superior bajo los pies ahora mismo (para la sombra del avatar). (None, None) en el vacío.
    def soporte_actual(self):
        return self._soporte(self.vertical.y)

    # El jugador pide volver al checkpoint (tecla R): cuenta como caída (penaliza igual). Retorna los eventos.
    def reaparecer_manual(self):
        eventos = []
        if not self.terminado:
            self._reaparecer(eventos)
        return eventos

    def _reaparecer(self, eventos):
        cp = self.nivel.plataformas[self.checkpoint]
        self.t += self.nivel.penalizacion_caida_s
        self.caidas += 1
        self.pisada_desaparece.pop(cp.id, None)
        px, py, pz = posicion_plataforma(cp, self.t)
        self.x, self.z = px, pz
        self.vertical.reiniciar(py)
        self.doble_usado = False
        self.sobre = cp.id
        if self.nivel.purga is not None:          # la purga se rearma: todo vuelve y empieza otra vez al pisar activa_en
            self.purga_t0 = None
            self.purga_acabada = False
        if resultado_v2_activo():
            self.ruta = ruta_tras_reaparecer(self.ruta, cp.id)
        else:
            self._registrar_nodo(cp.id)
        eventos.append("caida")

    # Un paso de `dt` s. (mx, mz) = dirección deseada en el mundo (se normaliza si pasa de 1); `salto` = pulsación.
    def paso(self, dt, mx=0.0, mz=0.0, salto=False):
        eventos = []
        if self.terminado or dt <= 0:
            return eventos
        antes = self.t
        self.t += dt

        for id_i, fin in list(self.interruptores.items()):
            if fin != math.inf and fin <= self.t and fin > antes:
                eventos.append(f"interruptor_apagado:{id_i}")

        # Arrastre de la plataforma móvil bajo los pies.
        previa = self.nivel.plataformas.get(self.sobre) if self.sobre else None
        if previa is not None and not self.vertical.en_aire and previa.tipo in MOVILES:
            ax, _, az = posicion_plataforma(previa, antes)
            bx, _, bz = posicion_plataforma(previa, self.t)
            self.x += bx - ax
            self.z += bz - az
        if previa is not None and not self.vertical.en_aire:
            if previa.tipo == "cinta" and previa.arrastre:          # la cinta arrastra (en el aire no)
                self.x += previa.arrastre[0] * dt
                self.z += previa.arrastre[1] * dt
            elif previa.tipo == "ritmo":                           # la barra sube o baja con el jugador encima
                self.vertical.y += posicion_plataforma(previa, self.t)[1] - posicion_plataforma(previa, antes)[1]

        largo = math.hypot(mx, mz)
        if largo > 1.0:
            mx, mz = mx / largo, mz / largo
        self.x += mx * VELOCIDAD * dt
        self.z += mz * VELOCIDAD * dt

        # Doble salto: una pulsación en el aire (fuera del coyote) da un único impulso extra por vuelo.
        v = self.vertical
        if (salto and v.en_aire and not self.doble_usado and (v.salto_usado or v.desde_suelo > TIEMPO_COYOTE)):
            v.vy = VELOCIDAD_SALTO
            v.memoria_salto = 0.0
            v.salto_usado = True
            self.doble_usado = True
            salto = False
            eventos.append("doble_salto")

        soporte, alto = self._soporte(v.y)
        objetivo = alto if soporte is not None else -1000.0
        salto_hecho, aterrizo = v.avanzar(objetivo, dt, pide_salto=salto, suavizar=False)
        if salto_hecho:
            eventos.append("salto")
        if aterrizo:
            self.doble_usado = False
            eventos.append("aterrizo")

        if soporte is not None and not v.en_aire:
            self.sobre = soporte.id
            self._registrar_nodo(soporte.id)
            if soporte.tipo == "desaparece" and soporte.id not in self.pisada_desaparece:
                self.pisada_desaparece[soporte.id] = self.t
            elif soporte.tipo == "desaparece" and fase_desaparece(
                    soporte, self.pisada_desaparece[soporte.id], self.t) == "solida":
                self.pisada_desaparece[soporte.id] = self.t      # reaparecida y pisada de nuevo: reinicia el ciclo
            if soporte.checkpoint and self.checkpoint != soporte.id:
                self.checkpoint = soporte.id
                eventos.append(f"checkpoint:{soporte.id}")
            purga = self.nivel.purga
            if purga is not None and soporte.id == purga["activa_en"] and self.purga_t0 is None:
                self.purga_t0 = self.t
                self.purga_acabada = False
                eventos.append("purga_inicio")
            if soporte.id == self.nivel.meta:
                self.terminado = True
                eventos.append("meta")
        elif v.en_aire:
            self.sobre = None

        if self.purga_t0 is not None and not self.purga_acabada and (
                self.terminado or self._frente() >= self.nivel.purga["z_fin"]):
            self.purga_acabada = True
            eventos.append("purga_fin")

        for sw in self.nivel.interruptores.values():
            if (math.hypot(self.x - sw.x, self.z - sw.z) <= sw.radio
                    and abs(v.y - sw.y) <= ALCANCE_INTERRUPTOR):
                ya = self.interruptor_activo(sw.id)
                self.interruptores[sw.id] = math.inf if sw.duracion_s is None else self.t + sw.duracion_s
                if not ya:
                    eventos.append(f"interruptor:{sw.id}")

        if v.y < self.nivel.y_muerte and not self.terminado:
            self._reaparecer(eventos)
        return eventos

    # Resultado de la carrera (solo tiene sentido con `terminado`).
    def resultado(self):
        return resultado_del_nivel(self.nivel, self.t, self.caidas, self.ruta)


# -- Textos del HUD (puros, para probarlos sin ventana) --

# «mm:ss.d» de un tiempo en segundos. Se redondea a décimas ANTES de partir en minutos: si no, 59,96 s salía
# como «00:60.0» en vez de «01:00.0».
def formatear_tiempo(segundos):
    decimas = int(round(max(0.0, segundos) * 10))
    minutos, resto = divmod(decimas, 600)
    return f"{minutos:02d}:{resto // 10:02d}.{resto % 10}"


# Ruta tras reaparecer en `checkpoint`: se recorta hasta la última vez que se pisó (el intento fallido desaparece de
# la ruta). Si el checkpoint no está en la ruta (no debería pasar), se añade al final como antes.
def ruta_tras_reaparecer(ruta, checkpoint):
    ruta = list(ruta)
    for i in range(len(ruta) - 1, -1, -1):
        if ruta[i] == checkpoint:
            return ruta[:i + 1]
    ruta.append(checkpoint)
    return ruta


# Parte una secuencia de ids en líneas de como mucho `maximo` caracteres, unidas por « > » (la flecha de la línea
# siguiente empieza con «> »). Un id más largo que `maximo` ocupa su propia línea.
def partir_ruta(ids, maximo=MAX_CARACTERES_RUTA):
    lineas, actual = [], ""
    for id_nodo in ids:
        trozo = str(id_nodo)
        candidato = f"{actual} > {trozo}" if actual else trozo
        if actual and len(candidato) > maximo:
            lineas.append(actual + " >")
            actual = trozo
        else:
            actual = candidato
    if actual:
        lineas.append(actual)
    return lineas


def _coste_texto(coste):
    return "sin datos" if coste is None else f"{coste:.1f} s"


# Textos del bloque «ruta Dijkstra» del panel final: (cabecera, [líneas de la ruta], pie). La ruta es la de
# REFERENCIA con la que se midió la eficiencia (la segura si la carrera fue segura y existe; si no, la óptima global).
# Total con datos incompletos: sin ruta dice que no hay ruta de referencia.
def textos_ruta_dijkstra(resultado, maximo=MAX_CARACTERES_RUTA):
    resultado = resultado or {}
    segura = resultado.get("categoria") != "dificil" and resultado.get("ruta_segura")
    if segura:
        ruta, coste, cual = resultado.get("ruta_segura") or [], resultado.get("coste_seguro"), "segura"
    else:
        ruta, coste, cual = resultado.get("ruta_optima") or [], resultado.get("coste_optimo"), "óptima"
    if not ruta:
        return "Ruta de referencia (Dijkstra): no hay ruta", [], ""
    cabecera = f"Ruta {cual} de referencia (Dijkstra, {_coste_texto(coste)}):"
    pie = f"Tu ruta: {_coste_texto(resultado.get('coste_real'))} en {max(0, len(resultado.get('ruta_real') or []) - 1)} saltos"
    return cabecera, partir_ruta(ruta, maximo), pie


NOMBRE_MEDALLA = {"bronce": "Bronce", "plata": "Plata", "oro": "Oro", None: "Ninguna"}
NOMBRE_CATEGORIA = {"facil": "Ruta segura", "dificil": "Ruta arriesgada"}

# Conducta de los NPC según su ESTADO emocional (Python puro: sin ursina ni panda3d). Punto 3 del plan final: lo que
# dicen los indicadores se tiene que NOTAR en cómo camina la gente, sin leer números.
#
# El estado de cada NPC sale de ambiente_ciudad.estado_npc(semilla, amb) ('sociable' | 'neutro' | 'celular' | 'aislado' |
# 'enojado'). Aquí se traduce a movimiento, como una VARIANTE de multitud_conducta.Conducta (que no se toca):
#
#   sociable  paso tranquilo; para más a menudo y mira alrededor; si lleva cerca a otro sociable que va en su sentido se
#             pone a su lado y acompasa el paso (caminan en pareja); si se cruza con otro sociable, a veces los dos se paran
#             unos segundos a CHARLAR, vueltos el uno hacia el otro.
#   neutro    exactamente la conducta de siempre.
#   celular   camina despacio y se para mucho y largo, sin mirar a los lados (va mirando la pantalla).
#   aislado   camina algo más lento, casi no se detiene y se ABRE de lado para no cruzarse con nadie (1,6 m en vez de 0,65).
#   enojado   camina rápido, no se detiene y no aguanta una cola: a los 2 s adelanta.
#
# El ritmo no salta: cada agente lleva su `ritmo` y lo acerca al de su estado a RITMO_POR_S por segundo.
#
# CAPA LOCAL. Como multitud_conducta, solo vive mientras el agente se dibuja y no viaja por la red. La posición canónica
# (multitud_calculos.posicion_en: función pura de (t, ruta, semilla)) NO cambia. Con `modular = False` (partida en línea)
# todos los métodos delegan en la clase base: el movimiento es idéntico al de antes y el estado solo sirve para la postura.
#
# Peatones del mundo chico (frontend/peatones.py): ritmo_de(estado) y parada_celular() dan lo mismo en pequeño.
#
#   c = ConductaConEstado(agentes)           # sustituye a multitud_conducta.Conducta(agentes)
#   c.fijar_ambiente(amb)                    # cada vez que cambia el Ambiente (barato: 5 sumas)
#   c.estado_de(i) -> estado                 # el del agente i con el último ambiente
#   c.modular = False                        # en línea

import math
from collections import namedtuple

from backend.logica import ambiente_ciudad as ac
from backend.logica import multitud_calculos as mc
from backend.logica import multitud_conducta as cd

SOCIABLE, NEUTRO, CELULAR, AISLADO, ENOJADO = "sociable", "neutro", "celular", "aislado", "enojado"

# ritmo: factor de la velocidad de paseo · ventana: factor del largo de la ventana de pausas (menor = más seguidas) ·
# prob: probabilidad de pausa por ventana · dur: (min, max) s · mirada: (min, max) grados a un lado al parar
Parametros = namedtuple("Parametros", "ritmo ventana prob dur mirada")

PARAMETROS = {
    SOCIABLE: Parametros(0.94, 0.8, 0.65, (3.0, 6.0), (50.0, 110.0)),
    NEUTRO: Parametros(1.0, 1.0, cd.PROBABILIDAD_PAUSA, cd.DURACION_PAUSA, cd.MIRADA_PAUSA),
    CELULAR: Parametros(0.70, 0.5, 0.85, (4.0, 8.0), (0.0, 0.0)),
    AISLADO: Parametros(0.86, 1.3, 0.2, (2.0, 3.5), (10.0, 25.0)),
    ENOJADO: Parametros(1.30, 1.6, 0.08, (1.2, 2.0), (20.0, 40.0)),
}

RITMO_POR_S = 0.35              # cuánto puede cambiar el ritmo de un agente en un segundo (sin tirones al cambiar de estado)

# Sociables
RADIO_COMPANIA = 3.0            # m: a esta distancia busca a otro sociable
HOMBRO_COMPANIA = 0.8           # m de lado a los que camina de su pareja
G_ALCANZAR, G_ESPERAR = 1.14, 0.84     # factores de ritmo para alcanzar al que va delante / esperar al que viene detrás
ADELANTE_COMPANIA = 0.7         # m por delante o por detrás a partir de los que corrige el paso
RADIO_CHARLA = 2.4              # m: dos sociables así de cerca pueden pararse a charlar
PROBABILIDAD_CHARLA = 0.55      # por encuentro (determinista por pareja y tramo de reloj)
TRAMO_CHARLA = 20.0             # s: una pareja tira el dado una vez por tramo
DURACION_CHARLA = (4.0, 8.0)    # s
DESCANSO_CHARLA = 25.0          # s sin otra charla

# Aislados
RADIO_EVITAR = 3.0              # m por delante a los que empieza a abrirse
HOMBRO_EVITAR = 1.6             # m de lado que quiere dejar con cualquiera

# Enojados
PACIENCIA_ENOJADO = 2.0         # s en cola antes de adelantar (la base aguanta PACIENCIA_AGENTE = 8)

ALCANCE_CELDAS = 2              # celdas a cada lado que se miran al buscar compañía (CELDA = 1,5 m -> 3 m asegurados)


def ritmo_de(estado):
    """Factor de la velocidad de paseo del estado (1.0 para lo desconocido)."""
    p = PARAMETROS.get(estado)
    return 1.0 if p is None else p.ritmo


def acercar(actual, objetivo, dt, por_segundo=RITMO_POR_S):
    """`actual` movido hacia `objetivo` como mucho `por_segundo * dt`."""
    paso = por_segundo * max(0.0, dt)
    if objetivo > actual:
        return min(objetivo, actual + paso)
    return max(objetivo, actual - paso)


def pausa_de_estado(semilla, t, estado):
    """Como multitud_conducta.pausa_local pero con los parámetros del estado: (inicio, fin, mirada) de la pausa del agente
    en la ventana que contiene `t`, o None. Determinista por (semilla, t, estado). Con 'neutro' es pausa_local."""
    p = PARAMETROS.get(estado)
    if p is None or estado == NEUTRO:
        return cd.pausa_local(semilla, t)
    largo, fase, k = _ventana(semilla, t, p)
    if mc._u(semilla, 3 * k + 100) >= p.prob:
        return None
    dur = p.dur[0] + (p.dur[1] - p.dur[0]) * mc._u(semilla, 3 * k + 101)
    u = mc._u(semilla, 3 * k + 102)
    inicio = (k - fase) * largo + 0.1 * largo + u * (0.8 * largo - dur)
    mirada = p.mirada[0] + (p.mirada[1] - p.mirada[0]) * mc._u(semilla, 3 * k + 103)
    return (inicio, inicio + dur, mirada if u < 0.5 else -mirada)


def _ventana(semilla, t, p):
    largo = (cd.VENTANA_PAUSA[0] + (cd.VENTANA_PAUSA[1] - cd.VENTANA_PAUSA[0]) * mc._u(semilla, 20)) * p.ventana
    fase = mc._u(semilla, 21)
    return largo, fase, math.floor(t / largo + fase)


def charla_de_pareja(semilla_a, semilla_b, t):
    """Duración (s) de la charla que empiezan los agentes de esas semillas si se encuentran en el instante `t`, o None si
    en este tramo de reloj no charlan. Simétrica y determinista."""
    a, b = (semilla_a, semilla_b) if semilla_a <= semilla_b else (semilla_b, semilla_a)
    mezcla = (a * 0x9E3779B1 + b) & 0xFFFFFFFFFFFF
    tramo = math.floor(t / TRAMO_CHARLA)
    if mc._u(mezcla, 2 * tramo + 400) >= PROBABILIDAD_CHARLA:
        return None
    return DURACION_CHARLA[0] + (DURACION_CHARLA[1] - DURACION_CHARLA[0]) * mc._u(mezcla, 2 * tramo + 401)


def parada_celular(semilla, t):
    """Para los peatones del mundo chico: (inicio, fin) de la parada «mirando el celular» de la ventana que contiene `t`,
    o None. Es la pausa del estado 'celular' sin la mirada."""
    pausa = pausa_de_estado(semilla, t, CELULAR)
    return None if pausa is None else (pausa[0], pausa[1])


def cortes_de(amb):
    """Límites acumulados de los estados sobre el eje 0..1 de cada NPC: [(limite, estado), ...] en el orden de
    ambiente_ciudad.ESTADOS_NPC. estado_con_cortes(u, cortes) == ambiente_ciudad.estado_npc(semilla, amb)."""
    acumulado, cortes = 0.0, []
    for estado, probabilidad in ac.probabilidades_npc(amb).items():
        acumulado += probabilidad
        cortes.append((acumulado, estado))
    return cortes


def estado_con_cortes(u, cortes):
    for limite, estado in cortes:
        if u < limite:
            return estado
    return ac.ESTADOS_NPC[-1]


class ConductaConEstado(cd.Conducta):
    """multitud_conducta.Conducta + conducta por estado emocional. Sin llamar a fijar_ambiente (o con modular = False)
    se comporta EXACTAMENTE como la base."""

    def __init__(self, agentes):
        super().__init__(agentes)
        n = len(agentes)
        self.modular = True
        self.umbral_npc = [ac.umbral_npc(a.semilla) for a in agentes]      # el u fijo de cada NPC (no cambia nunca)
        self._cortes = None                                                  # None = sin ambiente: todos neutros
        self.estado = [NEUTRO] * n
        self.ritmo = [1.0] * n
        self.charla_hasta = [-1e18] * n
        self.charla_con = [-1] * n
        self.descanso_charla = [-1e18] * n
        self.charlas = 0                                                     # charlas empezadas (diagnóstico)

    # -- Estado --

    def fijar_ambiente(self, amb):
        """Nuevo Ambiente: recalcula el estado de TODOS los agentes (n comparaciones; llamar cuando cambie, no por frame)."""
        self._cortes = cortes_de(amb)
        cortes, u, estado = self._cortes, self.umbral_npc, self.estado
        for i in range(len(estado)):
            estado[i] = estado_con_cortes(u[i], cortes)

    def estado_de(self, i):
        return self.estado[i]

    def charlando(self, i, t):
        return self.charla_hasta[i] > t

    def entrar(self, i, t):
        super().entrar(i, t)
        self.ritmo[i] = PARAMETROS[self.estado[i]].ritmo if self.modular else 1.0
        self.charla_hasta[i], self.charla_con[i], self.descanso_charla[i] = -1e18, -1, -1e18

    # -- Pausas por estado --

    def _pausa_de(self, i, t):
        estado = self.estado[i]
        if not self.modular or estado == NEUTRO:
            return super()._pausa_de(i, t)
        guardada = self._pausa[i]
        if guardada is not None and len(guardada) == 4 and guardada[3] == estado and guardada[0] <= t < guardada[1]:
            return guardada[2]
        semilla = self.agentes[i].semilla
        largo, fase, k = _ventana(semilla, t, PARAMETROS[estado])
        pausa = pausa_de_estado(semilla, t, estado)
        self._pausa[i] = ((k - fase) * largo, (k + 1 - fase) * largo, pausa, estado)
        return pausa

    # -- Percepción --

    def percibir(self, i, t, jugador=None):
        if not self.modular:
            return super().percibir(i, t, jugador)
        estado = self.estado[i]
        if estado != NEUTRO and len(self._pausa[i] or ()) == 3:
            self._pausa[i] = None                          # la ventana guardada era de la conducta base: se recalcula
        elif estado == NEUTRO and len(self._pausa[i] or ()) == 4:
            self._pausa[i] = None
        paso = t - self.t_perc[i]
        if paso < 0.0 or paso > 1.0:
            paso = 0.1
        super().percibir(i, t, jugador)
        ritmo = self.ritmo[i] = acercar(self.ritmo[i], PARAMETROS[estado].ritmo, paso)
        g = self.g_obj[i]
        andando = g == 1.0 or g == cd.G_RECUPERA           # la base lo deja caminar a su aire (o recuperando retraso)
        if andando and ritmo != 1.0:
            self.libre[i] = True                           # deja de perseguir al reloj canónico: lleva su propio paso
            self.g_obj[i] = ritmo
        if estado == ENOJADO:
            if self.cola[i] > PACIENCIA_ENOJADO:
                self.cola[i] = 0.0
                self.ignora_hasta[i] = t + cd.IGNORAR_AGENTES
            return
        if estado != SOCIABLE and estado != AISLADO:
            return
        if jugador is not None:
            dx, dz = jugador[0] - self.x[i], jugador[1] - self.z[i]
            if dx * dx + dz * dz < cd.RADIO_JUGADOR * cd.RADIO_JUGADOR:
                if estado == SOCIABLE and self.charla_hasta[i] > t and self.bloqueo[i] <= 0.0:
                    self._seguir_charla(i, t)
                return                                     # con el jugador cerca manda la conducta base (ceder, esquivar)
        if estado == SOCIABLE:
            self._socializar(i, t, andando)
        else:
            self._evitar(i)

    def _vecinos(self, i, radio):
        """Agentes activos a menos de `radio` m del agente i: [(j, adelante, lado, d2)] en sus ejes (lado + = izquierda)."""
        x, z = self.x[i], self.z[i]
        fx, fz = self.fx[i], self.fz[i]
        kx, kz = math.floor(x / cd.CELDA), math.floor(z / cd.CELDA)
        celdas, xs, zs = self._celdas, self.x, self.z
        r2 = radio * radio
        cerca = []
        for cx in range(kx - ALCANCE_CELDAS, kx + ALCANCE_CELDAS + 1):
            for cz in range(kz - ALCANCE_CELDAS, kz + ALCANCE_CELDAS + 1):
                lista = celdas.get((cx, cz))
                if not lista:
                    continue
                for j in lista:
                    if j == i or j not in self.activos:
                        continue
                    dx, dz = xs[j] - x, zs[j] - z
                    d2 = dx * dx + dz * dz
                    if d2 < r2:
                        cerca.append((j, dx * fx + dz * fz, dz * fx - dx * fz, d2))
        return cerca

    def _seguir_charla(self, i, t):
        """En plena charla: parado y vuelto hacia su pareja. Devuelve False si la charla se acabó (la pareja se fue)."""
        j = self.charla_con[i]
        if j < 0 or j not in self.activos or self.charla_hasta[j] <= t:
            self.charla_hasta[i] = -1e18
            return False
        dx, dz = self.x[j] - self.x[i], self.z[j] - self.z[i]
        if dx * dx + dz * dz > (RADIO_CHARLA + 1.5) ** 2:
            self.charla_hasta[i] = -1e18
            return False
        self.g_obj[i] = 0.0
        self.mirada[i] = cd._angulo(math.degrees(math.atan2(dx, dz)) - self.rumbo_camino[i])
        return True

    def _socializar(self, i, t, andando):
        if self.charla_hasta[i] > t and self._seguir_charla(i, t):
            return
        cerca = [v for v in self._vecinos(i, RADIO_COMPANIA) if self.estado[v[0]] == SOCIABLE]
        if not cerca:
            return
        j, ade, lat, d2 = min(cerca, key=lambda v: v[3])
        if (d2 < RADIO_CHARLA * RADIO_CHARLA and t >= self.descanso_charla[i] and t >= self.descanso_charla[j]
                and self.charla_hasta[j] <= t and self.bloqueo[i] <= 0.0 and self.bloqueo[j] <= 0.0):
            dur = charla_de_pareja(self.agentes[i].semilla, self.agentes[j].semilla, t)
            if dur is not None:
                for a, b in ((i, j), (j, i)):
                    self.charla_hasta[a], self.charla_con[a] = t + dur, b
                    self.descanso_charla[a] = t + dur + DESCANSO_CHARLA
                self.charlas += 1
                self._seguir_charla(i, t)
                return
            self.descanso_charla[i] = self.descanso_charla[j] = (math.floor(t / TRAMO_CHARLA) + 1) * TRAMO_CHARLA
        if not andando or not self.mov[j]:
            return
        if self.fx[i] * self.fx[j] + self.fz[i] * self.fz[j] < 0.5:
            return                                         # va en otro sentido: se cruzan y ya
        ritmo = self.ritmo[i]
        if ade > ADELANTE_COMPANIA:
            self.g_obj[i] = ritmo * G_ALCANZAR
        elif ade < -ADELANTE_COMPANIA:
            self.g_obj[i] = ritmo * G_ESPERAR
        self.libre[i] = True
        lado = HOMBRO_COMPANIA if lat >= 0.0 else -HOMBRO_COMPANIA
        self.dd_obj[i], self.v_lat[i] = self._corrimiento(i, lat - lado), cd.VEL_LATERAL

    def _evitar(self, i):
        empuje = 0.0
        for j, ade, lat, d2 in self._vecinos(i, RADIO_EVITAR):
            if ade < -0.5 or lat <= -HOMBRO_EVITAR or lat >= HOMBRO_EVITAR:
                continue
            if lat > 0.05 or (lat >= -0.05 and i > j):
                empuje += lat - HOMBRO_EVITAR
            else:
                empuje += lat + HOMBRO_EVITAR
        if empuje > cd.EMPUJE_MINIMO or empuje < -cd.EMPUJE_MINIMO:
            self.dd_obj[i], self.v_lat[i] = self._corrimiento(i, empuje), cd.VEL_LATERAL


# -- Estados sin conducta (multitud con la conducta apagada, peatones del mundo chico) ---------------------------------------

class EstadosNPC:
    """El estado emocional de una lista de NPC identificados por su semilla (int, str o tupla). Mismo resultado que
    ambiente_ciudad.estado_npc, pero con el umbral de cada uno calculado una sola vez."""

    def __init__(self, semillas):
        self.umbral_npc = [ac.umbral_npc(s) for s in semillas]
        self.estado = [NEUTRO] * len(self.umbral_npc)

    def fijar_ambiente(self, amb):
        cortes = cortes_de(amb)
        for i, u in enumerate(self.umbral_npc):
            self.estado[i] = estado_con_cortes(u, cortes)

    def estado_de(self, i):
        return self.estado[i]


# -- Cantidad de gente en la calle (punto 5) ---------------------------------------------------------------------------------

def factor_poblacion(amb, hora=None):
    """Fracción (0..1) de la población que está en la calle: la densidad del ambiente (0,35 ciudad rota .. 1,0 ciudad
    plena) por el factor horario de la multitud (`hora` de juego 0..24; None = sin reloj, no recorta)."""
    return ac.densidad_poblacion(amb) * mc.factor_horario(hora)


def activos_por_factor(umbrales, factor):
    """[bool] por NPC: está en la calle si su umbral FIJO queda por debajo del factor. Al bajar el factor desaparecen
    siempre los mismos y al subir vuelven los mismos (no se baraja a nadie)."""
    return [u < factor for u in umbrales]


def umbrales_repartidos(semillas):
    """Umbrales fijos 0..1 REPARTIDOS por igual ((rango + 0,5) / n, con el rango según umbral_npc): para grupos pequeños
    (los 12 peatones del mundo chico), donde unos umbrales al azar podrían quedar todos altos o todos bajos."""
    us = [ac.umbral_npc(s) for s in semillas]
    orden = sorted(range(len(us)), key=us.__getitem__)
    reparto = [0.0] * len(us)
    for rango, i in enumerate(orden):
        reparto[i] = (rango + 0.5) / len(us)
    return reparto

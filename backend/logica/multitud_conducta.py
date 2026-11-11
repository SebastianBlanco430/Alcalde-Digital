# Conducta local de la multitud (Python puro: NO importa ursina ni panda3d). Una capa fina sobre la posición ANALÍTICA
# de backend/logica/multitud_calculos.py, solo para los agentes que se DIBUJAN (niveles A y B, unos 40 como mucho):
#
#   - ceder el paso / esquivar al jugador: si lo tiene delante frena y se aparta de lado; si no hay sitio y el jugador
#     sigue ahí pasada la paciencia, da media vuelta (replanifica) en vez de atravesarlo o quedarse trabado;
#   - separación entre agentes (rejilla espacial de CELDA m): hace cola detrás del que va delante o está parado y se
#     abre de lado si se solapa con otro;
#   - pausas ocasionales a mitad de camino (se detiene, mira a un lado y sigue), deterministas por (semilla, reloj);
#   - arranque y frenada progresivos, y giro suave del cuerpo (sin saltos de rumbo en las esquinas).
#
# Cómo se mantiene dentro de la calle SIN consultar colisiones por frame: el agente nunca sale de la banda que su ruta ya
# validó contra mundo.es_transitable. Solo se cambian dos cosas de la evaluación analítica:
#   tau  s de retraso respecto al reloj canónico (frenar = tau crece; recuperar = camina algo más rápido hasta tau = 0)
#   dd   corrimiento del desvío lateral relativo, con d + dd siempre en [DESVIO_MIN, DESVIO_MAX] (lo validado)
# La media vuelta es otro punto del MISMO circuito (el simétrico: misma calle, otra acera, sentido contrario); el cambio
# de acera se anima con un residuo (ox, oz) que se consume andando.
#
# El estado es LOCAL y efímero: nace al dibujarse el agente (entrar) y muere al dejar de dibujarse (salir), así que el
# reloj compartido sigue mandando (dos equipos ven casi lo mismo y nada viaja por la red). Coste: avanzar() es O(1) por
# agente y frame (una evaluación analítica, la misma que ya se hacía); percibir() es O(vecinos de 9 celdas) y se llama
# escalonado (cada agente una vez cada PERIODO frames). Sin raycasts ni consultas al mundo.

import math

from backend.logica import multitud_calculos as mc

PERIODO = 6                     # frames entre dos percepciones de un mismo agente (escalonadas por índice)
CELDA = 1.5                     # m de la rejilla espacial
DESVIO_MIN, DESVIO_MAX = 0.15, 1.0            # banda de desvío relativo validada por multitud_calculos
BANDA_MINIMA = 0.2              # m: con menos banda útil el agente no se mueve de lado

# Marcha
ACELERACION, FRENADA = 2.2, 3.5               # por s, en unidades del factor de marcha g (0 = parado, 1 = su paso)
G_RECUPERA = 1.18               # factor con el que recupera el retraso
G_PRISA = 1.3                   # si el jugador le empuja por detrás
RETRASO_RECUPERABLE = 30.0      # s: con más retraso deja de intentar alcanzar al reloj (queda libre hasta dejar de verse)
VEL_LATERAL = 0.7               # m/s al apartarse de lado
VEL_LATERAL_VUELTA = 0.15       # m/s al volver a su carril
VEL_RESIDUO = 1.2               # m/s con la que cruza de acera tras la media vuelta
VEL_MOVIMIENTO = (0.15, 0.3)    # m/s: por debajo del primero está parado; por encima del segundo, andando (histéresis)
VEL_MAXIMA = 2.6                # m/s: tope de la velocidad que se anima (un tirón del reloj no dispara la marcha)

# Giro
GIRO_RAPIDEZ = 7.0              # 1/s: fracción del giro pendiente que se hace por segundo
GIRO_MAXIMO = 300.0             # grados/s

# Jugador
RADIO_JUGADOR = 6.0             # m: más lejos se ignora
D_ESQUIVA = 4.5                 # m por delante a los que empieza a apartarse
ANCHO_PASO = 1.0                # m a cada lado del rumbo: el pasillo en el que el jugador estorba
PASO_LIBRE = 0.85               # m de separación lateral que busca al pasar junto al jugador
PASO_MINIMO = 0.65              # m: con menos sitio que este no intenta pasar (cede el paso y, si sigue ahí, da la vuelta)
D_CEDER = 1.5                   # m por delante a los que se para
D_FRENAR = 3.0                  # m por delante a los que afloja el paso
ANCHO_CEDER = 0.6               # m a cada lado: tan centrado se para (más abierto solo se aparta)
RADIO_ROCE = 0.8                # m: el jugador pegado por un lado o por detrás
PACIENCIA_JUGADOR = 3.5         # s parado ante el jugador sin poder rodearlo antes de dar media vuelta
PACIENCIA_MAXIMA = 7.0          # s parado ante el jugador (aunque quepa rodearlo) antes de dar media vuelta
DESCANSO_VUELTA = 10.0          # s sin otra media vuelta

# Agentes
RADIO_VECINO = 1.5              # m (no mayor que CELDA: se miran las 9 celdas de alrededor)
D_COLA = 0.9                    # m por delante a los que se para detrás de otro
D_COLA_LENTA = 1.4              # m por delante a los que afloja el paso
ANCHO_COLA = 0.45               # m a cada lado: tan alineado hace cola
HOMBRO = 0.65                   # m de separación lateral que busca con otro agente
D_SOLAPE = 0.45                 # m por delante por debajo de los cuales ya no hace cola (se solapan: sigue y se abre)
EMPUJE_MINIMO = 0.03            # m: empuje lateral por debajo del cual conserva el carril que lleva
PASO_SEPARAR = 0.35             # m que se aparta del jugador que le roza
MARGEN_PARADA = 0.3             # s de parada que siempre conserva al descontar lo ya esperado
PACIENCIA_AGENTE = 8.0         # s en cola antes de ignorar a los agentes
IGNORAR_AGENTES = 6.0           # s que los ignora

# Pausas a mitad de camino (deterministas: mismas en todos los equipos)
VENTANA_PAUSA = (40.0, 75.0)    # s de la ventana de cada agente
PROBABILIDAD_PAUSA = 0.5        # de que en una ventana haya pausa
DURACION_PAUSA = (2.5, 5.5)     # s
MIRADA_PAUSA = (45.0, 100.0)    # grados a un lado a los que mira


def _angulo(a):
    return (a + 180.0) % 360.0 - 180.0


def girar_suave(actual, objetivo, dt, rapidez=GIRO_RAPIDEZ, maximo=GIRO_MAXIMO):
    """Nuevo rumbo (grados) hacia `objetivo` por el camino corto: proporcional a lo que falta y nunca más de `maximo`
    grados/s. Sin saltos aunque el objetivo cambie de golpe."""
    falta = _angulo(objetivo - actual)
    k = rapidez * dt
    paso = falta * (1.0 if k > 1.0 else k)
    tope = maximo * dt
    if paso > tope:
        paso = tope
    elif paso < -tope:
        paso = -tope
    return _angulo(actual + paso)


def pausa_local(semilla, t):
    """(inicio, fin, mirada): la pausa a mitad de camino del agente `semilla` en la ventana que contiene `t` (instantes
    absolutos del reloj; mirada en grados, con signo), o None si en esa ventana no para. Determinista."""
    largo = VENTANA_PAUSA[0] + (VENTANA_PAUSA[1] - VENTANA_PAUSA[0]) * mc._u(semilla, 20)
    fase = mc._u(semilla, 21)
    k = math.floor(t / largo + fase)
    if mc._u(semilla, 3 * k + 100) >= PROBABILIDAD_PAUSA:
        return None
    dur = DURACION_PAUSA[0] + (DURACION_PAUSA[1] - DURACION_PAUSA[0]) * mc._u(semilla, 3 * k + 101)
    u = mc._u(semilla, 3 * k + 102)
    inicio = (k - fase) * largo + 0.1 * largo + u * (0.8 * largo - dur)
    mirada = MIRADA_PAUSA[0] + (MIRADA_PAUSA[1] - MIRADA_PAUSA[0]) * mc._u(semilla, 3 * k + 103)
    return (inicio, inicio + dur, mirada if u < 0.5 else -mirada)


def banda_de(ruta):
    """Metros de desvío lateral por unidad de desvío relativo en `ruta` (0 si la ruta se validó sin desvío)."""
    return ruta.escala * min(math.hypot(nx, nz) for nx, nz in ruta.n_sal)


class Conducta:
    """Estado local de los agentes dibujados. Tras avanzar(i, t, dt) el agente `i` está en (x[i], z[i]) mirando a
    rumbo[i], con velocidad vel[i] (m/s, para la animación), mov[i] (¿anda?) y dist[i] (m recorridos del circuito)."""

    def __init__(self, agentes):
        n = len(agentes)
        self.agentes = agentes
        self.activos = set()
        self.x, self.z, self.rumbo = [0.0] * n, [0.0] * n, [0.0] * n
        self.vel, self.mov, self.dist = [0.0] * n, [False] * n, [0.0] * n
        self.tau, self.g, self.g_obj = [0.0] * n, [1.0] * n, [1.0] * n
        self.dd, self.dd_obj, self.v_lat = [0.0] * n, [0.0] * n, [VEL_LATERAL_VUELTA] * n
        self.ox, self.oz = [0.0] * n, [0.0] * n
        self.libre = [False] * n
        self.fx, self.fz = [0.0] * n, [1.0] * n              # rumbo del camino (unitario)
        self.rumbo_camino = [0.0] * n
        self.mirada = [0.0] * n
        self.bloqueo, self.cola = [0.0] * n, [0.0] * n       # s parado ante el jugador / en cola tras otro agente
        self.ignora_hasta, self.vuelta_desde = [0.0] * n, [-1e18] * n
        self.t_perc = [0.0] * n
        self._pausa = [None] * n                             # (ventana k, pausa o None)
        bandas = {}
        self.banda = []
        for a in agentes:
            if a.ruta.clave not in bandas:
                bandas[a.ruta.clave] = banda_de(a.ruta)
            self.banda.append(bandas[a.ruta.clave])
        self._d0 = [mc._parametros(a.ruta, a.semilla)[3] for a in agentes]
        self._celdas = {}
        self.vueltas = 0                                     # medias vueltas dadas (diagnóstico)

    # -- Alta y baja --

    def entrar(self, i, t):
        """El agente `i` empieza a dibujarse: estado limpio, en su posición canónica."""
        a = self.agentes[i]
        e = mc.posicion_en(t, a.ruta, a.semilla)
        self.x[i], self.z[i], self.rumbo[i] = e[0], e[1], e[2]
        self.vel[i], self.mov[i], self.dist[i] = e[3], e[4], e[5]
        self.tau[i], self.g[i], self.g_obj[i] = 0.0, 1.0, 1.0
        self.dd[i], self.dd_obj[i], self.v_lat[i] = 0.0, 0.0, VEL_LATERAL_VUELTA
        self.ox[i] = self.oz[i] = 0.0
        self.libre[i] = False
        r = math.radians(e[2])
        self.fx[i], self.fz[i], self.rumbo_camino[i] = math.sin(r), math.cos(r), e[2]
        self.mirada[i] = 0.0
        self.bloqueo[i] = self.cola[i] = 0.0
        self.ignora_hasta[i], self.vuelta_desde[i] = 0.0, -1e18
        self.t_perc[i] = t
        self.activos.add(i)

    def salir(self, i):
        self.activos.discard(i)

    # -- Rejilla --

    def reindexar(self):
        """Rehace la rejilla con las posiciones actuales de los agentes activos (una vez por ciclo de percepción)."""
        celdas = self._celdas
        if len(celdas) > 512:
            celdas.clear()
        else:
            for lista in celdas.values():
                lista.clear()
        x, z = self.x, self.z
        for i in self.activos:
            clave = (math.floor(x[i] / CELDA), math.floor(z[i] / CELDA))
            lista = celdas.get(clave)
            if lista is None:
                celdas[clave] = [i]
            else:
                lista.append(i)

    # -- Percepción (escalonada) --

    def percibir_tanda(self, fase, t, jugador=None):
        """Percibe los agentes activos cuyo índice cae en la tanda `fase` (0..PERIODO-1). Con fase 0 rehace la rejilla."""
        if fase == 0:
            self.reindexar()
        for i in self.activos:
            if i % PERIODO == fase:
                self.percibir(i, t, jugador)

    def _limites(self, i):
        d0 = self._d0[i]
        return DESVIO_MIN - d0, DESVIO_MAX - d0

    def _corrimiento(self, i, metros):
        """Corrimiento relativo (dd) que equivale a `metros` de más (izquierda +) sobre el actual, dentro de la banda."""
        banda = self.banda[i]
        if banda < BANDA_MINIMA:
            return self.dd[i]
        lo, hi = self._limites(i)
        dd = self.dd[i] + metros / banda
        return lo if dd < lo else hi if dd > hi else dd

    def _esquiva_jugador(self, i, lat):
        """(dd objetivo, cabe): hacia dónde apartarse de un jugador que está `lat` m a la izquierda (+) del agente para
        dejar PASO_LIBRE m; `cabe` dice si la banda da para tanto."""
        banda = self.banda[i]
        if banda < BANDA_MINIMA:
            return self.dd[i], False
        lo, hi = self._limites(i)
        actual = self.dd[i]
        derecha = actual + (lat - PASO_LIBRE) / banda           # deja al jugador a la izquierda
        izquierda = actual + (lat + PASO_LIBRE) / banda         # deja al jugador a la derecha
        cabe_d, cabe_i = derecha >= lo - 1e-9, izquierda <= hi + 1e-9
        if cabe_d and cabe_i:
            return (derecha if actual - derecha <= izquierda - actual else izquierda), True
        if cabe_d:
            return max(lo, derecha), True
        if cabe_i:
            return min(hi, izquierda), True
        # No cabe con la separación cómoda: se pega al lado que deja más sitio; si aun así quedan PASO_MINIMO m, pasa.
        sitio_d = lat + (actual - lo) * banda                   # m que quedarían entre los dos yendo a la derecha
        sitio_i = (hi - actual) * banda - lat
        if sitio_d >= sitio_i:
            return lo, sitio_d >= PASO_MINIMO
        return hi, sitio_i >= PASO_MINIMO

    def _pausa_de(self, i, t):
        guardada = self._pausa[i]
        if guardada is not None and guardada[0] <= t < guardada[1]:
            return guardada[2]
        a = self.agentes[i]
        largo = VENTANA_PAUSA[0] + (VENTANA_PAUSA[1] - VENTANA_PAUSA[0]) * mc._u(a.semilla, 20)
        fase = mc._u(a.semilla, 21)
        k = math.floor(t / largo + fase)
        pausa = pausa_local(a.semilla, t)
        self._pausa[i] = ((k - fase) * largo, (k + 1 - fase) * largo, pausa)
        return pausa

    def percibir(self, i, t, jugador=None):
        """Decide la marcha (g_obj) y el carril (dd_obj) del agente `i` para los próximos frames."""
        paso = t - self.t_perc[i]
        self.t_perc[i] = t
        if paso < 0.0 or paso > 1.0:
            paso = 0.1
        x, z = self.x[i], self.z[i]
        r = math.radians(self.rumbo_camino[i])
        fx, fz = math.sin(r), math.cos(r)
        self.fx[i], self.fz[i] = fx, fz
        g = 1.0
        dd_obj = None
        mirada = 0.0
        ante_jugador = en_cola = False

        pausa = self._pausa_de(i, t)
        if pausa is not None and pausa[0] <= t < pausa[1]:
            g, mirada = 0.0, pausa[2]

        if jugador is not None:
            dx, dz = jugador[0] - x, jugador[1] - z
            d2 = dx * dx + dz * dz
            if d2 < RADIO_JUGADOR * RADIO_JUGADOR:
                ade, lat = dx * fx + dz * fz, dz * fx - dx * fz
                if 0.0 < ade < D_ESQUIVA and -ANCHO_PASO < lat < ANCHO_PASO:
                    dd_obj, cabe = self._esquiva_jugador(i, lat)
                    if -ANCHO_CEDER < lat < ANCHO_CEDER:
                        if ade < D_CEDER:
                            g, mirada, ante_jugador = 0.0, 0.0, True
                            self.bloqueo[i] += paso
                            limite = PACIENCIA_MAXIMA if cabe else PACIENCIA_JUGADOR
                            if self.bloqueo[i] > limite and t - self.vuelta_desde[i] > DESCANSO_VUELTA:
                                self.media_vuelta(i, t)
                                return
                        elif ade < D_FRENAR and g > 0.6:
                            g = 0.6
                elif d2 < RADIO_ROCE * RADIO_ROCE:               # pegado por un lado o por detrás: se aparta
                    dd_obj = self._corrimiento(i, -PASO_SEPARAR if lat >= 0.0 else PASO_SEPARAR)
                    if ade <= 0.0:
                        g, mirada = G_PRISA, 0.0
        if not ante_jugador and self.bloqueo[i] > 0.0:
            self.bloqueo[i] = max(0.0, self.bloqueo[i] - paso)

        if t >= self.ignora_hasta[i]:
            kx, kz = math.floor(x / CELDA), math.floor(z / CELDA)
            celdas = self._celdas
            xs, zs = self.x, self.z
            empuje = 0.0
            cerca = False
            for cx in (kx - 1, kx, kx + 1):
                for cz in (kz - 1, kz, kz + 1):
                    lista = celdas.get((cx, cz))
                    if not lista:
                        continue
                    for j in lista:
                        if j == i:
                            continue
                        dx, dz = xs[j] - x, zs[j] - z
                        d2 = dx * dx + dz * dz
                        if d2 >= RADIO_VECINO * RADIO_VECINO:
                            continue
                        ade, lat = dx * fx + dz * fz, dz * fx - dx * fz
                        if ade <= -0.2:
                            continue                             # va detrás: es él quien me esquiva
                        cerca = True
                        fxj, fzj = self.fx[j], self.fz[j]
                        de_frente = fx * fxj + fz * fzj < -0.3 and self.mov[j]
                        alineado = -ANCHO_COLA < lat < ANCHO_COLA
                        # Solo hace cola si el otro aún está DELANTE con hueco: si ya se solapan, pararse los dejaría
                        # encimados hasta agotar la paciencia; es mejor seguir andando y abrirse de lado.
                        if ade > D_SOLAPE and not de_frente and alineado:
                            ade_j = -(dx * fxj + dz * fzj)
                            if not (ade_j > 0.05 and i < j):     # si los dos se ven delante, pasa el de índice menor
                                en_cola = True
                                freno = 0.0 if ade < D_COLA else 0.5 if ade < D_COLA_LENTA else 1.0
                                if g > freno:
                                    g = freno
                        if -HOMBRO < lat < HOMBRO:               # se abre de lado (suma de todos los vecinos)
                            if lat > 0.05 or (lat >= -0.05 and i > j):
                                empuje += lat - HOMBRO
                            else:
                                empuje += lat + HOMBRO
            if dd_obj is None and cerca:
                if empuje > EMPUJE_MINIMO or empuje < -EMPUJE_MINIMO:
                    dd_obj = self._corrimiento(i, empuje)
                else:
                    dd_obj = self.dd[i]                          # entre dos: conserva el carril (sin vaivén)
        if en_cola:
            self.cola[i] += paso
            if self.cola[i] > PACIENCIA_AGENTE:
                self.cola[i] = 0.0
                self.ignora_hasta[i] = t + IGNORAR_AGENTES
        elif self.cola[i] > 0.0:
            self.cola[i] = max(0.0, self.cola[i] - paso)

        # Lo que ya esperó (en una cola, cediendo el paso) cuenta como parada: si llega con retraso a una parada de su
        # ruta, la acorta. Adelantar el reloj mientras está quieto en el vértice no lo mueve de sitio.
        if self.tau[i] > MARGEN_PARADA and not self.mov[i] and self.ox[i] == 0.0 and self.oz[i] == 0.0:
            a = self.agentes[i]
            v, f, fase, _ = mc._parametros(a.ruta, a.semilla)
            ciclo = a.ruta.total_tiempo / v + f * a.ruta.total_pausas
            resto = mc.pausa_restante(a.ruta, (t - self.tau[i] + fase * ciclo) % ciclo, v, f) - MARGEN_PARADA
            if resto > 0.0:
                self.tau[i] -= resto if resto < self.tau[i] else self.tau[i]

        if g == 1.0 and not self.libre[i] and self.tau[i] > 0.05:
            if self.tau[i] < RETRASO_RECUPERABLE:
                g = G_RECUPERA
            else:
                self.libre[i] = True
        self.g_obj[i] = g
        self.mirada[i] = mirada
        if dd_obj is None:
            self.dd_obj[i], self.v_lat[i] = 0.0, VEL_LATERAL_VUELTA
        else:
            self.dd_obj[i], self.v_lat[i] = dd_obj, VEL_LATERAL

    # -- Replanificación --

    def _evaluar(self, i, t):
        a = self.agentes[i]
        ruta = a.ruta
        v, f, fase, d = mc._parametros(ruta, a.semilla)
        ciclo = ruta.total_tiempo / v + f * ruta.total_pausas
        return mc._evaluar(ruta, (t - self.tau[i] + fase * ciclo) % ciclo, v, f, d + self.dd[i])

    def media_vuelta(self, i, t):
        """El agente `i` se da la vuelta: pasa al punto simétrico de su circuito (misma calle, otra acera, sentido
        contrario). La posición no salta: la diferencia queda como residuo y se consume andando."""
        a = self.agentes[i]
        ruta = a.ruta
        v, f, fase, d = mc._parametros(ruta, a.semilla)
        ciclo = ruta.total_tiempo / v + f * ruta.total_pausas
        canonico = (t + fase * ciclo) % ciclo
        antes = mc._evaluar(ruta, (canonico - self.tau[i]) % ciclo, v, f, d + self.dd[i])
        simetrica = ruta.total_dist - antes[5]
        if simetrica >= ruta.total_dist:
            simetrica = 0.0
        u = mc.tiempo_en_distancia(ruta, simetrica, v, f) % ciclo
        despues = mc._evaluar(ruta, u, v, f, d + self.dd[i])
        self.tau[i] = (canonico - u) % ciclo
        self.ox[i] += antes[0] - despues[0]
        self.oz[i] += antes[1] - despues[1]
        self.libre[i] = True
        self.bloqueo[i] = 0.0
        self.vuelta_desde[i] = t
        self.g_obj[i] = 1.0
        self.mirada[i] = 0.0
        self.dd_obj[i], self.v_lat[i] = self.dd[i], VEL_LATERAL_VUELTA
        self.rumbo_camino[i] = despues[2]
        r = math.radians(despues[2])
        self.fx[i], self.fz[i] = math.sin(r), math.cos(r)
        self.vueltas += 1

    # -- Frame --

    def avanzar(self, i, t, dt):
        """Un paso de `dt` s del agente `i` en el instante `t` del reloj. O(1), sin consultas al mundo."""
        g, objetivo = self.g[i], self.g_obj[i]
        if g < objetivo:
            g += ACELERACION * dt
            if g > objetivo:
                g = objetivo
        elif g > objetivo:
            g -= FRENADA * dt
            if g < objetivo:
                g = objetivo
        tau = self.tau[i] + (1.0 - g) * dt
        if tau < 0.0 and not self.libre[i]:
            tau = 0.0
            if g > 1.0:
                g = 1.0
        self.g[i], self.tau[i] = g, tau
        dd, dd_obj = self.dd[i], self.dd_obj[i]
        if dd != dd_obj:
            banda = self.banda[i]
            if banda < BANDA_MINIMA:
                dd = dd_obj
            else:
                paso = self.v_lat[i] * dt / banda
                dd = dd_obj if abs(dd_obj - dd) <= paso else dd + (paso if dd_obj > dd else -paso)
            self.dd[i] = dd
        a = self.agentes[i]
        ruta = a.ruta
        v, f, fase, d = mc._parametros(ruta, a.semilla)
        ciclo = ruta.total_tiempo / v + f * ruta.total_pausas
        e = mc._evaluar(ruta, (t - tau + fase * ciclo) % ciclo, v, f, d + dd)
        x, z = e[0], e[1]
        ox, oz = self.ox[i], self.oz[i]
        if ox != 0.0 or oz != 0.0:
            resto = math.hypot(ox, oz)
            queda = resto - VEL_RESIDUO * dt
            if queda <= 0.0:
                ox = oz = 0.0
            else:
                ox, oz = ox * queda / resto, oz * queda / resto
            self.ox[i], self.oz[i] = ox, oz
            x, z = x + ox, z + oz
        mx, mz = x - self.x[i], z - self.z[i]
        self.x[i], self.z[i], self.dist[i] = x, z, e[5]
        self.rumbo_camino[i] = e[2]
        vel = math.hypot(mx, mz) / dt if dt > 1e-6 else 0.0
        if vel > VEL_MAXIMA:
            vel = VEL_MAXIMA
        anda = vel > (VEL_MOVIMIENTO[0] if self.mov[i] else VEL_MOVIMIENTO[1])
        self.vel[i], self.mov[i] = vel, anda
        if anda:
            hacia = math.degrees(math.atan2(mx, mz))
        else:
            hacia = e[2] + self.mirada[i]
        self.rumbo[i] = girar_suave(self.rumbo[i], hacia, dt)

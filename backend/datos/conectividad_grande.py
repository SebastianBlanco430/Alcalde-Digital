# Conectividad del mundo GRANDE (datos puros, sin ursina): lo mismo que conectividad.py (rejilla de 0,5 m donde cabe el
# centro del jugador, radio 0,35 m) pero SIN crear la rejilla de ~2,3 M de celdas. Las celdas libres se guardan como
# tramos por fila (barrido por bandas de 64 m, como quitar_bolsas_por_chunk de barrio_indexado.py) y los tramos
# vecinos se unen con union-find: UNA sola inundación vale para todas las preguntas.
#
# Una celda es libre si es_transitable() de MundoCiudad lo diría: dentro de limites_recorribles, sin obstáculo (edificio,
# casa, árbol, farola...) a menos de `radio` y con pendiente caminable (salvo sobre una escalera). La pendiente se
# decide primero con una cota rigurosa sobre los nodos de 1 m del terreno y solo las celdas dudosas llaman a
# terreno.caminable (la mayor parte de la ladera no cuesta nada).
#
#   construir_conectividad(mundo, limites=None, resolucion=0.5, radio=RADIO_JUGADOR) -> Conectividad
#   Conectividad.raiz_en(x, z)         raíz del tramo de la celda libre más cercana (<= 1 m) o None.
#   Conectividad.misma_zona(a, b)      ¿(x, z) a y b en el mismo componente?
#   Conectividad.bolsas(x, z)          componentes que NO contienen (x, z): [(celdas, (x, z) de una de ellas)].
#   puntos_a_verificar(mundo)          [(tipo, nombre, (x, z))] de lo que debe estar conectado.
#   fallos_de_conectividad(mundo)      lista de dicts {tipo, nombre, x, z, motivo}; [] = todo bien.
#   bolsas_aisladas(mundo)             componentes sueltos con su tamaño y una coordenada.

import math

from backend.datos._rejilla_barrio import RejillaBarrio
from backend.datos.barrio_indexado import CHUNK, _intervalo_bloqueado, _invertir, _Tramos, _unir_filas
from backend.datos.terreno import PASO_GRILLA, PENDIENTE_CAMINABLE
from backend.logica.mundo_ciudad import RADIO_JUGADOR

RESOLUCION = 0.5
LUGAR_NUCLEO = "Praça da Sé"
MAXIMO_CELDA_CERCANA = 1.0                    # m: como Rejilla.conectados
MARGEN_COTA = 0.999                           # la cota de pendiente debe quedar bajo tan(32°) con este margen
_TAN = math.tan(math.radians(PENDIENTE_CAMINABLE))
_CELDA_INDICE = 16.0
TIPOS_VEGETACION = frozenset({"palmera", "bananero", "arbusto", "arbol"})


# -- Intervalos bloqueados -------------------------------------------------------------------------------------------


def _caja_de(o):
    if o.es_circulo:
        return (o.cx - o.radio, o.cx + o.radio, o.cz - o.radio, o.cz + o.radio)
    return (o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)


def _intervalo_circulo(cx, cz, rr, x0, paso, i_min, i_max, z):
    # columnas con hypot(x - cx, z - cz) < rr (la condición exacta de Rejilla.bloquear_circulo)
    dz = abs(z - cz)
    if dz >= rr:
        return None
    hx = math.sqrt(rr * rr - dz * dz)
    lo = max(i_min, int(math.ceil((cx - hx - x0) / paso)) - 1)
    hi = min(i_max, int(math.floor((cx + hx - x0) / paso)) + 1)
    while lo <= hi and not math.hypot(x0 + lo * paso - cx, z - cz) < rr:
        lo += 1
    while hi >= lo and not math.hypot(x0 + hi * paso - cx, z - cz) < rr:
        hi -= 1
    return (lo, hi) if lo <= hi else None


def _celdas_dudosas(terreno, xmin, xmax, za, zb):
    """{J: [I, ...]}: celdas de 1 m del terreno (J fila, I columna desde terreno.extension) donde la pendiente PODRÍA
    superar el límite. Cota: |gx| <= mayor salto en x de los segmentos que toca el diferencial central (columnas I-1..I+1,
    filas J..J+1) y |gz| <= el mayor en z (columnas I..I+1, filas J-1..J+1). Lo que queda bajo la cota es caminable."""
    ex0, _, ez0, _ = terreno.extension
    p = PASO_GRILLA
    ia, ib = int(math.floor((xmin - ex0) / p)), int(math.floor((xmax - ex0) / p))
    ja, jb = int(math.floor((za - ez0) / p)), int(math.floor((zb - ez0) / p))
    altura = terreno.altura
    # alturas de los nodos I en [ia-1, ib+2], J en [ja-1, jb+2]
    xs = [ex0 + i * p for i in range(ia - 1, ib + 3)]
    h = [[altura(x, ez0 + j * p) for x in xs] for j in range(ja - 1, jb + 3)]
    n = len(xs)
    dx = [[abs(f[c + 1] - f[c]) for c in range(n - 1)] for f in h]                        # segmento c -> c+1
    dz = [[abs(g[c] - f[c]) for c in range(n)] for f, g in zip(h, h[1:])]                 # segmento fila r -> r+1
    # mx[r][c]: mayor dx de los segmentos c-1, c, c+1 (c = columna de nodo)
    mx = [[max(f[max(c - 1, 0):c + 2]) for c in range(n - 1)] for f in dx]
    cm = [[max(f[c], f[c + 1]) for c in range(n - 1)] for f in dz]
    tope2 = (_TAN * MARGEN_COTA) ** 2
    dudosas = {}
    for fila in range(1, len(h) - 2):                       # fila r = J - (ja - 1); celdas J con r en [1, ...]
        a, b = mx[fila], mx[fila + 1]
        c0, c1, c2 = cm[fila - 1], cm[fila], cm[fila + 1]
        lista = []
        for col in range(1, n - 2):                          # col c = I - (ia - 1) para la celda de nodos c..c+1
            gx = a[col] if a[col] > b[col] else b[col]
            gz = max(c0[col], c1[col], c2[col])
            if gx * gx + gz * gz >= tope2:
                lista.append(col - 1 + ia)
        if lista:
            dudosas[fila - 1 + ja] = lista
    return dudosas


def construir_conectividad(mundo, limites=None, resolucion=RESOLUCION, radio=RADIO_JUGADOR, chunk=CHUNK):
    """Los tramos libres de la zona `limites` (por defecto toda la recorrible) tras bloquear obstáculos y taludes."""
    if limites is None:
        limites = mundo.limites_recorribles()
    xmin, xmax, zmin, zmax = limites
    nx = int(math.floor((xmax - xmin) / resolucion)) + 1
    nz = int(math.floor((zmax - zmin) / resolucion)) + 1
    tramos = _Tramos(nx, nz)

    cajas, circulos = [], []
    indice = RejillaBarrio(_CELDA_INDICE)
    fijos = [e.como_obstaculo() for e in mundo.edificios()] + list(mundo.obstaculos())
    for o in fijos:
        if o.es_circulo:
            k = ("c", len(circulos))
            circulos.append((o.cx, o.cz, o.radio + radio))
            indice.insertar_caja(k, (o.cx - o.radio - radio, o.cx + o.radio + radio,
                                     o.cz - o.radio - radio, o.cz + o.radio + radio))
        else:
            k = ("b", len(cajas))
            c = _caja_de(o)
            cajas.append(c)
            indice.insertar_caja(k, (c[0] - radio, c[1] + radio, c[2] - radio, c[3] + radio))

    terreno = mundo.terreno
    escaleras = mundo.escaleras()
    i_esc = RejillaBarrio(_CELDA_INDICE)
    for k, e in enumerate(escaleras):
        m = e.ancho / 2
        i_esc.insertar_caja(k, (min(e.ax, e.bx) - m, max(e.ax, e.bx) + m, min(e.az, e.bz) - m, max(e.az, e.bz) + m))

    def en_escalera(x, z):
        return any(escaleras[k].contiene(x, z) for k in i_esc.cerca(x, x, z, z))

    filas_banda = max(1, int(chunk / resolucion))
    previa = None
    for j0 in range(0, nz, filas_banda):
        j1 = min(nz - 1, j0 + filas_banda - 1)
        z_a, z_b = zmin + j0 * resolucion, zmin + j1 * resolucion
        intervalos = {}
        for tipo, k in sorted(indice.cerca(xmin - radio, xmax + radio, z_a - radio, z_b + radio)):
            if tipo == "b":
                caja = cajas[k]
                zi, zf, xa, xb = caja[2] - radio, caja[3] + radio, caja[0] - radio, caja[1] + radio
            else:
                cx, cz, rr = circulos[k]
                zi, zf, xa, xb = cz - rr, cz + rr, cx - rr, cx + rr
            fa = max(j0, int(math.ceil((zi - zmin) / resolucion)))
            fb = min(j1, int(math.floor((zf - zmin) / resolucion)))
            ia = max(0, int(math.ceil((xa - xmin) / resolucion)))
            ib = min(nx - 1, int(math.floor((xb - xmin) / resolucion)))
            if ia > ib:
                continue
            for j in range(fa, fb + 1):
                z = zmin + j * resolucion
                iv = (_intervalo_bloqueado(cajas[k], radio, xmin, resolucion, ia, ib, z) if tipo == "b"
                      else _intervalo_circulo(*circulos[k], xmin, resolucion, ia, ib, z))
                if iv is not None:
                    intervalos.setdefault(j, []).append(iv)
        if terreno is not None:
            ex0, _, ez0, _ = terreno.extension
            for J, columnas in _celdas_dudosas(terreno, xmin, xmax, z_a, z_b).items():
                # filas finas j de [j0, j1] que caen en la celda J (cerrada)
                ja = max(j0, int(math.ceil((ez0 + J * PASO_GRILLA - zmin) / resolucion)))
                jb = min(j1, int(math.floor((ez0 + (J + 1) * PASO_GRILLA - zmin) / resolucion)))
                for j in range(ja, jb + 1):
                    z = zmin + j * resolucion
                    if int(math.floor((z - ez0) / PASO_GRILLA)) != J:
                        continue                       # la frontera la decide la celda de arriba (misma cota)
                    vistos = set()
                    for I in columnas:
                        ia = max(0, int(math.ceil((ex0 + I * PASO_GRILLA - xmin) / resolucion)))
                        ib = min(nx - 1, int(math.floor((ex0 + (I + 1) * PASO_GRILLA - xmin) / resolucion)))
                        for i in range(ia, ib + 1):
                            if i in vistos or int(math.floor((xmin + i * resolucion - ex0) / PASO_GRILLA)) != I:
                                continue
                            vistos.add(i)
                            x = xmin + i * resolucion
                            if not terreno.caminable(x, z) and not en_escalera(x, z):
                                intervalos.setdefault(j, []).append((i, i))
        for j in range(j0, j1 + 1):
            libres = _invertir(sorted(intervalos.get(j, ())), nx)
            ini = [t[0] for t in libres]
            fin = [t[1] for t in libres]
            ids = list(range(len(tramos.padre), len(tramos.padre) + len(libres)))
            tramos.padre.extend(ids)
            tramos.inicios[j], tramos.fines[j], tramos.ids[j] = ini, fin, ids
            if previa is not None:
                _unir_filas(tramos, previa, (ini, fin, ids))
            previa = (ini, fin, ids)
    return Conectividad(tramos, tuple(limites), resolucion)


# -- Resultado -------------------------------------------------------------------------------------------------------


class Conectividad:
    """Tramos libres por fila + union-find ya resuelto. Las celdas son (i, j): x = xmin + i*paso, z = zmin + j*paso."""

    def __init__(self, tramos, limites, resolucion):
        self.tramos = tramos
        self.limites = limites
        self.paso = resolucion
        self.nx, self.nz = tramos.nx, tramos.nz

    def punto(self, i, j):
        return (self.limites[0] + i * self.paso, self.limites[2] + j * self.paso)

    def libre(self, i, j):
        return self.tramos.libre(i, j)

    def esta_libre(self, x, z):
        return self.libre(int(round((x - self.limites[0]) / self.paso)), int(round((z - self.limites[2]) / self.paso)))

    def celdas_libres(self):
        return sum(f - i + 1 for fi, ff in zip(self.tramos.inicios, self.tramos.fines) for i, f in zip(fi, ff))

    def raiz_en(self, x, z, maximo=MAXIMO_CELDA_CERCANA):
        """Raíz del tramo de la celda libre más cercana a (x, z) a menos de `maximo` m (como Rejilla._libre_cercana)."""
        i0 = int(round((x - self.limites[0]) / self.paso))
        j0 = int(round((z - self.limites[2]) / self.paso))
        if not (0 <= i0 < self.nx and 0 <= j0 < self.nz):
            return None
        radio = int(math.ceil(maximo / self.paso))
        mejor = None
        for dj in range(-radio, radio + 1):
            for di in range(-radio, radio + 1):
                if self.tramos.libre(i0 + di, j0 + dj):
                    d = di * di + dj * dj
                    if mejor is None or d < mejor[0]:
                        mejor = (d, i0 + di, j0 + dj)
        if mejor is None:
            return None
        return self.tramos.raiz(self.tramos.tramo_en(mejor[1], mejor[2]))

    def misma_zona(self, a, b):
        ra, rb = self.raiz_en(*a), self.raiz_en(*b)
        return ra is not None and ra == rb

    def componentes(self):
        """{raíz: [celdas, (x, z) de la primera celda]} de todos los componentes."""
        t = self.tramos
        res = {}
        for j in range(self.nz):
            for ini, fin, ident in zip(t.inicios[j], t.fines[j], t.ids[j]):
                r = t.raiz(ident)
                if r in res:
                    res[r][0] += fin - ini + 1
                else:
                    res[r] = [fin - ini + 1, self.punto(ini, j)]
        return res

    def bolsas(self, x, z):
        """Componentes que no contienen la celda libre cercana a (x, z): [(celdas, (x, z))], de mayor a menor."""
        principal = self.raiz_en(x, z)
        lista = [(n, p) for r, (n, p) in self.componentes().items() if r != principal]
        lista.sort(key=lambda c: -c[0])
        return lista


# -- Qué debe estar conectado ----------------------------------------------------------------------------------------


def puntos_de_aparcamiento_grande(mundo, n=24):
    # el cálculo de los puntos vive en frontend/vehiculo_calculos.py (funciones puras, sin ursina); se importa al usarlo
    from frontend.vehiculo_calculos import puntos_de_aparcamiento
    return [(p.x, p.z) for p in puntos_de_aparcamiento(mundo, n=n)]


def puntos_a_verificar(mundo, aparcamientos=None, comercios=None):
    """[(tipo, nombre, (x, z))]: spawns de los roles, aparcamientos, centro de cada plaza, punto_entrada (o de
    interacción) de cada lugar, comercios resueltos."""
    from backend.logica.roles import ROLES
    from backend.datos.ciudad_3d import ESCALA_MUNDO
    puntos = [("spawn", rol, (info.spawn_x * ESCALA_MUNDO, info.spawn_y * ESCALA_MUNDO)) for rol, info in ROLES.items()]
    if aparcamientos is None:
        aparcamientos = puntos_de_aparcamiento_grande(mundo)
    puntos += [("aparcamiento", f"#{k}", p) for k, p in enumerate(aparcamientos)]
    for lugar in mundo.lugares():
        puntos.append(("plaza", lugar, tuple(mundo.coordenada(lugar))))
        try:
            ex, ez = mundo.edificio_de(lugar).punto_entrada()
        except ValueError:
            ex, ez = mundo.punto_interaccion(lugar)
        puntos.append(("entrada", lugar, (ex, ez)))
    if comercios is None:
        from backend.datos.ciudad_grande import resolver_comercios_grande
        comercios = resolver_comercios_grande(mundo)
    for c, (x, z, _rumbo) in comercios:
        puntos.append(("comercio", c.id, (x, z)))
    return puntos


def fallos_de_conectividad(mundo, conectividad=None, nucleo=LUGAR_NUCLEO):
    """Lista de fallos: un dict {tipo, nombre, x, z, motivo} por cada punto que no está en el componente del núcleo
    (la plaza `nucleo`). Una sola inundación; [] = todo conectado."""
    con = conectividad or construir_conectividad(mundo)
    cx, cz = mundo.coordenada(nucleo)
    principal = con.raiz_en(cx, cz)
    if principal is None:
        return [{"tipo": "nucleo", "nombre": nucleo, "x": cx, "z": cz, "motivo": "sin celda libre en el núcleo"}]
    fallos = []
    for tipo, nombre, (x, z) in puntos_a_verificar(mundo):
        r = con.raiz_en(x, z)
        if r is None:
            motivo = "sin celda libre a menos de 1 m (el jugador no cabe)"
        elif r != principal:
            motivo = "aislado del núcleo"
        else:
            continue
        fallos.append({"tipo": tipo, "nombre": nombre, "x": round(x, 2), "z": round(z, 2), "motivo": motivo})
    return fallos


def bolsas_aisladas(mundo, conectividad=None, nucleo=LUGAR_NUCLEO):
    """[(celdas, (x, z))]: componentes libres que no son el del núcleo, de mayor a menor."""
    con = conectividad or construir_conectividad(mundo)
    return con.bolsas(*mundo.coordenada(nucleo))


# -- Reparación de bolsas ----------------------------------------------------------------------------------------------


class _VistaConectividad:
    """Lo mínimo de un mundo que necesita construir_conectividad, con otra lista de obstáculos (sin construir MundoGrande)."""

    def __init__(self, mundo, obstaculos, edificios=None, escaleras=None, limites=None):
        self._m = mundo
        self._obstaculos = list(obstaculos)
        self._edificios = None if edificios is None else list(edificios)
        self._escaleras = None if escaleras is None else list(escaleras)
        self._limites = limites
        self.terreno = mundo.terreno

    def edificios(self):
        return self._m.edificios() if self._edificios is None else list(self._edificios)

    def obstaculos(self):
        return list(self._obstaculos)

    def escaleras(self):
        return self._m.escaleras() if self._escaleras is None else list(self._escaleras)

    def limites_recorribles(self):
        return self._m.limites_recorribles() if self._limites is None else self._limites

    def coordenada(self, lugar):
        return self._m.coordenada(lugar)


def _celdas_de_bolsas(con, principal):
    t = con.tramos
    for j in range(con.nz):
        for ini, fin, ident in zip(t.inicios[j], t.fines[j], t.ids[j]):
            if t.raiz(ident) != principal:
                for i in range(ini, fin + 1):
                    yield con.punto(i, j)


def quitar_bolsas_grande(mundo, nucleo=LUGAR_NUCLEO, maximo_vueltas=8, cerca=2.0):
    """(obstaculos, quitados): quita del mundo la casa más cercana a cada celda libre aislada (a menos de `cerca` m) y, si
    no hay casa, la vegetación (TIPOS_VEGETACION) más cercana; como barrio_favela.quitar_bolsas pero contando también el
    talud, y repite hasta que no queden bolsas o `maximo_vueltas`. No modifica `mundo`: devuelve la lista nueva."""
    from backend.logica.mundo_ciudad import CasaDecorativa, _distancia_punto_caja
    obstaculos = list(mundo.obstaculos())
    quitados = []
    nx_, nz_ = mundo.coordenada(nucleo)
    for _ in range(maximo_vueltas):
        con = construir_conectividad(_VistaConectividad(mundo, obstaculos))
        principal = con.raiz_en(nx_, nz_)
        celdas = list(_celdas_de_bolsas(con, principal))
        if not celdas:
            break
        indice = RejillaBarrio(_CELDA_INDICE)
        for k, o in enumerate(obstaculos):
            if isinstance(o, CasaDecorativa) or o.tipo in TIPOS_VEGETACION:
                indice.insertar_caja(k, _caja_de(o))
        quitar = set()
        for x, z in celdas:
            mejor, mejor_k = None, None            # clave (prioridad, distancia): primero casas, luego plantas
            for k in sorted(indice.cerca(x - cerca, x + cerca, z - cerca, z + cerca)):
                o = obstaculos[k]
                d = _distancia_punto_caja(x, z, _caja_de(o))
                clave = (0 if isinstance(o, CasaDecorativa) else 1, d)
                if d < cerca and (mejor_k is None or clave < mejor):
                    mejor, mejor_k = clave, k
            if mejor_k is not None:
                quitar.add(mejor_k)
        if not quitar:
            break
        quitados += [obstaculos[k] for k in sorted(quitar)]
        obstaculos = [o for k, o in enumerate(obstaculos) if k not in quitar]
    return obstaculos, quitados


# -- Caminos tapados ---------------------------------------------------------------------------------------------------


def puntos_de_caminos(mundo, paso=1.0):
    """[(nombre, (x, z))] a lo largo del eje de cada calle, beco y escalera y en el tramo puerta -> entrada de cada edificio."""
    def muestrear(nombre, a, b):
        largo = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(largo / paso)))
        return [(nombre, (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)) for k in range(n + 1)]

    puntos = []
    for a, b in mundo.segmentos():
        puntos += muestrear(f"calle {a} - {b}", mundo.coordenada(a), mundo.coordenada(b))
    if hasattr(mundo, "becos"):
        for k, beco in enumerate(mundo.becos()):
            for p, q in beco.tramos():
                puntos += muestrear(f"beco {k}", p, q)
    for k, e in enumerate(mundo.escaleras()):
        puntos += muestrear(f"escalera {k}", (e.ax, e.az), (e.bx, e.bz))
    for e in mundo.edificios():
        puntos += muestrear(f"puerta de {e.lugar}", e.punto_entrada(), e.punto_entrada())
    return puntos


def caminos_tapados(mundo, conectividad=None, nucleo=LUGAR_NUCLEO, paso=1.0):
    """Puntos de calles, becos, escaleras y accesos de puerta donde no cabe el jugador o que quedan fuera del componente del
    núcleo (algo los tapa): [{tipo, nombre, x, z, motivo}], un solo aviso por camino y motivo (el primer punto)."""
    con = conectividad or construir_conectividad(mundo)
    principal = con.raiz_en(*mundo.coordenada(nucleo))
    vistos, fallos = set(), []
    for nombre, (x, z) in puntos_de_caminos(mundo, paso):
        r = con.raiz_en(x, z, maximo=0.5)
        if r == principal:
            continue
        motivo = "no cabe el jugador" if r is None else "aislado del núcleo"
        if (nombre, motivo) in vistos:
            continue
        vistos.add((nombre, motivo))
        fallos.append({"tipo": nombre.split()[0], "nombre": nombre, "x": round(x, 2), "z": round(z, 2), "motivo": motivo})
    return fallos

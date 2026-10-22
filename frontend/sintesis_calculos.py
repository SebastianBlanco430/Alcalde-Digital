# Síntesis procedural de sonido (módulo PURO: solo stdlib; sin ursina ni panda3d).
# Genera muestras PCM como listas de floats en [-1, 1] a 44,1 kHz mono y las convierte a PCM de 16 bits / WAV.
# Todo es determinista: cada sonido usa su propio random.Random con semilla fija (nunca el generador global),
# así que regenerar da exactamente los mismos bytes. Los .wav de assets/sonidos/ salen de aquí una sola vez
# (scripts/generar_sonidos.py); si faltan, GestorAudio los vuelve a generar en memoria con estas funciones.
#
# Cómo evitar clics (la lección de audio-design): los sonidos cortos llevan fundido de entrada/salida; los
# bucles se hacen o bien con señales exactamente periódicas (motor) o bien con un fundido cruzado de potencia
# constante entre el final y el principio (viento, música), de modo que el empalme no salta.

import math
import random
import struct
import wave

TASA = 44100               # Hz
SEMILLA = 20261021         # base de las semillas de todos los sonidos
PICO_EFECTOS = 0.8         # pico tras normalizar un efecto
PICO_BUCLES = 0.6          # pico de los bucles de ambiente/motor (van de fondo)
PICO_MUSICA = 0.55

BPM = 90                   # música: negra = 0,667 s; compás = 2,667 s
COMPASES_MUSICA = 12       # 12 compases = 32 s


# ------------------------------------------------------------------ utilidades básicas

def n_muestras(segundos):
    return int(round(segundos * TASA))


def silencio(segundos):
    return [0.0] * n_muestras(segundos)


def ruido(rng, n):
    # Ruido blanco uniforme en [-1, 1].
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def _coef(fc):
    return 1.0 - math.exp(-2.0 * math.pi * fc / TASA)


def pasa_bajos(x, fc):
    # Filtro de un polo.
    a = _coef(fc)
    y = 0.0
    salida = []
    for v in x:
        y += a * (v - y)
        salida.append(y)
    return salida


def pasa_altos(x, fc):
    bajos = pasa_bajos(x, fc)
    return [v - b for v, b in zip(x, bajos)]


def pasa_banda(x, fc_baja, fc_alta):
    return pasa_altos(pasa_bajos(x, fc_alta), fc_baja)


def quitar_continua(x):
    if not x:
        return x
    media = sum(x) / len(x)
    return [v - media for v in x]


def envolvente(n, ataque_s, caida_s):
    # Ataque lineal y caída exponencial (constante de tiempo `caida_s`).
    na = max(1, n_muestras(ataque_s))
    tau = max(1e-4, caida_s) * TASA
    env = []
    for i in range(n):
        subida = min(1.0, (i + 1) / na)
        env.append(subida * math.exp(-i / tau))
    return env


def por(x, y):
    # Producto elemento a elemento (recorta al más corto).
    return [a * b for a, b in zip(x, y)]


def escalar(x, g):
    return [v * g for v in x]


def seno(freq, n, fase=0.0, inicio=0):
    w = 2.0 * math.pi * freq / TASA
    return [math.sin(w * (i + inicio) + fase) for i in range(n)]


def barrido(f0, f1, n):
    # Seno con frecuencia que va de f0 a f1 (exponencial) a lo largo de n muestras.
    fase = 0.0
    salida = []
    for i in range(n):
        f = f0 * (f1 / f0) ** (i / max(1, n - 1))
        fase += 2.0 * math.pi * f / TASA
        salida.append(math.sin(fase))
    return salida


def mezclar(destino, origen, inicio=0, ganancia=1.0, envolver=False):
    # Suma `origen` en `destino` desde la muestra `inicio`. Con envolver=True lo que pasa del final vuelve a
    # entrar por el principio (así la cola de una nota no se corta en un bucle).
    n = len(destino)
    if envolver:
        for i, v in enumerate(origen):
            destino[(inicio + i) % n] += v * ganancia
    else:
        for i, v in enumerate(origen):
            j = inicio + i
            if j >= n:
                break
            destino[j] += v * ganancia
    return destino


def fundido(x, entrada_s=0.005, salida_s=0.02):
    # Fundido lineal de entrada y de salida (en el sitio). Garantiza que empiece y acabe en 0: sin clic.
    n = len(x)
    ne = min(n_muestras(entrada_s), n // 2)
    ns = min(n_muestras(salida_s), n // 2)
    for i in range(ne):
        x[i] *= i / ne
    for i in range(ns):
        x[n - 1 - i] *= i / ns
    if n:
        x[0] = 0.0
        x[-1] = 0.0
    return x


def normalizar(x, pico=PICO_EFECTOS):
    # Escala para que el pico absoluto sea `pico` (si es silencio no hace nada).
    m = max((abs(v) for v in x), default=0.0)
    if m <= 1e-9:
        return x
    g = pico / m
    return [v * g for v in x]


def hacer_bucle(x, largo_s, cruce_s):
    # Convierte una señal de largo_s + cruce_s en un bucle de largo_s sin salto en el empalme: las primeras
    # `cruce` muestras se mezclan (potencia constante) con las que sobran al final.
    L = n_muestras(largo_s)
    N = n_muestras(cruce_s)
    if len(x) < L + N:
        raise ValueError("La señal debe durar al menos largo_s + cruce_s.")
    salida = x[:L]
    for i in range(N):
        t = (i + 0.5) / N
        w_in = math.sin(t * math.pi / 2)      # sube
        w_out = math.cos(t * math.pi / 2)     # baja
        salida[i] = x[i] * w_in + x[L + i] * w_out
    return salida


def a_pcm16(x):
    # Float [-1, 1] -> bytes PCM 16 bits little-endian (con recorte y sin NaN).
    entero = []
    for v in x:
        if v != v:                            # NaN
            v = 0.0
        v = max(-1.0, min(1.0, v))
        entero.append(int(round(v * 32767)))
    return struct.pack("<%dh" % len(entero), *entero)


def escribir_wav(ruta, x):
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TASA)
        w.writeframes(a_pcm16(x))


def leer_wav(ruta):
    with wave.open(str(ruta), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("Se espera WAV mono de 16 bits.")
        datos = w.readframes(w.getnframes())
    n = len(datos) // 2
    return [v / 32768.0 for v in struct.unpack("<%dh" % n, datos)]


def _rng(nombre, variante=0):
    # Semilla estable por sonido (no depende de hash(), que cambia entre ejecuciones).
    s = SEMILLA + variante * 7919
    for c in nombre:
        s = (s * 131 + ord(c)) % 2147483647
    return random.Random(s)


def _hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


# ------------------------------------------------------------------ efectos cortos

def paso_arena(variante=0):
    rng = _rng("paso_arena", variante)
    n = n_muestras(0.17)
    base = pasa_banda(ruido(rng, n), 250 + 60 * variante, 2600 - 300 * variante)
    cuerpo = por(base, envolvente(n, 0.012, 0.05))
    # granos de arena: pequeños chasquidos sueltos
    granos = [0.0] * n
    for _ in range(14):
        i = rng.randrange(int(0.01 * TASA), n)
        granos[i] = rng.uniform(-1, 1) * 0.6
    granos = por(pasa_banda(granos, 1500, 6000), envolvente(n, 0.001, 0.06))
    x = [a + b * 2.0 for a, b in zip(cuerpo, granos)]
    return normalizar(fundido(x, 0.004, 0.04), 0.5)


def paso_concreto(variante=0):
    rng = _rng("paso_concreto", variante)
    n = n_muestras(0.14)
    golpe = por(seno(105 + 14 * variante, n), envolvente(n, 0.002, 0.03))
    roce = por(pasa_banda(ruido(rng, n), 1200, 5500 + 700 * variante), envolvente(n, 0.001, 0.014))
    x = [g * 0.9 + r * 0.7 for g, r in zip(golpe, roce)]
    return normalizar(fundido(x, 0.002, 0.03), 0.55)


def salto():
    rng = _rng("salto")
    n = n_muestras(0.26)
    aire = por(pasa_banda(ruido(rng, n), 400, 3000), envolvente(n, 0.06, 0.1))
    tono = por(barrido(220, 440, n), envolvente(n, 0.02, 0.09))
    x = [a * 0.8 + t * 0.35 for a, t in zip(aire, tono)]
    return normalizar(fundido(x, 0.01, 0.06), 0.5)


def aterrizaje():
    rng = _rng("aterrizaje")
    n = n_muestras(0.28)
    golpe = por(barrido(130, 55, n), envolvente(n, 0.002, 0.07))
    polvo = por(pasa_banda(ruido(rng, n), 200, 2200), envolvente(n, 0.003, 0.05))
    x = [g * 1.0 + p * 0.6 for g, p in zip(golpe, polvo)]
    return normalizar(fundido(x, 0.003, 0.05), 0.65)


def clic_ui():
    rng = _rng("clic_ui")
    n = n_muestras(0.07)
    tono = por(seno(1850, n), envolvente(n, 0.001, 0.012))
    seco = por(pasa_altos(ruido(rng, n), 3000), envolvente(n, 0.0005, 0.004))
    x = [t + s * 0.4 for t, s in zip(tono, seco)]
    return normalizar(fundido(x, 0.001, 0.02), 0.45)


def hover_ui():
    n = n_muestras(0.05)
    x = por(seno(1250, n), envolvente(n, 0.004, 0.012))
    return normalizar(fundido(x, 0.003, 0.02), 0.22)


def _campana(freq, segundos, caida):
    n = n_muestras(segundos)
    x = [0.0] * n
    for h, a in ((1.0, 1.0), (2.01, 0.45), (2.76, 0.3), (4.1, 0.12)):
        pieza = por(seno(freq * h, n), envolvente(n, 0.002, caida / (0.6 + 0.4 * h)))
        mezclar(x, pieza, 0, a)
    return x


def mensaje_civitas():
    # Dos notas de campanilla ascendentes (E6 -> A6): aviso amable de «mensaje nuevo».
    x = silencio(0.7)
    mezclar(x, _campana(1318.5, 0.45, 0.18), 0, 0.8)
    mezclar(x, _campana(1760.0, 0.5, 0.2), n_muestras(0.13), 0.8)
    return normalizar(fundido(x, 0.002, 0.08), 0.55)


def mision_exito():
    # Arpegio mayor ascendente Do-Mi-Sol-Do con acorde final.
    x = silencio(1.1)
    for k, midi in enumerate((72, 76, 79, 84)):
        mezclar(x, _campana(_hz(midi), 0.5, 0.25), n_muestras(0.11 * k), 0.6)
    for midi in (72, 76, 79, 84):
        mezclar(x, _campana(_hz(midi), 0.6, 0.4), n_muestras(0.46), 0.35)
    return normalizar(fundido(x, 0.003, 0.12), 0.6)


def mision_fallo():
    # Descenso menor con tono ligeramente desafinado (serrucho suavizado).
    x = silencio(0.95)
    for k, midi in enumerate((67, 63, 60, 55)):
        n = n_muestras(0.42)
        f = _hz(midi)
        saw = [0.0] * n
        for h in (1, 2, 3, 4):
            mezclar(saw, seno(f * h, n), 0, 1.0 / h)
            mezclar(saw, seno(f * h * 1.004, n), 0, 0.6 / h)
        saw = pasa_bajos(saw, 1400)
        mezclar(x, por(saw, envolvente(n, 0.01, 0.2)), n_muestras(0.17 * k), 0.5)
    return normalizar(fundido(x, 0.004, 0.12), 0.55)


def bici_timbre():
    # Timbre de bici: dos «ding» metálicos agudos.
    x = silencio(0.9)
    for inicio in (0.0, 0.2):
        for f, a in ((2800, 1.0), (3560, 0.6), (5200, 0.25)):
            n = n_muestras(0.6)
            mezclar(x, por(seno(f, n), envolvente(n, 0.001, 0.16)), n_muestras(inicio), a * 0.5)
    return normalizar(fundido(x, 0.001, 0.1), 0.5)


# ------------------------------------------------------------------ bucles de vehículos

def motor_moto():
    # 2 s EXACTAS y periódico: el fundamental (60 Hz) y todos los armónicos caben en un número entero de
    # ciclos, así el empalme es continuo. La frecuencia de explosión (30 Hz) modula la amplitud.
    rng = _rng("motor_moto")
    largo, cruce = 2.0, 0.08
    n = n_muestras(largo + cruce)
    f0 = 60.0
    pesos = (1.0, 0.7, 0.55, 0.4, 0.28, 0.2, 0.12, 0.08)
    tono = [0.0] * n
    for h, p in enumerate(pesos, start=1):
        mezclar(tono, seno(f0 * h, n, fase=0.7 * h), 0, p)
    pulso = [0.55 + 0.45 * math.cos(2 * math.pi * 30.0 * i / TASA) ** 2 for i in range(n)]
    rumor = pasa_bajos(ruido(rng, n), 320)
    x = [t * m * 0.8 + r * 1.4 for t, m, r in zip(tono, pulso, rumor)]
    x = pasa_bajos(x, 2400)
    x = hacer_bucle(x, largo, cruce)
    return normalizar(quitar_continua(x), PICO_BUCLES)


def bici_cadena():
    # 2 s de rueda libre: tictic de la cadena (12 por bucle) sobre un zumbido finísimo.
    rng = _rng("bici_cadena")
    largo, cruce = 2.0, 0.05
    n = n_muestras(largo + cruce)
    x = [0.0] * n
    for k in range(12):
        inicio = n_muestras(largo / 12 * k)
        nc = n_muestras(0.03)
        clic = por(pasa_banda(ruido(rng, nc), 1800, 6500), envolvente(nc, 0.0005, 0.006))
        mezclar(x, clic, inicio, rng.uniform(0.7, 1.0), envolver=False)
    zumbido = por(pasa_banda(ruido(rng, n), 2000, 5000), [0.05] * n)
    x = [a + b for a, b in zip(x, zumbido)]
    # El primer tictic cae al inicio; para que la parte del cruce tenga el mismo patrón se repite el patrón
    # desplazado un bucle (los clics son periódicos).
    for k in range(12):
        inicio = n_muestras(largo + largo / 12 * k)
        if inicio < n:
            nc = n_muestras(0.03)
            clic = por(pasa_banda(ruido(rng, nc), 1800, 6500), envolvente(nc, 0.0005, 0.006))
            mezclar(x, clic, inicio, rng.uniform(0.7, 1.0))
    x = hacer_bucle(x, largo, cruce)
    return normalizar(quitar_continua(x), 0.45)


# ------------------------------------------------------------------ ambiente de la favela

def _ladrido(rng):
    n = n_muestras(0.2)
    f0 = 430.0
    x = [0.0] * n
    fase = 0.0
    for i in range(n):
        f = f0 * (1.0 - 0.35 * i / n)
        fase += 2 * math.pi * f / TASA
        s = 0.0
        for h in range(1, 7):
            s += math.sin(h * fase) / h
        x[i] = s
    x = pasa_banda(x, 350, 2200)
    x = por(x, envolvente(n, 0.008, 0.06))
    return fundido(normalizar(x, 1.0), 0.004, 0.03)


def _radio(rng, segundos):
    n = n_muestras(segundos)
    x = [0.0] * n
    notas = (57, 60, 62, 64, 67, 69)
    i = 0
    while i < n:
        dur = n_muestras(rng.choice((0.18, 0.25, 0.36)))
        f = _hz(rng.choice(notas))
        trozo = [1.0 if math.sin(2 * math.pi * f * j / TASA) >= 0 else -1.0 for j in range(min(dur, n - i))]
        trozo = por(trozo, envolvente(len(trozo), 0.01, 0.2))
        mezclar(x, trozo, i, 1.0)
        i += dur
    x = pasa_banda(x, 500, 3200)
    siseo = escalar(pasa_altos(ruido(rng, n), 2500), 0.15)
    x = [a + b for a, b in zip(x, siseo)]
    return fundido(normalizar(x, 1.0), 0.05, 0.2)


def ambiente_favela():
    # 16 s en bucle: viento + murmullo lejano + dos ladridos y una radio muy bajita. Los eventos se colocan
    # lejos de los extremos para que el fundido cruzado del empalme no los duplique.
    rng = _rng("ambiente_favela")
    largo, cruce = 16.0, 1.5
    n = n_muestras(largo + cruce)
    # viento: ruido grave con oleadas lentas
    viento = pasa_bajos(pasa_bajos(ruido(rng, n), 600), 380)
    oleadas = [0.55 + 0.45 * math.sin(2 * math.pi * 0.19 * i / TASA + 1.1) * math.sin(2 * math.pi * 0.07 * i / TASA)
               for i in range(n)]
    x = [v * o * 5.0 for v, o in zip(viento, oleadas)]
    # murmullo de gente a lo lejos: ruido de voz con sílabas
    voz = pasa_banda(ruido(rng, n), 220, 1500)
    silabas = [0.45 + 0.55 * abs(math.sin(2 * math.pi * 3.1 * i / TASA + 0.6 * math.sin(2 * math.pi * 0.31 * i / TASA)))
               for i in range(n)]
    murmullo = por(voz, silabas)
    mezclar(x, murmullo, 0, 0.55)
    # ladridos lejanos (apagados)
    ladrido = _ladrido(rng)
    ladrido = pasa_bajos(ladrido, 1800)
    for t in (4.0, 4.32, 4.62, 11.8, 12.15):
        mezclar(x, ladrido, n_muestras(t), 0.22)
    # radio lejana
    mezclar(x, _radio(rng, 3.0), n_muestras(7.5), 0.09)
    x = hacer_bucle(x, largo, cruce)
    return normalizar(quitar_continua(x), PICO_BUCLES)


# ------------------------------------------------------------------ música ambiente

# Progresión en la menor (aire de cómic/Borderlands): Am | F | Dm | E, repetida 3 veces (12 compases).
_ACORDES = (
    {"raiz": 45, "notas": (57, 60, 64), "arp": (69, 72, 76, 72)},      # Am
    {"raiz": 41, "notas": (53, 57, 60), "arp": (65, 69, 72, 69)},      # F
    {"raiz": 38, "notas": (50, 53, 57), "arp": (62, 65, 69, 65)},      # Dm
    {"raiz": 40, "notas": (52, 56, 59), "arp": (64, 68, 71, 68)},      # E
)
_MELODIA = (   # (octavo de compás, midi, octavos de duración); 4 compases
    (0, 81, 3), (4, 76, 2), (6, 79, 2),
    (8, 77, 3), (12, 72, 2), (14, 76, 2),
    (16, 74, 3), (20, 77, 2), (22, 81, 2),
    (24, 80, 4), (28, 76, 4),
)


def _cuerda(freq, segundos, rng, caida=0.997):
    # Karplus-Strong: cuerda pulsada barata y creíble.
    N = max(2, int(TASA / freq))
    buf = [rng.uniform(-1, 1) for _ in range(N)]
    n = n_muestras(segundos)
    salida = [0.0] * n
    for i in range(n):
        j = i % N
        v = buf[j]
        salida[i] = v
        buf[j] = caida * 0.5 * (v + buf[(j + 1) % N])
    return salida


def _nota_pad(midi, segundos):
    n = n_muestras(segundos)
    f = _hz(midi)
    x = [0.0] * n
    for h, p in ((1, 1.0), (2, 0.35), (3, 0.12)):
        mezclar(x, seno(f * h, n), 0, p)
        mezclar(x, seno(f * h * 1.003, n), 0, p * 0.6)
    ataque = n_muestras(0.5)
    sueltame = n_muestras(0.7)
    for i in range(n):
        g = min(1.0, i / ataque) * min(1.0, (n - i) / sueltame)
        x[i] *= g
    return x


def _nota_bajo(midi, segundos):
    n = n_muestras(segundos)
    f = _hz(midi)
    x = [0.0] * n
    for h, p in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.1)):
        mezclar(x, seno(f * h, n), 0, p)
    return por(pasa_bajos(x, 700), envolvente(n, 0.008, segundos * 0.55))


def _bombo():
    n = n_muestras(0.3)
    return por(barrido(140, 45, n), envolvente(n, 0.001, 0.09))


def _caja(rng):
    n = n_muestras(0.22)
    ruido_c = por(pasa_banda(ruido(rng, n), 900, 6000), envolvente(n, 0.001, 0.05))
    cuerpo = por(seno(190, n), envolvente(n, 0.001, 0.04))
    return [a * 0.8 + b * 0.5 for a, b in zip(ruido_c, cuerpo)]


def _hihat(rng):
    n = n_muestras(0.07)
    return por(pasa_altos(ruido(rng, n), 6500), envolvente(n, 0.0005, 0.012))


def _lead(midi, segundos):
    n = n_muestras(segundos)
    f = _hz(midi)
    fase = 0.0
    x = []
    for i in range(n):
        vib = 1.0 + 0.004 * math.sin(2 * math.pi * 5.2 * i / TASA) * min(1.0, i / (0.25 * TASA))
        fase += 2 * math.pi * f * vib / TASA
        x.append(math.sin(fase) + 0.35 * math.sin(2 * fase) + 0.12 * math.sin(3 * fase))
    ataque = 0.02
    return por(x, envolvente(n, ataque, segundos * 0.5))


def musica_ambiente():
    # 12 compases a 90 BPM (32 s) en bucle: 4 compases de base (pad + bajo + bombo + hi-hat), 4 más con arpegio
    # de cuerda, y 4 con melodía y caja suave. Las colas de las notas dan la vuelta al principio.
    rng = _rng("musica_ambiente")
    negra = 60.0 / BPM
    octavo = negra / 2
    compas = negra * 4
    total = n_muestras(compas * COMPASES_MUSICA)
    x = [0.0] * total
    cache = {}

    def memo(clave, fabrica):
        if clave not in cache:
            cache[clave] = fabrica()
        return cache[clave]

    bombo = _bombo()
    caja = _caja(rng)
    hat = _hihat(rng)
    for c in range(COMPASES_MUSICA):
        acorde = _ACORDES[c % 4]
        t0 = n_muestras(compas * c)
        tercio = c // 4          # 0: base, 1: +arpegio, 2: +melodía/caja
        # pad
        for midi in acorde["notas"]:
            mezclar(x, memo(("pad", midi), lambda m=midi: _nota_pad(m, compas + 0.9)), t0, 0.16, envolver=True)
        # bajo (octavos 0, 3, 4, 6)
        for paso, cambio in ((0, 0), (3, 0), (4, 7), (6, 12)):
            midi = acorde["raiz"] + cambio
            dur = octavo * (2.5 if paso in (0, 4) else 1.5)
            mezclar(x, memo(("bajo", midi, round(dur, 3)), lambda m=midi, d=dur: _nota_bajo(m, d)),
                    t0 + n_muestras(octavo * paso), 0.34, envolver=True)
        # percusión
        for paso in (0, 4):
            mezclar(x, bombo, t0 + n_muestras(octavo * paso), 0.5, envolver=True)
        if tercio == 2:
            for paso in (2, 6):
                mezclar(x, caja, t0 + n_muestras(octavo * paso) , 0.2, envolver=True)
        for paso in range(8):
            mezclar(x, hat, t0 + n_muestras(octavo * paso), 0.07 if paso % 2 == 0 else 0.11, envolver=True)
        # arpegio de cuerda pulsada
        if tercio >= 1:
            for k in range(8):
                midi = acorde["arp"][k % 4]
                clave = ("cuerda", midi, k % 2)
                nota = memo(clave, lambda m=midi: pasa_bajos(_cuerda(_hz(m), 0.9, random.Random(SEMILLA + m)), 3200))
                mezclar(x, nota, t0 + n_muestras(octavo * k), 0.17, envolver=True)
    # melodía en los 4 últimos compases
    base = n_muestras(compas * 8)
    for paso, midi, dur in _MELODIA:
        nota = memo(("lead", midi, dur), lambda m=midi, d=dur: _lead(m, octavo * d + 0.35))
        mezclar(x, nota, base + n_muestras(octavo * paso), 0.2, envolver=True)
    return normalizar(quitar_continua(x), PICO_MUSICA)


def musica_interior():
    # La misma música, apagada (filtro grave) y más baja: suena «dentro de un cuarto» al entrar a un edificio.
    base = musica_ambiente()
    # Filtro sobre dos vueltas seguidas y nos quedamos con la segunda: así el filtro llega al final con la
    # «memoria» del principio y el bucle sigue siendo continuo en el empalme.
    n = len(base)
    x = pasa_bajos(pasa_bajos(base + base, 900), 1400)[n:]
    return normalizar(quitar_continua(x), PICO_MUSICA * 0.8)


# ------------------------------------------------------------------ catálogo

# nombre -> (función generadora sin argumentos, ¿es bucle?)
CATALOGO = {
    "paso_arena_1": (lambda: paso_arena(0), False),
    "paso_arena_2": (lambda: paso_arena(1), False),
    "paso_concreto_1": (lambda: paso_concreto(0), False),
    "paso_concreto_2": (lambda: paso_concreto(1), False),
    "salto": (salto, False),
    "aterrizaje": (aterrizaje, False),
    "clic_ui": (clic_ui, False),
    "hover_ui": (hover_ui, False),
    "mensaje_civitas": (mensaje_civitas, False),
    "mision_exito": (mision_exito, False),
    "mision_fallo": (mision_fallo, False),
    "bici_timbre": (bici_timbre, False),
    "motor_moto": (motor_moto, True),
    "bici_cadena": (bici_cadena, True),
    "ambiente_favela": (ambiente_favela, True),
    "musica_ambiente": (musica_ambiente, True),
    "musica_interior": (musica_interior, True),
}


def generar(nombre):
    # Muestras (floats) del sonido `nombre`. KeyError si no existe.
    return CATALOGO[nombre][0]()


def es_bucle(nombre):
    return CATALOGO[nombre][1]


def salto_en_empalme(x, ventana=8):
    # Diferencia entre la muestra final y la inicial comparada con la variación típica entre muestras
    # contiguas: ~1 o menos = el empalme es tan suave como el resto de la señal. Para los tests.
    n = len(x)
    if n < 2 * ventana + 2:
        return 0.0
    paso_tipico = sum(abs(x[i + 1] - x[i]) for i in range(n - 1)) / (n - 1)
    return abs(x[0] - x[-1]) / max(paso_tipico, 1e-9)

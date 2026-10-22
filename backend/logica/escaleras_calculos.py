# Escaleras con peldaños de verdad (cálculos puros, sin ursina). Antes una Escalera se caminaba como
# una rampa: el jugador seguía la altura suave del terreno. Aquí la altura se CUANTIZA en peldaños
# de CONTRAHUELLA m a lo largo del eje de la escalera, y el renderizador (frontend/ciudad_3d.py) dibuja
# exactamente esos peldaños, así que lo que se ve es lo que se pisa.
#
# Cómo se forma el perfil (de punta a punta del eje de la escalera):
#   - `base` = la punta baja (altura del terreno) y `tope` = la punta alta; la dirección da igual.
#   - Cada punto del eje cae en el peldaño de nivel ceil((h - base - TOLERANCIA) / CONTRAHUELLA), así
#     el escalón nunca queda más de TOLERANCIA m enterrado bajo el terreno y a lo sumo CONTRAHUELLA
#     por encima. Todos los contrahuellas valen lo mismo; las huellas salen solas: cortas donde la
#     ladera es empinada (a ~31° miden 0.30 m para 0.18 m de subida) y largas donde es suave.
#   - El nivel solo sube desde la punta baja hacia la alta (no hay peldaños que suban y bajen por una
#     ondulación del terreno) y nunca pasa de `tope`: arriba queda a ras del descanso.
#
# Bandera reversible: con ESCALERAS_PELDANOS = False el mundo se comporta como antes (rampa) y el
# renderizador dibuja los peldaños de siempre.

import math
from bisect import bisect_right

ESCALERAS_PELDANOS = True

CONTRAHUELLA = 0.18          # m de subida por peldaño
HUELLA_REFERENCIA = 0.30     # m de fondo de un peldaño "de manual" (a esa pendiente sale solo)
TOLERANCIA = 0.05            # m máximos que un peldaño puede quedar enterrado bajo el terreno
TAPA_SOBRE_SUELO = 0.22      # m que la tapa dibujada sube sobre la altura de referencia (capas del suelo + pies)
PASO_MUESTREO = 0.02         # m entre muestras del eje al armar el perfil
FACTOR_SUBIDA = 0.8          # multiplicador de velocidad al SUBIR una escalera (bajar no frena)


# Nivel (0, 1, 2...) del peldaño que le toca a un suelo de altura `h` cuando la punta baja está en `base`.
def nivel_peldano(h, base, contrahuella=CONTRAHUELLA, tolerancia=TOLERANCIA):
    return max(0, math.ceil((h - base - tolerancia) / contrahuella))


# Altura cuantizada en peldaños de `h`: base + nivel · contrahuella, sin pasar de `tope`.
def altura_peldanos(h, base, tope, contrahuella=CONTRAHUELLA, tolerancia=TOLERANCIA):
    return min(tope, base + nivel_peldano(h, base, contrahuella, tolerancia) * contrahuella)


# Multiplicador de velocidad en una escalera: FACTOR_SUBIDA si se sube, 1 si se baja o está fuera.
def factor_subida(en_escalera, sube):
    return FACTOR_SUBIDA if (en_escalera and sube) else 1.0


# Cuántos peldaños tiene una escalera que salva `desnivel` m (al menos 1).
def numero_peldanos(desnivel, contrahuella=CONTRAHUELLA):
    return max(1, round(abs(desnivel) / contrahuella))


class PerfilEscalera:
    """Perfil de peldaños de una Escalera: `altura_en_s(s)` con s = metros desde el punto A.

    `altura_eje(s)` es la altura del terreno sobre el eje de la escalera. El perfil guarda los
    peldaños como tramos [(s0, s1, altura)] ya monótonos desde la punta baja."""

    def __init__(self, escalera, altura_terreno, contrahuella=CONTRAHUELLA, paso=PASO_MUESTREO):
        self.escalera = escalera
        self.contrahuella = contrahuella
        largo = escalera.largo
        self._ux = (escalera.bx - escalera.ax) / largo
        self._uz = (escalera.bz - escalera.az) / largo
        self.largo = largo
        ha = altura_terreno(escalera.ax, escalera.az)
        hb = altura_terreno(escalera.bx, escalera.bz)
        self.base, self.tope = min(ha, hb), max(ha, hb)
        self.baja_en_a = ha <= hb               # ¿la punta baja es A? (la escalera sube de A hacia B)
        n = max(2, int(math.ceil(largo / paso)))
        # muestras desde la punta BAJA hacia la alta: así el nivel solo puede subir
        s_muestras = [largo * i / n for i in range(n + 1)]
        if not self.baja_en_a:
            s_muestras = s_muestras[::-1]
        niveles = []
        mejor = 0
        for s in s_muestras:
            h = altura_terreno(escalera.ax + self._ux * s, escalera.az + self._uz * s)
            mejor = max(mejor, nivel_peldano(h, self.base, contrahuella))
            niveles.append(mejor)
        # tramos [(s_desde, s_hasta, altura)] en orden de s creciente desde A
        tramos = []
        for s, nivel in zip(s_muestras, niveles):
            altura = min(self.tope, self.base + nivel * contrahuella)
            if tramos and abs(tramos[-1][2] - altura) < 1e-9:
                a, b, _ = tramos[-1]
                tramos[-1] = (min(a, s), max(b, s), altura)
            else:
                tramos.append((s, s, altura))
        tramos.sort(key=lambda t: t[0])
        # cada tramo llega hasta la mitad entre su última muestra y la primera del siguiente
        suave = []
        for i, (a, b, altura) in enumerate(tramos):
            desde = 0.0 if i == 0 else (tramos[i - 1][1] + a) / 2
            hasta = largo if i == len(tramos) - 1 else (b + tramos[i + 1][0]) / 2
            suave.append((desde, hasta, altura))
        self.tramos = suave
        self._inicios = [t[0] for t in suave]

    @property
    def peldanos(self):
        """Cantidad de huellas distintas (tramos a distinta altura)."""
        return len(self.tramos)

    # Altura (referencia del suelo, sin TAPA_SOBRE_SUELO) del peldaño a `s` m de A (s se acota al eje).
    def altura_en_s(self, s):
        s = min(self.largo, max(0.0, s))
        i = max(0, bisect_right(self._inicios, s) - 1)
        return self.tramos[i][2]

    # Distancia s (m desde A) de la proyección de (x, z) sobre el eje, acotada al segmento.
    def s_de(self, x, z):
        e = self.escalera
        s = (x - e.ax) * self._ux + (z - e.az) * self._uz
        return min(self.largo, max(0.0, s))

    # Altura de peldaño bajo (x, z) o None si el punto no está sobre la escalera (Escalera.contiene).
    def altura_en(self, x, z):
        if not self.escalera.contiene(x, z):
            return None
        return self.altura_en_s(self.s_de(x, z))

    # ¿Se sube yendo del punto (x, z) hacia (x2, z2)? Compara el nivel de peldaño de ambos puntos
    # proyectados; con la misma altura mira hacia dónde está la punta alta.
    def sube_hacia(self, x, z, x2, z2):
        s0, s1 = self.s_de(x, z), self.s_de(x2, z2)
        if abs(s1 - s0) < 1e-9:
            return False
        return (s1 > s0) == self.baja_en_a


# Altura de peldaño más cercana a (x, z) entre varios perfiles (None si no está sobre ninguno).
def altura_sobre_escaleras(perfiles, x, z):
    for perfil in perfiles:
        h = perfil.altura_en(x, z)
        if h is not None:
            return h
    return None

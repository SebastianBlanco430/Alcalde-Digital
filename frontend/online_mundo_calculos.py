# Lógica PURA (sin ursina ni panda3d) del mundo online: cómo se dibuja un jugador remoto a partir de la
# muestra interpolada (banderas, altura, sombra, «ausente»), cómo se aplica una corrección del anfitrión al
# jugador local, los textos del HUD en línea (ping, reconexión, decisiones de otros, saludos rápidos) y el
# planificador de avisos. frontend/online_mundo.py y frontend/online_hud.py solo dibujan lo que sale de aquí.
#
# Todo texto que viene de la red (alias) pasa por backend.red.saneado.sanear_texto_visible antes de mostrarse:
# Ursina Text interpreta «<tags>» y «<image:...>».

import math
import time
from dataclasses import dataclass

from backend.red.saneado import sanear_texto_visible

# Máscara de banderas del snapshot (igual que backend.red.sesion_en_linea.BANDERAS).
BIT_AIRE, BIT_ESCALERA, BIT_DENTRO, BIT_VEHICULO = 1, 2, 4, 8

# Corrección del anfitrión al jugador LOCAL.
UMBRAL_CORRECCION_NULA = 0.02       # m: por debajo no se hace nada
UMBRAL_CORRECCION_SUAVE = 1.0       # m: hasta aquí se difumina visualmente; más = salto brusco
TAU_SUAVIZADO = 0.12                # s: constante de tiempo del difuminado
CORRECCION_NULA, CORRECCION_SUAVE, CORRECCION_BRUSCA = "nula", "suave", "brusca"

# Opacidad del avatar de un jugador desconectado («ausente»).
ALFA_AUSENTE = 0.45
SUFIJO_AUSENTE = " (ausente)"

# Avisos.
DURACION_AVISO = 3.0                # s que dura un aviso puntual
DURACION_SALUDO = 3.5
MAX_COLA_AVISOS = 4
TEXTO_INESTABLE = "Conexión inestable"
TEXTO_ESPERANDO = "Esperando a tus compañeros"
RETARDO_ESPERANDO = 1.5             # s sin misión antes de mostrar «Esperando»

# Saludos rápidos (lista FIJA, sin chat libre): el protocolo manda el índice 0..15.
SALUDOS = (
    "¡Hola!",
    "¡Buen trabajo!",
    "¡Ayuda, por favor!",
    "Voy para allá",
    "Espérame",
    "Gracias",
    "¡Vamos!",
    "Buena decisión",
)
COOLDOWN_SALUDO = 1.2               # s mínimo entre saludos propios (el anfitrión admite 1/s)

ETIQUETA_INDICADOR = {"convivencia": "convivencia", "confianza": "confianza", "desinformacion": "desinformación"}


# ---------------------------------------------------------------------------------------------
# Jugadores remotos
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EstadoVisual:
    x: float
    z: float
    y: float
    rumbo: float
    velocidad: float
    en_aire: bool
    escalera: bool
    dentro: bool
    vehiculo: bool
    ausente: bool

    # Un jugador que está dentro de un edificio no se dibuja en la calle.
    @property
    def visible(self):
        return not self.dentro


# Traduce la muestra interpolada (backend.red.interpolacion_calculos.Muestra) y el estado de conexión a lo
# que hay que dibujar. El desconectado queda quieto y sin saltar ni subir escaleras («pose quieta»).
def estado_visual(muestra, conectado=True):
    f = muestra.f if isinstance(muestra.f, int) and not isinstance(muestra.f, bool) else 0
    ausente = not conectado
    en_aire = bool(f & BIT_AIRE) and not ausente
    return EstadoVisual(
        x=muestra.x, z=muestra.z, y=muestra.y, rumbo=muestra.r % 360.0,
        velocidad=0.0 if ausente else max(0.0, muestra.v),
        en_aire=en_aire,
        escalera=bool(f & BIT_ESCALERA) and not en_aire and not ausente,
        dentro=bool(f & BIT_DENTRO),
        vehiculo=bool(f & BIT_VEHICULO),
        ausente=ausente)


# Velocidad vertical (m/s) estimada entre dos alturas consecutivas; 0 si dt es inútil. Alimenta la pose de
# salto (subida / caída) del animador humano.
def velocidad_vertical(y_anterior, y, dt, suavizado=0.5, anterior=0.0):
    if y_anterior is None or dt is None or dt <= 1e-4:
        return anterior
    bruta = (y - y_anterior) / dt
    bruta = max(-30.0, min(30.0, bruta))
    return anterior + (bruta - anterior) * suavizado


# Elevación (m) del avatar sobre el suelo que pisa: lo que hay que bajar la sombra y el aro para que se queden
# en el suelo mientras vuela. 0 si no está en el aire.
def elevacion_sobre_suelo(y, suelo_y, en_aire):
    if not en_aire or suelo_y is None:
        return 0.0
    return max(0.0, y - suelo_y)


# Texto de la etiqueta sobre el avatar: alias saneado (+ «(ausente)» si está desconectado).
def texto_etiqueta(nombre, ausente=False):
    base = sanear_texto_visible(str(nombre))
    return base + SUFIJO_AUSENTE if ausente else base


# ---------------------------------------------------------------------------------------------
# Corrección del anfitrión (jugador local)
# ---------------------------------------------------------------------------------------------
# «nula» (casi igual), «suave» (se difumina en TAU_SUAVIZADO) o «brusca» (salto, p. ej. te sacó de una pared).
def clasificar_correccion(distancia):
    if not isinstance(distancia, (int, float)) or not math.isfinite(distancia):
        return CORRECCION_BRUSCA
    if distancia < UMBRAL_CORRECCION_NULA:
        return CORRECCION_NULA
    if distancia <= UMBRAL_CORRECCION_SUAVE:
        return CORRECCION_SUAVE
    return CORRECCION_BRUSCA


# Desfase visual que decae exponencialmente: el avatar se dibuja en (verdad + desfase) y el desfase tiende a 0.
class SuavizadoCorreccion:

    def __init__(self, tau=TAU_SUAVIZADO):
        self.tau = tau
        self.ox = 0.0
        self.oz = 0.0

    def iniciar(self, ox, oz):
        self.ox, self.oz = float(ox), float(oz)

    @property
    def activo(self):
        return abs(self.ox) > 1e-3 or abs(self.oz) > 1e-3

    def avanzar(self, dt):
        k = math.exp(-max(0.0, dt) / self.tau) if self.tau > 0 else 0.0
        self.ox *= k
        self.oz *= k
        if not self.activo:
            self.ox = self.oz = 0.0
        return self.ox, self.oz

    def cancelar(self):
        self.ox = self.oz = 0.0


# ---------------------------------------------------------------------------------------------
# Textos del HUD
# ---------------------------------------------------------------------------------------------
# Pastilla de ping CON TEXTO («42 ms»): el color nunca es la única señal (filtros de daltonismo).
def texto_ping(ms):
    if ms is None or isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms) or ms < 0:
        return "— ms"
    return f"{int(round(ms))} ms"


def texto_reconectando(segundos):
    return f"Reconectando… ({int(max(0, segundos))} s)"


# «Ana decidió: +3 confianza, −2 desinformación» (ceros fuera; None si no hay nada que decir).
def texto_decision(nombre, deltas):
    partes = []
    for clave in ("convivencia", "confianza", "desinformacion"):
        valor = deltas.get(clave) if isinstance(deltas, dict) else None
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not valor:
            continue
        signo = "+" if valor > 0 else "−"
        partes.append(f"{signo}{abs(int(round(valor)))} {ETIQUETA_INDICADOR[clave]}")
    if not partes:
        return None
    return f"{sanear_texto_visible(str(nombre))} decidió: " + ", ".join(partes)


def texto_saludo(nombre, indice):
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(SALUDOS):
        frase = SALUDOS[0]
    else:
        frase = SALUDOS[indice]
    return f"{sanear_texto_visible(str(nombre))}: {frase}"


# Texto del panel de turno en línea (no hay turnos): quién eres y cuántos están en la sala.
def texto_turno_online(nombre, nombre_rol, n_jugadores):
    jugadores = "1 jugador" if n_jugadores == 1 else f"{n_jugadores} jugadores"
    return f"{sanear_texto_visible(str(nombre))} ({nombre_rol}) · {jugadores}"


# ¿Mostrar «Esperando a tus compañeros»? El jugador local no tiene misión y la partida sigue.
def esperando_companeros(hay_mision, terminada, desconectado):
    return (not hay_mision) and (not terminada) and (not desconectado)


# ---------------------------------------------------------------------------------------------
# Planificador de avisos
# ---------------------------------------------------------------------------------------------
# Un solo texto visible a la vez, por prioridad: condición de red (reconectando / inestable) > avisos puntuales
# (cola, cada uno `duracion` s) > aviso persistente de baja prioridad («Esperando a tus compañeros»).
class PlanificadorAvisos:

    def __init__(self, reloj=time.monotonic, retardo_persistente=RETARDO_ESPERANDO):
        self._reloj = reloj
        self._retardo_persistente = retardo_persistente
        self._condicion = None
        self._persistente = None
        self._cola = []                 # [(texto, expira)]
        self._desde_persistente = None

    def condicion(self, texto):
        self._condicion = texto or None

    def persistente(self, texto):
        if texto != self._persistente:
            self._persistente = texto or None
            self._desde_persistente = self._reloj()

    def empujar(self, texto, duracion=DURACION_AVISO):
        if not texto:
            return
        if self._cola and self._cola[-1][0] == texto:
            return
        self._cola.append((texto, None, float(duracion)))
        self._cola = self._cola[-MAX_COLA_AVISOS:]

    # Texto a mostrar ahora (o None). El primer aviso puntual arranca su cuenta al empezar a mostrarse.
    def actual(self):
        ahora = self._reloj()
        if self._condicion:
            return self._condicion
        while self._cola:
            texto, inicio, duracion = self._cola[0]
            if inicio is None:
                inicio = ahora
                self._cola[0] = (texto, inicio, duracion)
            if ahora - inicio >= duracion:
                self._cola.pop(0)
                continue
            return texto
        if self._persistente and ahora - self._desde_persistente >= self._retardo_persistente:
            return self._persistente
        return None

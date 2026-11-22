# La gente reacciona al jugador (M8 del plan ambiente y pulseras; ALCALDE_NPC_REACCION=0 = como antes). Puro: sin ursina.
# Cuando un peatón ENTRA a menos de RADIO m del jugador, ~30 % reaccionan (fijo por NPC y encuentro, no al azar global):
#   florece / sano   «saludo»: se gira hacia el jugador y suelta un globo corto (frases_npc.json → reaccion.saludo);
#   tenso / apagado  «espalda» (se gira al lado contrario) o «celular» (saca el celular), con un globo seco (reaccion.seco).
# Cada NPC reacciona como mucho una vez por ENFRIAMIENTO s. Al cruzar de nivel (ambiente_vivo.ultimo_evento), hasta
# MAX_CAMBIO NPC cercanos dicen una frase de frases_npc.json → cambio.mejora / cambio.empeora.
# La vista (giro, postura y globo) la pone frontend/registro_ambiente_npc.py. Solo poses procedurales (npc_postura).
import math
import os

NPC_REACCION = True
RADIO = 4.0                 # m al jugador
PROBABILIDAD = 0.30
ENFRIAMIENTO = 45.0         # s entre dos reacciones del mismo NPC
DURACION = 2.6              # s que dura el giro / la postura
RADIO_CAMBIO = 12.0         # m: quién comenta el cambio de nivel
MAX_CAMBIO = 2
NIVELES_BUENOS = ("florece", "sano")
SALUDO, ESPALDA, CELULAR = "saludo", "espalda", "celular"


def activo():
    valor = os.environ.get("ALCALDE_NPC_REACCION", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(NPC_REACCION)


def _azar(*partes):
    """Número fijo 0..1 a partir de enteros/textos (sin hash() de Python: igual en cada ejecución)."""
    n = 1469598103934665603
    for parte in partes:
        for ch in str(parte):
            n = ((n ^ ord(ch)) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        n = ((n ^ 0x7C) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    n = ((n ^ (n >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF      # mezcla final (splitmix64)
    n = ((n ^ (n >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    n ^= n >> 31
    return (n >> 11) / float(1 << 53)


def tipo_reaccion(nivel, clave, encuentro):
    """None (no reacciona) o SALUDO / ESPALDA / CELULAR para ese NPC en su encuentro número `encuentro`."""
    if _azar(clave, encuentro, "r") >= PROBABILIDAD:
        return None
    if nivel in NIVELES_BUENOS:
        return SALUDO
    return ESPALDA if _azar(clave, encuentro, "t") < 0.5 else CELULAR


def grupo_frases(tipo):
    return ("reaccion", "saludo") if tipo == SALUDO else ("reaccion", "seco")


def yaw_hacia(desde, hacia, alejarse=False):
    """Grados (convención de Ursina: rotation_y, 0 = +z) para mirar de `desde` (x, z) a `hacia` (o darle la espalda)."""
    dx, dz = hacia[0] - desde[0], hacia[1] - desde[1]
    yaw = math.degrees(math.atan2(dx, dz))
    return (yaw + 180.0) % 360.0 if alejarse else yaw % 360.0


def elegir_frase(textos, grupo, clave, n):
    """Texto de frases_npc.json[grupo[0]][grupo[1]] (lista de {"t": ...}) elegido fijo por NPC y vez. None si no hay."""
    lista = (textos or {}).get(grupo[0], {}).get(grupo[1], [])
    lista = [f["t"] if isinstance(f, dict) else str(f) for f in lista]
    if not lista:
        return None
    return lista[int(_azar(clave, n, "f") * len(lista)) % len(lista)]


class ReaccionesNPC:
    """Lleva quién está cerca, cuántas veces se encontró con el jugador y su enfriamiento."""

    def __init__(self):
        self.t = 0.0
        self._cerca = set()
        self._encuentros = {}
        self._hasta = {}            # clave -> instante desde el que puede volver a reaccionar
        self.reacciones = 0

    def actualizar(self, dt, npcs, jugador, nivel):
        """`npcs`: [(clave, x, z)]; `jugador`: (x, z). Devuelve [(clave, tipo)] de las reacciones nuevas."""
        self.t += max(0.0, dt)
        nuevas, ahora_cerca = [], set()
        for clave, x, z in npcs:
            if math.hypot(x - jugador[0], z - jugador[1]) > RADIO:
                continue
            ahora_cerca.add(clave)
            if clave in self._cerca:                 # ya estaba cerca: solo cuenta al ENTRAR
                continue
            n = self._encuentros[clave] = self._encuentros.get(clave, 0) + 1
            if self._hasta.get(clave, -1.0) > self.t:
                continue
            tipo = tipo_reaccion(nivel, clave, n)
            if tipo is not None:
                self._hasta[clave] = self.t + ENFRIAMIENTO
                self.reacciones += 1
                nuevas.append((clave, tipo))
        self._cerca = ahora_cerca
        return nuevas


def comentan_cambio(npcs, jugador, maximo=MAX_CAMBIO, radio=RADIO_CAMBIO):
    """Claves de los (hasta `maximo`) NPC más cercanos al jugador dentro de `radio` m."""
    cerca = sorted((math.hypot(x - jugador[0], z - jugador[1]), clave) for clave, x, z in npcs)
    return [clave for d, clave in cerca if d <= radio][:maximo]


def grupo_cambio(direccion):
    return ("cambio", "mejora") if direccion == "sube" else ("cambio", "empeora")

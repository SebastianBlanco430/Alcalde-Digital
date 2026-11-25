# Reloj de la sala en línea (paridad del multijugador, PURO: sin red ni ursina; se prueba en tests/test_b_multi_reloj.py).
# La partida de 1 jugador tiene semana de 15 min con noches saltadas, radio de mañana y noche, sello por días y NPC que
# comentan el día anterior; todo cuelga del reloj (backend/logica/reloj_partida.py), y en línea no había reloj. Aquí el
# ANFITRIÓN lleva UN reloj para toda la sala (es el único escritor, como del resto del estado) y lo reparte:
#
#   - Avanza con el tick del anfitrión (backend/red/anfitrion.py) y se difunde en el mensaje «reloj» (protocolo v7) una
#     vez por segundo y en cada cambio de día o de noche. Los clientes lo pintan con frontend/multi_reloj_linea.py.
#   - A las 20:00 el reloj se para (noche pendiente) y cada cliente pone la radio de la noche. Cuando TODOS los conectados
#     avisan con «noche_lista» (al ponerse la mañana) o pasan PLAZO_NOCHE segundos, el anfitrión salta la noche.
#   - Con el día 7 terminado la partida acaba por tiempo (partida_coop._terminar("tiempo")), como en la local.
#   - El diario del día (misiones cerradas con su veredicto, de toda la sala) viaja con la noche: la radio cuenta el día
#     del grupo, no solo el del cliente.
#
# Bandera ALCALDE_MULTI_PARIDAD (por defecto encendida): =0 deja el multijugador exactamente como antes (sin reloj en
# línea, protocolo v6). Las dos máquinas de una sala tienen que tenerla igual (la versión del protocolo cambia con ella).
#
#   activo()                    ¿paridad del multijugador?
#   preparar(partida)           cuelga un RelojSala de la PartidaCooperativa (o nada, con la bandera apagada)
#   RelojSala.avanzar(dt, ids)  -> campos del mensaje «reloj» si toca difundir, o None

import os

from backend.logica import reloj_partida

_NO = ("0", "false", "no", "off")

# s: la noche pasa aunque falte alguien por cerrar su radio
PLAZO_NOCHE = 20.0
# s entre dos «reloj» sin cambios (los clientes interpolan en medio)
PERIODO_ENVIO = 1.0
# Entradas del diario que caben en el mensaje (lista_str de 16)
MAX_DIARIO = 16
# «id|veredicto» en el diario del mensaje
SEPARADOR = "|"
# s reales del principio en los que el reloj no corre: cada cliente ve el prólogo (frontend/prologo_cinematica.py, unos
# 61 s con sus cartelas; tests/test_b_multi_reloj.py comprueba que esto lo cubre) y en la partida local el reloj está
# parado durante las cinemáticas. Quien lo salta puede jugar ya; la hora espera. Con ALCALDE_PROLOGO=0 no se espera.
ESPERA_INICIO = 65.0
# s de gracia al acabar la semana para quien está dentro de un minijuego (la local para el reloj con la misión en curso)
GRACIA_FIN = 60.0
# s reales: tope de un paso del reloj de la sala (un tick atascado no salta horas)
DT_MAX_SALA = 2.0


def activo():
    """¿Paridad del multijugador? Encendida salvo ALCALDE_MULTI_PARIDAD=0 (se lee en cada llamada). Sin constante en el
    código a propósito: la versión del protocolo (backend/red/protocolo.py) se decide con esta MISMA regla del entorno,
    así dos equipos con la paridad distinta nunca se conectan con la misma versión."""
    return os.environ.get("ALCALDE_MULTI_PARIDAD", "").strip().lower() not in _NO


def diario_a_texto(entradas):
    """[{"id", "veredicto"}] -> ["id|veredicto"] (las últimas MAX_DIARIO; veredicto vacío = sin carta de misión)."""
    return [f"{e['id']}{SEPARADOR}{e.get('veredicto') or ''}"[:64] for e in entradas][-MAX_DIARIO:]


def diario_de_texto(lista):
    """["id|veredicto"] -> [{"id", "veredicto"}] (veredicto None si venía vacío). Ignora lo mal formado."""
    salida = []
    for texto in lista or ():
        if not isinstance(texto, str) or SEPARADOR not in texto:
            continue
        id_mision, veredicto = texto.rsplit(SEPARADOR, 1)
        if id_mision:
            salida.append({"id": id_mision, "veredicto": veredicto or None})
    return salida


class RelojSala:
    """El reloj de la partida en el anfitrión, con la espera de la noche y el diario de la sala."""

    def __init__(self, reloj=None, plazo_noche=PLAZO_NOCHE, periodo=PERIODO_ENVIO, espera_inicio=0.0):
        # Siempre con noches saltadas (como la feria): el reloj espejo de los clientes (frontend/multi_reloj_linea.py) y
        # la radio de la noche cuentan con el cierre de las 20:00; con ALCALDE_HILO_NOCHES=0 en el anfitrión los clientes
        # verían la hora a saltos y la noche no llegaría nunca.
        self.reloj = reloj if reloj is not None else reloj_partida.RelojPartida(noches=True)
        self.plazo_noche = float(plazo_noche)
        self.periodo = float(periodo)
        # s que quedan antes de que el reloj empiece a correr (el prólogo de los clientes)
        self.espera = float(espera_inicio)
        # Ids que ya cerraron la radio de esta noche
        self.listos = set()
        self.t_noche = 0.0
        # {día: [{"id", "veredicto"}]}
        self.diario = {}
        # El primer avance ya difunde
        self._t_envio = self.periodo
        # (día, noche, fin) del último mensaje
        self._visto = None

    # -- Partida --

    def anotar(self, id_mision, veredicto=None):
        """Una misión cerrada por cualquiera de la sala, en el día de hoy."""
        self.diario.setdefault(self.reloj.dia(), []).append({"id": str(id_mision), "veredicto": veredicto})

    def noche_lista(self, id_jugador, dia):
        """El jugador cerró la radio de la noche del día `dia` (si es la de hoy y hay noche pendiente)."""
        if self.reloj.noche_pendiente() and int(dia) == self.reloj.dia():
            self.listos.add(id_jugador)

    def terminado(self):
        return self.reloj.terminado()

    # -- Tick --

    def avanzar(self, dt, conectados):
        """Avanza `dt` segundos reales con los ids `conectados`. Devuelve los campos de «reloj» si toca difundirlo."""
        dt = max(0.0, float(dt))
        if self.espera > 0.0:
            self.espera = max(0.0, self.espera - dt)
        elif self.reloj.noche_pendiente():
            self.t_noche += dt
            vivos = set(conectados)
            if not vivos or vivos <= self.listos or self.t_noche >= self.plazo_noche:
                self.reloj.pasar_noche()
                self.listos.clear()
                self.t_noche = 0.0
        else:
            # El tick del anfitrión es de 1 s y RelojPartida.avanzar recorta cada paso a 0,5 s (DT_MAX, pensado para
            # frames): se suma en horas, con un tope propio por si el anfitrión se atasca.
            self.reloj.avanzar_horas(min(dt, DT_MAX_SALA) / self.reloj.seg_por_hora())
        self._t_envio += dt
        clave = (self.reloj.dia(), self.reloj.noche_pendiente(), self.reloj.terminado())
        if clave != self._visto or self._t_envio >= self.periodo:
            self._visto = clave
            self._t_envio = 0.0
            return self.estado()
        return None

    def estado(self):
        """Campos del mensaje «reloj» (sin la «t»)."""
        dia, noche = self.reloj.dia(), self.reloj.noche_pendiente()
        campos = {"dia": dia, "hora": round(float(self.reloj.hora()), 3), "noche": bool(noche),
                  "fin": bool(self.reloj.terminado())}
        if noche:
            campos["diario"] = diario_a_texto(self.diario.get(dia, []))
        return campos


def preparar(partida):
    """Cuelga el reloj de la sala de la partida (servidor.construir_anfitrion). Con la bandera apagada, nada."""
    sin_prologo = os.environ.get("ALCALDE_PROLOGO", "").strip().lower() in _NO
    partida.reloj_sala = RelojSala(espera_inicio=0.0 if sin_prologo else ESPERA_INICIO) if activo() else None
    return partida.reloj_sala

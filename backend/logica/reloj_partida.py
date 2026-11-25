# Reloj de la partida (modelo puro, sin ursina): 7 días de juego. Es el eje de tiempo del plan final (docs/PLAN_FINAL.md):
# de él cuelgan el fin por tiempo, los efectos retardados y el costo de aislamiento (backend/logica/flujo_tiempo.py).
#
# ESCALA. La partida empieza el día 1 a las 08:00 y termina al COMPLETAR el día 7 (24:00 del día 7). Cada hora de juego
# dura SEGUNDOS_REALES_POR_HORA = 11,25 s reales: 1 día = 4,5 min y la partida entera (160 h de juego) = 30 min reales
# (tope pedido para la entrega; antes eran 15 s y 40 min).
# ALCALDE_SEG_POR_HORA=<n> cambia la escala (p. ej. 2 para probar la semana en ~5 min); se lee al crear cada reloj.
#
# CUÁNDO CORRE (decisión): solo con el MUNDO ACTIVO. El reloj no lee ningún reloj real: avanza únicamente cuando alguien
# llama a avanzar(dt). El frontend lo llama una vez por frame con el mundo en primer plano y NO lo llama (o lo deja en
# pausa con pausar()) en menús, minijuegos, modales, cinemáticas y pausa. Así leer una carta o trabajar no «gasta» la
# semana, y el reloj es determinista: las pruebas lo mueven con avanzar() / avanzar_horas().
#
# Un frame muy largo (carga de chunks, ventana en segundo plano) no puede comerse horas de juego: avanzar() recorta cada
# dt a DT_MAX segundos reales. avanzar_horas() no recorta (pruebas, simulaciones y depuración).
#
# BANDERA. RELOJ = False (o ALCALDE_RELOJ=0) lo apaga: main.py no envuelve el flujo y el juego es el de antes (la partida
# termina solo al agotar el catálogo). En línea no existe (el protocolo no lo conoce): ver docs/PLAN_FINAL.md.
#
# NOCHES SALTADAS (hilo conductor, docs/HILO_CONDUCTOR.md; NOCHES = True o ALCALDE_HILO_NOCHES=1/0). Cada día se juega de
# 08:00 a HORA_CIERRE (20:00): el reloj se DETIENE a las 20:00 (noche_pendiente() -> True) hasta que alguien llama a
# pasar_noche(), que salta a las 08:00 del día siguiente (lo hace la radio tras su emisión de la noche, o FlujoConTiempo
# si nadie la retiene). La partida termina el día 7 a las 20:00: 7 x 12 = 84 h activas. La escala por defecto pasa a
# SEGUNDOS_REALES_POR_HORA_NOCHES = 900 / 84 ≈ 10,71 s (partida de 15 min); ALCALDE_SEG_POR_HORA sigue mandando.
# fraccion_partida() cuenta solo horas activas; horas_restantes() sigue siendo de reloj (hasta el fin, noches incluidas).
# Con la bandera apagada todo es como antes (días de 24 h, fin a las 24:00 del día 7).
#
#   reloj = RelojPartida()
#   reloj.avanzar(dt)            -> horas de juego que avanzó (0.0 si está en pausa o terminado)
#   reloj.pausar() / reanudar() / en_pausa()
#   reloj.dia()                  -> 1..7
#   reloj.hora()                 -> 0.0..24.0 (24.0 solo al terminar el día 7)
#   reloj.hora_texto()           -> «Día 3 · 14:30»
#   reloj.tiempo_absoluto()      -> horas desde las 00:00 del día 1 (arranca en 8.0); sirve de marca de tiempo
#   reloj.fraccion_partida()     -> 0.0..1.0
#   reloj.terminado()            -> True al completar el día 7
#   reloj.a_dict() / RelojPartida.desde_dict(datos)
#   reloj.noche_pendiente()      -> True parado a las 20:00 de un día 1..6 (solo con noches saltadas)
#   reloj.pasar_noche()          -> salta a las 08:00 del día siguiente; True si saltó
#   reloj.avanzar_hacia(t, h)    -> avanza como mucho `h` horas hacia la marca absoluta `t` (modo feria)

import math
import os

RELOJ = True
NOCHES = True                       # noches saltadas y partida de 15 min (ALCALDE_HILO_NOCHES=0 la apaga)

DIAS = 7
HORAS_POR_DIA = 24.0
HORA_INICIO = 8.0                   # el día 1 empieza a las 08:00
HORA_CIERRE = 20.0                  # con noches saltadas, el día se cierra a las 20:00
SEGUNDOS_REALES_POR_HORA = 11.25    # 1 día = 4,5 min reales; partida (160 h) = 30 min
# Objetivo de 15 min reales con noches saltadas: 7 días x 12 h activas = 84 h -> 900 / 84 ≈ 10,71 s por hora.
MINUTOS_OBJETIVO_NOCHES = 15.0
SEGUNDOS_REALES_POR_HORA_NOCHES = MINUTOS_OBJETIVO_NOCHES * 60.0 / (DIAS * (HORA_CIERRE - HORA_INICIO))
DT_MAX = 0.5                        # s reales: tope de un paso de avanzar()

_VERSION = 1
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Hay reloj de partida? ALCALDE_RELOJ=1/0 manda sobre RELOJ (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_RELOJ", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(RELOJ)


def noches_activas():
    """¿Se saltan las noches (días de 08:00 a 20:00)? ALCALDE_HILO_NOCHES=1/0 manda sobre NOCHES (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_HILO_NOCHES", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(NOCHES)


def segundos_por_hora(noches=None):
    """Segundos reales por hora de juego: ALCALDE_SEG_POR_HORA si es un número positivo; si no, la constante (la de 15
    min si se saltan las noches). `noches` None = noches_activas()."""
    crudo = os.environ.get("ALCALDE_SEG_POR_HORA", "").strip()
    if crudo:
        try:
            valor = float(crudo)
        except ValueError:
            valor = 0.0
        if math.isfinite(valor) and valor > 0:
            return valor
    noches = noches_activas() if noches is None else bool(noches)
    return SEGUNDOS_REALES_POR_HORA_NOCHES if noches else SEGUNDOS_REALES_POR_HORA


def _numero(valor, nombre, minimo=None):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito.")
    if minimo is not None and valor < minimo:
        raise ValueError(f"{nombre} inválido: {valor!r}; debe ser >= {minimo}.")
    return float(valor)


def texto_de(tiempo_absoluto):
    """«Día 3 · 14:30» de una marca de tiempo absoluta (horas desde las 00:00 del día 1). Sirve para los avisos."""
    minutos = int(math.floor(max(0.0, tiempo_absoluto) * 60.0 + 1e-6))
    dia, resto = divmod(minutos, int(HORAS_POR_DIA) * 60)
    return f"Día {dia + 1} · {resto // 60:02d}:{resto % 60:02d}"


class RelojPartida:

    # `seg_por_hora`: None = segundos_por_hora() (constante o variable de entorno). `dias` y `hora_inicio` existen para
    # las pruebas; el juego usa los valores por defecto. `noches`: True, False o None (= noches_activas()).
    def __init__(self, seg_por_hora=None, dias=DIAS, hora_inicio=HORA_INICIO, noches=None):
        self._noches = noches_activas() if noches is None else bool(noches)
        self._seg_por_hora = _numero(seg_por_hora if seg_por_hora is not None else segundos_por_hora(self._noches),
                                     "seg_por_hora", 1e-6)
        if isinstance(dias, bool) or not isinstance(dias, int) or dias < 1:
            raise ValueError(f"dias inválido: {dias!r}.")
        self._dias = dias
        self._hora_inicio = _numero(hora_inicio, "hora_inicio", 0.0)
        if self._hora_inicio >= HORAS_POR_DIA:
            raise ValueError(f"hora_inicio inválida: {hora_inicio!r}; debe ser menor que 24.")
        self._absoluto = self._hora_inicio      # horas desde las 00:00 del día 1
        self._pausado = False

    # -- Avance --

    # Avanza `dt` segundos REALES (recortados a DT_MAX). No hace nada en pausa o con la partida terminada. Devuelve las
    # horas de juego avanzadas. ValueError si dt no es un número finito >= 0.
    def avanzar(self, dt):
        dt = min(_numero(dt, "dt", 0.0), DT_MAX)
        return self._sumar(dt / self._seg_por_hora)

    # Avanza `horas` de juego sin el recorte de DT_MAX (la pausa y el fin mandan igual). Para pruebas y simulación.
    def avanzar_horas(self, horas):
        return self._sumar(_numero(horas, "horas", 0.0))

    def _sumar(self, horas):
        if self._pausado or self.terminado():
            return 0.0
        nuevo = min(self._tope(), self._absoluto + horas)
        avance, self._absoluto = nuevo - self._absoluto, nuevo
        return avance

    # Modo feria: avanza como mucho `horas` hacia la marca absoluta `objetivo` (nunca pasa del cierre del día ni vuelve
    # atrás). Respeta la pausa y el fin, como _sumar.
    def avanzar_hacia(self, objetivo, horas):
        falta = _numero(objetivo, "objetivo") - self._absoluto
        if falta <= 0:
            return 0.0
        return self._sumar(min(falta, _numero(horas, "horas", 0.0)))

    # -- Noches saltadas --

    def noches(self):
        return self._noches

    # Hasta dónde puede llegar el reloj sin que nadie salte la noche: el cierre del día (20:00) o el fin de la partida.
    def _tope(self):
        if not self._noches:
            return self._fin()
        return min(self._fin(), (self.dia() - 1) * HORAS_POR_DIA + HORA_CIERRE)

    def noche_pendiente(self):
        return self._noches and not self.terminado() and self._absoluto >= self._tope() - 1e-9

    # Salta a las 08:00 (hora de inicio) del día siguiente. Solo con la noche pendiente; True si saltó.
    def pasar_noche(self):
        if not self.noche_pendiente():
            return False
        self._absoluto = self.dia() * HORAS_POR_DIA + self._hora_inicio
        return True

    def pausar(self):
        self._pausado = True

    def reanudar(self):
        self._pausado = False

    def en_pausa(self):
        return self._pausado

    # -- Lectura --

    def _fin(self):
        if self._noches:
            return (self._dias - 1) * HORAS_POR_DIA + HORA_CIERRE
        return self._dias * HORAS_POR_DIA

    def seg_por_hora(self):
        return self._seg_por_hora

    def dias(self):
        return self._dias

    def tiempo_absoluto(self):
        return self._absoluto

    def horas_transcurridas(self):
        return self._absoluto - self._hora_inicio

    def horas_restantes(self):
        return self._fin() - self._absoluto

    def dia(self):
        return min(self._dias, int(self._absoluto // HORAS_POR_DIA) + 1)

    def hora(self):
        return self._absoluto - (self.dia() - 1) * HORAS_POR_DIA

    def hora_texto(self):
        if self.terminado():
            return texto_de(self._fin()) if self._noches else f"Día {self._dias} · 24:00"
        return texto_de(self._absoluto)

    # Con noches saltadas solo cuentan las horas activas (08:00-20:00 de cada día).
    def fraccion_partida(self):
        if self._noches:
            activas_dia = HORA_CIERRE - self._hora_inicio
            hechas = (self.dia() - 1) * activas_dia + min(activas_dia, max(0.0, self.hora() - self._hora_inicio))
            return min(1.0, max(0.0, hechas / (self._dias * activas_dia)))
        return min(1.0, max(0.0, self.horas_transcurridas() / (self._fin() - self._hora_inicio)))

    def terminado(self):
        return self._absoluto >= self._fin() - 1e-9

    # -- Serialización (JSON) --

    def a_dict(self):
        return {"version": _VERSION, "absoluto": self._absoluto, "pausado": self._pausado, "dias": self._dias,
                "hora_inicio": self._hora_inicio}

    # La escala (seg_por_hora) NO se guarda: es un ajuste de la sesión, no de la partida. Las noches saltadas tampoco
    # (las decide la bandera al restaurar; un guardado de días de 24 h con hora pasada de las 20:00 queda con la noche
    # pendiente). ValueError si los datos no son válidos (quien restaura decide: flujo_tiempo vuelve al reloj recién creado).
    @classmethod
    def desde_dict(cls, datos, seg_por_hora=None, noches=None):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Reloj guardado con formato desconocido.")
        reloj = cls(seg_por_hora, datos.get("dias", DIAS), datos.get("hora_inicio", HORA_INICIO), noches)
        absoluto = _numero(datos.get("absoluto"), "absoluto", 0.0)
        reloj._absoluto = min(reloj._fin(), max(reloj._hora_inicio, absoluto))
        reloj._pausado = bool(datos.get("pausado", False))
        return reloj

    def __repr__(self):
        return f"RelojPartida({self.hora_texto()!r}, pausado={self._pausado})"

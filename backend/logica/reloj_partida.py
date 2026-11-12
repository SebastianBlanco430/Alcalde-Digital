# Reloj de la partida (modelo puro, sin ursina): 7 días de juego. Es el eje de tiempo del plan final (docs/PLAN_FINAL.md):
# de él cuelgan el fin por tiempo, los efectos retardados y el costo de aislamiento (backend/logica/flujo_tiempo.py).
#
# ESCALA. La partida empieza el día 1 a las 08:00 y termina al COMPLETAR el día 7 (24:00 del día 7). Cada hora de juego
# dura SEGUNDOS_REALES_POR_HORA = 15 s reales: 1 día = 6 min y la partida entera (160 h de juego) = 40 min reales.
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

import math
import os

RELOJ = True

DIAS = 7
HORAS_POR_DIA = 24.0
HORA_INICIO = 8.0                   # el día 1 empieza a las 08:00
SEGUNDOS_REALES_POR_HORA = 15.0     # 1 día = 6 min reales; partida ≈ 40 min
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


def segundos_por_hora():
    """Segundos reales por hora de juego: ALCALDE_SEG_POR_HORA si es un número positivo; si no, la constante."""
    crudo = os.environ.get("ALCALDE_SEG_POR_HORA", "").strip()
    if crudo:
        try:
            valor = float(crudo)
        except ValueError:
            valor = 0.0
        if math.isfinite(valor) and valor > 0:
            return valor
    return SEGUNDOS_REALES_POR_HORA


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
    # las pruebas; el juego usa los valores por defecto.
    def __init__(self, seg_por_hora=None, dias=DIAS, hora_inicio=HORA_INICIO):
        self._seg_por_hora = _numero(seg_por_hora if seg_por_hora is not None else segundos_por_hora(),
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
        nuevo = min(self._fin(), self._absoluto + horas)
        avance, self._absoluto = nuevo - self._absoluto, nuevo
        return avance

    def pausar(self):
        self._pausado = True

    def reanudar(self):
        self._pausado = False

    def en_pausa(self):
        return self._pausado

    # -- Lectura --

    def _fin(self):
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
            return f"Día {self._dias} · 24:00"
        return texto_de(self._absoluto)

    def fraccion_partida(self):
        return min(1.0, max(0.0, self.horas_transcurridas() / (self._fin() - self._hora_inicio)))

    def terminado(self):
        return self._absoluto >= self._fin() - 1e-9

    # -- Serialización (JSON) --

    def a_dict(self):
        return {"version": _VERSION, "absoluto": self._absoluto, "pausado": self._pausado, "dias": self._dias,
                "hora_inicio": self._hora_inicio}

    # La escala (seg_por_hora) NO se guarda: es un ajuste de la sesión, no de la partida. ValueError si los datos no son
    # válidos (quien restaura decide: flujo_tiempo vuelve al reloj recién creado).
    @classmethod
    def desde_dict(cls, datos, seg_por_hora=None):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Reloj guardado con formato desconocido.")
        reloj = cls(seg_por_hora, datos.get("dias", DIAS), datos.get("hora_inicio", HORA_INICIO))
        absoluto = _numero(datos.get("absoluto"), "absoluto", 0.0)
        reloj._absoluto = min(reloj._fin(), max(reloj._hora_inicio, absoluto))
        reloj._pausado = bool(datos.get("pausado", False))
        return reloj

    def __repr__(self):
        return f"RelojPartida({self.hora_texto()!r}, pausado={self._pausado})"

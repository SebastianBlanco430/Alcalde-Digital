# Costo de aislamiento (modelo puro, serializable, sin ursina). Guía de diseño del plan final: la mejor estrategia NO puede
# ser desconectarse. Si el jugador pasa GRACIA_HORAS de juego sin PARTICIPAR (sin cerrar ninguna misión: ni decidir sobre
# una noticia, ni resolver un caso, ni un parkour), la ciudad nota su ausencia: convivencia y confianza decaen despacio.
#
# REGLA
#   - «Participar» = cerrar una misión (FlujoConTiempo.completar_mision / revisar_misiones_digitales llaman a participar()).
#   - Pasadas GRACIA_HORAS = 24 h de juego (6 min reales) desde la última participación, se acumulan PUNTOS_POR_HORA = 0,25
#     puntos por hora de juego. Se cobran en puntos ENTEROS (un punto cada 4 h): cada punto resta 1 a los indicadores
#     «convivencia» y «confianza» y, con GameState, 1 a la confianza de «ciudadanos» e «instituciones».
#   - TOPE_PUNTOS = 16 en TODA la partida: ignorar siempre deja convivencia y confianza en 34 (de 50) y el índice de
#     confianza por grupos en 39,3 (final malo por poco), nunca en cero. Al volver a participar el contador de horas se
#     reinicia, pero lo perdido no vuelve solo: hay que ganarlo jugando.
#   - Solo cuenta mientras HAY una misión que atender: con el catálogo agotado no se puede participar y no se cobra
#     (lo decide FlujoConTiempo, que entonces llama a participar()).
#   - Avisos (texto para el HUD): uno al empezar a decaer en cada racha de ausencia y otro al llegar al tope.
# Las cifras de la simulación (ignorar / compartir todo / verificar con criterio) están en docs/PLAN_FINAL.md y las vigila
# tests/test_equilibrio_estrategias.py.
#
#   costo = CostoAislamiento()
#   costo.participar(ahora)          # ahora = reloj.tiempo_absoluto()
#   costo.avanzar(ahora)             -> Cobro(puntos, aviso): puntos enteros a restar AHORA (0 casi siempre) y aviso o None
#   costo.horas_sin_participar(ahora), costo.total(), costo.en_tope()
#   efecto_de(puntos)                -> efectos_retardados.Efecto listo para efectos_retardados.aplicar
#   costo.a_dict() / CostoAislamiento.desde_dict(datos)
#
# BANDERA. AISLAMIENTO = False (o ALCALDE_AISLAMIENTO=0): el flujo no crea el contador y no hay decaimiento.

import math
import os
from collections import namedtuple

AISLAMIENTO = True

GRACIA_HORAS = 24.0
PUNTOS_POR_HORA = 0.25
TOPE_PUNTOS = 16
INDICADORES_AFECTADOS = ("convivencia", "confianza")
GRUPOS_AFECTADOS = ("ciudadanos", "instituciones")

AVISO_INICIO = ("Llevas un día sin participar en la vida de la ciudad: la gente nota tu ausencia y la convivencia y la "
                "confianza empiezan a bajar.")
AVISO_TOPE = ("Tu ausencia ya le costó a la ciudad todo lo que podía costarle. No bajará más por esto, pero tampoco se "
              "recupera sola: hay que volver a participar.")
MENSAJE_EFECTO = "Nadie respondió por la ciudad: la convivencia y la confianza se resienten."

_VERSION = 1
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")

Cobro = namedtuple("Cobro", "puntos aviso")
SIN_COBRO = Cobro(0, None)


def activo():
    """¿Hay costo de aislamiento? ALCALDE_AISLAMIENTO=1/0 manda sobre la constante."""
    valor = os.environ.get("ALCALDE_AISLAMIENTO", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(AISLAMIENTO)


def _hora(valor, nombre="ahora"):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito de horas.")
    return float(valor)


def efecto_de(puntos):
    """El Efecto (efectos_retardados) que resta `puntos` a los indicadores y grupos afectados."""
    from backend.logica import efectos_retardados
    return efectos_retardados.crear_efecto(
        "aislamiento", MENSAJE_EFECTO, {n: -puntos for n in INDICADORES_AFECTADOS},
        {g: -puntos for g in GRUPOS_AFECTADOS}, "aislamiento")


class CostoAislamiento:

    def __init__(self, gracia=GRACIA_HORAS, puntos_por_hora=PUNTOS_POR_HORA, tope=TOPE_PUNTOS):
        self._gracia = max(0.0, _hora(gracia, "gracia"))
        self._ritmo = max(0.0, _hora(puntos_por_hora, "puntos_por_hora"))
        self._tope = max(0, int(tope))
        self._ultima = None             # hora absoluta de la última participación (None = aún no se ha mirado el reloj)
        self._cobrado_hasta = None      # hora hasta la que ya se acumuló decaimiento
        self._resto = 0.0               # fracción de punto acumulada sin cobrar
        self._total = 0                 # puntos cobrados en toda la partida
        self._avisado = False           # ya se avisó del inicio en esta racha de ausencia

    # El jugador cerró una misión: se reinicia la cuenta de horas (lo ya perdido NO vuelve).
    def participar(self, ahora):
        self._ultima = _hora(ahora)
        self._cobrado_hasta = None
        self._resto = 0.0
        self._avisado = False

    # Llamar al avanzar el reloj. Devuelve Cobro(puntos, aviso). La primera llamada solo anota la hora de partida.
    def avanzar(self, ahora):
        ahora = _hora(ahora)
        if self._ultima is None:
            self._ultima = ahora
            return SIN_COBRO
        if self._total >= self._tope:
            return SIN_COBRO
        desde = max(self._ultima + self._gracia, self._cobrado_hasta if self._cobrado_hasta is not None else -math.inf)
        if ahora <= desde:
            return SIN_COBRO
        self._resto += (ahora - desde) * self._ritmo
        self._cobrado_hasta = ahora
        puntos = min(int(self._resto + 1e-9), self._tope - self._total)
        if puntos <= 0:
            return SIN_COBRO
        self._resto = max(0.0, self._resto - puntos)
        self._total += puntos
        aviso = None
        if self._total >= self._tope:
            aviso, self._avisado = AVISO_TOPE, True
        elif not self._avisado:
            aviso, self._avisado = AVISO_INICIO, True
        return Cobro(puntos, aviso)

    def horas_sin_participar(self, ahora):
        return 0.0 if self._ultima is None else max(0.0, _hora(ahora) - self._ultima)

    def total(self):
        return self._total

    def tope(self):
        return self._tope

    def en_tope(self):
        return self._total >= self._tope

    # -- Serialización (JSON) --

    def a_dict(self):
        return {"version": _VERSION, "ultima": self._ultima, "cobrado_hasta": self._cobrado_hasta, "resto": self._resto,
                "total": self._total, "avisado": self._avisado}

    # ValueError si los datos no son válidos. Gracia, ritmo y tope NO se guardan: son balance del código, no de la partida.
    @classmethod
    def desde_dict(cls, datos, **opciones):
        if not isinstance(datos, dict) or datos.get("version") != _VERSION:
            raise ValueError("Costo de aislamiento guardado con formato desconocido.")
        costo = cls(**opciones)
        for campo in ("ultima", "cobrado_hasta"):
            valor = datos.get(campo)
            setattr(costo, f"_{campo}", None if valor is None else _hora(valor, campo))
        costo._resto = max(0.0, _hora(datos.get("resto", 0.0), "resto"))
        total = datos.get("total", 0)
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError(f"total inválido: {total!r}.")
        costo._total = min(total, costo._tope)
        costo._avisado = bool(datos.get("avisado", False))
        return costo

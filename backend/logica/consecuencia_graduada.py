# Consecuencia GRADUADA de los minijuegos de verificar (modelo puro, sin ursina). Antes un minijuego se reducía a «bien / mal»
# (backend/logica/minijuegos.cerrar_lote): verificar al 61 % o al 100 % daba lo mismo. Ahora lo bien que se verificó se nota:
#
#   - PROPINA: con «bien», hasta PROPINA_MAX reales más según la calidad (los vecinos agradecen una verificación clara).
#   - CONFIANZA: hasta CONFIANZA_MAX puntos extra en el grupo de la misión (la confianza de GameState, no el indicador).
#   - DUDAS: un aprobado JUSTO (menos de MARGEN_JUSTO sobre el umbral) programa un efecto retardado pequeño: «Ayer
#     verificaste a medias...»: la desinformación sube un poco y el grupo duda. Verificar a medias no es verificar.
#   - Con «mal» no se añade nada: el veredicto fallado ya cobra lo suyo (confianza_misiones) y no se castiga dos veces.
#
# El pago fijo de la misión, el veredicto y los efectos retardados de siempre NO cambian: esto se SUMA después.
#
#   calcular(minijuego, mision, ahora)  -> Graduacion(calidad, propina, confianza, retardado, texto)   (pura)
#   FlujoConConsecuenciaGraduada        envoltorio del flujo (mismo patrón que dilemas.FlujoConDilemas): al completar una
#                                       misión con resultado["minijuego"] (lo pone frontend/escenas/escena_minijuego.py)
#                                       aplica la propina, la confianza y programa las dudas. `ultima_graduacion` para la vista.
#   envolver(flujo)                     lo que llama main.crear_flujo
#
# Los cambios solo existen fuera de línea (en línea no hay minijuegos ni este flujo). El guardado no necesita clave propia: lo
# aplicado ya vive en la billetera, el GameState y la cola de efectos, que se guardan como siempre.
#
# BANDERA. CONSECUENCIA_GRADUADA = False (o ALCALDE_CONSECUENCIA_GRADUADA=0): main no envuelve el flujo y todo es como antes.

import math
import os
import sys
from collections import namedtuple

from backend.logica import efectos_retardados

CONSECUENCIA_GRADUADA = True

PROPINA_MAX = 6                 # R$ con una verificación perfecta (el pago fijo de una misión es de R$ 10 a 30)
CONFIANZA_MAX = 2.0             # puntos extra de confianza del grupo con una verificación perfecta
MARGEN_JUSTO = 0.15             # por encima del umbral y por debajo de umbral + esto: «aprobado justo»
HORAS_DUDAS = 24.0
DUDAS_DELTAS = {"desinformacion": 2}
DUDAS_CONFIANZA = -1.0          # sobre el grupo de la misión
PERFECTA = 0.95                 # fracción desde la que la verificación se cuenta como impecable

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")

Graduacion = namedtuple("Graduacion", "calidad propina confianza retardado texto")    # retardado: (en_horas_abs, Efecto) | None


def activo():
    """¿Hay consecuencia graduada? ALCALDE_CONSECUENCIA_GRADUADA=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_CONSECUENCIA_GRADUADA", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(CONSECUENCIA_GRADUADA)


def _numero(valor, por_defecto=0.0):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return por_defecto
    return float(valor)


# Calidad 0..1 de un aprobado: 0 justo en el umbral, 1 con todo bien. None si no aprobó (o el dict no sirve).
def calidad(minijuego):
    if not isinstance(minijuego, dict) or not minijuego.get("bien") or not minijuego.get("completado", True):
        return None
    total = _numero(minijuego.get("total"))
    if total <= 0:
        return None
    fraccion = max(0.0, min(1.0, _numero(minijuego.get("aciertos")) / total))
    umbral = max(0.0, min(0.99, _numero(minijuego.get("umbral"), 0.6)))
    return max(0.0, min(1.0, (fraccion - umbral) / (1.0 - umbral)))


def calcular(minijuego, mision, ahora=0.0):
    """Lo que añade un minijuego APROBADO según lo bien que se jugó; None si no aprobó. No toca nada (pura)."""
    q = calidad(minijuego)
    if q is None:
        return None
    grupo = getattr(mision, "grupo", None)
    propina = int(round(PROPINA_MAX * q))
    confianza = {grupo: round(CONFIANZA_MAX * q, 2)} if grupo in efectos_retardados.GRUPOS and q > 0 else {}
    retardado = None
    umbral = _numero(minijuego.get("umbral"), 0.6)
    fraccion = _numero(minijuego.get("aciertos")) / _numero(minijuego.get("total"), 1.0)
    titulo = getattr(mision, "titulo", "el rumor")
    if fraccion < umbral + MARGEN_JUSTO:
        mensaje = (f"{efectos_retardados._cuando(HORAS_DUDAS)} verificaste a medias «{titulo}»: algunos vecinos no "
                   f"quedaron convencidos y el rumor siguió dando vueltas.")
        dudas = {grupo: DUDAS_CONFIANZA} if grupo in efectos_retardados.GRUPOS else {}
        retardado = (ahora + HORAS_DUDAS, efectos_retardados.crear_efecto(
            "dudas", mensaje, DUDAS_DELTAS, dudas, f"mision:{getattr(mision, 'id', '')}"))
        texto = "Pasaste raspando: lo que no revisaste puede volver mañana."
    elif fraccion >= PERFECTA:
        texto = "Verificación impecable: los vecinos te dan una propina y confían más en ti."
    else:
        texto = "Buena verificación: los vecinos lo notan."
    return Graduacion(q, propina, confianza, retardado, texto)


# -- Envoltorio del flujo ---------------------------------------------------------------------------------------------

_PROPIOS = ("_flujo", "ultima_graduacion")


class FlujoConConsecuenciaGraduada:

    def __init__(self, flujo):
        self._flujo = flujo
        # {"mision", "propina", "confianza", "dudas", "texto"} de la última misión con minijuego aprobado; None si no hubo.
        self.ultima_graduacion = None

    def completar_mision(self, resultado):
        jugador = self._flujo.jugador_activo()
        leer_mision = getattr(self._flujo, "mision_actual", None)
        mision = leer_mision() if leer_mision is not None else None      # antes de delegar: completar pasa el turno
        siguiente = self._flujo.completar_mision(resultado)
        self.ultima_graduacion = None
        minijuego = resultado.get("minijuego") if isinstance(resultado, dict) else None
        if mision is not None and minijuego is not None:
            try:        # la parte graduada nunca puede impedir cerrar una misión
                self._aplicar(jugador, mision, minijuego)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                print(f"[consecuencia_graduada] no aplicada: {error}", file=sys.stderr)
        return siguiente

    def _aplicar(self, jugador, mision, minijuego):
        reloj = getattr(self._flujo, "reloj", None)
        ahora = reloj.tiempo_absoluto() if reloj is not None else 0.0
        g = calcular(minijuego, mision, ahora)
        if g is None:
            return
        propina = 0
        if g.propina > 0 and jugador is not None:
            from backend.logica.perfil_economia import perfil_de
            perfil = perfil_de(jugador)
            if perfil.inventario.ingresar(g.propina).ok:
                perfil.ganado += g.propina
                perfil.registrar(f"Propina: {getattr(mision, 'titulo', 'misión')}", g.propina)
                propina = g.propina
        game_state = getattr(self._flujo, "game_state", None)
        if g.confianza and game_state is not None:
            from backend.logica.game_state import PESO_INVESTIGACION
            game_state.aplicar_evento(
                "verificacion_graduada", efectos={gr: {"investigacion": d / PESO_INVESTIGACION} for gr, d in g.confianza.items()},
                origen=f"mision:{getattr(mision, 'id', '')}", datos={"calidad": round(g.calidad, 2)})
        cola = getattr(self._flujo, "cola_efectos", None)
        if g.retardado is not None and cola is not None:
            cola.programar(*g.retardado)
        self.ultima_graduacion = {"mision": getattr(mision, "id", None), "propina": propina, "confianza": dict(g.confianza),
                                  "dudas": g.retardado is not None, "texto": g.texto}

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)


# Lo que llama main.crear_flujo: envuelve `flujo` si la bandera está encendida. Sin reloj funciona igual (sin dudas).
def envolver(flujo):
    if not activo():
        return flujo
    return FlujoConConsecuenciaGraduada(flujo)

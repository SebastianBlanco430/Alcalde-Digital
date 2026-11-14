# Minijuegos de las misiones de «verificar» (modelo puro, sin ursina). Antes las 47 misiones usaban la misma pantalla (lote de
# noticias de frontend/escenas/escena_juego.py); ahora cada misión puede jugarse con un minijuego distinto (rastrear la fuente,
# comparar versiones, ordenar la cadena, chat del barrio, señales de edición, contrarreloj).
#
# ADITIVO. Nada del flujo cambia: el minijuego devuelve «bien / mal» y este módulo lo TRADUCE a lo que el sistema de hoy ya
# entiende: las decisiones «compartir» / «reportar» sobre las cartas del lote (EstadoPartida.decidir + LoteMision.registrar).
# Así el resultado de la misión (lote.resultado(): decisiones, deltas, propagaciones, veredicto) es el MISMO dict que entrega la
# pantalla de siempre, y de ahí en adelante todo funciona igual (pago, confianza por grupo, efectos retardados, GameState,
# guardado). El protocolo en línea no cambia: en línea no se usan minijuegos (ver `frontend/registro_minijuegos.py`).
#
# BANDERA. ALCALDE_MINIJUEGOS=0 (o MINIJUEGOS = False) apaga todo: el juego queda idéntico a hoy. Se lee en cada llamada.
#
# TRADUCCIÓN (decisión de diseño, ver nota 53 de la bóveda):
#   - «Bien» = el jugador resolvió el minijuego con la fracción de aciertos >= UMBRAL_BIEN.
#   - La CARTA DE MISIÓN (el rumor) se decide con la decisión CORRECTA si salió bien (compartir si el rumor es verdadero, reportar
#     si es falso) y con la contraria si salió mal: así el veredicto (pasada / fallada) y la confianza del grupo siguen la regla de
#     siempre (confianza_misiones.veredicto).
#   - Las demás cartas del lote (salen del mazo) se resuelven igual: correcta si salió bien, contraria si salió mal, según la
#     veracidad de cada noticia. El jugador ya mostró cómo verifica; no se le pide repetirlo con cartas que no ve.

import os
import random
from dataclasses import dataclass

from backend.logica import confianza_misiones

MINIJUEGOS = True               # bandera por defecto; ALCALDE_MINIJUEGOS=0 la apaga

# Id del minijuego de siempre (el lote de noticias de escena_juego). Es el RESPALDO de todo.
ACTUAL = "juego"
# Ids de los minijuegos nuevos (los registra frontend/minijuegos/__init__.py).
RASTREAR = "rastrear"
COMPARAR = "comparar"
CRONOLOGIA = "cronologia"
CHAT = "chat"
SENALES = "senales"
CONTRARRELOJ = "contrarreloj"
IDS = (RASTREAR, COMPARAR, CRONOLOGIA, CHAT, SENALES, CONTRARRELOJ)

UMBRAL_BIEN = 0.6               # fracción de aciertos desde la que se cuenta como «verificó bien»
_SEGURIDAD_BUCLE = 12           # tope de vueltas al cerrar un lote (nunca debería llegar)


def activo():
    """¿Hay minijuegos? ALCALDE_MINIJUEGOS=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_MINIJUEGOS", "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    return bool(MINIJUEGOS)


@dataclass(frozen=True)
class ResultadoMinijuego:
    """Resultado común de TODOS los minijuegos (lo que devuelve `empezar`/`resultado()` de cada partida pura)."""
    minijuego: str
    aciertos: float          # puntos logrados (puede ser fraccionario: aciertos parciales)
    total: float             # puntos posibles (> 0)
    completado: bool = True  # False si se abandonó o se acabó el tiempo sin jugar nada
    detalle: str = ""        # frase corta con lo que pasó, en palabras (sin cifras de indicadores)
    umbral: float = UMBRAL_BIEN   # fracción mínima para contar como «bien» (un minijuego fácil de ganar por inercia lo sube)

    @property
    def fraccion(self):
        return 0.0 if self.total <= 0 else max(0.0, min(1.0, self.aciertos / self.total))

    @property
    def bien(self):
        return self.completado and self.fraccion >= self.umbral - 1e-9

    def a_dict(self):
        return {"minijuego": self.minijuego, "aciertos": self.aciertos, "total": self.total,
                "completado": self.completado, "bien": self.bien, "detalle": self.detalle, "umbral": self.umbral}


def contraria(decision):
    return "reportar" if decision == "compartir" else "compartir"


def decision_para_mision(mision, bien):
    """Decisión sobre la carta de misión que corresponde a `bien`; None si la misión no es de verificar con veredicto."""
    correcta = confianza_misiones.decision_correcta(mision)
    if correcta is None:
        return None
    return correcta if bien else contraria(correcta)


def decision_para_noticia(noticia, bien):
    """Decisión sobre una carta del mazo (NodoNoticia: .veracidad) según `bien`."""
    correcta = "compartir" if getattr(noticia, "veracidad", True) else "reportar"
    return correcta if bien else contraria(correcta)


def cerrar_lote(estado, lote, mision, bien):
    """Resuelve TODO el lote con las mismas llamadas que hace la pantalla de siempre y devuelve `lote.resultado()`.

    `estado`: EstadoPartida; `lote`: LoteMision de la misión. Cada vuelta: toma la carta en mesa, decide, aplica
    (estado.decidir) y registra (lote.registrar). Sin cartas en mesa o con el lote ya terminado, no hace nada más.
    """
    for _ in range(_SEGURIDAD_BUCLE):
        if lote.terminada() or not estado.hay_noticia():
            break
        if lote.es_carta_de_mision():
            decision = decision_para_mision(mision, bien) or "reportar"
        else:
            decision = decision_para_noticia(estado.noticia_actual(), bien)
        lote.intentos_decidir = getattr(lote, "intentos_decidir", 0) + 1   # ANTES de decidir: decidir muta y luego puede fallar
        deltas = estado.decidir(decision)
        lote.registrar(decision, deltas, estado.hay_noticia())
    return lote.resultado()


def elegir_caso(casos, mision, tema, usados=None, azar=None):
    """Elige un caso de `casos` (lista de dicts) para la misión, evitando repetir los de `usados` (set de ids, se actualiza).

    Prioridad: caso hecho a propósito para esta misión (`misiones`; se reutiliza aunque ya saliera, porque habla de SU rumor) >
    caso del mismo `tema` entre los no usados > cualquiera de los no usados. Si ya se usaron todos, se reinicia el conjunto.
    Determinista si se pasa `azar` (random.Random).
    """
    if not casos:
        return None
    usados = usados if usados is not None else set()
    azar = azar if azar is not None else random
    propios = [c for c in casos if getattr(mision, "id", None) in c.get("misiones", ())]
    if propios:
        nuevos = [c for c in propios if c["id"] not in usados]
        elegido = azar.choice(nuevos or propios)
        usados.add(elegido["id"])
        return elegido
    libres = [c for c in casos if c["id"] not in usados]
    if not libres:
        usados.clear()
        libres = list(casos)
    del_tema = [c for c in libres if tema in c.get("temas", ())]
    elegido = azar.choice(del_tema or libres)
    usados.add(elegido["id"])
    return elegido


def resolver(valor, es_verdadera):
    """Un texto de los casos puede ser un str o {"v": ..., "f": ...} (según la veracidad del rumor)."""
    if isinstance(valor, dict) and ("v" in valor or "f" in valor):
        return valor["v"] if es_verdadera else valor["f"]
    return valor


def preparar_caso(caso, mision):
    """Copia del `caso` lista para jugar: textos {"v","f"} resueltos según la veracidad del rumor y {rumor}/{lugar}/{pista}
    sustituidos por los de la misión. No modifica el caso original (son datos compartidos)."""
    es_verdadera = bool(getattr(mision, "es_verdadera", False))
    campos = {"rumor": getattr(mision, "rumor", ""), "lugar": getattr(mision, "destino", ""),
              "pista": getattr(mision, "pista", "")}

    def aplicar(valor):
        if isinstance(valor, dict):
            if valor and set(valor) <= {"v", "f"}:
                return aplicar(resolver(valor, es_verdadera))
            return {k: aplicar(v) for k, v in valor.items()}
        if isinstance(valor, (list, tuple)):
            return [aplicar(v) for v in valor]
        return rellenar(valor, **campos)

    preparado = aplicar(caso)
    preparado["es_verdadera"] = es_verdadera
    return preparado


def rellenar(texto, **campos):
    """Sustituye {rumor}, {lugar}, {pista}... en un texto de caso; las claves que no existen quedan tal cual."""
    if not isinstance(texto, str):
        return texto
    for clave, valor in campos.items():
        texto = texto.replace("{" + clave + "}", str(valor))
    return texto

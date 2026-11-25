# Guion de la Rádio Comunitária (modelo puro, sin ursina). Hilo conductor: docs/HILO_CONDUCTOR.md.
#
# Elige QUÉ dice la radio; cuándo y cómo se ve lo decide el frontend (frontend/radio_calculos.py y radio_emision.py).
# Los textos viven en backend/datos/radio_textos.json (editable, sin código). Dos emisiones por día:
#   - MAÑANA (una línea): «manana»[día][estado de la ciudad].
#   - NOCHE (días 1-6; tres líneas, dos en modo corto): qué hizo el jugador ese día («hizo»[resultado]), qué pasó en la
#     red sin él («red»[día][quedaron | limpio]) y una consecuencia visible («ciudad»[día][estado]). Sin números.
#   - PUENTE (día 7, antes del final): «puente»[estado].
# Las misiones sin terminar al cierre cuentan como «sin verificar» (la radio lo dice; el efecto es el de no hacer nada,
# que ya aplica el reparto por días al caducarlas).
#
# ESTADO DE LA CIUDAD: promedio de convivencia, confianza y 100 - desinformación (como evaluar_final_indicadores):
# >= UMBRAL_BIEN «bien», < UMBRAL_MAL «mal», en medio «tenso».
# RESULTADO DEL DÍA (del diario de FlujoConTiempo): «acierto» (solo pasadas), «error» (solo falladas), «mixto» (de las
# dos) o «nada» (ninguna misión cerrada con veredicto).
#
# BANDERA. RADIO = True (o ALCALDE_HILO_RADIO=0, o ALCALDE_HILO=0 para todo el hilo) la apaga: sin emisiones y la noche
# se salta sin pausa.
#
#   guion = GuionRadio()                                  # carga radio_textos.json
#   guion.manana(dia, estado)                             -> texto
#   guion.noche(dia, resultado, quedaron, estado, corto)  -> [textos]
#   guion.puente(estado)                                  -> texto
#   estado_ciudad(indicadores) / resultado_dia(diario) / tema_dia(diario, temas) / segundos_lectura(texto, lectura)

import json
import os
from collections import Counter
from pathlib import Path

RADIO = True
HILO = True
RUTA_TEXTOS = Path(__file__).resolve().parent.parent / "datos" / "radio_textos.json"

UMBRAL_BIEN = 60.0
UMBRAL_MAL = 40.0
ESTADOS = ("bien", "tenso", "mal")
RESULTADOS = ("acierto", "mixto", "error", "nada")
LECTURA = {"base": 1.5, "por_caracter": 0.06, "minimo": 2.5}

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def _bandera(variable, por_defecto):
    valor = os.environ.get(variable, "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(por_defecto)


def hilo_activo():
    """¿Hilo conductor? ALCALDE_HILO=0 apaga a la vez radio, sello y reacciones de los NPC."""
    return _bandera("ALCALDE_HILO", HILO)


def activo():
    """¿Hay radio? ALCALDE_HILO_RADIO=1/0 manda sobre RADIO; ALCALDE_HILO=0 la apaga también."""
    return hilo_activo() and _bandera("ALCALDE_HILO_RADIO", RADIO)


def cargar_textos(ruta=None):
    with open(ruta or RUTA_TEXTOS, encoding="utf-8") as archivo:
        return json.load(archivo)


def estado_ciudad(indicadores):
    """«bien» | «tenso» | «mal» de los tres indicadores (dict); «tenso» si faltan."""
    try:
        indice = (float(indicadores["convivencia"]) + float(indicadores["confianza"])
                  + 100.0 - float(indicadores["desinformacion"])) / 3.0
    except (KeyError, TypeError, ValueError):
        return "tenso"
    if indice >= UMBRAL_BIEN:
        return "bien"
    return "mal" if indice < UMBRAL_MAL else "tenso"


def resultado_dia(diario):
    """Resultado del día a partir de [{"id", "veredicto"}]."""
    veredictos = {e.get("veredicto") for e in diario or ()}
    pasadas, falladas = "pasada" in veredictos, "fallada" in veredictos
    if pasadas and falladas:
        return "mixto"
    if pasadas:
        return "acierto"
    return "error" if falladas else "nada"


def tema_dia(diario, temas):
    """El tema más repetido entre las misiones cerradas del día (empate: el de la primera), o None."""
    lista = [temas[e["id"]] for e in diario or () if e.get("id") in temas]
    if not lista:
        return None
    cuenta = Counter(lista)
    mayor = max(cuenta.values())
    return next(t for t in lista if cuenta[t] == mayor)


def segundos_lectura(texto, lectura=None):
    """Regla de lectura de los globos de cinemática: base + por_caracter · caracteres, con un mínimo."""
    regla = dict(LECTURA, **(lectura or {}))
    return max(float(regla["minimo"]), float(regla["base"]) + float(regla["por_caracter"]) * len(texto or ""))


class GuionRadio:

    def __init__(self, textos=None):
        self.textos = textos if textos is not None else cargar_textos()
        self._ultimas = {}          # clave -> índice de la última variante dicha (no se repite seguida)

    @property
    def emisora(self):
        return self.textos.get("emisora", "Rádio Comunitária")

    @property
    def locutora(self):
        return self.textos.get("locutora", "")

    @property
    def temas(self):
        return self.textos.get("temas", {})

    @property
    def lectura(self):
        return self.textos.get("lectura", LECTURA)

    # Una variante de `opciones` sin repetir la última dicha con la misma clave (rota en orden: determinista).
    def _variante(self, clave, opciones):
        opciones = [o for o in (opciones or []) if isinstance(o, str) and o.strip()]
        if not opciones:
            return None
        indice = (self._ultimas.get(clave, -1) + 1) % len(opciones)
        self._ultimas[clave] = indice
        return opciones[indice]

    @staticmethod
    def _estado(estado):
        return estado if estado in ESTADOS else "tenso"

    def manana(self, dia, estado):
        por_dia = self.textos.get("manana", {}).get(str(dia), {})
        estado = self._estado(estado)
        return self._variante(("manana", dia, estado), por_dia.get(estado) or por_dia.get("tenso"))

    # Recuento de la noche. `quedaron`: hubo misiones del día sin verificar al cierre. `corto`: dos líneas (feria).
    def noche(self, dia, resultado, quedaron, estado, corto=False):
        noche = self.textos.get("noche", {})
        resultado = resultado if resultado in RESULTADOS else "nada"
        estado = self._estado(estado)
        lineas = [self._variante(("hizo", resultado), noche.get("hizo", {}).get(resultado))]
        if not corto:
            red = noche.get("red", {}).get(str(dia), {})
            lineas.append(self._variante(("red", dia), red.get("quedaron" if quedaron else "limpio")))
        ciudad = noche.get("ciudad", {}).get(str(dia), {})
        lineas.append(self._variante(("ciudad", dia, estado), ciudad.get(estado)))
        return [linea for linea in lineas if linea]

    def puente(self, estado):
        puente = self.textos.get("puente", {})
        return self._variante(("puente",), puente.get(self._estado(estado)) or puente.get("tenso"))

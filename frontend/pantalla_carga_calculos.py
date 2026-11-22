# Pantalla de carga del arranque (M7.3): cálculo puro del progreso (NO importa ursina ni panda3d).
# La vista es frontend/pantalla_carga.py; los constructores (main.registrar_escenas, Ciudad3D, Peatones, extensiones)
# solo llaman a pantalla_carga.avance(etapa, fraccion).
#
# PROGRESO: cada etapa tiene un peso (segundos que tardó, medidos con la caché caliente). El progreso global es
#   (pesos de las etapas anteriores + peso de la actual * fracción) / total, nunca retrocede y nunca pasa de 1.
#   Una etapa que no se llama (p. ej. sin economía) simplemente se salta: su peso se suma al llegar a la siguiente.
# RECALIBRADO: al terminar se guardan los segundos reales de cada etapa en <caché>/pantalla_carga.json
#   ($ALCALDE_CACHE_DIR o ~/.alcalde_digital/cache, como backend/datos/cache_mundo.py), mezclados con los anteriores.
#   La siguiente carga usa esos pesos. Un archivo ausente, ilegible o raro se ignora: se usan los pesos fijos.
# BANDERA: ALCALDE_PANTALLA_CARGA=0 (o PANTALLA_CARGA = False) quita la pantalla: el arranque de antes.

import json
import os
import time
from pathlib import Path

PANTALLA_CARGA = True
INTERVALO_DIBUJO = 0.4           # s: como mucho un cuadro cada esto (2,5 por segundo: la carga no se alarga)
NOMBRE_ARCHIVO = "pantalla_carga.json"
MEZCLA = 0.5                     # peso de la última medida frente a lo guardado antes
TIEMPO_MAXIMO_ETAPA = 600.0      # s: una medida mayor (o negativa, o no numérica) se descarta

# (etapa, peso en s medido el 2026-11-21 con caché caliente (total ~27,6 s), texto que se muestra). En orden de construcción.
ETAPAS = (
    ("mundo", 0.05, "Trazando el mapa de Ciudad Nova…"),
    ("menus", 0.8, "Preparando los menús…"),
    ("ciudad_base", 0.12, "Construyendo la ciudad…"),
    ("ciudad_suelo", 1.33, "Nivelando el terreno…"),
    ("ciudad_calles", 0.47, "Trazando las calles…"),
    ("ciudad_marcas", 0.01, "Pintando las calles…"),
    ("ciudad_plazas", 0.06, "Construyendo las plazas…"),
    ("ciudad_edificios", 2.6, "Levantando los edificios…"),
    ("ciudad_obstaculos", 6.4, "Levantando las casas del morro…"),
    ("ciudad_decorado", 0.6, "Poniendo farolas y árboles…"),
    ("ciudad_escaleras", 0.08, "Tallando las escaleras…"),
    ("ciudad_muros", 0.01, "Levantando los muros de contención…"),
    ("ciudad_combinar", 8.0, "Juntando las piezas de la ciudad…"),
    ("ciudad_sombras", 0.17, "Encendiendo el sol…"),
    ("jugador", 0.01, "Preparando la cámara…"),
    ("peatones", 2.8, "Preparando a los vecinos…"),
    ("hud", 0.22, "Preparando el teléfono y el mapa…"),
    ("vehiculos", 0.28, "Aparcando bicis y motos…"),
    ("economia", 1.65, "Abriendo los comercios…"),
    ("interior", 0.32, "Amueblando los interiores…"),
    ("extensiones", 1.8, "Cargando misiones y extras…"),
    ("final", 0.07, "Últimos retoques…"),
)
ORDEN = tuple(nombre for nombre, _, _ in ETAPAS)
PESOS = {nombre: peso for nombre, peso, _ in ETAPAS}
TEXTOS = {nombre: texto for nombre, _, texto in ETAPAS}
TEXTO_INICIAL = "Abriendo Alcalde Digital…"
# Segundos del combine() de cada grupo de Ciudad3D (medido): la barra avanza dentro de "ciudad_combinar" según esto.
PESOS_COMBINAR = {"suelo": 0.01, "calles": 0.05, "plazas": 0.4, "edificios": 0.34, "muros": 0.12, "vegetacion": 3.0,
                  "mobiliario": 2.7, "escaleras": 0.27, "ventanas": 0.03, "luces": 1.0, "calles_arena": 0.01}


def pantalla_carga_activa(valor=None):
    valor = (os.environ.get("ALCALDE_PANTALLA_CARGA", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PANTALLA_CARGA)


def texto_de(etapa):
    return TEXTOS.get(etapa, "Cargando…")


def _limitar(fraccion):
    if fraccion is None:
        return 0.0
    try:
        fraccion = float(fraccion)
    except (TypeError, ValueError):
        return 0.0
    if fraccion != fraccion:        # NaN
        return 0.0
    return min(1.0, max(0.0, fraccion))


def fraccion_acumulada(pesos, hechos):
    """Fracción 0..1 hecha tras los primeros `hechos` pasos de una lista con `pesos` (todo 0 -> por número de pasos)."""
    pesos = [max(0.0, float(p)) for p in pesos]
    if not pesos:
        return 1.0
    hechos = min(len(pesos), max(0, int(hechos)))
    total = sum(pesos)
    if total <= 0:
        return hechos / len(pesos)
    return min(1.0, sum(pesos[:hechos]) / total)


class ProgresoCarga:
    """Progreso 0->1 por etapas con pesos; mide de paso cuánto dura cada etapa (para recalibrar)."""

    def __init__(self, pesos=None, reloj=time.perf_counter, orden=ORDEN):
        base = dict(PESOS)
        base.update(pesos or {})
        self._orden = tuple(orden)
        self._pesos = [max(0.0, float(base.get(nombre, 0.0))) for nombre in self._orden]
        self._total = sum(self._pesos) or 1.0
        self._antes = []                # suma de los pesos de las etapas anteriores a cada una
        acumulado = 0.0
        for peso in self._pesos:
            self._antes.append(acumulado)
            acumulado += peso
        self._reloj = reloj
        self.progreso = 0.0
        self.etapa = None
        self.texto = TEXTO_INICIAL
        self._tiempos = {}
        self._inicio_etapa = None

    def avance(self, etapa, fraccion=None):
        """Marca `etapa` (con `fraccion` 0..1 hecha) y devuelve el progreso global, que nunca retrocede."""
        if etapa != self.etapa:
            self._cerrar_etapa()
            self.etapa = etapa
            self._inicio_etapa = self._reloj()
            self.texto = texto_de(etapa)
        if etapa in self._orden:
            i = self._orden.index(etapa)
            valor = (self._antes[i] + self._pesos[i] * _limitar(fraccion)) / self._total
            self.progreso = min(1.0, max(self.progreso, valor))
        return self.progreso

    def terminar(self):
        self._cerrar_etapa()
        self.etapa = None
        self.progreso = 1.0
        return self.progreso

    def _cerrar_etapa(self):
        if self.etapa is not None and self._inicio_etapa is not None:
            duracion = max(0.0, self._reloj() - self._inicio_etapa)
            self._tiempos[self.etapa] = self._tiempos.get(self.etapa, 0.0) + duracion
        self._inicio_etapa = None

    def tiempos(self):
        """Segundos medidos por etapa (las cerradas hasta ahora)."""
        return dict(self._tiempos)


class Limitador:
    """¿Toca dibujar un cuadro? Como mucho uno cada `intervalo` s (el primero, siempre)."""

    def __init__(self, intervalo=INTERVALO_DIBUJO):
        self.intervalo = intervalo
        self._ultimo = None

    def toca(self, ahora, forzar=False):
        if forzar or self._ultimo is None or ahora - self._ultimo >= self.intervalo:
            self._ultimo = ahora
            return True
        return False


def _tiempo_valido(valor):
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor == valor
            and 0.0 <= valor <= TIEMPO_MAXIMO_ETAPA)


def depurar_tiempos(datos):
    """Solo las etapas conocidas con un tiempo razonable (lo demás se descarta)."""
    if not isinstance(datos, dict):
        return {}
    return {etapa: float(valor) for etapa, valor in datos.items() if etapa in PESOS and _tiempo_valido(valor)}


def pesos_recalibrados(guardados, base=None):
    """Pesos fijos con los medidos encima (los que falten o sean raros: el fijo). Si todo es 0, los fijos."""
    pesos = dict(PESOS if base is None else base)
    pesos.update(depurar_tiempos(guardados))
    if sum(pesos.values()) <= 0:
        return dict(PESOS if base is None else base)
    return pesos


def mezclar(anteriores, nuevos, mezcla=MEZCLA):
    """Media móvil por etapa: una carga rara (caché fría) no manda sola."""
    anteriores, nuevos = depurar_tiempos(anteriores), depurar_tiempos(nuevos)
    resultado = dict(anteriores)
    for etapa, valor in nuevos.items():
        previo = anteriores.get(etapa)
        resultado[etapa] = valor if previo is None else previo * (1 - mezcla) + valor * mezcla
    return {etapa: round(valor, 3) for etapa, valor in resultado.items()}


def ruta_tiempos(directorio=None):
    if directorio is None:
        elegido = os.environ.get("ALCALDE_CACHE_DIR")      # misma carpeta que backend/datos/cache_mundo.directorio()
        directorio = Path(elegido) if elegido else Path.home() / ".alcalde_digital" / "cache"
    return Path(directorio) / NOMBRE_ARCHIVO


def leer_tiempos(ruta):
    try:
        return depurar_tiempos(json.loads(Path(ruta).read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):      # RecursionError: JSON anidado sin fin
        return {}


def guardar_tiempos(ruta, tiempos):
    """Escribe los tiempos mezclados con los que ya había. Devuelve lo guardado ({} si no se pudo)."""
    ruta = Path(ruta)
    datos = mezclar(leer_tiempos(ruta), tiempos)
    if not datos:
        return {}
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporal, ruta)
    except OSError:
        return {}
    return datos

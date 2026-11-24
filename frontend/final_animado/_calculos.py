# Cálculos del final animado (PURO: no importa ursina; se prueba con pytest). Lo usan director.py (Ursina) y, para leer
# los planos, la escenografía de decorado-actores. Contrato: frontend/final_animado/contrato.md.
#
#   Guion         cargar_guion(datos=None) · planos_de(final, roles) -> [Plano] · estado_ciudad(final) -> dict
#   Línea         LineaTiempo(planos, escala): qué plano y qué t (0..1) tocan a un tiempo T, alfa del negro (fundido de
#                 entrada, cortes de 0,35 s + 0,35 s, fundido de salida) y subtítulo visible (texto, alfa)
#   Subtítulos    reparto_subtitulos (tiempo según el largo, con un mínimo legible) · px_subtitulo(alto_ventana) ·
#                 partir_lineas(texto, medir, ancho) a 2 líneas como mucho
#   Saltar        MantenerParaSaltar: acumulador de ~0,9 s que se vacía al soltar; una pulsación corta solo enseña el aviso
#   Curvas        lineal, suave (smoothstep), muy_suave (smootherstep), salida (ease-out)

import json
import math
from dataclasses import dataclass
from pathlib import Path

FINALES = ("bueno", "neutro", "malo")
ROLES = ("ciudadano", "periodista", "influencer", "candidato")
ROL_POR_DEFECTO = "ciudadano"
RUTA_DATOS = Path(__file__).resolve().parents[2] / "backend" / "datos" / "finales_historia.json"

ENTRADA_INICIAL = 0.8           # s: el primer plano aparece desde el negro de la carga
FUNDIDO_CORTE = 0.35            # s de ida a negro y otros tantos de vuelta en cada corte
SALIDA_FINAL = 1.0              # s: fundido final a negro antes de limpiar
SUBTITULO_MINIMO = 2.4          # s: lo menos que se deja una frase en pantalla (si el plano da)
SUBTITULO_FUNDIDO = 0.25        # s de aparición y de salida de cada frase
SUBTITULO_BASE = 12             # caracteres «gratis» de cada frase en el reparto (una frase corta también se lee)
SALTAR_SEGUNDOS = 0.9           # mantener para saltar
SALTAR_VACIADO = 3.0            # el acumulador se vacía 3 veces más rápido de lo que se llena
AVISO_SEGUNDOS = 2.5            # tras una pulsación corta el aviso se queda a la vista
AVISO_INICIAL = 4.0             # s: el aviso se ve al empezar (después del fundido de entrada), luego solo al pulsar
PX_SUBTITULO_FRACCION = 0.026   # del alto de la ventana: 19 px a 720p, 28 px a 1080p
PX_SUBTITULO_MIN, PX_SUBTITULO_MAX = 14, 40


# -- Curvas --------------------------------------------------------------------------------------------------------------

def _recorte(t):
    return 0.0 if t <= 0.0 else 1.0 if t >= 1.0 else float(t)


def lineal(t):
    return _recorte(t)


def suave(t):
    t = _recorte(t)
    return t * t * (3.0 - 2.0 * t)


def muy_suave(t):
    t = _recorte(t)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def salida(t):
    t = _recorte(t)
    return 1.0 - (1.0 - t) * (1.0 - t)


CURVAS = {"lineal": lineal, "suave": suave, "muy_suave": muy_suave, "salida": salida}


# -- Guion ----------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Plano:
    id: str
    final: str
    ancla: str
    segundos: float
    subtitulos: tuple
    rol: str | None
    indice: int


def cargar_guion(datos=None):
    """La sección «animacion» de finales_historia.json (o de `datos`, ya cargado: el JSON entero o la sección)."""
    if datos is None:
        with open(RUTA_DATOS, encoding="utf-8") as f:
            datos = json.load(f)
    if isinstance(datos, dict) and "animacion" in datos:
        datos = datos["animacion"]
    if not isinstance(datos, dict) or not any(final in datos for final in FINALES):
        raise ValueError("el guion no trae la sección «animacion»")
    return datos


def roles_validos(roles, por_rol=None):
    """Roles presentes (en orden de turno, sin repetir) que tienen plano propio; sin ninguno, el del ciudadano."""
    conocidos = tuple(por_rol) if por_rol else ROLES
    salida_roles = []
    for rol in roles or ():
        if rol in conocidos and rol not in salida_roles:
            salida_roles.append(rol)
    return salida_roles or [ROL_POR_DEFECTO]


def planos_de(final, roles, guion=None):
    """Planos del final en orden. El hueco {"rol": true} se cambia por el plano de cada rol presente (solo: 8 s; varios:
    5 s cada uno, «segundos_rol»). Lanza KeyError si el final no existe."""
    g = cargar_guion() if guion is None else cargar_guion(guion)
    seccion = g[final]
    por_rol = seccion.get("por_rol", {})
    presentes = roles_validos(roles, por_rol)
    tiempos = g.get("segundos_rol", {})
    segundos_rol = float(tiempos.get("solo", 8.0) if len(presentes) == 1 else tiempos.get("varios", 5.0))
    planos = []
    for entrada in seccion["planos"]:
        if entrada.get("rol"):
            for rol in presentes:
                propio = por_rol[rol]
                planos.append(Plano(str(propio["id"]), final, str(propio["ancla"]),
                                    float(propio.get("segundos", segundos_rol)), tuple(propio.get("subtitulos", ())),
                                    rol, len(planos)))
            continue
        planos.append(Plano(str(entrada["id"]), final, str(entrada["ancla"]), float(entrada["segundos"]),
                            tuple(entrada.get("subtitulos", ())), None, len(planos)))
    return planos


def estado_ciudad(final, guion=None):
    """{"etapa": -3|0|3, "hora": float, "musica": str|None, "sonido": str|None} del final."""
    g = cargar_guion() if guion is None else cargar_guion(guion)
    seccion = g[final]
    return {"etapa": int(seccion.get("etapa", 0)), "hora": float(seccion.get("hora", 12.0)),
            "musica": seccion.get("musica"), "sonido": seccion.get("sonido")}


def texto_saltar(guion=None):
    try:
        g = cargar_guion() if guion is None else cargar_guion(guion)
        return str(g.get("saltar", "Mantén para saltar"))
    except Exception:
        return "Mantén para saltar"


def duracion_total(planos, escala=1.0):
    return sum(p.segundos for p in planos) * float(escala)


# -- Subtítulos -----------------------------------------------------------------------------------------------------------

def reparto_subtitulos(subtitulos, segundos, margen=FUNDIDO_CORTE, minimo=SUBTITULO_MINIMO):
    """[(inicio, fin)] en s dentro de un plano de `segundos`: entre el fin del fundido de entrada y el principio del de
    salida, cada frase según su largo, con al menos `minimo` s si el plano da (si no, a partes iguales)."""
    textos = [str(s) for s in subtitulos or ()]
    if not textos:
        return []
    margen = min(margen, segundos / 4.0)
    disponible = max(0.0, segundos - 2.0 * margen)
    n = len(textos)
    pesos = [len(t) + SUBTITULO_BASE for t in textos]
    if disponible < n * minimo:
        duraciones = [disponible / n] * n
    else:
        fijos = [False] * n
        duraciones = [0.0] * n
        for _ in range(n + 1):                    # los que no llegan al mínimo se fijan y el resto se reparte de nuevo
            libre = disponible - sum(minimo for f in fijos if f)
            peso_libre = sum(p for p, f in zip(pesos, fijos) if not f)
            cambio = False
            for i in range(n):
                if fijos[i]:
                    duraciones[i] = minimo
                    continue
                duraciones[i] = libre * pesos[i] / peso_libre
                if duraciones[i] < minimo:
                    fijos[i] = cambio = True
            if not cambio:
                break
        for i in range(n):
            if fijos[i]:
                duraciones[i] = minimo
    tramos, inicio = [], margen
    for d in duraciones:
        tramos.append((inicio, inicio + d))
        inicio += d
    return tramos


def px_subtitulo(alto_ventana):
    """Tamaño en px reales de la fuente del subtítulo para una ventana de `alto_ventana` px (>= 14 a 720p, >= 18 a 1080p)."""
    alto = max(1.0, float(alto_ventana))
    return int(max(PX_SUBTITULO_MIN, min(PX_SUBTITULO_MAX, round(alto * PX_SUBTITULO_FRACCION))))


def alto_subtitulo(alto_ventana):
    """El mismo tamaño en unidades de camera.ui (el alto de la ventana mide 1)."""
    return px_subtitulo(alto_ventana) / max(1.0, float(alto_ventana))


def partir_lineas(texto, medir, ancho, max_lineas=2):
    """(lineas, cabe): `texto` partido en <= `max_lineas` líneas de ancho <= `ancho` según `medir(cadena) -> ancho`.
    Con 2 líneas busca el corte más equilibrado. Si no cabe, las primeras líneas con «…» y cabe = False."""
    texto = " ".join(str(texto or "").split())
    if not texto or medir(texto) <= ancho or max_lineas <= 1:
        return ([texto], not texto or medir(texto) <= ancho)
    palabras = texto.split(" ")
    if max_lineas == 2:
        mejor = None
        for i in range(1, len(palabras)):
            a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
            peor = max(medir(a), medir(b))
            if mejor is None or peor < mejor[0]:
                mejor = (peor, [a, b])
        if mejor is not None and mejor[0] <= ancho:
            return (mejor[1], True)
    lineas, actual = [], ""
    for palabra in palabras:                       # voraz: llena cada línea
        prueba = palabra if not actual else actual + " " + palabra
        if medir(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    if len(lineas) <= max_lineas and all(medir(linea) <= ancho for linea in lineas):
        return (lineas, True)
    lineas = lineas[:max_lineas]
    ultima = lineas[-1]
    while ultima and medir(ultima + "…") > ancho and " " in ultima:
        ultima = ultima.rsplit(" ", 1)[0]
    lineas[-1] = ultima.rstrip(" ,;:.") + "…"
    return (lineas, False)


# -- Línea de tiempo ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Tramo:
    plano: Plano
    inicio: float
    fin: float
    subtitulos: tuple            # ((texto, inicio, fin), ...) en tiempo GLOBAL de la línea

    @property
    def duracion(self):
        return self.fin - self.inicio


class LineaTiempo:
    """Los planos uno detrás de otro (cada uno dura segundos·escala). El negro: entrada desde la carga, cortes de
    FUNDIDO_CORTE de ida y de vuelta centrados en cada frontera, y salida al final."""

    def __init__(self, planos, escala=1.0, entrada=ENTRADA_INICIAL, corte=FUNDIDO_CORTE, salida_final=SALIDA_FINAL):
        if not planos:
            raise ValueError("un final sin planos")
        escala = max(0.0, float(escala))
        self.escala = escala
        self.entrada = entrada * min(1.0, escala) if escala < 1.0 else entrada
        self.corte = corte * min(1.0, escala) if escala < 1.0 else corte
        self.salida = salida_final * min(1.0, escala) if escala < 1.0 else salida_final
        tramos, inicio = [], 0.0
        for plano in planos:
            dur = plano.segundos * escala
            subs = tuple((texto, inicio + a * escala, inicio + b * escala)
                         for texto, (a, b) in zip(plano.subtitulos, reparto_subtitulos(plano.subtitulos, plano.segundos)))
            tramos.append(Tramo(plano, inicio, inicio + dur, subs))
            inicio += dur
        self.tramos = tuple(tramos)
        self.duracion = inicio

    def indice_en(self, tiempo):
        if tiempo >= self.duracion:
            return len(self.tramos) - 1
        for i, tramo in enumerate(self.tramos):
            if tiempo < tramo.fin:
                return i
        return len(self.tramos) - 1

    def en(self, tiempo):
        """(índice del plano, t 0..1 dentro de él) al tiempo `tiempo` (s desde el principio)."""
        i = self.indice_en(tiempo)
        tramo = self.tramos[i]
        t = 1.0 if tramo.duracion <= 0 else (tiempo - tramo.inicio) / tramo.duracion
        return i, _recorte(t)

    def negro(self, tiempo):
        """Alfa del telón negro (1 = pantalla negra) al tiempo `tiempo`."""
        alfa = 0.0
        if self.entrada > 0 and tiempo < self.entrada:
            alfa = max(alfa, 1.0 - tiempo / self.entrada)
        elif tiempo <= 0:
            alfa = 1.0
        fin = self.duracion
        if self.salida > 0 and tiempo > fin - self.salida:
            alfa = max(alfa, 1.0 - (fin - tiempo) / self.salida)
        elif tiempo >= fin:
            alfa = 1.0
        if self.corte > 0:
            for tramo in self.tramos[1:]:
                distancia = abs(tiempo - tramo.inicio)
                if distancia < self.corte:
                    alfa = max(alfa, 1.0 - distancia / self.corte)
        return _recorte(alfa)

    def subtitulo(self, tiempo):
        """(texto, alfa) del subtítulo visible, o (None, 0)."""
        tramo = self.tramos[self.indice_en(tiempo)]
        fundido = SUBTITULO_FUNDIDO * min(1.0, self.escala) if self.escala < 1.0 else SUBTITULO_FUNDIDO
        for texto, a, b in tramo.subtitulos:
            if a <= tiempo < b:
                if fundido <= 0:
                    return texto, 1.0
                return texto, _recorte(min((tiempo - a) / fundido, (b - tiempo) / fundido))
        return None, 0.0

    def cortes(self):
        """Tiempos en que empieza cada plano (el director llama a `entrar` al cruzarlos)."""
        return [tramo.inicio for tramo in self.tramos]


# -- Mantener para saltar -------------------------------------------------------------------------------------------------

class MantenerParaSaltar:
    """Acumulador: mientras se mantiene, sube a 1 en `segundos`; al soltar se vacía (`vaciado` veces más rápido). `listo`
    pasa a True al llenarse (una vez). Una pulsación (o mantener) enseña el aviso `aviso_s` s."""

    def __init__(self, segundos=SALTAR_SEGUNDOS, vaciado=SALTAR_VACIADO, aviso_s=AVISO_SEGUNDOS, aviso_inicial=0.0):
        self.segundos = max(1e-6, float(segundos))
        self.vaciado = float(vaciado)
        self.aviso_s = float(aviso_s)
        self.progreso = 0.0
        self.listo = False
        self._aviso = float(aviso_inicial)

    def pulsacion(self):
        self._aviso = max(self._aviso, self.aviso_s)

    def avanzar(self, dt, mantenido):
        """Un frame. Devuelve True SOLO en el frame en que se completa."""
        dt = max(0.0, float(dt))
        if self.listo:
            return False
        if mantenido:
            self._aviso = max(self._aviso, self.aviso_s)
            self.progreso = min(1.0, self.progreso + dt / self.segundos)
        else:
            self.progreso = max(0.0, self.progreso - dt * self.vaciado / self.segundos)
            self._aviso = max(0.0, self._aviso - dt)
        if self.progreso >= 1.0:
            self.listo = True
            return True
        return False

    @property
    def aviso_visible(self):
        return self._aviso > 0.0 or self.progreso > 0.0

    @property
    def alfa_aviso(self):
        """Alfa del aviso: entero mientras se ve, con medio segundo de salida."""
        if self.progreso > 0.0:
            return 1.0
        return _recorte(self._aviso / 0.5)


def rotacion_mirando(origen, objetivo):
    """(pitch, yaw) en grados para mirar de `origen` a `objetivo` (x, y, z): pitch > 0 mira hacia abajo, yaw 0 = +z."""
    dx, dy, dz = (objetivo[i] - origen[i] for i in range(3))
    return (-math.degrees(math.atan2(dy, math.hypot(dx, dz))), math.degrees(math.atan2(dx, dz)))

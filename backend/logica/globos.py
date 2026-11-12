# Globos de texto de los NPC (Python puro: sin ursina ni panda3d). Punto 4 del plan final: de vez en cuando un peatón
# cercano «dice» una frase corta que refleja su estado, cómo está la ciudad y la hora. Aquí se decide QUÉ frase y CUÁNDO;
# dibujarla es cosa de frontend/globos_npc.py.
#
# FRASES: backend/datos/frases_npc.json
#   {"version": 1,
#    "neutro": [...], "sociable": [...], "aislado": [...], "celular": [...], "enojado": [...],      por estado del NPC
#    "ciudad": {"florece": [...], "sano": [...], "tenso": [...], "apagado": [...]},                  por nivel del Ambiente
#    "hora":   {"madrugada": [...], "manana": [...], "tarde": [...], "noche": [...]}}                por franja horaria
#   cada elemento = {"t": "texto", "dia_min": n}   (dia_min opcional: la frase no sale antes de ese día de la partida)
# Si el archivo falta o está dañado se usa RESPALDO (unas pocas frases embebidas) y se avisa una vez por stderr; una
# categoría que falte o venga vacía se completa con la del respaldo. Un elemento mal formado se ignora.
#
# SelectorFrases.elegir(estado, nivel, hora, dia) -> texto
#   Escoge primero la categoría (estado 60 %, ciudad 25 %, hora 15 %; solo entre las que tienen frases) y luego la frase
#   por ROTACIÓN: cada categoría es una baraja que se recorre entera antes de volver a barajar. Además una MEMORIA de las
#   últimas `memoria` frases dichas (en cualquier categoría) impide repetir una frase en los siguientes N globos.
#
# PlanificadorGlobos: piscina de `ranuras` globos REASIGNABLES (no uno por NPC).
#   avanzar(dt, candidatos, nivel, hora, dia)   candidatos = [(clave_npc, estado, distancia_m, peso)] YA filtrados por
#       el frontend (cerca de la cámara y a la vista). Envejece los globos, libera los vencidos, apaga con un fundido los
#       de NPC que dejaron de ser candidatos y, si toca (enfriamiento global y por NPC), da un globo nuevo.
#   ranuras[k] -> Ranura(clave, texto, edad, duracion, serie) | clave None = libre.  alfa(k) -> 0..1 (fundido).
#
# Todo el azar es inyectado (`azar`: objeto con random(), uniform(a, b) y shuffle(lista); p. ej. random.Random(semilla)).

import json
import os
import sys
from collections import deque

ESTADOS = ("neutro", "sociable", "aislado", "celular", "enojado")
NIVELES = ("florece", "sano", "tenso", "apagado")
FRANJAS = ("madrugada", "manana", "tarde", "noche")
RUTA_FRASES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos", "frases_npc.json")
VERSION = 1
LARGO_MAXIMO = 90               # caracteres: una frase más larga se descarta (no cabe en un globo)

PESO_ESTADO, PESO_CIUDAD, PESO_HORA = 0.60, 0.25, 0.15
MEMORIA = 8                     # frases recientes que no se repiten

RANURAS = 4
MAXIMO_A_LA_VEZ = 2             # globos visibles a la vez (las otras ranuras absorben los fundidos de salida)
ENFRIAMIENTO_GLOBAL = (3.0, 7.0)        # s entre dos globos nuevos
ENFRIAMIENTO_NPC = 30.0         # s sin que el mismo NPC vuelva a hablar
DURACION = (3.0, 5.0)           # s en pantalla (según el largo del texto)
FUNDIDO = 0.35                  # s de entrada y de salida
CARACTERES_POR_SEGUNDO = 22.0   # para alargar la duración de las frases largas
MAXIMO_ENFRIAMIENTOS = 96       # entradas del registro por NPC antes de podar

RESPALDO = {
    "version": VERSION,
    "neutro": [{"t": "Otro día más en el barrio."}, {"t": "A ver qué dicen hoy las noticias."},
               {"t": "Voy tarde, como siempre."}],
    "sociable": [{"t": "¡Buenas! ¿Cómo va todo?"}, {"t": "Nos vemos en la plaza más tarde."},
                 {"t": "Qué gusto encontrarse gente en la calle."}],
    "aislado": [{"t": "Mejor paso de largo."}, {"t": "Ya casi no hablo con nadie."},
                {"t": "Prefiero no meterme."}],
    "celular": [{"t": "Llevo tres horas haciendo scroll y no recuerdo nada."}, {"t": "Un video más y ya."},
                {"t": "¿Eso que leí era verdad?"}],
    "enojado": [{"t": "¡Otra vez con ese cuento!"}, {"t": "Ya no se le puede creer a nadie."},
                {"t": "Todo el mundo opina y nadie revisa."}],
    "ciudad": {
        "florece": [{"t": "Da gusto ver la plaza llena."}, {"t": "Hoy el barrio amaneció contento."}],
        "sano": [{"t": "Se respira tranquilo por aquí."}, {"t": "Poco a poco esto mejora."}],
        "tenso": [{"t": "Anda el ambiente pesado."}, {"t": "La gente anda prevenida."}],
        "apagado": [{"t": "Ya nadie levanta la cara en el parque."}, {"t": "Qué solas están las calles."}],
    },
    "hora": {
        "madrugada": [{"t": "A esta hora no hay ni un alma."}],
        "manana": [{"t": "Un tinto y a trabajar."}],
        "tarde": [{"t": "Qué calor hace a esta hora."}],
        "noche": [{"t": "Ya es hora de ir cerrando."}],
    },
}

_avisados = set()


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[globos] {motivo}", file=sys.stderr)


def franja_de(hora):
    """Franja horaria de una hora de juego 0..24: madrugada [0, 6) · manana [6, 12) · tarde [12, 19) · noche [19, 24).
    None si no hay hora."""
    if hora is None or isinstance(hora, bool) or not isinstance(hora, (int, float)) or hora != hora:
        return None
    hora = hora % 24.0
    if hora < 6.0:
        return "madrugada"
    if hora < 12.0:
        return "manana"
    if hora < 19.0:
        return "tarde"
    return "noche"


def _limpiar_lista(crudo):
    """[(texto, dia_min)] válidos de una lista del JSON (acepta también cadenas sueltas). Lo mal formado se ignora."""
    frases = []
    if not isinstance(crudo, list):
        return frases
    for elemento in crudo:
        dia_min = 1
        if isinstance(elemento, str):
            texto = elemento
        elif isinstance(elemento, dict):
            texto = elemento.get("t")
            dia = elemento.get("dia_min", 1)
            if isinstance(dia, int) and not isinstance(dia, bool) and dia >= 1:
                dia_min = dia
        else:
            continue
        if not isinstance(texto, str):
            continue
        texto = " ".join(texto.split())
        if texto and len(texto) <= LARGO_MAXIMO and all(texto != t for t, _ in frases):
            frases.append((texto, dia_min))
    return frases


def normalizar(datos):
    """Catálogo interno {("estado", e) | ("ciudad", n) | ("hora", f): [(texto, dia_min), ...]} a partir del dict del JSON.
    Las categorías que falten o queden vacías se toman de RESPALDO. Nunca lanza."""
    datos = datos if isinstance(datos, dict) else {}
    catalogo = {}

    def poner(clave, crudo, respaldo):
        frases = _limpiar_lista(crudo)
        catalogo[clave] = frases if frases else _limpiar_lista(respaldo)

    ciudad = datos.get("ciudad") if isinstance(datos.get("ciudad"), dict) else {}
    hora = datos.get("hora") if isinstance(datos.get("hora"), dict) else {}
    for estado in ESTADOS:
        poner(("estado", estado), datos.get(estado), RESPALDO[estado])
    for nivel in NIVELES:
        poner(("ciudad", nivel), ciudad.get(nivel), RESPALDO["ciudad"][nivel])
    for franja in FRANJAS:
        poner(("hora", franja), hora.get(franja), RESPALDO["hora"][franja])
    return catalogo


def cargar_frases(ruta=None):
    """(catálogo normalizado, origen): origen "archivo" si se leyó el JSON, "respaldo" si falta o está dañado."""
    ruta = RUTA_FRASES if ruta is None else ruta
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, dict):
            raise ValueError("la raíz no es un objeto")
        if datos.get("version", VERSION) != VERSION:
            raise ValueError(f"versión desconocida: {datos.get('version')!r}")
        return normalizar(datos), "archivo"
    except FileNotFoundError:
        _avisar(f"no existe {os.path.basename(ruta)}; se usan las frases de respaldo.")
    except (OSError, ValueError) as error:
        _avisar(f"{os.path.basename(ruta)} no se pudo leer ({error}); se usan las frases de respaldo.")
    return normalizar(RESPALDO), "respaldo"


class SelectorFrases:

    def __init__(self, catalogo=None, azar=None, memoria=MEMORIA):
        if azar is None:
            import random
            azar = random.Random()
        self._catalogo = normalizar(RESPALDO) if catalogo is None else catalogo
        self._azar = azar
        self._recientes = deque(maxlen=max(0, int(memoria)))
        self._barajas = {}                       # clave de categoría -> [índices pendientes] (se saca del final)

    def recientes(self):
        return list(self._recientes)

    def _baraja(self, clave):
        pendientes = self._barajas.get(clave)
        if not pendientes:
            pendientes = list(range(len(self._catalogo.get(clave, ()))))
            self._azar.shuffle(pendientes)
            self._barajas[clave] = pendientes
        return pendientes

    def _sacar(self, clave, dia):
        """Siguiente frase de la baraja de `clave` que se puede decir (día alcanzado y no reciente), o None."""
        frases = self._catalogo.get(clave)
        if not frases:
            return None
        for _ in range(2):                       # lo que queda de la baraja y, si no basta, una baraja nueva
            pendientes = self._baraja(clave)
            for k in range(len(pendientes) - 1, -1, -1):
                texto, dia_min = frases[pendientes[k]]
                if dia_min <= dia and texto not in self._recientes:
                    del pendientes[k]
                    return texto
            self._barajas[clave] = []
        return None

    def elegir(self, estado, nivel=None, hora=None, dia=None):
        """La frase del globo, o None si no hay ninguna que no sea repetida. `dia` None = sin filtro de día."""
        dia = 10 ** 9 if dia is None else dia
        opciones = []
        if estado not in ESTADOS:
            estado = "neutro"
        opciones.append((("estado", estado), PESO_ESTADO))
        if nivel in NIVELES:
            opciones.append((("ciudad", nivel), PESO_CIUDAD))
        franja = franja_de(hora)
        if franja is not None:
            opciones.append((("hora", franja), PESO_HORA))
        while opciones:
            total = sum(peso for _, peso in opciones)
            tirada, acumulado, elegido = self._azar.random() * total, 0.0, len(opciones) - 1
            for k, (_, peso) in enumerate(opciones):
                acumulado += peso
                if tirada < acumulado:
                    elegido = k
                    break
            clave, _ = opciones.pop(elegido)
            texto = self._sacar(clave, dia)
            if texto is not None:
                self._recientes.append(texto)
                return texto
        return None


class Ranura:
    __slots__ = ("clave", "texto", "edad", "duracion", "serie")

    def __init__(self):
        self.clave, self.texto, self.edad, self.duracion, self.serie = None, "", 0.0, 0.0, 0


def duracion_de(texto):
    """Segundos en pantalla de un texto: DURACION[0] para lo corto y hasta DURACION[1] según el largo."""
    return max(DURACION[0], min(DURACION[1], 1.5 + len(texto) / CARACTERES_POR_SEGUNDO))


def alfa_de(edad, duracion, fundido=FUNDIDO):
    """Opacidad 0..1 de un globo de `edad` s que dura `duracion` s: entra y sale con un fundido de `fundido` s."""
    if edad <= 0.0 or edad >= duracion:
        return 0.0
    if fundido <= 0.0:
        return 1.0
    return max(0.0, min(1.0, edad / fundido, (duracion - edad) / fundido))


class PlanificadorGlobos:

    def __init__(self, selector, azar=None, ranuras=RANURAS, maximo=MAXIMO_A_LA_VEZ,
                 enfriamiento_global=ENFRIAMIENTO_GLOBAL, enfriamiento_npc=ENFRIAMIENTO_NPC):
        if azar is None:
            import random
            azar = random.Random()
        self._selector, self._azar = selector, azar
        self.ranuras = [Ranura() for _ in range(max(1, int(ranuras)))]
        self._maximo = max(1, min(int(maximo), len(self.ranuras)))
        self._enfriamiento_global, self._enfriamiento_npc = enfriamiento_global, float(enfriamiento_npc)
        self.t = 0.0
        self._siguiente = self._azar.uniform(*enfriamiento_global)      # el primer globo tampoco sale al instante
        self._callados = {}                      # clave de NPC -> instante hasta el que no vuelve a hablar
        self.dichos = 0

    def alfa(self, k):
        r = self.ranuras[k]
        return 0.0 if r.clave is None else alfa_de(r.edad, r.duracion)

    def activos(self):
        return sum(1 for r in self.ranuras if r.clave is not None)

    def vaciar(self):
        for r in self.ranuras:
            r.clave = None

    def avanzar(self, dt, candidatos=(), nivel=None, hora=None, dia=None):
        """Un paso de `dt` s. Devuelve la Ranura que acaba de recibir un globo nuevo, o None."""
        dt = max(0.0, dt)
        self.t += dt
        presentes = {c[0] for c in candidatos}
        hablando = set()
        vivos = 0
        for r in self.ranuras:
            if r.clave is None:
                continue
            r.edad += dt
            if r.edad >= r.duracion:
                r.clave = None
                continue
            if r.clave not in presentes and r.duracion - r.edad > FUNDIDO:
                r.duracion = r.edad + FUNDIDO                 # se alejó o salió de la vista: se apaga ya (con fundido)
            hablando.add(r.clave)
            if r.duracion - r.edad > FUNDIDO:
                vivos += 1
        if self.t < self._siguiente or vivos >= self._maximo or not candidatos:
            return None
        libre = next((r for r in self.ranuras if r.clave is None), None)
        if libre is None:
            return None
        callados = self._callados
        aptos = [c for c in candidatos if c[0] not in hablando and callados.get(c[0], -1.0) <= self.t]
        if not aptos:
            return None
        # Más cerca = más probable (peso / (1 + distancia)); el peso lo da el frontend (p. ej. más a quien charla).
        pesos = [(c[3] if len(c) > 3 else 1.0) / (1.0 + max(0.0, c[2])) for c in aptos]
        tirada, acumulado, elegido = self._azar.random() * sum(pesos), 0.0, aptos[-1]
        for c, peso in zip(aptos, pesos):
            acumulado += peso
            if tirada < acumulado:
                elegido = c
                break
        self._siguiente = self.t + self._azar.uniform(*self._enfriamiento_global)
        texto = self._selector.elegir(elegido[1], nivel, hora, dia)
        if texto is None:
            return None
        libre.clave, libre.texto, libre.edad, libre.duracion = elegido[0], texto, 0.0, duracion_de(texto)
        libre.serie += 1
        self.dichos += 1
        callados[elegido[0]] = self.t + self._enfriamiento_npc
        if len(callados) > MAXIMO_ENFRIAMIENTOS:
            for clave in [c for c, hasta in callados.items() if hasta <= self.t]:
                del callados[clave]
        return libre

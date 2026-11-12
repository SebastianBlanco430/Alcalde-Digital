# Manillas (modelo puro, sin ursina): cintas de muñeca al estilo de las fitinhas do Senhor do Bonfim. En el juego son el
# «termómetro» que lleva la gente: cada indicador de la ciudad tiene su manilla en el HUD y cada NPC lleva una según su
# estado emocional (backend/logica/ambiente_ciudad.perfil_npc).
#
# ACCESIBLE POR DISEÑO: el estado NUNCA depende solo del color (y menos de rojo/verde). Cada nivel se lee por CUATRO
# canales redundantes:
#   1. color   — paleta tipo Okabe-Ito con escalones de luminancia (se distinguen también en escala de grises);
#   2. patrón  — lisa, rayada, punteada, deshilachada... (forma del tejido);
#   3. nudos   — 3, 2, 1 o 0 nudos (la fitinha tradicional lleva tres: uno por deseo);
#   4. desgaste— cuánto de deshilachada está (0.0 nueva .. 1.0 a punto de romperse), continuo.
# tests/test_manillas.py comprueba con frontend/daltonismo_calculos (simulación de protanopia, deuteranopia, tritanopia y
# acromatopsia) que ningún par de colores de una misma paleta colapsa, y que patrón y nudos son únicos por nivel.
#
# NIVELES. Un valor 0-100 se convierte en «bondad» (para desinformación y conflictos, 100 - valor: menos es mejor) y la
# bondad cae en uno de cuatro niveles, los mismos nombres que usa el Ambiente:
#   florece (>= 75) · sano (>= 50) · tenso (>= 25) · apagado (< 25)
#
#   manilla_de(indicador, valor)   -> Manilla(color, patron, desgaste, descripcion)
#   detalle_manilla(indicador, valor) -> dict con lo anterior + nivel, nudos, nombre y símbolo del indicador
#   manilla_de_npc(estado)         -> Manilla del estado emocional de un NPC
#   detalle_manilla_npc(estado)    -> dict con lo anterior + nudos
#
# Los colores son tuplas RGB 0-255 (el frontend las convierte a su tipo de color).

import math
from collections import namedtuple

# color: (r, g, b) 0-255 · patron: nombre del tejido · desgaste: 0.0..1.0 · descripcion: texto corto para el jugador
Manilla = namedtuple("Manilla", "color patron desgaste descripcion")

INDICADORES = ("convivencia", "confianza", "desinformacion", "bienestar", "conflictos")
# En estos, MENOS es mejor: la bondad es 100 - valor.
INVERTIDOS = ("desinformacion", "conflictos")

NOMBRES = {
    "convivencia": "Convivencia", "confianza": "Confianza", "desinformacion": "Desinformación",
    "bienestar": "Bienestar digital", "conflictos": "Conflictos",
}
# Identidad del indicador que NO depende del color: un símbolo (dije de la cinta) y su posición en la muñeca.
SIMBOLOS = {
    "convivencia": "manos", "confianza": "llave", "desinformacion": "megafono", "bienestar": "sol", "conflictos": "rayo",
}

NIVELES = ("florece", "sano", "tenso", "apagado")       # de mejor a peor
UMBRALES_NIVEL = (75.0, 50.0, 25.0)                     # bondad mínima de florece, sano y tenso

# nivel -> (color, patrón, nudos). Luminancias muy separadas: amarillo claro, azul medio, bermellón, violeta oscuro.
ESTILO_NIVEL = {
    "florece": ((240, 228, 66), "lisa", 3),
    "sano": ((86, 180, 233), "rayada", 2),
    "tenso": ((213, 94, 0), "punteada", 1),
    "apagado": ((60, 36, 84), "deshilachada", 0),
}

# Frase corta por indicador y nivel (lo que el jugador lee al pasar el cursor por la manilla).
_FRASES = {
    "convivencia": ("los vecinos se buscan", "hay trato cordial", "cada quien por su lado", "nadie se saluda"),
    "confianza": ("se cree en lo que se publica", "se confía con cautela", "se duda de todo", "nadie cree a nadie"),
    "desinformacion": ("casi no corren bulos", "algún bulo suelto", "los bulos corren", "manda el rumor"),
    "bienestar": ("la red suma a la vida", "uso sano de la red", "la red cansa", "la red aísla"),
    "conflictos": ("calles en calma", "roces menores", "discusiones a diario", "la calle está crispada"),
}

# Estados emocionales de un NPC (ambiente_ciudad.ESTADOS_NPC) -> (color, patrón, nudos, desgaste, descripción).
ESTADOS_NPC = ("sociable", "neutro", "aislado", "celular", "enojado")
ESTILO_NPC = {
    "sociable": ((240, 228, 66), "lisa", 3, 0.0, "abierto a conversar"),
    "neutro": ((250, 250, 245), "trenzada", 2, 0.2, "va a lo suyo"),
    "celular": ((86, 180, 233), "rayada", 1, 0.45, "pegado al celular"),
    "aislado": ((60, 36, 84), "deshilachada", 0, 0.8, "evita a la gente"),
    "enojado": ((213, 94, 0), "zigzag", 1, 0.6, "está crispado"),
}

PATRONES = tuple(sorted({e[1] for e in ESTILO_NIVEL.values()} | {e[1] for e in ESTILO_NPC.values()}))


def _valor(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"Valor de indicador inválido: {valor!r}.")
    return max(0.0, min(100.0, float(valor)))


def _indicador(indicador):
    if indicador not in INDICADORES:
        raise ValueError(f"Indicador desconocido: {indicador!r}; válidos: {INDICADORES}.")
    return indicador


def bondad(indicador, valor):
    """0-100 donde más es mejor: el valor tal cual, o 100 - valor en desinformación y conflictos."""
    valor = _valor(valor)
    return 100.0 - valor if _indicador(indicador) in INVERTIDOS else valor


def nivel_de_bondad(bondad_valor):
    for nivel, umbral in zip(NIVELES, UMBRALES_NIVEL):
        if bondad_valor >= umbral:
            return nivel
    return NIVELES[-1]


def desgaste_de(indicador, valor):
    """Cuánto de deshilachada está la manilla: 0.0 (bondad 100) .. 1.0 (bondad 0), lineal y continuo."""
    return round(1.0 - bondad(indicador, valor) / 100.0, 4)


def manilla_de(indicador, valor):
    """Manilla(color, patron, desgaste, descripcion) del `indicador` con ese `valor` (0-100; se recorta)."""
    nivel = nivel_de_bondad(bondad(indicador, valor))
    color, patron, _nudos = ESTILO_NIVEL[nivel]
    frase = _FRASES[indicador][NIVELES.index(nivel)]
    return Manilla(color, patron, desgaste_de(indicador, valor), f"{NOMBRES[indicador]}: {frase}")


def detalle_manilla(indicador, valor):
    """Todo lo que la vista puede pintar: la Manilla más nivel, nudos, nombre y símbolo del indicador (JSON-serializable)."""
    manilla = manilla_de(indicador, valor)
    nivel = nivel_de_bondad(bondad(indicador, valor))
    return {
        "indicador": indicador, "nombre": NOMBRES[indicador], "simbolo": SIMBOLOS[indicador], "nivel": nivel,
        "color": list(manilla.color), "patron": manilla.patron, "nudos": ESTILO_NIVEL[nivel][2],
        "desgaste": manilla.desgaste, "descripcion": manilla.descripcion,
    }


def manillas_de_ciudad(valores):
    """{indicador: detalle} de los indicadores presentes en `valores` (los ausentes se omiten), en orden de INDICADORES."""
    return {nombre: detalle_manilla(nombre, valores[nombre]) for nombre in INDICADORES if nombre in valores}


def _estado(estado):
    if estado not in ESTILO_NPC:
        raise ValueError(f"Estado de NPC desconocido: {estado!r}; válidos: {ESTADOS_NPC}.")
    return ESTILO_NPC[estado]


def manilla_de_npc(estado):
    """Manilla del estado emocional de un NPC ('sociable', 'neutro', 'aislado', 'celular', 'enojado')."""
    color, patron, _nudos, desgaste, descripcion = _estado(estado)
    return Manilla(color, patron, desgaste, descripcion)


def detalle_manilla_npc(estado):
    manilla = manilla_de_npc(estado)
    return {"estado": estado, "color": list(manilla.color), "patron": manilla.patron, "nudos": _estado(estado)[2],
            "desgaste": manilla.desgaste, "descripcion": manilla.descripcion}

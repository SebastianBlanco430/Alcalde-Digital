# Nombres de los NPC según su género (datos puros, sin ursina). Sirven para dos cosas:
#   1. Saber de qué género es un nombre ya escrito en los datos (comercios, mototaxistas, NPC clave, etapas): así el
#      modelo 3D que se le da casa con el nombre (antes Inés Duarte salía con smoking y Marcos Vela con el modelo de
#      mujer).
#   2. Dar un nombre acorde a un NPC que no lo tiene, de forma determinista (mismo índice y semilla = mismo nombre,
#      también en el modo cooperativo, donde cada cliente construye los NPC con la misma semilla).
# Nombres brasileños y latinos, coherentes con la favela de Ciudad Nova.

import random
import unicodedata

HOMBRE, MUJER = "hombre", "mujer"

NOMBRES_HOMBRE = ("João", "Pedro", "Lucas", "Mateus", "Gabriel", "Rafael", "Thiago", "Bruno", "Felipe", "Diego",
                  "Marcos", "Carlos", "Antônio", "Francisco", "Paulo", "Rodrigo", "Gustavo", "Leandro", "Fábio",
                  "Renato", "Wagner", "Edson", "Jorge", "Sérgio", "Heitor", "Nilton", "Osvaldo", "Otávio", "Zeca",
                  "Beto", "Kauê", "Nonato", "Zequinha", "Zé", "Tomás", "Octavio", "Chucho")
NOMBRES_MUJER = ("Maria", "Ana", "Juliana", "Fernanda", "Camila", "Larissa", "Beatriz", "Patrícia", "Aline",
                 "Letícia", "Vanessa", "Daniela", "Gabriela", "Mariana", "Rita", "Sônia", "Cláudia", "Regina",
                 "Luana", "Tatiane", "Inés", "Lúcia", "Marta", "Neide", "Cleide", "Quitéria", "Lu", "Cleo",
                 "Rosa", "Bruna")

# Tratamientos que deciden el género por sí solos (en minúsculas y sin tildes).
TRATAMIENTOS_HOMBRE = ("seu", "senhor", "sr", "don", "tio", "dom")
TRATAMIENTOS_MUJER = ("dona", "senhora", "sra", "tia")      # «doña» queda «dona» al quitar la tilde


def _plano(texto):
    sin_tildes = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.replace(" ", " ").strip().lower()


_HOMBRES = frozenset(_plano(n) for n in NOMBRES_HOMBRE)
_MUJERES = frozenset(_plano(n) for n in NOMBRES_MUJER)


# Género de un nombre visible ("Dona Lúcia", "Seu Zé", "Inés Duarte", "Fiscal Rojas"): HOMBRE, MUJER o None si no
# se puede saber ("Florista", "Peatón 3"). Mira el tratamiento y, si no hay, la primera palabra que esté en las listas.
def genero_de_nombre(nombre):
    palabras = [p.strip(".,()") for p in _plano(nombre).split()]
    palabras = [p for p in palabras if p]
    if not palabras:
        return None
    if palabras[0] in TRATAMIENTOS_MUJER:
        return MUJER
    if palabras[0] in TRATAMIENTOS_HOMBRE:
        return HOMBRE
    for palabra in palabras:
        if palabra in _MUJERES:
            return MUJER
        if palabra in _HOMBRES:
            return HOMBRE
    return None


# Nombre determinista para el NPC `indice` del género pedido (generador propio: no toca otros azares).
def nombre_npc(indice, semilla, genero):
    lista = NOMBRES_MUJER if genero == MUJER else NOMBRES_HOMBRE
    return random.Random(semilla * 7307 + indice * 389 + (1 if genero == MUJER else 0)).choice(lista)

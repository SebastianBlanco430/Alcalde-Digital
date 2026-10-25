# Traducción entre paréntesis de los nombres y palabras en portugués que ve el jugador: «Prefeitura (Alcaldía)».
# Solo para mostrar: las claves (lugares, ids de misión, ciudadanos, textos de las huellas online) no cambian; la
# interfaz llama a nombre_visible() o glosar_texto() al convertirlas en texto.
#
# Se traduce lo que tiene un significado común, aunque el lugar sea inventado («Morro da Esperança»). No se traducen
# los nombres de persona, los topónimos que son solo un nombre («Praça da Sé») ni lo que se entiende igual en
# español («Mercado Municipal»): van en PROPIOS, que además evita traducir una palabra suelta dentro de ellos. En un
# texto solo lleva paréntesis la primera vez que aparece cada término.
#
# GLOSAR_NOMBRES = False (o ALCALDE_SIN_GLOSAS=1) deja los textos como antes.

import os
import re
from functools import lru_cache

GLOSAR_NOMBRES = True

# Lugares, letreros y cuentas de Civitas.
LUGARES = {
    "Prefeitura": "Alcaldía",
    "Prefeitura de Ciudad Nova": "Alcaldía de Ciudad Nova",
    "Morro da Esperança": "Cerro de la Esperanza",
    "Parque do Povo": "Parque del Pueblo",
    "Rodoviária": "Terminal de buses",
    "Escola de Samba": "Escuela de samba",
    "Escola de Samba Unidos da Esperança": "Escuela de samba",
    "G.R.E.S. Unidos da Esperança": "Escuela de samba",
    "Rádio Comunitária": "Radio comunitaria",
    "Rádio Comunitária 98,7": "Radio comunitaria",
    "Rádio Comunitária 98,7 FM": "Radio comunitaria",
    "Estação do Teleférico": "Estación del teleférico",
    "Lan House da Praça": "Cibercafé de la plaza",
    "Biblioteca do Parque": "Biblioteca del parque",
    "Jornal do Morro": "Periódico del cerro",
    "Fofoca da Laje": "Chisme de la azotea",
    "Zap do Morro": "WhatsApp del cerro",
}

# Traducción corta para los sitios estrechos (chip del minimapa, monitor, «Empieza en»).
CORTOS = {
    "Morro da Esperança": "Cerro",
    "Parque do Povo": "Parque",
    "Rodoviária": "Terminal",
    "Rádio Comunitária": "Radio",
    "Estação do Teleférico": "Teleférico",
}

# Palabras y frases sueltas; la traducción toma la mayúscula del texto («Mutirão (Trabajo...)», «mutirão (trabajo...)»).
TERMINOS = {
    "corrente do zap": "cadena de WhatsApp",
    "mutirão": "trabajo comunitario voluntario",
    "ensaio": "ensayo",
    "feira": "feria",
    "feijão": "frijoles",
    "laje": "azotea",
    "morro": "cerro",
    "zap": "WhatsApp",
    "praça": "plaza",
    "bom dia": "buenos días",
    "dica do dia": "consejo del día",
    "tudo bem?": "¿Todo bien?",
    "valeu": "gracias",
    "obrigado": "gracias",
    "até a próxima": "hasta la próxima",
    "até logo": "hasta luego",
    "isso é um absurdo!": "¡Esto es un absurdo!",
    "tá, mas cadê a fonte?": "ya, pero ¿dónde está la fuente?",
    "ganhe dinheiro fácil": "gana dinero fácil",
}

# Se dejan tal cual, también por dentro.
PROPIOS = (
    "Praça da Sé", "Mercado Municipal", "Hospital Santa Casa", "Santa Casa", "Universidade de Ciudad Nova",
    "Universidade de Nova", "Universidade", "Ciudad Nova",
    "Ana", "Beto", "Carlos", "Diana", "Elena", "Fábio", "Gina", "Hugo", "Ivan", "Júlia", "Kauã", "Luana", "Marcos",
    "Nayara", "Otávio", "Paula", "Quitéria",
    "Luana Ferreira", "Kauã Oliveira", "Dona Quitéria", "Seu Otávio", "Nayara Santos", "Marcos do Morro",
    "Mestre Zé do Pandeiro", "Joao Mendes",
)

# Etiquetas de «Tendencias»: la traducción va en la línea de la categoría, no dentro del #.
ETIQUETAS = {
    "#PrefeituraAberta": "Alcaldía abierta",
    "#MorroDaEsperança": "Cerro de la Esperanza",
    "#EnsaioDeSamba": "Ensayo de samba",
    "#PreçoDaFeira": "Precio de la feria",
    "#RádioDoMorro": "Radio del cerro",
}


def glosas_activas():
    return GLOSAR_NOMBRES and os.environ.get("ALCALDE_SIN_GLOSAS", "").strip() != "1"


# Pone en mayúscula la traducción de un término si el original empieza en mayúscula.
def _con_mayuscula_de(original, glosa):
    if glosa[:1].islower() and original[:1].isupper():
        return glosa[:1].upper() + glosa[1:]
    return glosa


def _con_glosa(texto, glosa):
    return f"{texto} ({glosa})"


# Traducción de una clave conocida, o None. Los letreros 3D la ponen en una segunda línea. `corto` usa CORTOS.
def glosa_de(clave, corto=False):
    if not glosas_activas() or not isinstance(clave, str):
        return None
    glosa = (CORTOS.get(clave) if corto else None) or LUGARES.get(clave)
    if glosa is None:
        termino = TERMINOS.get(clave.lower())
        if termino is None:
            return None
        glosa = _con_mayuscula_de(clave, termino)
    return glosa


# «Clave (traducción)»; lo que no está en las tablas (o ya está traducido) se devuelve igual.
def nombre_visible(clave, corto=False):
    glosa = glosa_de(clave, corto)
    return clave if glosa is None else _con_glosa(clave, glosa)


# Traducción de una etiqueta de tendencia, o None.
def glosa_etiqueta(etiqueta):
    if not glosas_activas():
        return None
    return ETIQUETAS.get(etiqueta)


# Término entero: sin letras pegadas a los lados ni dentro de un #hashtag.
def _patron(termino):
    return re.compile(r"(?<![\w#])" + re.escape(termino) + r"(?!\w)", re.IGNORECASE)


# (patrón, traducción o None, sigue_mayuscula), los más largos primero: «Praça da Sé» se reconoce antes que «praça».
def _tabla():
    filas = [(t, g, False) for t, g in LUGARES.items()]
    filas += [(t, g, True) for t, g in TERMINOS.items()]
    filas += [(t, None, False) for t in PROPIOS]
    filas.sort(key=lambda fila: len(fila[0]), reverse=True)
    return [(_patron(t), g, sigue) for t, g, sigue in filas]


_TABLA = _tabla()


# Traduce la primera aparición de cada término de un texto (misión, noticia, comentario...). Un texto ya traducido
# se devuelve igual. Con caché porque el teléfono rehace su vista en cada frame.
def glosar_texto(texto):
    if not glosas_activas() or not isinstance(texto, str) or not texto:
        return texto
    return _glosar(texto)


@lru_cache(maxsize=2048)
def _glosar(texto):
    ocupados = []          # (inicio, fin) de lo ya reconocido
    inserciones = []       # (posición, texto a insertar)
    vistos = set()
    for patron, glosa, sigue in _TABLA:
        for m in patron.finditer(texto):
            inicio, fin = m.span()
            if any(inicio < b and fin > a for a, b in ocupados):
                continue
            ocupados.append((inicio, fin))
            if glosa is None:
                continue
            clave = glosa.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            final = _con_mayuscula_de(m.group(0), glosa) if sigue else glosa
            sufijo = f" ({final})"
            if texto[fin:fin + len(sufijo)].lower() == sufijo.lower():
                continue          # ya glosado
            inserciones.append((fin, sufijo))
    for posicion, sufijo in sorted(inserciones, reverse=True):
        texto = texto[:posicion] + sufijo + texto[posicion:]
    return texto

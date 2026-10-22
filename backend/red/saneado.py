# Saneado de texto que viene de la red (nombres de jugador, motivos, resúmenes...).
# Módulo PURO. Motivo: el `Text` de Ursina interpreta «<etiquetas>» y «<image:...>»
# (ursina/text.py, use_tags con start_tag '<'), así que NUNCA se debe mostrar texto de red sin pasar
# por aquí. El saneado se aplica en el anfitrión Y en el cliente (un anfitrión puede ser malicioso).
import unicodedata

LARGO_MIN_NOMBRE = 1
LARGO_MAX_NOMBRE = 16
SIGNOS_PERMITIDOS = frozenset("-_.")
RESERVADOS = ("civitas", "anfitrion", "sistema")   # comparados sin mayúsculas ni tildes

# Caracteres invisibles o de dirección de texto que se eliminan siempre
_BIDI_Y_INVISIBLES = frozenset(
    list(range(0x200B, 0x2010))      # ancho cero, ZWNJ, ZWJ, LRM, RLM
    + list(range(0x202A, 0x202F))    # LRE RLE PDF LRO RLO
    + list(range(0x2060, 0x2070))    # word joiner, invisibles matemáticos, aislantes
    + [0x061C, 0xFEFF, 0x180E, 0x00AD]
)


def _clave_comparacion(texto):
    """Clave para comparar nombres: NFD sin marcas combinantes y en minúsculas."""
    nfd = unicodedata.normalize("NFD", texto)
    sin_marcas = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return sin_marcas.casefold()


def es_reservado(nombre):
    """True si el nombre coincide con uno reservado (Civitas, Anfitrión, Sistema)."""
    return _clave_comparacion(nombre.strip()) in RESERVADOS


def _caracter_permitido(c):
    if c == " " or c in SIGNOS_PERMITIDOS:
        return True
    cat = unicodedata.category(c)
    return cat.startswith("L") or cat == "Nd"


def validar_nombre(texto):
    """Devuelve el nombre normalizado (NFC) si es válido; None si no.

    Válido: str de 1 a 16 caracteres, solo letras, dígitos, espacio y -_. ; sin espacios
    en los extremos ni dobles; sin < >, controles ni marcas bidi; y no reservado.
    """
    if type(texto) is not str:
        return None
    nombre = unicodedata.normalize("NFC", texto)
    if not (LARGO_MIN_NOMBRE <= len(nombre) <= LARGO_MAX_NOMBRE):
        return None
    if nombre != nombre.strip(" ") or "  " in nombre:
        return None
    if not all(_caracter_permitido(c) for c in nombre):
        return None
    if not any(c.isalnum() for c in nombre):
        return None            # solo signos: ilegible
    if es_reservado(nombre):
        return None
    return nombre


def limpiar_nombre(texto):
    """Versión indulgente para campos de entrada: quita lo no permitido y recorta a 16.

    Puede devolver "" (entonces el campo no es válido). No comprueba reservados.
    """
    if type(texto) is not str:
        return ""
    nfc = unicodedata.normalize("NFC", texto)
    filtrado = "".join(c for c in nfc if _caracter_permitido(c))
    filtrado = " ".join(filtrado.split(" "))          # conserva un solo espacio entre palabras
    partes = [p for p in filtrado.split(" ") if p]
    return " ".join(partes)[:LARGO_MAX_NOMBRE].strip(" ")


def nombre_unico(nombre, existentes):
    """Añade « (2)», « (3)»... si el nombre ya existe (sin mayúsculas ni tildes).

    El resultado nunca pasa de 16 caracteres: se recorta la base antes del sufijo.
    `existentes` es un iterable de nombres ya en uso.
    """
    usados = {_clave_comparacion(e) for e in existentes}
    if _clave_comparacion(nombre) not in usados:
        return nombre
    n = 2
    while True:
        sufijo = f" ({n})"
        base = nombre[:LARGO_MAX_NOMBRE - len(sufijo)].rstrip(" ")
        candidato = base + sufijo
        if _clave_comparacion(candidato) not in usados:
            return candidato
        n += 1


def sanear_texto_visible(texto, largo_max=200):
    """Texto de red seguro para mostrar en un `Text` de Ursina.

    NFC; sustituye < y > por « ‹ › » (así ninguna etiqueta se interpreta); elimina controles
    (los saltos de línea pasan a espacio), marcas bidi/invisibles y caracteres sin asignar;
    colapsa espacios y recorta a `largo_max`. Nunca lanza: lo no-str da "".
    """
    if type(texto) is not str:
        return ""
    salida = []
    for c in unicodedata.normalize("NFC", texto):
        if c == "<":
            salida.append("‹")
        elif c == ">":
            salida.append("›")
        elif c in "\n\r\t":
            salida.append(" ")
        elif ord(c) in _BIDI_Y_INVISIBLES:
            continue
        elif unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            continue
        else:
            salida.append(c)
    limpio = " ".join("".join(salida).split(" ")).strip()
    return " ".join(p for p in limpio.split(" ") if p)[:max(0, int(largo_max))]

# Matemática y textos del minijuego «Chat del barrio» visual (frontend/minijuegos_visual/chat_visual.py). Python puro, sin
# ursina, con tests en tests/test_chat_visual.py.
#
# - Quién está «escribiendo…» y cuántos a la vez (más cuanto más presión).
# - La viñeta oscura que cierra la pantalla con la presión, y cuándo vibra el teléfono.
# - Qué DATOS entregaría una respuesta, leídos SOLO del texto de la respuesta (nunca de su valor: no se chiva la buena).
# - La hora del teléfono.

import re

DEMORA_ESCRIBIENDO = 0.7          # s de «escribiendo…» antes de que se vea un mensaje nuevo
VINETA_MAX = 0.72                 # opacidad máxima de la viñeta
UMBRALES_VIBRACION = (0.5, 0.75, 0.9)

# Categorías de datos personales: (patrón, descripción). Se buscan en el texto de la respuesta.
_NUMERO = re.compile(r"\d[\d\s\-.]{3,}\d")
_PATRONES = (
    (re.compile(r"\bdocumento|\bDNI\b|\bRG\b|\bCPF\b", re.I), "un documento de identidad"),
    (re.compile(r"\btel[eé]fono|\bcelular|\bwhats", re.I), "un número de teléfono"),
    (re.compile(r"\bcuenta\b|\bPIX\b|\bclave\b|\bcontraseña", re.I), "datos de una cuenta"),
    (re.compile(r"\bdirecci[oó]n|\bvive en\b|\bsu casa\b|\bcalle [A-ZÁÉÍÓÚ]", re.I), "una dirección"),
    (re.compile(r"\bfoto\b", re.I), "una foto"),
)
# Frases de «ceder»: entregar algo sin preguntar.
_CEDER = re.compile(r"ah[ií] va|te lo paso|lo doy|tengo el de|es el \d|toma\b|te mando|les mando|mando mi|lo comparto|"
                    r"aqu[ií] lo tienes|con los tel[eé]fonos|en privado", re.I)
# Frases de «no ceder»: negativas, que anulan la alarma.
_NEGAR = re.compile(r"\bno (mando|paso|doy|voy a dar|comparto)|se lo tienes que pedir|preg[uú]nt(a|e)n?(le)?\b|"
                    r"yo no (paso|doy)|que me lo pida", re.I)


def datos_expuestos(texto):
    """Lista de (descripción, fragmento) de datos que la respuesta entregaría. Vacía si no entrega nada."""
    texto = str(texto or "")
    if _NEGAR.search(texto):
        return []
    salida = []
    numero = _NUMERO.search(texto)
    if numero:
        salida.append(("un número privado", numero.group(0).strip()))
    frase = _CEDER.search(texto)
    cede = bool(frase) or bool(numero)
    for patron, descripcion in _PATRONES:
        encontrado = patron.search(texto)
        if encontrado and cede:
            salida.append((descripcion, encontrado.group(0)))
    if frase and not salida:
        salida.append(("un dato personal", frase.group(0)))      # cede sin decir cuál: se avisa igual
    vistos, unicos = set(), []
    for descripcion, fragmento in salida:
        if descripcion not in vistos:
            vistos.add(descripcion)
            unicos.append((descripcion, fragmento))
    return unicos


def aviso_datos(texto):
    """Rótulo de aviso para la respuesta con el foco ('' si no entrega datos)."""
    datos = datos_expuestos(texto)
    if not datos:
        return ""
    partes = []
    for descripcion, fragmento in datos[:2]:
        partes.append(f"{descripcion} ({fragmento})" if any(c.isdigit() for c in fragmento) else descripcion)
    return "Si envías esto, entregas: " + " y ".join(partes)


def vineta(presion, reducir=False):
    """Opacidad de la viñeta oscura: crece con la presión (empieza a notarse a mitad)."""
    p = max(0.0, min(1.0, presion))
    alfa = VINETA_MAX * max(0.0, (p - 0.25) / 0.75) ** 1.3
    return alfa * (0.7 if reducir else 1.0)


def vibra(presion_antes, presion_ahora):
    """¿El teléfono vibra ahora? Sí al cruzar cada umbral de presión."""
    return any(presion_antes < u <= presion_ahora for u in UMBRALES_VIBRACION)


def escribiendo(nombres, presion):
    """Rótulo «X y N más están escribiendo…»: más gente cuanto más presión. `nombres` sin repetir."""
    nombres = [n for n in dict.fromkeys(nombres) if n]
    if not nombres:
        return ""
    cuantos = 1 + int(max(0.0, min(1.0, presion)) * 3)
    if cuantos <= 1 or len(nombres) == 1:
        extra = cuantos - 1
        if extra <= 0:
            return f"{nombres[0]} está escribiendo…"
        return f"{nombres[0]} y {extra} más están escribiendo…"
    return f"{nombres[0]}, {nombres[1 % len(nombres)]} y {cuantos - 2 if cuantos > 2 else 1} más están escribiendo…"


def puntos_escribiendo(t):
    """'.', '..' o '...' según el tiempo (los puntitos animados)."""
    return "." * (1 + int(t * 3) % 3)


def enfado(presion):
    """0..1: cuánto se enrojecen los avatares del grupo."""
    return max(0.0, min(1.0, (presion - 0.3) / 0.7))


def hora_texto(minutos_del_dia):
    """«hh:mm» a partir de minutos desde la medianoche."""
    m = int(minutos_del_dia) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def nombre_corto(de):
    """'Marcela (organizadora)' -> 'Marcela'."""
    return str(de or "").split("(")[0].strip() or "Alguien"


def inicial(de):
    corto = nombre_corto(de)
    return corto[0].upper() if corto else "?"


def ruta_dato(n_saltos=4):
    """Puntos (x, y) normalizados por los que «vuela» un dato expuesto hasta un perfil desconocido (de izquierda a derecha)."""
    puntos = [(-0.42, -0.05)]
    for i in range(1, n_saltos):
        x = -0.42 + 0.84 * i / n_saltos
        y = 0.16 if i % 2 else -0.18
        puntos.append((x, y))
    puntos.append((0.42, 0.05))
    return puntos


def punto_en_ruta(puntos, f):
    """Posición a lo largo de la ruta (f en 0..1), por tramos rectos de igual duración."""
    if not puntos:
        return 0.0, 0.0
    f = max(0.0, min(1.0, f))
    tramos = len(puntos) - 1
    if tramos <= 0:
        return puntos[0]
    pos = f * tramos
    i = min(int(pos), tramos - 1)
    local = pos - i
    (ax, ay), (bx, by) = puntos[i], puntos[i + 1]
    return ax + (bx - ax) * local, ay + (by - ay) * local

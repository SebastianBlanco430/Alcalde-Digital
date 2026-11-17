# Cálculos puros (sin ursina) del teléfono en grande (frontend/registro_telefono_grande.py): geometría, transición,
# cómo se parte una burbuja de chat con sus tramos marcables, a qué parte de la pantalla va cada elemento y el scroll del
# panel lateral. Todo con unidades de camera.ui (escena 16:9: x en ±0.889, y en ±0.5) y funciones `medir(cadena) -> ancho`
# inyectadas, así se prueba sin ventana (tests/test_telefono_grande.py).
#
#   ease_in_out(p) / rect_transicion(desde, hasta, p)   el teléfono crece desde el icono del HUD hasta el centro
#   remitente_partido(remitente)                        «+55 … (no está en tus contactos)» -> (nombre, subtítulo)
#   partir_burbuja(texto, fragmentos, medir, ancho)     líneas con los tramos marcables (número, x, ancho) de cada una
#   plan_zonas(elementos, zonas)                        dónde se dibuja cada elemento (cabecera, burbuja, foto…, detalle)
#   plan_scroll(alturas, visible, desplazamiento, sep)  qué filas del panel lateral se ven y dónde
#   tamano_burbuja(anchos, alto_linea, relleno)         ancho y alto de la burbuja

import re

# -- Geometría (unidades de camera.ui) --------------------------------------------------------------------------------
TELEFONO_ANCHO, TELEFONO_ALTO = 0.48, 0.92
TELEFONO_X = 0.26
BISEL_LADO, BISEL_ARRIBA, BISEL_ABAJO = 0.018, 0.035, 0.03
PANTALLA_ANCHO = TELEFONO_ANCHO - 2 * BISEL_LADO
PANTALLA_ALTO = TELEFONO_ALTO - BISEL_ARRIBA - BISEL_ABAJO
PANTALLA_Y = (BISEL_ABAJO - BISEL_ARRIBA) / 2           # centro de la pantalla respecto al centro del teléfono
ALTO_BARRA_ESTADO = 0.032
LATERAL_ANCHO, LATERAL_ALTO = 0.58, 0.80
LATERAL_X = TELEFONO_X - TELEFONO_ANCHO / 2 - 0.05 - LATERAL_ANCHO / 2
DURACION_TRANSICION = 0.25
MAX_ELEMENTOS = 7
MAX_CABECERA = 2
ELIPSIS = "…"

# Zonas que se dibujan como lista (en orden) dentro de su parte de la pantalla.
ZONAS_LISTA = ("cabecera", "texto", "ubicacion", "etiquetas", "contador", "fuente", "detalle")


def ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def rect_transicion(desde, hasta, p):
    """Rectángulo (x, y, ancho, alto) a mitad de camino entre `desde` y `hasta` con ease_in_out."""
    t = ease_in_out(p)
    return tuple(a + (b - a) * t for a, b in zip(desde, hasta))


def rect_telefono():
    return (TELEFONO_X, 0.0, TELEFONO_ANCHO, TELEFONO_ALTO)


def escala_de_rect(rect):
    """(x, y, escala) para dibujar el teléfono (construido a TELEFONO_ALTO) dentro de `rect` sin deformarlo."""
    x, y, ancho, alto = rect
    return x, y, max(1e-3, min(ancho / TELEFONO_ANCHO, alto / TELEFONO_ALTO))


def remitente_partido(remitente):
    """«+55 21 98871-0417 (no está en tus contactos)» -> («+55 21 98871-0417», «no está en tus contactos»)."""
    texto = " ".join(str(remitente or "").split())
    coincide = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", texto)
    if coincide and coincide.group(1):
        return coincide.group(1), coincide.group(2)
    return texto, ""


def inicial(nombre):
    for caracter in str(nombre or ""):
        if caracter.isalnum():
            return caracter.upper()
    return "?"


# -- Burbuja de chat ---------------------------------------------------------------------------------------------------

def _rangos(texto, fragmentos):
    """{numero: (inicio, fin)} de cada fragmento que aparece en `texto` (sin distinguir mayúsculas). Un fragmento que se
    solapa con otro ya encontrado no cuenta (cae en «Otros detalles»)."""
    bajo = texto.lower()
    rangos = {}
    for numero, fragmento in fragmentos:
        frag = " ".join(str(fragmento or "").split()).lower()
        if not frag:
            continue
        inicio = bajo.find(frag)
        if inicio < 0:
            continue
        fin = inicio + len(frag)
        if any(inicio < f and i < fin for i, f in rangos.values()):
            continue
        rangos[numero] = (inicio, fin)
    return rangos


CORTES = "/.-_?=&"          # dónde se prefiere partir una palabra larga (un enlace): justo después de uno de estos


def _palabras(texto, medir, ancho):
    """[(inicio, fin, palabra)]; una palabra más ancha que `ancho` se corta en trozos que sí caben, por un «/», «.» o
    «-» si se puede (un enlace se lee mejor así) y si no, por letras."""
    salida = []
    for m in re.finditer(r"\S+", texto):
        palabra, inicio = m.group(0), m.start()
        if medir(palabra) <= ancho:
            salida.append((inicio, m.end(), palabra))
            continue
        trozo_inicio = 0
        while trozo_inicio < len(palabra):
            fin = trozo_inicio + 1
            while fin < len(palabra) and medir(palabra[trozo_inicio:fin + 1]) <= ancho:
                fin += 1
            if fin < len(palabra):
                cortes = [k + 1 for k in range(trozo_inicio + 1, fin - 1) if palabra[k] in CORTES]
                if cortes:
                    fin = cortes[-1]
            salida.append((inicio + trozo_inicio, inicio + fin, palabra[trozo_inicio:fin]))
            trozo_inicio = fin
    return salida


def _recortar(texto, medir, ancho):
    if medir(texto + ELIPSIS) <= ancho:
        return texto + ELIPSIS
    while texto and medir(texto.rstrip() + ELIPSIS) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + ELIPSIS


def partir_burbuja(texto, fragmentos, medir, ancho, max_lineas=None):
    """Parte `texto` en líneas de hasta `ancho` y localiza los tramos marcables.

    `fragmentos`: [(numero, fragmento literal)]. Devuelve {"lineas": [{"texto", "tramos": [{"numero", "x", "ancho"}]}],
    "encontrados": [numeros con al menos un tramo visible], "recortado": bool}. Un fragmento que cruza el salto de línea
    da un tramo en cada línea (se resaltan las dos partes)."""
    texto = " ".join(str(texto or "").split())
    rangos = _rangos(texto, fragmentos)
    palabras = _palabras(texto, medir, ancho)
    grupos, actual = [], []
    for palabra in palabras:
        prueba = " ".join(p[2] for p in actual + [palabra])
        if actual and medir(prueba) > ancho:
            grupos.append(actual)
            actual = []
        actual.append(palabra)
    if actual:
        grupos.append(actual)
    recortado = False
    if max_lineas is not None and len(grupos) > max_lineas:
        recortado = True
        grupos = grupos[:max_lineas]

    def numero_de(inicio, fin):
        for numero, (i, f) in rangos.items():
            if inicio < f and i < fin:
                return numero
        return None

    lineas, encontrados = [], []
    for indice, grupo in enumerate(grupos):
        cadena = " ".join(p[2] for p in grupo)
        ultima_recortada = recortado and indice == len(grupos) - 1
        if ultima_recortada:
            cadena = _recortar(cadena, medir, ancho)
        tramos = []
        k = 0
        while k < len(grupo):
            numero = numero_de(grupo[k][0], grupo[k][1])
            if numero is None:
                k += 1
                continue
            j = k
            while j + 1 < len(grupo) and numero_de(grupo[j + 1][0], grupo[j + 1][1]) == numero:
                j += 1
            antes = " ".join(p[2] for p in grupo[:k])
            x = medir(antes + " ") if antes else 0.0
            ancho_tramo = medir(" ".join(p[2] for p in grupo[k:j + 1]))
            if not ultima_recortada or x + ancho_tramo <= medir(cadena):
                tramos.append({"numero": numero, "x": x, "ancho": ancho_tramo})
                if numero not in encontrados:
                    encontrados.append(numero)
            k = j + 1
        lineas.append({"texto": cadena, "tramos": tramos})
    return {"lineas": lineas, "encontrados": encontrados, "recortado": recortado}


def tamano_burbuja(anchos, alto_linea, relleno):
    """(ancho, alto) de una burbuja con líneas de `anchos` y su relleno a cada lado."""
    ancho = (max(anchos) if anchos else 0.0) + 2 * relleno
    return ancho, len(anchos) * alto_linea + 2 * relleno


# -- Zonas -------------------------------------------------------------------------------------------------------------

def plan_zonas(elementos, zonas):
    """Dónde va cada elemento. `elementos`: [{"id", "texto"}] en el orden de la bandeja (el número es el de las teclas
    1-n y el de control.marcar). `zonas`: {id: {"zona", "fragmento"?, "x"?, "y"?}} (lo que no está = detalle).

    Devuelve {"numeros": {numero: id}, "textos": {numero: texto}, "burbuja": [(numero, fragmento)] (tramos del texto
    principal: burbuja del DM o leyenda del muro), "foto": [(numero, x, y)],
    y una lista de números por cada zona de ZONAS_LISTA}. La cabecera admite MAX_CABECERA; el resto pasa a «detalle»."""
    plan = {"numeros": {}, "textos": {}, "burbuja": [], "foto": []}
    for zona in ZONAS_LISTA:
        plan[zona] = []
    for numero, elemento in enumerate(list(elementos)[:MAX_ELEMENTOS], start=1):
        plan["numeros"][numero] = elemento["id"]
        plan["textos"][numero] = elemento["texto"]
        zona = zonas.get(elemento["id"]) or {"zona": "detalle"}
        nombre = zona.get("zona", "detalle")
        # «texto» con fragmento es lo mismo que «burbuja»: un tramo del texto principal de la pantalla (leyenda del muro)
        if nombre in ("burbuja", "texto") and zona.get("fragmento"):
            plan["burbuja"].append((numero, zona["fragmento"]))
        elif nombre == "foto" and zona.get("x") is not None:
            plan["foto"].append((numero, zona["x"], zona["y"]))
        elif nombre == "cabecera" and len(plan["cabecera"]) < MAX_CABECERA:
            plan["cabecera"].append(numero)
        elif nombre in ZONAS_LISTA and nombre != "cabecera":
            plan[nombre].append(numero)
        else:
            plan["detalle"].append(numero)
    return plan


def completar_detalles(plan, encontrados):
    """Los fragmentos de burbuja que no se pudieron dibujar (no están en el texto o quedaron recortados) pasan a detalle,
    en orden de número. Devuelve la lista de detalle resultante (no modifica `plan`)."""
    faltan = [numero for numero, _f in plan["burbuja"] if numero not in encontrados]
    return sorted(plan["detalle"] + faltan)


# -- Scroll del panel lateral ------------------------------------------------------------------------------------------

def plan_scroll(alturas, visible, desplazamiento=0.0, separacion=0.0):
    """Filas apiladas hacia abajo dentro de una ventana de alto `visible`.

    Devuelve {"desplazamiento": recortado a [0, maximo], "maximo", "filas": [(indice, y_arriba)]} con solo las filas que
    caben ENTERAS en la ventana (y_arriba desde el borde superior, 0 = arriba, valores negativos hacia abajo)."""
    total = sum(alturas) + separacion * max(0, len(alturas) - 1)
    maximo = max(0.0, total - visible)
    desplazamiento = max(0.0, min(maximo, desplazamiento))
    filas, y = [], 0.0
    for indice, alto in enumerate(alturas):
        arriba = y - desplazamiento
        if arriba >= -1e-9 and arriba + alto <= visible + 1e-9:
            filas.append((indice, -arriba))
        y += alto + separacion
    return {"desplazamiento": desplazamiento, "maximo": maximo, "filas": filas}

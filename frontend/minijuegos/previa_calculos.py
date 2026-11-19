# Cálculos PUROS (sin ursina) de la pantalla previa: recorte de frases a pocas palabras y reparto de medidas.
# Los textos originales viven en backend/datos/minijuegos_instrucciones.py y no se tocan: aquí solo se acortan para la vista.

import re

MAX_PALABRAS_PASO = 8
MAX_PALABRAS_REDES = 24
MAX_CARACTERES_RUMOR = 150
ILUSTRACIONES = ("rastrear", "comparar", "cronologia", "chat", "senales", "contrarreloj")
GENERICA = "generica"

# Palabras que no pueden cerrar una frase recortada («...con el» queda colgando).
_COLGANTES = {"a", "al", "de", "del", "el", "la", "los", "las", "un", "una", "y", "o", "u", "e", "en", "con", "que", "si",
              "se", "su", "sus", "por", "para", "no", "es", "lo", "te", "tu"}
_FIN_CLAUSULA = ":;,"
_CONECTORES = {"y", "o", "si", "cuando", "porque"}


def _palabras(texto):
    return str(texto).split()


def _limpia_final(palabras):
    """Quita conectores y signos que quedarían colgando al final de un recorte."""
    while palabras and palabras[-1].strip(".,;:()«»¿¡").lower() in _COLGANTES | {""}:
        palabras = palabras[:-1]
    if not palabras:
        return ""
    texto = " ".join(palabras).rstrip(",;: ")
    return texto


def primera_oracion(texto):
    """Primera oración (hasta «. », «? » o «! » seguido de mayúscula o comilla). Sin puntos finales raros."""
    texto = " ".join(str(texto).split())
    partes = re.split(r"(?<=[.?!])\s+(?=[A-ZÁÉÍÓÚÑ«¿¡])", texto)
    return partes[0].strip() if partes and partes[0] else texto


def recortar_frase(frase, max_palabras=MAX_PALABRAS_PASO):
    """Frase de a lo sumo `max_palabras` palabras. Corta en el último límite de cláusula (coma, punto y coma, dos puntos)
    que quepa; si no hay, corta en seco y quita conectores colgantes. Siempre devuelve texto sin punto final largo."""
    oracion = primera_oracion(frase)
    palabras = _palabras(oracion)
    if len(palabras) <= max_palabras:
        return oracion.rstrip(" ;:,")
    mejor = None
    for i, p in enumerate(palabras[:max_palabras], start=1):
        if p[-1] in _FIN_CLAUSULA and i >= 3:
            mejor = i
    if mejor is not None:
        return _limpia_final(palabras[:mejor])
    corte = palabras[:max_palabras]
    # Si el recorte deja una sola palabra después de un conector («...izquierda y elige»), se corta antes del conector.
    for i in range(len(corte) - 2, 2, -1):
        if corte[i].lower() in _CONECTORES and len(corte) - i - 1 <= 1:
            return _limpia_final(corte[:i])
        if len(corte) - i - 1 > 1:
            break
    return _limpia_final(corte)


# Versiones cortas ESCRITAS A MANO de los pasos conocidos: cortar en seco deja frases colgando («...Con las flechas arriba y
# abajo eliges»). Si el paso no está aquí (texto nuevo o editado), se usa el recorte automático de siempre.
PASOS_CORTOS = {
    "En cada paso verás tres mensajes: quién lo mandó, a qué hora y qué dice.": "Verás tres mensajes: quién, cuándo y qué dice.",
    "Elige el más ANTIGUO que no diga «reenviado»: ese es el eslabón anterior de la cadena.": "Elige el más ANTIGUO que no diga «reenviado».",
    "Cada error es un rodeo. Con demasiados rodeos pierdes el rastro.": "Cada error es un rodeo: pierdes el rastro.",
    "Compara cada línea de la copia (derecha) con la misma línea del original (izquierda).": "Compara cada línea con el original.",
    "Marca las líneas alteradas; puedes desmarcarlas si te equivocas.": "Marca las líneas alteradas; puedes desmarcar.",
    "Pulsa «Confirmar marcas», o «No veo diferencias» si crees que la copia es fiel.": "Pulsa «Confirmar marcas» o «No veo diferencias».",
    "Arriba va lo que se dijo primero y abajo lo último: fíjate en el día y la hora.": "Arriba lo primero, abajo lo último.",
    "Agarra un mensaje (Enter o clic), súbelo o bájalo y vuelve a pulsar para soltarlo.": "Agarra un mensaje, súbelo o bájalo y suéltalo.",
    "Cuando creas que está en orden, pulsa «Comprobar el orden».": "Si está en orden, pulsa «Comprobar el orden».",
    "Lee el chat de la izquierda y elige una de las tres respuestas de la derecha.": "Lee el chat y elige una respuesta.",
    "La presión del grupo sube con el tiempo: si tardas demasiado, te quedas en visto.": "La presión sube: tardas y quedas en visto.",
    "Piensa qué datos entregas con cada respuesta, no cuál te saca más rápido del apuro.": "Piensa qué datos entregas con cada respuesta.",
    "Recorre las zonas de la captura: la lupa de la derecha te dice qué estás mirando.": "Recorre las zonas; la lupa te guía.",
    "Marca hasta tres zonas sospechosas: cuenta rara, hora imposible, premio a cambio de reenviar...": "Marca hasta tres zonas sospechosas.",
    "Confirma tus marcas, o pulsa «No veo nada raro» si crees que es auténtica.": "Confirma, o pulsa «No veo nada raro».",
    "FRENA lo que creas falso y DEJA PASAR lo que creas cierto.": "FRENA lo falso; DEJA PASAR lo cierto.",
    "La barra de cada noticia muestra cuánto se difundió: si se llena antes de que decidas, no cuenta.": "La barra muestra cuánto se difundió cada noticia.",
    "Con las flechas arriba y abajo eliges la noticia.": "Con flechas arriba y abajo eliges la noticia.",
}


def recortar_pasos(pasos, n=3, max_palabras=MAX_PALABRAS_PASO):
    """Los `n` primeros pasos recortados (lista de str; nunca vacía por paso si había texto)."""
    salida = []
    for p in list(pasos or ())[:n]:
        curado = PASOS_CORTOS.get(" ".join(str(p).split()))
        if curado and len(curado.split()) <= max_palabras:
            if len(_palabras(curado)) > max_palabras:          # la versión curada también respeta el límite
                curado = recortar_frase(curado, max_palabras) or " ".join(_palabras(curado)[:max_palabras])
            salida.append(curado)
            continue
        corto = recortar_frase(p, max_palabras)
        salida.append(corto or " ".join(_palabras(p)[:max_palabras]))
    return salida


def frase_redes(redes, max_palabras=MAX_PALABRAS_REDES):
    """El hábito de redes como UNA frase para el post-it."""
    return recortar_frase(redes, max_palabras) if redes else ""


def recortar_rumor(rumor, max_caracteres=MAX_CARACTERES_RUMOR):
    """Rumor para el recorte de periódico: una sola línea de texto, con «...» si se corta."""
    texto = " ".join(str(rumor or "").split())
    if len(texto) <= max_caracteres:
        return texto
    corte = texto[:max_caracteres].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return corte + "..."


def ilustracion_de(minijuego_id):
    """Nombre de la ilustración del minijuego; los ids desconocidos o ausentes usan la genérica."""
    return minijuego_id if minijuego_id in ILUSTRACIONES else GENERICA


def repartir(ancho_util, corta=False, ancho_ilustracion=0.5, separacion=0.05, n_pasos=3, hueco_pasos=0.025):
    """Reparto horizontal: ilustración a la izquierda y, a la derecha, recorte, pasos y post-it.
    Devuelve dict con x0, ancho_ilustracion, x_derecha, ancho_derecha, ancho_paso (por columna) y n_pasos."""
    x0 = -ancho_util / 2
    x_derecha = x0 + ancho_ilustracion + separacion
    ancho_derecha = ancho_util - ancho_ilustracion - separacion
    n = max(1, n_pasos)
    ancho_paso = (ancho_derecha - (n - 1) * hueco_pasos) / n
    return {"x0": x0, "ancho_ilustracion": ancho_ilustracion, "x_derecha": x_derecha, "ancho_derecha": ancho_derecha,
            "ancho_paso": ancho_paso, "hueco_pasos": hueco_pasos, "n_pasos": n, "con_pasos": not corta}


def y_botones(y_fin_columna, alto, y_defecto=-0.397, separacion=0.045, y_min=-0.405):
    """Centro vertical de la fila «Empezar» / «Ver tutorial»: justo bajo el último bloque de la columna de texto (`y_fin_columna`,
    borde inferior) con `separacion`, sin bajar de `y_min`. Sin dato de columna: `y_defecto`."""
    if y_fin_columna is None:
        return y_defecto
    return max(y_min, float(y_fin_columna) - separacion - alto / 2)

# Cálculos puros (sin ursina) del panel de dilemas: cómo se REDACTA cada opción y cada resultado. Regla de diseño del plan
# final: consecuencias visibles, no números. La pantalla del dilema nunca enseña un indicador ni una cifra: cada opción dice
# en lenguaje natural qué se nota AHORA (lo que se ve en el momento) y un pie avisa de que lo demás llega en uno o dos días.
# Lo retardado NO se adelanta: si se escribiera aquí, la mejor opción dejaría de ser un dilema.
#
#   pista_inmediata(deltas, confianza)  -> «Ahora: un poco más de convivencia; algo menos de confianza en la ciudad.»
#   contenido_dilema(oferta)            -> dict para dibujar la pregunta (título, situación, opciones con tecla y pista, pie)
#   contenido_resultado(resultado)      -> dict para dibujar lo que pasó al elegir (el texto del efecto inmediato; el resto llega solo, como aviso)

# Cuánto pesa un delta en palabras (valor absoluto): hasta 1 «un poco», hasta 3 «algo», más «bastante».
CUANTIAS = ((1.0, "un poco"), (3.0, "algo"), (float("inf"), "bastante"))

# (nombre, signo) -> frase tras la cuantía. Para indicadores de la ciudad y para la confianza por grupo.
FRASES = {
    ("convivencia", 1): "más de convivencia en el barrio", ("convivencia", -1): "menos de convivencia en el barrio",
    ("confianza", 1): "más de confianza en la ciudad", ("confianza", -1): "menos de confianza en la ciudad",
    ("desinformacion", 1): "más de rumores sueltos", ("desinformacion", -1): "menos de rumores sueltos",
    ("ciudadanos", 1): "mejor con los vecinos", ("ciudadanos", -1): "peor con los vecinos",
    ("policia", 1): "mejor con la policía", ("policia", -1): "peor con la policía",
    ("instituciones", 1): "mejor con las instituciones", ("instituciones", -1): "peor con las instituciones",
}
# Para la desinformación, «más» es malo: el orden «lo bueno primero» la trata al revés.
_MALO_SI_SUBE = ("desinformacion",)

TITULO_RESULTADO = "Lo que pasó"
PIE_DECISION = "1-3 o clic: elegir  ·  Esc: decidir más tarde"
PIE_RESULTADO = "E / Intro: continuar"
AVISO_RETARDO = "Lo que elijas puede traer consecuencias en uno o dos días."
SIN_CAMBIOS = "casi nada cambia a la vista"
CHIP_PENDIENTE = "K  ·  Mensaje sin responder"


def cuantia(valor):
    magnitud = abs(valor)
    return next(texto for limite, texto in CUANTIAS if magnitud <= limite)


def _es_bueno(nombre, signo):
    return signo < 0 if nombre in _MALO_SI_SUBE else signo > 0


# Frases de un efecto inmediato (indicadores + grupos), lo bueno primero. Lista de textos sin cifras.
def frases(deltas, confianza=None):
    partes = []
    for nombre, valor in list((deltas or {}).items()) + list((confianza or {}).items()):
        if not valor:
            continue
        signo = 1 if valor > 0 else -1
        frase = FRASES.get((nombre, signo))
        if frase is not None:
            partes.append((not _es_bueno(nombre, signo), f"{cuantia(valor)} {frase}"))
    return [texto for _, texto in sorted(partes, key=lambda p: p[0])]


def pista_inmediata(deltas, confianza=None):
    partes = frases(deltas, confianza)
    return "Ahora: " + ("; ".join(partes) if partes else SIN_CAMBIOS) + "."


def contenido_dilema(oferta):
    """Lo que dibuja el panel para una oferta de FlujoConDilemas.dilema_pendiente(). Sin cifras ni nombres de indicador."""
    opciones = [{"tecla": str(i), "id": o["id"], "etiqueta": o["etiqueta"],
                 "pista": pista_inmediata(o.get("deltas"), o.get("confianza"))}
                for i, o in enumerate(oferta["opciones"], start=1)]
    return {"id": oferta["id"], "titulo": oferta["titulo"], "situacion": oferta["situacion"], "opciones": opciones,
            "aviso": AVISO_RETARDO, "pie": PIE_DECISION}


def contenido_resultado(resultado):
    return {"titulo": TITULO_RESULTADO, "texto": resultado["texto"], "pie": PIE_RESULTADO}

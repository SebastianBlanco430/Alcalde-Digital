# Qué minijuego juega cada misión de «verificar» (datos puros). El dueño edita backend/datos/misiones_semilla.py a mano; el mapeo
# misión -> minijuego vive AQUÍ, aparte, para no tocar ese archivo.
#
# Orden de decisión de asignar(mision):
#   1. ASIGNACION_POR_ID: la lista explícita (las 14 misiones del catálogo).
#   2. Por TEMA del rumor (palabras clave de su texto): foto/video/audio -> comparar, premios/cupones/encuestas -> señales, datos
#      personales -> chat, salud/seguridad urgente -> contrarreloj, fechas y horarios -> cronología.
#   3. Por GRUPO de confianza y DIFICULTAD: instituciones -> rastrear, policía -> contrarreloj, ciudadanos -> cronología.
#   4. Respaldo: ACTUAL («juego», el lote de noticias de siempre).
# Una asignación a un minijuego que no esté en `habilitados` (o a una misión que no es de verificar) cae al respaldo.

from backend.logica import minijuegos as mj

ASIGNACION_POR_ID = {
    # -- Rastrear la fuente: rumores de instituciones, normas y cifras oficiales --
    "periodista_prefeitura": mj.RASTREAR,
    "candidato_morro": mj.RASTREAR,
    "candidato_mercado": mj.RASTREAR,
    "generica_universidade": mj.RASTREAR,
    # -- Comparar versiones: fotos, videos, audios, carteles y volantes que circulan --
    "periodista_radio": mj.COMPARAR,
    "ciudadano_teleferico": mj.COMPARAR,
    # -- Ordenar la cadena: eventos, horarios y fechas --
    "ciudadano_praca": mj.CRONOLOGIA,
    "generica_rodoviaria": mj.CRONOLOGIA,
    "influencer_samba": mj.CRONOLOGIA,
    "generica_feira": mj.CRONOLOGIA,
    # -- Chat del barrio: piden datos, cuentas, cuotas (dilema entre ayudar y proteger a un amigo) --
    "generica_mutirao": mj.CHAT,
    # -- Señales de edición: cadenas, cupones, capturas con premios y encuestas --
    "generica_corrente": mj.SENALES,
    # -- Contrarreloj: salud, seguridad y servicios que se propagan rápido --
    "influencer_parque": mj.CONTRARRELOJ,
    "generica_santa_casa": mj.CONTRARRELOJ,
}

# Tema del rumor -> palabras clave (en minúsculas) que lo delatan en `mision.rumor`. El orden importa: gana el primero que case.
TEMAS = (
    ("imagen", ("foto", "video", "audio", "imagen", "captura")),
    ("estafa", ("cadena", "premio", "cupón", "descuento", "encuesta", "ganador", "reto")),
    ("datos", ("cuenta", "documento", "teléfono", "número", "cuota", "exigen", "exige")),
    ("salud", ("salud", "sanitaria", "brote", "vacuna", "enferm", "suero", "hospital", "tinte", "aditivos")),
    ("seguridad", ("seguridad", "ladrones", "evacuaron", "incidentes", "agentes", "guardia", "desalojar", "luces")),
    ("dinero", ("precio", "cobra", "pagan", "triple", "doble", "impuesto", "subir", "despedir")),
    ("evento", ("viernes", "sábado", "domingo", "lunes", "mañana", "horas", "ensayos", "concierto", "feria", "sorteo",
                "clases", "oferta", "hornea", "atiende")),
    ("politica", ("alcaldía", "prefeitura", "licitó", "autoridades", "candidato", "voten", "elección")),
)

# Tema -> minijuego cuando la misión no está en la lista explícita.
MINIJUEGO_POR_TEMA = {
    "imagen": mj.COMPARAR,
    "estafa": mj.SENALES,
    "datos": mj.CHAT,
    "salud": mj.CONTRARRELOJ,
    "seguridad": mj.CONTRARRELOJ,
    "dinero": mj.SENALES,
    "evento": mj.CRONOLOGIA,
    "politica": mj.RASTREAR,
}

MINIJUEGO_POR_GRUPO = {"instituciones": mj.RASTREAR, "policia": mj.CONTRARRELOJ, "ciudadanos": mj.CRONOLOGIA}


# Minijuegos cuyo caso busca una ALTERACIÓN (la captura o la copia están manipuladas): solo tienen sentido con un rumor falso.
SOLO_FALSAS = (mj.COMPARAR, mj.SENALES)


def tema_de(mision):
    """Tema del rumor ("imagen", "estafa", "datos", "salud", "seguridad", "dinero", "evento", "politica") o "general"."""
    texto = (getattr(mision, "rumor", "") or "").lower()
    for tema, claves in TEMAS:
        if any(clave in texto for clave in claves):
            return tema
    return "general"


def _es_de_verificar(mision):
    return (getattr(mision, "tipo", "verificar") == "verificar"
            and isinstance(getattr(mision, "es_verdadera", None), bool))


def asignar(mision, habilitados=mj.IDS):
    """Id del minijuego de la misión (uno de mj.IDS) o mj.ACTUAL si no aplica o no está habilitado."""
    if mision is None or not _es_de_verificar(mision):
        return mj.ACTUAL
    elegido = ASIGNACION_POR_ID.get(mision.id)
    if elegido is None:
        elegido = MINIJUEGO_POR_TEMA.get(tema_de(mision))
    if elegido is None:
        elegido = MINIJUEGO_POR_GRUPO.get(getattr(mision, "grupo", ""))
    if elegido in SOLO_FALSAS and mision.es_verdadera:
        elegido = mj.RASTREAR          # estos dos buscan una alteración: con un rumor verdadero no hay nada que encontrar
    return elegido if elegido in habilitados else mj.ACTUAL

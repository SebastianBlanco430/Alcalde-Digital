# Cálculos puros (sin ursina) del panel de la bandeja de Civitas (frontend/registro_habitos.py): cómo se REDACTA cada fase.
# Misma regla que los dilemas: nada de cifras de indicadores en pantalla. Lo que sí se ve es el dinero (es del jugador), el
# tiempo de pantalla (es el punto) y, al final, la revisión de cada elemento con su explicación: ahí está lo que se aprende.
#
# Accesibilidad: nada depende solo del color. Las marcas son «[x]» / «[ ]» y la revisión dice «[OK]» o «[!]». Sin emojis ni
# flechas: la fuente del juego no los tiene (salen como un cuadro vacío).
#
#   contenido_marcar(evento, marcas)     -> dict de la fase de marcar (título, remitente, texto, filas con su marca, pie)
#   contenido_decidir(evento, marcas)    -> dict de la fase de decidir (opciones con tecla)
#   contenido_revision(resultado)        -> dict de lo que pasó y la revisión elemento por elemento
#   contenido_feed(publicacion)          -> dict de una publicación del feed (con el contador del día)
#   texto_minutos(minutos)               -> «1 h 12 min»

CHIP_PENDIENTE = "L  ·  Civitas: mensaje nuevo"
TITULO_REVISION = "Lo que pasó"
TITULO_FEED = "Civitas · Para ti"
MARCA_SI = "[x]"
MARCA_NO = "[ ]"
MAX_ELEMENTOS = 7

INSTRUCCION = {
    "estafa": "Marca lo que te parece sospechoso antes de decidir.",
    "publicar": "Marca lo que vas a TAPAR antes de publicar.",
}
PIE_MARCAR = "1-{n} o clic: marcar  ·  Intro: decidir  ·  Esc: más tarde"
PIE_DECIDIR = "1-{n} o clic: elegir  ·  Retroceso: volver a marcar  ·  Esc: más tarde"
PIE_REVISION = "E / Intro: continuar"
PIE_FEED = "Espacio o flecha abajo: siguiente publicación  ·  Esc: dejar el celular"
AVISO_FEED = "Cada publicación se come unos minutos de la semana y te cansa un poco."
INTRO_FEED = "Tu feed de Civitas. Siempre hay algo más abajo."


def texto_minutos(minutos):
    minutos = max(0, int(round(minutos)))
    horas, resto = divmod(minutos, 60)
    if horas == 0:
        return f"{resto} min"
    return f"{horas} h {resto:02d} min" if resto else f"{horas} h"


def contenido_marcar(evento, marcas):
    marcas = set(marcas or ())
    filas = [{"tecla": str(i), "id": e["id"], "marcado": e["id"] in marcas,
              "texto": f"{i}  {MARCA_SI if e['id'] in marcas else MARCA_NO}  {e['texto']}"}
             for i, e in enumerate(evento["elementos"][:MAX_ELEMENTOS], start=1)]
    return {"fase": "marcar", "titulo": evento["titulo"], "remitente": f"De: {evento['remitente']}",
            "texto": evento["texto"], "instruccion": INSTRUCCION.get(evento["tipo"], ""), "filas": filas,
            "pie": PIE_MARCAR.format(n=len(filas)), "hasta": f"Responde antes de: {evento['hasta_texto']}"}


def contenido_decidir(evento, marcas):
    marcadas = len(set(marcas or ()) & {e["id"] for e in evento["elementos"]})
    verbo = "tapas" if evento["tipo"] == "publicar" else "marcaste como sospechosos"
    opciones = [{"tecla": str(i), "id": o["id"], "texto": f"{i}   {o['etiqueta']}"}
                for i, o in enumerate(evento["opciones"], start=1)]
    return {"fase": "decidir", "titulo": evento["titulo"], "remitente": f"De: {evento['remitente']}",
            "texto": evento["texto"], "instruccion": f"Elementos que {verbo}: {marcadas} de {len(evento['elementos'])}.",
            "opciones": opciones, "pie": PIE_DECIDIR.format(n=len(opciones))}


def _linea_revision(fila):
    marca = "[OK]" if fila["acertado"] else "[!]"
    return f"{marca} {fila['texto']}: {fila['explicacion']}"


def contenido_revision(resultado):
    texto = resultado["texto"]
    if resultado.get("perdida"):
        texto = texto if f"R$ {resultado['perdida']}" in texto else f"{texto} (-R$ {resultado['perdida']})"
    if resultado.get("llega"):
        texto += " Lo demás se verá en uno o dos días."
    filas = [{"texto": _linea_revision(f), "acertado": f["acertado"]} for f in resultado["revision"][:MAX_ELEMENTOS]]
    bien = sum(1 for f in resultado["revision"] if f["acertado"])
    return {"fase": "revision", "titulo": TITULO_REVISION, "texto": texto, "filas": filas,
            "resumen": f"Juzgaste bien {bien} de {len(resultado['revision'])} elementos.", "pie": PIE_REVISION}


def contenido_feed(publicacion=None, minutos_hoy=0):
    if publicacion is None:
        return {"fase": "feed", "titulo": TITULO_FEED, "texto": INTRO_FEED, "pista": False,
                "contador": f"Hoy en Civitas: {texto_minutos(minutos_hoy)}", "aviso": AVISO_FEED, "pie": PIE_FEED}
    texto = ("[Pista] " if publicacion["pista"] else "") + publicacion["texto"]
    return {"fase": "feed", "titulo": TITULO_FEED, "texto": texto, "pista": publicacion["pista"],
            "contador": f"Hoy en Civitas: {texto_minutos(publicacion['minutos_hoy'])}  ·  {publicacion['hora_texto']}",
            "aviso": AVISO_FEED, "pie": PIE_FEED}

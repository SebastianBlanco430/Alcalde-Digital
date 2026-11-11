# Textos de los tres finales de la partida (datos puros; el frontend solo los pinta). El final lo decide
# backend/logica/confianza_misiones.evaluar_final a partir de la confianza de los tres grupos de Ciudad Nova.
# Perder es un final válido: no hay «game over», solo una ciudad que quedó de otra manera.
#
# Uso desde la vista:
#   final = flujo.final_partida()                    # dict de evaluar_final, o None sin consecuencias
#   textos = finales_textos.texto_final(final["final"])   # {"titulo", "texto"}
#   lineas = finales_textos.lineas_resumen(final)    # «Misiones acertadas: 9 · falladas: 5», «Policía: 60»...

FINALES_TEXTOS = {
    "bueno": {
        "titulo": "Ciudad Nova confía",
        "texto": (
            "La campaña termina y Civitas amanece más tranquila. Los rumores siguieron circulando, pero casi siempre "
            "hubo alguien que fue a mirar antes de compartir. La policía, los vecinos y las instituciones saben que "
            "pueden creer en lo que se publica, y el día de la elección Ciudad Nova vota informada. Gane quien gane, "
            "el nuevo alcalde recibe una ciudad que aprendió a comprobar antes de creer."
        ),
    },
    "neutro": {
        "titulo": "Ciudad Nova duda",
        "texto": (
            "La campaña termina con la ciudad partida en dos. Algunos bulos se frenaron a tiempo y otros corrieron "
            "más rápido que su desmentido. En Civitas ya nadie sabe del todo a quién creerle: unos vecinos confían, "
            "otros prefieren callar. Ciudad Nova llega a la elección con más preguntas que certezas, y el próximo "
            "alcalde tendrá que ganarse, paso a paso, la confianza que quedó a medias."
        ),
    },
    "malo": {
        "titulo": "Ciudad Nova desconfía",
        "texto": (
            "La campaña termina y en Civitas manda el rumor. Lo que era mentira se compartió como cierto, y lo "
            "que era cierto se denunció como mentira. La policía, los vecinos y las instituciones dejaron de creerse "
            "entre sí, y el día de la elección muchos se quedan en casa. Ciudad Nova tendrá alcalde, pero le tocará "
            "gobernar una ciudad que ya no sabe en qué creer. Recuperar esa confianza será la primera tarea."
        ),
    },
}

# Nombre visible de cada grupo de confianza, en el orden en que se muestran.
NOMBRES_GRUPOS = {"policia": "Policía", "ciudadanos": "Ciudadanos", "instituciones": "Instituciones"}


# {"titulo", "texto"} del final ("bueno" | "neutro" | "malo"). ValueError con otra clave.
def texto_final(clave):
    if clave not in FINALES_TEXTOS:
        raise ValueError(f"Final desconocido: {clave!r}; válidos: {tuple(FINALES_TEXTOS)}.")
    return dict(FINALES_TEXTOS[clave])


# Líneas del resumen listas para pintar, a partir del dict de confianza_misiones.evaluar_final: la primera con las
# misiones acertadas y falladas, y una por grupo con su confianza (entero, redondeo normal).
def lineas_resumen(final):
    lineas = [f"Misiones acertadas: {final['pasadas']} · falladas: {final['falladas']}"]
    for grupo, nombre in NOMBRES_GRUPOS.items():
        lineas.append(f"{nombre}: {int(final['confianza'][grupo] + 0.5)}")
    return lineas

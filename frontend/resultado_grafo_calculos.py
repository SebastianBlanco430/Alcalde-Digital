# Cálculos puros (SIN ursina) de la pantalla «Resultado de la misión»: el estado FINAL
# acumulado del grafo social tras TODAS las propagaciones de la misión, los textos del
# resumen y del mensaje de cierre, la leyenda y el tiempo de la animación.
# frontend/panel_resultado_grafo.py solo dibuja lo que se calcula aquí.
#
# Entrada: lista de propagaciones COMPLETAS (con "niveles") tal como las guarda
# LoteMision.propagaciones_con_niveles(): {"origen", "accion", "niveles", "alcance"}.

from frontend import estilo, grafo_social_vista as vista

# Colores (RGB 0-255) de los saltos: misma paleta que el panel pequeño de alcance.
COLOR_ORIGEN = estilo.COLOR_DESTINO                       # amarillo: quien publica
COLORES_SALTO = {1: estilo.COLOR_RUTA, 2: (80, 190, 110)}  # cian, verde
COLOR_SALTO_LEJANO = (235, 140, 60)                       # saltos 3 o más
COLOR_SIN_RECIBIR = estilo.COLOR_BARRA_FONDO              # gris: nunca la recibió
COLOR_FRENADO = estilo.COLOR_BARRA_BAJO                   # origen cuando solo se reportó
COLOR_INFLUYENTE = (255, 200, 80)                         # aro dorado
COLOR_AISLADO = estilo.COLOR_BARRA_BAJO                   # aro rojo
COLOR_ARISTA_INACTIVA = (70, 74, 100)

NODO_ORIGEN = "origen"
NODO_FRENADO = "frenado"
NODO_ALCANZADO = "alcanzado"
NODO_PENDIENTE = "pendiente"      # aún no le llega (animación) o nunca le llegó (final)


# Color de un nodo alcanzado en el salto `salto` (0 = origen).
def color_del_salto(salto):
    if salto <= 0:
        return COLOR_ORIGEN
    return COLORES_SALTO.get(salto, COLOR_SALTO_LEJANO)


# Estado final acumulado del grafo tras todas las `propagaciones` de la misión.
# Retorna un dict JSON-serializable:
#   total, origen (None si no hubo propagaciones), compartidas, reportadas, decisiones,
#   salto_minimo {ciudadano: salto más temprano en que lo alcanzó una publicación; el origen es 0},
#   veces {ciudadano: cuántas publicaciones compartidas lo alcanzaron (el origen: todas)},
#   recibieron [ciudadanos que SÍ la recibieron, sin el origen], sin_recibir [los demás sin el origen],
#   alcance_total (suma de los alcances), porcentaje (0-100, redondeado; sin el origen, igual que el
#   panel pequeño), saltos_max, aislados [sin camino desde el origen], influyentes {ciudadano: grado}.
def estado_acumulado(grafo_social, propagaciones):
    nombres = grafo_social.ciudadanos()
    total = len(nombres)
    compartidas = [p for p in propagaciones if p["accion"] == "compartir"]
    reportadas = [p for p in propagaciones if p["accion"] == "reportar"]
    origen = propagaciones[0]["origen"] if propagaciones else None

    salto_minimo = {}
    veces = {}
    for propagacion in compartidas:
        if propagacion["origen"] not in nombres:
            continue
        for nombre, salto in vista.saltos_por_ciudadano(propagacion).items():
            veces[nombre] = veces.get(nombre, 0) + 1
            if nombre not in salto_minimo or salto < salto_minimo[nombre]:
                salto_minimo[nombre] = salto

    recibieron = [n for n in nombres if n in salto_minimo and n != origen]
    sin_recibir = [n for n in nombres if n not in salto_minimo and n != origen]
    return {
        "total": total,
        "origen": origen,
        "compartidas": len(compartidas),
        "reportadas": len(reportadas),
        "decisiones": len(compartidas) + len(reportadas),
        "salto_minimo": salto_minimo,
        "veces": veces,
        "recibieron": recibieron,
        "sin_recibir": sin_recibir,
        "alcance_total": sum(p["alcance"] for p in propagaciones),
        "porcentaje": round(100 * len(recibieron) / total) if total > 0 else 0,
        "saltos_max": max((len(p["niveles"]) for p in compartidas), default=0),
        "aislados": vista.aislados(grafo_social, origen) if origen is not None else [],
        "influyentes": vista.influyentes(grafo_social),
    }


# -- Animación (nodos que se encienden por salto) -------------------------------------

# Segundos que dura la animación completa: un PASO (grafo_social_vista.PASO_SEGUNDOS) por salto.
def duracion_animacion(estado):
    return estado["saltos_max"] * vista.PASO_SEGUNDOS


# Salto ya encendido en el instante `t` (0 = solo el origen), acotado al último salto.
def salto_en(estado, t):
    if t <= 0:
        return 0
    return min(estado["saltos_max"], int(t / vista.PASO_SEGUNDOS + 1e-9))


# ¿Terminó la animación en `t`? (sin saltos: terminada desde el inicio).
def animacion_terminada(estado, t):
    return t >= duracion_animacion(estado) - 1e-9


# Estado de un ciudadano cuando ya se encendieron `salto` saltos.
def estado_nodo(estado, nombre, salto):
    if nombre == estado["origen"]:
        return NODO_ORIGEN if estado["compartidas"] > 0 else NODO_FRENADO
    minimo = estado["salto_minimo"].get(nombre)
    if minimo is not None and minimo <= salto:
        return NODO_ALCANZADO
    return NODO_PENDIENTE


# Color RGB del nodo según su estado en el salto `salto`.
def color_nodo(estado, nombre, salto):
    situacion = estado_nodo(estado, nombre, salto)
    if situacion == NODO_ORIGEN:
        return COLOR_ORIGEN
    if situacion == NODO_FRENADO:
        return COLOR_FRENADO
    if situacion == NODO_ALCANZADO:
        return color_del_salto(estado["salto_minimo"][nombre])
    return COLOR_SIN_RECIBIR


# Salto en que se enciende cada arista (el mayor de sus dos extremos) o None si no se enciende
# (algún extremo nunca recibió la publicación). Solo cuenta si el salto ya se alcanzó.
def salto_de_arista(estado, a, b, salto):
    minimos = estado["salto_minimo"]
    if a not in minimos or b not in minimos:
        return None
    encendida = max(minimos[a], minimos[b])
    return encendida if encendida <= salto else None


# Veces mínimas que la publicación pasó por ambos extremos de una arista (grosor de la línea).
def veces_de_arista(estado, a, b):
    return min(estado["veces"].get(a, 0), estado["veces"].get(b, 0))


# Grosor de una arista encendida: crece un poco con las veces, con tope.
def grosor_arista(veces, base, extra, tope=4):
    return base + extra * (max(1, min(veces, tope)) - 1)


# -- Layout ------------------------------------------------------------------------

# Escala las posiciones del grafo en [-1, 1] a un rectángulo de medio ancho/alto dados,
# centrado en (cx, cy). Resultado {nombre: (x, y)}.
def puntos_en_rectangulo(posiciones, medio_ancho, medio_alto, centro=(0.0, 0.0)):
    cx, cy = centro
    return {n: (cx + x * medio_ancho, cy + y * medio_alto) for n, (x, y) in posiciones.items()}


# Dónde va la etiqueta (nombre) de un ciudadano, según su posición normalizada (x, y) en [-1, 1]:
# bajo el nodo, salvo en los bordes (|x| > 0.7 o |y| > 0.9), donde va al lado y hacia afuera para no
# salirse de la tarjeta ni chocar con los nodos de la fila de abajo.
def lado_etiqueta(x_normalizada, y_normalizada):
    if abs(y_normalizada) > 0.9 or abs(x_normalizada) > 0.7:
        return "izquierda" if x_normalizada < 0 else "derecha"
    return "abajo"


# -- Textos ------------------------------------------------------------------------

# "+8" / "-3" / "0" con el signo siempre explícito (el menos es el guion normal).
def texto_delta(valor):
    if valor > 0:
        return f"+{valor}"
    return str(valor)


# Color del cambio de un indicador: verde si mejora, rojo si empeora, tenue si no cambia.
# Convivencia y confianza mejoran al subir; la desinformación mejora al bajar.
def color_delta(indicador, valor):
    if valor == 0:
        return estilo.COLOR_TEXTO_TENUE
    mejora = valor < 0 if indicador == "desinformacion" else valor > 0
    return estilo.COLOR_BARRA_ALTO if mejora else estilo.COLOR_BARRA_BAJO


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


# Nombres separados por coma ("Ana, Beto y Carlos" -> con "y" final); "ninguno" si no hay. Con más de `maximo`
# (con el grafo de 17 ciudadanos una comunidad aislada puede tener 12) se acorta: "Ana, Beto, Carlos y 9 más".
def lista_nombres(nombres, maximo=4):
    nombres = list(nombres)
    if not nombres:
        return "ninguno"
    if len(nombres) == 1:
        return nombres[0]
    if len(nombres) > maximo:
        return ", ".join(nombres[:maximo - 1]) + f" y {len(nombres) - maximo + 1} más"
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


# Líneas del resumen: [(etiqueta, valor)] en el orden en que se muestran.
def lineas_resumen(estado):
    decisiones = estado["decisiones"]
    detalle = f"{_plural(estado['compartidas'], 'compartida', 'compartidas')}, " \
              f"{_plural(estado['reportadas'], 'reportada', 'reportadas')}"
    recibieron = len(estado["recibieron"])
    influyentes = ", ".join(f"{n} ({g})" for n, g in estado["influyentes"].items()) or "ninguno"
    return [
        ("Decisiones", f"{decisiones} ({detalle})"),
        ("Alcance total", f"{estado['alcance_total']} (suma de las propagaciones)"),
        ("Red alcanzada", f"{estado['porcentaje']}% ({recibieron} de {estado['total']})"),
        ("Aislados", lista_nombres(estado["aislados"])),
        ("Influyentes", influyentes),
    ]


# Mensaje de cierre según lo decidido y cómo cambiaron la desinformación y la confianza (`deltas`).
def mensaje_cierre(estado, deltas):
    compartidas, reportadas = estado["compartidas"], estado["reportadas"]
    des = deltas.get("desinformacion", 0)
    confianza = deltas.get("confianza", 0)
    if estado["decisiones"] == 0:
        return "No tomaste decisiones en esta misión."
    if des > 0:
        efecto = "La desinformación creció."
    elif des < 0:
        efecto = "La desinformación bajó."
    else:
        efecto = "La desinformación no cambió."
    pct = estado["porcentaje"]
    if reportadas == 0:
        return (f"Compartiste todas las noticias y llegaron al {pct}% de la red. "
                f"{efecto} Lo que se comparte se expande por los contactos.")
    if compartidas == 0:
        cierre = ("Reportar frena la desinformación antes de que se propague." if des < 0 else
                  "Reportar una noticia verdadera resta confianza." if confianza < 0 else
                  "Reportar frena la propagación.")
        return f"Reportaste todas las noticias y ninguna salió de tu círculo. {efecto} {cierre}"
    return (f"Compartiste {_plural(compartidas, 'noticia', 'noticias')} (llegaron al {pct}% de la red) "
            f"y reportaste {reportadas}. {efecto} Cada decisión cuenta: compartir expande, reportar frena.")


# Leyenda: [(clave, texto, rgb, tipo)] con tipo "relleno" (círculo de color) o "aro".
def leyenda():
    return [
        ("origen", "Origen", COLOR_ORIGEN, "relleno"),
        ("salto1", "1.er salto", COLORES_SALTO[1], "relleno"),
        ("salto2", "2.º salto", COLORES_SALTO[2], "relleno"),
        ("salto3", "3.º o más", COLOR_SALTO_LEJANO, "relleno"),
        ("sin_recibir", "No la recibió", COLOR_SIN_RECIBIR, "relleno"),
        ("influyente", "Muy conectado", COLOR_INFLUYENTE, "aro"),
        ("aislado", "Comunidad aislada", COLOR_AISLADO, "aro"),
    ]

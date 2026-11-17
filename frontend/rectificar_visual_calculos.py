# Cálculos de «Rectificar» visual (frontend/rectificar_visual.py). Python puro, sin ursina, con tests en
# tests/test_rectificar_visual.py.
#
# La publicación vieja SIGUE VIVA en el feed: sus contadores suben mientras se lee la tarjeta y llegan comentarios
# enfadados. Según la decisión:
#   rectificar  la corrección se escribe letra a letra, los contadores bajan y los comentarios pasan a «gracias por aclarar»;
#   borrar      la publicación se desvanece... y a los 2 s reaparece como CAPTURA en manos de otro usuario;
#   defender    los comentarios se multiplican y la publicación se replica en copias por la pantalla.
# Al día siguiente, la consecuencia llega con la MISMA tarjeta. En el mundo, vecinos cercanos se enojan (defender) o se
# muestran sociables (rectificar).

import math

VIVA, RECTIFICAR, BORRAR, DEFENDER = "viva", "rectificar", "borrar", "defender"
DECISIONES = (RECTIFICAR, BORRAR, DEFENDER)

BASE = {"reacciones": 120, "comentarios": 34, "compartidos": 58}
RITMO = {"reacciones": 9.0, "comentarios": 1.6, "compartidos": 4.5}     # por segundo con la publicación viva
DUR_BAJADA = 2.5               # s en que los contadores bajan al rectificar
FRACCION_RECTIFICADA = 0.35    # a cuánto bajan
T_DESVANECER = 0.6
T_CAPTURA = 2.0                # s tras borrar en que reaparece como captura
MULT_DEFENDER = 3.0
LETRAS_POR_SEGUNDO = 40.0
COPIAS_MAX = 6
INTERVALO_COMENTARIO = {VIVA: 1.3, RECTIFICAR: 1.6, BORRAR: 1.4, DEFENDER: 0.35}
SEGUNDOS_VECINOS = 25.0
RADIO_VECINOS = 14.0
MAX_VECINOS = 5

CORRECCION = "Me equivoqué: lo que compartí era falso. Aquí está la información verificada. Perdón por difundirlo."

COMENTARIOS = {
    VIVA: (("Vecina Rosa", "¡¿En serio?! Ya lo pasé a mi familia."),
           ("Beto", "Esto no es verdad y lo sigues dejando ahí."),
           ("Doña Célia", "¿Y la fuente? Mucha gente se asustó."),
           ("Grupo del morro", "Ya lo compartieron en tres grupos más."),
           ("Tiago", "Bórralo o corrígelo, por favor."),
           ("Anónimo", "Jajaja, todos se lo creyeron.")),
    RECTIFICAR: (("Vecina Rosa", "Gracias por aclarar. Ya avisé a mi familia."),
                 ("Beto", "Así se hace. Todos nos equivocamos."),
                 ("Doña Célia", "Gracias por poner la fuente."),
                 ("Tiago", "Lo comparto para que se sepa la verdad.")),
    BORRAR: (("Anónimo", "Lo borró, pero yo tengo la captura."),
             ("Grupo del morro", "Mira lo que había publicado..."),
             ("Beto", "Borrar no arregla nada si no explicas."),
             ("Vecina Rosa", "¿Entonces era falso o no?")),
    DEFENDER: (("Beto", "¡Encima lo defiende!"),
               ("Anónimo", "Compartido. Que se entere todo el barrio."),
               ("Doña Célia", "Esto es peligroso, gente."),
               ("Grupo del morro", "Ya está en todos los grupos."),
               ("Tiago", "No puedo creer que sigas con esto."),
               ("Vecina Rosa", "Mi hija lo vio en la escuela.")),
}

TITULO_DIA_SIGUIENTE = {
    RECTIFICAR: "Ayer rectificaste esta publicación",
    BORRAR: "Ayer borraste esta publicación... alguien guardó la captura",
    DEFENDER: "Ayer defendiste esta publicación",
}


def contadores(estado, t, t_decision=None):
    """Contadores {reacciones, comentarios, compartidos} de la publicación a los `t` s de abrir la tarjeta.
    `t_decision`: segundo en que se decidió (None = aún viva)."""
    if t_decision is None or estado == VIVA:
        return {k: int(BASE[k] + RITMO[k] * max(0.0, t)) for k in BASE}
    en_decision = {k: BASE[k] + RITMO[k] * max(0.0, t_decision) for k in BASE}
    tras = max(0.0, t - t_decision)
    if estado == RECTIFICAR:
        k = min(1.0, tras / DUR_BAJADA)
        k = k * k * (3 - 2 * k)
        return {c: int(v + (v * FRACCION_RECTIFICADA - v) * k) for c, v in en_decision.items()}
    if estado == BORRAR:
        if tras < T_CAPTURA:
            return {c: 0 for c in en_decision}
        return {c: int(v * 0.4 + RITMO[c] * 1.5 * (tras - T_CAPTURA)) for c, v in en_decision.items()}
    if estado == DEFENDER:
        return {c: int(v + RITMO[c] * MULT_DEFENDER * tras) for c, v in en_decision.items()}
    return {k: int(v) for k, v in en_decision.items()}


def texto_contadores(c):
    return f"Reacciones {c['reacciones']}   ·   Compartidos {c['compartidos']}\nComentarios {c['comentarios']}"


def comentarios_visibles(estado, t, n=4):
    """Los `n` comentarios más recientes (nombre, texto), el más nuevo primero. Llegan uno cada INTERVALO s."""
    lista = COMENTARIOS.get(estado, COMENTARIOS[VIVA])
    llegados = 1 + int(max(0.0, t) / INTERVALO_COMENTARIO.get(estado, 1.3))
    salida = []
    for i in range(min(n, llegados)):
        salida.append(lista[(llegados - 1 - i) % len(lista)])
    return salida


def opacidad_publicacion(estado, tras):
    """Opacidad de la publicación original tras decidir (`tras` s). Borrar la desvanece."""
    if estado != BORRAR:
        return 1.0
    return max(0.0, 1.0 - tras / T_DESVANECER)


def captura_visible(estado, tras):
    return estado == BORRAR and tras >= T_CAPTURA


def letras(texto, tras, reducir=False):
    if reducir:
        return len(texto)
    return max(0, min(len(texto), int(tras * LETRAS_POR_SEGUNDO)))


def copias_visibles(estado, tras, reducir=False):
    """Cuántas copias de la publicación hay por la pantalla (defender): una más cada 0,4 s."""
    if estado != DEFENDER:
        return 0
    if reducir:
        return COPIAS_MAX
    return max(0, min(COPIAS_MAX, int(tras / 0.4)))


def posiciones_copias(semilla=0, n=COPIAS_MAX, aspecto=16 / 9):
    """(x, y, giro) de las copias: en la franja de arriba y en la parte baja del panel, que en la revisión queda vacía
    (no tapan la explicación). Coordenadas de camera.ui con el panel desplazado a la izquierda (lado_a_lado)."""
    base = [(-0.62, -0.21), (-0.30, -0.29), (0.02, -0.20), (-0.55, 0.435), (0.02, 0.44), (-0.12, -0.33)]
    salida = []
    for i in range(n):
        x, y = base[i % len(base)]
        giro = ((semilla * 37 + i * 53) % 21) - 10
        salida.append((x, y, float(giro)))
    return salida


def texto_publicacion(texto_evento):
    """La publicación compartida, sacada del texto de la tarjeta («... Lo que compartiste: X»)."""
    texto = str(texto_evento or "")
    marca = "Lo que compartiste:"
    if marca in texto:
        texto = texto.split(marca, 1)[1]
    texto = texto.strip()
    # Si cita lo que escribiste entre comillas angulares, la publicación es esa cita.
    if "«" in texto and "»" in texto.split("«", 1)[1]:
        return texto.split("«", 1)[1].split("»", 1)[0].strip()
    return texto


def decision_de_clave(clave):
    """(caso_id, decision) de la clave de un aviso retardado de rectificar («rectificar_<caso>_<decision>_luego»).
    None si no es de rectificar."""
    clave = str(clave or "")
    if not clave.startswith("rectificar_") or not clave.endswith("_luego"):
        return None
    cuerpo = clave[len("rectificar_"):-len("_luego")]
    for decision in DECISIONES:
        sufijo = "_" + decision
        if cuerpo.endswith(sufijo):
            return cuerpo[:-len(sufijo)], decision
    return None


def postura_vecinos(decision):
    """Postura de los vecinos cercanos tras decidir (None = no cambia)."""
    return {DEFENDER: "enojado", RECTIFICAR: "sociable"}.get(decision)


def mas_cercanos(posiciones, centro, n=MAX_VECINOS, radio=RADIO_VECINOS):
    """Índices de las `n` posiciones (x, z) más cercanas a `centro` dentro de `radio`."""
    cx, cz = centro
    con_d = []
    for i, p in enumerate(posiciones):
        if p is None:
            continue
        d = math.hypot(p[0] - cx, p[1] - cz)
        if d <= radio:
            con_d.append((d, i))
    return [i for _, i in sorted(con_d)[:n]]


def lado_a_lado(aspecto, ancho_panel=1.30, ancho_telefono=0.40, hueco=0.02):
    """(x del panel, x del teléfono) para que quepan uno junto al otro, o None si la ventana es demasiado estrecha."""
    media = aspecto / 2
    total = ancho_panel + hueco + ancho_telefono
    if total > 2 * media - 0.04:
        return None
    izquierda = -total / 2
    return izquierda + ancho_panel / 2, izquierda + ancho_panel + hueco + ancho_telefono / 2

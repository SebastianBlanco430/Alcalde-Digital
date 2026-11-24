# Decisiones del flujo de la Fiscalía (Python puro: NO importa ursina; tests en tests/test_fiscalia_escena_flujo.py).
# La escena (frontend/fiscalia/escena_fiscalia.py) pregunta aquí qué hacer entre un nodo y el siguiente; aquí no hay
# reglas del caso (salen del JSON por la sesión), solo de puesta en escena.

from frontend.fiscalia import salas_calculos as sc

FUNDIDO, CORTE, FINAL = "fundido", "corte", "final"
NO_DISPONIBLE = "Fiscalía no disponible en esta partida"
SIN_CASOS = "La Fiscalía no tiene casos abiertos para ti ahora"
DURACION_CORTE_SALA = 0.9         # s del corte «sale ella, entra él» (negro corto)


def transicion(anterior, nueva):
    """Qué hay entre la vista `anterior` y `nueva` (VistaNodo; anterior puede ser None):
    FINAL si `nueva` es un final; FUNDIDO (con el rótulo de la sala) si cambia la escena o es la primera;
    CORTE si en la sala cambia el interrogado; None si sigue en la misma sala con la misma gente.
    modelos-personajes (24-nov): también hay CORTE cuando el interrogado entra tras un nodo sin ocupante (el narrador
    o el fiscal tras el vidrio: «n_sala_entra» de encuesta_trucada y audio_del_candidato). Antes eso daba None, nadie
    llamaba a _cambiar_ocupante y Lívia / Jandira hablaban frente a una silla vacía."""
    if nueva is None:
        return None
    if nueva.tipo == "final":
        return FINAL
    if anterior is None or anterior.escena != nueva.escena:
        return FUNDIDO
    if nueva.escena == sc.SALA and ocupante(anterior) != ocupante(nueva) and ocupante(nueva) is not None:
        return CORTE
    return None


def ocupante(vista, fiscal="fiscal"):
    """Quién está sentado frente al jugador en la escena de la vista: en la sala, el interrogado que habla (el fiscal
    mira desde el vidrio); en la oficina, el fiscal; en el laboratorio, nadie (el jugador camina)."""
    if vista is None:
        return None
    if vista.escena == sc.OFICINA:
        return fiscal
    if vista.escena == sc.SALA:
        return vista.personaje if vista.personaje not in (None, fiscal) else None
    return None


def rotulo(escena, escenas_caso=None):
    """Texto del fundido al entrar a `escena` (el del caso, si lo trae; si no, el de siempre)."""
    propio = escenas_caso.get(escena) if isinstance(escenas_caso, dict) else None
    if isinstance(propio, dict):                     # forma del JSON: {"rotulo": ...}; CasoV2.escenas ya da el texto
        propio = propio.get("rotulo")
    return (propio if isinstance(propio, str) else None) or sc.ROTULOS.get(escena, "")


def reloj_corre(vista, linea_completa, modal_abierto, en_transicion):
    """¿Corre el reloj este frame? Solo con reloj, la línea ya escrita, sin modal y sin fundido."""
    return (vista is not None and vista.reloj_segundos is not None and bool(linea_completa)
            and not modal_abierto and not en_transicion)


def elegir_caso(mision, catalogo, terminado, abierto=None):
    """Id del caso a abrir en la Fiscalía: el de la misión actual si es una investigación v2 sin terminar; si no, None
    (la puerta dice SIN_CASOS). `catalogo`: ids en orden; `terminado(id)` -> bool. `abierto` se conserva por
    compatibilidad: la misión de un caso solo sale el día de ese caso.
    Sesión E (D2 de la verificación): antes, sin esa misión, abría «el primero del catálogo sin terminar»: tras cerrar
    «Cuentas fantasma», E otra vez abría el caso del día 5 sin que nadie lo pidiera."""
    ids = list(catalogo or ())
    objetivo = getattr(mision, "objetivo", None) if getattr(mision, "tipo", None) == "investigacion" else None
    if objetivo in ids and not terminado(objetivo):
        return objetivo
    return None


def caso_abierto(dia_caso, dia_actual):
    """¿Ya se puede abrir un caso cuyo `mision.dia` es `dia_caso`? Sin día conocido (partida sin reparto) sí."""
    try:
        return dia_actual is None or int(dia_caso or 1) <= int(dia_actual)
    except (TypeError, ValueError):
        return True


def parkour_completado(antes, despues):
    """¿El parkour terminó en la meta en ESTA visita? `antes`/`despues`: el último resultado del nivel (dict o None) antes
    de lanzarlo y al volver (registro_parkour.resultado)."""
    return despues is not None and despues is not antes and bool(despues.get("completado"))


def aviso_laboratorio(cerca, puerta):
    """Qué ofrece la E en el laboratorio: ('terminal', nivel), ('puerta', None) o (None, None)."""
    if cerca is not None:
        return "terminal", cerca
    if puerta:
        return "puerta", None
    return None, None


def es_acotacion(texto):
    """Una frase del jugador entre paréntesis («(Lo miras sin decir nada.)») es una acotación: sin comillas ni nombre."""
    t = str(texto or "").strip()
    return t.startswith("(") and t.endswith(")")


# -- Puerta del laboratorio (O10 de la verificación de misiones) --
# Sin las pruebas del laboratorio ningún caso llega al umbral de éxito (solidez máxima 36 < 55-60): el cuadro «¿Pasar a
# la sala?» lo dice ANTES de cerrar el laboratorio. Genérico: sale de los parkours del caso (hechos frente a disponibles).

def aviso_puerta_laboratorio(parkours):
    """Aviso extra del cuadro «¿Pasar a la sala?» ("" si ya se revisaron todos los terminales o no hay laboratorio)."""
    parkours = tuple(parkours or ())
    pendientes = [p for p in parkours if not getattr(p, "completado", False)]
    if not pendientes:
        return ""
    if len(pendientes) == len(parkours):
        return "Aún no revisaste los equipos del laboratorio: sin esas pruebas el caso no se sostiene."
    nombres = " ni ".join(f"«{getattr(p, 'nombre', p)}»" for p in pendientes)
    return f"Aún no revisaste {nombres}: sin esa prueba el caso queda más débil."


# -- Tope del modo «terminal» (riesgo §2.7 de la verificación) --
# En «terminal» la escena no atiende ninguna tecla. Si la animación de sentarse o la apertura del parkour fallan sin
# avisar, a los TOPE_TERMINAL s fuera de fundidos el jugador se levanta solo. Mientras el parkour está abierto la escena
# está desactivada (no corre su update): el tiempo jugando no cuenta.
TOPE_TERMINAL = 12.0


def tope_terminal(t, dt, en_transicion, tope=TOPE_TERMINAL):
    """(nuevo t, vencido). No cuenta durante un fundido; al vencer vuelve a 0."""
    if en_transicion:
        return t, False
    t = t + max(0.0, float(dt or 0.0))
    if t > tope:
        return 0.0, True
    return t, False

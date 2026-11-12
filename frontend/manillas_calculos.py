# Manillas de Bonfim en el frontend (punto 6 del plan final): parte PURA (sin ursina ni panda3d; se prueba sin ventana).
# La vista vive en frontend/registro_manillas.py y el dibujo de la cinta (Pillow) en frontend/manillas_dibujo.py.
#
# Homenaje a las «fitinhas do Senhor do Bonfim» (Salvador, Brasil): cintas de colores que se anudan en la muñeca. Aquí son
# el termómetro físico de la ciudad (brazalete del HUD, una cinta por indicador) y de cada vecino (cinta en su muñeca
# izquierda). El estado se lee por CUATRO canales (color, tejido, nudos, desgaste), nunca solo por el color: la paleta y
# los estilos salen de backend/logica/manillas.py.
#
#   valores_ciudad(amb, indicadores)               -> {indicador: valor 0-100} de las 5 manillas del HUD (o None)
#   aspecto_ciudad(indicador, valor, nivel_previo) -> detalle de la manilla con HISTÉRESIS de nivel (no parpadea)
#   clave_textura(detalle)                         -> clave de caché de la cinta ya cuantizada
#   texto_tooltip(detalle, valor) / lineas_leyenda()
#   oculto_hud(...)                                -> ¿el brazalete se esconde? (pausa, mapa, paneles, cinemática, final)
#   cinta_bajo_cursor(punto, centros, w, h)        -> índice de la cinta bajo el ratón, o None
#   elegir_cintas_npc(candidatos, asignados, ...)  -> quién lleva cada cinta de la piscina (reasignable, sin saltos)
#   geometria_anillo(...)                          -> malla (vértices, uv, triángulos) del aro de la muñeca
#   colores_finales()                              -> la paleta tal como se pinta (HUD, NPC y leyenda), para los tests

import math

from backend.logica import manillas as m

TECLA = "b"                          # leyenda / detalle de las manillas (libre en el mundo; ver frontend/teclas.py)
INDICADORES_HUD = m.INDICADORES      # convivencia, confianza, desinformacion, bienestar, conflictos
ETIQUETAS_CORTAS = {
    "convivencia": "Conviv.", "confianza": "Confianza", "desinformacion": "Bulos", "bienestar": "Bienestar",
    "conflictos": "Roces",
}
MARGEN_HISTERESIS = 2.0              # puntos de bondad que hay que pasar del umbral para cambiar de nivel
PASOS_DESGASTE = 6                   # el desgaste continuo se dibuja en 6 grados (las texturas se cachean)
DURACION_FUNDIDO = 0.6               # s: una cinta nueva se funde sobre la anterior

# --- NPC ---
RADIO_CINTA_NPC = 13.0               # m de la cámara: más lejos nadie lleva cinta visible (no se leería)
RADIO_SALIDA_NPC = 16.0              # histéresis: la cinta ya puesta se conserva hasta aquí
CAPACIDAD_NPC = 12                   # piscina fija de cintas (no hay una entidad por agente)
PERIODO_ASIGNACION = 4               # frames entre dos repartos de la piscina


# ---------------------------------------------------------------- ciudad

def valores_ciudad(amb, indicadores):
    """Los 5 valores 0-100 que pintan las manillas del brazalete: convivencia, confianza y desinformación suavizadas
    (`indicadores`, de ambiente_vivo.suave().valores()) y bienestar / conflictos del Ambiente. None si aún no hay partida."""
    if not indicadores:
        return None
    try:
        return {
            "convivencia": float(indicadores["convivencia"]), "confianza": float(indicadores["confianza"]),
            "desinformacion": float(indicadores["desinformacion"]), "bienestar": float(amb.bienestar),
            "conflictos": float(amb.conflictos),
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def nivel_con_histeresis(indicador, valor, nivel_previo=None, margen=MARGEN_HISTERESIS):
    """Nivel de la manilla; con `nivel_previo` solo cambia si la bondad sale de su banda por más de `margen` puntos."""
    bondad = m.bondad(indicador, valor)
    nuevo = m.nivel_de_bondad(bondad)
    if nivel_previo not in m.NIVELES or nivel_previo == nuevo:
        return nuevo
    i = m.NIVELES.index(nivel_previo)
    alto = 101.0 if i == 0 else m.UMBRALES_NIVEL[i - 1]       # techo de la banda del nivel previo
    bajo = -1.0 if i == len(m.NIVELES) - 1 else m.UMBRALES_NIVEL[i]
    return nivel_previo if bajo - margen <= bondad < alto + margen else nuevo


def aspecto_ciudad(indicador, valor, nivel_previo=None):
    """detalle_manilla(...) con el nivel (y su color, tejido y nudos) decidido con histéresis."""
    detalle = m.detalle_manilla(indicador, valor)
    nivel = nivel_con_histeresis(indicador, valor, nivel_previo)
    if nivel != detalle["nivel"]:
        color, patron, nudos = m.ESTILO_NIVEL[nivel]
        frase = m._FRASES[indicador][m.NIVELES.index(nivel)]
        detalle.update(nivel=nivel, color=list(color), patron=patron, nudos=nudos,
                       descripcion=f"{m.NOMBRES[indicador]}: {frase}")
    detalle["valor"] = round(max(0.0, min(100.0, float(valor))), 1)
    return detalle


def cuantizar_desgaste(desgaste, pasos=PASOS_DESGASTE):
    """Desgaste 0..1 redondeado a `pasos` grados (0.0 .. 1.0)."""
    d = max(0.0, min(1.0, float(desgaste)))
    return round(d * pasos) / pasos


def clave_textura(detalle):
    """Clave de caché de una cinta: (color, tejido, nudos, grado de desgaste)."""
    return (tuple(detalle["color"]), detalle["patron"], int(detalle["nudos"]), cuantizar_desgaste(detalle["desgaste"]))


def progreso_fundido(t, duracion=DURACION_FUNDIDO):
    """0..1 con suavizado (smoothstep) del fundido de una cinta nueva sobre la anterior."""
    if duracion <= 0:
        return 1.0
    x = max(0.0, min(1.0, t / duracion))
    return x * x * (3.0 - 2.0 * x)


def oculto_hud(en_pausa=False, cinematica=False, mapa_abierto=False, panel_abierto=False, terminada=False,
               sin_partida=False):
    """El brazalete se esconde como el resto del HUD: pausa, cinemática, mapa grande, paneles modales, fin de partida."""
    return bool(en_pausa or cinematica or mapa_abierto or panel_abierto or terminada or sin_partida)


def cinta_bajo_cursor(punto, centros, mitad_ancho, mitad_alto):
    """Índice de la cinta cuyo rectángulo contiene `punto` (x, y en camera.ui), o None."""
    if punto is None:
        return None
    for i, (cx, cy) in enumerate(centros):
        if abs(punto[0] - cx) <= mitad_ancho and abs(punto[1] - cy) <= mitad_alto:
            return i
    return None


def _nudos_texto(n):
    return {0: "sin nudos", 1: "1 nudo"}.get(n, f"{n} nudos")


def texto_tooltip(detalle):
    """Dos líneas del cursor sobre una manilla: la frase y cómo se lee (valor, tejido y nudos)."""
    nivel = detalle["nivel"]
    return (detalle["descripcion"],
            f"{nivel.capitalize()} · {detalle['patron']} · {_nudos_texto(detalle['nudos'])} · {round(detalle.get('valor', 0))}/100")


_NOTA_LECTURA = "No solo el color: mira el tejido, los nudos y lo deshilachada que está."
_NOTA_CULTURA = ("Inspiradas en las fitinhas do Bonfim, las cintas de colores que se anudan en la muñeca en Salvador (Brasil): "
                 "tres nudos, tres deseos.")


def lineas_leyenda():
    """Contenido de la leyenda: {"titulo", "ciudad": [(indicador, nombre, simbolo)], "niveles": [(nivel, patron, nudos, texto)],
    "vecinos": [(estado, patron, nudos, texto)], "notas": [str]}. Todo sale de backend/logica/manillas.py."""
    niveles = []
    textos_nivel = {"florece": "Florece: la ciudad va muy bien", "sano": "Sano: va bien", "tenso": "Tenso: hay fricción",
                    "apagado": "Apagado: va mal"}
    for nivel in m.NIVELES:
        _color, patron, nudos = m.ESTILO_NIVEL[nivel]
        niveles.append((nivel, patron, nudos, textos_nivel[nivel]))
    vecinos = []
    for estado in m.ESTADOS_NPC:
        manilla = m.manilla_de_npc(estado)
        vecinos.append((estado, manilla.patron, m.detalle_manilla_npc(estado)["nudos"],
                        f"{estado.capitalize()}: {manilla.descripcion}"))
    return {
        "titulo": "Manillas de Bonfim",
        "ciudad": [(i, m.NOMBRES[i], m.SIMBOLOS[i]) for i in INDICADORES_HUD],
        "niveles": niveles, "vecinos": vecinos, "notas": [_NOTA_LECTURA, _NOTA_CULTURA],
    }


# ---------------------------------------------------------------- NPC

def elegir_cintas_npc(candidatos, asignados, capacidad=CAPACIDAD_NPC, radio=RADIO_CINTA_NPC, radio_salida=RADIO_SALIDA_NPC):
    """Reparte la piscina de cintas. `candidatos`: [(id, distancia_a_la_cámara)] de los NPC dibujados con estado; `asignados`:
    {id: ranura} de ahora. Devuelve {id: ranura} nuevo:
      - quien ya lleva cinta la conserva mientras siga entre los candidatos a menos de `radio_salida`;
      - los nuevos (a menos de `radio`) entran de más cerca a más lejos, hasta llenar la piscina;
      - si no caben, los lejanos ceden su ranura a los cercanos (nunca se pierde un candidato cercano por uno lejano)."""
    cerca = {i: d for i, d in candidatos if d <= radio_salida}
    nuevo = {i: r for i, r in asignados.items() if i in cerca and 0 <= r < capacidad}
    libres = [r for r in range(capacidad) if r not in nuevo.values()]
    pendientes = sorted((i for i, d in cerca.items() if i not in nuevo and d <= radio), key=lambda i: (cerca[i], str(i)))
    for i in pendientes:
        if libres:
            nuevo[i] = libres.pop(0)
            continue
        peor = max(nuevo, key=lambda k: (cerca[k], str(k)))          # el más lejano de los que llevan cinta
        if cerca[peor] > cerca[i] + 0.5:
            nuevo[i] = nuevo.pop(peor)
    return nuevo


def geometria_anillo(radio, alto, segmentos=10):
    """Aro hueco de la muñeca (eje Y): (vértices, uvs, triángulos). Doble cara (los triángulos van en los dos sentidos)."""
    vertices, uvs, triangulos = [], [], []
    for k in range(segmentos + 1):
        ang = 2 * math.pi * (k % segmentos) / segmentos
        x, z = radio * math.cos(ang), radio * math.sin(ang)
        vertices += [(x, 0.0, z), (x, alto, z)]
        uvs += [(k / segmentos, 0.0), (k / segmentos, 1.0)]
    for k in range(segmentos):
        a, b, c, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        triangulos += [(a, b, c), (b, d, c), (a, c, b), (b, c, d)]
    return vertices, uvs, triangulos


# ---------------------------------------------------------------- accesibilidad

def colores_finales():
    """La paleta tal como se pinta, por contexto: {"hud": {nivel: color}, "npc": {estado: color}, "leyenda": {clave: color}}.
    La leyenda junta ambos (los niveles y los estados); sus entradas llevan prefijo para no chocar."""
    hud = {nivel: tuple(m.ESTILO_NIVEL[nivel][0]) for nivel in m.NIVELES}
    npc = {estado: tuple(m.ESTILO_NPC[estado][0]) for estado in m.ESTADOS_NPC}
    leyenda = {f"nivel:{k}": v for k, v in hud.items()}
    leyenda.update({f"estado:{k}": v for k, v in npc.items()})
    return {"hud": hud, "npc": npc, "leyenda": leyenda}


def firmas_de_forma():
    """(tejido, nudos, desgaste) de cada entrada por contexto: lo que desambigua dos colores que el filtro colapse."""
    hud = {n: (m.ESTILO_NIVEL[n][1], m.ESTILO_NIVEL[n][2]) for n in m.NIVELES}
    npc = {e: (m.ESTILO_NPC[e][1], m.ESTILO_NPC[e][2]) for e in m.ESTADOS_NPC}
    leyenda = {f"nivel:{k}": v for k, v in hud.items()}
    leyenda.update({f"estado:{k}": v for k, v in npc.items()})
    return {"hud": hud, "npc": npc, "leyenda": leyenda}

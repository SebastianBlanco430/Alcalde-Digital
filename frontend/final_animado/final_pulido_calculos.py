# Pulido de las cinemáticas finales (PURO: no importa ursina; se prueba con pytest en tests/test_b_final_pulido.py).
# Los planos del final animado se escribieron cuando los modelos v2 no estaban: aquí van las correcciones encontradas
# revisando bueno, malo y neutro toma por toma (docs/FINALES_PULIDOS.md trae cada defecto con su captura y su arreglo).
# Nada de esto cambia textos ni duraciones: solo dónde está cada cosa, qué pose hace y qué cuerpo la hace.
#
# Bandera ALCALDE_FINALES_PULIDOS (por defecto encendida): =0 deja los finales exactamente como antes. Se lee en cada
# llamada, así una prueba puede cambiarla sin recargar módulos.
#
#   activo()                         ¿se usan las correcciones?
#   corregir_puestas(puestas)        {id: Puesta} con los planos corregidos (los demás, los mismos objetos)
#   tomas(tomas_base)                {id: toma} con las cámaras corregidas encima de las de siempre
#   receta_vecino(k)                 id del elenco v2 (personajes_fiscalia.json) del vecino k, o None

import os
from dataclasses import replace

PULIDOS = True
_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Finales pulidos? ALCALDE_FINALES_PULIDOS=1/0 manda sobre PULIDOS (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_FINALES_PULIDOS", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(PULIDOS)


# -- Elenco ------------------------------------------------------------------------------------------------------------

# Los vecinos v0..v9 salían de la fábrica de peatones (cuerpos v1, el ciudadano.glb viejo incluido) junto a los
# protagonistas v2. Con el pulido son la gente del barrio del elenco v2 (los mismos de la Fiscalía), sin la fiscal ni
# Arenas, que tienen su papel. Orden pensado para que los planos con pocos vecinos mezclen mujeres y hombres.
ELENCO_VECINOS = ("vecina", "seu_ze", "jandira", "nico", "livia", "ramiro", "ines", "marcos", "eurico", "baltazar")


def receta_vecino(k):
    """Id de la receta v2 del vecino k (0..9), o None fuera del reparto."""
    if 0 <= int(k) < len(ELENCO_VECINOS):
        return ELENCO_VECINOS[int(k)]
    return None


# -- Ventana del Morro (planos m4/b5/n4 del ciudadano) -----------------------------------------------------------------

# El paño era más bajo que el letrero de la casa de verdad y el hueco quedaba por debajo de la cabeza del protagonista
# v2: se veía el torso sin cara y el cartel «Morro da Esperança» tapaba medio cuadro. Ahora el paño es una fachada
# entera (tapa el letrero que queda detrás), el hueco está a la altura de la cara y los postigos abren HACIA FUERA,
# contra la pared, sin cruzar el hueco ni al ciudadano.
VENTANA_ALTO = 3.7
VENTANA_ANCHO = 5.2
# Ancho, alféizar, dintel
VENTANA_HUECO = (1.3, 1.05, 2.25)
# m que el paño baja por debajo del suelo (el Morro tiene pendiente)
VENTANA_ZOCALO = 0.6
# +1: abren hacia fuera (antes -1: hacia dentro, a través del hueco)
GIRO_POSTIGOS = 1.0
# El banderín, encima del dintel (antes a 2,3: le tapaba la cabeza)
BANDERIN_ALTO = 2.55


# -- Pancarta y props --------------------------------------------------------------------------------------------------

# Pancarta (actores.Pancarta): (alto de las manos, adelante) abajo y arriba. Abajo, el cartel le tapaba la cara; ahora
# queda a la altura del pecho y, arriba, por encima de la cabeza.
PANCARTA_ABAJO = (0.5, 0.5)
PANCARTA_ARRIBA = (1.78, 0.14)
# El gorro de la bandeja quedaba sobre la cara de los cuerpos v2
GORRO_PANADERO = False
# Banda de Octavio: el cubo era más hondo que el torso del smoking v2 y asomaba como una tabla.
# anillo: (radio de lado, radio de fondo, ancho de la cinta) en m, inclinado `giro` del hombro a la cadera contraria
# (el origen del smoking v2 queda ~0,25 m por debajo de los pies: con y = 1,3 la medalla caía en la cintura)
BANDA = {"pos": (0.0, 1.52, 0.0), "giro": (0, 0, 48), "anillo": (0.34, 0.22, 0.075)}


# -- Panel final (frontend/panel_final.py) ----------------------------------------------------------------------------

# Alto del panel (como PanelFinalSemana), fila de barras y borde superior del resumen: así la franja del desenlace
# (FRANJA_Y = -0,292, 0,112 de alto) queda entre el resumen (hasta 3 líneas en línea: acertadas, confianza media e
# indicadores) y el botón, sin tapar nada. Las barras suben al hueco que dejaba el párrafo.
PANEL_FINAL_ALTO = 0.94
PANEL_FINAL_Y_BARRAS = 0.01
PANEL_FINAL_Y_RESUMEN = -0.105


# -- Puestas -----------------------------------------------------------------------------------------------------------

# m2: las calles «arden», pero desde la toma aérea no se veía ni una llama. Fogatas (derecha, frente) en las calles que
# mira la cámara (marco de la plaza), con su humo.
FOGATAS_M2 = ((8.5, -7.0), (12.5, -12.5), (17.0, -9.0), (6.5, -14.5), (15.5, -18.0), (21.0, -14.0))


def _ciudadano_pulido(pz, P, final):
    """La ventana del Morro: el ciudadano se asoma con la cara en el hueco. Malo: mira el humo, se retira con la
    cabeza baja y SOLO DESPUÉS se cierran los postigos (antes se cerraban sobre su cara)."""
    piezas = []
    for pieza in pz.piezas:
        if pieza.tipo == "ventana_morro" and final == "malo":
            pieza = replace(pieza, tramo=(0.74, 0.94))
        elif pieza.tipo == "banderin_ventana":
            pieza = replace(pieza, alto=BANDERIN_ALTO)
        piezas.append(pieza)
    d, f = P.CIUDADANO_MORRO
    actores = []
    for actor in pz.actores:
        if actor.id == "prota:ciudadano" and final == "malo":
            actor = replace(actor, accion="apoyado", pasos=(
                P.Paso(0.0, 0.42, "apoyado", mira=-25.0),
                P.Paso(0.42, 0.56, "cabeza_baja", mira=0.0),
                P.Paso(0.56, 0.72, "cabeza_baja", hasta=(d, f - 0.55)),
                P.Paso(0.72, 1.0, "cabeza_baja")))
        actores.append(actor)
    return replace(pz, actores=tuple(actores), piezas=tuple(piezas))


# (derecha, frente) del pie del micrófono en los planos del candidato
MICROFONO = (-0.6, 0.45)
# Los íconos del directo, detrás de la influencer
ICONOS_FRENTE = -0.6
ICONOS_ALTO = 1.4
OCTAVIO_N5 = (-1.3, 0.9)
# Escala de cada fogata: desde 17-26 m de alto tiene que leerse como fuego
FOGATA_MEDIDA = 2.2


def _fogatas(P):
    return tuple(P.Pieza("fogata", d, f, variante=k % 3, medida=FOGATA_MEDIDA) for k, (d, f) in enumerate(FOGATAS_M2))


def corregir_puestas(puestas):
    """Copia de `puestas` ({id: Puesta}) con los planos corregidos. Pura: no toca el dict de entrada."""
    from frontend.final_animado import puesta as P
    out = dict(puestas)
    for pre, final in (("m4", "malo"), ("b5", "bueno"), ("n4", "neutro")):
        clave = f"{pre}_ciudadano"
        if clave in out:
            out[clave] = _ciudadano_pulido(out[clave], P, final)
    if "m2_calles_arden" in out:
        out["m2_calles_arden"] = replace(out["m2_calles_arden"], piezas=out["m2_calles_arden"].piezas + _fogatas(P))
    if "b2_sede_oscura" in out:
        # Arenas se iba hasta el borde del cuadro y se quedaba cortado (solo la cabeza): ahora sale del todo.
        arenas = []
        for actor in out["b2_sede_oscura"].actores:
            if actor.id == P.ARENAS:
                pasos = actor.pasos[:-1] + (P.Paso(0.34, 0.98, "quieto", hasta=(8.0, 6.5)),)
                actor = replace(actor, pasos=pasos)
            arenas.append(actor)
        out["b2_sede_oscura"] = replace(out["b2_sede_oscura"], actores=tuple(arenas))
    for pre in ("m4", "b5", "n4"):
        # Candidato: el pie del micrófono le cruzaba el torso; va a su izquierda (la cámara también se corre).
        clave = f"{pre}_candidato"
        if clave in out:
            piezas = tuple(replace(p, derecha=MICROFONO[0], frente=MICROFONO[1]) if p.tipo == "microfono" else p
                           for p in out[clave].piezas)
            out[clave] = replace(out[clave], piezas=piezas)
        # Influencer: los íconos subían pegados a la cámara (enormes y cortados arriba); salen detrás de ella.
        clave = f"{pre}_influencer"
        if clave in out:
            piezas = tuple(replace(p, frente=ICONOS_FRENTE, alto=ICONOS_ALTO) if p.tipo == "iconos" else p
                           for p in out[clave].piezas)
            out[clave] = replace(out[clave], piezas=piezas)
    if "n5_candidatos" in out:
        # Octavio quedaba bajo el cartel amarillo de la calle (le tapaba la cabeza): más cerca de la puerta.
        actores = tuple(replace(a, derecha=OCTAVIO_N5[0], frente=OCTAVIO_N5[1]) if a.id == P.OCTAVIO else a
                        for a in out["n5_candidatos"].actores)
        out["n5_candidatos"] = replace(out["n5_candidatos"], actores=actores)
    if "b6_podio" in out:
        # El confeti pasaba pegado a la cámara (un papel amarillo tapaba medio cuadro): solo sobre el público.
        piezas = tuple(replace(p, frente=3.6, medida=4.5) if p.tipo == "confeti" else p
                       for p in out["b6_podio"].piezas)
        out["b6_podio"] = replace(out["b6_podio"], piezas=piezas)
    return out


# -- Cámaras -----------------------------------------------------------------------------------------------------------

# Encima de camaras.TOMAS. Ciudadano: más baja y más cerca, a la altura de la cara (desde 2,8-3,2 m se veía el letrero
# de la casa encima del paño). b6: el final del travelling quedaba detrás del atril, que tapaba a Octavio.
TOMAS_PULIDAS = {
    # (la ventana está 1,3 m más afuera que antes, con su cuarto detrás: la cámara se corre lo mismo)
    "ciudadano": {"ancla": "morro", "pos": [(1.2, 2.1, 8.9), (1.8, 2.2, 7.6)],
                  "mira": [(2.2, 1.85, 0.3), (2.2, 1.8, 0.3)], "fov": (52.0, 46.0)},
    # Candidato: más de frente (el vecino que le da la mano ya no queda entre la cámara y Octavio).
    "candidato": {"ancla": "tarima", "pos": [(1.3, 1.75, 4.6), (1.0, 1.75, 3.9)],
                  "mira": [(0.3, 1.5, 0.0), (0.3, 1.6, 0.0)], "fov": (56.0, 54.0)},
    # m5: la cámara subía mirando el edificio y las pancartas del suelo (de lo que habla el subtítulo) salían del cuadro
    # a mitad del plano; ahora retrocede por detrás de ellas y termina con ellas delante y la Prefeitura al fondo.
    "m5_plaza_vacia": {"ancla": "protesta",
                       "pos": [(1.8, 1.2, -4.4), (1.2, 2.2, -6.6), (0.4, 3.4, -9.0)],
                       "mira": [(0.0, 0.1, -1.8), (0.0, 0.4, -0.5), ("prefeitura", 1.5, 4.2, -1.1)],
                       "fov": (54.0, 60.0)},
    "b6_podio": {"ancla": "podio", "pos": [(0.0, 4.5, 13.0), (0.0, 3.6, 8.5), (1.2, 3.0, 5.8)],
                 "mira": [(0.0, 1.6, -2.0), (0.0, 2.0, 0.0)], "fov": (62.0, 52.0)},
}


def tomas(tomas_base):
    """Copia de `tomas_base` (camaras.TOMAS) con las tomas corregidas."""
    out = dict(tomas_base)
    for pre in ("m4", "b5", "n4"):
        out[f"{pre}_ciudadano"] = TOMAS_PULIDAS["ciudadano"]
        out[f"{pre}_candidato"] = TOMAS_PULIDAS["candidato"]
    for clave in ("b6_podio", "m5_plaza_vacia"):
        out[clave] = TOMAS_PULIDAS[clave]
    return out

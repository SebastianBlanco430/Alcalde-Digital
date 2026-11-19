# Marco visual COMÚN de los minijuegos de verificar (Ursina): mesa de papel de fondo, cabecera con el rumor en una tira de papel,
# sello redondo y panel de resultado de papel. La lógica pura vive en marco_calculos.py. Apagado con ALCALDE_MARCO_VISUAL=0.
#
# Cada función es independiente y la llama su dueño dentro de un guardián: si falla, vuelve a lo de siempre.

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente, panel_tinta, rgb
from frontend.minijuegos import ui
from frontend.minijuegos.limite_texto import MAX_RUMOR, limitar_texto
from frontend.minijuegos_visual import marco_calculos as mc

ASPECTO = 16 / 9
Z_MESA = 0.15                       # detrás de todo el contenido del minijuego y delante del fondo azul de la escena (0,2)


# -- T1: mesa --

def montar_mesa(padre):
    """Mesa de redacción a pantalla completa con vetas muy suaves. Devuelve la Entity (o None si el marco está apagado)."""
    if not mc.activo():
        return None
    mesa = Entity(parent=padre, z=Z_MESA)
    Entity(parent=mesa, model="quad", scale=(ASPECTO + 0.06, 1.06), color=rgb(mc.MESA), z=0.0)
    for x, y, largo, alfa in mc.vetas():
        Entity(parent=mesa, model="quad", scale=(largo * ASPECTO, a_unidades(1.5)),
               color=color.rgba32(*mc.MESA_VETA, alfa), position=((x - 0.5) * ASPECTO, y - 0.5, -0.001))
    return mesa


# -- T2: cabecera --

def titulo_con_contorno(padre, titulo, px, ancho, posicion):
    """Título de papel con sombra dura de tinta (dos copias desplazadas detrás)."""
    d = a_unidades(2)
    for dx in (d, -d):
        sombra = ui.texto(padre, titulo, px, ancho, estilo.TINTA, (posicion[0] + dx, posicion[1] - d), negrita=True)
        sombra.z = ui.Z_TEXTO + 0.004
    return ui.texto(padre, titulo, px, ancho, mc.TEXTO_SOBRE_MESA, posicion, negrita=True)


def cabecera(padre, titulo, rumor, ancho_util, y_titulo=0.49):
    """Título con contorno de tinta y rumor en tira de papel con pestaña «RUMOR». Devuelve (titulo, rumor_text, tira)."""
    x0 = -ancho_util / 2
    d = a_unidades(2)
    t = titulo_con_contorno(padre, titulo, mc.PX_TITULO, ancho_util, (x0, y_titulo))
    y_top = y_titulo - a_unidades(mc.PX_TITULO) * 1.08 - a_unidades(4)
    ancho_pestana = ui.medir("RUMOR", mc.PX_ETIQUETA, True) + a_unidades(18)
    margen = a_unidades(10)
    ancho_texto = ancho_util - ancho_pestana - 2 * margen - a_unidades(8)
    cuerpo = "«" + limitar_texto(" ".join(str(rumor).split()), MAX_RUMOR) + "»"
    lineas = ui.lineas_de(cuerpo, mc.PX_RUMOR, ancho_texto, True)
    ancho_real = max(ui.medir(l, mc.PX_RUMOR, True) for l in lineas)
    ancho = min(ancho_util, ancho_pestana + 2 * margen + ancho_real + a_unidades(8))
    alto = max(ui.alto_de(len(lineas), mc.PX_RUMOR) + a_unidades(14), a_unidades(40))
    tira = Entity(parent=padre, position=(x0 + ancho / 2, y_top - alto / 2, 0),
                  rotation_z=mc.rotacion_tira(bv.reducir_movimiento()))
    panel_tinta(tira, ancho, alto, tono=mc.PAPEL, radio_px=mc.RADIO_PAPEL_PX)
    pestana = Entity(parent=tira, position=(-ancho / 2 + ancho_pestana / 2, 0, -0.002))
    ui.rect(pestana, ancho_pestana, alto, mc.ROJO_PESTANA, z=0.0, radio_px=4)
    Text("RUMOR", parent=pestana, origin=(0, 0), position=(0, 0, ui.Z_TEXTO), scale=escala_fuente(mc.PX_ETIQUETA),
         color=rgb(mc.PAPEL), font=tipografia.FUENTE_TITULO)
    r = ui.texto(tira, cuerpo, mc.PX_RUMOR, ancho_texto, mc.TINTA,
                 (-ancho / 2 + ancho_pestana + margen, alto / 2 - a_unidades(7)), negrita=True)
    return t, r, tira


# -- T4: sello redondo --

def sello(padre, bien, x, y, diametro=0.13):
    """Sello redondo (verde con palomita / rojo con tachón) MÁS la palabra: nunca solo color."""
    tono = mc.color_sello(bien)
    c = Entity(parent=padre, position=(x, y, -0.01))
    Entity(parent=c, model="circle", scale=diametro, color=rgb(estilo.TINTA), z=0.001)
    Entity(parent=c, model="circle", scale=diametro - a_unidades(6), color=rgb(tono), z=0.0)
    Entity(parent=c, model="circle", scale=diametro - a_unidades(14), color=rgb(mc.PAPEL), z=-0.001)
    g = a_unidades(5)
    y_marca = diametro * 0.12
    if bien:       # palomita: trazo corto hacia abajo y trazo largo hacia arriba, unidos en el vértice
        _trazo(c, diametro * -0.075, y_marca - diametro * 0.01, diametro * 0.16, g, 42, tono)
        _trazo(c, diametro * 0.07, y_marca + diametro * 0.05, diametro * 0.28, g, -48, tono)
    else:          # tachón
        _trazo(c, 0, y_marca, diametro * 0.30, g, 45, tono)
        _trazo(c, 0, y_marca, diametro * 0.30, g, -45, tono)
    Text(mc.palabra_sello(bien), parent=c, origin=(0, 0), position=(0, -diametro * 0.26, ui.Z_TEXTO),
         scale=escala_fuente(16), color=rgb(tono), font=tipografia.FUENTE_TITULO)
    return c


def _trazo(padre, x, y, largo, grosor, rot, tono):
    Entity(parent=padre, model="quad", scale=(largo, grosor), color=rgb(tono), position=(x, y, -0.003), rotation_z=rot)


# -- T4: panel de resultado --

ALTO_PANEL_MAX = 0.24
Y_PANEL_ABAJO = -0.487


def _compacto(padre, lineas, px, tono, posicion, negrita=False, k=None):
    """Bloque de texto ya envuelto, con el interlineado compacto. Devuelve su alto."""
    t = ui.texto(padre, "\n".join(lineas), px, None, tono, posicion, negrita=negrita)
    k = mc.LINEA_COMPACTA if k is None else k
    t.line_height = k
    return len(lineas) * a_unidades(px) * k


def panel_resultado(banner, ancho, bien, titulo, detalle, pista, ancho_columna_boton=0.36, veredicto=""):
    """Dibuja en `banner` el marco de papel con sello, título (30), detalle (19, máx. 2 líneas) y pista aparte (17, máx. 2
    líneas). Devuelve un dict con `y` (centro), `alto` y `x_boton` (centro de la columna del botón)."""
    margen = a_unidades(12)
    m_vert = a_unidades(7)          # margen vertical más justo: el panel debe quedar bajo y=-0,30
    d_sello = 0.12
    x0 = -ancho / 2 + margen + d_sello + a_unidades(14)
    ancho_texto = ancho - (x0 + ancho / 2) - ancho_columna_boton - margen
    # El veredicto («El rumor era falso.») comparte renglón con el título si cabe: así el detalle queda en 1 línea y el panel baja.
    x_ver = ui.medir(titulo, mc.PX_TITULO_RESULTADO, True) + a_unidades(18)
    junto = bool(veredicto) and x_ver + ui.medir(veredicto, mc.PX_DETALLE_RESULTADO) <= ancho_texto
    if veredicto and not junto:
        detalle = f"{detalle} {veredicto}"
    l_det = mc.limitar_lineas(ui.lineas_de(detalle, mc.PX_DETALLE_RESULTADO, ancho_texto), 2)
    l_pis = mc.limitar_lineas(ui.lineas_de(pista, mc.PX_PISTA, ancho_texto), 2)
    k = 1.08
    h_tit = a_unidades(mc.PX_TITULO_RESULTADO) * k
    h = (h_tit + len(l_det) * a_unidades(mc.PX_DETALLE_RESULTADO) * k + a_unidades(3)
         + len(l_pis) * a_unidades(mc.PX_PISTA) * k + 2 * m_vert)
    alto = max(0.15, min(ALTO_PANEL_MAX, h))
    y = Y_PANEL_ABAJO + alto / 2
    banner.y = y
    panel_tinta(banner, ancho, alto, tono=mc.PAPEL, radio_px=mc.RADIO_PAPEL_PX)
    sello(banner, bien, -ancho / 2 + margen + d_sello / 2, 0.0, d_sello)
    yt = alto / 2 - m_vert
    if junto:
        ui.texto(banner, veredicto, mc.PX_DETALLE_RESULTADO, None, mc.TINTA,
                 (x0 + x_ver, yt - a_unidades(mc.PX_TITULO_RESULTADO - mc.PX_DETALLE_RESULTADO) * 0.8))
    yt -= _compacto(banner, [titulo], mc.PX_TITULO_RESULTADO, mc.TINTA, (x0, yt), True, k)
    yt -= _compacto(banner, l_det, mc.PX_DETALLE_RESULTADO, mc.TINTA, (x0, yt), False, k)
    _compacto(banner, l_pis, mc.PX_PISTA, mc.TEXTO_SUAVE, (x0, yt - a_unidades(3)), False, k)
    return {"y": y, "alto": alto, "x_boton": ancho / 2 - ancho_columna_boton / 2 - margen + a_unidades(6)}


def chip(padre, texto, x, y, px=18):
    """Moneda/chip amarillo de tinta (propina). Devuelve su ancho."""
    ancho = ui.medir(texto, px, True) + a_unidades(22)
    alto = a_unidades(px) * 1.9
    c = Entity(parent=padre, position=(x, y, -0.01))
    panel_tinta(c, ancho, alto, tono=estilo.COLOR_ACENTO, radio_px=mc.RADIO_PAPEL_PX)
    Text(texto, parent=c, origin=(0, 0), position=(0, 0, ui.Z_TEXTO), scale=escala_fuente(px),
         color=rgb(estilo.COLOR_ACENTO_TEXTO), font=tipografia.FUENTE_TITULO)
    return ancho

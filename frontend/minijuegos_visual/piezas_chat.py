# Piezas visuales del «Chat del barrio» (Ursina): globo con cola, avatar circular, reloj de presión, botón-sello, sombra plana.
# Cálculo en chat_piezas_calculos.py (puro).

import json
import math

from panda3d.core import TransparencyAttrib
from ursina import Entity, Mesh, Text, color

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos_visual import chat_piezas_calculos as pc


def rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def sombra_plana(parent, ancho, alto, centro, z=0.01, radio_px=8, escala=1.0):
    """Sombra dura de tinta desplazada (+x, -y); `escala` reduce el desplazamiento en piezas pequeñas."""
    dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
    dx, dy = dx * escala, dy * escala
    return ui.rect(parent, ancho, alto, rgba(estilo.TINTA, estilo.ALFA_SOMBRA / 255),
                   (centro[0] + a_unidades(dx), centro[1] + a_unidades(dy)), z=z, radio_px=radio_px)


def globo(parent, ancho, alto, centro, tono, lado="izq", z=0.0, con_cola=True):
    """Globo de tinta (borde de 3 px) con relleno `tono`, sombra dura pequeña y cola; devuelve una Entity cuyo origen es el
    centro del globo."""
    raiz = Entity(parent=parent, position=(centro[0], centro[1], z))
    borde = a_unidades(estilo.GROSOR_BORDE_PX)
    sombra_plana(raiz, ancho + 2 * borde, alto + 2 * borde, (0, 0), z=0.0035, radio_px=9, escala=0.5)
    ui.rect(raiz, ancho + 2 * borde, alto + 2 * borde, estilo.TINTA, (0, 0), z=0.002, radio_px=9)
    ui.rect(raiz, ancho, alto, tono, (0, 0), z=0.001, radio_px=8)
    if con_cola:
        x, y, giro = pc.cola_globo(lado, ancho, alto)
        Entity(parent=raiz, model="quad", color=rgba(estilo.TINTA), position=(x, y, 0.0025), scale=0.022, rotation_z=giro)
        Entity(parent=raiz, model="quad", color=rgba(tono), position=(x, y, 0.0005), scale=0.016, rotation_z=giro)
    return raiz


_TEXTURAS_AVATAR = {}


def textura_avatar(de, indice=0, lado=96):
    """Retrato de cómic (dialogo_retratos) recortado en círculo sobre el color del rol. Se crea una vez por personaje."""
    retrato = pc.retrato_de(de, indice)
    tono = pc.color_personaje(de, indice)
    clave = (json.dumps(retrato, sort_keys=True), tono, lado)
    if clave not in _TEXTURAS_AVATAR:
        from PIL import Image, ImageDraw
        from ursina import Texture
        from frontend import dialogo_retratos
        cara = dialogo_retratos.dibujar_retrato_caso(retrato, "neutral", lado * 2).convert("RGBA")
        base = Image.new("RGBA", cara.size, tuple(tono) + (255,))
        base.alpha_composite(cara)
        mascara = Image.new("L", (cara.size[0] * 2, cara.size[1] * 2), 0)
        ImageDraw.Draw(mascara).ellipse((0, 0, mascara.size[0] - 1, mascara.size[1] - 1), fill=255)
        base.putalpha(mascara.resize(cara.size, Image.LANCZOS))
        textura = Texture(base)
        textura.filtering = "bilinear"
        _TEXTURAS_AVATAR[clave] = textura
    return _TEXTURAS_AVATAR[clave]


def avatar(parent, de, indice, centro, diametro=0.05, z=0.0):
    """Retrato de cómic con borde de tinta (en vez de una inicial). Devuelve (raiz, cara)."""
    raiz = Entity(parent=parent, position=(centro[0], centro[1], z))
    borde = a_unidades(estilo.GROSOR_BORDE_PX)
    Entity(parent=raiz, model="circle", scale=diametro + 2 * borde, color=rgba(estilo.TINTA), z=0.002)
    cara = Entity(parent=raiz, model="quad", scale=diametro, texture=textura_avatar(de, indice), z=0.001)
    cara.setTransparency(TransparencyAttrib.M_alpha)
    return raiz, cara


class RelojPresion(Entity):
    """Reloj de papel con borde de tinta: un arco claro que se vacía (cian > 66 %, amarillo 34-66 %, rojo < 34 %) y, encima,
    los SEGUNDOS que quedan en número grande de tinta (el número y la palabra «seg» dicen el estado: no solo el color)."""

    def __init__(self, diametro=0.12, **opciones):
        super().__init__(**opciones)
        self.radio = diametro / 2
        borde = a_unidades(estilo.GROSOR_BORDE_PX)
        dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
        Entity(parent=self, model="circle", scale=diametro + 2 * borde, color=rgba(estilo.TINTA, estilo.ALFA_SOMBRA / 255),
               position=(a_unidades(dx), a_unidades(dy), 0.0045))
        Entity(parent=self, model="circle", scale=diametro + 2 * borde, color=rgba(estilo.TINTA), z=0.003)
        Entity(parent=self, model="circle", scale=diametro, color=rgba(estilo.PAPEL), z=0.002)
        self._sector = Entity(parent=self, z=-0.001)
        self.numero = Text("", parent=self, origin=(0, 0), position=(0, 0.006, -0.004), scale=escala_fuente(36),
                           font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
        self.unidad = Text("seg", parent=self, origin=(0, 0), position=(0, -diametro * 0.30, -0.004),
                           scale=escala_fuente(15), font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
        self._ultimo = None
        self._ultimo_segundos = None

    def fijar(self, restante, segundos=None):
        r = round(max(0.0, min(1.0, restante)), 2)
        if segundos is not None and segundos != self._ultimo_segundos:
            self._ultimo_segundos = segundos
            self.numero.text = str(segundos)
        if r == self._ultimo:
            return
        self._ultimo = r
        verts, tris = pc.arco_reloj(r, self.radio * 0.9)
        if not verts:
            self._sector.model = None
            return
        self._sector.model = Mesh(vertices=[(x, y, 0) for x, y in verts], triangles=tris, mode="triangle")
        self._sector.double_sided = True
        self._sector.color = rgba(pc.color_reloj_papel(r))


class TelefonoPapel(Entity):
    """Teléfono de papel: cuerpo crema con borde de tinta de 3 px y sombra dura (4, -5), pantalla de papel con filo de tinta y
    barra de estado (Civitas, hora, señal, batería) en tinta. `centro` es el centro del cuerpo; `pantalla` devuelve el
    rectángulo útil (cx, cy, ancho, alto) de la pantalla."""

    CUERPO = (232, 220, 190)
    MARCO = 0.018
    BARRA = 0.05

    def __init__(self, ancho, alto, centro, minutos=None, **opciones):
        super().__init__(**opciones)
        import datetime
        cx, cy = centro
        self.ancho, self.alto, self.centro = ancho, alto, centro
        borde = a_unidades(estilo.GROSOR_BORDE_PX)
        sombra_plana(self, ancho + 2 * borde, alto + 2 * borde, (cx, cy), z=0.0095, radio_px=18)
        ui.rect(self, ancho + 2 * borde, alto + 2 * borde, estilo.TINTA, (cx, cy), z=0.009, radio_px=18)
        ui.rect(self, ancho, alto, self.CUERPO, (cx, cy), z=0.008, radio_px=16)
        # Pantalla: papel con filo de tinta fino.
        self.pantalla_ancho = ancho - 2 * self.MARCO
        self.pantalla_alto = alto - self.BARRA - self.MARCO
        self.pantalla_cy = cy - alto / 2 + self.MARCO + self.pantalla_alto / 2
        fino = a_unidades(2)
        ui.rect(self, self.pantalla_ancho + 2 * fino, self.pantalla_alto + 2 * fino, estilo.TINTA,
                (cx, self.pantalla_cy), z=0.0075, radio_px=10)
        ui.rect(self, self.pantalla_ancho, self.pantalla_alto, estilo.PAPEL, (cx, self.pantalla_cy), z=0.007, radio_px=9)
        # Barra de estado en la franja de arriba del cuerpo (tinta sobre crema).
        if minutos is None:
            ahora = datetime.datetime.now()
            minutos = ahora.hour * 60 + ahora.minute
        y = cy + alto / 2 - self.BARRA / 2
        x_izq, x_der = cx - ancho / 2 + 0.03, cx + ancho / 2 - 0.03
        Text("Civitas", parent=self, origin=(-0.5, 0), position=(x_izq, y, 0.0), scale=escala_fuente(13),
             font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
        Text(pc_hora(minutos), parent=self, origin=(0.5, 0), position=(x_der - 0.06, y, 0.0), scale=escala_fuente(13),
             font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
        ui.rect(self, 0.046, 0.02, estilo.TINTA, (x_der - 0.022, y), z=-0.001, radio_px=3)
        ui.rect(self, 0.04, 0.014, (88, 190, 120), (x_der - 0.022, y), z=-0.002, radio_px=2)

    def pantalla(self):
        return self.centro[0], self.pantalla_cy, self.pantalla_ancho, self.pantalla_alto


def pc_hora(minutos):
    from frontend.minijuegos_visual.chat_visual_calculos import hora_texto
    return hora_texto(minutos)


def boton_sello(parent, texto, ancho, alto, centro, tono=None, z=0.0):
    """Pulsador/sello plano de tinta con texto: sombra, borde y relleno."""
    raiz = Entity(parent=parent, position=(centro[0], centro[1], z))
    sombra_plana(raiz, ancho, alto, (0, 0), z=0.003)
    ui.rect(raiz, ancho + 0.006, alto + 0.006, estilo.TINTA, (0, 0), z=0.002, radio_px=9)
    ui.rect(raiz, ancho, alto, tono or estilo.COLOR_ACENTO, (0, 0), z=0.001, radio_px=8)
    Text(texto, parent=raiz, origin=(0, 0), position=(0, 0, -0.002), scale=escala_fuente(16),
         font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
    return raiz


def trazo(parent, a, b, grosor, tono, z=0.0):
    """Segmento recto (un quad girado) entre los puntos a y b."""
    largo = math.hypot(b[0] - a[0], b[1] - a[1])
    return Entity(parent=parent, model="quad", color=rgba(tono), position=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z),
                  scale=(largo + grosor * 0.6, grosor), rotation_z=math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))


def marca(parent, tipo, centro, tam=0.036, z=0.0):
    """Palomita verde ('bien') o aspa roja ('mal') dibujada con trazos, con contorno de tinta. Devuelve la raíz."""
    raiz = Entity(parent=parent, position=(centro[0], centro[1], z))
    if tipo == "bien":
        pts = [(x * tam, y * tam) for x, y in pc.puntos_palomita()]
        segs, tono = list(zip(pts, pts[1:])), estilo.ESTADO_EXITO
    else:
        segs, tono = [((a[0] * tam, a[1] * tam), (b[0] * tam, b[1] * tam)) for a, b in pc.puntos_aspa()], estilo.ESTADO_ERROR
    for a, b in segs:
        trazo(raiz, a, b, tam * 0.36, estilo.TINTA, z=0.002)
    for a, b in segs:
        trazo(raiz, a, b, tam * 0.2, tono, z=0.0)
    return raiz


class GloboRespuesta(ui.Tarjeta):
    """Respuesta como globo de PAPEL (fondo crema, texto tinta, borde de tinta de 3 px, sombra plana, cola hacia el móvil y
    número en círculo amarillo). Sigue siendo una ui.Tarjeta (fijar_estado/fijar_foco/habilitada/al_clic/estado) y reaplica
    su estilo en cada cambio de estado; el borde amarillo grueso solo sale con el foco."""

    FONDOS = {"correcta": (214, 242, 222), "incorrecta": (250, 218, 218), "descartada": (222, 220, 212)}
    RESERVA = 0.045
    _marca = None
    _marca_tipo = ""

    def __init__(self, ancho, alto, cuerpo, numero, px=17, **opciones):
        super().__init__(ancho, alto, cuerpo, "", px, 13, tono=estilo.PAPEL, reserva=self.RESERVA, **opciones)
        self.cuerpo.color = rgba(estilo.TINTA)
        self.cuerpo.x += self.RESERVA
        sombra_plana(self, ancho, alto, (0, 0), z=0.0055)
        x, y, giro = pc.cola_globo("izq", ancho, alto, tam=0.02)
        Entity(parent=self, model="quad", color=rgba(estilo.TINTA), position=(x - 0.006, y, 0.0045), scale=0.024, rotation_z=giro)
        Entity(parent=self, model="quad", color=rgba(estilo.PAPEL), position=(x - 0.002, y, 0.0035), scale=0.018, rotation_z=giro)
        cx, cy = -ancho / 2 + 0.032, alto / 2 - 0.032
        Entity(parent=self, model="circle", color=rgba(estilo.TINTA), position=(cx, cy, -0.01), scale=0.046)
        Entity(parent=self, model="circle", color=rgba(estilo.COLOR_ACENTO), position=(cx, cy, -0.011), scale=0.04)
        Text(str(numero), parent=self, origin=(0, 0), position=(cx, cy, -0.012), scale=escala_fuente(15),
             font=tipografia.FUENTE_TITULO, color=rgba(estilo.TINTA))
        self._pintar()

    def _pintar(self):
        if self.is_empty() or self.borde.is_empty():
            return
        borde, grosor, _etiqueta = self.ESTADOS[self.estado]
        if self.estado == "normal":
            borde, grosor = estilo.TINTA, 3
        if self._foco:
            borde, grosor = ui.COLOR_FOCO, max(grosor, 6)
        extra = ui.a_unidades(grosor) if hasattr(ui, "a_unidades") else grosor / 835.0
        if getattr(self, "_grosor_pintado", None) != grosor:
            self._grosor_pintado = grosor
            self.borde.model = ui.modelo_redondeado(self.ancho + 2 * extra, self.alto + 2 * extra, 9 + grosor)
            self.borde.scale = (self.ancho + 2 * extra, self.alto + 2 * extra)
        self.borde.color = rgba(borde)
        self.etiqueta.text = ""                  # sin «>> ELEGIR» ni etiquetas: el borde y las marcas lo dicen
        self.fondo.color = rgba(self.FONDOS.get(self.estado, estilo.PAPEL))
        self._pintar_marca()

    def _pintar_marca(self):
        tipo = {"correcta": "bien", "incorrecta": "mal"}.get(self.estado, "")
        if getattr(self, "_marca_tipo", "") == tipo:
            return
        self._marca_tipo = tipo
        if self._marca is not None:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self._marca)
            self._marca = None
        if tipo:
            self._marca = marca(self, tipo, (self.ancho / 2 - 0.04, 0.0), 0.04, z=-0.012)

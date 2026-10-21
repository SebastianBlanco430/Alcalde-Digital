# Vista de la red social «Civitas» de la EscenaJuego (Ursina, en camera.ui): un cliente tipo X con
# tema oscuro de cómic (tinta, Atkinson, amarillo y cian) dibujado con quads, texto y los iconos de
# red_social_iconos. Es solo VISTA: no decide nada; EscenaJuego le pasa la publicación activa y los
# callbacks de decisión, y todo lo que se calcula (autores, contadores, comentarios, tweens) vive en
# red_social_calculos.py (puro, con tests).
#
# Layout (unidades de camera.ui, escena 16:9: x en ±0.889, y en ±0.5):
#   barra superior : logo «Civitas» + los tres indicadores (BarraIndicador, `barras`)
#   izquierda      : navegación (Inicio, Explorar, Notificaciones, Mensajes, Perfil) + «Publicar» + perfil
#   centro         : pestañas «Para ti / Siguiendo» + píldora «Misión: ...», la publicación activa como
#                    tarjeta real (avatar, nombre, insignia, @usuario, hora, texto, vista previa, acciones
#                    con contadores, botones «Compartir» / «Reportar») y el hilo de respuestas falsas
#   derecha        : «Tendencias», «A quién seguir» y el panel de alcance (PanelPropagacion, misma API;
#                    sustituye a «A quién seguir» mientras hay una propagación a la vista)
#
# El contenido de la publicación se reutiliza (no se crean entidades por noticia): cambiar de noticia
# solo cambia textos, colores y texturas, así el número de entidades es fijo (≈ 260).

from panda3d.core import TextNode
from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend import red_social_calculos as calc
from frontend import red_social_iconos as ico
from frontend.componentes import (
    BarraIndicador, BotonPeligro, BotonPrimario, a_unidades, escala_fuente, modelo_redondeado,
    medidas_tinta, panel_tinta, rgb,
)
from frontend.panel_propagacion import PanelPropagacion
from frontend.texto import envolver_texto

ANCHO_ESCENA = 16 / 9
MITAD = ANCHO_ESCENA / 2

# --- Geometría de las tres columnas ---
ANCHO_NAV = 0.31
X_NAV = -MITAD
X_FEED_IZQ = -MITAD + ANCHO_NAV
ANCHO_FEED = 0.93
X_FEED_DER = X_FEED_IZQ + ANCHO_FEED
CX_FEED = (X_FEED_IZQ + X_FEED_DER) / 2
ANCHO_DER = MITAD - X_FEED_DER
CX_DER = (X_FEED_DER + MITAD) / 2
ANCHO_TARJETA_DER = ANCHO_DER - 0.048
ALTO_BARRA = 0.115
Y_BASE_BARRA = 0.5 - ALTO_BARRA

# --- Colores propios de la red (además de estilo.py) ---
COLOR_LINEA = (58, 62, 88)          # separadores finos
COLOR_VERDE = (60, 200, 120)        # republicar
COLOR_ROSA = (244, 70, 130)         # me gusta
COLOR_ROJO = estilo.ESTADO_ERROR    # reportar
COLOR_TENUE = estilo.COLOR_TEXTO_TENUE

PX_NOMBRE, PX_CUERPO, PX_META, PX_RESPUESTA = 20, 21, 16, 17
LINEA_CUERPO = 1.3
LINEA_RESPUESTA = 1.25


# ----------------------------------------------------------------------------- utilidades

# Mide cadenas con las mismas fuentes con que Ursina dibuja el texto (px de 600).
class Medidor:

    def __init__(self):
        normal = Text("", add_to_scene_entities=False)
        negrita = Text("", font=tipografia.FUENTE_TITULO, add_to_scene_entities=False)
        self._fuentes = {False: normal.font, True: negrita.font}
        from ursina import destroy
        destroy(normal)
        destroy(negrita)

    def ancho(self, cadena, px, negrita=False):
        nodo = TextNode("medida_red_social")
        nodo.setFont(self._fuentes[negrita])
        return nodo.calcWidth(cadena) * a_unidades(px)

    def funcion(self, px, negrita=False):
        return lambda cadena: self.ancho(cadena, px, negrita)


def _texto(padre, cadena, px, pos, tono, origen=(-0.5, 0), negrita=False, z=-0.01):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena, parent=padre, origin=origen, position=(pos[0], pos[1], z),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


def _rect(padre, ancho, alto, tono, pos, radio_px=0, z=0):
    modelo = modelo_redondeado(ancho, alto, radio_px) if radio_px else "quad"
    return Entity(parent=padre, model=modelo, scale=(ancho, alto), position=(pos[0], pos[1], z), color=rgb(tono))


def _icono(padre, nombre, lado, pos, tono, lleno=False, z=-0.01):
    return Entity(parent=padre, model="quad", texture=ico.textura_icono(nombre, lleno), scale=lado,
                  position=(pos[0], pos[1], z), color=rgb(tono))


# Ajusta un panel_tinta ya creado a un nuevo tamaño y centro (el radio queda en el de la malla nueva).
def _redimensionar_panel(panel, ancho, alto, centro_y, radio_px=estilo.RADIO_PANEL_PX):
    borde, (sx, sy) = medidas_tinta()
    radio = radio_px + estilo.GROSOR_BORDE_PX
    if panel.sombra is not None:
        panel.sombra.model = modelo_redondeado(ancho + 2 * borde, alto + 2 * borde, radio)
        panel.sombra.scale = (ancho + 2 * borde, alto + 2 * borde)
        panel.sombra.position = (sx, centro_y + sy, panel.sombra.z)
    panel.borde.model = modelo_redondeado(ancho + 2 * borde, alto + 2 * borde, radio)
    panel.borde.scale = (ancho + 2 * borde, alto + 2 * borde)
    panel.borde.position = (0, centro_y, panel.borde.z)
    panel.fondo.model = modelo_redondeado(ancho, alto, radio_px)
    panel.fondo.scale = (ancho, alto)
    panel.fondo.position = (0, centro_y, panel.fondo.z)


# ----------------------------------------------------------------------------- piezas

# Avatar circular con borde de tinta y la inicial del autor.
class Avatar(Entity):

    def __init__(self, diametro, **opciones):
        super().__init__(**opciones)
        self.diametro = diametro
        Entity(parent=self, model="circle", scale=diametro, color=rgb(estilo.TINTA), z=0.002)
        self.disco = Entity(parent=self, model="circle", scale=diametro * 0.86, z=0.001)
        px = max(17, int(diametro * 600 * 0.5))
        self.letra = Text("", parent=self, origin=(0, 0), position=(0, 0.0015, -0.002),
                          scale=escala_fuente(px), font=tipografia.FUENTE_TITULO)

    def fijar(self, autor):
        self.disco.color = rgb(autor["color_avatar"])
        self.letra.text = autor["inicial"]
        self.letra.color = rgb(autor["color_letra"])


# Insignia de verificado (azul = cuenta, dorada = organización); invisible si no hay.
class Insignia(Entity):

    def __init__(self, lado, **opciones):
        super().__init__(model="quad", scale=lado, enabled=False, **opciones)
        self.lado = lado

    def fijar(self, tipo, x, y):
        self.enabled = tipo in ("azul", "dorada")
        if self.enabled:
            self.texture = ico.textura_verificado(tipo)
            self.position = (x, y, self.z)


# Icono de acción con su contador (responder, republicar, me gusta, vistas, guardar).
class AccionPost(Entity):

    LADO = 0.036

    def __init__(self, nombre, con_cuenta=True, **opciones):
        super().__init__(**opciones)
        self.nombre = nombre
        self.icono = Entity(parent=self, model="quad", scale=self.LADO, texture=ico.textura_icono(nombre),
                            color=rgb(COLOR_TENUE))
        self.cuenta = None
        if con_cuenta:
            self.cuenta = Text("", parent=self, origin=(-0.5, 0), position=(self.LADO * 0.75, 0, -0.001),
                               scale=escala_fuente(17), color=rgb(COLOR_TENUE))

    def fijar_cuenta(self, n):
        if self.cuenta is not None:
            self.cuenta.text = calc.formatear_numero(n)

    def fijar_estado(self, lleno, tono):
        self.icono.texture = ico.textura_icono(self.nombre, lleno)
        self.icono.color = rgb(tono)
        if self.cuenta is not None:
            self.cuenta.color = rgb(tono)

    def fijar_escala(self, factor):
        self.icono.scale = self.LADO * factor


# Aviso emergente abajo del feed: icono de color + texto; sube y se desvanece.
class Aviso(Entity):

    def __init__(self, medidor, **opciones):
        super().__init__(enabled=False, **opciones)
        self._medidor = medidor
        self.panel = panel_tinta(self, 0.3, 0.06, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX)
        self.icono = Entity(parent=self, model="quad", scale=0.034, z=-0.01)
        self.texto = Text("", parent=self, origin=(-0.5, 0), scale=escala_fuente(19), font=tipografia.FUENTE_TITULO,
                          color=rgb(estilo.COLOR_TEXTO), position=(0, 0, -0.01))
        self.y_reposo = 0.0

    def preparar(self, cadena, nombre_icono, tono, lleno=True):
        ancho_texto = self._medidor.ancho(cadena, 19, True)
        ancho = ancho_texto + 0.034 + 0.07
        _redimensionar_panel(self.panel, ancho, 0.06, 0, estilo.RADIO_TARJETA_PX)
        izquierda = -ancho / 2
        self.icono.texture = ico.textura_icono(nombre_icono, lleno)
        self.icono.color = rgb(tono)
        self.icono.position = (izquierda + 0.03 + 0.017, 0, -0.01)
        self.texto.text = cadena
        self.texto.position = (izquierda + 0.03 + 0.034 + 0.014, 0, -0.01)


# ----------------------------------------------------------------------------- publicación

# Tarjeta de la publicación activa: toda su geometría se recoloca en `mostrar(datos)`.
class TarjetaPost(Entity):

    ANCHO = ANCHO_FEED - 0.03
    PAD = 0.022
    LADO_AVATAR = 0.066
    ALTO_IMAGEN = 0.13
    ALTO_ENLACE = 0.105
    ALTO_ACCIONES = 0.05
    ALTO_BOTON = 0.068
    Y_TOP = 0.305

    def __init__(self, medidor, al_compartir, al_reportar, **opciones):
        super().__init__(**opciones)
        self.medidor = medidor
        self.datos = None
        self.lineas = []
        w = self.ANCHO
        x0 = -w / 2 + self.PAD
        self.x0 = x0
        self.panel = panel_tinta(self, w, 0.6, tono=estilo.COLOR_PANEL, radio_px=estilo.RADIO_TARJETA_PX,
                                 position=(0, 0, 0.1))
        # Cabecera.
        self.avatar = Avatar(self.LADO_AVATAR, parent=self, z=-0.01)
        self.nombre = _texto(self, "", PX_NOMBRE, (0, 0), estilo.COLOR_TEXTO, negrita=True)
        self.insignia = Insignia(0.028, parent=self, z=-0.01)
        self.meta = _texto(self, "", PX_META, (0, 0), COLOR_TENUE)
        self.mas = _icono(self, "mas", 0.04, (0, 0), COLOR_TENUE)
        # Cuerpo.
        self.cuerpo = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(PX_CUERPO),
                           color=rgb(estilo.COLOR_TEXTO), z=-0.01)
        self.cuerpo.line_height = LINEA_CUERPO
        # Vista previa: imagen o enlace.
        self.imagen = Entity(parent=self, model="quad", z=-0.01, enabled=False)
        self.enlace = panel_tinta(self, w - 2 * self.PAD, self.ALTO_ENLACE, tono=estilo.COLOR_FONDO,
                                  radio_px=estilo.RADIO_CHIP_PX, sombra=False, borde_px=2, z=-0.005)
        self.enlace.enabled = False
        self.enlace_miniatura = Entity(parent=self.enlace, model="quad", z=-0.01)
        self.enlace_dominio = _texto(self.enlace, "", PX_META, (0, 0), COLOR_TENUE, z=-0.01)
        self.enlace_titulo = Text("", parent=self.enlace, origin=(-0.5, 0.5), scale=escala_fuente(PX_RESPUESTA),
                                  font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO), z=-0.01)
        self.enlace_titulo.line_height = 1.2
        # Acciones.
        self.linea_acciones = _rect(self, w - 2 * self.PAD, 0.003, COLOR_LINEA, (0, 0), z=-0.005)
        self.acciones = {
            "respuestas": AccionPost("responder", parent=self, z=-0.01),
            "republicaciones": AccionPost("republicar", parent=self, z=-0.01),
            "me_gusta": AccionPost("me_gusta", parent=self, z=-0.01),
            "vistas": AccionPost("vistas", parent=self, z=-0.01),
            "guardar": AccionPost("guardar", con_cuenta=False, parent=self, z=-0.01),
        }
        # Decisión: los dos botones de siempre (misma API que antes).
        self.boton_compartir = BotonPrimario("Compartir", al_clic=al_compartir, ancho=0.36, alto=self.ALTO_BOTON,
                                             parent=self, z=-0.02, tamano_fuente_px=22)
        self.boton_reportar = BotonPeligro("Reportar", al_clic=al_reportar, ancho=0.30, alto=self.ALTO_BOTON,
                                           parent=self, z=-0.02, tamano_fuente_px=22)
        self.boton_reportar.text_entity.font = tipografia.FUENTE_TITULO
        for boton, nombre, tono in ((self.boton_compartir, "republicar", estilo.COLOR_ACENTO_TEXTO),
                                    (self.boton_reportar, "bandera", (250, 244, 228))):
            lado_x, lado_y = 0.038 / boton.base_scale[0], 0.038 / boton.base_scale[1]
            Entity(parent=boton, model="quad", texture=ico.textura_icono(nombre), color=rgb(tono),
                   scale=(lado_x, lado_y), position=(-0.5 + 0.045 / boton.base_scale[0], 0, -0.1))
        self._cuentas = {}
        self.altura = 0.5
        self.y_base = 0.0

    # -- contenido --

    def _colocar_cabecera(self, autor, hora, y_top):
        x0 = self.x0
        yc = y_top - self.PAD - self.LADO_AVATAR / 2
        self.avatar.position = (x0 + self.LADO_AVATAR / 2, yc, self.avatar.z)
        self.avatar.fijar(autor)
        xt = x0 + self.LADO_AVATAR + 0.016
        self.nombre.text = autor["nombre"]
        self.nombre.position = (xt, yc + 0.015, -0.01)
        ancho_nombre = self.medidor.ancho(autor["nombre"], PX_NOMBRE, True)
        self.insignia.fijar(autor["verificado"], xt + ancho_nombre + 0.022, yc + 0.015)
        self.meta.text = f"{autor['handle']} · {hora}"
        self.meta.position = (xt, yc - 0.019, -0.01)
        self.mas.position = (x0 + self.ANCHO - 2 * self.PAD - 0.014, yc, -0.01)
        return yc - self.LADO_AVATAR / 2

    def mostrar(self, datos):
        self.datos = datos
        w_util = self.ANCHO - 2 * self.PAD
        x0 = self.x0
        y = self.Y_TOP
        y = self._colocar_cabecera(datos["autor"], datos["hora"], y) - 0.014
        # Cuerpo envuelto con la medida real.
        medir = self.medidor.funcion(PX_CUERPO)
        self.lineas = envolver_texto(datos["texto"], medir, w_util) or [""]
        self.cuerpo.text = "\n".join(self.lineas)
        self.cuerpo.position = (x0, y, -0.01)
        alto_cuerpo = len(self.lineas) * a_unidades(PX_CUERPO) * LINEA_CUERPO
        y -= alto_cuerpo + 0.016
        # Vista previa.
        media = datos["media"]
        self.imagen.enabled = False
        self.enlace.enabled = False
        if media["tipo"] == "imagen":
            alto = self.ALTO_IMAGEN
            px_ancho = 640
            px_alto = max(40, round(px_ancho * alto / w_util))
            self.imagen.texture = ico.textura_vista_previa(media["variante"], media["semilla"], px_ancho, px_alto)
            self.imagen.scale = (w_util, alto)
            self.imagen.position = (0, y - alto / 2, -0.01)
            self.imagen.enabled = True
            y -= alto + 0.016
        elif media["tipo"] == "enlace":
            alto = self.ALTO_ENLACE
            self.enlace.position = (0, y - alto / 2, -0.005)
            self.enlace.enabled = True
            lado = alto - 0.016
            self.enlace_miniatura.texture = ico.textura_vista_previa(media["variante"], media["semilla"], 128, 128)
            self.enlace_miniatura.scale = lado
            self.enlace_miniatura.position = (-w_util / 2 + 0.008 + lado / 2, 0, -0.01)
            xt = -w_util / 2 + lado + 0.026
            self.enlace_dominio.text = media["dominio"]
            self.enlace_dominio.position = (xt, alto / 2 - 0.022, -0.01)
            ancho_t = w_util - lado - 0.04
            lineas = envolver_texto(media["titulo_enlace"], self.medidor.funcion(PX_RESPUESTA, True), ancho_t) or [""]
            self.enlace_titulo.text = "\n".join(lineas[:2])
            self.enlace_titulo.position = (xt, alto / 2 - 0.04, -0.01)
            y -= alto + 0.016
        # Acciones.
        self.linea_acciones.position = (0, y + 0.004, -0.005)
        yc = y - 0.008 - self.ALTO_ACCIONES / 2
        pasos = (0.0, 0.2, 0.4, 0.6, 0.82)
        for paso, nombre in zip(pasos, ("respuestas", "republicaciones", "me_gusta", "vistas", "guardar")):
            self.acciones[nombre].position = (x0 + 0.02 + paso * w_util * 0.98, yc, -0.01)
        self.restaurar_acciones(datos["contadores"])
        y = yc - self.ALTO_ACCIONES / 2 - 0.012
        # Decisión.
        yb = y - 0.004 - self.ALTO_BOTON / 2
        separacion = 0.04
        total = self.boton_compartir.base_scale[0] + separacion + self.boton_reportar.base_scale[0]
        izq = -total / 2
        self.boton_compartir.position = (izq + self.boton_compartir.base_scale[0] / 2, yb, -0.02)
        self.boton_reportar.position = (izq + self.boton_compartir.base_scale[0] + separacion
                                        + self.boton_reportar.base_scale[0] / 2, yb, -0.02)
        fondo = yb - self.ALTO_BOTON / 2 - self.PAD
        self.altura = self.Y_TOP - fondo
        _redimensionar_panel(self.panel, self.ANCHO, self.altura, (self.Y_TOP + fondo) / 2, estilo.RADIO_TARJETA_PX)
        self.panel.borde.color = rgb(estilo.TINTA)
        self.fondo_y = fondo

    # Contadores y estados de los iconos de acción a su valor inicial (sin animación).
    def restaurar_acciones(self, contadores):
        self._cuentas = dict(contadores)
        for nombre in ("respuestas", "republicaciones", "me_gusta", "vistas"):
            accion = self.acciones[nombre]
            accion.fijar_cuenta(contadores[nombre])
            accion.fijar_estado(False, COLOR_TENUE)
            accion.fijar_escala(1.0)
        self.acciones["guardar"].fijar_estado(False, COLOR_TENUE)
        self.panel.borde.color = rgb(estilo.TINTA)

    def fijar_cuenta(self, nombre, valor):
        self._cuentas[nombre] = valor
        self.acciones[nombre].fijar_cuenta(valor)

    def cuentas(self):
        return dict(self._cuentas)

    def texto_dentro_de_la_tarjeta(self):
        limites = self.cuerpo.getTightBounds(self)
        if limites is None:
            return True
        minimo, maximo = limites
        return minimo.x >= -self.ANCHO / 2 and maximo.x <= self.ANCHO / 2


# Hilo de respuestas (3 filas reutilizables).
class FilaRespuesta(Entity):

    LADO_AVATAR = 0.05

    def __init__(self, medidor, **opciones):
        super().__init__(**opciones)
        self.medidor = medidor
        self.avatar = Avatar(self.LADO_AVATAR, parent=self, z=-0.01)
        self.nombre = _texto(self, "", PX_RESPUESTA, (0, 0), estilo.COLOR_TEXTO, negrita=True)
        self.insignia = Insignia(0.024, parent=self, z=-0.01)
        self.meta = _texto(self, "", PX_META, (0, 0), COLOR_TENUE)
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(PX_RESPUESTA),
                          color=rgb(estilo.COLOR_TEXTO), z=-0.01)
        self.texto.line_height = LINEA_RESPUESTA
        self.corazon = _icono(self, "me_gusta", 0.026, (0, 0), COLOR_TENUE)
        self.me_gusta = _texto(self, "", PX_META, (0, 0), COLOR_TENUE)
        self.linea = _rect(self, TarjetaPost.ANCHO - 0.04, 0.002, COLOR_LINEA, (0, 0), z=0)
        self.alto = 0.1
        self.lineas = []

    # Cuánto mide una respuesta (sin colocarla), para decidir cuántas caben.
    @staticmethod
    def altura_de(medidor, texto, ancho_texto):
        lineas = envolver_texto(texto, medidor.funcion(PX_RESPUESTA), ancho_texto) or [""]
        return 0.03 + 0.012 + len(lineas) * a_unidades(PX_RESPUESTA) * LINEA_RESPUESTA + 0.022

    @staticmethod
    def ancho_texto():
        return TarjetaPost.ANCHO - 2 * TarjetaPost.PAD - FilaRespuesta.LADO_AVATAR - 0.016

    # Coloca la fila con su borde superior en `y_top` (coordenadas de escena); devuelve su alto.
    def mostrar(self, comentario, y_top, x_izq):
        autor = comentario["autor"]
        yc = y_top - 0.012 - self.LADO_AVATAR / 2
        self.avatar.position = (x_izq + self.LADO_AVATAR / 2, yc, self.avatar.z)
        self.avatar.fijar(autor)
        xt = x_izq + self.LADO_AVATAR + 0.016
        yn = y_top - 0.024
        self.nombre.text = autor["nombre"]
        self.nombre.position = (xt, yn, -0.01)
        ancho_nombre = self.medidor.ancho(autor["nombre"], PX_RESPUESTA, True)
        self.insignia.fijar(autor["verificado"], xt + ancho_nombre + 0.018, yn)
        despues = xt + ancho_nombre + (0.04 if autor["verificado"] else 0.012)
        self.meta.text = f"{autor['handle']} · {comentario['hora']}"
        self.meta.position = (despues, yn, -0.01)
        self.lineas = envolver_texto(comentario["texto"], self.medidor.funcion(PX_RESPUESTA), self.ancho_texto()) or [""]
        self.texto.text = "\n".join(self.lineas)
        self.texto.position = (xt, y_top - 0.04, -0.01)
        alto = 0.03 + 0.012 + len(self.lineas) * a_unidades(PX_RESPUESTA) * LINEA_RESPUESTA + 0.022
        x_der = x_izq + TarjetaPost.ANCHO - 2 * TarjetaPost.PAD
        cuenta = calc.formatear_numero(comentario["me_gusta"])
        ancho_cuenta = self.medidor.ancho(cuenta, PX_META)
        self.me_gusta.text = cuenta
        self.me_gusta.position = (x_der - ancho_cuenta, yn, -0.01)
        self.corazon.position = (x_der - ancho_cuenta - 0.022, yn, -0.01)
        self.linea.position = (x_izq - 0.0 + (TarjetaPost.ANCHO - 2 * TarjetaPost.PAD) / 2, y_top - alto, 0)
        self.alto = alto
        return alto


# ----------------------------------------------------------------------------- vista completa

class VistaRedSocial(Entity):

    DURACION_ENTRADA = 0.4
    DURACION_EFECTO = 0.5
    DURACION_AVISO = 1.7
    Y_MIN_FEED = -0.455

    def __init__(self, nombres_indicadores, al_compartir, al_reportar, **opciones):
        super().__init__(**opciones)
        self.medidor = Medidor()
        self.animador = calc.Animador()
        self._efecto_activo = False
        self._hay_pendiente = False
        self._pendiente = None
        self._texto_actual = object()
        self._datos = None
        self._alcance_visible = None
        self._aviso_t = None

        # Fondo opaco: toda la escena es la «aplicación».
        _rect(self, ANCHO_ESCENA, 1.0, estilo.COLOR_FONDO, (0, 0), z=0.9)
        self._construir_columnas()
        self._construir_barra_superior(nombres_indicadores)
        self._construir_nav()
        self._construir_cabecera_feed()
        # Feed: publicación + respuestas.
        self.grupo_post = Entity(parent=self, position=(CX_FEED, 0, 0.3))
        self.tarjeta = TarjetaPost(self.medidor, al_compartir, al_reportar, parent=self.grupo_post)
        self.boton_compartir = self.tarjeta.boton_compartir
        self.boton_reportar = self.tarjeta.boton_reportar
        self.grupo_respuestas = Entity(parent=self, position=(CX_FEED, 0, 0.3))
        self.filas = [FilaRespuesta(self.medidor, parent=self.grupo_respuestas) for _ in range(3)]
        self._construir_columna_derecha()
        # Aviso emergente y sello de misión completada.
        self.aviso = Aviso(self.medidor, parent=self, position=(CX_FEED, -0.455, -0.2))
        self.sello = Entity(parent=self, position=(CX_FEED, -0.02, -0.25), rotation_z=-3, enabled=False)
        self.sello.panel = panel_tinta(self.sello, 0.62, 0.1, tono=(60, 170, 100), radio_px=estilo.RADIO_PANEL_PX)
        self.sello.texto = Text("", parent=self.sello, origin=(0, 0), position=(0, 0, -0.01),
                                scale=escala_fuente(34), font=tipografia.FUENTE_TITULO,
                                color=rgb((250, 244, 228)))

    # -- construcción --

    def _construir_columnas(self):
        for x in (X_FEED_IZQ, X_FEED_DER):
            _rect(self, 0.003, 1.0 - ALTO_BARRA, COLOR_LINEA, (x, -ALTO_BARRA / 2), z=0.5)

    def _construir_barra_superior(self, nombres):
        _rect(self, ANCHO_ESCENA, ALTO_BARRA, estilo.COLOR_PANEL, (0, 0.5 - ALTO_BARRA / 2), z=0.6)
        _rect(self, ANCHO_ESCENA, 0.005, estilo.TINTA, (0, Y_BASE_BARRA), z=0.55)
        # Logo propio: rombo con «C» + palabra «Civitas» con sombra de tinta.
        Entity(parent=self, model="quad", texture=ico.textura_logo(), scale=0.085, position=(X_NAV + 0.06, 0.5 - ALTO_BARRA / 2, 0.1))
        for dx, dy, tono, z in ((0.004, -0.004, estilo.TINTA, 0.11), (0, 0, estilo.ACENTO_PRIMARIO, 0.1)):
            _texto(self, "Civitas", 30, (X_NAV + 0.12 + dx, 0.5 - ALTO_BARRA / 2 + dy), tono, negrita=True, z=z)
        # Indicadores (mismos nombres y clase de siempre).
        self.barras = {}
        ancho_bloque = 0.49
        x0 = X_FEED_IZQ + 0.02
        for i, nombre in enumerate(nombres):
            xb = x0 + i * ancho_bloque
            Entity(parent=self, model="quad", texture=_textura_indicador(nombre), scale=0.05,
                   position=(xb + 0.03, 0.5 - 0.057, 0.05))
            self.barras[nombre] = BarraIndicador(
                estilo.ETIQUETAS_INDICADORES[nombre], ancho_bloque - 0.15, parent=self,
                position=(xb + 0.07, 0.5 - 0.005, 0.05))

    def _construir_nav(self):
        items = (("inicio", "Inicio"), ("explorar", "Explorar"), ("notificaciones", "Notificaciones"),
                 ("mensajes", "Mensajes"), ("perfil", "Perfil"))
        y = Y_BASE_BARRA - 0.065
        self.nav = {}
        for i, (nombre, etiqueta) in enumerate(items):
            yi = y - i * 0.088
            activo = nombre == "inicio"
            icono = _icono(self, nombre, 0.046, (X_NAV + 0.056, yi), estilo.COLOR_TEXTO, lleno=activo, z=0.1)
            texto = _texto(self, etiqueta, 18, (X_NAV + 0.056 + 0.046, yi), estilo.COLOR_TEXTO, negrita=activo, z=0.1)
            self.nav[nombre] = (icono, texto)
        # Punto rojo de avisos sobre la campana.
        Entity(parent=self, model="circle", scale=0.016, color=rgb(COLOR_ROJO), position=(X_NAV + 0.056 + 0.016, y - 2 * 0.088 + 0.018, 0.05))
        # Botón «Publicar» (decorativo: avisa que hay que decidir sobre la publicación).
        self.boton_publicar = BotonPrimario("Publicar", al_clic=self._clic_publicar, ancho=ANCHO_NAV - 0.1, alto=0.07,
                                            parent=self, position=(X_NAV + ANCHO_NAV / 2 - 0.005, y - 5 * 0.088 - 0.01, 0.1),
                                            tamano_fuente_px=22)
        # Perfil del jugador (abajo).
        self.avatar_jugador = Avatar(0.058, parent=self, position=(X_NAV + 0.056 + 0.01, -0.43, 0.1))
        self.nombre_jugador = _texto(self, "", 18, (X_NAV + 0.056 + 0.05, -0.415), estilo.COLOR_TEXTO, negrita=True, z=0.1)
        self.rol_jugador = _texto(self, "", PX_META, (X_NAV + 0.056 + 0.05, -0.447), COLOR_TENUE, z=0.1)

    def _construir_cabecera_feed(self):
        y = Y_BASE_BARRA - 0.045
        _rect(self, ANCHO_FEED, 0.003, COLOR_LINEA, (CX_FEED, y - 0.03), z=0.5)
        _texto(self, "Para ti", 20, (X_FEED_IZQ + 0.06, y), estilo.COLOR_TEXTO, negrita=True, z=0.1)
        _rect(self, 0.085, 0.007, estilo.ACENTO_PRIMARIO, (X_FEED_IZQ + 0.06 + 0.0425, y - 0.03), radio_px=2, z=0.09)
        _texto(self, "Siguiendo", 20, (X_FEED_IZQ + 0.22, y), COLOR_TENUE, z=0.1)
        # Píldora de misión (a la derecha).
        self.pildora = panel_tinta(self, 0.4, 0.05, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_CHIP_PX,
                                   sombra=False, borde_px=2, position=(X_FEED_DER - 0.25, y, 0.1))
        self.texto_mision = Text("", parent=self.pildora, origin=(0, 0), position=(0, 0, -0.01),
                                 scale=escala_fuente(18), color=rgb(estilo.COLOR_ACENTO))
        self.pildora.enabled = False
        self._y_cabecera = y

    def _construir_columna_derecha(self):
        w = ANCHO_TARJETA_DER
        x_izq = CX_DER - w / 2
        # Tendencias.
        alto_t = 0.27
        y_t = Y_BASE_BARRA - 0.02 - alto_t / 2
        panel_tinta(self, w, alto_t, tono=estilo.COLOR_PANEL, radio_px=estilo.RADIO_TARJETA_PX,
                    position=(CX_DER, y_t, 0.2))
        _texto(self, "Tendencias para ti", 20, (x_izq + 0.022, y_t + alto_t / 2 - 0.035), estilo.COLOR_TEXTO, negrita=True, z=0.1)
        self.tendencias = []
        for i in range(3):
            yf = y_t + alto_t / 2 - 0.082 - i * 0.066
            categoria = _texto(self, "", PX_META, (x_izq + 0.022, yf), COLOR_TENUE, z=0.1)
            etiqueta = _texto(self, "", 19, (x_izq + 0.022, yf - 0.029), estilo.COLOR_TEXTO, negrita=True, z=0.1)
            cuenta = _texto(self, "", PX_META, (x_izq + w - 0.022, yf), COLOR_TENUE, origen=(0.5, 0), z=0.1)
            self.tendencias.append((categoria, etiqueta, cuenta))
        y_borde = y_t - alto_t / 2 - 0.02
        # Ranura que alterna entre «A quién seguir» y el panel de alcance.
        alto_slot = 0.55
        y_slot = y_borde - alto_slot / 2
        # --- Alcance ---
        self.slot_alcance = Entity(parent=self)
        panel_tinta(self.slot_alcance, w, alto_slot, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_TARJETA_PX,
                    position=(CX_DER, y_slot, 0.2))
        self.panel_propagacion = PanelPropagacion(parent=self, position=(CX_DER, y_slot, 0.1))
        self.slot_alcance.enabled = False
        # --- A quién seguir + consejo ---
        self.slot_seguir = Entity(parent=self)
        alto_s = 0.3
        y_s = y_borde - alto_s / 2
        panel_tinta(self.slot_seguir, w, alto_s, tono=estilo.COLOR_PANEL, radio_px=estilo.RADIO_TARJETA_PX,
                    position=(CX_DER, y_s, 0.2))
        _texto(self.slot_seguir, "A quién seguir", 20, (x_izq + 0.022, y_s + alto_s / 2 - 0.035), estilo.COLOR_TEXTO,
               negrita=True, z=0.1)
        self.seguir = []
        for i in range(3):
            yf = y_s + alto_s / 2 - 0.1 - i * 0.075
            avatar = Avatar(0.05, parent=self.slot_seguir, position=(x_izq + 0.022 + 0.025, yf, 0.1))
            nombre = _texto(self.slot_seguir, "", 17, (x_izq + 0.1, yf + 0.014), estilo.COLOR_TEXTO, negrita=True, z=0.1)
            insignia = Insignia(0.024, parent=self.slot_seguir, z=0.1)
            handle = _texto(self.slot_seguir, "", PX_META, (x_izq + 0.1, yf - 0.016), COLOR_TENUE, z=0.1)
            pastilla = _rect(self.slot_seguir, 0.1, 0.042, estilo.PAPEL, (x_izq + w - 0.022 - 0.05, yf), radio_px=14, z=0.1)
            _texto(self.slot_seguir, "Seguir", 17, (x_izq + w - 0.022 - 0.05, yf), estilo.TINTA, origen=(0, 0), negrita=True, z=0.09)
            self.seguir.append((avatar, nombre, insignia, handle))
        alto_c = 0.2
        y_c = y_s - alto_s / 2 - 0.02 - alto_c / 2
        panel_tinta(self.slot_seguir, w, alto_c, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX,
                    position=(CX_DER, y_c, 0.2))
        _texto(self.slot_seguir, "Consejo de Civitas", 19, (x_izq + 0.022, y_c + alto_c / 2 - 0.035), estilo.ACENTO_PRIMARIO,
               negrita=True, z=0.1)
        lineas = envolver_texto("Antes de compartir, mira quién publica, la fecha y si otras fuentes lo confirman.",
                                self.medidor.funcion(17), w - 0.044)
        Text("\n".join(lineas), parent=self.slot_seguir, origin=(-0.5, 0.5), position=(x_izq + 0.022, y_c + alto_c / 2 - 0.065, 0.1),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO)).line_height = 1.25

    # -- ciclo --

    def _clic_publicar(self):
        self.mostrar_aviso("Primero decide qué hacer con la publicación", "mas", COLOR_TENUE, lleno=False)

    # Perfil del jugador en la barra lateral.
    def fijar_jugador(self, nombre, rol):
        autor = calc.autor_jugador(nombre, rol)
        self.avatar_jugador.fijar(autor)
        medir = self.medidor.funcion(18, True)
        self.nombre_jugador.text = calc.recortar_a_ancho(nombre or "Jugador", medir, 0.19)
        self.rol_jugador.text = calc.recortar_a_ancho(str(rol or ""), self.medidor.funcion(PX_META), 0.19)

    def fijar_mision(self, cadena):
        self.texto_mision.text = cadena
        self.pildora.enabled = bool(cadena)
        if cadena:
            ancho = self.medidor.ancho(cadena, 18) + 0.05
            _redimensionar_panel(self.pildora, ancho, 0.05, 0, estilo.RADIO_CHIP_PX)
            self.pildora.x = X_FEED_DER - 0.02 - ancho / 2

    def fijar_completada(self, cadena):
        visible = bool(cadena)
        if visible and not self.sello.enabled:
            self.sello.texto.text = cadena
            ancho = self.medidor.ancho(cadena, 34, True) + 0.1
            _redimensionar_panel(self.sello.panel, ancho, 0.1, 0, estilo.RADIO_PANEL_PX)
            self.sello.enabled = True
            self.animador.agregar(0.35, lambda p: setattr(self.sello, "scale", calc.ease_out_back(p) * 1.0))
        elif not visible:
            self.sello.enabled = False
        self.sello.texto.text = cadena

    # Reinicia el estado visual al entrar a la escena.
    def reiniciar(self):
        self.animador.cancelar()
        self._efecto_activo = False
        self._hay_pendiente = False
        self._pendiente = None
        self._texto_actual = object()
        self.aviso.enabled = False
        self._aviso_t = None
        self.sello.enabled = False
        self.grupo_post.y = 0
        self.grupo_respuestas.y = 0
        self.grupo_post.setColorScale(1, 1, 1, 1)
        self.grupo_respuestas.setColorScale(1, 1, 1, 1)

    # Publicación a la vista: `texto` (None = no hay más noticias). Si hay un efecto de decisión en
    # curso se aplaza hasta que termine, para que se vea lo que hizo el jugador.
    def poner_publicacion(self, texto):
        if texto == self._texto_actual and not self._hay_pendiente:
            return
        if self._efecto_activo:
            self._hay_pendiente, self._pendiente = True, texto
            return
        self._mostrar(texto, animar=True)

    def _mostrar(self, texto, animar):
        self._texto_actual = texto
        if texto is None:
            datos = calc.publicacion_de("No hay más noticias disponibles.")
            datos["comentarios"] = []
            datos["media"] = {"tipo": "ninguna", "variante": "ciudad", "semilla": 0, "titulo_enlace": "", "dominio": ""}
            datos["autor"] = {"nombre": "Civitas", "handle": "@civitas", "inicial": "C", "color_avatar": estilo.ACENTO_PRIMARIO,
                              "color_letra": estilo.TINTA, "verificado": "dorada", "tipo": "institucion"}
            datos["hora"] = "ahora"
        else:
            datos = calc.publicacion_de(texto)
        self._datos = datos
        self.tarjeta.mostrar(datos)
        self._mostrar_respuestas(datos)
        self._mostrar_tendencias(datos)
        if animar:
            self._animar_entrada()

    def _mostrar_respuestas(self, datos):
        comentarios = datos["comentarios"]
        x_izq = -TarjetaPost.ANCHO / 2 + TarjetaPost.PAD
        y = self.tarjeta.fondo_y - 0.012
        alturas = [FilaRespuesta.altura_de(self.medidor, c["texto"], FilaRespuesta.ancho_texto()) for c in comentarios]
        cabe = calc.cuantos_caben(alturas, 0.0, y - self.Y_MIN_FEED)
        for i, fila in enumerate(self.filas):
            fila.enabled = i < cabe
            if i < cabe:
                y -= fila.mostrar(comentarios[i], y, x_izq)

    def _mostrar_tendencias(self, datos):
        for (categoria, etiqueta, cuenta), (cat, tag, n) in zip(self.tendencias, datos["tendencias"]):
            categoria.text, etiqueta.text, cuenta.text = cat, tag, n
        for (avatar, nombre, insignia, handle), autor in zip(self.seguir, datos["seguir"]):
            avatar.fijar(autor)
            nombre.text = calc.recortar_a_ancho(autor["nombre"], self.medidor.funcion(17, True), 0.19)
            x = nombre.x + self.medidor.ancho(nombre.text, 17, True) + 0.018
            insignia.fijar(autor["verificado"], x, nombre.y)
            handle.text = calc.recortar_a_ancho(autor["handle"], self.medidor.funcion(PX_META), 0.19)

    # El post y su hilo entran deslizándose desde abajo con fundido.
    def _animar_entrada(self):
        def post(p):
            e = calc.ease_out_cubic(p)
            self.grupo_post.y = -0.22 * (1 - e)
            self.grupo_post.setColorScale(1, 1, 1, min(1.0, e * 1.6))

        def respuestas(p):
            e = calc.ease_out_cubic(p)
            self.grupo_respuestas.y = -0.3 * (1 - e)
            self.grupo_respuestas.setColorScale(1, 1, 1, min(1.0, e * 1.6))

        post(0.0)
        respuestas(0.0)
        self.animador.agregar(self.DURACION_ENTRADA, post)
        self.animador.agregar(self.DURACION_ENTRADA, respuestas, retraso=0.08)

    # Efecto de decidir sobre la publicación visible: iconos que se llenan, contadores que suben, aviso.
    def iniciar_decision(self, tipo):
        self.animador.terminar_todo()        # si había una entrada/efecto en curso, termínalo
        if self._datos is None:
            return
        tarjeta = self.tarjeta
        base = tarjeta.cuentas()
        incremento = calc.incremento_por_decision(self._datos["contadores"], tipo)
        objetivo = calc.sumar_contadores(base, incremento)
        self._efecto_activo = True
        dur = self.DURACION_EFECTO
        acc = tarjeta.acciones

        def subir(p):
            for nombre in ("republicaciones", "me_gusta", "vistas"):
                if objetivo[nombre] != base[nombre]:
                    tarjeta.fijar_cuenta(nombre, calc.cuenta_animada(base[nombre], objetivo[nombre], p))

        if tipo == "compartir":
            acc["republicaciones"].fijar_estado(True, COLOR_VERDE)
            tarjeta.panel.borde.color = rgb(COLOR_VERDE)
            self.animador.agregar(0.42, lambda p: acc["republicaciones"].fijar_escala(calc.pop(p, 0.55)))
            self.animador.agregar(0.42, lambda p: self._pop_corazon(p), retraso=0.08)
            self.mostrar_aviso("Republicaste", "republicar", COLOR_VERDE, lleno=False)
        else:
            tarjeta.panel.borde.color = rgb(COLOR_ROJO)
            self.mostrar_aviso("Reportaste la publicación", "bandera", COLOR_ROJO, lleno=True)
        self.animador.agregar(dur, subir, al_fin=self._fin_efecto)

    def _pop_corazon(self, p):
        accion = self.tarjeta.acciones["me_gusta"]
        if p > 0 and accion.icono.color != rgb(COLOR_ROSA):
            accion.fijar_estado(True, COLOR_ROSA)
        accion.fijar_escala(calc.pop(p, 0.6))

    def _fin_efecto(self):
        self._efecto_activo = False
        if self._hay_pendiente:
            texto, self._pendiente, self._hay_pendiente = self._pendiente, None, False
            self._mostrar(texto, animar=True)

    # Aviso emergente: sube 0.04, se queda y se desvanece.
    def mostrar_aviso(self, cadena, icono, tono, lleno=True):
        self.aviso.preparar(cadena, icono, tono, lleno)
        self.aviso.enabled = True
        base = -0.455
        total = self.DURACION_AVISO

        def paso(p):
            t = p * total
            if t < 0.18:
                e = calc.ease_out_cubic(t / 0.18)
                alfa, dy = e, -0.04 * (1 - e)
            elif t < total - 0.3:
                alfa, dy = 1.0, 0.0
            else:
                alfa, dy = max(0.0, (total - t) / 0.3), 0.0
            self.aviso.y = base + dy
            self.aviso.setColorScale(1, 1, 1, alfa)

        def fin():
            self.aviso.enabled = False

        paso(0.0)
        self._aviso_tween_id = getattr(self, "_aviso_tween_id", 0) + 1
        mi_id = self._aviso_tween_id
        self.animador.agregar(total, lambda p: paso(p) if mi_id == self._aviso_tween_id else None,
                              al_fin=lambda: fin() if mi_id == self._aviso_tween_id else None)

    # Avanza animaciones y alterna «A quién seguir» / panel de alcance según haya propagación.
    def avanzar(self, dt):
        self.animador.avanzar(dt)
        visible = bool(self.panel_propagacion.enabled)
        if visible != self._alcance_visible:
            self._alcance_visible = visible
            self.slot_alcance.enabled = visible
            self.slot_seguir.enabled = not visible


def _textura_indicador(nombre):
    from frontend import iconos
    return iconos.textura_icono(nombre)

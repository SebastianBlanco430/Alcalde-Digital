# Pantallas del teléfono en grande (Ursina, camera.ui) y su panel lateral. Solo VISTA: no deciden nada. Las arma y las
# alimenta frontend/registro_telefono_grande.py con lo que ya calcula el control de la bandeja (ControlHabitos) o de los
# dilemas (ControlDilemas); lo que se puede calcular sin ventana vive en frontend/telefono_grande_calculos.py.
#
#   PanelLateral   a la izquierda del teléfono: título, instrucción, filas (marcar, con «[x]»), revisión con scroll y pie
#   HojaOpciones   hoja inferior de la pantalla con 2-3 opciones de hasta dos líneas (fase DECIDIR)
#   PantallaDM     chat privado de Civitas: cabecera con avatar y número, burbuja con hora y los tramos marcables
#   PantallaMuro   editor de una publicación: foto con pegatinas, leyenda, ubicación y etiquetas; publicada, comentarios
#   PantallaRectificar   banner de verificación, tu publicación con contadores y lo que se sabe (tarjetas marcables)
#   PantallaChat   grupo o cadena de reenviados (dilemas K); PantallaNotificaciones: pantalla bloqueada
#   PantallaFeed   una publicación por pantalla; la nueva entra desde abajo (dos huecos alternados)
#
# Accesibilidad: lo marcado nunca se distingue solo por color: el tramo pasa de subrayado a recuadro, el número gana un
# anillo grueso y el panel lateral dice «[x]». Sin emojis ni flechas (la fuente no los tiene).
# Número de entidades FIJO: cada pantalla crea su pool (líneas, tramos, números, chips) una vez y solo cambia textos,
# posiciones y colores al pasar de un aviso a otro.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend import red_social_calculos as rsc
from frontend import red_social_iconos as ico
from frontend import hud_contextual_calculos as hctx
from frontend import telefono_grande_calculos as tgc
from frontend.componentes import a_unidades, escala_fuente, modelo_redondeado, rgb
from frontend.componentes import boton_piel_secundario, panel_piel
from frontend.red_social_vista import AccionPost, Avatar, Medidor
from frontend.texto import envolver_texto

COLOR_CHAT = (17, 19, 28)
COLOR_CABECERA = (30, 34, 56)
COLOR_BURBUJA = (46, 50, 71)
COLOR_BURBUJA_MIA = (52, 92, 150)
COLOR_PILDORA = (40, 44, 64)
ALFA_MARCADO = 120
MAX_LINEAS_BURBUJA = 8
MAX_TRAMOS = 12
MAX_DETALLES = 4
Z_HOJA = -0.03

# Lo que se ve en el chat después de decidir (el texto pedagógico va en el panel lateral).
SISTEMA_DM = {
    "ignorar": "Dejaste el mensaje sin responder.",
    "reportar": "Reportaste este chat. Civitas lo revisará.",
}

_MEDIDOR = None


def medidor():
    global _MEDIDOR
    if _MEDIDOR is None:
        _MEDIDOR = Medidor()
    return _MEDIDOR


def alto_linea(px):
    return a_unidades(px) * 1.3


def _texto(padre, px, pos, tono=estilo.COLOR_TEXTO, origen=(-0.5, 0.5), negrita=False, z=-0.01):
    opciones = {"font": tipografia.fuente_piel(titulo=True)} if negrita else {}
    return Text("", parent=padre, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px), color=rgb(tono),
                **opciones)


def _quad(padre, tono, z=0.0, radio_px=0, ancho=0.1, alto=0.1):
    tinte = rgb(tono) if isinstance(tono, tuple) and len(tono) == 3 else tono
    modelo = modelo_redondeado(ancho, alto, radio_px) if radio_px else "quad"
    return Entity(parent=padre, model=modelo, scale=(ancho, alto), z=z, color=tinte)


def _redimensionar(entidad, ancho, alto, radio_px):
    """Cambia el tamaño de un quad redondeado (rehace la malla solo si cambió)."""
    clave = (round(ancho, 4), round(alto, 4), radio_px)
    if getattr(entidad, "_medida", None) != clave:
        entidad.model = modelo_redondeado(ancho, alto, radio_px) if radio_px else "quad"
        entidad._medida = clave
    entidad.scale = (ancho, alto)


def _poner(texto, cadena):
    cadena = cadena or ""
    if texto.text != cadena:
        texto.text = cadena if cadena else " "


def autor_simple(nombre):
    """Lo que necesita Avatar.fijar para `nombre` (color estable por nombre, letra legible encima)."""
    tono = rsc.crear_azar(nombre, "avatar").elegir(rsc.COLORES_AVATAR)
    luz = 0.299 * tono[0] + 0.587 * tono[1] + 0.114 * tono[2]
    return {"inicial": tgc.inicial(nombre), "color_avatar": tono, "color_letra": estilo.TINTA if luz > 150 else estilo.PAPEL}


def _recortar(cadena, medir, ancho):
    if medir(cadena) <= ancho:
        return cadena
    while cadena and medir(cadena + tgc.ELIPSIS) > ancho:
        cadena = cadena[:-1]
    return cadena.rstrip() + tgc.ELIPSIS


# ----------------------------------------------------------------------------- piezas marcables

class Tramo(Entity):
    """Zona tocable de un elemento marcable: subrayada sin marcar, con recuadro marcada. Llama a al_clic(numero)."""

    def __init__(self, al_clic, **opciones):
        super().__init__(enabled=False, **opciones)
        self.numero = None
        self.fondo = Entity(parent=self, model="quad", z=0.002)
        self.toque = Entity(parent=self, model="quad", collider="box", color=color.clear, z=-0.004)
        self.toque.on_click = lambda: self.numero is not None and al_clic(self.numero)

    def fijar(self, numero, x, y, ancho, alto, marcado):
        """(x, y) = esquina superior izquierda en coordenadas del padre."""
        self.numero = numero
        self.enabled = True
        self.position = (x + ancho / 2, y - alto / 2, self.z)
        if marcado:
            self.fondo.scale = (ancho + 0.008, alto)
            self.fondo.y = 0
            self.fondo.color = color.rgba32(*estilo.COLOR_ACENTO, ALFA_MARCADO)
        else:
            self.fondo.scale = (ancho, 0.004)
            self.fondo.y = -alto / 2 + 0.003
            self.fondo.color = rgb(estilo.ACENTO_SECUNDARIO)
        self.toque.scale = (ancho + 0.01, alto + 0.008)


class Numero(Entity):
    """Número del elemento (el de las teclas 1-n): círculo cian; marcado, amarillo con anillo grueso de tinta."""

    def __init__(self, al_clic, **opciones):
        super().__init__(enabled=False, **opciones)
        self.numero = None
        self.anillo = Entity(parent=self, model="circle", color=rgb(estilo.TINTA), scale=0.03, z=0.002)
        self.disco = Entity(parent=self, model="circle", scale=0.024, z=0.001, collider="sphere")
        self.disco.on_click = lambda: self.numero is not None and al_clic(self.numero)
        self.texto = Text("", parent=self, origin=(0, 0), position=(0, 0.001, -0.002), scale=escala_fuente(12),
                          color=rgb(estilo.TINTA), font=tipografia.fuente_piel(titulo=True))

    def fijar(self, numero, x, y, marcado):
        self.numero = numero
        self.enabled = True
        self.position = (x, y, self.z)
        self.texto.text = str(numero)
        self.disco.color = rgb(estilo.COLOR_ACENTO if marcado else estilo.ACENTO_SECUNDARIO)
        self.anillo.scale = 0.036 if marcado else 0.029


class Chip(Entity):
    """Fila de «Otros detalles»: un elemento que no es una parte dibujable de la pantalla. Tocable."""

    ALTO = 0.034

    def __init__(self, al_clic, ancho, **opciones):
        super().__init__(enabled=False, **opciones)
        self.numero = None
        self.ancho = ancho
        self.fondo = _quad(self, COLOR_PILDORA, z=0.002, radio_px=6, ancho=ancho, alto=self.ALTO)
        self.fondo.collider = "box"
        self.fondo.on_click = lambda: self.numero is not None and al_clic(self.numero)
        self.texto = _texto(self, 12, (-ancho / 2 + 0.045, 0), origen=(-0.5, 0))
        self.marca = Numero(al_clic, parent=self, position=(-ancho / 2 + 0.02, 0, -0.003))

    def fijar(self, numero, texto, marcado, y):
        self.numero = numero
        self.enabled = True
        self.y = y
        medir = medidor().funcion(12)
        _poner(self.texto, _recortar(("[x] " if marcado else "") + texto, medir, self.ancho - 0.06))
        self.texto.color = rgb(estilo.COLOR_ACENTO if marcado else estilo.COLOR_TEXTO)
        self.marca.fijar(numero, -self.ancho / 2 + 0.02, 0, marcado)


# ----------------------------------------------------------------------------- panel lateral

class PanelLateral(Entity):
    """Panel de texto junto al teléfono. contenido: {"titulo", "subtitulo", "texto", "instruccion", "botones":
    [(texto, marcado)] (clic = al_clic(n)), "lineas": [(texto, tono)] (con scroll), "aviso", "pie"}."""

    MAX_FILAS = tgc.MAX_ELEMENTOS
    PX_LINEA = 14

    def __init__(self, al_clic, **opciones):
        super().__init__(enabled=False, **opciones)
        ancho, alto = tgc.LATERAL_ANCHO, tgc.LATERAL_ALTO
        self.ancho_texto = ancho - 0.07
        self.marco = panel_piel(self, ancho, alto, tono=estilo.COLOR_PANEL)
        x0 = -ancho / 2 + 0.035
        self.x0 = x0
        self.arriba = alto / 2 - 0.035
        self.titulo = _texto(self, 22, (x0, self.arriba), estilo.COLOR_ACENTO, negrita=True)
        self.subtitulo = _texto(self, 14, (x0, 0), estilo.COLOR_TEXTO_TENUE)
        self.texto = _texto(self, 16, (x0, 0))
        self.instruccion = _texto(self, 15, (x0, 0), estilo.COLOR_ACENTO)
        self.filas = []
        for i in range(self.MAX_FILAS):
            boton = boton_piel_secundario(" ", al_clic=lambda n=i + 1: al_clic(n), ancho=self.ancho_texto, alto=0.048,
                                          tamano_fuente_px=15, parent=self)
            boton.text_entity.origin = (-0.5, 0)
            boton.text_entity.x = -0.47
            boton.enabled = False
            self.filas.append(boton)
        self.lineas = [_texto(self, self.PX_LINEA, (x0, 0)) for _ in range(self.MAX_FILAS)]
        self.indicador = _texto(self, 12, (ancho / 2 - 0.03, 0), estilo.COLOR_TEXTO_TENUE, origen=(0.5, 0.5))
        self.aviso = _texto(self, 13, (x0, -alto / 2 + 0.085), estilo.COLOR_TEXTO_TENUE, origen=(-0.5, -0.5))
        self.pie = _texto(self, 13, (x0, -alto / 2 + 0.025), estilo.COLOR_TEXTO_TENUE, origen=(-0.5, -0.5))
        self._lineas_datos = []
        self._alturas = []
        self._y_lineas = 0.0
        self._ventana = 0.0
        self.desplazamiento = 0.0

    def _bloque(self, texto, cadena, px, y, max_lineas):
        """Pone `cadena` partida en líneas a partir de `y` (borde superior). Devuelve la y debajo del bloque."""
        if not cadena:
            texto.enabled = False
            return y
        texto.enabled = True
        lineas = envolver_texto(" ".join(cadena.split()), medidor().funcion(px), self.ancho_texto)
        if len(lineas) > max_lineas:
            lineas = lineas[:max_lineas - 1] + [_recortar(" ".join(lineas[max_lineas - 1:]), medidor().funcion(px),
                                                           self.ancho_texto)]
        _poner(texto, "\n".join(lineas))
        texto.y = y
        return y - len(lineas) * alto_linea(px) - 0.012

    def mostrar(self, contenido):
        self.enabled = True
        y = self.arriba
        medir_titulo = medidor().funcion(22, negrita=True)
        _poner(self.titulo, _recortar(contenido.get("titulo") or "", medir_titulo, self.ancho_texto))
        y -= alto_linea(22) + 0.004
        y = self._bloque(self.subtitulo, contenido.get("subtitulo"), 14, y, 1)
        # sin botones (dilemas: las opciones van solo en el teléfono) hay sitio para la situación entera
        y = self._bloque(self.texto, contenido.get("texto"), 16, y, 6 if contenido.get("botones") else 10)
        y = self._bloque(self.instruccion, contenido.get("instruccion"), 15, y, 2)
        botones = contenido.get("botones") or []
        for i, boton in enumerate(self.filas):
            hay = i < len(botones)
            boton.enabled = hay
            if hay:
                texto, marcado = botones[i]
                boton.text = texto
                tono = rgb(estilo.ACENTO_PRIMARIO if marcado else estilo.COLOR_BOTON_TEXTO)
                boton.text_color = tono
                boton.highlight_text_color = tono
                boton.position = (0, y - 0.024 - i * 0.056, -0.02)
        if botones:
            y -= len(botones) * 0.056
        self._lineas_datos = list(contenido.get("lineas") or [])
        self._y_lineas = y
        hay_aviso = bool(contenido.get("aviso"))
        # el aviso se parte en líneas (antes era una sola y se salía del panel por la derecha)
        lineas_aviso = envolver_texto(" ".join((contenido.get("aviso") or "").split()), medidor().funcion(13),
                                      self.ancho_texto)[:2] if hay_aviso else []
        # la revisión no tiene aviso: la ventana llega hasta encima del pie (deja sitio al indicador de scroll)
        extra_aviso = max(0, len(lineas_aviso) - 1) * alto_linea(13)
        self._suelo = (self.aviso.y + 0.035 + extra_aviso) if hay_aviso else (self.pie.y + 0.075)
        self._ventana = max(0.05, y - self._suelo - 0.03)
        self._alturas = []
        medir = medidor().funcion(self.PX_LINEA)
        self._partidas = []
        for texto, _tono in self._lineas_datos[:self.MAX_FILAS]:
            partida = envolver_texto(" ".join(texto.split()), medir, self.ancho_texto)
            self._partidas.append(partida)
            self._alturas.append(len(partida) * alto_linea(self.PX_LINEA))
        self.desplazamiento = 0.0
        self._colocar_lineas()
        _poner(self.aviso, "\n".join(lineas_aviso))
        pie = contenido.get("pie") or ""
        lineas_pie = envolver_texto(pie, medidor().funcion(13), self.ancho_texto) if pie else []
        _poner(self.pie, "\n".join(lineas_pie[:2]))

    def _colocar_lineas(self):
        plan = tgc.plan_scroll(self._alturas, self._ventana, self.desplazamiento, separacion=0.01)
        self.desplazamiento = plan["desplazamiento"]
        visibles = dict(plan["filas"])
        for i, linea in enumerate(self.lineas):
            if i < len(self._partidas) and i in visibles:
                linea.enabled = True
                _poner(linea, "\n".join(self._partidas[i]))
                linea.color = rgb(self._lineas_datos[i][1])
                linea.y = self._y_lineas + visibles[i]
            else:
                linea.enabled = False
        if plan["maximo"] > 0:
            ocultas = len(self._partidas) - len(visibles)
            self.indicador.enabled = True
            _poner(self.indicador, f"{ocultas} más: flechas o rueda" if ocultas else "")
            self.indicador.y = self._suelo + 0.012
        else:
            self.indicador.enabled = False

    def desplazar(self, pasos):
        """Mueve el scroll de la revisión. True si hay algo que desplazar."""
        if not self._alturas:
            return False
        self.desplazamiento += pasos * 0.06
        self._colocar_lineas()
        return True

    def ocultar(self):
        self.enabled = False


# ----------------------------------------------------------------------------- piezas comunes de las pantallas

def _partir(cadena, px, ancho, max_lineas=None, negrita=False):
    """Líneas de `cadena` en `ancho`; con `max_lineas`, la última se recorta con elipsis."""
    medir = medidor().funcion(px, negrita)
    lineas = envolver_texto(" ".join(str(cadena or "").split()), medir, ancho) if cadena else []
    if max_lineas is not None and len(lineas) > max_lineas:
        lineas = lineas[:max_lineas - 1] + [_recortar(" ".join(lineas[max_lineas - 1:]), medir, ancho)]
    return lineas


class Tarjeta(Entity):
    """Tarjeta de texto (aviso, evidencia, notificación). Con número es marcable: clic = al_clic(numero); marcada,
    fondo amarillo tenue, «[x]» y número con anillo grueso. fijar(...) devuelve su alto; (x, y) = esquina sup. izq."""

    PX = 12
    RELLENO = 0.012

    def __init__(self, al_clic=None, tono=COLOR_PILDORA, **opciones):
        super().__init__(enabled=False, **opciones)
        self.numero = None
        self.tono = tono
        self.fondo = _quad(self, tono, z=0.002, radio_px=8)
        if al_clic is not None:
            self.fondo.collider = "box"
            self.fondo.on_click = lambda: self.numero is not None and al_clic(self.numero)
        self.franja = _quad(self, estilo.COLOR_ACENTO, z=0.001, ancho=0.005, alto=0.05)
        self.titulo = _texto(self, self.PX, (0, 0), estilo.COLOR_TEXTO, negrita=True)
        self.texto = _texto(self, self.PX, (0, 0))
        self.marca = Numero(al_clic or (lambda n: None), parent=self, z=-0.01)

    def fijar(self, x, y, ancho, texto, titulo="", numero=None, marcado=False, max_lineas=3, franja=None,
              tono_texto=estilo.COLOR_TEXTO):
        self.enabled = True
        self.numero = numero
        sangria = 0.045 if numero is not None else self.RELLENO + (0.006 if franja else 0)
        ancho_texto = ancho - sangria - self.RELLENO
        y_local = -self.RELLENO
        self.titulo.enabled = bool(titulo)
        if titulo:
            _poner(self.titulo, _recortar(titulo, medidor().funcion(self.PX, True), ancho_texto))
            self.titulo.position = (sangria, y_local, -0.01)
            y_local -= alto_linea(self.PX)
        cadena = ("[x] " if marcado else "") + texto
        lineas = _partir(cadena, self.PX, ancho_texto, max_lineas)
        _poner(self.texto, "\n".join(lineas))
        self.texto.position = (sangria, y_local, -0.01)
        self.texto.color = rgb(estilo.COLOR_ACENTO if marcado else tono_texto)
        alto = -y_local + len(lineas) * alto_linea(self.PX) + self.RELLENO * 0.6
        _redimensionar(self.fondo, ancho, alto, 8)
        self.fondo.position = (ancho / 2, -alto / 2, 0.002)
        self.fondo.color = color.rgba32(*estilo.COLOR_ACENTO, 70) if marcado else rgb(self.tono)
        self.franja.enabled = bool(franja)
        if franja:
            self.franja.scale = (0.005, alto - 0.012)
            self.franja.position = (0.008, -alto / 2, 0.001)
            self.franja.color = rgb(franja)
        if numero is not None:
            self.marca.fijar(numero, 0.022, -alto / 2, marcado)
        else:
            self.marca.enabled = False
        self.position = (x, y, self.z)
        return alto

    def ocultar(self):
        self.enabled = False


class Mensaje(Entity):
    """Mensaje de chat o comentario: avatar, autor, «Reenviado muchas veces», texto y foto opcional. Los míos van a la
    derecha, sin avatar ni autor. fijar(...) devuelve el alto; (x, y) = esquina superior izquierda de la columna."""

    PX = 13
    RELLENO = 0.012
    D_AVATAR = 0.036
    FOTO = (0.22, 0.132)

    def __init__(self, **opciones):
        super().__init__(enabled=False, **opciones)
        self.avatar = Avatar(self.D_AVATAR, parent=self, z=-0.005)
        self.burbuja = _quad(self, COLOR_BURBUJA, z=0.002, radio_px=10)
        self.autor = _texto(self, 11, (0, 0), estilo.ACENTO_SECUNDARIO, negrita=True)
        self.reenvio_icono = Entity(parent=self, model="quad", texture=ico.textura_icono("republicar"), scale=0.016,
                                    color=rgb(estilo.COLOR_TEXTO_TENUE), z=-0.01)
        self.reenvio = _texto(self, 10, (0, 0), estilo.COLOR_TEXTO_TENUE)
        self.texto = _texto(self, self.PX, (0, 0))
        self.foto = Entity(parent=self, model="quad", scale=self.FOTO, z=-0.005, enabled=False)

    def fijar(self, x, y, ancho, texto, autor="", mio=False, foto="", reenviado=False, max_lineas=5):
        self.enabled = True
        ancho_burbuja_max = ancho - (0 if mio else self.D_AVATAR + 0.01) - 0.04
        ancho_texto = ancho_burbuja_max - 2 * self.RELLENO
        lineas = _partir(texto, self.PX, ancho_texto, max_lineas)
        medir = medidor().funcion(self.PX)
        ancho_lineas = max([medir(l) for l in lineas] + [0.0])
        mostrar_autor = bool(autor) and not mio
        ancho_autor = medidor().ancho(autor, 11, True) if mostrar_autor else 0.0
        ancho_reenvio = medidor().ancho("Reenviado muchas veces", 10) + 0.022 if reenviado else 0.0
        hay_foto = bool(foto)
        ancho_b = min(ancho_burbuja_max, max(ancho_lineas, ancho_autor, ancho_reenvio,
                                             self.FOTO[0] if hay_foto else 0.0) + 2 * self.RELLENO)
        x_b = ancho - ancho_b if mio else self.D_AVATAR + 0.01
        y_local = -self.RELLENO
        self.autor.enabled = mostrar_autor
        if mostrar_autor:
            _poner(self.autor, _recortar(autor, medidor().funcion(11, True), ancho_b - 2 * self.RELLENO))
            self.autor.position = (x_b + self.RELLENO, y_local, -0.01)
            self.autor.color = rgb(autor_simple(autor)["color_avatar"])
            y_local -= alto_linea(11)
        self.reenvio.enabled = self.reenvio_icono.enabled = reenviado
        if reenviado:
            self.reenvio_icono.position = (x_b + self.RELLENO + 0.008, y_local - 0.008, -0.01)
            _poner(self.reenvio, "Reenviado muchas veces")
            self.reenvio.position = (x_b + self.RELLENO + 0.02, y_local, -0.01)
            y_local -= alto_linea(10)
        self.foto.enabled = hay_foto
        if hay_foto:
            from frontend import fotos_avisos
            self.foto.texture = fotos_avisos.textura(foto) if foto in fotos_avisos.NOMBRES else None
            self.foto.color = color.white
            self.foto.position = (x_b + self.RELLENO + self.FOTO[0] / 2, y_local - self.FOTO[1] / 2, -0.005)
            y_local -= self.FOTO[1] + 0.008
        _poner(self.texto, "\n".join(lineas))
        self.texto.position = (x_b + self.RELLENO, y_local, -0.01)
        y_local -= len(lineas) * alto_linea(self.PX)
        alto = -y_local + self.RELLENO * 0.6
        _redimensionar(self.burbuja, ancho_b, alto, 10)
        self.burbuja.position = (x_b + ancho_b / 2, -alto / 2, 0.002)
        self.burbuja.color = rgb(COLOR_BURBUJA_MIA if mio else COLOR_BURBUJA)
        self.avatar.enabled = not mio
        if not mio:
            self.avatar.fijar(autor_simple(autor or "?"))
            self.avatar.position = (self.D_AVATAR / 2, -self.D_AVATAR / 2, -0.005)
        self.position = (x, y, self.z)
        return alto

    def ocultar(self):
        self.enabled = False


class Pildora(Entity):
    """Aviso gris centrado del sistema («Saliste del grupo»). fijar(y, texto, ancho_max) devuelve el alto."""

    PX = 12

    def __init__(self, **opciones):
        super().__init__(enabled=False, **opciones)
        self.fondo = _quad(self, COLOR_PILDORA, z=0.002, radio_px=8)
        self.texto = _texto(self, self.PX, (0, 0), origen=(0, 0.5))

    def fijar(self, y, texto, ancho_max):
        self.enabled = True
        lineas = _partir(texto, self.PX, ancho_max - 0.03, 2)
        medir = medidor().funcion(self.PX)
        ancho = max(medir(l) for l in lineas) + 0.03
        alto = len(lineas) * alto_linea(self.PX) + 0.014
        _redimensionar(self.fondo, ancho, alto, 8)
        self.fondo.position = (0, -alto / 2, 0.002)
        _poner(self.texto, "\n".join(lineas))
        self.texto.position = (0, -0.007, -0.01)
        self.y = y
        return alto

    def ocultar(self):
        self.enabled = False


class Pegatina(Entity):
    """Zona marcable de una FOTO: anillo cian con su número; marcada, una pegatina amarilla que la tapa (con «x»)."""

    R = 0.028

    def __init__(self, al_clic, **opciones):
        super().__init__(enabled=False, **opciones)
        self.numero = None
        self.anillo = Entity(parent=self, model="circle", color=rgb(estilo.TINTA), scale=self.R * 2 + 0.008, z=0.002)
        self.disco = Entity(parent=self, model="circle", scale=self.R * 2, z=0.001, collider="sphere")
        self.disco.on_click = lambda: self.numero is not None and al_clic(self.numero)
        self.cruz = _texto(self, 15, (0, 0.004), estilo.TINTA, origen=(0, 0), negrita=True)
        self.marca = Numero(al_clic, parent=self, position=(self.R * 0.8, self.R * 0.8, -0.01))

    def fijar(self, numero, x, y, marcado):
        self.numero = numero
        self.enabled = True
        self.position = (x, y, self.z)
        if marcado:
            self.disco.color = rgb(estilo.COLOR_ACENTO)
            self.anillo.scale = self.R * 2 + 0.01
            self.anillo.color = rgb(estilo.TINTA)
            _poner(self.cruz, "x")
        else:
            # sin marcar: solo un aro cian fino (el disco casi transparente deja ver la foto)
            self.disco.color = color.rgba32(*estilo.PAPEL, 70)
            self.anillo.scale = self.R * 2 + 0.008
            self.anillo.color = color.rgba32(*estilo.ACENTO_SECUNDARIO, 230)
            _poner(self.cruz, "")
        self.marca.fijar(numero, self.R * 0.8, self.R * 0.8, marcado)


# ----------------------------------------------------------------------------- hoja de opciones

class FilaOpcion(Entity):
    """Una opción de la hoja: hasta dos líneas de texto; clic = al_clic(n)."""

    PX = 13

    def __init__(self, n, al_clic, ancho, **opciones):
        super().__init__(enabled=False, **opciones)
        self.ancho = ancho
        self.fondo = _quad(self, estilo.COLOR_BOTON, z=0.002, radio_px=10)
        self.fondo.collider = "box"
        self.fondo.on_click = lambda: al_clic(n)
        self.fondo.on_mouse_enter = lambda: setattr(self.fondo, "color", rgb(estilo.COLOR_BOTON_RESALTADO))
        self.fondo.on_mouse_exit = lambda: setattr(self.fondo, "color", rgb(estilo.COLOR_BOTON))
        self.texto = _texto(self, self.PX, (0, 0), estilo.COLOR_BOTON_TEXTO)

    def fijar(self, y, texto):
        """(y) = borde superior. Devuelve el alto."""
        self.enabled = True
        lineas = _partir(texto, self.PX, self.ancho - 0.03, 2)
        alto = len(lineas) * alto_linea(self.PX) + 0.02
        _redimensionar(self.fondo, self.ancho, alto, 10)
        self.fondo.color = rgb(estilo.COLOR_BOTON)
        self.fondo.position = (0, -alto / 2, 0.002)
        _poner(self.texto, "\n".join(lineas))
        self.texto.position = (-self.ancho / 2 + 0.015, -0.01, -0.01)
        self.y = y
        return alto


class HojaOpciones(Entity):
    """Hoja inferior de la pantalla con hasta 3 opciones (cada una en una o dos líneas); clic = al_clic(n).
    mostrar(titulo, opciones) devuelve la y de su borde superior (lo de encima sigue a la vista)."""

    MAX = 3
    SEPARACION = 0.01

    def __init__(self, al_clic, **opciones):
        super().__init__(enabled=False, **opciones)
        self.ancho = tgc.PANTALLA_ANCHO
        self.abajo = -tgc.PANTALLA_ALTO / 2
        self.fondo = _quad(self, COLOR_CABECERA, z=0.003, radio_px=18)
        self.fondo.collider = "box"            # tapa los tramos de debajo: un clic aquí no marca nada
        self.agarre = _quad(self, estilo.COLOR_TEXTO_TENUE, z=0.001, radio_px=3, ancho=0.06, alto=0.006)
        self.titulo = _texto(self, 14, (0, 0), estilo.COLOR_TEXTO, origen=(0, 0.5), negrita=True)
        self.filas = [FilaOpcion(i + 1, al_clic, self.ancho - 0.04, parent=self, z=-0.01) for i in range(self.MAX)]

    def mostrar(self, titulo, opciones):
        self.enabled = True
        alturas = []
        y = 0.0
        for i, fila in enumerate(self.filas):
            if i < len(opciones):
                alturas.append(fila.fijar(0, opciones[i]))
            else:
                fila.enabled = False
        alto = 0.06 + sum(alturas) + self.SEPARACION * max(0, len(alturas) - 1) + 0.025
        arriba = self.abajo + alto
        _redimensionar(self.fondo, self.ancho, alto, 18)
        self.fondo.y = self.abajo + alto / 2
        self.agarre.y = arriba - 0.012
        _poner(self.titulo, titulo)
        self.titulo.y = arriba - 0.022
        y = arriba - 0.058
        for fila, alto_fila in zip(self.filas, alturas):
            fila.y = y
            y -= alto_fila + self.SEPARACION
        return arriba

    def ocultar(self):
        self.enabled = False


# ----------------------------------------------------------------------------- base de pantalla

class Pantalla(Entity):
    """Base: fondo, cabecera (avatar, nombre, línea de debajo), hoja de opciones y el bloque de lo que pasó después
    (mi mensaje, aviso del sistema y respuestas). Coordenadas en la pantalla del teléfono (centro = 0, 0)."""

    ALTO_CABECERA = 0.07
    MAX_RESPUESTAS = 3

    def __init__(self, al_elegir, **opciones):
        super().__init__(enabled=False, **opciones)
        self.ancho = tgc.PANTALLA_ANCHO
        self.izquierda = -self.ancho / 2
        self.arriba = tgc.PANTALLA_ALTO / 2 - tgc.ALTO_BARRA_ESTADO
        self.abajo = -tgc.PANTALLA_ALTO / 2
        alto_fondo = tgc.PANTALLA_ALTO - tgc.ALTO_BARRA_ESTADO - 0.02
        _quad(self, COLOR_CHAT, z=0.004, ancho=self.ancho, alto=alto_fondo).y = -tgc.ALTO_BARRA_ESTADO / 2 - 0.01
        self.y_cabecera = self.arriba - self.ALTO_CABECERA / 2
        # la cabecera va por DELANTE del contenido: lo que se desplaza hacia arriba pasa por debajo
        self.cabecera_fondo = _quad(self, COLOR_CABECERA, z=-0.02, ancho=self.ancho, alto=self.ALTO_CABECERA)
        self.cabecera_fondo.y = self.y_cabecera
        self.avatar = Avatar(0.046, parent=self, position=(self.izquierda + 0.036, self.y_cabecera, -0.025))
        self.x_nombre = self.izquierda + 0.07
        self.nombre = _texto(self, 14, (self.x_nombre, self.y_cabecera + 0.012), negrita=True, origen=(-0.5, 0), z=-0.025)
        self.sub = _texto(self, 11, (self.x_nombre, self.y_cabecera - 0.013), estilo.COLOR_TEXTO_TENUE, origen=(-0.5, 0),
                          z=-0.025)
        self.contenido_arriba = self.arriba - self.ALTO_CABECERA - 0.015
        self.columna = self.ancho - 0.04          # ancho útil de la conversación
        self.x_columna = self.izquierda + 0.02
        self.mio = Mensaje(parent=self, z=-0.006)
        self.sistema = Pildora(parent=self, z=-0.006)
        self.respuestas = [Mensaje(parent=self, z=-0.006) for _ in range(self.MAX_RESPUESTAS)]
        self.hoja = HojaOpciones(al_elegir, parent=self, z=Z_HOJA)

    def fijar_cabecera(self, nombre, sub, autor=None):
        self.avatar.fijar(autor or autor_simple(nombre))
        ancho = self.ancho / 2 - 0.02 - self.x_nombre
        _poner(self.nombre, _recortar(nombre, medidor().funcion(14, True), ancho))
        _poner(self.sub, _recortar(sub or "", medidor().funcion(11), ancho))

    def fijar_hoja(self, datos):
        """Devuelve el «suelo» del contenido: el borde de la hoja si está abierta, si no el fondo de la pantalla."""
        if datos["fase"] in ("decidir",) and datos.get("opciones"):
            return self.hoja.mostrar(datos.get("pregunta") or "¿Qué haces?", datos["opciones"])
        self.hoja.ocultar()
        return self.abajo + 0.01

    def bloque_resultado(self, datos, y, suelo=None):
        """Pone lo que pasó después de decidir a partir de `y` (borde superior); lo que no cabe encima de `suelo` no se
        muestra (el texto completo sigue en el panel lateral). Devuelve la lista de (entidad, alto)."""
        partes = []
        resultado = datos.get("resultado_canal") or {}
        en_revision = datos["fase"] == "revision"
        if en_revision and resultado.get("mio"):
            partes.append((self.mio, lambda yy: self.mio.fijar(self.x_columna, yy, self.columna, resultado["mio"], mio=True)))
        else:
            self.mio.ocultar()
        if en_revision and resultado.get("sistema"):
            partes.append((self.sistema, lambda yy: self.sistema.fijar(yy, resultado["sistema"], self.columna)))
        else:
            self.sistema.ocultar()
        respuestas = resultado.get("respuestas", []) if en_revision else []
        for i, mensaje in enumerate(self.respuestas):
            if i < len(respuestas):
                r = respuestas[i]
                partes.append((mensaje, lambda yy, r=r, m=mensaje: m.fijar(self.x_columna, yy, self.columna, r["texto"],
                                                                         autor=r["autor"], foto=r.get("foto", ""))))
            else:
                mensaje.ocultar()
        suelo = self.abajo + 0.01 if suelo is None else suelo
        colocadas = []
        for entidad, poner in partes:
            alto = poner(y)
            if y - alto < suelo and colocadas:
                entidad.ocultar()
                continue
            colocadas.append((entidad, alto))
            y -= alto + 0.012
        return colocadas

    def ocultar(self):
        self.enabled = False

# ----------------------------------------------------------------------------- pantalla DM

class PantallaDM(Entity):
    """Chat privado de Civitas. datos: {"remitente", "texto", "hora", "plan" (tgc.plan_zonas), "marcas": {numeros},
    "fase": marcar | decidir | revision, "opciones": [textos], "decision": id, "decision_texto": texto}."""

    PX = 15

    def __init__(self, al_marcar, al_elegir, **opciones):
        super().__init__(enabled=False, **opciones)
        ancho, alto = tgc.PANTALLA_ANCHO, tgc.PANTALLA_ALTO
        self.izquierda = -ancho / 2
        arriba = alto / 2 - tgc.ALTO_BARRA_ESTADO
        _quad(self, COLOR_CHAT, z=0.002, ancho=ancho, alto=alto - tgc.ALTO_BARRA_ESTADO - 0.02).y = -tgc.ALTO_BARRA_ESTADO / 2 - 0.01
        # cabecera
        self.alto_cabecera = 0.08
        self.y_cabecera = arriba - self.alto_cabecera / 2
        _quad(self, COLOR_CABECERA, z=0.001, ancho=ancho, alto=self.alto_cabecera).y = self.y_cabecera
        self.avatar = Avatar(0.052, parent=self, position=(self.izquierda + 0.04, self.y_cabecera, -0.01))
        self.x_nombre = self.izquierda + 0.078
        self.nombre = _texto(self, 15, (self.x_nombre, self.y_cabecera + 0.013), negrita=True, origen=(-0.5, 0))
        self.sub = _texto(self, 12, (self.x_nombre, self.y_cabecera - 0.014), estilo.COLOR_TEXTO_TENUE, origen=(-0.5, 0))
        logo = Entity(parent=self, model="quad", texture=ico.textura_logo(), scale=0.03,
                      position=(ancho / 2 - 0.03, self.y_cabecera, -0.01))
        logo.color = color.white
        # píldora de fecha
        self.y_pildora = arriba - self.alto_cabecera - 0.03
        _quad(self, COLOR_PILDORA, z=0.001, radio_px=8, ancho=0.08, alto=0.026).y = self.y_pildora
        self.pildora = _texto(self, 11, (0, self.y_pildora), estilo.COLOR_TEXTO_TENUE, origen=(0, 0))
        # burbuja entrante
        self.relleno = 0.016
        self.ancho_texto = ancho - 0.16          # deja a la derecha de la burbuja sitio para dos números
        self.x_burbuja = self.izquierda + 0.025
        self.y_burbuja = self.y_pildora - 0.03
        self.burbuja = _quad(self, COLOR_BURBUJA, z=0.001, radio_px=12, ancho=0.2, alto=0.1)
        self.lineas = [_texto(self, self.PX, (self.x_burbuja + self.relleno, 0)) for _ in range(MAX_LINEAS_BURBUJA)]
        self.hora = _texto(self, 11, (0, 0), estilo.COLOR_TEXTO_TENUE, origen=(0.5, -0.5))
        # piezas marcables (pool)
        self.tramos = [Tramo(al_marcar, parent=self, z=-0.005) for _ in range(MAX_TRAMOS)]
        self.numeros = [Numero(al_marcar, parent=self, z=-0.02) for _ in range(tgc.MAX_ELEMENTOS)]
        self.titulo_detalles = _texto(self, 11, (self.x_burbuja, 0), estilo.COLOR_TEXTO_TENUE)
        self.chips = [Chip(al_marcar, ancho - 0.05, parent=self, x=0, z=-0.01) for _ in range(MAX_DETALLES)]
        # respuesta (revisión): burbuja propia a la derecha o aviso del sistema al centro
        self.mia = _quad(self, COLOR_BURBUJA_MIA, z=0.001, radio_px=12, ancho=0.2, alto=0.05)
        self.mia_texto = _texto(self, 14, (0, 0), origen=(0.5, 0.5))
        self.sistema_fondo = _quad(self, COLOR_PILDORA, z=0.001, radio_px=8, ancho=0.3, alto=0.032)
        self.sistema = _texto(self, 12, (0, 0), estilo.COLOR_TEXTO, origen=(0, 0))
        # barra de escribir (fase de marcar)
        self.y_escribir = -alto / 2 + 0.04
        self.escribir = _quad(self, COLOR_PILDORA, z=0.001, radio_px=14, ancho=ancho - 0.05, alto=0.045)
        self.escribir.y = self.y_escribir
        self.escribir_texto = _texto(self, 13, (self.izquierda + 0.045, self.y_escribir), estilo.COLOR_TEXTO_TENUE,
                                     origen=(-0.5, 0))
        self.escribir_texto.text = "Escribe un mensaje"
        self.hoja = HojaOpciones(al_elegir, parent=self, z=Z_HOJA)

    def mostrar(self, datos):
        self.enabled = True
        plan, marcas, fase = datos["plan"], datos["marcas"], datos["fase"]
        medir = medidor().funcion(self.PX)
        nombre, sub = tgc.remitente_partido(datos["remitente"])
        autor = autor_simple(nombre)
        if not any(c.isalpha() for c in nombre):        # un número suelto: no hay cara ni nombre que poner
            autor["inicial"] = "?"
        self.avatar.fijar(autor)
        ancho_nombre = tgc.PANTALLA_ANCHO / 2 - 0.06 - self.x_nombre
        _poner(self.nombre, _recortar(nombre, medidor().funcion(15, negrita=True), ancho_nombre))
        _poner(self.sub, _recortar(sub, medidor().funcion(12), ancho_nombre))
        _poner(self.pildora, "Hoy")
        # cabecera marcable: el primer elemento es el nombre; el segundo, la línea de debajo
        usados_tramo = 0
        usados_numero = 0
        filas = ((self.nombre, 15, True), (self.sub, 12, False))
        for k, numero in enumerate(plan["cabecera"]):
            entidad, px, negrita = filas[k] if len(plan["cabecera"]) > 1 else (self.nombre, 15, True)
            texto_fila = entidad.text if entidad.text.strip() else "?"
            ancho_fila = min(ancho_nombre, medidor().ancho(texto_fila, px, negrita))
            alto_fila = a_unidades(px) * 1.25 if len(plan["cabecera"]) > 1 else self.alto_cabecera * 0.62
            arriba_fila = entidad.y + alto_fila / 2 if len(plan["cabecera"]) > 1 else self.y_cabecera + alto_fila / 2
            self.tramos[usados_tramo].fijar(numero, self.x_nombre - 0.004, arriba_fila, ancho_fila + 0.008, alto_fila,
                                            numero in marcas)
            usados_tramo += 1
            self.numeros[usados_numero].fijar(numero, self.x_nombre + ancho_fila + 0.022, entidad.y if len(plan["cabecera"]) > 1
                                              else self.y_cabecera, numero in marcas)
            usados_numero += 1
        # burbuja con sus tramos
        partida = tgc.partir_burbuja(datos["texto"], plan["burbuja"], medir, self.ancho_texto, MAX_LINEAS_BURBUJA)
        alto_l = alto_linea(self.PX)
        anchos = [medir(l["texto"]) for l in partida["lineas"]]
        alto_hora = 0.022
        ancho_b, alto_b = tgc.tamano_burbuja(anchos, alto_l, self.relleno)
        ancho_b = max(ancho_b, 0.16)
        alto_b += alto_hora
        _redimensionar(self.burbuja, ancho_b, alto_b, 12)
        self.burbuja.position = (self.x_burbuja + ancho_b / 2, self.y_burbuja - alto_b / 2, self.burbuja.z)
        primero = {}                              # número -> índice de la línea donde aparece por primera vez
        for i, linea in enumerate(self.lineas):
            hay = i < len(partida["lineas"])
            linea.enabled = hay
            if not hay:
                continue
            y_linea = self.y_burbuja - self.relleno - i * alto_l
            _poner(linea, partida["lineas"][i]["texto"])
            linea.y = y_linea
            for tramo in partida["lineas"][i]["tramos"]:
                if usados_tramo >= len(self.tramos):
                    break
                x = self.x_burbuja + self.relleno + tramo["x"]
                self.tramos[usados_tramo].fijar(tramo["numero"], x - 0.003, y_linea + 0.002, tramo["ancho"] + 0.006,
                                                alto_l, tramo["numero"] in marcas)
                usados_tramo += 1
                primero.setdefault(tramo["numero"], i)
        # los números van FUERA de la burbuja, a la altura de su línea (dentro taparían letras)
        por_linea = {}
        for numero, i in primero.items():
            if usados_numero >= len(self.numeros):
                break
            k = por_linea.get(i, 0)
            por_linea[i] = k + 1
            y_centro = self.y_burbuja - self.relleno - i * alto_l - alto_l / 2 + 0.002
            self.numeros[usados_numero].fijar(numero, self.x_burbuja + ancho_b + 0.02 + k * 0.032, y_centro,
                                              numero in marcas)
            usados_numero += 1
        _poner(self.hora, datos.get("hora") or "")
        self.hora.position = (self.x_burbuja + ancho_b - self.relleno, self.y_burbuja - alto_b + 0.008, self.hora.z)
        for tramo in self.tramos[usados_tramo:]:
            tramo.enabled = False
        for numero in self.numeros[usados_numero:]:
            numero.enabled = False
        # otros detalles
        y = self.y_burbuja - alto_b - 0.03
        detalles = tgc.completar_detalles(plan, partida["encontrados"])[:MAX_DETALLES]
        self.titulo_detalles.enabled = bool(detalles)
        if detalles:
            _poner(self.titulo_detalles, "Otros detalles")
            self.titulo_detalles.y = y + 0.012
            y -= 0.012
        for i, chip in enumerate(self.chips):
            if i < len(detalles):
                numero = detalles[i]
                chip.fijar(numero, plan["textos"][numero], numero in marcas, y - Chip.ALTO / 2)
                y -= Chip.ALTO + 0.008
            else:
                chip.enabled = False
        # fase
        self.escribir.enabled = self.escribir_texto.enabled = fase == "marcar"
        if fase == "decidir":
            self.hoja.mostrar("¿Qué haces?", datos.get("opciones") or [])
        else:
            self.hoja.ocultar()
        self._respuesta(fase, datos, y - 0.02)

    def _respuesta(self, fase, datos, y):
        revision = fase == "revision"
        decision = datos.get("decision")
        sistema = SISTEMA_DM.get(decision) if revision else None
        propia = revision and sistema is None and datos.get("decision_texto")
        self.mia.enabled = self.mia_texto.enabled = bool(propia)
        self.sistema.enabled = self.sistema_fondo.enabled = bool(sistema)
        y = min(y, -0.12)
        if propia:
            medir = medidor().funcion(14)
            lineas = envolver_texto(datos["decision_texto"], medir, self.ancho_texto * 0.8)[:3]
            ancho = max(medir(l) for l in lineas) + 2 * self.relleno
            alto = len(lineas) * alto_linea(14) + 2 * self.relleno
            derecha = tgc.PANTALLA_ANCHO / 2 - 0.025
            _redimensionar(self.mia, ancho, alto, 12)
            self.mia.position = (derecha - ancho / 2, y - alto / 2, self.mia.z)
            _poner(self.mia_texto, "\n".join(lineas))
            self.mia_texto.position = (derecha - self.relleno, y - self.relleno, self.mia_texto.z)
        if sistema:
            medir = medidor().funcion(12)
            ancho = min(tgc.PANTALLA_ANCHO - 0.04, medir(sistema) + 0.04)
            _redimensionar(self.sistema_fondo, ancho, 0.032, 8)
            self.sistema_fondo.position = (0, y - 0.016, self.sistema_fondo.z)
            _poner(self.sistema, _recortar(sistema, medir, ancho - 0.02))
            self.sistema.position = (0, y - 0.016, self.sistema.z)

    def ocultar(self):
        self.enabled = False


# ----------------------------------------------------------------------------- muro (publicar)

class PantallaMuro(Pantalla):
    """Editor de una publicación propia (publicar y dilemas de muro). datos: además de lo común, "extra" con foto,
    leyenda, ubicacion, etiquetas y comentarios; "expuestos": ids que quedaron a la vista al publicar."""

    PX = 13
    MAX_COMENTARIOS = 3

    def __init__(self, al_marcar, al_elegir, **opciones):
        super().__init__(al_elegir, **opciones)
        self.alto_foto = self.columna * 0.6
        self.foto = Entity(parent=self, model="quad", scale=(self.columna, self.alto_foto), z=-0.002)
        self.pegatinas = [Pegatina(al_marcar, parent=self, z=-0.01) for _ in range(tgc.MAX_ELEMENTOS)]
        self.lineas = [_texto(self, self.PX, (self.x_columna, 0)) for _ in range(4)]
        self.tramos = [Tramo(al_marcar, parent=self, z=-0.005) for _ in range(4)]
        self.numeros = [Numero(al_marcar, parent=self, z=-0.02) for _ in range(4)]
        self.tarjetas = [Tarjeta(al_marcar, parent=self, z=-0.006) for _ in range(MAX_DETALLES + 2)]
        self.comentarios = [Mensaje(parent=self, z=-0.006) for _ in range(self.MAX_COMENTARIOS)]

    def mostrar(self, datos):
        self.enabled = True
        extra = datos["extra"]
        plan, marcas, fase = datos["plan"], datos["marcas"], datos["fase"]
        revision = fase == "revision"
        publicado = revision and datos.get("decision") not in ("no_publicar",) and not datos.get("borrador")
        self.fijar_cabecera("Tu muro" if publicado else "Nueva publicación",
                            "Publicado ahora" if publicado else "Civitas · borrador", autor=autor_simple("Tú"))
        y = self.contenido_arriba
        # foto con sus zonas
        from frontend import fotos_avisos
        nombre_foto = extra.get("foto") or ""
        self.foto.enabled = nombre_foto in fotos_avisos.NOMBRES
        usados = 0
        if self.foto.enabled:
            self.foto.texture = fotos_avisos.textura(nombre_foto)
            self.foto.color = color.white
            self.foto.position = (0, y - self.alto_foto / 2, self.foto.z)
            x0, y0 = -self.columna / 2, y
            for numero, fx, fy in plan["foto"]:
                if usados >= len(self.pegatinas):
                    break
                marcado = numero in marcas
                if revision and not marcado:
                    continue               # publicado: solo quedan las pegatinas que pusiste
                self.pegatinas[usados].fijar(numero, x0 + fx * self.columna, y0 - fy * self.alto_foto, marcado)
                usados += 1
            y -= self.alto_foto + 0.014
        for pegatina in self.pegatinas[usados:]:
            pegatina.enabled = False
        # leyenda con sus tramos
        y = self._leyenda(extra.get("leyenda") or datos.get("texto") or "", plan, marcas, y, revision)
        # ubicación, etiquetas y lo demás, como tarjetas marcables
        filas = []
        if extra.get("ubicacion"):
            filas += [(n, "Ubicación: " + extra["ubicacion"]) for n in plan["ubicacion"]] or [(None, "Ubicación: " + extra["ubicacion"])]
        if extra.get("etiquetas"):
            filas += [(n, extra["etiquetas"]) for n in plan["etiquetas"]] or [(None, extra["etiquetas"])]
        dibujados = {n for n, _f in plan["burbuja"] if n in self._encontrados} | {n for n, *_r in plan["foto"]}
        dibujados |= set(plan["ubicacion"]) | set(plan["etiquetas"])
        resto = [n for n in sorted(plan["numeros"]) if n not in dibujados]
        filas += [(n, plan["textos"][n]) for n in resto]
        suelo = self.fijar_hoja(datos)
        for i, tarjeta in enumerate(self.tarjetas):
            if i < len(filas) and not revision:
                numero, texto = filas[i]
                alto = tarjeta.fijar(self.x_columna, y, self.columna, texto, numero=numero,
                                     marcado=numero in marcas, max_lineas=2)
                y -= alto + 0.008
            else:
                tarjeta.ocultar()
        # después de publicar: comentarios de extraños sobre lo que quedó a la vista
        comentarios = [extra.get("comentarios", {}).get(ident) for ident in datos.get("expuestos", [])]
        comentarios = [c for c in comentarios if c] if publicado else []
        y -= 0.006
        for i, mensaje in enumerate(self.comentarios):
            if i < len(comentarios) and y > suelo + 0.06:
                autor = ("anon_" + str(400 + 37 * i), "visitante_" + str(12 + i), "perfil_nuevo")[i % 3]
                y -= mensaje.fijar(self.x_columna, y, self.columna, comentarios[i], autor=autor, max_lineas=2) + 0.01
            else:
                mensaje.ocultar()
        if revision and not publicado and not datos.get("resultado_canal"):
            datos = dict(datos, resultado_canal={"sistema": "No la publicaste: quedó en borradores."})
        self.bloque_resultado(datos, y, suelo=suelo)

    def _leyenda(self, texto, plan, marcas, y, revision):
        medir = medidor().funcion(self.PX)
        partida = tgc.partir_burbuja(texto, plan["burbuja"], medir, self.columna - 0.05, len(self.lineas))
        self._encontrados = partida["encontrados"]
        alto_l = alto_linea(self.PX)
        usados_t = usados_n = 0
        primero = {}
        for i, linea in enumerate(self.lineas):
            hay = i < len(partida["lineas"])
            linea.enabled = hay
            if not hay:
                continue
            y_linea = y - i * alto_l
            _poner(linea, partida["lineas"][i]["texto"])
            linea.y = y_linea
            for tramo in partida["lineas"][i]["tramos"]:
                if usados_t >= len(self.tramos) or revision:
                    break
                self.tramos[usados_t].fijar(tramo["numero"], self.x_columna + tramo["x"] - 0.003, y_linea + 0.002,
                                            tramo["ancho"] + 0.006, alto_l, tramo["numero"] in marcas)
                usados_t += 1
                primero.setdefault(tramo["numero"], i)
        for numero, i in primero.items():
            if usados_n < len(self.numeros):
                self.numeros[usados_n].fijar(numero, self.ancho / 2 - 0.035, y - i * alto_l - alto_l / 2 + 0.002,
                                             numero in marcas)
                usados_n += 1
        for tramo in self.tramos[usados_t:]:
            tramo.enabled = False
        for numero in self.numeros[usados_n:]:
            numero.enabled = False
        return y - len(partida["lineas"]) * alto_l - 0.014


# ----------------------------------------------------------------------------- rectificar

class PantallaRectificar(Pantalla):
    """Tu publicación que resultó falsa: banner de verificación, la publicación con sus contadores y lo que se sabe
    (tarjetas marcables). Revisión: corregida, la captura que ya circula (borrar) o contadores que siguen subiendo."""

    PX = 13

    def __init__(self, al_marcar, al_elegir, **opciones):
        super().__init__(al_elegir, **opciones)
        self.banner = Tarjeta(parent=self, tono=(70, 40, 40), z=-0.006)
        self.post = Tarjeta(parent=self, tono=COLOR_BURBUJA, z=-0.006)
        self.etiqueta = Pildora(parent=self, z=-0.008)
        self.cuentas = [AccionPost(nombre, parent=self, z=-0.01) for nombre in ("republicar", "responder", "me_gusta")]
        self.titulo_saber = _texto(self, 11, (self.x_columna, 0), estilo.COLOR_TEXTO_TENUE)
        self.evidencias = [Tarjeta(al_marcar, parent=self, z=-0.006) for _ in range(tgc.MAX_ELEMENTOS)]

    def mostrar(self, datos):
        self.enabled = True
        extra = datos["extra"]
        plan, marcas, fase = datos["plan"], datos["marcas"], datos["fase"]
        revision = fase == "revision"
        decision = datos.get("decision")
        self.fijar_cabecera(datos.get("remitente") or "Civitas · Verificación", datos.get("titulo") or "",
                            autor={"inicial": "V", "color_avatar": estilo.ESTADO_AVISO, "color_letra": estilo.TINTA})
        aviso, _sep, compartido = (datos.get("texto") or "").partition(" Lo que compartiste: ")
        y = self.contenido_arriba
        y -= self.banner.fijar(self.x_columna, y, self.columna, aviso, titulo="Verificación", max_lineas=3,
                               franja=estilo.ESTADO_AVISO) + 0.012
        # tu publicación
        tachar = revision and decision == "borrar"
        texto_post = compartido or datos.get("titulo") or ""
        titulo_post = "Tu publicación (borrada)" if tachar else "Tu publicación"
        alto_post = self.post.fijar(self.x_columna, y, self.columna, texto_post, titulo=titulo_post, max_lineas=3,
                                    tono_texto=estilo.COLOR_TEXTO_TENUE if tachar else estilo.COLOR_TEXTO)
        y -= alto_post + 0.006
        reenvios = int(extra.get("reenvios") or 0)
        if revision and decision == "defender":
            reenvios = reenvios * 2 + 17          # dejarla: sigue corriendo
        cuentas = (reenvios, max(1, reenvios // 9), reenvios * 3 + 5)
        for i, (accion, n) in enumerate(zip(self.cuentas, cuentas)):
            accion.position = (self.x_columna + 0.02 + i * 0.13, y - 0.014, accion.z)
            accion.fijar_cuenta(n)
            accion.fijar_estado(False, estilo.COLOR_TEXTO_TENUE)
        y -= 0.036
        etiqueta = {"rectificar": "Corregido por ti", "borrar": "Ya circula una captura de tu publicación",
                    "defender": "Sigue circulando"}.get(decision) if revision else None
        if etiqueta:
            y -= self.etiqueta.fijar(y, etiqueta, self.columna) + 0.01
        else:
            self.etiqueta.ocultar()
        suelo = self.fijar_hoja(datos)
        # lo que se sabe
        numeros = sorted(plan["numeros"]) if not revision else []
        self.titulo_saber.enabled = bool(numeros)
        if numeros:
            _poner(self.titulo_saber, "Lo que se sabe")
            self.titulo_saber.y = y
            y -= alto_linea(11) + 0.004
        contadores = set(plan["contador"])
        for i, tarjeta in enumerate(self.evidencias):
            if i < len(numeros):
                n = numeros[i]
                franja = estilo.ACENTO_SECUNDARIO if n in contadores else None
                y -= tarjeta.fijar(self.x_columna, y, self.columna, plan["textos"][n], numero=n, marcado=n in marcas,
                                   max_lineas=2, franja=franja) + 0.008
            else:
                tarjeta.ocultar()
        self.bloque_resultado(datos, y, suelo=suelo)


# ----------------------------------------------------------------------------- grupo y cadena

class PantallaChat(Pantalla):
    """Chat de grupo («grupo») o mensajes reenviados en cadena («cadena»): mensajes del JSON y, tras decidir, lo que
    escribiste y lo que contestan."""

    MAX_MENSAJES = 4

    def __init__(self, al_elegir, **opciones):
        super().__init__(al_elegir, **opciones)
        self.pildora = Pildora(parent=self, z=-0.006)
        self.mensajes = [Mensaje(parent=self, z=-0.006) for _ in range(self.MAX_MENSAJES)]

    def mostrar(self, datos):
        self.enabled = True
        extra = datos["extra"]
        nombre = extra.get("nombre_grupo") or datos.get("titulo") or "Grupo"
        cadena = extra["canal"] == "cadena"
        mensajes = extra.get("mensajes") or []
        autores = {m["autor"] for m in mensajes if m["autor"] != "Reenviado"}
        sub = "Reenviado muchas veces" if cadena else f"{len(autores) + 1} participantes"
        self.fijar_cabecera(nombre, sub)
        y = self.contenido_arriba
        alto_pildora = self.pildora.fijar(y, "Hoy", 0.2)
        y -= alto_pildora + 0.012
        suelo = self.fijar_hoja(datos)
        colocados = [(self.pildora, self.contenido_arriba, alto_pildora)]
        for i, mensaje in enumerate(self.mensajes):
            if i < len(mensajes):
                m = mensajes[i]
                alto = mensaje.fijar(self.x_columna, y, self.columna, m["texto"], autor=m["autor"], foto=m.get("foto", ""),
                                     reenviado=m.get("reenviado", False), max_lineas=4)
                colocados.append((mensaje, y, alto))
                y -= alto + 0.012
            else:
                mensaje.ocultar()
        # con la hoja abierta, la conversación sube (como en un chat): se ven los últimos mensajes y los primeros
        # quedan fuera por arriba
        if datos["fase"] == "decidir" and y < suelo:
            subida = suelo - y + 0.004
            for entidad, arriba, alto in colocados:
                if arriba + subida - 0.004 > self.contenido_arriba + 0.002:
                    entidad.ocultar()
                else:
                    entidad.y += subida
            y += subida
        self.bloque_resultado(datos, y, suelo=suelo)


# ----------------------------------------------------------------------------- notificaciones (pantalla bloqueada)

class PantallaNotificaciones(Pantalla):
    """Pantalla bloqueada con la hora en grande y las notificaciones apiladas."""

    MAX = 4

    def __init__(self, al_elegir, **opciones):
        super().__init__(al_elegir, **opciones)
        self.cabecera_fondo.enabled = False
        self.avatar.enabled = False
        self.reloj = _texto(self, 44, (0, self.arriba - 0.03), estilo.COLOR_TEXTO, origen=(0, 0.5), negrita=True)
        self.fecha = _texto(self, 13, (0, self.arriba - 0.115), estilo.COLOR_TEXTO_TENUE, origen=(0, 0.5))
        self.avisos = [Tarjeta(parent=self, tono=COLOR_BURBUJA, z=-0.006) for _ in range(self.MAX)]

    def mostrar(self, datos):
        self.enabled = True
        extra = datos["extra"]
        _poner(self.nombre, "")
        _poner(self.sub, "")
        _poner(self.reloj, datos.get("hora") or "12:00")
        _poner(self.fecha, extra.get("nombre_grupo") or "")
        y = self.arriba - 0.16
        suelo = self.fijar_hoja(datos)
        mensajes = extra.get("mensajes") or []
        for i, tarjeta in enumerate(self.avisos):
            if i < len(mensajes) and y > suelo + 0.05:
                y -= tarjeta.fijar(self.x_columna, y, self.columna, mensajes[i]["texto"], titulo=mensajes[i]["autor"],
                                   max_lineas=2) + 0.008
            else:
                tarjeta.ocultar()
        self.bloque_resultado(datos, y - 0.01, suelo=suelo)


# ----------------------------------------------------------------------------- feed

class PostFeed(Entity):
    """Una publicación del feed a pantalla completa (autor, texto, imagen y acciones)."""

    PX = 15

    def __init__(self, ancho, **opciones):
        super().__init__(**opciones)
        self.ancho = ancho
        self.avatar = Avatar(0.044, parent=self, position=(-ancho / 2 + 0.022, -0.022, -0.005))
        self.autor = _texto(self, 13, (-ancho / 2 + 0.055, -0.01), negrita=True, origen=(-0.5, 0))
        self.hora = _texto(self, 11, (-ancho / 2 + 0.055, -0.032), estilo.COLOR_TEXTO_TENUE, origen=(-0.5, 0))
        self.pista = Pildora(parent=self, z=-0.006)
        self.texto = _texto(self, self.PX, (-ancho / 2, 0))
        self.imagen = Entity(parent=self, model="quad", scale=(ancho, ancho * 0.56), z=-0.002, enabled=False)
        self.acciones = [AccionPost(n, parent=self, z=-0.01) for n in ("responder", "republicar", "me_gusta")]

    def fijar(self, texto, pista):
        datos = rsc.publicacion_de(texto)
        self.avatar.fijar(datos["autor"])
        _poner(self.autor, _recortar(datos["autor"]["nombre"], medidor().funcion(13, True), self.ancho - 0.07))
        _poner(self.hora, datos["hora"])
        y = -0.06
        self.pista.enabled = bool(pista)
        if pista:
            alto = self.pista.fijar(y, "Pista para tu investigación", self.ancho)
            self.pista.x = 0
            y -= alto + 0.01
        lineas = _partir(texto, self.PX, self.ancho, 9)
        _poner(self.texto, "\n".join(lineas))
        self.texto.y = y
        y -= len(lineas) * alto_linea(self.PX) + 0.014
        media = datos["media"]
        self.imagen.enabled = media["tipo"] == "imagen"
        if self.imagen.enabled:
            alto_img = self.ancho * 0.56
            self.imagen.texture = ico.textura_vista_previa(media["variante"], media["semilla"], 320, 180)
            self.imagen.color = color.white
            self.imagen.y = y - alto_img / 2
            y -= alto_img + 0.014
        c = datos["contadores"]
        for i, (accion, n) in enumerate(zip(self.acciones, (c["respuestas"], c["republicaciones"], c["me_gusta"]))):
            accion.position = (-self.ancho / 2 + 0.02 + i * 0.13, y - 0.014, accion.z)
            accion.fijar_cuenta(n)
            accion.fijar_estado(False, estilo.COLOR_TEXTO_TENUE)


class PantallaFeed(Pantalla):
    """Feed de Civitas: una publicación por pantalla. Al llegar otra, la vieja sube y la nueva entra desde abajo (0,2 s).
    Dos huecos que se alternan: número de entidades fijo."""

    DURACION = 0.2
    SUBIDA = 0.08
    if hctx.animaciones_activas():
        DURACION = hctx.tiempo("FEED_ENTRADA")

    def __init__(self, **opciones):
        super().__init__(lambda n: None, **opciones)
        self.contador = Pildora(parent=self, z=-0.03)
        self.huecos = [PostFeed(self.columna, parent=self, z=-0.006) for _ in range(2)]
        self.actual = 0
        self._texto = None
        self._t = None
        self.intro = _texto(self, 14, (self.x_columna, 0), estilo.COLOR_TEXTO_TENUE)

    def mostrar(self, datos):
        self.enabled = True
        feed = datos.get("feed") or {}
        self.fijar_cabecera("Civitas", "Para ti", autor={"inicial": "C", "color_avatar": estilo.ACENTO_SECUNDARIO,
                                                         "color_letra": estilo.TINTA})
        self.hoja.ocultar()
        y0 = self.contenido_arriba
        alto = self.contador.fijar(y0, feed.get("contador") or "", self.columna)
        self.y_post = y0 - alto - 0.02
        texto = feed.get("texto") or ""
        if not feed.get("publicacion"):
            for hueco in self.huecos:
                hueco.enabled = False
            self.intro.enabled = True
            _poner(self.intro, "\n".join(_partir(texto, 14, self.columna)))
            self.intro.y = self.y_post
            self._texto = None
            return
        self.intro.enabled = False
        if texto == self._texto:
            return
        anterior = self.huecos[self.actual] if self._texto is not None else None
        self.actual = 1 - self.actual if anterior is not None else self.actual
        nuevo = self.huecos[self.actual]
        nuevo.enabled = True
        nuevo.fijar(texto, feed.get("pista"))
        self._texto = texto
        self._anterior = anterior
        if anterior is None:
            nuevo.y = self.y_post
            self.huecos[1 - self.actual].enabled = False
            self._t = None
        else:
            self._t = 0.0
            self._colocar(0.0)

    def _colocar(self, p):
        # sin recorte de pantalla en Ursina: la vieja se va al empezar y la nueva sube un tramo corto (no se sale)
        if self._anterior is not None:
            self._anterior.enabled = False
            self._anterior = None
        # M3.6 (ALCALDE_UI_ANIMACIONES): ease-out en 0,18 s (antes ease_in_out en 0,2 s)
        curva = hctx.ease_out if hctx.animaciones_activas() else tgc.ease_in_out
        self.huecos[self.actual].y = self.y_post - self.SUBIDA * (1 - curva(p))

    def update(self):
        if self._t is None:
            return
        from ursina import time as tiempo
        self._t = min(self.DURACION, self._t + tiempo.dt)
        self._colocar(self._t / self.DURACION)
        if self._t >= self.DURACION:
            self._t = None

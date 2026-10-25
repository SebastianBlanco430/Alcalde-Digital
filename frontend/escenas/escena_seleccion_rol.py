# Escena de selección de jugadores y roles (Ursina), hot-seat en una sola PC.
# Paso 1: cuántos jugadores (1 a 4). Paso 2: cada jugador elige un rol exclusivo
# (los ya tomados se ven deshabilitados). Al terminar aparece "Comenzar".
# No conoce al gestor: recibe `fabrica_sesion` (crea una SesionJuego nueva en cada
# al_entrar) y el callback `al_comenzar(sesion)`. La lógica de roles vive en
# backend/logica/sesion.py; aquí solo se llama y se dibuja.
# Visual (T8): fondo de menú en capas, una tarjeta por rol con su retrato (iconos.py), nombre,
# descripción y lugar de inicio; hover (sube y se aclara), foco de teclado (anillo cian, flechas +
# Enter) y rol tomado en gris con el nombre del jugador.
# Confirmación (T-selección): clic/Enter en una tarjeta solo la RESALTA como candidata (anillo amarillo +
# insignia «Elegido»); el botón «Seleccionar» la confirma. «Cambiar» deshace la última confirmación y
# «Atrás» vuelve a «¿Cuántos jugadores?». `elegir_rol(rol)` sigue confirmando de inmediato (API previa).

from panda3d.core import TextNode
from ursina import Button, Entity, Text, color, window

from backend.datos.nombres_visibles import nombre_visible
from backend.logica.roles import ORDEN_ROLES, ROLES
from backend.logica.sesion import MAX_JUGADORES
from frontend import estilo, iconos, tipografia
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, modelo_redondeado, panel_tinta, rgb,
)
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FocoTeclado, FondoMenu, anadir_filo
from frontend.texto import envolver_texto

ANCHO_TARJETA = 0.38
ALTO_TARJETA = 0.56
SEPARACION_TARJETAS = 0.045
LADO_RETRATO = 0.22
ALFA_VELO = 105
RECORTE_RETRATO = 1.0     # los retratos nuevos traen margen transparente arriba: sin recorte


# Tarjeta pulsable de un rol. Misma API que un botón: `accion`, fijar_habilitado,
# esta_habilitado, manejar_clic, fijar_foco, bajo_el_raton.
class TarjetaRol(Entity):

    def __init__(self, rol, al_clic=None, **opciones):
        super().__init__(**opciones)
        info = ROLES[rol]
        self.rol = rol
        self.accion = al_clic
        self._habilitado = True
        self._tomado_por = None
        self._foco = False
        self._y_base = self.y
        w, h = ANCHO_TARJETA, ALTO_TARJETA

        borde = a_unidades(estilo.GROSOR_BORDE_PX)
        radio = estilo.RADIO_PANEL_PX
        # Anillo de foco (cian) detrás del panel.
        g = a_unidades(4)
        self.anillo = Entity(
            parent=self, model=modelo_redondeado(w + 2 * (borde + g), h + 2 * (borde + g), radio + 7),
            scale=(w + 2 * (borde + g), h + 2 * (borde + g)), color=rgb(estilo.ESTADO_INFO), z=0.006)
        self.anillo.enabled = False
        # Anillo de candidata (amarillo) más ancho que el de foco: queda como un segundo contorno.
        gc = a_unidades(9)
        self._candidata = False
        self.anillo_candidata = Entity(
            parent=self, model=modelo_redondeado(w + 2 * (borde + gc), h + 2 * (borde + gc), radio + 10),
            scale=(w + 2 * (borde + gc), h + 2 * (borde + gc)), color=rgb(estilo.ACENTO_PRIMARIO), z=0.0065)
        self.anillo_candidata.enabled = False
        self.panel = panel_tinta(self, w, h, estilo.COLOR_TARJETA, radio)
        anadir_filo(self.panel, w, h, radio)

        # Retrato sobre un cuadro del color del rol (la identidad del rol se conserva).
        caja = LADO_RETRATO + 0.02
        self.caja_retrato = panel_tinta(
            self, caja, caja, info.color, estilo.RADIO_TARJETA_PX, sombra=False,
            position=(0, h / 2 - caja / 2 - 0.03, -0.0005), borde_px=2)
        self.retrato = Entity(
            parent=self.caja_retrato, model="quad", texture=iconos.textura_retrato(rol),
            scale=(LADO_RETRATO, LADO_RETRATO * RECORTE_RETRATO), z=-0.001,
            y=-LADO_RETRATO * (1 - RECORTE_RETRATO) / 2, texture_scale=(1, RECORTE_RETRATO))

        self.texto_nombre = Text(
            info.nombre, parent=self, origin=(0, 0), position=(0, -0.035, -0.001),
            scale=escala_fuente(28), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self._ajustar_ancho(self.texto_nombre, 28, w - 2 * a_unidades(18))
        self.texto_descripcion = Text(
            "", parent=self, origin=(0, 0.5), position=(0, -0.072, -0.001),
            scale=escala_fuente(18), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.texto_descripcion.line_height = 1.3
        self._ancho_texto = w - 2 * a_unidades(22)
        self.texto_descripcion.text = self._envolver(self.texto_descripcion, info.descripcion)
        self.texto_lugar = Text(
            "", parent=self, origin=(0, 0), position=(0, -h / 2 + 0.05, -0.001),
            scale=escala_fuente(16), color=rgb(estilo.ACENTO_SECUNDARIO))
        self.texto_lugar.line_height = 1.2

        # Insignia «Elegido» (candidata): píldora amarilla con borde de tinta sobre el borde superior.
        self.insignia = panel_tinta(
            self, 0.17, 0.05, estilo.ACENTO_PRIMARIO, estilo.RADIO_CHIP_PX, sombra=False,
            position=(0, h / 2 + 0.004, -0.004))
        self.texto_insignia = Text(
            "Elegido", parent=self.insignia, origin=(0, 0), position=(0, 0, -0.003),
            scale=escala_fuente(20), font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
        self.insignia.enabled = False

        # Zona de ratón transparente sobre toda la tarjeta.
        self.zona = Button(
            parent=self, model="quad", scale=(w, h), color=color.clear, highlight_color=color.clear,
            pressed_color=color.clear, collider="box", z=-0.01)
        self.zona.on_click = self.manejar_clic
        self.zona.on_mouse_enter = self._al_entrar_raton
        self.zona.on_mouse_exit = self._al_salir_raton
        self._pintar()

    # `texto` partido en líneas que caben en el ancho útil de la tarjeta, con la fuente de `objeto`.
    def _envolver(self, objeto, texto):
        nodo = TextNode("medida")
        nodo.setFont(objeto.font)
        factor = objeto.size * objeto.scale_x
        return "\n".join(envolver_texto(texto, lambda s: nodo.calcWidth(s) * factor, self._ancho_texto))

    # Reduce `objeto` (escala de `px` px) hasta que su texto quepa en `ancho`.
    @staticmethod
    def _ajustar_ancho(objeto, px, ancho):
        nodo = TextNode("medida")
        nodo.setFont(objeto.font)
        medido = nodo.calcWidth(objeto.text) * objeto.size * escala_fuente(px)
        if medido > ancho:
            objeto.scale = escala_fuente(px) * ancho / medido

    # -- API de botón --

    def bajo_el_raton(self):
        return self.zona.hovered

    def esta_habilitado(self):
        return self._habilitado

    def fijar_habilitado(self, valor):
        self._habilitado = bool(valor)
        self.zona.disabled = not self._habilitado
        self._pintar()

    def manejar_clic(self):
        if not self._habilitado or self.accion is None:
            return
        self.accion()

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self.anillo.enabled = self._foco and self._habilitado

    def tiene_foco(self):
        return self._foco

    # Marca la tarjeta como elegida por `jugador` (nombre) o libre (None).
    def marcar_tomado(self, jugador):
        self._tomado_por = jugador
        self._pintar()

    # Resalta (True) o quita (False) la marca de candidata: anillo amarillo, insignia y fondo claro.
    def marcar_candidata(self, valor):
        self._candidata = bool(valor) and self._tomado_por is None
        self.anillo_candidata.enabled = self._candidata
        self.insignia.enabled = self._candidata
        self._pintar()

    def es_candidata(self):
        return self._candidata

    # -- Vista --

    def _al_entrar_raton(self):
        if self._habilitado:
            self.animate_y(self._y_base + 0.012, duration=0.10, curve=_curva())
        self._pintar(hover=True)

    def _al_salir_raton(self):
        self.animate_y(self._y_base, duration=0.10, curve=_curva())
        self._pintar(hover=False)

    def _pintar(self, hover=None):
        hover = self.zona.hovered if hover is None else hover
        if self._tomado_por is not None:
            tono, gris = estilo.COLOR_PANEL, True
            self.texto_lugar.text = f"Elegido por {self._tomado_por}"
            self.texto_lugar.color = rgb(estilo.ACENTO_PRIMARIO)
        else:
            gris = not self._habilitado
            tono = estilo.COLOR_PANEL if gris else (
                estilo.COLOR_SUPERFICIE_ALTA if hover else estilo.COLOR_TARJETA)
            self.texto_lugar.text = self._envolver(
                self.texto_lugar, f"Empieza en: {nombre_visible(ROLES[self.rol].lugar_inicio, corto=True)}")
            self.texto_lugar.color = rgb(estilo.COLOR_TEXTO_TENUE if gris else estilo.ACENTO_SECUNDARIO)
        self.panel.fondo.color = rgb(tono)
        self.retrato.texture = iconos.textura_retrato(self.rol, gris=gris)
        self.texto_nombre.color = rgb(estilo.COLOR_TEXTO_TENUE if gris else estilo.COLOR_TEXTO)
        self.texto_descripcion.color = rgb(estilo.COLOR_TEXTO_TENUE if gris else estilo.COLOR_TEXTO)
        self.caja_retrato.fondo.color = rgb(
            _apagar(ROLES[self.rol].color) if gris else ROLES[self.rol].color)
        self.anillo.enabled = self._foco and self._habilitado
        if self._candidata and self._tomado_por is None:
            self.panel.fondo.color = rgb(estilo.COLOR_SUPERFICIE_ALTA)

    # Entrada: la tarjeta sube desde 3 cm con ease_out (retrasada por su posición).
    def entrar(self, indice):
        self.y = self._y_base - 0.03
        self.animate_y(self._y_base, duration=0.18, delay=0.04 * indice, curve=_curva())


def _curva():
    from ursina import curve
    return curve.out_quad


def _apagar(tono):
    return tuple(int(c * 0.35 + 40 * 0.65) for c in tono)


# Escala (<= 1) con la que la fila de tarjetas cabe en pantalla: la ventana es 16:9 (ancho útil
# +-0,888) y ahí vale 1; en una ventana más estrecha se reduce para no cortar las tarjetas.
def escala_para_ancho(aspecto, n_tarjetas=4, margen=0.03):
    ancho_fila = n_tarjetas * ANCHO_TARJETA + (n_tarjetas - 1) * SEPARACION_TARJETAS
    return max(0.3, min(1.0, aspecto * (1 - 2 * margen) / ancho_fila))


# Pantalla de elección de cantidad de jugadores y de rol de cada uno.
class EscenaSeleccionRol(Escena):

    Y_INSTRUCCION = 0.405
    Y_SUBTITULO = 0.335
    Y_CANTIDAD = 0.04
    ANCHO_BOTON_CANTIDAD = 0.30
    ALTO_BOTON_CANTIDAD = a_unidades(80)
    SEPARACION_CANTIDAD = 0.36

    Y_TARJETAS = -0.03
    Y_RESUMEN = -0.345
    Y_COMENZAR = -0.43
    ANCHO_SELECCIONAR = a_unidades(360)
    X_LATERAL = 0.62           # centro de «Atrás» (izquierda) y «Cambiar» (derecha)

    def __init__(self, fabrica_sesion, al_comenzar, **opciones):
        super().__init__(**opciones)
        self._fabrica_sesion = fabrica_sesion
        self._al_comenzar = al_comenzar
        self.sesion = None
        self.total_jugadores = 0
        self._paso_previo = None
        self._aspecto = None
        self._candidata = None      # rol resaltado a la espera de «Seleccionar»
        self._elecciones = []       # roles ya confirmados, en orden (para «Cambiar»)

        self.fondo = FondoMenu(velo=ALFA_VELO, parent=self)

        dx, dy = a_unidades(3), -a_unidades(3)
        self.sombra_instruccion = Text(
            "", parent=self, origin=(0, 0), position=(dx, self.Y_INSTRUCCION + dy, 0.002),
            scale=escala_fuente(40), font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
        self.texto_instruccion = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_INSTRUCCION),
            scale=escala_fuente(40), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO),
        )
        self.texto_subtitulo = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_SUBTITULO),
            scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO))
        self.texto_resumen = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_RESUMEN),
            scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO),
        )

        # Paso 1: cantidad de jugadores.
        self.grupo_cantidad = Entity(parent=self)
        self.botones_cantidad = {}
        for n in range(1, MAX_JUGADORES + 1):
            x = (n - 2.5) * self.SEPARACION_CANTIDAD
            etiqueta = "1 jugador" if n == 1 else f"{n} jugadores"
            self.botones_cantidad[n] = BotonSecundario(
                etiqueta, al_clic=lambda n=n: self.elegir_cantidad(n),
                ancho=self.ANCHO_BOTON_CANTIDAD, alto=self.ALTO_BOTON_CANTIDAD,
                tamano_fuente_px=24, parent=self.grupo_cantidad, position=(x, self.Y_CANTIDAD),
            )

        # Paso 2: una tarjeta por rol (retrato, nombre, descripción y lugar de inicio).
        self.grupo_roles = Entity(parent=self)
        self.botones_rol = {}
        self.muestras_rol = {}
        total = len(ORDEN_ROLES)
        paso = ANCHO_TARJETA + SEPARACION_TARJETAS
        for indice, rol in enumerate(ORDEN_ROLES):
            x = (indice - (total - 1) / 2) * paso
            tarjeta = TarjetaRol(rol, al_clic=lambda rol=rol: self.previsualizar_rol(rol),
                                 parent=self.grupo_roles, position=(x, self.Y_TARJETAS))
            self.botones_rol[rol] = tarjeta
            self.muestras_rol[rol] = tarjeta.retrato   # la muestra de cada rol es su retrato

        self.boton_comenzar = BotonPrimario(
            "Comenzar", al_clic=self.comenzar, ancho=a_unidades(260), alto=a_unidades(60),
            tamano_fuente_px=26, parent=self, position=(0, self.Y_COMENZAR),
        )
        # «Seleccionar» confirma la candidata; queda deshabilitado mientras no haya ninguna.
        self.boton_seleccionar = BotonPrimario(
            "Seleccionar", al_clic=self.confirmar_candidata, ancho=self.ANCHO_SELECCIONAR,
            alto=a_unidades(60), tamano_fuente_px=26, parent=self, position=(0, self.Y_COMENZAR),
        )
        self.boton_cambiar = BotonSecundario(
            "Cambiar", al_clic=self.deshacer_ultima_eleccion, ancho=a_unidades(170), alto=a_unidades(48),
            tamano_fuente_px=20, parent=self, position=(self.X_LATERAL, self.Y_COMENZAR),
        )
        self.boton_atras = BotonSecundario(
            "Atrás", al_clic=self.volver_a_cantidad, ancho=a_unidades(170), alto=a_unidades(48),
            tamano_fuente_px=20, parent=self, position=(-self.X_LATERAL, self.Y_COMENZAR),
        )
        self.foco = FocoTeclado(self._controles_activos, parent=self)
        self._reiniciar()

    # Ajusta las filas al ancho real de la ventana (solo cambia si cambia la proporción).
    def update(self):
        aspecto = round(window.aspect_ratio, 3)
        if aspecto != self._aspecto:
            self._aspecto = aspecto
            escala = escala_para_ancho(aspecto)
            self.grupo_roles.scale = escala
            self.grupo_cantidad.scale = escala
            # Los botones laterales no deben salirse por los lados en ventanas estrechas.
            x = max(0.42, min(self.X_LATERAL, aspecto / 2 - a_unidades(170) / 2 - 0.02))
            self.boton_cambiar.x = x
            self.boton_atras.x = -x

    # Controles que el teclado puede recorrer según el paso.
    def _controles_activos(self):
        if self.total_jugadores == 0:
            return list(self.botones_cantidad.values())
        laterales = [self.boton_atras] if not self._elecciones else [self.boton_cambiar, self.boton_atras]
        if self.todos_eligieron():
            return [self.boton_comenzar] + laterales
        return list(self.botones_rol.values()) + [self.boton_seleccionar] + laterales

    # -- Ciclo de vida --

    # Cada vez que se entra se parte de una sesión nueva (y de cero jugadores).
    def al_entrar(self, **datos):
        self._reiniciar()

    def _reiniciar(self):
        self.sesion = self._fabrica_sesion() if self._fabrica_sesion else None
        self.total_jugadores = 0
        self._paso_previo = None
        self._candidata = None
        self._elecciones = []
        self.refrescar()

    # -- Pasos --

    # Paso 1: fija cuántos jugadores jugarán (1 a 4) y pasa a elegir roles.
    def elegir_cantidad(self, cantidad):
        if self.total_jugadores or cantidad not in self.botones_cantidad:
            return
        self.total_jugadores = cantidad
        self.refrescar()

    # Paso 2: el siguiente jugador toma `rol` (nombre automático "Jugador N").
    def elegir_rol(self, rol):
        if not self.total_jugadores or self.todos_eligieron():
            return
        if rol not in self.sesion.roles_disponibles():
            return
        numero = len(self.sesion.jugadores()) + 1
        self.sesion.agregar_jugador(f"Jugador {numero}", rol)
        self._elecciones.append(rol)
        self._candidata = None
        self.refrescar()

    # Resalta `rol` como candidata sin tomarlo (se puede cambiar de candidata cuantas veces se quiera).
    def previsualizar_rol(self, rol):
        if not self.total_jugadores or self.todos_eligieron() or self.sesion is None:
            return
        if rol not in self.sesion.roles_disponibles():
            return
        self._candidata = rol
        self._actualizar_candidata()
        # Con el teclado, el foco salta a «Seleccionar» para confirmar con Enter.
        if self.foco.visible:
            lista = self.foco.controles()
            if self.boton_seleccionar in lista:
                self.foco.indice = lista.index(self.boton_seleccionar)
                self.foco._aplicar()

    # Confirma la candidata como rol del jugador actual (no hace nada si no hay candidata).
    def confirmar_candidata(self):
        if self._candidata is not None:
            self.elegir_rol(self._candidata)

    # Quita la última confirmación (la sesión se reconstruye con los jugadores anteriores: el backend
    # no tiene operación de quitar). El jugador deshecho vuelve a elegir; sin candidata.
    def deshacer_ultima_eleccion(self):
        if not self._elecciones or self.sesion is None:
            return
        previas = self._elecciones[:-1]
        self.sesion = self._fabrica_sesion()
        for numero, rol in enumerate(previas, start=1):
            self.sesion.agregar_jugador(f"Jugador {numero}", rol)
        self._elecciones = previas
        self._candidata = None
        self._paso_previo = None
        self.refrescar()

    # Vuelve a «¿Cuántos jugadores?» y reinicia la sesión.
    def volver_a_cantidad(self):
        if self.total_jugadores:
            self._reiniciar()

    def todos_eligieron(self):
        return self.total_jugadores > 0 and len(self.sesion.jugadores()) >= self.total_jugadores

    def comenzar(self):
        if self.todos_eligieron():
            self._al_comenzar(self.sesion)

    # -- Vista --

    def _fijar_instruccion(self, texto):
        self.texto_instruccion.text = texto
        self.sombra_instruccion.text = texto

    # Reduce la letra de «Seleccionar: <rol>» hasta que quepa dentro del botón (nombres largos).
    def _ajustar_texto_seleccionar(self):
        boton = self.boton_seleccionar
        base = escala_fuente(26)
        boton.text_size = base
        entidad = boton.text_entity
        if entidad is None:
            return
        nodo = TextNode("medida")
        nodo.setFont(entidad.font)
        medido = nodo.calcWidth(boton.text) * entidad.size * base
        util = self.ANCHO_SELECCIONAR * 0.86
        if medido > util:
            boton.text_size = base * util / medido

    # Pinta la candidata y habilita «Seleccionar» (con su nombre) solo si hay una.
    def _actualizar_candidata(self):
        for rol, tarjeta in self.botones_rol.items():
            tarjeta.marcar_candidata(rol == self._candidata)
        hay = self._candidata is not None
        self.boton_seleccionar.text = f"Seleccionar: {ROLES[self._candidata].nombre}" if hay else "Seleccionar"
        self.boton_seleccionar.fijar_habilitado(hay)
        self._ajustar_texto_seleccionar()
        if self.total_jugadores and not self.todos_eligieron():
            numero = len(self.sesion.jugadores()) + 1
            self.texto_subtitulo.text = (
                f"Jugador {numero} de {self.total_jugadores}"
                + (f"  ·  pulsa Seleccionar para confirmar a {ROLES[self._candidata].nombre}" if hay else
                   "  ·  haz clic en un rol para resaltarlo"))

    def refrescar(self):
        eligiendo_cantidad = self.total_jugadores == 0
        listo = self.todos_eligieron()
        self.grupo_cantidad.enabled = eligiendo_cantidad
        self.grupo_roles.enabled = not eligiendo_cantidad
        self.boton_comenzar.enabled = listo
        self.boton_seleccionar.enabled = not eligiendo_cantidad and not listo
        self.boton_cambiar.enabled = bool(self._elecciones)
        self.boton_atras.enabled = not eligiendo_cantidad

        if eligiendo_cantidad:
            self._fijar_instruccion("¿Cuántos jugadores?")
            self.texto_subtitulo.text = "Se turnan en el mismo computador."
        elif listo:
            self._fijar_instruccion("Todo listo: pulsa Comenzar")
            self.texto_subtitulo.text = ""
        else:
            numero = len(self.sesion.jugadores()) + 1
            self._fijar_instruccion(f"Jugador {numero}: elige tu rol")
            self.texto_subtitulo.text = f"Jugador {numero} de {self.total_jugadores}"

        libres = self.sesion.roles_disponibles() if self.sesion else list(ORDEN_ROLES)
        elegidos = self.sesion.jugadores() if self.sesion else []
        dueno = {j.rol: j.nombre for j in elegidos}
        for rol, boton in self.botones_rol.items():
            boton.marcar_tomado(dueno.get(rol))
            boton.fijar_habilitado(rol in libres and not listo)

        self._actualizar_candidata()
        self.texto_resumen.text = "   ·   ".join(
            f"{j.nombre}: {ROLES[j.rol].nombre}" for j in elegidos
        )

        paso = "cantidad" if eligiendo_cantidad else ("listo" if listo else "roles")
        if paso != self._paso_previo:
            if paso == "roles" and self._paso_previo == "cantidad":
                for indice, tarjeta in enumerate(self.botones_rol.values()):
                    tarjeta.entrar(indice)
            self._paso_previo = paso
        self.foco.reiniciar()

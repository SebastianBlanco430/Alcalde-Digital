# HUD 2D del mundo (Ursina, en camera.ui): teléfono, minimapa, aviso de interacción
# y panel de turno (la ruta en el piso la dibuja frontend/marcadores_mundo.py).
# Todo se decide en frontend/hud_calculos.py (Python puro, con tests sin ventana);
# aquí solo se dibuja lo que el modelo dice. Coordenadas de camera.ui: y en
# [-0.5, 0.5] (0.5 = arriba), x en [-aspecto/2, aspecto/2].
#
# Nada de aquí usa update(): EscenaMundo llama a HudMundo.actualizar(dt) en su
# update(), así la escena desactivada no gasta nada y los tests avanzan las
# animaciones a mano con dt fijos (sin depender del reloj real).
#
# Fuente por defecto: no tiene flechas ni ✓ ★ ▲ (por eso la flecha del GPS es una
# malla propia) y Text interpreta "<...>" como etiquetas (por eso _seguro()).

import dataclasses
import math
import os
import time

from panda3d.core import TextNode
from ursina import Entity, Mesh, Text, camera, color, window

from backend.datos.nombres_visibles import nombre_visible
from backend.logica import ajustes as modelo_ajustes
from backend.logica import navegacion
from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
from backend.logica.roles import ROLES
from frontend import (
    diseno_adaptable, diseno_adaptable_calculos, estilo, hud_calculos, hud_contextual_calculos as hctx,
    hud_esquinas_calculos as hec, hud_modo_calculos as hm, hud_tamanos_calculos as ht, iconos,
    panel_unico_calculos as pu,
    minimapa_calculos as mm, notificaciones_calculos)
from frontend.componentes import (
    BarraIndicador, BotonAccion, BotonPrimario, a_unidades, destruir_arbol, escala_fuente,
    modelo_redondeado, panel_tinta, rgb)
from frontend.componentes import boton_piel, panel_piel, piel_botw
from frontend import ui_botw_calculos
from frontend.texto import envolver_texto

MARGEN = 0.02                       # separación de los bordes de la pantalla
ESCALA_HUD = 0.9                     # el HUD conserva su diseño, reducido un 10 %
COLOR_FONDO_HUD = color.rgba32(12, 14, 24, 240)
COLOR_RUTA = estilo.COLOR_RUTA          # cian: la ruta (minimapa y mundo); fuente única en estilo.py
COLOR_DESTINO = estilo.COLOR_DESTINO    # amarillo: el destino (igual que la baliza del mundo)
COLOR_ALERTA = (214, 62, 62)        # insignia de no leídos
COLOR_RESALTADO = (62, 78, 138)     # mensaje sin leer en el teléfono

# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW, encendida por defecto, =0 o Ajustes › Estilo «Clásico»
# la apagan): los chips y marcos del HUD pasan a velo violeta translúcido con filo claro. Los nombres de arriba no
# cambian; los fondos se piden a _fondo_hud() y los tonos a _tono().
COLOR_FONDO_HUD_BOTW = color.rgba32(*estilo.BOTW_VELO, estilo.BOTW_ALFA_VELO)


# ¿El tutorial está señalando el HUD? La consulta la pone frontend/registro_tutorial.py con fijar_consulta_senalando():
# una vista no importa controladores (contrato MVC, R3). Sin consulta, nada se está señalando.
_CONSULTA_SENALANDO = None


def fijar_consulta_senalando(consulta):
    global _CONSULTA_SENALANDO
    _CONSULTA_SENALANDO = consulta


# Fondo de los bloques del HUD que no usan el estilo único: el de siempre o el velo BOTW.
def _fondo_hud():
    return COLOR_FONDO_HUD_BOTW if piel_botw() else COLOR_FONDO_HUD


# Tono de estilo.py con su equivalente BOTW si la piel está puesta.
def _tono(tono):
    return ui_botw_calculos.tono(tono)


# Curva de salida cuadrática (rápida al inicio, suave al final) para t en [0, 1].
def _ease_out_quad(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


# Icono cuadrado del HUD (textura de frontend/iconos.py) de `lado` unidades de camera.ui.
def _icono(padre, nombre, lado, posicion, **opciones):
    return Entity(parent=padre, model="quad", texture=iconos.textura_icono(nombre),
                  scale=(lado, lado), position=posicion, **opciones)


# Separa «Misión: X» en ("Misión:", "X"); otro texto (p. ej. «Sin misión activa») -> ("", texto).
PREFIJO_MISION = "Misión:"


def _separar_mision(cadena):
    if cadena.startswith(PREFIJO_MISION):
        return PREFIJO_MISION, cadena[len(PREFIJO_MISION):].lstrip()
    return "", cadena


# Text interpreta "<...>" como etiquetas: se cambian por paréntesis.
def _seguro(cadena):
    return cadena.replace("<", "(").replace(">", ")")


# Función cadena -> ancho (camera.ui) con la fuente y la escala de un Text ya creado.
def _medidor(texto):
    nodo = TextNode("medida")
    nodo.setFont(texto.font)
    factor = texto.size * texto.scale_x

    def medir(cadena):
        # Panda a veces lanza AssertionError («glyph->_page->get_num_components() == 1», dynamicTextFont.cxx) al
        # generar glifos nuevos desde Python; en C++ solo avisa y sigue. Visto el 2026-11-21 al armar el toast (tumbaba
        # el juego). Si pasa, se estima el ancho (~0,55 em por carácter) en vez de cerrar el juego.
        try:
            return nodo.calcWidth(cadena) * factor
        except AssertionError:
            return len(cadena) * ANCHO_EM_ESTIMADO * factor

    return medir


ANCHO_EM_ESTIMADO = 0.55


# Text de varias líneas con origen arriba-izquierda, envuelto a `ancho`. Devuelve
# (texto, alto) con el alto estimado en unidades de camera.ui.
# `max_lineas`: si el texto ocupa más, se corta y la última línea acaba en «...» (None = sin límite).
def _texto_envuelto(padre, cadena, ancho, px, rgb_texto, posicion, max_lineas=None):
    texto = Text("", parent=padre, origin=(-0.5, 0.5), position=posicion,
                 scale=escala_fuente(px), color=rgb(rgb_texto))
    texto.line_height = 1.25
    medir = _medidor(texto)
    lineas = envolver_texto(_seguro(cadena), medir, ancho) or [""]
    if max_lineas is not None and len(lineas) > max(1, max_lineas):
        lineas = lineas[:max(1, max_lineas)]
        ultima = lineas[-1]
        while ultima and medir(ultima + "...") > ancho:
            ultima = ultima[:-1]
        lineas[-1] = ultima.rstrip() + "..."
    texto.text = "\n".join(lineas)
    return texto, len(lineas) * a_unidades(px) * texto.line_height


# Alto de una línea de `px` en _texto_envuelto (line_height 1.25).
def _alto_linea(px):
    return a_unidades(px) * 1.25


def _fondo(padre, ancho, alto, tono, radio_px=8, **opciones):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio_px),
                  scale=(ancho, alto), color=tono, **opciones)


# panel_tinta con el estilo único del bloque (M3.3, panel_unico_calculos): mismo radio, borde y tono por categoría.
def _tinta(padre, bloque, ancho, alto, **opciones):
    e = pu.estilo_de(bloque)
    # con la piel BOTW el fondo de los bloques es el velo violeta translúcido del menú (panel_piel lo pone con COLOR_PANEL)
    tono = estilo.COLOR_PANEL if piel_botw() and tuple(e.tono) == estilo.COLOR_FONDO else e.tono
    return panel_piel(padre, ancho, alto, tono=tono, radio_px=e.radio_px, borde_px=e.borde_px, **opciones)


# Fondo de tamaño variable (FondoTinta o el _fondo de antes) y su alfa de aparición.
def _ajustar_fondo(fondo, ancho, alto, radio_px):
    if isinstance(fondo, FondoTinta):
        fondo.ajustar(ancho, alto)
    else:
        fondo.model = modelo_redondeado(ancho, alto, radio_px)
        fondo.scale = (ancho, alto)


def _alfa_fondo(fondo, nivel):
    if isinstance(fondo, FondoTinta):
        fondo.fijar_alfa(nivel)
    else:
        base = _fondo_hud()
        fondo.color = color.rgba(base.r, base.g, base.b, base.a * nivel)


# Fondo de un bloque del HUD con el estilo único que cambia de tamaño (lo rehace solo si cambia) y se funde con
# setAlphaScale (cara, borde y sombra a la vez). Sustituye a un `_fondo` cuando ALCALDE_PANEL_UNICO está encendida.
class FondoTinta(Entity):

    def __init__(self, padre, bloque, ancho, alto, **opciones):
        super().__init__(parent=padre, **opciones)
        self.bloque = bloque
        self.panel = None
        self._medidas = None
        self._alfa = None
        self.ajustar(ancho, alto)

    def ajustar(self, ancho, alto):
        medidas = (round(ancho, 4), round(alto, 4))
        if medidas == self._medidas:
            return
        self._medidas = medidas
        if self.panel is not None:
            destruir_arbol(self.panel)
        self.panel = _tinta(self, self.bloque, ancho, alto)
        if getattr(self, "_fundido", None) is not None:
            self._fundido.invalidar()

    def fijar_alfa(self, alfa):
        alfa = round(float(alfa), 3)
        if hctx.animaciones_activas():   # M3.6: fundido REAL pieza a pieza (setAlphaScale no baja a los modelos)
            if getattr(self, "_fundido", None) is None:
                from frontend.fundido_ui import FundidoArbol
                self._fundido = FundidoArbol(self)
            self._fundido.aplicar(alfa)
            return
        if alfa == self._alfa:
            return
        if self._alfa is None:
            from panda3d.core import TransparencyAttrib
            self.setTransparency(TransparencyAttrib.M_alpha)
        self._alfa = alfa
        self.setAlphaScale(alfa)


# -- Sello de la Tradición y silencio de la noche (hilo conductor, docs/HILO_CONDUCTOR.md) ----------------------------


# Capa del sello (1..4) si `texto` es el mensaje de la misión `mision` y su rumor lleva sello, o el anuncio de campaña
# del día 5 (frontend/carteles_campana.py); None si no
# (ALCALDE_HILO_SELLO=0 o ALCALDE_HILO=0: nunca). El día sale del reloj de la partida (día 1 sin reloj).
def _capa_sello(texto, mision):
    if not texto:
        return None
    from backend.logica import sello_rumores
    from frontend import ambiente_vivo
    anuncio = sello_rumores.capa_anuncio(texto, ambiente_vivo.dia() or 1)
    if anuncio is not None or mision is None:
        return anuncio
    mensaje = hud_calculos.glosar_texto(getattr(mision, "mensaje", "") or "")
    if not mensaje or mensaje not in texto:
        return None
    return sello_rumores.capa_de(getattr(mision, "id", None), ambiente_vivo.dia() or 1)


# Silencio de la noche (modo normal con noches saltadas): desde las 19:30 el mensaje de una misión nueva no sale en el
# banner (sigue en el teléfono). En feria la hora no es de reloj: no hay silencio.
def _en_silencio(texto, mision):
    if mision is None or not texto:
        return False
    from backend.logica import modo_feria, reloj_partida
    from frontend import ambiente_vivo, radio_calculos
    hora = ambiente_vivo.hora()
    if hora is None or modo_feria.activo() or not reloj_partida.noches_activas():
        return False
    mensaje = hud_calculos.glosar_texto(getattr(mision, "mensaje", "") or "")
    return bool(mensaje) and mensaje in texto and radio_calculos.en_silencio(hora)


# Lado (unidades de camera.ui) del sello de la capa `capa`.
def _lado_sello(capa):
    from frontend import sello_tradicion_calculos as stc
    return a_unidades(stc.estilo_de_capa(capa)[0])


# Pone el sello de la capa `capa` en un bloque de `ancho` x `alto` centrado en 0 (banner, toast o fila del panel).
def _poner_sello(padre, capa, ancho, alto, toast=False):
    from frontend import sello_tradicion, sello_tradicion_calculos as stc
    lado_px, _alfa, sitio = stc.estilo_de_capa(capa)
    lado = a_unidades(lado_px)
    if toast:                                   # una línea: el sello va pegado a la izquierda, por fuera
        posicion = (-ancho / 2 - lado / 2 - 0.006, 0, -0.003)
    elif sitio == "esquina":
        posicion = (ancho / 2 - lado / 2 - 0.006, -alto / 2 + lado / 2 + 0.006, -0.003)
    else:                                       # junto al remitente (arriba a la derecha), más grande en la capa 3-4
        posicion = (ancho / 2 - lado / 2 - 0.008, alto / 2 - lado / 2 - 0.006, -0.003)
    return sello_tradicion.crear_sello_capa(padre, capa, posicion)


# -- Teléfono ------------------------------------------------------------------


class TelefonoUI(Entity):

    DURACION_NOTIFICACION = 4.0     # segundos con el banner visible
    VELOCIDAD_DESLIZ = 5.0          # niveles por segundo (el banner sube en 0.2 s)

    ANCHO_ICONO, ALTO_ICONO = 0.075, 0.12
    ANCHO_BANNER = 0.44
    ANCHO_PANEL, ALTO_PANEL = 0.42, 0.50      # más alto tapa el chip del destino del minimapa; la casilla
                                              # «Seguir misión» le quita sitio a los mensajes (se recortan solos)
    ALTO_CASILLA = a_unidades(34)

    # obtener_telefono(): Telefono del jugador ACTIVO. obtener_mision(): Mision actual
    # o None. Son callables para no atar la vista a la sesión (se prueban con falsos).
    def __init__(self, obtener_telefono, obtener_mision, **opciones):
        super().__init__(**opciones)
        self._obtener_telefono = obtener_telefono
        self._obtener_mision = obtener_mision
        self._telefono = None
        self._nuevos_al_abrir = 0        # no leídos justo antes de abrir (para resaltar)
        self.tiempo_notificacion = 0.0
        self.nivel_banner = 0.0          # 0 = oculto bajo la pantalla, 1 = a la vista
        # M3.6 (ALCALDE_UI_ANIMACIONES): toast y banner con la regla de la UI (entra 180 ms, sale 120 ms, ease-out).
        self._fundido_banner = None
        if hctx.animaciones_activas():
            self._fundido_banner = (hctx.Fundido() if hctx.activo() else
                                    hctx.Fundido(hctx.TIEMPOS.BANNER_ENTRADA, hctx.TIEMPOS.BANNER_SALIDA))
        self._arbol_toast = None
        self.vista = None
        self._firma_banner = None
        self._firma_panel = None
        # Varios mensajes seguidos con el teléfono cerrado: el banner los repasa de uno en uno (4 s cada uno) en vez de
        # pisarse (docs/PLAN_CLARIDAD_JUEGO.md §2.6). None = el banner de antes (ALCALDE_NOTIF_TELEFONO=0).
        # HUD contextual (M3.2, ALCALDE_HUD_CONTEXTUAL): en vez del banner largo, un toast de UNA línea junto al botón
        # (hctx.TIEMPOS.TOAST s por mensaje) que entra y sale con fundido. False = el banner de antes.
        self.contextual = hctx.activo()
        self.duracion_notificacion = hctx.TIEMPOS.TOAST if self.contextual else self.DURACION_NOTIFICACION
        self._cola_banner = notificaciones_calculos.ColaBanner(self.duracion_notificacion) \
            if notificaciones_calculos.activo() else None

        self.x_derecho = window.aspect_ratio / 2 - MARGEN
        self.y_inferior = -0.5 + MARGEN
        self._construir_icono()
        self.banner = Entity(parent=self)
        self.panel = Entity(parent=self, enabled=False)

    # -- Construcción --

    def _construir_icono(self):
        antes = list(self.children)
        self._construir_piezas_icono()
        self.grupo_icono = None
        if hm.activo():          # M3.5: las piezas del botón en un grupo, para fundirlas juntas en el HUD «mínimo»
            self.grupo_icono = Entity(parent=self)
            for pieza in [c for c in self.children if c not in antes and c is not self.grupo_icono]:
                pieza.parent = self.grupo_icono

    def _construir_piezas_icono(self):
        centro_x = self.x_derecho - self.ANCHO_ICONO / 2
        centro_y = self.y_inferior + self.ALTO_ICONO / 2
        self.icono = BotonAccion("", al_clic=self.alternar, ancho=self.ANCHO_ICONO,
                                 alto=self.ALTO_ICONO, parent=self, position=(centro_x, centro_y))
        self.icono.color = rgb((26, 29, 44))
        self.icono.highlight_color = rgb((44, 50, 78))
        self.icono.pressed_color = rgb((44, 50, 78))
        if pu.activo():          # estilo único (M3.3): esquinas de chip, borde de tinta y sombra plana detrás del botón
            e = pu.estilo_de("telefono")
            self.icono.model = modelo_redondeado(self.ANCHO_ICONO, self.ALTO_ICONO, e.radio_px)
            self.fondo_icono = _tinta(self, "telefono", self.ANCHO_ICONO, self.ALTO_ICONO,
                                      position=(centro_x, centro_y, 0.001))
        ancho_pantalla, alto_pantalla = self.ANCHO_ICONO - 0.014, self.ALTO_ICONO - 0.026
        _fondo(self, ancho_pantalla, alto_pantalla, rgb(_tono(estilo.COLOR_BOTON)), 5,
               position=(centro_x, centro_y + 0.004, -0.001))
        # icono del teléfono (frontend/iconos.py) dentro de la pantalla
        _icono(self, "telefono", ancho_pantalla, (centro_x, centro_y + 0.004, -0.002))
        # insignia roja con el contador de no leídos
        self.insignia = Entity(parent=self, position=(centro_x - 0.03, centro_y + 0.052, -0.004),
                               enabled=False)
        Entity(parent=self.insignia, model="circle", scale=0.04, color=rgb(COLOR_ALERTA))
        self.texto_contador = Text("0", parent=self.insignia, origin=(0, 0), position=(0, 0, -0.001),
                                   scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO))

    # -- Estado --

    def telefono(self):
        return self._telefono

    def alternar(self):
        if self._telefono is not None:
            self._telefono.alternar()

    # Casilla «Seguir misión» (clic en el panel; la tecla M la maneja el controlador del jugador).
    def alternar_seguir(self):
        if self._telefono is not None:
            self._telefono.alternar_seguir_mision()

    # Un paso de `dt` segundos: sincroniza con el teléfono del jugador activo, corre el
    # reloj de la notificación (4 s y luego terminar_notificacion), desliza el banner y
    # dibuja. Con dt = 0 solo sincroniza y dibuja. Determinista: depende de los dt.
    def avanzar(self, dt):
        telefono = self._obtener_telefono()
        if telefono is not self._telefono:        # cambió el turno: otro teléfono
            if self._telefono is not None:
                # El saliente ya no se ve: su banner no debe quedar "notificando" para siempre
                # (los mensajes siguen sin leer; no se marcan como leídos).
                self._telefono.terminar_notificacion()
            self._telefono = telefono
            self.tiempo_notificacion = 0.0
            self.nivel_banner = 0.0
            if self._fundido_banner is not None:
                self._fundido_banner.fijar(0.0)
            self._nuevos_al_abrir = 0
            if self._cola_banner is not None and telefono is not None:
                self._cola_banner.reiniciar(len(telefono.mensajes()), telefono.no_leidos())
        if telefono is None:
            self.enabled = False
            return
        self.enabled = True

        if telefono.estado() == hud_calculos.ABIERTO:
            pass                                   # conserva cuántos eran nuevos
        else:
            self._nuevos_al_abrir = telefono.no_leidos()
        if self._cola_banner is not None:
            notificando = telefono.estado() == hud_calculos.NOTIFICANDO
            if self._cola_banner.avanzar(notificando, len(telefono.mensajes()), dt):
                telefono.terminar_notificacion()
            self.tiempo_notificacion = self._cola_banner.tiempo
        elif telefono.estado() == hud_calculos.NOTIFICANDO:
            self.tiempo_notificacion += dt
            if self.tiempo_notificacion >= self.duracion_notificacion:
                telefono.terminar_notificacion()
        else:
            self.tiempo_notificacion = 0.0

        if telefono.estado() == hud_calculos.NOTIFICANDO and telefono.mensajes():
            # Silencio desde las 19:30 (hilo conductor): la misión nueva no se anuncia en el banner.
            if _en_silencio(hud_calculos.glosar_texto(telefono.mensajes()[-1].texto), self._obtener_mision()):
                telefono.terminar_notificacion()
        objetivo = 1.0 if telefono.estado() == hud_calculos.NOTIFICANDO else 0.0
        if self._fundido_banner is not None:          # M3.6: nivel_banner = alfa ya con su curva
            self.nivel_banner = self._fundido_banner.avanzar(objetivo > 0, dt)
        elif self.contextual:
            self.nivel_banner = hctx.avanzar_fundido(self.nivel_banner, objetivo > 0, dt)
        else:
            self.nivel_banner = hud_calculos.avanzar_hacia(
                self.nivel_banner, objetivo, dt * self.VELOCIDAD_DESLIZ)
        self.vista = hud_calculos.vista_telefono(
            telefono, self._obtener_mision(), self._nuevos_al_abrir)
        indice = None if self._cola_banner is None else self._cola_banner.indice
        if indice is not None:                     # el banner enseña el mensaje que toca de la cola, no solo el último
            mensajes = telefono.mensajes()
            if indice < len(mensajes) - 1:
                self.vista = dataclasses.replace(
                    self.vista, texto_notificacion=hud_calculos.glosar_texto(mensajes[indice].texto))
        self._dibujar()

    # Lo que se ve ahora (para los tests y el HUD).
    def banner_visible(self):
        return self.banner.enabled and self.nivel_banner > 0

    def panel_visible(self):
        return self.panel.enabled

    def contador_visible(self):
        return self.insignia.enabled

    # -- Dibujo --

    def _dibujar(self):
        vista = self.vista
        self.insignia.enabled = vista.contador > 0
        contador = str(min(vista.contador, 9)) + ("+" if vista.contador > 9 else "")
        if self.texto_contador.text != contador:     # .text rehace la malla aunque sea el mismo texto
            self.texto_contador.text = contador
        self._dibujar_banner(vista)
        self._dibujar_panel(vista)

    def _dibujar_banner(self, vista):
        if vista.texto_notificacion != self._firma_banner:
            self._firma_banner = vista.texto_notificacion
            self._armar_banner(vista.texto_notificacion)
        visible = vista.modo == hud_calculos.MODO_NOTIFICACION or self.nivel_banner > 0
        self.banner.enabled = (visible and bool(vista.texto_notificacion)
                               and vista.modo != hud_calculos.MODO_ABIERTO)
        if self.contextual:
            self._colocar_toast()
            return
        y_visible = self.y_inferior + self._alto_banner / 2
        y_oculto = -0.5 - self._alto_banner / 2 - MARGEN
        self.banner.position = (self.x_derecho - self.ANCHO_ICONO - 0.012 - self.ANCHO_BANNER / 2,
                                hud_calculos.mezclar(y_oculto, y_visible, self.nivel_banner
                                                     if self._fundido_banner is not None
                                                     else _ease_out_quad(self.nivel_banner)))

    # -- Toast (HUD contextual) --

    ANCHO_TOAST = 0.44               # máximo; el toast se ajusta a su texto
    PX_TOAST = 16
    HUECO_TOAST = 0.02               # aire entre el toast y el botón del teléfono

    # Toast de UNA línea, centrado en altura con el botón y a su izquierda; entra deslizándose y fundiéndose.
    def _colocar_toast(self):
        alfa = self.nivel_banner if self._fundido_banner is not None else hctx.alfa_de(self.nivel_banner)
        x = (self.x_derecho - self.ANCHO_ICONO - self.HUECO_TOAST - self._ancho_toast / 2
             + (1.0 - alfa) * hctx.TIEMPOS.DESLIZ_TOAST)
        self.banner.position = (x, self.y_inferior + self.ALTO_ICONO / 2)
        if alfa != getattr(self, "_alfa_toast", None):
            self._alfa_toast = alfa
            if self._fundido_banner is not None:      # M3.6: fundido REAL del toast (pieza a pieza)
                if self._arbol_toast is None:
                    from frontend.fundido_ui import FundidoArbol
                    self._arbol_toast = FundidoArbol(self.banner)
                self._arbol_toast.aplicar(alfa)
            else:
                self.banner.setAlphaScale(alfa)

    def _armar_toast(self, texto):
        from panda3d.core import TransparencyAttrib
        for hijo in list(self.banner.children):
            destruir_arbol(hijo)
        relleno, lado_icono = (pu.relleno("toast") if pu.activo() else 0.012), a_unidades(20)
        linea = Text("", parent=self.banner, origin=(-0.5, 0), scale=escala_fuente(self.PX_TOAST),
                     color=rgb(estilo.COLOR_TEXTO))
        medir = _medidor(linea)
        maximo = self.ANCHO_TOAST - 2 * relleno - lado_icono - 0.008
        linea.text = _seguro(hctx.linea_toast(texto, medir, maximo))
        ancho = min(self.ANCHO_TOAST, medir(linea.text) + 2 * relleno + lado_icono + 0.008)
        alto = a_unidades(self.PX_TOAST) * 1.5 + 2 * 0.008
        self._ancho_toast, self._alto_banner = ancho, alto
        if pu.activo():
            _tinta(self.banner, "toast", ancho, alto, z=0.002)
        else:
            _fondo(self.banner, ancho, alto, rgb(_tono(estilo.COLOR_PANEL)), 10, z=0.002)
        izquierda = -ancho / 2 + relleno
        _icono(self.banner, "telefono", lado_icono, (izquierda + lado_icono / 2, 0, -0.001))
        linea.position = (izquierda + lado_icono + 0.008, 0, -0.001)
        capa = _capa_sello(texto, self._obtener_mision())
        if capa is not None:
            _poner_sello(self.banner, capa, ancho, alto, toast=True)
        self.banner.setTransparency(TransparencyAttrib.M_alpha)
        self._alfa_toast = None
        if self._arbol_toast is not None:
            self._arbol_toast.invalidar()

    _ancho_toast = 0.3

    def _armar_banner(self, texto):
        if self.contextual:
            self._armar_toast(texto)
            return
        for hijo in list(self.banner.children):
            destruir_arbol(hijo)
        relleno = 0.012
        titulo = Text(hud_calculos.ENCABEZADO_TELEFONO, parent=self.banner, origin=(-0.5, 0.5),
                      scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))
        lado_icono = a_unidades(24)
        cuerpo, alto_texto = _texto_envuelto(
            self.banner, texto, self.ANCHO_BANNER - 2 * relleno, 18, estilo.COLOR_TEXTO, (0, 0))
        self._alto_banner = a_unidades(15) * 1.3 + alto_texto + 2 * relleno
        _fondo(self.banner, self.ANCHO_BANNER, self._alto_banner, rgb(_tono(estilo.COLOR_PANEL)), 10,
               z=0.002)
        izquierda, arriba = -self.ANCHO_BANNER / 2 + relleno, self._alto_banner / 2 - relleno
        _icono(self.banner, "telefono", lado_icono,
               (izquierda + lado_icono / 2, arriba - a_unidades(8), -0.001))
        titulo.position = (izquierda + lado_icono + 0.006, arriba, -0.001)
        cuerpo.position = (izquierda, arriba - a_unidades(15) * 1.3, -0.001)
        capa = _capa_sello(texto, self._obtener_mision())
        if capa is not None:
            _poner_sello(self.banner, capa, self.ANCHO_BANNER, self._alto_banner)

    _alto_banner = 0.12

    def _dibujar_panel(self, vista):
        abierto = vista.modo == hud_calculos.MODO_ABIERTO
        self.panel.enabled = abierto
        if not abierto or vista == self._firma_panel:
            return
        self._firma_panel = vista
        for hijo in list(self.panel.children):
            destruir_arbol(hijo)
        ancho, alto = self.ANCHO_PANEL, self.ALTO_PANEL
        relleno = 0.016
        izquierda, ancho_texto = -ancho / 2 + relleno, ancho - 2 * relleno
        centro_x = self.x_derecho - ancho / 2
        centro_y = self.y_inferior + self.ALTO_ICONO + 0.012 + alto / 2
        self.panel.position = (centro_x, centro_y)
        _fondo(self.panel, ancho, alto, rgb(_tono(estilo.COLOR_PANEL)), 12, z=0.002)

        y = alto / 2 - relleno
        lado_icono = a_unidades(30)
        _icono(self.panel, "telefono", lado_icono, (izquierda + lado_icono / 2, y - a_unidades(15), -0.001))
        Text(vista.encabezado, parent=self.panel, origin=(-0.5, 0.5),
             position=(izquierda + lado_icono + 0.008, y, -0.001),
             scale=escala_fuente(26), color=rgb(estilo.COLOR_TEXTO))
        y -= a_unidades(26) * 1.3
        Entity(parent=self.panel, model="quad", scale=(ancho_texto, 0.002), position=(0, y, -0.001),
               color=rgb(estilo.COLOR_BARRA_FONDO))
        y -= 0.012
        prefijo, titulo_mision = _separar_mision(vista.linea_mision)
        if prefijo:                      # «Misión:» en el color del destino, con su icono
            lado_mision = a_unidades(20)
            _icono(self.panel, "mision", lado_mision, (izquierda + lado_mision / 2, y - a_unidades(10), -0.001))
            Text(prefijo, parent=self.panel, origin=(-0.5, 0.5),
                 position=(izquierda + lado_mision + 0.006, y, -0.001),
                 scale=escala_fuente(17), color=rgb(COLOR_DESTINO))
            y -= a_unidades(17) * 1.35
        mision, alto_mision = _texto_envuelto(
            self.panel, titulo_mision, ancho_texto, 19, estilo.COLOR_TEXTO, (izquierda, y, -0.001))
        y -= alto_mision
        if vista.linea_destino:
            _, alto_destino = _texto_envuelto(self.panel, vista.linea_destino, ancho_texto, 17,
                                              estilo.COLOR_TEXTO_TENUE, (izquierda, y, -0.001))
            y -= max(alto_destino, a_unidades(17) * 1.25)
        if vista.texto_seguir:
            y = self._dibujar_casilla(vista, izquierda, ancho_texto, y - 0.008)
        y -= 0.014
        Text("Mensajes", parent=self.panel, origin=(-0.5, 0.5), position=(izquierda, y, -0.001),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))
        y -= a_unidades(17) * 1.5
        Text("Tab para cerrar", parent=self.panel, origin=(0.5, -0.5),
             position=(ancho / 2 - relleno, -alto / 2 + 0.008, -0.001),
             scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))

        limite_inferior = -alto / 2 + 0.034      # deja sitio a la ayuda de la base
        for indice, fila in enumerate(vista.filas):      # los más recientes primero
            capa = _capa_sello(fila.texto, self._obtener_mision())
            # Con sello, el texto le deja su sitio a la derecha (si no, el sello tapa el final de la línea).
            ancho_cuerpo = ancho_texto - 0.016 - (_lado_sello(capa) + 0.008 if capa is not None else 0.0)
            cuerpo, alto_texto = _texto_envuelto(
                self.panel, fila.texto, ancho_cuerpo, 16, estilo.COLOR_TEXTO,
                (izquierda + 0.008, y - 0.007, -0.002))
            alto_fila = alto_texto + 0.014
            if y - alto_fila < limite_inferior and indice == 0:
                # Con misión activa (título, destino y casilla) el último mensaje casi nunca cabía entero y la lista
                # quedaba vacía, sin el mensaje ni su sello: el más reciente se muestra siempre, recortado con «...».
                cabe = int((y - limite_inferior - 0.014) // _alto_linea(16))
                if cabe >= 1:
                    destruir_arbol(cuerpo)
                    cuerpo, alto_texto = _texto_envuelto(
                        self.panel, fila.texto, ancho_cuerpo, 16, estilo.COLOR_TEXTO,
                        (izquierda + 0.008, y - 0.007, -0.002), max_lineas=cabe)
                    alto_fila = alto_texto + 0.014
            if y - alto_fila < limite_inferior:   # no cabe: se omiten los más antiguos
                destruir_arbol(cuerpo)
                break
            tono = COLOR_RESALTADO if fila.resaltado else _tono(estilo.COLOR_TARJETA)
            _fondo(self.panel, ancho_texto, alto_fila, rgb(tono), 6,
                   position=(0, y - alto_fila / 2, -0.001))
            if capa is not None:                 # sello de la Tradición en el mensaje (hilo conductor)
                fila_sello = Entity(parent=self.panel, position=(0, y - alto_fila / 2, 0))
                _poner_sello(fila_sello, capa, ancho_texto, alto_fila)
            y -= alto_fila + 0.008

    # Casilla «Seguir misión» (docs/DISENO.md): toda la fila es un botón; caja con borde de tinta, amarilla y con
    # visto si está marcada, vacía si no, y el estado ESCRITO («Sí» / «No»), no solo dibujado. Devuelve la y de abajo.
    def _dibujar_casilla(self, vista, izquierda, ancho_texto, y):
        alto = self.ALTO_CASILLA
        centro_y = y - alto / 2
        fila = BotonAccion("", al_clic=self.alternar_seguir, ancho=ancho_texto, alto=alto, parent=self.panel,
                           position=(0, centro_y, -0.001))
        fila.color = rgb(_tono(estilo.COLOR_TARJETA))
        fila.highlight_color = rgb(estilo.COLOR_SUPERFICIE_ALTA)
        fila.pressed_color = rgb(estilo.COLOR_SUPERFICIE_ALTA)
        lado = a_unidades(20)
        cx = izquierda + 0.012 + lado / 2
        borde = a_unidades(3)
        _fondo(self.panel, lado + 2 * borde, lado + 2 * borde, rgb(_tono(estilo.TINTA)), 4, position=(cx, centro_y, -0.002))
        _fondo(self.panel, lado, lado, rgb(COLOR_DESTINO if vista.sigue_mision else _tono(estilo.COLOR_FONDO)), 3,
               position=(cx, centro_y, -0.003))
        if vista.sigue_mision:              # visto de tinta: un trazo corto y uno largo
            Entity(parent=self.panel, model="quad", color=rgb(_tono(estilo.TINTA)), rotation_z=45,
                   position=(cx - lado * 0.2, centro_y - lado * 0.06, -0.004), scale=(lado * 0.42, lado * 0.16))
            Entity(parent=self.panel, model="quad", color=rgb(_tono(estilo.TINTA)), rotation_z=-55,
                   position=(cx + lado * 0.1, centro_y + lado * 0.06, -0.004), scale=(lado * 0.7, lado * 0.16))
        Text(vista.texto_seguir, parent=self.panel, origin=(-0.5, 0), position=(cx + lado / 2 + 0.012, centro_y, -0.004),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO))
        return y - alto


# -- Minimapa ------------------------------------------------------------------


class Minimapa(Entity):

    ANCHO = 280 / 720                # ~280 x 200 px de la ventana de 1280 x 720
    ALTO = 200 / 720
    LARGO_FLECHA = 0.05
    YAW_MIN_CASAS = 1.5              # grados de giro a partir de los cuales se rehacen casas y escaleras
    COLOR_CASAS = color.rgba32(88, 92, 108, 200)    # casas: algo transparentes
    COLOR_ESCALERAS = color.rgba32(200, 190, 160, 255)
    ANCHO_MIN_ESCALERA = 0.003       # grosor mínimo de una escalera en camera.ui (unidades)
    COLOR_CALLES = (140, 146, 164)   # antes (112, 116, 132): más contraste sobre el fondo oscuro
    COLOR_LUGAR_SIN_IDENTIDAD = (150, 152, 164)   # lugar que no está en estilo.COLORES_LUGAR

    # rotacion_libre (mundo 3D): el yaw se cambia cada frame con fijar_yaw() y la escala no depende de él.
    # registro: RegistroMinimapa del que se leen marcadores y zonas (None = el global de minimapa_calculos).
    # gestor_ajustes: de dónde salen giro y detalle (None = el global; sin ajustes activos se queda en lo de siempre).
    def __init__(self, mapa, yaw_grados=None, rotacion_libre=False, registro=None, gestor_ajustes=None, **opciones):
        super().__init__(**opciones)
        self._mapa = mapa
        yaw = 0 if yaw_grados is None else yaw_grados
        self.registro = registro if registro is not None else mm.registro()
        self.modo_rotacion = "camara"          # «camara» (gira con la cámara) | «norte» (norte arriba)
        self._satelite = None                  # foto aérea de la ciudad de fondo (mapa_satelite); None = el minimapa vectorial de siempre
        self.fondo_satelite = None
        # Misión con punto exacto (puerta de la Fiscalía): EscenaMundo deja aquí el punto y la línea del suelo para que
        # el minimapa marque ese mismo destino (sesión E, ruta-fiscalia). None = el lugar y la ruta de esquinas.
        self.punto_destino = None
        self.ruta_puntos = None
        self.densidad = 2                     # nivel de detalle 1..3 (minimapa_calculos.detalle)
        self._yaw_camara = yaw                 # yaw real de la cámara (la geometría usa el efectivo según el modo)
        self.geometria = hud_calculos.GeometriaMinimapa(
            mapa, (self.ANCHO, self.ALTO), yaw, rotacion_libre=rotacion_libre)
        self.position = (window.aspect_ratio / 2 - MARGEN - self.ANCHO / 2,
                         0.5 - MARGEN - self.ALTO / 2)

        # Capas con z cada vez más negativo = más cerca de la cámara de camera.ui.
        self.panel_unico = pu.activo()     # estilo único (M3.3): marco «tarjeta» y chip del lugar «chip»
        if self.panel_unico:
            self.fondo = FondoTinta(self, "minimapa", self.ANCHO, self.ALTO)
        else:
            self.fondo = _fondo(self, self.ANCHO, self.ALTO, _fondo_hud(), 10)
        self.capa_calles = Entity(parent=self, z=-0.001)
        self.capa_casas = Entity(parent=self, z=-0.0015)      # casas y escaleras (una malla cada una)
        self.capa_ruta = Entity(parent=self, z=-0.002)
        self.capa_lugares = Entity(parent=self, z=-0.003)
        self.capa_plazas = Entity(parent=self.capa_lugares)   # plazas y marcas de puerta: se gira entera
        self.capa_jugadores = Entity(parent=self, z=-0.004)
        self.flecha = Entity(
            parent=self, z=-0.006, scale=self.LARGO_FLECHA, double_sided=True,
            color=color.white, enabled=False,
            model=Mesh(vertices=[(0, 1, 0), (-0.42, 0, 0), (0, 0.28, 0), (0.42, 0, 0)],
                       triangles=[(0, 1, 2), (0, 2, 3)]))
        # La punta de la flecha (en el espacio local del modelo): los tests miden con ella.
        self.punta_flecha = Entity(parent=self.flecha, position=(0, 1, 0))

        self.segmentos_ruta = []      # cuadros reutilizados para dibujar la ruta
        self.puntos = {}              # nombre -> (aro, punto) de cada jugador
        self.lugares = {}             # lugar -> círculo de la plaza
        self.contornos_lugar = {}     # lugar -> círculo de tinta detrás de la plaza
        self.calles = []              # [(cuadro, a, b)] para recolocarlas al girar
        self.marcas_edificios = {}    # lugar -> cuadrito en la puerta (solo mundo con edificios)
        self._firma_ruta = None
        self._destino_etiqueta = None
        self.malla_casas = Entity(parent=self.capa_casas, enabled=False, color=self.COLOR_CASAS)
        self.malla_escaleras = Entity(parent=self.capa_casas, z=-0.0003, enabled=False,
                                      color=self.COLOR_ESCALERAS)
        self.reconstrucciones_casas = 0   # cuántas veces se rehicieron las mallas (lo usan los tests)
        self._yaw_casas = None            # yaw con el que se construyeron las mallas
        self._yaw_mapa = None             # yaw con el que se colocaron calles y plazas
        self._construir_mapa()
        self._reconstruir_casas()
        self.marcador_destino = Entity(parent=self.capa_lugares, model="circle", z=0.0005,
                                       color=rgb(COLOR_DESTINO), enabled=False)
        # Etiqueta corta del destino, bajo el minimapa (chip oscuro con el nombre en amarillo).
        self.px_etiqueta, self.hueco_etiqueta = 16, 0.012           # ver fijar_estilo_etiqueta()
        self.etiqueta_destino = Text("", parent=self, origin=(0.5, 0.5), scale=escala_fuente(self.px_etiqueta),
                                     position=(self.ANCHO / 2 - 0.008, -self.ALTO / 2 - self.hueco_etiqueta, -0.007),
                                     color=rgb(COLOR_DESTINO), enabled=False)
        if self.panel_unico:
            self.fondo_etiqueta = FondoTinta(self, "lugar", 0.1, 0.03, z=-0.0065, enabled=False)
        else:
            self.fondo_etiqueta = _fondo(self, 0.1, 0.03, _fondo_hud(), 6, z=-0.0065, enabled=False)
        self._iniciar_capas()
        self._gestor = None
        if modelo_ajustes.AJUSTES:
            self._gestor = gestor_ajustes if gestor_ajustes is not None else modelo_ajustes.obtener()
            self._gestor.suscribir(self._al_cambiar_ajustes)        # aplica ya lo guardado y sigue los cambios en vivo

    def on_destroy(self):
        if getattr(self, "_gestor", None) is not None:
            self._gestor.desuscribir(self._al_cambiar_ajustes)

    def _construir_mapa(self):
        g = self.geometria
        for a, b in self._mapa.segmentos():
            cuadro = Entity(parent=self.capa_calles, model="quad", color=rgb(self.COLOR_CALLES))
            self.calles.append((cuadro, a, b))
        for lugar in self._mapa.lugares():
            # contorno de tinta: separa el color del lugar del aro amarillo del destino
            self.contornos_lugar[lugar] = Entity(parent=self.capa_plazas, model="circle", z=0.0002,
                                                 scale=g.diametro_plaza() * 1.22, color=rgb(_tono(estilo.TINTA)))
            self.lugares[lugar] = Entity(parent=self.capa_plazas, model="circle",
                                         scale=g.diametro_plaza(),
                                         color=rgb(self.color_de_lugar(lugar)))
        for lugar in self._mapa.lugares():
            try:
                self._mapa.edificio_de(lugar)
            except (AttributeError, ValueError):
                continue
            self.marcas_edificios[lugar] = Entity(
                parent=self.capa_plazas, model="quad", z=-0.0005, scale=0.011,
                color=rgb((60, 64, 84)))
        self._colocar_mapa()

    # Color de identidad del lugar (estilo.COLORES_LUGAR). Los nombres del mapa son más largos
    # («Universidade de Ciudad Nova», «Parque do Povo»): se busca el nombre exacto y, si no,
    # la clave con la que empieza. Lugar desconocido: gris neutro.
    @classmethod
    def color_de_lugar(cls, lugar):
        if lugar in estilo.COLORES_LUGAR:
            return estilo.COLORES_LUGAR[lugar]
        for clave, tono in estilo.COLORES_LUGAR.items():
            if lugar.startswith(clave):
                return tono
        return cls.COLOR_LUGAR_SIN_IDENTIDAD

    # Posiciona calles, plazas y marcas según el yaw actual de la geometría.
    def _colocar_mapa(self):
        g = self.geometria
        for cuadro, a, b in self.calles:
            self._poner_segmento(cuadro, g.lugar(a), g.lugar(b), g.ancho_calle())    # color fijo: al crearla
        for lugar, circulo in self.lugares.items():
            circulo.position = g.lugar(lugar)
            self.contornos_lugar[lugar].position = (*g.lugar(lugar)[:2], 0.0002)
        for lugar, marca in self.marcas_edificios.items():
            marca.position = g.punto(*self._mapa.edificio_de(lugar).puerta())
        self._yaw_mapa = g.yaw
        self.capa_calles.rotation_z = self.capa_plazas.rotation_z = 0

    # Gira el minimapa con la cámara. La escala no cambia; las mallas de casas y escaleras se rehacen solo si el
    # yaw cambió más de YAW_MIN_CASAS, y calles y plazas solo se recolocan una a una cada YAW_MIN_MAPA_SUAVE grados.
    # Con el giro «norte arriba» el mapa no gira (yaw efectivo 0) y la flecha de mirada enseña hacia dónde mira la cámara.
    def fijar_yaw(self, yaw_grados):
        self._yaw_camara = yaw_grados
        self.flecha_mirada.rotation_z = yaw_grados
        yaw_grados = mm.yaw_efectivo(self.modo_rotacion, yaw_grados)
        if abs(yaw_grados - self.geometria.yaw) < 0.05:
            return
        self.geometria.girar(yaw_grados)
        self._girar_satelite()
        if hud_calculos.diferencia_yaw(yaw_grados, self._yaw_capas) > self._umbral_capas():
            self._capas_sucias = True                   # marcadores y zonas se proyectan con el yaw
        self._girar_capa_extra()
        if (self.GIRO_SUAVE_MAPA and self._yaw_mapa is not None
                and hud_calculos.diferencia_yaw(yaw_grados, self._yaw_mapa) <= self.YAW_MIN_MAPA_SUAVE):
            self._girar_capas_mapa()
        else:
            self._colocar_mapa()
        self._firma_ruta = None            # la ruta y la flecha se redibujan con el nuevo yaw
        if (self._yaw_casas is not None
                and hud_calculos.diferencia_yaw(yaw_grados, self._yaw_casas) > self._umbral_casas()):
            self._reconstruir_casas()
        self._girar_capa_casas()

    # Rendimiento (GIRO_SUAVE_CASAS): rehacer las mallas costaba varios ms y, al girar la cámara, pasaba casi
    # cada frame. Entre reconstrucciones se gira la capa entera lo que falta (exacto: el giro del minimapa es
    # alrededor de su centro) y solo se rehace cada YAW_MIN_CASAS_SUAVE grados. False = lo de siempre.
    GIRO_SUAVE_CASAS = True
    YAW_MIN_CASAS_SUAVE = 6.0

    def _umbral_casas(self):
        return self.YAW_MIN_CASAS_SUAVE if self.GIRO_SUAVE_CASAS else self.YAW_MIN_CASAS

    # Rendimiento (GIRO_SUAVE_MAPA): recolocar calles, plazas y marcas costaba ~0,3 ms por frame al girar la cámara.
    # Como con las casas, entre recolocaciones se giran las capas enteras (exacto: el giro es alrededor del centro
    # del minimapa) y solo se recoloca cada YAW_MIN_MAPA_SUAVE grados. False = lo de siempre.
    GIRO_SUAVE_MAPA = True
    YAW_MIN_MAPA_SUAVE = 6.0

    # Rendimiento (GIRO_SUAVE_CAPAS): marcadores y zonas se rehacían (mallas nuevas) cada grado de giro, es decir casi
    # cada frame al girar la cámara o al correr. Entre reconstrucciones se gira la capa entera (como las casas) y solo
    # se rehace cada YAW_MIN_CAPAS_SUAVE grados. False o ALCALDE_SIN_GIRO_SUAVE_CAPAS=1 = lo de siempre (1 grado).
    GIRO_SUAVE_CAPAS = True
    YAW_MIN_CAPAS_SUAVE = 6.0

    @classmethod
    def _giro_suave_capas(cls):
        return cls.GIRO_SUAVE_CAPAS and os.environ.get("ALCALDE_SIN_GIRO_SUAVE_CAPAS", "").strip() != "1"

    def _umbral_capas(self):
        return self.YAW_MIN_CAPAS_SUAVE if self._giro_suave_capas() else 1.0

    def _girar_capa_extra(self):
        if self.capa_extra is None or self._yaw_capas is None or not self._giro_suave_capas():
            return
        delta = (self.geometria.yaw - self._yaw_capas + 180) % 360 - 180
        self.capa_extra.rotation_z = -delta

    def _girar_capas_mapa(self):
        delta = (self.geometria.yaw - self._yaw_mapa + 180) % 360 - 180
        self.capa_calles.rotation_z = self.capa_plazas.rotation_z = -delta

    def _girar_capa_casas(self):
        if not self.GIRO_SUAVE_CASAS or self._yaw_casas is None:
            return
        delta = (self.geometria.yaw - self._yaw_casas + 180) % 360 - 180
        self.capa_casas.rotation_z = -delta     # rotation_z gira en sentido horario; el yaw, antihorario

    # Rehace las dos mallas (casas y escaleras) con el yaw actual. Mundo sin obstaculos() o
    # escaleras() (mapa 2D): no hay nada que dibujar y las mallas quedan apagadas.
    def _reconstruir_casas(self):
        g = self.geometria
        obstaculos = getattr(self._mapa, "obstaculos", None)
        escaleras = getattr(self._mapa, "escaleras", None)
        cuadros = g.cuadros_casas(obstaculos()) if callable(obstaculos) else []
        rectangulos = [hud_calculos.segmento_a_rectangulo(p0, p1, max(ancho, self.ANCHO_MIN_ESCALERA))
                       for p0, p1, ancho in (g.segmentos_escaleras(escaleras())
                                             if callable(escaleras) else [])]
        self._yaw_casas = g.yaw
        self.reconstrucciones_casas += 1
        for entidad, cuadrilateros in ((self.malla_casas, cuadros),
                                       (self.malla_escaleras, rectangulos)):
            entidad.enabled = bool(cuadrilateros)
            entidad.model = self._malla_de_cuadrilateros(cuadrilateros) if cuadrilateros else None

    # -- Satélite (mundo chico) --

    # Con la foto aérea de la ciudad (frontend/mapa_satelite.py) el minimapa pasa a ser el de FOTO (frontend/minimapa_foto.py):
    # una ventana de ~90 m centrada en el jugador, ampliada y recortada al recuadro. Las capas vectoriales (calles, casas, ruta,
    # plazas, jugadores) se apagan y Minimapa.actualizar / fijar_yaw se lo delegan. Cualquier fallo deja el minimapa de siempre.
    def poner_satelite(self, satelite):
        if satelite is None or self._satelite is not None:
            return
        foto = None
        try:
            from frontend.minimapa_foto import MinimapaFoto
            foto = MinimapaFoto(self, self._mapa, satelite, yaw=mm.yaw_efectivo(self.modo_rotacion, self._yaw_camara))
            self.fondo_satelite, self._satelite = foto, satelite
            foto.fijar_yaw(self.geometria.yaw, self._yaw_camara)
            for capa in (self.capa_ruta, self.capa_lugares, self.flecha, self.marcador_destino, self.flecha_mirada):
                capa.enabled = False
            self._aplicar_detalle()
        except Exception as error:                     # noqa: BLE001
            from frontend import mapa_satelite
            mapa_satelite._avisar_una_vez("minimapa", error)
            if foto is not None and self._satelite is None:
                destruir_arbol(foto)                   # se construyó a medias y no llegó a instalarse
            if self._satelite is not None:
                self._quitar_satelite()                # se instaló y algo falló después: vuelve el vectorial entero

    def _quitar_satelite(self):
        """Vuelve al minimapa vectorial (la foto falló): reactiva sus capas y borra la de foto."""
        if self.fondo_satelite is not None:
            destruir_arbol(self.fondo_satelite)
        self.fondo_satelite, self._satelite = None, None
        for capa in (self.capa_ruta, self.capa_lugares, self.capa_casas):
            capa.enabled = True
        self.marcador_destino.enabled = False
        self.flecha_mirada.enabled = False
        self._firma_ruta = None
        self._aplicar_detalle()
        self._colocar_mapa()                 # las capas vectoriales no siguieron el giro mientras estuvo la foto: se recolocan
        self._reconstruir_casas()
        self._capas_sucias = True

    def _girar_satelite(self):
        if self.fondo_satelite is not None:
            self.fondo_satelite.fijar_yaw(self.geometria.yaw, self._yaw_camara)

    # Una sola Mesh de polígonos regulares [(u, v, radio, rgb)], cada uno de su color (colores por vértice). La usan también
    # el minimapa de foto (minimapa_foto.py) y el mapa a pantalla completa (mapa_grande_vista.py).
    @staticmethod
    def _malla_de_poligonos(poligonos, lados=14):
        vertices, triangulos, colores = [], [], []
        for u, v, radio, tono in poligonos:
            base = len(vertices)
            vertices.append((u, v, 0))
            vertices += [(u + radio * math.cos(2 * math.pi * k / lados), v + radio * math.sin(2 * math.pi * k / lados), 0)
                         for k in range(lados)]
            triangulos += [(base, base + 1 + k, base + 1 + (k + 1) % lados) for k in range(lados)]
            colores += [rgb(tono)] * (lados + 1)
        return Mesh(vertices=vertices, triangles=triangulos, colors=colores)

    # -- Capas de marcadores y zonas (frontend/minimapa_calculos.py) y controles (giro, detalle) --

    ICONO = 0.0085                   # radio en pantalla (camera.ui) de un marcador
    BORDE_ZONA = 0.0025              # grosor en pantalla del borde de una zona
    INTERVALO_SONDEO = 1 / 15        # s entre preguntas a las fuentes registradas (NPC que se mueven...)
    MAX_ROTULOS = 6                  # rótulos de altura («+3 m») dibujados a la vez
    PX_ROTULO = 12

    # M3.4 (ALCALDE_HUD_TAMANOS): el rótulo sube lo justo para medir >= 18 px a 1080p con la escala del minimapa.
    def _px_rotulo(self):
        if not ht.activo():
            return self.PX_ROTULO
        return ht.px_asegurado(self.PX_ROTULO, abs(self.scale_x) or 1.0)

    # Estado de las capas y la flecha de mirada (norte arriba). Lo llama __init__ al final.
    def _iniciar_capas(self):
        self.capa_extra = None                  # marcadores y zonas: se rehace solo si cambia el registro
        self._version_capas = None
        self._capas_sucias = True
        self._yaw_capas = self.geometria.yaw
        self._t_sondeo = 0.0
        self.rotulos_altura = []                # pool de Text con «+3 m» junto a los marcadores de altura (detalle 3)
        self.reconstrucciones_capas = 0         # cuántas veces se rehicieron marcadores y zonas (lo usan las pruebas)
        forma = Mesh(vertices=[(0, 1.4, 0), (-0.45, 0.8, 0), (0.45, 0.8, 0)], triangles=[(0, 1, 2)])
        self.flecha_mirada = Entity(parent=self, z=-0.0068, scale=self.LARGO_FLECHA * 0.45, enabled=False)
        Entity(parent=self.flecha_mirada, model=forma, double_sided=True, color=rgb(_tono(estilo.TINTA)), scale=1.35, z=0.0001)
        Entity(parent=self.flecha_mirada, model=forma, double_sided=True, color=color.white)

    def _casas_activas(self):
        return mm.detalle(self.densidad)["casas"] and self.registro.capa_visible("edificios") and self._satelite is None

    # Ajustes en vivo: giro («camara» / «norte») y detalle (1..3).
    def _al_cambiar_ajustes(self, ajustes, cambiadas):
        if "minimapa_densidad" in cambiadas:
            self.densidad = ajustes.minimapa_densidad
            self._aplicar_detalle()
            self._capas_sucias = True
        if "minimapa_rotacion" in cambiadas:
            self.modo_rotacion = ajustes.minimapa_rotacion
            self.flecha_mirada.enabled = self.modo_rotacion == "norte" and self._satelite is None
            self.fijar_yaw(self._yaw_camara)

    # Capas base según el detalle y la visibilidad del registro (calles, edificios, jugadores).
    def _aplicar_detalle(self):
        self.capa_calles.enabled = self.registro.capa_visible("calles") and self._satelite is None
        self.capa_jugadores.enabled = self.registro.capa_visible("jugador") and self._satelite is None
        activas = self._casas_activas()
        self.capa_casas.enabled = activas

    # Un paso: pregunta a las fuentes (unas 15 veces por segundo), rehace marcadores y zonas solo si cambiaron, y
    # coloca la flecha de mirada y los rótulos de altura en la posición del jugador activo.
    def _actualizar_capas(self, posiciones, activo):
        ahora = time.perf_counter()
        if ahora - self._t_sondeo >= self.INTERVALO_SONDEO:
            self._t_sondeo = ahora
            self.registro.sondear()
        if self._capas_sucias or self.registro.version != self._version_capas:
            self._aplicar_detalle()
            self._rehacer_capas()
        pos = next(((x, z) for nombre, _, x, z in posiciones if nombre == activo), None)
        self._poner_flecha_mirada(pos)
        self._poner_rotulos_altura(pos)

    def _rehacer_capas(self):
        reg, g = self.registro, self.geometria
        if self.capa_extra is not None:
            destruir_arbol(self.capa_extra)
        self.capa_extra = extra = Entity(parent=self, z=-0.0035)
        self._version_capas = reg.version
        self._capas_sucias = False
        self._yaw_capas = g.yaw
        self.reconstrucciones_capas += 1
        # coordenadas de pantalla con el yaw; los vértices se acotan al recuadro
        def proyectar(x, z):
            return g.acotar(*g.punto(x, z))
        radio, grosor = self.ICONO, self.BORDE_ZONA
        for tono, grupo in mm.plan_zonas(reg.zonas(), proyectar, grosor).items():
            vertices, triangulos = grupo["relleno"]
            if triangulos:
                Entity(parent=extra, z=0.001, model=Mesh(vertices=vertices, triangles=triangulos),
                       color=color.rgba32(*tono, int(255 * mm.ALFA_RELLENO_ZONA)))
            Entity(parent=extra, z=0.0005, model=self._malla_de_cuadrilateros(grupo["borde"]),
                   color=color.rgba32(*tono, int(255 * mm.ALFA_BORDE_ZONA)))
        marcadores = [m for m in reg.marcadores() if g.contiene(*g.punto(m.x, m.z))]
        if marcadores:
            vertices, triangulos, colores = mm.plan_marcadores(marcadores, proyectar, radio)
            Entity(parent=extra, model=Mesh(vertices=vertices, triangles=triangulos,
                                            colors=[color.rgba(*c) for c in colores]))

    # Con «norte arriba» el mapa no gira: un triangulito junto al punto del jugador enseña hacia dónde mira la cámara.
    def _poner_flecha_mirada(self, pos):
        visible = pos is not None and self.modo_rotacion == "norte" and self.registro.capa_visible("jugador")
        if visible != self.flecha_mirada.enabled:
            self.flecha_mirada.enabled = visible
        if visible:
            g = self.geometria
            self.flecha_mirada.position = (*g.acotar(*g.punto(*pos), margen=0.014), -0.0068)

    # Parkour: «+3 m» / «-2 m» / «Nivel» junto a los marcadores de altura cercanos (detalle «Detallado»). Texto, no solo color.
    def _poner_rotulos_altura(self, pos):
        reg, g = self.registro, self.geometria
        rotulos = []
        if pos is not None and mm.detalle(self.densidad)["rotulos"] and reg.capa_visible("alturas"):
            rotulos = mm.rotulos_de_altura(reg.marcadores(["alturas"]), pos[0], pos[1], reg.altura_jugador,
                                           self.MAX_ROTULOS, None)
        usados = 0
        for marcador, texto, nivel in rotulos:
            u, v = g.punto(marcador.x, marcador.z)
            if not g.contiene(u, v):
                continue
            if usados >= len(self.rotulos_altura):
                self.rotulos_altura.append(Text("", parent=self, origin=(-0.5, 0), scale=escala_fuente(self._px_rotulo()),
                                                z=-0.0072))
            rotulo = self.rotulos_altura[usados]
            usados += 1
            rotulo.position = (u + self.ICONO * 1.6, v, -0.0072)
            if rotulo.text != texto:
                rotulo.text = _seguro(texto)
            if getattr(rotulo, "nivel", None) != nivel:
                rotulo.nivel = nivel
                rotulo.color = rgb(mm.COLORES_NIVEL[nivel])
            if not rotulo.enabled:
                rotulo.enabled = True
        for rotulo in self.rotulos_altura[usados:]:
            if rotulo.enabled:
                rotulo.enabled = False

    # Una sola Mesh con todos los cuadriláteros [(c0, c1, c2, c3)] de (u, v): dos triángulos cada uno.
    @staticmethod
    def _malla_de_cuadrilateros(cuadrilateros):
        vertices, triangulos = [], []
        for i, esquinas in enumerate(cuadrilateros):
            base = 4 * i
            vertices += [(u, v, 0) for u, v in esquinas]
            triangulos += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        return Mesh(vertices=vertices, triangles=triangulos)

    # Coloca un cuadro como línea gruesa de p0 a p1 (rotation_z en sentido horario). Sin `tono` conserva su color
    # (las calles: se recolocan en cada giro de la cámara y su color no cambia).
    def _poner_segmento(self, cuadro, p0, p1, grosor, tono=None):
        cu, cv, largo, rotacion = hud_calculos.segmento_a_cuadro(p0, p1)
        cuadro.position = (cu, cv)
        cuadro.scale = (largo, grosor)
        cuadro.rotation_z = rotacion
        if tono is not None:
            cuadro.color = tono

    # posiciones: [(nombre, rgb_rol, x, z)] de todos los jugadores; activo: nombre del
    # jugador del turno; destino: lugar o None; ruta: lugares que faltan (GuiaRuta).
    def actualizar(self, posiciones, activo, destino, ruta):
        g = self.geometria
        if self._satelite is not None:
            self._poner_etiqueta_destino(destino)
            try:
                self.fondo_satelite.actualizar(posiciones, activo, destino, ruta)
                return
            except Exception as error:                 # noqa: BLE001  la foto falla en marcha: vuelve el minimapa vectorial
                from frontend import mapa_satelite
                mapa_satelite._avisar_una_vez("minimapa_frame", error)
                self._quitar_satelite()
        presentes = {nombre for nombre, _, _, _ in posiciones}
        for nombre, (aro, punto) in self.puntos.items():
            if nombre not in presentes:          # jugador de una partida anterior: se oculta
                aro.enabled = punto.enabled = False
        for nombre, rgb_rol, x, z in posiciones:
            if nombre not in self.puntos:
                aro = Entity(parent=self.capa_jugadores, model="circle", color=color.white)
                punto = Entity(parent=self.capa_jugadores, model="circle", z=-0.0005)
                self.puntos[nombre] = (aro, punto)
            aro, punto = self.puntos[nombre]
            es_activo = nombre == activo
            u, v = g.acotar(*g.punto(x, z), margen=0.014)    # fuera del mapa: pegado al borde
            aro.position = punto.position = (u, v)
            aro.enabled = es_activo
            punto.enabled = True                 # reaparece si el nombre vuelve a estar
            aro.scale = 0.026
            punto.scale = 0.018 if es_activo else 0.012
            punto.color = rgb(rgb_rol) if es_activo else color.rgba32(*rgb_rol, 130)
            punto.z = -0.0005 if es_activo else 0.001     # los demás, detrás del activo

        self._poner_etiqueta_destino(destino)
        if destino is None:
            self.marcador_destino.enabled = False
        else:
            self.marcador_destino.enabled = True
            exacto = self.punto_destino                 # puerta de la Fiscalía: el mismo punto que la ruta del suelo
            self.marcador_destino.position = g.acotar(*(g.punto(*exacto) if exacto else g.lugar(destino)), margen=0.014)
            self.marcador_destino.scale = g.diametro_plaza() * 1.6

        self._actualizar_capas(posiciones, activo)
        for nombre, rgb_rol, x, z in posiciones:
            if nombre == activo:
                self._dibujar_ruta(x, z, ruta)
                return
        self._dibujar_ruta(0, 0, [])

    # Chip «Destino: <lugar>» bajo el minimapa, alineado a su borde derecho. Sin destino se oculta.
    def _poner_etiqueta_destino(self, destino):
        if destino == self._destino_etiqueta:
            return
        self._destino_etiqueta = destino
        self.etiqueta_destino.enabled = self.fondo_etiqueta.enabled = destino is not None
        if destino is None:
            return
        # Con la traducción corta: el chip no debe pasar del ancho del minimapa.
        self.etiqueta_destino.text = _seguro(nombre_visible(destino, corto=True))
        ancho = _medidor(self.etiqueta_destino)(self.etiqueta_destino.text)
        px, hueco = self.px_etiqueta, self.hueco_etiqueta
        relleno, alto = 0.012, a_unidades(px) * 1.5
        if self.panel_unico:
            relleno = pu.relleno("lugar")
            self.fondo_etiqueta.ajustar(ancho + 2 * relleno, alto)
        else:
            self.fondo_etiqueta.model = modelo_redondeado(ancho + 2 * relleno, alto, 6)
            self.fondo_etiqueta.scale = (ancho + 2 * relleno, alto)
        derecha = self.ANCHO / 2
        self.fondo_etiqueta.position = (derecha - (ancho + 2 * relleno) / 2, -self.ALTO / 2 - hueco - alto / 2 + 0.002, -0.0065)
        self.etiqueta_destino.position = (derecha - relleno, -self.ALTO / 2 - hueco + 0.002 - (alto - a_unidades(px)) / 2, -0.007)

    # Letra (px locales) y hueco bajo el mapa (local) del chip del lugar; redibuja el que esté puesto. Lo usa el mapa
    # de esquinas (hud_esquinas_calculos): el minimapa se achica al 80 % y el chip no debe quedar ilegible.
    def fijar_estilo_etiqueta(self, px, hueco):
        self.px_etiqueta, self.hueco_etiqueta = px, hueco
        self.etiqueta_destino.scale = escala_fuente(px)
        actual, self._destino_etiqueta = self._destino_etiqueta, None
        if actual is not None:
            self._poner_etiqueta_destino(actual)

    def _dibujar_ruta(self, x, z, ruta):
        # Misión con punto exacto (puerta de la Fiscalía): la misma línea que el suelo, no la de centros de plaza.
        exacta = [tuple(p) for p in (self.ruta_puntos or ())[1:]]
        firma = (tuple(ruta), tuple(exacta), round(x, 3), round(z, 3))
        if firma == self._firma_ruta:
            return
        self._firma_ruta = firma
        g = self.geometria
        if exacta:
            puntos = [g.punto(x, z)] + [g.punto(*p) for p in exacta]
            pares = list(zip(puntos, puntos[1:]))
        else:
            pares = g.segmentos_ruta(x, z, ruta)
        segmentos = [r for r in (g.recortar_segmento(p0, p1) for p0, p1 in pares)
                     if r is not None]        # lo que queda fuera del recuadro no se dibuja
        while len(self.segmentos_ruta) < len(segmentos):
            self.segmentos_ruta.append(Entity(parent=self.capa_ruta, model="quad"))
        for cuadro, (p0, p1) in zip(self.segmentos_ruta, segmentos):
            self._poner_segmento(cuadro, p0, p1, max(g.ancho_calle() * 0.55, 0.006), rgb(COLOR_RUTA))
            cuadro.enabled = True
        for cuadro in self.segmentos_ruta[len(segmentos):]:
            cuadro.enabled = False

        if exacta:
            (u0, v0), (u1, v1) = pares[0]
            flecha = (u0, v0, navegacion.angulo_hacia(u0, v0, u1, v1))
        else:
            flecha = g.flecha(x, z, ruta)
        self.flecha.enabled = flecha is not None
        if flecha is not None:
            self.flecha.position = g.acotar(flecha[0], flecha[1], margen=self.LARGO_FLECHA)
            self.flecha.rotation_z = flecha[2]       # horario desde arriba = rotation_z de Ursina

    def entidades_dibujadas(self):
        # Entidades visibles con su posición local (u, v): para comprobar el recorte.
        todas = [self.capa_calles, self.capa_ruta, self.capa_lugares, self.capa_plazas, self.capa_jugadores]
        resultado = []
        for capa in todas:
            resultado += [e for e in capa.children if e.enabled and e is not self.capa_plazas]
        if self.flecha.enabled:
            resultado.append(self.flecha)
        return resultado


# -- Aviso de interacción --------------------------------------------------------


class AvisoInteraccion(Entity):

    TEXTO = "Presiona E para acceder"
    ANCHO_MIN, ANCHO_MAX, ALTO = 0.44, 0.66, 0.07    # el máximo deja libre el banner del teléfono
    RELLENO = 0.05
    LADO_TECLA = 0.05                 # la tecla E dibujada (icono 'interactuar')
    SEPARACION_TECLA = 0.012
    DURACION_APARICION = 0.12         # segundos: alfa 0 -> 1 y sube 6 px (ease_out_quad)
    SUBIDA_PX = 6

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.y_base = -0.5 + MARGEN + 0.04
        self.position = (0, self.y_base)
        if pu.activo():          # estilo único (M3.3): chip con borde de tinta; mismo relleno que el resto de chips
            self.RELLENO = 2 * pu.relleno("aviso_e")
            self.fondo = FondoTinta(self, "aviso_e", self.ANCHO_MIN, self.ALTO, z=0.001)
        else:
            self.fondo = _fondo(self, self.ANCHO_MIN, self.ALTO, _fondo_hud(), 12, z=0.001)
        self.tecla = _icono(self, "interactuar", self.LADO_TECLA, (0, 0, -0.001))
        self.texto = Text(self.TEXTO, parent=self, origin=(-0.5, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO))
        self._ancho = self.ANCHO_MIN
        self._ancho_texto = 0.0
        self.aparicion = 0.0          # segundos desde que apareció (0 .. DURACION_APARICION)
        self.DURACION_APARICION = hctx.tiempo("AVISO_ENTRADA")      # M3.6: 0,12 -> 0,18 s (regla de la UI)
        self.nivel = 0.0              # avance eased 0..1 de la aparición (1 = ya a la vista)
        self.enabled = False
        self._colocar()

    # Tecla + texto como un grupo centrado dentro del fondo.
    def _colocar(self):
        grupo = self.LADO_TECLA + self.SEPARACION_TECLA + self._ancho_texto
        izquierda = -grupo / 2
        self.tecla.x = izquierda + self.LADO_TECLA / 2
        self.texto.x = izquierda + self.LADO_TECLA + self.SEPARACION_TECLA

    # `texto`: otro mensaje (p. ej. "Presiona E para entrar a la Prefeitura"); None = el de siempre.
    # El fondo se ajusta al ancho de tecla + texto (entre ANCHO_MIN y ANCHO_MAX; si aun así no
    # cabe, el texto se achica).
    def actualizar(self, estado_mision, estado_telefono, texto=None, tipo_mision="verificar"):
        cadena = _seguro(texto if texto is not None else self.TEXTO)
        if cadena != self.texto.text:
            self.texto.text = cadena
            self.texto.scale = escala_fuente(22)
            ancho_texto = _medidor(self.texto)(cadena)
            # El máximo nunca pasa del ancho real de la ventana (en 16:9 sigue siendo ANCHO_MAX).
            ancho_max = min(self.ANCHO_MAX, diseno_adaptable.aspecto() - 4 * MARGEN)
            maximo = ancho_max - self.RELLENO - self.LADO_TECLA - self.SEPARACION_TECLA
            if ancho_texto > maximo:
                self.texto.scale = escala_fuente(22) * maximo / ancho_texto
                ancho_texto = maximo
            self._ancho_texto = ancho_texto
            self._ancho = max(self.ANCHO_MIN,
                              ancho_texto + self.LADO_TECLA + self.SEPARACION_TECLA + self.RELLENO)
            _ajustar_fondo(self.fondo, self._ancho, self.ALTO, 12)
            self._colocar()
        visible = hud_calculos.aviso_visible(estado_mision, estado_telefono, tipo_mision)
        if visible and not self.enabled:      # acaba de aparecer: la animación empieza de cero
            self.aparicion = 0.0
            self._aplicar_aparicion()
        self.enabled = visible

    # Avanza `dt` segundos la aparición (llamado desde HudMundo.actualizar; determinista).
    def avanzar(self, dt):
        if not self.enabled:
            return
        self.aparicion = min(self.DURACION_APARICION, self.aparicion + dt)
        self._aplicar_aparicion()

    def _aplicar_aparicion(self):
        self.nivel = _ease_out_quad(self.aparicion / self.DURACION_APARICION)
        self.y = self.y_base - a_unidades(self.SUBIDA_PX) * (1 - self.nivel)
        alfa = int(round(255 * self.nivel))
        _alfa_fondo(self.fondo, self.nivel)
        self.tecla.color = color.rgba32(255, 255, 255, alfa)
        self.texto.color = color.rgba32(*_tono(estilo.COLOR_TEXTO), alfa)


# -- Aviso genérico adaptable --------------------------------------------------------


# Chip de texto en la parte baja de la pantalla para avisos sueltos («E: montar bici», «Espacio:
# saltar»...). A diferencia de AvisoInteraccion no lleva la tecla E dibujada ni depende del estado
# de la misión: lo controla quien llama con mostrar()/ocultar(). El ancho se adapta a la ventana:
# el texto se encoge hasta el 75 %, luego se parte en hasta dos líneas y solo si ni así cabe
# se recorta con elipsis. Si el aviso de «E» está visible, se apila encima de él.
class AvisoGenerico(Entity):

    ANCHO_MIN, ALTO = 0.30, 0.07
    ANCHO_MAX = 0.66                  # como AvisoInteraccion: deja libre el banner del teléfono; en ventanas estrechas manda el ancho de la ventana
    RELLENO = 0.05
    PX = 22
    ESCALA_MIN = 0.75
    MAX_LINEAS = 2
    LINEA = 1.25                      # interlineado
    DURACION_APARICION = 0.12
    SUBIDA_PX = 6

    def __init__(self, referencia=None, **opciones):
        super().__init__(**opciones)
        self._referencia = referencia          # AvisoInteraccion sobre el que se apila (opcional)
        self.DURACION_APARICION = hctx.tiempo("AVISO_ENTRADA")      # M3.6: 0,12 -> 0,18 s (regla de la UI)
        self.y_base = -0.5 + MARGEN + 0.04
        self.position = (0, self.y_base)
        if pu.activo():          # estilo único (M3.3)
            self.RELLENO = 2 * pu.relleno("aviso")
            self.fondo = FondoTinta(self, "aviso", self.ANCHO_MIN, self.ALTO, z=0.001)
        else:
            self.fondo = _fondo(self, self.ANCHO_MIN, self.ALTO, _fondo_hud(), 12, z=0.001)
        self.texto = Text("", parent=self, origin=(0, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(self.PX), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = self.LINEA
        self.cadena = ""              # texto pedido (sin partir)
        self.lineas = []              # líneas que se dibujan
        self.plan = None              # último plan de ajuste (escala, lineas, recortado)
        self.aparicion = 0.0
        self.nivel = 0.0
        self.deseado = False          # True entre mostrar() y ocultar()
        self.enabled = False
        diseno_adaptable.suscribir(lambda aspecto, factor: self._componer())

    # Ancho máximo del chip para la ventana actual.
    def ancho_maximo(self):
        return min(self.ANCHO_MAX, diseno_adaptable.aspecto() - 4 * MARGEN)

    # Muestra `texto`. Si ya se muestra el mismo no reinicia la animación.
    def mostrar(self, texto):
        cadena = _seguro(str(texto))
        if not cadena.strip():
            self.ocultar()
            return
        cambio = cadena != self.cadena
        self.cadena = cadena
        if cambio:
            self._componer()
        if not self.deseado:
            self.deseado = True
            self.aparicion = 0.0
            self.enabled = True
            self._aplicar_aparicion()

    def ocultar(self):
        self.deseado = False
        self.enabled = False
        self.aparicion = 0.0

    # Reparte el texto en líneas dentro del ancho de la ventana y ajusta el fondo.
    def _componer(self):
        if not self.cadena:
            return
        self.texto.scale = escala_fuente(self.PX)
        medir = _medidor(self.texto)
        maximo = self.ancho_maximo() - self.RELLENO
        plan = diseno_adaptable_calculos.plan_texto_en_ancho(
            self.cadena, medir, maximo, self.ESCALA_MIN, self.MAX_LINEAS)
        self.plan = plan
        self.lineas = plan["lineas"]
        self.texto.text = "\n".join(self.lineas)
        self.texto.scale = escala_fuente(self.PX) * plan["escala"]
        ancho_texto = max((medir(linea) for linea in self.lineas), default=0.0) * plan["escala"]
        self._ancho = max(self.ANCHO_MIN, ancho_texto + self.RELLENO)
        self._alto = max(self.ALTO, len(self.lineas) * a_unidades(self.PX) * self.LINEA * plan["escala"]
                         + 0.03)
        _ajustar_fondo(self.fondo, self._ancho, self._alto, 12)

    _ancho = ANCHO_MIN
    _alto = ALTO

    # Avanza `dt` segundos la aparición (llamado desde HudMundo.actualizar; determinista).
    def avanzar(self, dt):
        if not self.enabled:
            return
        self.aparicion = min(self.DURACION_APARICION, self.aparicion + dt)
        self._aplicar_aparicion()

    def _aplicar_aparicion(self):
        self.nivel = _ease_out_quad(self.aparicion / self.DURACION_APARICION)
        # Sube sobre el aviso de «E» si éste está a la vista (su alto + un hueco).
        apilado = 0.0
        ref = self._referencia
        if ref is not None and ref.enabled:
            apilado = ref.ALTO / 2 + self._alto / 2 + 0.012
        self.y = self.y_base + (self._alto - self.ALTO) / 2 + apilado - a_unidades(self.SUBIDA_PX) * (1 - self.nivel)
        alfa = int(round(255 * self.nivel))
        _alfa_fondo(self.fondo, self.nivel)
        self.texto.color = color.rgba32(*_tono(estilo.COLOR_TEXTO), alfa)


# -- Panel de turno ----------------------------------------------------------------


class PanelTurno(Entity):

    RELLENO = 0.014

    # esquinas: mapa de esquinas (hud_esquinas_calculos; None = la bandera ALCALDE_HUD_ESQUINAS). Con él el panel es
    # UNA línea «Misión: <título> · <quién juega>»; texto_turno sigue teniendo el texto del turno, pero oculto.
    def __init__(self, esquinas=None, **opciones):
        super().__init__(**opciones)
        self.esquinas = hec.activo() if esquinas is None else bool(esquinas)
        px_mision = hec.PX_MISION if self.esquinas else 17
        if pu.activo():          # estilo único (M3.3): chip con borde de tinta y el relleno de los chips
            self.RELLENO = pu.relleno("mision")
            self.fondo = FondoTinta(self, "mision", 0.1, 0.1, z=0.001)
        else:
            self.fondo = _fondo(self, 0.1, 0.1, _fondo_hud(), 8, z=0.001)
        self.texto_turno = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(22),
                                color=rgb(estilo.COLOR_TEXTO), enabled=not self.esquinas)
        # «Misión:» va aparte, en el color del destino; texto_mision lleva el título.
        self.texto_prefijo = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(px_mision),
                                  color=rgb(COLOR_DESTINO))
        self.texto_mision = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(px_mision),
                                 color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.jugadores = None            # jugadores de la sesión (lo pone HudMundo): con 2+ la línea dice de quién es el turno
        self._crudo = None               # (turno, mision) tal cual llegaron a fijar()
        if self.esquinas:
            self.position = hec.origen_mision(window.aspect_ratio)
        else:
            self.position = (-window.aspect_ratio / 2 + MARGEN, 0.5 - MARGEN)

    # Fija los textos y ajusta el fondo al más ancho.
    def fijar(self, turno, mision):
        self._crudo = (turno, mision)
        if self.esquinas:
            self.texto_turno.text = _seguro(turno)
            self._componer_linea()
            return
        prefijo, titulo = _separar_mision(mision)
        self.texto_turno.text = _seguro(turno)
        self.texto_prefijo.text = prefijo
        self.texto_prefijo.enabled = bool(prefijo)
        self.texto_mision.text = _seguro(titulo)
        # El título arranca tras «Misión: » (el espacio se mide con el mismo TextNode).
        avance = _medidor(self.texto_prefijo)(prefijo + " ") if prefijo else 0.0
        ancho = max(_medidor(self.texto_turno)(self.texto_turno.text),
                    avance + _medidor(self.texto_mision)(self.texto_mision.text))
        alto_turno, alto_mision = a_unidades(22) * 1.2, a_unidades(17) * 1.2
        r = self.RELLENO
        _ajustar_fondo(self.fondo, ancho + 2 * r, alto_turno + alto_mision + 2 * r, 8)
        self.fondo.position = ((ancho + 2 * r) / 2, -(alto_turno + alto_mision + 2 * r) / 2)
        self.texto_turno.position = (r, -r, -0.001)
        self.texto_prefijo.position = (r, -r - alto_turno, -0.001)
        self.texto_mision.position = (r + avance, -r - alto_turno, -0.001)
        self._ancho_total = ancho + 2 * r
        self.ajustar_ancho()

    _ancho_total = 0.0

    # Ancho máximo del panel de turno: lo que queda entre el borde izquierdo y el minimapa. Si el
    # panel no cabe (ventana estrecha) se escala entero, anclado a su esquina superior izquierda.
    # En 16:9 el máximo es de sobra y la escala se queda en 1 (comportamiento de siempre).
    def ajustar_ancho(self, aspecto=None, factor=None):
        if aspecto is None:
            aspecto = diseno_adaptable.aspecto()
        if self.esquinas:
            self._componer_linea(aspecto)
            return
        maximo = aspecto - 2 * MARGEN - Minimapa.ANCHO - 0.03
        escala = diseno_adaptable_calculos.factor_para_ancho(self._ancho_total, maximo, minimo=0.4)
        self.scale = ESCALA_HUD * escala

    # Mapa de esquinas: cuántos jugadores hay (con 2+ la línea nombra al del turno). Recompone si cambió.
    def fijar_jugadores(self, n):
        if n == self.jugadores:
            return
        self.jugadores = n
        if self.esquinas and self._crudo is not None:
            self._componer_linea()

    # Mapa de esquinas: «Misión: <título> · <quién>» en UNA línea que cabe en el hueco de la esquina (de la izquierda a
    # la franja central). Se encoge hasta hec.ESCALA_MIN_MISION y, si ni así, se recorta el título con elipsis.
    def _componer_linea(self, aspecto=None):
        if self._crudo is None:
            return
        if aspecto is None:
            aspecto = diseno_adaptable.aspecto()
        turno, mision = self._crudo
        prefijo, titulo = _separar_mision(mision)
        cabeza = prefijo + " " if prefijo else ""
        sufijo = _seguro(hec.sufijo_mision(turno, (self.jugadores or 1) > 1))
        medir = _medidor(self.texto_mision)            # prefijo y título van a la misma letra
        r = self.RELLENO
        maximo = hec.layout_esquinas(aspecto, 1.0)["mision"].ancho / ESCALA_HUD - 2 * r
        escala, titulo = hec.plan_linea_mision(cabeza, _seguro(titulo), sufijo, medir, maximo)
        self.texto_prefijo.text = prefijo
        self.texto_prefijo.enabled = bool(prefijo)
        self.texto_mision.text = titulo + sufijo
        avance = medir(cabeza) if prefijo else 0.0
        ancho = avance + medir(self.texto_mision.text)
        alto = a_unidades(hec.PX_MISION) * 1.2
        _ajustar_fondo(self.fondo, ancho + 2 * r, alto + 2 * r, 8)
        self.fondo.position = ((ancho + 2 * r) / 2, -(alto + 2 * r) / 2)
        self.texto_prefijo.position = (r, -r, -0.001)
        self.texto_mision.position = (r + avance, -r, -0.001)
        self._ancho_total = ancho + 2 * r
        self.scale = ESCALA_HUD * escala


# -- Fin de la partida ---------------------------------------------------------------


# Panel centrado "Partida terminada": indicadores finales de la ciudad y un botón para
# volver al menú. Lo muestra EscenaMundo cuando FlujoPartida.partida_terminada().
class PanelFinPartida(Entity):

    TITULO = "Partida terminada"
    ANCHO, ALTO = 0.62, 0.70
    ANCHO_BARRA = 0.44
    LADO_ICONO = 0.07
    SEPARACION_FILA = 0.12
    DURACION_BARRAS = 0.8             # segundos que tardan las barras en crecer de 0 al valor
    INDICADORES = ("convivencia", "confianza", "desinformacion")

    def __init__(self, al_menu, **opciones):
        super().__init__(**opciones)
        self.panel = panel_piel(self, self.ANCHO, self.ALTO, tono=estilo.COLOR_FONDO)
        Text(self.TITULO, parent=self, origin=(0, 0), position=(0, self.ALTO / 2 - 0.07, -0.001),
             scale=escala_fuente(32), color=rgb(estilo.COLOR_TEXTO))
        Text("Indicadores finales de Ciudad Nova", parent=self, origin=(0, 0),
             position=(0, self.ALTO / 2 - 0.13, -0.001), scale=escala_fuente(17),
             color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.barras = {}
        self.textos = {}                  # nombre -> Text «Etiqueta: valor» de cada barra
        self.valores = {}
        izquierda = -self.ANCHO / 2 + 0.05
        for i, nombre in enumerate(self.INDICADORES):
            arriba = 0.16 - i * self.SEPARACION_FILA
            _icono(self, nombre, self.LADO_ICONO,
                   (izquierda + self.LADO_ICONO / 2, arriba - 0.05, -0.001))
            barra = BarraIndicador(estilo.ETIQUETAS_INDICADORES[nombre], self.ANCHO_BARRA, 0,
                                   parent=self, position=(izquierda + self.LADO_ICONO + 0.02, arriba, -0.001))
            self.barras[nombre] = barra
            self.textos[nombre] = barra.texto_etiqueta
        self.boton_menu = boton_piel(
            "Volver al menú", "primario", al_clic=al_menu, ancho=0.36, alto=a_unidades(56),
            parent=self, position=(0, -self.ALTO / 2 + 0.09, -0.001))
        self.DURACION_BARRAS = hctx.tiempo("BARRAS_FIN")              # M3.6: 0,8 -> 0,3 s (nada de UI > 300 ms)
        self.tiempo = self.DURACION_BARRAS          # animación terminada
        self.enabled = False

    # Muestra el panel con los valores de `indicadores` (dict nombre -> 0..100). Las
    # etiquetas muestran ya el valor final; las barras crecen en DURACION_BARRAS (avanzar).
    # Llamarlo otra vez con el panel ya visible no reinicia la animación.
    def mostrar(self, indicadores):
        ya_visible = self.enabled
        for nombre, barra in self.barras.items():
            self.valores[nombre] = indicadores[nombre]
            barra.actualizar(indicadores[nombre])
        if not ya_visible:
            self.tiempo = 0.0
            self._dibujar_barras()
        self.enabled = True

    def ocultar(self):
        self.enabled = False

    # Un paso de `dt` segundos de la animación de las barras (lo llama HudMundo.actualizar).
    def avanzar(self, dt):
        if not self.enabled or self.tiempo >= self.DURACION_BARRAS:
            return
        self.tiempo = min(self.DURACION_BARRAS, self.tiempo + dt)
        self._dibujar_barras()

    # Proporción del valor final alcanzada (0..1, ease_out_quad).
    def avance(self):
        return _ease_out_quad(self.tiempo / self.DURACION_BARRAS)

    def _dibujar_barras(self):
        for nombre, barra in self.barras.items():
            ancho = barra.ancho_barra * max(0.0, min(1.0, self.valores[nombre] / 100)) * self.avance()
            if ancho <= 0:
                barra.relleno.enabled = False
                continue
            barra.relleno.enabled = True
            barra.relleno.scale_x = ancho
            barra.relleno.x = ancho / 2
            barra.relleno.model = modelo_redondeado(ancho, barra.alto_barra, 4)
            barra.relleno.color = rgb(self._color_de(nombre))

    # Color por tercio del valor final; en «desinformacion» un valor alto es MALO (se invierte).
    def _color_de(self, nombre):
        valor = self.valores[nombre]
        return estilo.rgb_por_valor(100 - valor if nombre == "desinformacion" else valor)


# -- HUD completo -------------------------------------------------------------------


class HudMundo(Entity):

    # mapa: MapaCiudad. El HUD arranca desactivado (EscenaMundo lo activa al entrar).
    # al_menu: callback del botón "Volver al menú" del panel de fin de partida.
    # rotacion_libre: mundo 3D (el minimapa gira con la cámara; ver actualizar(yaw_grados)).
    def __init__(self, mapa, obtener_flujo, al_menu=None, rotacion_libre=False, **opciones):
        opciones.setdefault("parent", camera.ui)
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self._mapa = mapa
        self._obtener_flujo = obtener_flujo
        self.panel_turno = PanelTurno(parent=self)
        self.minimapa = Minimapa(mapa, rotacion_libre=rotacion_libre, parent=self)
        self.telefono_ui = TelefonoUI(self._telefono_activo, self._mision_actual, parent=self)
        self.aviso = AvisoInteraccion(parent=self)
        self.panel_fin = PanelFinPartida(
            lambda: al_menu() if al_menu is not None else None, parent=self)
        self.guia = hud_calculos.GuiaRuta(mapa)
        # hook: callable() -> lugar al que lleva la ruta del minimapa durante un trabajo en el mundo (entregas en moto,
        # frontend/entregas_mundo.py), o None = el destino de la misión.
        self.destino_trabajo = None
        # Aviso genérico (API pública: mostrar_aviso / ocultar_aviso), apilado sobre el de «E».
        self.aviso_generico = AvisoGenerico(parent=self, referencia=self.aviso)
        for componente in (
                self.panel_turno, self.minimapa, self.telefono_ui,
                self.aviso, self.aviso_generico, self.panel_fin):
            componente.scale = ESCALA_HUD
        # Mapa de esquinas (M3.1, ALCALDE_HUD_ESQUINAS): minimapa al 80 % pegado a la esquina de arriba a la derecha y
        # teléfono en la de abajo a la derecha, con el margen de seguridad común (hud_esquinas_calculos). Se colocan
        # ANTES de anclar: diseno_adaptable mueve luego cada bloque con su borde conservando ese margen.
        self.esquinas = self.panel_turno.esquinas
        if self.esquinas:
            aspecto = window.aspect_ratio
            self.minimapa.scale = hec.escala_minimapa()
            self.minimapa.position = hec.centro_minimapa(aspecto)
            self.minimapa.fijar_estilo_etiqueta(hec.PX_ETIQUETA_LUGAR, hec.hueco_etiqueta_local())
            self.telefono_ui.position = hec.desplazamiento_telefono(aspecto, aspecto, MARGEN)
        # Diseño adaptable: lo anclado a un borde sigue al borde cuando cambia la ventana (no-op
        # si el gestor no está instalado o UI_ADAPTABLE es False).
        diseno_adaptable.anclar(self.panel_turno, "izquierda")
        diseno_adaptable.anclar(self.minimapa, "derecha")
        diseno_adaptable.anclar(self.telefono_ui, "derecha")
        diseno_adaptable.suscribir(self.panel_turno.ajustar_ancho)
        # Ajuste «HUD: Completo / Mínimo» (M3.5, ALCALDE_HUD_MINIMO_AJUSTE): en «mínimo» solo misión y reloj; los bloques
        # registrados (registrar_bloque) aparecen bajo demanda con hud_modo_calculos.ControlHudModo.
        self.modo_hud = hm.ControlHudModo() if hm.activo() else None
        self._bloques = {}               # nombre -> [entidad, firma() | None, alfa aplicado | None]
        self._arboles_modo = {}          # nombre -> FundidoArbol (M3.6)
        self._gestor_modo = None
        if self.modo_hud is not None:
            self.registrar_bloque("minimapa", self.minimapa, lambda: self.minimapa._destino_etiqueta)
            if self.telefono_ui.grupo_icono is not None:
                self.registrar_bloque("telefono", self.telefono_ui.grupo_icono)
            from frontend import hud_ajustes
            hud_ajustes.registrar()
            if modelo_ajustes.AJUSTES:
                self._gestor_modo = modelo_ajustes.obtener()
                self._gestor_modo.suscribir(self._al_cambiar_ajustes)
        # Mapa a pantalla casi completa (tecla N): solo con la foto aérea (satélite) del mundo 3D.
        self.puede_abrir_mapa = None       # callable() -> bool que pone la escena (pausa, cinemática, otros paneles)
        self.mapa_grande = None
        self._ampliado = None              # VIS-007: minimapa ampliado con N cuando no hay mapa grande (sin foto aérea)
        # Con SATÉLITE (frontend/mapa_satelite.py) el mundo 3D tiene mapa a pantalla completa: la foto aérea de la ciudad con
        # las plazas, el destino de la misión y la ruta (la foto la pone EscenaMundo con poner_satelite()).
        from frontend import mapa_satelite
        if rotacion_libre and mapa_satelite.activo():
            from frontend.mapa_grande_vista import MapaGrandeVista
            self.mapa_grande = MapaGrandeVista(
                mapa, self._puede_abrir_mapa_grande, parent=self,
                ocultar=(self.minimapa, self.panel_turno, self.telefono_ui, self.aviso, self.aviso_generico))

    # -- Ajuste «HUD: Completo / Mínimo» (M3.5) --

    # Un bloque del HUD que en «mínimo» sale bajo demanda. `firma()`: su valor (si cambia, se asoma 4 s); None = sin valor.
    # Lo llaman también etapas_final_vista (franja) y economia_mundo (dinero). No-op con la bandera apagada.
    def registrar_bloque(self, nombre, entidad, firma=None):
        if self.modo_hud is not None and nombre in self.modo_hud.bloques:
            self._bloques[nombre] = [entidad, firma, None]

    def _al_cambiar_ajustes(self, ajustes, cambiadas):
        if self.modo_hud is not None and "hud_modo" in cambiadas:
            self.modo_hud.fijar_modo(ajustes.hud_modo)

    def on_destroy(self):
        if getattr(self, "_gestor_modo", None) is not None:
            self._gestor_modo.desuscribir(self._al_cambiar_ajustes)

    def input(self, key):
        if self.modo_hud is not None:
            self.modo_hud.tecla(key)
        if self.mapa_grande is None:
            from frontend import mapa_grande_calculos
            if key == mapa_grande_calculos.TECLA_MAPA:
                if self._ampliado is not None:
                    self._cerrar_minimapa_ampliado()
                elif self._puede_abrir_mapa_grande():
                    self._abrir_minimapa_ampliado()

    # -- VIS-007: minimapa ampliado (respaldo del mapa a pantalla completa cuando la foto aérea no salió) --

    ALTO_AMPLIADO = 0.74                   # alto en camera.ui del minimapa ampliado (la ventana mide 1)

    def _abrir_minimapa_ampliado(self):
        mini = self.minimapa
        ocultos = [e for e in (self.panel_turno, self.telefono_ui, self.aviso, self.aviso_generico) if e.enabled]
        self._ampliado = (mini.position, mini.scale, mini.z, ocultos)
        if getattr(self, "_velo_ampliado", None) is None:
            self._velo_ampliado = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 170))
        self._velo_ampliado.z = mini.z + 0.5
        self._velo_ampliado.enabled = True
        for e in ocultos:
            e.enabled = False
        factor = self.ALTO_AMPLIADO / Minimapa.ALTO
        mini.scale = mini.scale * factor
        mini.position = (0, 0, mini.z)

    def _cerrar_minimapa_ampliado(self):
        if self._ampliado is None:
            return False
        posicion, escala, z, ocultos = self._ampliado
        self._ampliado = None
        self.minimapa.scale = escala
        self.minimapa.position = posicion
        self.minimapa.z = z
        self._velo_ampliado.enabled = False
        for e in ocultos:
            e.enabled = True
        return True

    @staticmethod
    def _tutorial_senalando():
        try:
            return _CONSULTA_SENALANDO is not None and bool(_CONSULTA_SENALANDO())
        except Exception:
            return False

    def _actualizar_modo(self, dt, telefono):
        modo = self.modo_hud
        if modo is None or (not modo.minimo and all(r[2] in (None, 1.0) for r in self._bloques.values())):
            return
        tutorial = self._tutorial_senalando()
        abierto = telefono is not None and telefono.estado() == hud_calculos.ABIERTO
        modo.mantener("telefono", tutorial or abierto or self.telefono_ui.banner_visible())
        modo.mantener("minimapa", tutorial or self.mapa_grande_abierto())
        modo.mantener("franja", tutorial)
        modo.mantener("dinero", tutorial)
        for nombre, registro in self._bloques.items():
            firma = registro[1]
            if firma is not None:
                try:
                    valor = firma()
                except Exception:
                    valor = None
                modo.observar(nombre, valor)
        alfas = modo.avanzar(dt)
        for nombre, registro in self._bloques.items():
            entidad = registro[0]
            visible = alfas.get(nombre, 1.0) > 0.0
            # Oculto = hide() de Panda, reconciliado CADA frame con el `visible` de Ursina (la economía lo usa para
            # esconder minimapa y teléfono con sus paneles): se ve solo si los dos lo quieren. No se toca `enabled`.
            # (Un setAlphaScale en el padre no sirve: Ursina pone setColorScaleOff en cada modelo; y ocultar con un bit
            # de máscara no lo respeta la cámara de la UI.)
            try:
                oculto = not (visible and entidad.visible)
                if entidad.node().isOverallHidden() != oculto:
                    entidad.hide() if oculto else entidad.show()
            except Exception:            # entidad ya destruida (otra partida): se olvida
                continue
            if hctx.animaciones_activas():   # M3.6: el bloque entra y sale con fundido real (solo mientras cambia)
                arbol = self._arboles_modo.get(nombre)
                if arbol is None:
                    from frontend.fundido_ui import FundidoArbol
                    arbol = self._arboles_modo[nombre] = FundidoArbol(entidad)
                alfa = alfas.get(nombre, 1.0)
                if alfa <= 0.0:
                    arbol.invalidar()        # oculto: al volver se recogen sus piezas de nuevo (pudo rehacerse)
                else:
                    arbol.aplicar(alfa)
            estado = 1.0 if visible else 0.0
            if estado != registro[2] and nombre == "telefono":
                self.telefono_ui.icono.collision = visible        # invisible = no se puede pulsar
            registro[2] = estado
        self._bloques = {n: r for n, r in self._bloques.items() if not r[0].isEmpty()}

    # Foto aérea de la ciudad (mapa_satelite.Satelite) para el minimapa y el mapa grande. None = los vectoriales de siempre.
    def poner_satelite(self, satelite):
        if satelite is None:
            return
        self.minimapa.poner_satelite(satelite)
        if self.mapa_grande is not None:
            self.mapa_grande.poner_satelite(satelite)

    # La foto no salió: el mundo se queda como antes (sin mapa a pantalla completa).
    def sin_satelite(self):
        if self.mapa_grande is not None:
            self.mapa_grande.enabled = False          # ya no recibe la N aunque Ursina tarde un frame en retirarlo
            destruir_arbol(self.mapa_grande)
            self.mapa_grande = None

    # ¿Se puede abrir el mapa grande ahora? Partida en curso, ni minijuego ni teléfono abierto, y lo que diga la escena.
    def _puede_abrir_mapa_grande(self):
        flujo = self._obtener_flujo()
        if flujo is None or flujo.partida_terminada() or flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return False
        if flujo.jugador_activo().telefono.bloquea_movimiento():
            return False
        return self.puede_abrir_mapa is None or bool(self.puede_abrir_mapa())

    def mapa_grande_abierto(self):
        return (self.mapa_grande is not None and self.mapa_grande.abierto) or self._ampliado is not None

    # Cierra el mapa grande (o el minimapa ampliado) si estaba abierto; True si lo cerró (Escape lo usa para no abrir
    # además la pausa).
    def cerrar_mapa_grande(self):
        if self._cerrar_minimapa_ampliado():
            return True
        return self.mapa_grande is not None and self.mapa_grande.cerrar()

    # Aviso adaptable en la parte baja de la pantalla, sobre «Presiona E...» si éste está visible.
    # `texto` se encoge o se parte en dos líneas para caber en la ventana (elipsis solo si ni así).
    # Lo usa EscenaMundo para avisos como «E: montar bici» o «Espacio: saltar».
    def mostrar_aviso(self, texto):
        self.aviso_generico.mostrar(texto)

    # Oculta el aviso genérico (con fundido corto).
    def ocultar_aviso(self):
        self.aviso_generico.ocultar()

    def _telefono_activo(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.jugador_activo().telefono

    def _mision_actual(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.mision_actual()

    # Lugar del hook `destino_trabajo` (None sin hook, sin trabajo en curso o si falla).
    def _destino_de_trabajo(self):
        if self.destino_trabajo is None:
            return None
        try:
            return self.destino_trabajo()
        except Exception:
            return None

    # Un paso del HUD (dt segundos): ruta, minimapa, teléfono y aviso con el estado del
    # modelo. Devuelve True si la ruta cambió (EscenaMundo redibuja la del mundo).
    # yaw_grados (mundo 3D): yaw de la cámara; el minimapa gira con él (arriba = adelante).
    def actualizar(self, dt, sesion, yaw_grados=None):
        self.aviso_generico.avanzar(dt)
        flujo = self._obtener_flujo()
        if flujo is None or sesion is None:
            return False
        if yaw_grados is not None:
            self.minimapa.fijar_yaw(yaw_grados)
        activo = flujo.jugador_activo()
        if self.esquinas:
            self.panel_turno.fijar_jugadores(len(sesion.jugadores()))
        mision = flujo.mision_actual()
        destino = mision.destino if mision is not None else None
        # «Seguir misión» desmarcada: ni ruta ni destino en el minimapa (el aviso de la E sí usa el destino real).
        seguido = hud_calculos.destino_visible(destino, hud_calculos.sigue_mision(activo.telefono))
        trabajo = self._destino_de_trabajo()
        if trabajo is not None:
            seguido = trabajo
        cambio = self.guia.actualizar(activo.x, activo.z, seguido)

        self.minimapa.actualizar(
            [(j.nombre, ROLES[j.rol].color, j.x, j.z) for j in sesion.jugadores()],
            activo.nombre, seguido, self.guia.ruta)
        if self.mapa_grande is not None and self.mapa_grande.abierto:
            self.mapa_grande.actualizar(
                [(j.nombre, ROLES[j.rol].color, j.x, j.z) for j in sesion.jugadores()],
                activo.nombre, 0.0 if yaw_grados is None else yaw_grados, seguido, self.guia.ruta)
        self.telefono_ui.avanzar(dt)
        self.panel_fin.avanzar(dt)
        self.aviso.actualizar(flujo.estado_mision(), activo.telefono.estado(),
                              self._texto_aviso(destino), getattr(mision, "tipo", "verificar"))
        self.aviso.avanzar(dt)
        self._actualizar_modo(dt, activo.telefono)
        return cambio

    # "Presiona E para entrar a <edificio>" si el mapa tiene edificios (mundo 3D); None = el de siempre.
    def _texto_aviso(self, destino):
        edificio_de = getattr(self._mapa, "edificio_de", None)
        if destino is None or edificio_de is None:
            return None
        try:
            return f"Presiona E para entrar a {nombre_visible(edificio_de(destino).titulo)}"
        except ValueError:
            return None

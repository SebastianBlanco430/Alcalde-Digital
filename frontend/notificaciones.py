# Notificaciones de evento por el teléfono (docs/PLAN_CLARIDAD_JUEGO.md §2.6). Todo aviso de algo que PASÓ (veredicto y
# pago, efectos retardados, avisos del reloj, cambio de etapa, partida guardada, resultado de compra/trabajo) llega como
# mensaje al teléfono del jugador activo:
#
#   - teléfono CERRADO: el banner de siempre (frontend/hud.TelefonoUI), que ahora repasa los mensajes de uno en uno;
#   - teléfono ABIERTO: una TARJETA a la izquierda del panel del teléfono, alineada con su borde superior (PilaTarjetas):
#     máx. 3 hacia abajo, 4 s cada una; no tapa el panel;
#   - `jugador` distinto del activo (hot-seat: el veredicto de quien ya pasó el turno): el mensaje queda SIN LEER en su
#     teléfono y le sale el banner al empezar su turno;
#   - sin teléfono (en línea, sin flujo): el aviso de hoy.
#
# Los avisos de INTERACCIÓN («E: comprar», «Presiona E…») no pasan por aquí: se quedan abajo como siempre.
# La cola y los tiempos son puros (frontend/notificaciones_calculos.py). ALCALDE_NOTIF_TELEFONO=0 lo apaga: quien
# llama conserva su aviso de antes (cada sitio pregunta `activo()`).

import sys

from frontend import notificaciones_calculos as nc
from frontend.notificaciones_calculos import REMITENTE, ColaTarjetas, activo  # noqa: F401  (API pública)

ANCHO_TARJETA = 0.46             # camera.ui, antes de ESCALA_HUD
RELLENO = 0.014
SEPARACION = 0.010               # hueco entre tarjetas, y entre la pila y el panel del teléfono
DESLIZ_ENTRADA = 0.06            # la tarjeta entra desde la derecha este trecho (no pasa por encima del panel)
LADO_ICONO = 0.032
PX_REMITENTE, PX_TEXTO = 14, 13
MAX_LINEAS = 4
Z_PILA = -0.06                   # por delante del resto del HUD


def _avisar(texto):
    print(f"[notificaciones] {texto}", file=sys.stderr)


def _telefono_activo(escena):
    """Teléfono del jugador activo, o None (sin flujo, en línea o un flujo sin teléfonos)."""
    if getattr(escena, "online", None) is not None:
        return None
    flujo = getattr(escena, "flujo", None)
    if flujo is None:
        return None
    try:
        return flujo.jugador_activo().telefono
    except Exception:
        return None


def _abierto(telefono):
    try:
        return bool(telefono.bloquea_movimiento())
    except Exception:
        return False


def _aviso_de_hoy(escena, texto):
    """El aviso de antes: el temporal de la economía (se quita solo) o, si no hay, el genérico del HUD."""
    temporal = getattr(getattr(escena, "economia", None), "aviso_temporal", None)
    try:
        if callable(temporal):
            temporal(texto)
        else:
            escena.hud.mostrar_aviso(texto)
    except Exception as error:
        _avisar(f"aviso no mostrado ({type(error).__name__}: {error})")


def pila_de(escena):
    """La pila de tarjetas de la escena (se crea la primera vez). Las pruebas ponen una falsa en
    `escena._pila_notificaciones` (con `agregar(texto, remitente, tono)`)."""
    pila = getattr(escena, "_pila_notificaciones", None)
    if pila is None:
        pila = escena._pila_notificaciones = _crear_pila(escena)
    return pila


def notificar_evento(escena_mundo, texto, remitente=REMITENTE, tono="info", jugador=None):
    """Avisa de algo que pasó. `jugador`: a quién va (None = el activo). Devuelve por dónde salió: "tarjeta" (teléfono
    abierto), "banner" (cerrado), "pendiente" (el jugador no es el activo: queda sin leer en su teléfono hasta su turno),
    "aviso" (sin teléfono: el de hoy) o None (texto vacío)."""
    texto = str(texto or "").strip()
    if not texto:
        return None
    telefono = _telefono_activo(escena_mundo)
    ajeno = getattr(jugador, "telefono", None) if telefono is not None else None
    if ajeno is not None and ajeno is not telefono:
        if _abierto(ajeno):                # lo dejó abierto al pasar el turno: cerrado, para que el mensaje quede sin leer
            ajeno.cerrar()
        ajeno.notificar(texto, remitente)
        return "pendiente"
    if telefono is None:
        _aviso_de_hoy(escena_mundo, texto)
        return "aviso"
    abierto = _abierto(telefono)
    telefono.notificar(texto, remitente)
    if not abierto:
        return "banner"                    # lo enseña TelefonoUI
    try:
        pila_de(escena_mundo).agregar(texto, remitente, tono)
    except Exception as error:             # el mensaje ya está en el teléfono: no se pierde
        _avisar(f"tarjeta no apilada ({type(error).__name__}: {error})")
    return "tarjeta"


class ColaAlTelefono:
    """Misma API que veredicto_calculos.ColaAvisos, pero cada aviso sale ya por el teléfono (no hay nada que pintar en
    el centro): la usan los vigías que antes encolaban avisos (reloj, causa-efecto, cambio de etapa)."""

    def __init__(self, escena, remitente=REMITENTE, tono="aviso"):
        self.escena, self.remitente, self.tono = escena, remitente, tono
        self.actual = None

    def agregar(self, texto):
        if texto:
            notificar_evento(self.escena, texto, self.remitente, self.tono)

    def pendientes(self):
        return 0

    def vaciar(self):
        pass

    def avanzar(self, dt):
        return None


def en_espera(escena):
    """¿Las tarjetas esperan? Pausa, cinemática, mapa grande, tutorial o paneles modales abiertos."""
    try:
        economia = getattr(escena, "economia", None)
        return bool(getattr(escena, "en_pausa", False) or getattr(escena, "_cinematica", False)
                    or escena._bloqueado_por_paneles() or escena.hud.mapa_grande_abierto()
                    or (economia is not None and economia.bloquea_controles()))
    except Exception:
        return False


# ---------------------------------------------------------------- vista Ursina

def _crear_pila(escena):
    from ursina import Entity, Text, camera, color, time

    from frontend import estilo, hud as hud_mod, tipografia
    from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb
    from frontend.texto import envolver_texto

    escala = getattr(hud_mod, "ESCALA_HUD", 1.0)
    alto_linea = a_unidades(PX_TEXTO) * 1.25

    class VistaTarjeta(Entity):
        """Una tarjeta: panel de tinta, disco del tono con su símbolo, remitente en negrita y el texto (hasta 4 líneas)."""

        def __init__(self, tarjeta, **opciones):
            super().__init__(**opciones)
            self.numero = tarjeta.numero
            simbolo, constante = nc.TONOS[tarjeta.tono]
            tono = getattr(estilo, constante)
            ancho_texto = ANCHO_TARJETA - 3 * RELLENO - LADO_ICONO
            cuerpo = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(PX_TEXTO), color=rgb(estilo.COLOR_TEXTO))
            cuerpo.line_height = 1.25
            lineas = envolver_texto(hud_mod._seguro(tarjeta.texto), hud_mod._medidor(cuerpo), ancho_texto) or [""]
            if len(lineas) > MAX_LINEAS:            # el mensaje completo está en el teléfono (abierto)
                lineas = lineas[:MAX_LINEAS]
                lineas[-1] = lineas[-1].rstrip()[:-1].rstrip() + "…"
            cuerpo.text = "\n".join(lineas)
            self.alto = 2 * RELLENO + a_unidades(PX_REMITENTE) * 1.4 + len(lineas) * alto_linea
            self.fondo = panel_tinta(self, ANCHO_TARJETA, self.alto, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                     borde_px=estilo.GROSOR_BORDE_DENSO_PX, z=0.002)
            izquierda, arriba = -ANCHO_TARJETA / 2 + RELLENO, self.alto / 2 - RELLENO
            x_icono = izquierda + LADO_ICONO / 2
            Entity(parent=self, model="circle", scale=LADO_ICONO + 0.006, position=(x_icono, arriba - LADO_ICONO / 2, -0.001),
                   color=rgb(estilo.TINTA))
            Entity(parent=self, model="circle", scale=LADO_ICONO, position=(x_icono, arriba - LADO_ICONO / 2, -0.002),
                   color=rgb(tono))
            Text(simbolo, parent=self, origin=(0, 0), position=(x_icono, arriba - LADO_ICONO / 2, -0.003),
                 scale=escala_fuente(16), color=rgb(estilo.TINTA), font=tipografia.FUENTE_TITULO)
            x_texto = izquierda + LADO_ICONO + RELLENO
            Text(hud_mod._seguro(tarjeta.remitente), parent=self, origin=(-0.5, 0.5), position=(x_texto, arriba, -0.001),
                 scale=escala_fuente(PX_REMITENTE), color=rgb(tono), font=tipografia.FUENTE_TITULO)
            cuerpo.position = (x_texto, arriba - a_unidades(PX_REMITENTE) * 1.4, -0.001)
            # Para el fundido de salida: el alfa propio de cada pieza (la sombra ya es translúcida).
            self._piezas = [(e, e.color[3]) for e in self._descendientes(self) if hasattr(e, "color")]
            self._alfa = 1.0

        @staticmethod
        def _descendientes(entidad):
            for hijo in entidad.children:
                yield hijo
                yield from VistaTarjeta._descendientes(hijo)

        def fijar_alfa(self, valor):
            if abs(valor - self._alfa) < 0.01:
                return
            self._alfa = valor
            for pieza, base in self._piezas:
                c = pieza.color
                pieza.color = color.rgba(c[0], c[1], c[2], base * valor)

    class PilaTarjetas(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.cola = nc.ColaTarjetas()
            self.vistas = {}                 # número de tarjeta -> VistaTarjeta

        def agregar(self, texto, remitente=REMITENTE, tono="info"):
            return self.cola.agregar(texto, remitente, tono)

        def _esquina(self):
            """(x del borde derecho, y del borde superior) de la pila: a la izquierda del panel del teléfono, alineada
            con su borde superior (no lo tapa)."""
            ui = escena.hud.telefono_ui
            centro = ui.panel.get_position(camera.ui)
            ancho, alto = type(ui).ANCHO_PANEL * ui.scale_x, type(ui).ALTO_PANEL * ui.scale_y
            return centro.x - ancho / 2 - SEPARACION, centro.y + alto / 2

        def update(self):
            self.avanzar(min(time.dt, 0.1))

        def avanzar(self, dt):
            if en_espera(escena):                 # pausa, cinemática, tutorial, panel modal: esperan sin envejecer
                self.cola.avanzar(dt, en_pausa=True)
                for vista in self.vistas.values():
                    vista.enabled = False
                return
            visibles = self.cola.avanzar(dt)
            vivos = {t.numero for t in visibles}
            for numero in [n for n in self.vistas if n not in vivos]:
                destruir_arbol(self.vistas.pop(numero))          # caducó
            if not visibles:
                return
            derecha, y = self._esquina()
            for tarjeta in visibles:
                vista = self.vistas.get(tarjeta.numero)
                if vista is None:
                    vista = self.vistas[tarjeta.numero] = VistaTarjeta(tarjeta, parent=self, scale=escala)
                vista.enabled = True
                ancho, alto = ANCHO_TARJETA * escala, vista.alto * escala
                fuera = (1.0 - nc.entrada(tarjeta.edad)) * DESLIZ_ENTRADA
                vista.position = (derecha - ancho / 2 + fuera, y - alto / 2)
                vista.fijar_alfa(nc.alfa(tarjeta.edad))
                y -= alto + SEPARACION

    return PilaTarjetas(parent=escena.hud, z=Z_PILA)

# Rueda de opciones del caso de Fiscalía v2 (Ursina, en camera.ui), al estilo de los diálogos de Detroit: cuatro huecos
# fijos alrededor de un centro (0 arriba, 1 derecha, 2 abajo, 3 izquierda) con el reloj en anillo en medio.
#   - Hueco libre: panel de tinta con la etiqueta; resaltado en amarillo.
#   - Hueco bloqueado: silueta oscura con candado y la pista («[Falta una prueba]»); se resalta pero no se elige (tiembla).
#   - Hueco usado (una opción que el jugador ya eligió): la opción gastada, oscura, con ✓ y su etiqueta tachada en gris
#     (la rueda no se reordena). Si no se sabe su etiqueta (desapareció sin elegirla), no se dibuja, como el que nunca tuvo
#     opción: antes era una silueta vacía que se leía como un rectángulo oscuro sin nada.
# Es solo vista: la entrada (ratón, teclas, mando) la decide hud_caso.py y llama a resaltar()/temblar()/hueco_bajo_raton().
# La geometría (centro respecto a la cara, cajas) está en rueda_calculos.py; tiempos y mallas en ui_calculos.py.
# Aquí también viven las mallas pequeñas que comparten las demás piezas (arco, candado, triángulo, palomita).

import math

from ursina import Entity, Mesh, Text, color, mouse

from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import escala_fuente, modelo_redondeado, panel_tinta, rgb
from frontend.fiscalia import rueda_calculos as rc
from frontend.fiscalia import ui_calculos as uc

ROJO_RELOJ = (235, 87, 87)
TONO_LIBRE = estilo.COLOR_PANEL
TONO_BLOQUEADO = (26, 28, 40)
TONO_USADO = (28, 30, 42)


# -- Mallas pequeñas compartidas ---------------------------------------------------------------------------------------

def malla(vertices):
    m = Mesh(vertices=list(vertices) or [(0, 0, 0)] * 3, mode="triangle", static=False)
    return m


def poner_vertices(entidad, vertices):
    """Cambia la malla de `entidad` (la apaga si no hay vértices)."""
    vertices = list(vertices)
    entidad.enabled = bool(vertices)
    if vertices:
        entidad.model.vertices = vertices
        entidad.model.generate()


def triangulo(padre, tamano, arriba=True, tono=(255, 255, 255), **opciones):
    """Triángulo ▲ (o ▼): la fuente del juego no trae esos glifos."""
    s = 1 if arriba else -1
    vs = [(-0.5, -0.5 * s, 0), (0.5, -0.5 * s, 0), (0, 0.5 * s, 0)]
    return Entity(parent=padre, model=malla(vs), scale=tamano, color=rgb(tono), double_sided=True, **opciones)


def palomita(padre, tamano, tono=(80, 190, 110), **opciones):
    """✓ dibujada con dos trazos (la fuente no la trae)."""
    raiz = Entity(parent=padre, scale=tamano, **opciones)
    Entity(parent=raiz, model="quad", position=(-0.22, -0.12), scale=(0.42, 0.16), rotation_z=45, color=rgb(tono))
    Entity(parent=raiz, model="quad", position=(0.14, 0.04), scale=(0.75, 0.16), rotation_z=-55, color=rgb(tono))
    return raiz


def candado(padre, tamano, tono=estilo.PAPEL, **opciones):
    """Candado: cuerpo redondeado y asa en arco. `tamano` = alto total (unidades de camera.ui)."""
    raiz = Entity(parent=padre, scale=tamano, **opciones)
    Entity(parent=raiz, model=modelo_redondeado(0.80, 0.58, 2), position=(0, -0.21), scale=(0.80, 0.58), color=rgb(tono))
    Entity(parent=raiz, model=malla(uc.vertices_arco(0.20, 0.31, 0, math.pi, 12)), position=(0, 0.10),
           color=rgb(tono), double_sided=True)
    for x in (-0.255, 0.255):
        Entity(parent=raiz, model="quad", position=(x, 0.06), scale=(0.11, 0.10), color=rgb(tono))
    Entity(parent=raiz, model="quad", position=(0, -0.21, -0.01), scale=(0.10, 0.22), color=rgb(estilo.TINTA))
    return raiz


def ancho_real(texto):
    """Ancho del Text en unidades de su padre (Text.width de Ursina no incluye la escala del propio Text)."""
    try:
        return float(texto.width) * float(texto.scale_x)
    except Exception:                    # noqa: BLE001
        return 0.3


def ajustar(texto, cadena, ancho, px, max_lineas=1):
    """Pone `cadena` en el Text encogiéndolo (sin bajar del piso legible) o partiéndolo para que quepa en `ancho`.
    Con varias líneas permitidas, primero se parte a tamaño completo y solo si no cabe se encoge."""
    base = escala_fuente(px)
    if max_lineas and max_lineas > 1:
        plan = diseno_adaptable.ajustar_texto(texto, ancho, escala_base=base, escala_min=1.0, max_lineas=None,
                                              cadena=cadena)
        if plan is not None and len(plan["lineas"]) <= max_lineas:
            return plan
    plan = diseno_adaptable.ajustar_texto(texto, ancho, escala_base=base, escala_min=uc.escala_min(px),
                                          max_lineas=max_lineas, cadena=cadena)
    if plan is None:
        texto.scale = base
        texto.text = cadena
    return plan


# -- Hueco de la rueda de diálogo ------------------------------------------------------------------------------------

class Hueco(Entity):
    """Un hueco fijo de la rueda. Estados: «libre», «bloqueada», «usado» (gastada: ✓ y etiqueta tachada) o «nada»."""

    def __init__(self, indice, ancho, alto, **opciones):
        super().__init__(**opciones)
        self.indice = indice
        self.ancho, self.alto = ancho, alto
        self.estado = "nada"
        self.opcion = None
        self.etiqueta_usada = ""
        self.resaltado = False
        # Zona del ratón (detrás de todo, transparente): el único collider del hueco.
        self.zona = Entity(parent=self, model="quad", scale=(ancho, alto), color=color.clear, collider="box", z=0.02)
        self.silueta = Entity(parent=self, model=modelo_redondeado(ancho, alto, estilo.RADIO_TARJETA_PX),
                              scale=(ancho, alto), color=color.rgba32(*estilo.PAPEL, 26), z=0.01)
        self.panel = panel_tinta(self, ancho, alto, tono=TONO_LIBRE, radio_px=estilo.RADIO_TARJETA_PX)
        self.numero = Text(str(indice + 1), parent=self.panel, origin=(0, 0), position=(-ancho / 2 + 0.02, 0, -0.01),
                           scale=escala_fuente(uc.TAM["numero"]), font=tipografia.FUENTE_TITULO,
                           color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.candado = candado(self.panel, 0.034, position=(-ancho / 2 + 0.03, 0.002, -0.01), enabled=False)
        self._contenido()
        self.marca = palomita(self.panel, 0.026, tono=estilo.COLOR_TEXTO_TENUE, position=(-ancho / 2 + 0.022, 0, -0.01),
                              enabled=False)
        self.tachado = Entity(parent=self.panel, model="quad", scale=(0.1, 0.0035), position=(0, 0, -0.012),
                              color=rgb(estilo.COLOR_TEXTO_TENUE), enabled=False)
        self._aplicar()

    def _contenido(self):
        self.texto = Text("", parent=self.panel, origin=(0, 0), position=(0.012, 0, -0.01),
                          scale=escala_fuente(uc.TAM["etiqueta"]), font=tipografia.FUENTE_TITULO,
                          color=rgb(estilo.COLOR_TEXTO))

    def fijar(self, opcion, estado, etiqueta_usada=""):
        self.opcion = opcion if estado in ("libre", "bloqueada") else None
        self.estado = estado
        self.etiqueta_usada = str(etiqueta_usada or "") if estado == "usado" else ""
        self._rellenar()
        self._aplicar()

    def _rellenar(self):
        o = self.opcion
        if o is None:
            self.texto.text = ""
            if self.etiqueta_usada:
                ajustar(self.texto, self.etiqueta_usada, self.ancho - 0.075, uc.TAM["etiqueta"])
                self.texto.x = 0.016
                ancho = min(self.ancho - 0.06, ancho_real(self.texto) + 0.012)
                self.tachado.scale_x = ancho
                self.tachado.x = self.texto.x
            return
        if self.estado == "bloqueada":
            ajustar(self.texto, o.pista or "[Falta una prueba]", self.ancho - 0.085, uc.TAM["pista"])
            self.texto.x = 0.022
        else:
            ajustar(self.texto, o.etiqueta, self.ancho - 0.065, uc.TAM["etiqueta"])
            self.texto.x = 0.012

    def resaltar(self, valor):
        self.resaltado = bool(valor)
        self._aplicar()

    def _aplicar(self):
        e = self.estado
        usado = e == "usado" and bool(self.etiqueta_usada)
        self.enabled = e in ("libre", "bloqueada") or usado
        self.panel.enabled = e in ("libre", "bloqueada") or usado
        self.silueta.enabled = False
        self.zona.collision = e in ("libre", "bloqueada")
        self.candado.enabled = e == "bloqueada"
        self.numero.enabled = e == "libre"
        self.marca.enabled = usado
        self.tachado.enabled = usado
        if usado:
            self.panel.fondo.color = rgb(TONO_USADO)
            self._colorear_texto(estilo.COLOR_TEXTO_TENUE)
        if e == "libre":
            tono = estilo.COLOR_ACENTO if self.resaltado else TONO_LIBRE
            self.panel.fondo.color = rgb(tono)
            self._colorear_texto(estilo.COLOR_ACENTO_TEXTO if self.resaltado else estilo.COLOR_TEXTO)
            self.numero.color = rgb(estilo.TINTA if self.resaltado else estilo.COLOR_TEXTO_TENUE)
        elif e == "bloqueada":
            self.panel.fondo.color = rgb(estilo.COLOR_SUPERFICIE_ALTA if self.resaltado else TONO_BLOQUEADO)
            self._colorear_texto(estilo.COLOR_TEXTO if self.resaltado else estilo.COLOR_TEXTO_TENUE)

    def _colorear_texto(self, tono):
        self.texto.color = rgb(tono)


# -- Rueda -------------------------------------------------------------------------------------------------------------

class Rueda(Entity):
    """Cuatro huecos (de la clase `fabrica`) alrededor del anillo del reloj. `posicion` del Entity = centro."""

    N_SEGMENTOS = 48

    def __init__(self, fabrica=Hueco, ancho=rc.ANCHO_HUECO, alto=rc.ALTO_HUECO, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto = ancho, alto
        self.huecos = [fabrica(i, ancho, alto, parent=self) for i in range(4)]
        self._finales = [(c[0], c[1]) for c in rc.cajas((0, 0), ancho, alto)]
        for h, (x, y) in zip(self.huecos, self._finales):
            h.position = (x, y, 0)
        r_out = rc.RADIO_RELOJ
        self.anillo_fondo = Entity(parent=self, model=malla(uc.vertices_arco(r_out - 0.011, r_out, 0, 2 * math.pi, 48)),
                                   color=color.rgba32(*estilo.TINTA, 200), double_sided=True, z=0.002)
        self.disco = Entity(parent=self, model=modelo_redondeado(0.074, 0.074, 22), scale=(0.074, 0.074),
                            color=color.rgba32(*estilo.TINTA, 170), z=0.003)
        self.anillo = Entity(parent=self, model=malla([]), color=rgb(estilo.PAPEL), double_sided=True, z=0.001)
        self.segundos = Text("", parent=self, origin=(0, 0), z=-0.01, scale=escala_fuente(uc.TAM["reloj"]),
                             font=tipografia.FUENTE_TITULO, color=rgb(estilo.PAPEL))
        self.punto = Entity(parent=self, model=modelo_redondeado(0.022, 0.022, 7), scale=(0.022, 0.022),
                            color=rgb(estilo.PAPEL), z=-0.005)
        self._k_reloj = -1
        self._reloj = (None, None)
        self._t_entrada = 0.0
        self._t = 0.0
        self._temblor = {}
        self.resaltado = None
        self.visible_rueda = False
        self.enabled = False

    # -- Contenido --

    def preparar(self, opciones, usados=()):
        """Pone las opciones (VistaOpcion, cada una en su `posicion`) y marca como «usado» los huecos de `usados`
        (posiciones, o {posición: etiqueta} para dibujar la opción gastada; sin etiqueta no se dibuja)."""
        por_pos = {}
        for o in opciones or ():
            p = int(getattr(o, "posicion", 0))
            if 0 <= p < 4 and p not in por_pos:
                por_pos[p] = o
        for i, h in enumerate(self.huecos):
            o = por_pos.get(i)
            if o is not None:
                h.fijar(o, "bloqueada" if getattr(o, "estado", "libre") == "bloqueada" else "libre")
            elif i in usados:
                h.fijar(None, "usado", usados.get(i, "") if isinstance(usados, dict) else "")
            else:
                h.fijar(None, "nada")
        if self.resaltado is not None and self.huecos[self.resaltado].estado not in ("libre", "bloqueada"):
            self.resaltar(None)
        return por_pos

    def ocupados(self):
        return {h.indice for h in self.huecos if h.estado in ("libre", "bloqueada")}

    def opcion(self, indice):
        if indice is None or not 0 <= indice < 4:
            return None
        return self.huecos[indice].opcion

    # -- Visibilidad --

    def mostrar(self, animar=True):
        if not self.visible_rueda:
            self._t_entrada = 0.0 if animar else uc.DUR_ENTRADA
            self.visible_rueda = True
        self.enabled = True
        self._colocar_huecos(1.0 if not animar else uc.entrada(self._t_entrada))

    def esconder(self):
        self.visible_rueda = False
        self.enabled = False
        self.resaltar(None)
        self._temblor.clear()

    # -- Resaltado y «no» --

    def resaltar(self, indice):
        if indice is not None and (not 0 <= indice < 4 or self.huecos[indice].estado not in ("libre", "bloqueada")):
            return
        self.resaltado = indice
        for h in self.huecos:
            h.resaltar(h.indice == indice)

    def temblar(self, indice):
        self._temblor[indice] = 0.0

    def hueco_bajo_raton(self):
        e = getattr(mouse, "hovered_entity", None)
        for h in self.huecos:
            if e is h.zona and h.estado in ("libre", "bloqueada") and self.visible_rueda:
                return h.indice
        return None

    # -- Reloj --

    def fijar_reloj(self, restante, total):
        self._reloj = (restante, total)
        con_reloj = restante is not None and bool(total)
        self.anillo_fondo.enabled = con_reloj
        self.disco.enabled = con_reloj
        self.segundos.enabled = con_reloj
        # Sin reloj el centro queda vacío: el punto claro que había se leía como una mancha suelta en la pared (S9).
        self.punto.enabled = False
        if not con_reloj:
            self.anillo.enabled = False
            self._k_reloj = -1
            return
        f = uc.fraccion_reloj(restante, total)
        k = uc.segmentos_visibles(f, self.N_SEGMENTOS)
        if k != self._k_reloj:
            self._k_reloj = k
            poner_vertices(self.anillo, uc.arco_reloj(f, rc.RADIO_RELOJ - 0.011, rc.RADIO_RELOJ, self.N_SEGMENTOS))
        urgente = uc.reloj_urgente(restante)
        tono = ROJO_RELOJ if urgente else estilo.PAPEL
        self.anillo.color = rgb(tono)
        self.segundos.color = rgb(tono)
        texto = uc.texto_reloj(restante)
        if self.segundos.text != texto:
            self.segundos.text = texto

    # -- Frame --

    def avanzar(self, dt, reducir=False):
        self._t += dt
        if not self.visible_rueda:
            return
        if self._t_entrada < uc.DUR_ENTRADA:
            self._t_entrada += dt
            self._colocar_huecos(uc.entrada(self._t_entrada, reducir=reducir))
        restante, _ = self._reloj
        s = uc.pulso(self._t, uc.reloj_urgente(restante), reducir)
        self.segundos.scale = escala_fuente(uc.TAM["reloj"]) * s
        for i in list(self._temblor):
            t = self._temblor[i] + dt
            self._temblor[i] = t
            h = self.huecos[i]
            x, y = self._finales[i]
            if t >= uc.DUR_TEMBLOR:
                del self._temblor[i]
                h.x = x
            else:
                h.x = x + uc.temblor(t, reducir)

    def _colocar_huecos(self, k):
        """Entrada: los huecos salen del centro hacia su sitio (k de 0 a 1)."""
        k = max(0.0, min(1.0, k))
        for h, (x, y) in zip(self.huecos, self._finales):
            h.position = (x * (0.55 + 0.45 * k), y * (0.55 + 0.45 * k), 0)
            h.scale = 0.85 + 0.15 * k

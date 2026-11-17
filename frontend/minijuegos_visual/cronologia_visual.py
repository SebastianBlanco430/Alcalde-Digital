# «Cronología» visual (Ursina): «Ordenar la cadena de difusión» como una PÁGINA DE HISTORIETA. Misma partida
# (frontend/minijuegos/cronologia_calculos.PartidaOrden) y mismo resultado; solo cambia cómo se ve y se toca:
#   - cada mensaje es una VIÑETA (borde de tinta, la escena del hecho, cartela amarilla «quién · hora» y un globo con lo
#     que dice). La escena sale del caso y de quién lo dice (frontend/minijuegos_visual/cronologia_vinetas_calculos.py);
#   - las viñetas están en una cuadrícula que se LEE como un cómic: de izquierda a derecha y de arriba abajo. Ese orden de
#     lectura ES el orden cronológico: ordenar los hechos = ordenar la historieta. El último hueco es la portada;
#   - se agarra una viñeta (Enter / Espacio / clic), las flechas la llevan antes o después y se suelta; «C» comprueba;
#   - al comprobar: sellos «EN SU PUESTO» / «ERA LA 3.ª» y la historieta se «lee» en su orden REAL mientras el rumor CRECE
#     con cada reenvío (mayúsculas, signos y «¡¡COMPARTE YA!!»).
# APAGADO: ALCALDE_CRONOLOGIA_VISUAL=0. GUARDIÁN: si la página falla al montarse, el minijuego se construye como siempre
# (la lista); si falla después, se avisa una vez y lo añadido se queda quieto. REDUCIR MOVIMIENTO: sin levantar ni latir.

import math

from ursina import Entity, Mesh, Text, color

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.componentes import destruir_arbol, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.cronologia import ANCHO_BOTONES, MinijuegoCronologia
from frontend.minijuegos.cronologia_calculos import PartidaOrden
from frontend.minijuegos_visual import cronologia_vinetas_calculos as vin
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual

CRONOLOGIA_VISUAL = True
VARIABLE = "ALCALDE_CRONOLOGIA_VISUAL"

COLUMNAS = 3
CANAL = 0.024                     # calle (hueco) entre viñetas
Y_ABAJO_PAGINA = -0.42            # la página llega hasta aquí (el pie de teclas está en -0,485)
BORDE = 0.007                     # grosor del borde de tinta
ALTO_CARTELA = 0.034
PAPEL = (252, 248, 232)
AMARILLO = (255, 214, 60)
FOCO = (255, 214, 60)
AGARRE = (80, 200, 255)          # cian: se distingue del amarillo del foco
VERDE = (60, 170, 90)
ROJO = (210, 50, 50)
DUR_PASO = 1.0
ESCALA_MAX_BURBUJA = 1.1


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _triangulo():
    return Mesh(vertices=[(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)], triangles=[(0, 1, 2)], mode="triangle")


def dibujar_vineta(padre, figuras, alto, position=(0, 0, 0)):
    """Escena de una viñeta (las primitivas de cronologia_vinetas_calculos) de `alto` unidades. Las figuras grandes
    llevan contorno de tinta, como en un cómic."""
    raiz = Entity(parent=padre, position=position, scale=alto)
    for i, f in enumerate(figuras):
        z = -0.002 * (i + 1)
        if f["f"] == "texto":
            Text(f["t"], parent=raiz, origin=(0, 0), position=(f["x"], f["y"], z - 0.001), scale=f["tam"] / Text.size,
                 font=tipografia.FUENTE_TITULO, color=_rgba(f["c"]))
            continue
        modelo = {"rect": "quad", "circulo": "circle"}.get(f["f"])
        contorno = i >= 2 and min(f["w"], f["h"]) >= 0.045 and f["c"] != vin.TINTA
        if contorno:
            Entity(parent=raiz, model=modelo or _triangulo(), position=(f["x"], f["y"], z + 0.001),
                   scale=(f["w"] + 0.024, f["h"] + 0.024), rotation_z=f.get("rot", 0.0), color=_rgba(vin.TINTA))
        Entity(parent=raiz, model=modelo or _triangulo(), position=(f["x"], f["y"], z), scale=(f["w"], f["h"]),
               rotation_z=f.get("rot", 0.0), color=_rgba(f["c"]))
    return raiz


class Vineta(Entity):
    """Un HUECO de la página (su sitio no cambia; lo que cambia es qué mensaje muestra). Misma interfaz que ui.Tarjeta
    para el minijuego base: titulo, cuerpo, estado, habilitada, al_clic, fijar_estado(), fijar_foco()."""

    ESTADOS = {"normal", "seleccionada", "correcta", "incorrecta"}

    def __init__(self, ancho, alto, numero, al_clic=None, al_cursor=None, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto = ancho, alto
        self.al_clic, self.al_cursor = al_clic, al_cursor
        self.habilitada = True
        self.estado = "normal"
        self._foco = False
        self._etiqueta = None
        alto_escena = (ancho - 2 * BORDE) / vin.ASPECTO
        self.alto_escena = alto_escena
        self.marco_foco = Entity(parent=self, model="quad", scale=(ancho + 0.03, alto + 0.03), z=0.02,
                                 color=_rgba(FOCO), enabled=False)
        self.sombra = Entity(parent=self, model="quad", scale=(ancho, alto), position=(0.008, -0.01, 0.015),
                             color=_rgba((0, 0, 0), 0.45))
        Entity(parent=self, model="quad", scale=(ancho, alto), z=0.01, color=_rgba(vin.TINTA))
        self.fondo = Entity(parent=self, model="quad", scale=(ancho - 2 * BORDE, alto - 2 * BORDE), z=0.009,
                            color=_rgba(PAPEL))
        # La escena va arriba, a todo el ancho; debajo, el globo con lo que se dijo.
        self.y_escena = alto / 2 - BORDE - alto_escena / 2
        self.hueco_escena = Entity(parent=self, position=(0, self.y_escena, 0.005))
        Entity(parent=self, model="quad", scale=(ancho - 2 * BORDE, 0.004),
               position=(0, self.y_escena - alto_escena / 2, 0.004), color=_rgba(vin.TINTA))
        # Cartela amarilla (arriba a la izquierda, sobre la escena).
        ancho_cartela = ancho - 2 * BORDE - 0.035
        self.cartela = Entity(parent=self, position=(-ancho / 2 + BORDE + ancho_cartela / 2,
                                                      alto / 2 - BORDE - ALTO_CARTELA / 2, -0.02))
        Entity(parent=self.cartela, model="quad", scale=(ancho_cartela, ALTO_CARTELA), color=_rgba(AMARILLO), z=0.001)
        Entity(parent=self.cartela, model="quad", scale=(ancho_cartela, 0.003), y=-ALTO_CARTELA / 2,
               color=_rgba(vin.TINTA))
        self._ancho_cartela = ancho_cartela
        self.titulo = Text("", parent=self.cartela, origin=(-0.5, 0), x=-ancho_cartela / 2 + 0.008,
                           scale=escala_fuente(12), font=tipografia.FUENTE_TITULO, color=_rgba(vin.TINTA))
        # Globo de diálogo (blanco con borde de tinta y cola hacia el personaje, que está a la derecha de la escena).
        alto_globo = alto - 2 * BORDE - alto_escena - 0.016
        y_globo = -alto / 2 + BORDE + 0.006 + alto_globo / 2
        self._ancho_globo = ancho - 2 * BORDE - 0.02
        self.globo = Entity(parent=self, position=(0, y_globo, -0.02))
        ui.rect(self.globo, self._ancho_globo + 0.006, alto_globo + 0.006, vin.TINTA, (0, 0), z=0.002, radio_px=12)
        ui.rect(self.globo, self._ancho_globo, alto_globo, (255, 255, 255), (0, 0), z=0.001, radio_px=10)
        Entity(parent=self.globo, model=_triangulo(), scale=(0.028, 0.03),
               position=(self._ancho_globo * 0.28, alto_globo / 2 + 0.012, 0.0015), color=_rgba(vin.TINTA))
        Entity(parent=self.globo, model=_triangulo(), scale=(0.02, 0.024),
               position=(self._ancho_globo * 0.28, alto_globo / 2 + 0.008, 0.0005), color=_rgba((255, 255, 255)))
        self._alto_globo = alto_globo
        self.cuerpo = Text("", parent=self.globo, origin=(-0.5, 0), position=(-self._ancho_globo / 2 + 0.012, 0, -0.001),
                           scale=escala_fuente(13), color=_rgba((25, 25, 35)), line_height=1.15)
        # Número de lectura del hueco (no se mueve: «esta es la 1.ª viñeta», «la 2.ª»...).
        self.numero = Entity(parent=self, position=(ancho / 2 - 0.004, alto / 2 - 0.004, -0.03))
        Entity(parent=self.numero, model="circle", scale=0.042, color=_rgba(vin.TINTA), z=0.001)
        Entity(parent=self.numero, model="circle", scale=0.034, color=_rgba(PAPEL))
        Text(str(numero), parent=self.numero, origin=(0, 0), z=-0.001, scale=escala_fuente(15),
             font=tipografia.FUENTE_TITULO, color=_rgba(vin.TINTA))
        # Cartel «AGARRADA» y sello del resultado.
        self.agarre = Entity(parent=self, position=(0, self.y_escena - alto_escena / 2 + 0.024, -0.04), enabled=False)
        Entity(parent=self.agarre, model="quad", scale=(min(ancho - 0.03, 0.34), 0.034), color=_rgba(vin.TINTA), z=0.002)
        Entity(parent=self.agarre, model="quad", scale=(min(ancho - 0.036, 0.334), 0.028), color=_rgba(AGARRE), z=0.001)
        Text("AGARRADA: muévela con las flechas", parent=self.agarre, origin=(0, 0), scale=escala_fuente(10),
             font=tipografia.FUENTE_TITULO, color=_rgba(vin.TINTA))
        self.sello = Entity(parent=self, position=(0, self.y_escena - 0.01, -0.05), rotation_z=-8, enabled=False)
        self.sello_borde = Entity(parent=self.sello, model="quad", scale=(ancho * 0.72, 0.06), z=0.001)
        self.sello_fondo = Entity(parent=self.sello, model="quad", scale=(ancho * 0.72 - 0.01, 0.05))
        self.sello_txt = Text("", parent=self.sello, origin=(0, 0), z=-0.001, scale=escala_fuente(17),
                              font=tipografia.FUENTE_TITULO, color=_rgba(PAPEL))
        # Zona de clic.
        self.golpe = Entity(parent=self, model="quad", scale=(ancho, alto), collider="box", color=_rgba((0, 0, 0), 0),
                            z=-0.06)
        self.golpe.on_click = self._clic
        self.golpe.on_mouse_enter = self._entra
        self._pintar()

    # -- Contenido --

    def mostrar(self, escena, item):
        """Pone la escena (Entity hecha con dibujar_vineta) y los textos del mensaje `item` en este hueco."""
        escena.parent = self.hueco_escena
        escena.position = (0, 0, 0)
        escena.enabled = True
        # La HORA es la pista para ordenar: siempre entera. Si no cabe, se recorta el nombre.
        hora = f"  ·  {item.get('hora') or 'sin hora'}"
        quien = str(item["quien"])
        while len(ui.lineas_de(quien + hora, 12, self._ancho_cartela - 0.016, True)) > 1 and len(quien) > 4:
            quien = quien.rstrip("…")[:-1].rstrip(" «(·") + "…"
        self.titulo.text = quien + hora
        lineas = ui.lineas_de(item["texto"], 13, self._ancho_globo - 0.04)      # aire a la derecha del globo
        maximo = max(1, int((self._alto_globo - 0.012) / 0.026))
        if len(lineas) > maximo:
            lineas = lineas[:maximo]
            lineas[-1] = lineas[-1].rstrip(" .,") + "…"
        self.cuerpo.text = "\n".join(lineas)

    # -- Interfaz de ui.Tarjeta --

    def fijar_estado(self, estado, etiqueta=None):
        self.estado = estado if estado in self.ESTADOS else "normal"
        self._etiqueta = etiqueta
        self._pintar()

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self._pintar()

    def _pintar(self):
        if self.is_empty():
            return
        agarrada = self.estado == "seleccionada"
        self.marco_foco.enabled = self._foco or agarrada
        self.marco_foco.color = _rgba(AGARRE if agarrada else FOCO)
        self.agarre.enabled = agarrada
        levantar = agarrada and not bv.reducir_movimiento()
        self.sombra.position = (0.012, -0.014, 0.015) if levantar else (0.008, -0.01, 0.015)
        self.z = -0.03 if agarrada else 0.0
        self.rotation_z = -2 if levantar else 0           # la agarrada se inclina y crece un poco: «está en la mano»
        self.scale = 1.03 if levantar else 1.0
        if self.estado in ("correcta", "incorrecta"):
            tono = VERDE if self.estado == "correcta" else ROJO
            self.sello.enabled = True
            self.sello_borde.color = _rgba(PAPEL)
            self.sello_fondo.color = _rgba(tono)
            texto = self._etiqueta or ("EN SU PUESTO" if self.estado == "correcta" else "FUERA DE SITIO")
            self.sello_txt.text = texto.replace("ERA EL", "ERA LA").replace(".º", ".ª")
        else:
            self.sello.enabled = False

    def _clic(self):
        if not self.is_empty() and self.habilitada and self.al_clic is not None:
            self.al_clic()

    def _entra(self):
        if not self.is_empty() and self.habilitada and self.al_cursor is not None:
            self.al_cursor()


class CronologiaVisual(CapaVisual, MinijuegoCronologia):

    _reloj_roto = False             # (nombre histórico: «lo visual está roto»)
    AYUDA = ("Flechas: cambiar de viñeta   Enter o Espacio: agarrar o soltar (agarrada, las flechas la llevan antes o "
             "después)   C: comprobar")

    def construir(self):
        self._listo = False
        self._t_reproduccion = None
        self.burbuja = None
        self.pagina = None
        try:
            self._construir_pagina()
            self._listo = True
            self._pintar_filas()
        except Exception as error:      # noqa: BLE001  la página no se pudo montar: el minijuego de siempre
            bv.avisar_una_vez("cronologia_visual", error)
            self._reloj_roto = True
            if self.pagina is not None:
                destruir_arbol(self.pagina)
            for nombre in ("boton_subir", "boton_bajar", "boton_comprobar", "nota", "intro"):
                e = getattr(self, nombre, None)
                if e is not None:
                    destruir_arbol(e)
            MinijuegoCronologia.construir(self)

    # -- Montaje --

    def _construir_pagina(self):
        self.partida = PartidaOrden(self.caso, self.azar)
        p = self.partida
        self.agarrado = False
        n = len(p.orden)
        y = Y_CONTENIDO_ARRIBA
        texto_intro = ("Ordena la historieta para ver cómo se fue contando el rumor. Se lee de izquierda a derecha y de "
                       "arriba abajo: la viñeta 1 es lo que se dijo primero. Fíjate en la hora de cada cartela.")
        self.intro = ui.texto(self, texto_intro, 16, ANCHO_UTIL, estilo.COLOR_TEXTO, (-ANCHO_UTIL / 2, y))
        y -= self.intro.alto + 0.018
        self.y0 = y
        # Página: a la izquierda; la columna de botones, a la derecha (como en el resto de minijuegos).
        x_der = ANCHO_UTIL / 2 - ANCHO_BOTONES / 2
        izquierda, derecha = -ANCHO_UTIL / 2 + 0.02, x_der - ANCHO_BOTONES / 2 - 0.05   # el papel, dentro de los márgenes
        filas_pagina = math.ceil((n + 1) / COLUMNAS)
        ancho = (derecha - izquierda - (COLUMNAS - 1) * CANAL) / COLUMNAS
        alto = min((y - Y_ABAJO_PAGINA - (filas_pagina - 1) * CANAL) / filas_pagina, ancho * 0.95)
        self.pagina = Entity(parent=self)
        alto_total = filas_pagina * alto + (filas_pagina - 1) * CANAL
        # Papel de la página detrás de todo, con su sombra.
        cx, cy = (izquierda + derecha) / 2, y - alto_total / 2
        Entity(parent=self.pagina, model="quad", position=(cx + 0.01, cy - 0.012, 0.06),
               scale=(derecha - izquierda + 0.05, alto_total + 0.05), color=_rgba((0, 0, 0), 0.5))
        Entity(parent=self.pagina, model="quad", position=(cx, cy, 0.05),
               scale=(derecha - izquierda + 0.04, alto_total + 0.04), color=_rgba((236, 228, 206)))
        self._sitios = []
        for i in range(filas_pagina * COLUMNAS):
            fila, col = divmod(i, COLUMNAS)
            self._sitios.append((izquierda + ancho / 2 + col * (ancho + CANAL), y - alto / 2 - fila * (alto + CANAL)))
        self.filas = [Vineta(ancho, alto, pos + 1, parent=self.pagina, position=(*self._sitios[pos], 0),
                             al_clic=lambda pos=pos: self.tocar(pos), al_cursor=lambda pos=pos: self.poner_foco(pos))
                      for pos in range(n)]
        # Flechas de lectura en las calles (de una viñeta a la siguiente de su fila).
        for pos in range(n):
            if pos % COLUMNAS != COLUMNAS - 1:
                x, yy = self._sitios[pos]
                Entity(parent=self.pagina, model=_triangulo(), rotation_z=90, scale=(0.022, 0.016),
                       position=(x + ancho / 2 + CANAL / 2, yy, -0.01), color=_rgba(vin.TINTA))
        self._portada(self._sitios[n], ancho, alto)
        # Una escena por mensaje, hecha UNA vez: luego solo cambia de hueco.
        escenario = vin.escenario_de(self.caso)
        alto_escena = self.filas[0].alto_escena
        self.escenas = [dibujar_vineta(self.pagina, vin.figuras(escenario, vin.actor_de(item), item.get("quien", "")),
                                       alto_escena) for item in p.correcto]
        self.alto_fila, self.paso = alto, alto + CANAL
        # Botones (los mismos que el minijuego base, con nombres de historieta).
        self.boton_subir = ui.Boton("Mover antes", lambda: self._mover(-1), ANCHO_BOTONES, 0.07, 17, parent=self,
                                    position=(x_der, y - 0.035))
        self.boton_bajar = ui.Boton("Mover después", lambda: self._mover(+1), ANCHO_BOTONES, 0.07, 17, parent=self,
                                    position=(x_der, y - 0.125))
        self.boton_comprobar = ui.Boton("Comprobar el orden", self.comprobar, ANCHO_BOTONES, 0.08, 17, primario=True,
                                        parent=self, position=(x_der, y - 0.235))
        self.nota = ui.texto(self, "", 15, ANCHO_BOTONES, estilo.COLOR_TEXTO_TENUE, (x_der - ANCHO_BOTONES / 2, y - 0.3))
        self.focables = self.filas + [self.boton_comprobar]

    def _portada(self, sitio, ancho, alto):
        """El último hueco: la portada del cómic con el título del caso y cómo se lee."""
        portada = Entity(parent=self.pagina, position=(*sitio, 0))
        Entity(parent=portada, model="quad", scale=(ancho, alto), z=0.01, color=_rgba(vin.TINTA))
        Entity(parent=portada, model="quad", scale=(ancho - 2 * BORDE, alto - 2 * BORDE), z=0.009, color=_rgba(ROJO))
        for k in range(5):                       # franjas de portada (dentro del recuadro)
            Entity(parent=portada, model="quad", scale=(ancho - 2 * BORDE, 0.018),
                   y=-alto / 2 + BORDE + 0.03 + k * (alto - 0.07) / 4, z=0.008, color=_rgba((228, 78, 70)))
        titulo = ui.lineas_de(self.caso.get("titulo", "La cadena"), 18, ancho - 0.06, True)[:3]
        caja_alto = 0.03 * len(titulo) + 0.02
        ui.rect(portada, ancho - 0.04, caja_alto + 0.006, vin.TINTA, (0, 0.04), z=0.002, radio_px=6)
        ui.rect(portada, ancho - 0.046, caja_alto, AMARILLO, (0, 0.04), z=0.001, radio_px=5)
        Text("\n".join(titulo), parent=portada, origin=(0, 0), position=(0, 0.04, -0.001), scale=escala_fuente(18),
             font=tipografia.FUENTE_TITULO, color=_rgba(vin.TINTA))
        banda_y = 0.04 - caja_alto / 2 - 0.05
        Entity(parent=portada, model="quad", scale=(ancho - 2 * BORDE, 0.05), y=banda_y, z=0.001, color=_rgba(vin.TINTA))
        self.portada_txt = Text("Se lee de izquierda a derecha", parent=portada, origin=(0, 0),
                                position=(0, banda_y, -0.001), scale=escala_fuente(14), font=tipografia.FUENTE_TITULO,
                                color=_rgba(PAPEL))
        Text("FIN", parent=portada, origin=(0.5, -0.5), position=(ancho / 2 - 0.02, -alto / 2 + 0.015, -0.001),
             scale=escala_fuente(14), font=tipografia.FUENTE_TITULO, color=_rgba(AMARILLO))

    # -- Pintar la página según la partida --

    def _pintar_filas(self):
        if self._reloj_roto or not getattr(self, "_listo", False):
            if not self._reloj_roto:
                return                 # aún montando la página
            super()._pintar_filas()
            return
        self._vigilar(self._pintar_pagina)

    def _pintar_pagina(self):
        for pos, vineta in enumerate(self.filas):
            k = self.partida.orden[pos]
            vineta.mostrar(self.escenas[k], self.partida.item(pos))
            if not self.terminado:
                vineta.fijar_estado("seleccionada" if (self.agarrado and pos == self.foco) else "normal")

    def _mover(self, delta):
        antes = self.foco
        super()._mover(delta)
        if getattr(self, "_listo", False) and not self._reloj_roto and self.foco != antes and self._fx is not None:
            self._vigilar(self._fx.pulso, self.filas[self.foco])

    # -- Momento estrella: la historieta se lee en su orden real y el rumor crece con cada reenvío --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if getattr(self, "_listo", False) and not self._reloj_roto:
            self._vigilar(self._empezar_reproduccion)
            bien = sum(1 for x in self.partida.en_su_puesto() if x)
            self.portada_txt.text = f"{bien} de {len(self.filas)} en su puesto"

    def _empezar_reproduccion(self):
        x_der = ANCHO_UTIL / 2 - ANCHO_BOTONES / 2
        self.nota.enabled = False
        for b in (self.boton_subir, self.boton_bajar, self.boton_comprobar):
            b.enabled = False
        # Globo de cómic anclado arriba a la IZQUIERDA (crece hacia la derecha y hacia abajo, lejos de la página), con
        # borde de tinta y pico hacia la página. Su alto se ajusta a las líneas de cada reenvío.
        self.burbuja = Entity(parent=self, position=(x_der - ANCHO_BOTONES / 2, self.y0 - 0.005, -0.1))
        self.burbuja_forma = Entity(parent=self.burbuja)
        self.burbuja_quien = Text("", parent=self.burbuja, origin=(-0.5, 0.5), position=(0.016, -0.016, -0.003),
                                  scale=escala_fuente(13), font=tipografia.FUENTE_TITULO, color=_rgba((90, 90, 110)))
        self.burbuja_txt = Text("", parent=self.burbuja, origin=(-0.5, 0.5), position=(0.016, -0.05, -0.003),
                                scale=escala_fuente(15), color=_rgba((25, 25, 35)), line_height=1.1)
        self._t_reproduccion = 0.0
        self._paso_visto = None

    def _pintar_reproduccion(self, reducir):
        correcto = self.partida.correcto
        paso = calc.paso_reproduccion(self._t_reproduccion, len(correcto), DUR_PASO)
        if paso is None:
            if self._t_reproduccion > DUR_PASO * len(correcto) + 2.5:
                self.burbuja.enabled = False
                for vineta in self.filas:
                    vineta.fijar_foco(False)
                self.nota.enabled = True
                self._t_reproduccion = None
            return
        if paso == self._paso_visto:
            return
        self._paso_visto = paso
        item = correcto[paso]
        self.burbuja_quien.text = f"Reenvío {paso + 1} de {len(correcto)} · {calc.recortar(item['quien'], 16)}"
        texto = calc.exagerar(item["texto"], paso)
        lineas = ui.lineas_de(texto, 15, ANCHO_BOTONES - 0.04)[:6]
        self.burbuja_txt.text = "\n".join(lineas)
        self._forma_burbuja(0.07 + 0.03 * len(lineas))
        self.burbuja.scale = 1.0 if reducir else min(ESCALA_MAX_BURBUJA, calc.escala_burbuja(paso))
        # Se «lee» la viñeta de ese mensaje (donde la dejó el jugador): se enciende su marco y late.
        for pos, vineta in enumerate(self.filas):
            es = self.partida.orden[pos] == paso
            vineta.fijar_foco(es)
            if es and self._fx is not None:
                self._fx.pulso(vineta)

    def _forma_burbuja(self, alto):
        for hijo in list(self.burbuja_forma.children):
            destruir_arbol(hijo)
        ancho = ANCHO_BOTONES + 0.02
        ui.rect(self.burbuja_forma, ancho + 0.008, alto + 0.008, vin.TINTA, (ancho / 2, -alto / 2), z=0.002, radio_px=16)
        ui.rect(self.burbuja_forma, ancho, alto, (255, 255, 255), (ancho / 2, -alto / 2), z=0.001, radio_px=14)
        Entity(parent=self.burbuja_forma, model=_triangulo(), rotation_z=-90, scale=(0.04, 0.04),
               position=(-0.016, -0.04, 0.0015), color=_rgba(vin.TINTA))
        Entity(parent=self.burbuja_forma, model=_triangulo(), rotation_z=-90, scale=(0.028, 0.03),
               position=(-0.009, -0.04, 0.0005), color=_rgba((255, 255, 255)))

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not getattr(self, "_listo", False) or self._reloj_roto:
            return
        if self._t_reproduccion is not None:
            self._t_reproduccion += dt
            self._vigilar(self._pintar_reproduccion, self._fx.reducir if self._fx is not None else bv.reducir_movimiento())

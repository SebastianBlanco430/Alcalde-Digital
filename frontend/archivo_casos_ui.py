# Archivo de casos (Ursina, camera.ui): panel a pantalla completa con el historial de la investigación. Izquierda, el
# registro cronológico (tres líneas por registro: categoría + título, detalle y deltas con signo) con filtros por caso,
# tipo y grupo/NPC y desplazamiento; derecha, los casos jugados, las evidencias con su origen y el efecto acumulado por
# grupo / NPC. Toda la lógica (qué se muestra, filtros, textos) vive en backend/logica/archivo_casos.py; aquí solo se
# dibuja, y solo cuando algo cambia (abrir, filtrar, desplazar): no hay update() por frame.
#
# El texto SIEMPRE acompaña al color (la categoría va escrita; los deltas llevan signo). Se diseña a 16:9 (x en
# [-0.89, 0.89]) y se encoge si la ventana es más estrecha (diseno_adaptable.ajustar_escala).
# `ControlArchivoCasos` es el Entity que oye las teclas (J abre/cierra; el resto solo con el panel abierto).

from ursina import Entity, Text, camera, color

from backend.logica import archivo_casos as logica
from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import BotonSecundario, escala_fuente, panel_tinta, rgb

FILAS = 8
ALTO_FILA = 0.083
ARRIBA_FILAS = 0.305                          # y de la primera fila (su borde superior)
X_FILAS = -0.855
ANCHO_FILA_CHARS = 98
ANCHO_LATERAL_CHARS = 42
ANCHO_IZQ, ALTO_PANEL = 1.24, 0.93
ANCHO_DER = 0.52
CENTRO_IZQ, CENTRO_DER = -0.25, 0.615
Z_PANEL = -0.06
COLOR_CATEGORIA = {
    "evidencia": estilo.ESTADO_INFO, "decision": estilo.COLOR_ACENTO, "prueba": (255, 170, 60),
    "hallazgo": estilo.COLOR_TEXTO_TENUE, "acusacion": estilo.ESTADO_ERROR, "resultado": estilo.ESTADO_EXITO,
}
TECLAS_FILTRO = {"caso": "C", "tipo": "T", "actor": "F"}


def _texto(padre, cadena="", px=15, origen=(0, 0), pos=(0, 0), tono=estilo.COLOR_TEXTO, negrita=False, z=-0.02):
    extra = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena, parent=padre, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px),
                color=rgb(tono), **extra)


class ArchivoCasosUI(Entity):

    # textos: backend/datos/archivo_casos_textos.json ya cargado. al_cerrar: callable opcional.
    def __init__(self, textos, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        self.textos = textos
        self.consulta = None
        self.ctx = None
        self.z = Z_PANEL
        self.fondo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 240), z=0.02)
        self._construir_izquierda()
        self._construir_derecha()
        self.pista = _texto(self, textos["pista"], 13, pos=(0, -0.488), tono=estilo.COLOR_TEXTO_TENUE)
        self.mensaje = _texto(self, "", 18, pos=(0, 0.0), tono=estilo.COLOR_TEXTO)
        self.mensaje.enabled = False
        diseno_adaptable.ajustar_escala(self)

    # -- Construcción --

    def _construir_izquierda(self):
        self.panel = panel_tinta(self, ANCHO_IZQ, ALTO_PANEL, tono=estilo.COLOR_FONDO, position=(CENTRO_IZQ, 0, 0))
        self.titulo = _texto(self, self.textos["titulo"], 22, origen=(-0.5, 0), pos=(X_FILAS, 0.425), negrita=True,
                             tono=estilo.COLOR_ACENTO)
        self._filtros = {}
        for i, cual in enumerate(("caso", "tipo", "actor")):
            x = -0.675 + i * 0.4
            boton = BotonSecundario("", al_clic=None, ancho=0.385, alto=0.05, parent=self)
            boton.position = (x, 0.365, 0)
            etiqueta = _texto(self, "", 14, origen=(-0.5, 0), pos=(x - 0.18, 0.365), tono=estilo.COLOR_BOTON_TEXTO)
            self._filtros[cual] = (boton, etiqueta)
        self._filtros["caso"][0].accion = self.ciclar_caso
        self._filtros["tipo"][0].accion = self.ciclar_tipo
        self._filtros["actor"][0].accion = self.ciclar_actor
        self._tirillas, self._filas = [], []
        for i in range(FILAS):
            y = ARRIBA_FILAS - i * ALTO_FILA
            tirilla = Entity(parent=self, model="quad", scale=(0.008, ALTO_FILA - 0.014), position=(X_FILAS - 0.012, y - (ALTO_FILA - 0.014) / 2, -0.01),
                             color=rgb(estilo.COLOR_BARRA_FONDO))
            fila = _texto(self, "", 13, origen=(-0.5, 0.5), pos=(X_FILAS + 0.008, y))
            fila.line_height = 1.0
            self._tirillas.append(tirilla)
            self._filas.append(fila)
        self._escala_fila = escala_fuente(13)
        alto_pista = FILAS * ALTO_FILA
        self.riel = Entity(parent=self, model="quad", scale=(0.006, alto_pista), position=(0.355, ARRIBA_FILAS - alto_pista / 2, -0.01),
                           color=rgb(estilo.COLOR_BARRA_FONDO))
        self.pulgar = Entity(parent=self, model="quad", scale=(0.012, alto_pista), position=(0.355, ARRIBA_FILAS - alto_pista / 2, -0.02),
                             color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.posicion = _texto(self, "", 14, origen=(-0.5, 0), pos=(X_FILAS, -0.43), tono=estilo.COLOR_TEXTO_TENUE)
        self.vacio = _texto(self, self.textos["vacio"], 16, pos=(CENTRO_IZQ, 0.0), tono=estilo.COLOR_TEXTO_TENUE)

    def _construir_derecha(self):
        self.panel_der = panel_tinta(self, ANCHO_DER, ALTO_PANEL, tono=estilo.COLOR_PANEL, position=(CENTRO_DER, 0, 0))
        x = CENTRO_DER - ANCHO_DER / 2 + 0.02
        secciones = self.textos["secciones"]
        self._laterales = {}
        self._titulos_der = []
        for clave, y_titulo in (("casos", 0.425), ("evidencias", 0.215), ("resumen", -0.095)):
            self._titulos_der.append(_texto(self, secciones[clave], 17, origen=(-0.5, 0), pos=(x, y_titulo), negrita=True,
                                            tono=estilo.COLOR_ACENTO))
            cuerpo = _texto(self, "", 13, origen=(-0.5, 0.5), pos=(x, y_titulo - 0.025))
            cuerpo.line_height = 1.0
            self._laterales[clave] = cuerpo
        self._escala_lateral = escala_fuente(13)

    # -- Estado --

    def abierto(self):
        return bool(self.enabled)

    # Abre con el archivo reconstruido (ver backend/logica/archivo_casos.construir) y el Contexto de nombres.
    # archivo None = sin GameState: solo el aviso «Archivo no disponible».
    def abrir(self, archivo, ctx):
        self.ctx = ctx
        self.consulta = logica.ConsultaArchivo(archivo, FILAS) if archivo is not None else None
        self.enabled = True
        self.refrescar()

    def cerrar(self):
        self.enabled = False

    # -- Acciones (las llama el control con las teclas y los botones) --

    def ciclar_caso(self):
        self._accion("ciclar_caso")

    def ciclar_tipo(self):
        self._accion("ciclar_categoria")

    def ciclar_actor(self):
        self._accion("ciclar_actor")

    def quitar_filtros(self):
        self._accion("quitar_filtros")

    def desplazar(self, filas):
        self._accion("desplazar", filas)

    def pagina(self, sentido):
        self._accion("pagina", sentido)

    def al_inicio(self):
        self._accion("al_inicio")

    def al_final(self):
        self._accion("al_final")

    def _accion(self, nombre, *args):
        if self.consulta is None:
            return
        getattr(self.consulta, nombre)(*args)
        self.refrescar()

    # -- Dibujo --

    def refrescar(self):
        c = self.consulta
        sin_archivo = c is None
        self.mensaje.enabled = sin_archivo
        for clave in ("caso", "tipo", "actor"):
            boton, etiqueta = self._filtros[clave]
            boton.enabled = etiqueta.enabled = not sin_archivo
        for cuerpo in self._laterales.values():
            cuerpo.enabled = not sin_archivo
        self.panel_der.enabled = not sin_archivo
        for titulo in self._titulos_der:
            titulo.enabled = not sin_archivo
        self.pista.text = self.textos.get("pista_no_disponible", self.textos["pista"]) if sin_archivo else self.textos["pista"]
        self.riel.enabled = self.pulgar.enabled = not sin_archivo
        if sin_archivo:
            self.mensaje.text = f"{self.textos['no_disponible']}\n{self.textos.get('no_disponible_detalle', '')}"
            for fila, tirilla in zip(self._filas, self._tirillas):
                fila.enabled = tirilla.enabled = False
            self.vacio.enabled = False
            self.posicion.text = ""
            return
        for clave in ("caso", "tipo", "actor"):
            etiqueta = logica.etiqueta_filtro(c, clave, self.ctx)
            self._filtros[clave][1].text = f"{etiqueta} [{TECLAS_FILTRO[clave]}]"
        visibles = c.visibles()
        total_filtrado = len(c.entradas())
        self.vacio.enabled = not visibles
        if not visibles:
            self.vacio.text = self.textos["sin_coincidencias"] if c.archivo.entradas else self.textos["vacio"]
        for i in range(FILAS):
            fila, tirilla = self._filas[i], self._tirillas[i]
            if i >= len(visibles):
                fila.enabled = tirilla.enabled = False
                continue
            entrada = visibles[i]
            fila.enabled = tirilla.enabled = True
            fila.text = "\n".join(logica.lineas_de_entrada(entrada, self.ctx, ANCHO_FILA_CHARS))
            tirilla.color = rgb(COLOR_CATEGORIA.get(entrada.categoria, estilo.COLOR_TEXTO_TENUE))
        desde, hasta, total = c.posicion()
        self.posicion.text = self.textos["posicion"].format(desde=desde, hasta=hasta, total=total) if total else ""
        self._dibujar_pulgar(desde, hasta, total_filtrado)
        self._lateral("casos", logica.lineas_casos_jugados(c.archivo, self.ctx, ANCHO_LATERAL_CHARS, 5))
        self._lateral("evidencias", logica.lineas_evidencias(c.archivo, self.ctx, ANCHO_LATERAL_CHARS, 10))
        self._lateral("resumen", logica.lineas_resumen(c, self.ctx, ANCHO_LATERAL_CHARS, 9))

    def _lateral(self, clave, lineas):
        self._laterales[clave].text = "\n".join(lineas)

    def _dibujar_pulgar(self, desde, hasta, total):
        alto_riel = self.riel.scale_y
        if total <= FILAS or total == 0:
            self.pulgar.scale_y = alto_riel
            self.pulgar.y = self.riel.y
            return
        alto = max(0.03, alto_riel * FILAS / total)
        recorrido = alto_riel - alto
        fraccion = (desde - 1) / max(1, total - FILAS)
        self.pulgar.scale_y = alto
        self.pulgar.y = self.riel.y + alto_riel / 2 - alto / 2 - recorrido * fraccion


# Entity siempre activo que oye las teclas del Archivo. J abre/cierra (si `puede_abrir()`); con el panel abierto atiende
# el desplazamiento y los filtros. `abrir_o_cerrar()` hace lo que hace J (para los tests y los botones).
class ControlArchivoCasos(Entity):

    def __init__(self, ui, tecla, puede_abrir, al_abrir, **opciones):
        super().__init__(**opciones)
        self.ui = ui
        self.tecla = tecla
        self._puede_abrir = puede_abrir
        self._al_abrir = al_abrir

    def abrir_o_cerrar(self):
        if self.ui.abierto():
            self.ui.cerrar()
        elif self._puede_abrir():
            self._al_abrir()

    def input(self, key):
        if key == self.tecla:
            self.abrir_o_cerrar()
            return
        if not self.ui.abierto():
            return
        ui = self.ui
        if key in ("down arrow", "scroll down"):
            ui.desplazar(1)
        elif key in ("up arrow", "scroll up"):
            ui.desplazar(-1)
        elif key == "page down":
            ui.pagina(1)
        elif key == "page up":
            ui.pagina(-1)
        elif key == "home":
            ui.al_inicio()
        elif key == "end":
            ui.al_final()
        elif key == "c":
            ui.ciclar_caso()
        elif key == "t":
            ui.ciclar_tipo()
        elif key == "f":
            ui.ciclar_actor()
        elif key == "x":
            ui.quitar_filtros()

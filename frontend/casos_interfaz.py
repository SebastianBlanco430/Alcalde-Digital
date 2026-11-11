# Interfaz 2D (camera.ui) para jugar un caso en el mundo digital: retrato y nombre del que habla, cuadro de diálogo,
# menú de preguntas / pruebas / acusación (numerado, se elige con 1-9 o con clic), panel de evidencias, temporizador de
# la pregunta con TEXTO además de color, mensajes de acierto/error y una pista de teclas. Qué filas mostrar lo decide
# la capa pura (mundo_digital_calculos.filas_de_nodo); aquí solo se dibujan.
#
# Se diseña a 16:9 (x en [-0.89, 0.89]) y se encoge si la ventana es más estrecha (diseno_adaptable.ajustar_escala).
# Estilo: estilo.py y panel_tinta; texto con la fuente por defecto (Atkinson Hyperlegible, con tildes y ñ).

from ursina import Entity, Text, camera, color

from frontend import diseno_adaptable, estilo, tipografia
from frontend import mundo_digital_calculos as calc
from frontend.componentes import BotonSecundario, escala_fuente, panel_tinta, rgb

MAX_FILAS = 9
MAX_EVIDENCIAS = 8
ANCHO_DIALOGO, ALTO_DIALOGO = 0.92, 0.36
ANCHO_OPCIONES, ALTO_OPCIONES = 0.92, 0.38
POS_DIALOGO = (-0.07, 0.17)
POS_OPCIONES = (-0.07, -0.25)
POS_RETRATO = (-0.70, 0.20)
POS_EVIDENCIAS = (0.665, 0.03)
ANCHO_EVIDENCIAS, ALTO_EVIDENCIAS = 0.44, 0.78
SEGUNDOS_MENSAJE = 3.5
COLOR_PELIGRO = (255, 120, 130)
COLOR_BUENO = (120, 240, 160)
TEXTO_PISTA = "1-9: elegir    P: presentar prueba    Esc: cerrar sesión (el caso queda guardado)"
POS_ENLACE = (0.665, -0.405)          # botón del parkour (debajo del panel de evidencias)
ANCHO_ENLACE, ALTO_ENLACE = 0.44, 0.06


def _texto(padre, cadena="", px=18, origen=(0, 0), pos=(0, 0), tono=estilo.COLOR_TEXTO, negrita=False, z=-0.02):
    extra = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena, parent=padre, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px),
                color=rgb(tono), **extra)


Y_BARRA_TIEMPO = -0.04            # y de la barra del temporizador dentro de su caja (debajo de la pista)


class InterfazCaso(Entity):

    # acciones: {"fila": callable(Fila), "evidencia": callable(id)}.
    def __init__(self, acciones, textura, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        self._acciones = acciones
        self._textura = textura
        self._mensaje_t = 0.0
        self._filas_texto = []
        self._construir_cabecera()
        self._construir_retrato()
        self._construir_dialogo()
        self._construir_opciones()
        self._construir_evidencias()
        self._construir_enlace()
        self._pista = _texto(self, TEXTO_PISTA, 14, pos=(-0.07, -0.485), tono=estilo.COLOR_TEXTO_TENUE)
        diseno_adaptable.ajustar_escala(self)

    # -- Construcción --

    def _construir_cabecera(self):
        self.titulo = _texto(self, "", 20, origen=(-0.5, 0), pos=(-0.86, 0.465), negrita=True)
        self.temporizador = Entity(parent=self, position=(-0.07, 0.435), enabled=False)
        # La barra va DEBAJO de la pista (antes a -0.033 tachaba el renglón de la pista, que llega a -0.03).
        self.temporizador.fondo = Entity(parent=self.temporizador, model="quad", scale=(0.62, 0.09), y=-0.004,
                                         color=color.rgba32(*estilo.COLOR_FONDO, 215), z=0.01)
        self.temporizador.texto = _texto(self.temporizador, "", 18, pos=(0, 0.018), negrita=True)
        self.temporizador.pista = _texto(self.temporizador, "", 13, pos=(0, -0.013), tono=estilo.COLOR_TEXTO_TENUE)
        self.temporizador.barra_fondo = Entity(parent=self.temporizador, model="quad", scale=(0.58, 0.008),
                                               position=(0, Y_BARRA_TIEMPO, -0.005), color=rgb(estilo.COLOR_BARRA_FONDO))
        self.temporizador.barra = Entity(parent=self.temporizador, model="quad", scale=(0.58, 0.008),
                                         position=(0, Y_BARRA_TIEMPO, -0.01), color=rgb(estilo.ESTADO_INFO))

    def _construir_retrato(self):
        marco = panel_tinta(self, 0.34, 0.34, tono=estilo.COLOR_PANEL, position=(*POS_RETRATO, 0))
        self.retrato = Entity(parent=marco, model="quad", scale=(0.31, 0.31), z=-0.01)
        placa = panel_tinta(self, 0.34, 0.1, tono=estilo.COLOR_PANEL, position=(POS_RETRATO[0], POS_RETRATO[1] - 0.235, 0))
        self.nombre = _texto(placa, "", 19, pos=(0, 0.02), negrita=True)
        self.rol = _texto(placa, "", 14, pos=(0, -0.022), tono=estilo.COLOR_TEXTO_TENUE)
        self._rol_base = escala_fuente(14)

    def _construir_dialogo(self):
        self.panel_dialogo = panel_tinta(self, ANCHO_DIALOGO, ALTO_DIALOGO, tono=estilo.COLOR_PANEL,
                                         position=(*POS_DIALOGO, 0))
        self.dialogo_titulo = _texto(self.panel_dialogo, "", 21, origen=(-0.5, 0.5), pos=(-0.43, 0.165), negrita=True,
                                     tono=estilo.COLOR_ACENTO)
        self._dialogo_base = escala_fuente(20)
        self.dialogo = Text("", parent=self.panel_dialogo, origin=(-0.5, 0.5), position=(-0.43, 0.14, -0.02),
                            scale=self._dialogo_base, color=rgb(estilo.COLOR_TEXTO))
        self.mensaje = _texto(self, "", 17, pos=(POS_DIALOGO[0], POS_DIALOGO[1] - ALTO_DIALOGO / 2 - 0.028), negrita=True)

    def _construir_opciones(self):
        self.panel_opciones = panel_tinta(self, ANCHO_OPCIONES, ALTO_OPCIONES, tono=estilo.COLOR_FONDO,
                                          position=(*POS_OPCIONES, 0))
        self._botones, self._etiquetas = [], []
        for _ in range(MAX_FILAS):
            boton = BotonSecundario("", al_clic=None, ancho=ANCHO_OPCIONES - 0.04, alto=0.05, parent=self.panel_opciones)
            boton.enabled = False
            etiqueta = Text("", parent=self.panel_opciones, origin=(-0.5, 0), scale=escala_fuente(17),
                            color=rgb(estilo.COLOR_BOTON_TEXTO))
            etiqueta.enabled = False
            self._botones.append(boton)
            self._etiquetas.append(etiqueta)
        self._etiqueta_base = escala_fuente(17)

    def _construir_evidencias(self):
        self.panel_evidencias = panel_tinta(self, ANCHO_EVIDENCIAS, ALTO_EVIDENCIAS, tono=estilo.COLOR_FONDO,
                                            position=(*POS_EVIDENCIAS, 0))
        self.evidencias_titulo = _texto(self.panel_evidencias, "Evidencias", 19, pos=(0, 0.345), negrita=True)
        self._filas_ev, self._etiquetas_ev, self._datos_ev = [], [], []
        for i in range(MAX_EVIDENCIAS):
            y = 0.275 - i * 0.062
            boton = BotonSecundario("", al_clic=None, ancho=ANCHO_EVIDENCIAS - 0.04, alto=0.052, parent=self.panel_evidencias)
            boton.position = (0, y, 0)
            boton.enabled = False
            etiqueta = Text("", parent=self.panel_evidencias, origin=(-0.5, 0), position=(-0.19, y, -0.02),
                            scale=escala_fuente(16), color=rgb(estilo.COLOR_BOTON_TEXTO))
            etiqueta.enabled = False
            self._filas_ev.append(boton)
            self._etiquetas_ev.append(etiqueta)
        self._detalle_base = escala_fuente(15)
        self.detalle = Text("", parent=self.panel_evidencias, origin=(-0.5, 0.5), position=(-0.2, -0.17, -0.02),
                            scale=self._detalle_base, color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.sin_evidencias = _texto(self.panel_evidencias, "Aún no tienes evidencias.", 15, pos=(0, 0.2),
                                     tono=estilo.COLOR_TEXTO_TENUE)

    # Botón opcional «puerta al parkour»: lo declara el caso en su JSON (backend/logica/enlace_parkour.py).
    def _construir_enlace(self):
        self.enlace = BotonSecundario("", al_clic=None, ancho=ANCHO_ENLACE, alto=ALTO_ENLACE, parent=self)
        self.enlace.position = (*POS_ENLACE, 0)
        self.enlace_etiqueta = Text("", parent=self, origin=(-0.5, 0), position=(POS_ENLACE[0] - ANCHO_ENLACE / 2 + 0.02,
                                    POS_ENLACE[1], -0.02), scale=escala_fuente(15), color=rgb(estilo.COLOR_BOTON_TEXTO))
        self.enlace_pista = Text("", parent=self, origin=(0, 0.5), position=(POS_ENLACE[0], POS_ENLACE[1] - ALTO_ENLACE / 2 - 0.006, -0.02),
                                 scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._enlace_base = escala_fuente(15)
        self._pista_base = escala_fuente(12)
        self.enlace.enabled = self.enlace_etiqueta.enabled = self.enlace_pista.enabled = False

    # -- Contenido --

    # `texto`/`pista` vienen del JSON del caso; `tecla` se anota en la etiqueta (la acción es de la escena). None lo oculta.
    def mostrar_enlace(self, texto, pista, tecla, accion):
        visible = texto is not None
        self.enlace.enabled = self.enlace_etiqueta.enabled = self.enlace_pista.enabled = visible
        if not visible:
            return
        self.enlace.accion = accion
        self._ajustar(self.enlace_etiqueta, f"{texto}  [{tecla.upper()}]", ANCHO_ENLACE - 0.04, self._enlace_base, 0.7, 1)
        self._ajustar(self.enlace_pista, pista or "", ANCHO_ENLACE - 0.02, self._pista_base, 0.8, 3)

    def fijar_caso(self, caso):
        self.titulo.text = f"Caso: {caso.titulo}"

    def mostrar_hablante(self, nombre, rol, retrato_json, expresion):
        self.nombre.text = nombre
        # «rol · actitud» se encoge hasta caber en la placa (0,34 de ancho): con roles largos se salía por los lados.
        self._ajustar(self.rol, f"{rol}  ·  {expresion}" if rol else str(expresion), 0.31, self._rol_base, 0.7, 1)
        if retrato_json is None:
            self.retrato.enabled = False
        else:
            self.retrato.enabled = True
            self.retrato.texture = self._textura(retrato_json, expresion)

    def mostrar_texto(self, titulo, texto):
        self.dialogo_titulo.text = titulo or ""
        self.dialogo.y = 0.14 if not titulo else 0.1
        self._ajustar(self.dialogo, texto, 0.86, self._dialogo_base, 0.72, 7)

    @staticmethod
    def _ajustar(entidad, cadena, ancho, base, escala_min, max_lineas):
        plan = diseno_adaptable.ajustar_texto(entidad, ancho, escala_base=base, escala_min=escala_min,
                                              max_lineas=max_lineas, cadena=cadena)
        if plan is None:
            entidad.text = cadena

    def mostrar_filas(self, filas):
        n = len(filas)
        alto_fila = min(0.07, (ALTO_OPCIONES - 0.04) / max(n, 5))
        arriba = ALTO_OPCIONES / 2 - 0.03 - alto_fila / 2
        self._filas_texto = list(filas)
        for i in range(MAX_FILAS):
            boton, etiqueta = self._botones[i], self._etiquetas[i]
            if i >= n:
                boton.enabled = etiqueta.enabled = False
                continue
            fila = filas[i]
            y = arriba - i * alto_fila
            boton.enabled = etiqueta.enabled = True
            boton.position = (0, y, 0)
            boton.scale = (ANCHO_OPCIONES - 0.04, alto_fila - 0.008)
            boton.base_scale = (boton.scale_x, boton.scale_y)
            boton.fijar_habilitado(fila.habilitada)
            boton.accion = (lambda f=fila: self._acciones["fila"](f))
            etiqueta.position = (-ANCHO_OPCIONES / 2 + 0.035, y, -0.02)
            cadena = calc.etiqueta_opcion(i, fila.texto) if fila.tipo != "salir" else fila.texto
            if not fila.habilitada and fila.motivo:
                cadena += f"   [{fila.motivo}]"
            self._ajustar(etiqueta, cadena, ANCHO_OPCIONES - 0.1, self._etiqueta_base, 0.75, 2)
            etiqueta.color = rgb(estilo.COLOR_BOTON_TEXTO if fila.habilitada else estilo.COLOR_TEXTO_TENUE)

    def mostrar_evidencias(self, items):
        # items: [(id, nombre, descripcion)]
        self._datos_ev = list(items)
        self.evidencias_titulo.text = f"Evidencias ({len(items)})"
        self.sin_evidencias.enabled = not items
        for i in range(MAX_EVIDENCIAS):
            boton, etiqueta = self._filas_ev[i], self._etiquetas_ev[i]
            if i >= len(items):
                boton.enabled = etiqueta.enabled = False
                continue
            eid, nombre, _ = items[i]
            boton.enabled = etiqueta.enabled = True
            boton.accion = (lambda e=eid: self.mostrar_detalle(e))
            self._ajustar(etiqueta, nombre, ANCHO_EVIDENCIAS - 0.1, escala_fuente(16), 0.7, 1)
        if not items:
            self.detalle.text = ""
            self._detalle_id = None
        elif getattr(self, "_detalle_id", None) not in [d[0] for d in items]:
            self.mostrar_detalle(items[0][0])

    def mostrar_detalle(self, id_evidencia):
        for eid, nombre, descripcion in self._datos_ev:
            if eid == id_evidencia:
                self._detalle_id = eid
                self._ajustar(self.detalle, descripcion, ANCHO_EVIDENCIAS - 0.08, self._detalle_base, 0.8, 9)
                return

    def mostrar_mensaje(self, texto, bueno=False):
        self.mensaje.text = texto
        self.mensaje.color = rgb(COLOR_BUENO if bueno else COLOR_PELIGRO)
        self._mensaje_t = SEGUNDOS_MENSAJE if texto else 0.0

    # restante/total en segundos; None oculta el temporizador (el nodo no tiene reloj).
    def mostrar_temporizador(self, restante, total):
        if restante is None or not total:
            self.temporizador.enabled = False
            return
        self.temporizador.enabled = True
        nivel = calc.nivel_temporizador(restante, total)
        tono = {"normal": estilo.ESTADO_INFO, "aviso": estilo.ESTADO_AVISO, "urgente": estilo.ESTADO_ERROR}[nivel]
        self.temporizador.texto.text = calc.texto_temporizador(restante, total)
        self.temporizador.pista.text = "Si se acaba, se toma la opción por defecto"
        fraccion = calc.fraccion_temporizador(restante, total)
        ancho = 0.58 * fraccion
        self.temporizador.barra.scale_x = max(ancho, 1e-4)
        self.temporizador.barra.x = -0.29 + ancho / 2
        self.temporizador.barra.color = rgb(tono)

    def avanzar(self, dt):
        if self._mensaje_t > 0:
            self._mensaje_t -= dt
            if self._mensaje_t <= 0:
                self.mensaje.text = ""

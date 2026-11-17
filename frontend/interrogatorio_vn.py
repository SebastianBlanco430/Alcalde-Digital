# Interrogatorio de los casos como NOVELA VISUAL (Ursina). Sustituye a la interfaz 2D del caso (frontend/casos_interfaz.py,
# que no se toca: esta clase HEREDA de InterfazCaso y conserva su API, su panel de evidencias, su temporizador con texto y
# su botón del parkour):
#
#   - En vez del retrato 2D, el MODELO 3D del personaje que habla aparece de cerca (plano de pecho) delante de la cámara
#     del mundo digital, con el decorado detrás oscurecido. Qué .glb y qué colores lleva cada personaje sale de
#     backend/datos/interrogatorio_modelos.json + el retrato del JSON del caso (si falta, un modelo por defecto).
#   - El cuadro de diálogo (texto letra a letra) y las opciones (preguntas, pruebas, acusación) van ABAJO.
#   - Cada nodo trae una `expresion` (neutral, serio, nervioso, enojado, satisfecho...): se traduce a postura del cuerpo
#     (npc_postura) + gesto de cara (frontend/rostro_expresivo.py) + clip (Hablar mientras sale el texto, con la boca
#     abriéndose con cada vocal; Idle al terminar). Los cambios se mezclan en 0,25 s.
#   - Prueba correcta: la carta vuela sobre la mesa, la cámara se acerca de golpe al personaje, el fondo se tiñe de alerta
#     y aparece «¡CONTRADICCIÓN!» con el personaje nervioso o enojado. Prueba equivocada: gesto de burla.
#   - Acusación: tablero de sospechosos con sus modelos en fila; al elegir, el elegido se acerca a la cámara.
#
# Toda la matemática está en frontend/interrogatorio_vn_calculos.py (puro, con tests). Teclado (1-9, P, Esc, Enter) y
# ratón siguen igual: los maneja la escena (frontend/escenas/escena_mundo_digital.py) como siempre.
#
# APAGADO: ALCALDE_INTERROGATORIO_VN=0 (o INTERROGATORIO_VN = False): se usa InterfazCaso tal cual.
# GUARDIÁN: si la vista nueva falla al construirse, elegir_interfaz_caso() devuelve InterfazCaso; si falla un modelo, ese
# personaje sale con su retrato 2D; si falla algo en un frame, avisa una vez por stderr y se apaga lo 3D (queda el retrato).
# REDUCIR MOVIMIENTO: texto entero de golpe, sin acercamiento de cámara ni parpadeo del fondo de alerta.

import math

from ursina import Entity, Text, camera, color, window

from frontend import banderas_visuales as bv
from frontend import diseno_adaptable, estilo, tipografia
from frontend import interrogatorio_vn_calculos as calc
from frontend import mundo_digital_calculos as mdc
from frontend.casos_interfaz import InterfazCaso, MAX_FILAS
from frontend.componentes import BotonSecundario, escala_fuente, panel_tinta, rgb

INTERROGATORIO_VN = True
VARIABLE = "ALCALDE_INTERROGATORIO_VN"

# Zonas de pantalla (camera.ui a 16:9): el personaje arriba a la izquierda, diálogo y opciones abajo, evidencias a la derecha.
ANCHO_VN = 1.26
POS_DIALOGO_VN, ALTO_DIALOGO_VN = (-0.235, -0.115), 0.18
POS_OPCIONES_VN, ALTO_OPCIONES_VN = (-0.235, -0.338), 0.22
POS_PLACA = (-0.70, 0.022)
POS_TEMPORIZADOR = (0.10, 0.452)
POS_MENSAJE = (-0.12, 0.335)
ANCHO_MENSAJE = 0.53
X_PERSONAJE_UI, Y_CORONILLA_UI = -0.40, 0.40
DISTANCIA = 2.3
ACERCAMIENTO = 0.55            # m que se acerca el personaje en la contradicción
DISTANCIA_TABLERO = 2.7
X_TABLERO_UI = (-0.84, 0.36)   # franja de pantalla del tablero de sospechosos
Y_TABLERO_UI = 0.30            # coronilla de las miniaturas
ROJO = (235, 87, 87)
# Orden de dibujo en el grupo "fixed": telón, luego el cuerpo del personaje; las piezas de la cara (rostro_modelo) usan
# órdenes 8..20, así que van DESPUÉS del cuerpo como siempre y el telón nunca las tapa.
ORDEN_FONDO, ORDEN_PERSONAJES = -20, -10
ALFA_FONDO = 228              # el mundo digital se intuye detrás; los retratos del decorado casi no se ven


def activo():
    return bv.activa(INTERROGATORIO_VN, VARIABLE)


def elegir_interfaz_caso(acciones, textura, **opciones):
    """Interfaz del caso: la de novela visual si su bandera está encendida y se construye bien; si no, la de siempre."""
    if activo():
        try:
            return InterfazVN(acciones, textura, **opciones)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("interrogatorio_vn", error)
    return InterfazCaso(acciones, textura, **opciones)


class InterfazVN(InterfazCaso):

    def __init__(self, acciones, textura, **opciones):
        super().__init__(acciones, textura, **opciones)
        self.temporizador.position = POS_TEMPORIZADOR
        self.escenario = EscenarioVN()
        self.escenario.dueno = self         # el escenario se esconde solo si esta interfaz deja de verse
        self._caso = None
        self._acusados = {}
        self._ultima_fila = None
        self._texto_completo = ""
        self._t_texto = 0.0
        self._hablante = None
        self._expresion = "neutral"
        self._reaccion = None              # (expresion, segundos restantes)
        self._t_contradiccion = None
        self._t_carta = None
        self._tablero = False
        self._elegido = None
        self._t_elegido = None
        self._construir_efectos()

    # -- Construcción (sustituye a las piezas de InterfazCaso que cambian de sitio) --

    def _construir_retrato(self):
        # Sin marco de retrato: el personaje es 3D. El retrato 2D queda como respaldo (si su modelo no carga).
        self.retrato = Entity(parent=self, model="quad", scale=(0.36, 0.36), position=(X_PERSONAJE_UI, 0.20, 0.01),
                              enabled=False)
        placa = panel_tinta(self, 0.32, 0.08, tono=estilo.COLOR_PANEL, position=(*POS_PLACA, -0.03))
        self.nombre = Text("", parent=placa, origin=(0, 0), position=(0, 0.014, -0.02), scale=escala_fuente(18),
                           font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self.rol = Text("", parent=placa, origin=(0, 0), position=(0, -0.018, -0.02), scale=escala_fuente(13),
                        color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._rol_base = escala_fuente(13)

    def _construir_dialogo(self):
        self.panel_dialogo = panel_tinta(self, ANCHO_VN, ALTO_DIALOGO_VN, tono=estilo.COLOR_PANEL,
                                         position=(*POS_DIALOGO_VN, 0))
        x0 = -ANCHO_VN / 2 + 0.03
        self.dialogo_titulo = Text("", parent=self.panel_dialogo, origin=(-0.5, 0.5), position=(x0, 0.075, -0.02),
                                   scale=escala_fuente(19), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_ACENTO))
        self._titulo_base = escala_fuente(19)
        self._dialogo_base = escala_fuente(19)
        self.dialogo = Text("", parent=self.panel_dialogo, origin=(-0.5, 0.5), position=(x0, 0.072, -0.02),
                            scale=self._dialogo_base, color=rgb(estilo.COLOR_TEXTO))
        self.mensaje = Text("", parent=self, origin=(-0.5, 0.5), position=(*POS_MENSAJE, -0.04), scale=escala_fuente(17),
                            font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self._mensaje_base = escala_fuente(17)
        self._siguiente = Text("»", parent=self.panel_dialogo, origin=(0, 0), position=(ANCHO_VN / 2 - 0.03, -0.065, -0.02),
                               scale=escala_fuente(14), color=rgb(estilo.COLOR_ACENTO), enabled=False)

    def _construir_opciones(self):
        self.panel_opciones = panel_tinta(self, ANCHO_VN, ALTO_OPCIONES_VN, tono=estilo.COLOR_FONDO,
                                          position=(*POS_OPCIONES_VN, 0))
        self._botones, self._etiquetas = [], []
        for _ in range(MAX_FILAS):
            boton = BotonSecundario("", al_clic=None, ancho=0.5, alto=0.05, parent=self.panel_opciones)
            boton.enabled = False
            etiqueta = Text("", parent=self.panel_opciones, origin=(-0.5, 0), scale=escala_fuente(16),
                            color=rgb(estilo.COLOR_BOTON_TEXTO))
            etiqueta.enabled = False
            self._botones.append(boton)
            self._etiquetas.append(etiqueta)
        self._etiqueta_base = escala_fuente(16)

    def _construir_efectos(self):
        # Franja oscura bajo los paneles: con la ventana estrecha la interfaz se encoge y debajo asomarían las piernas del
        # personaje (a 16:9 queda fuera de la pantalla).
        Entity(parent=self, model="quad", position=(0, -1.0, 0.05), scale=(6, 1.0), color=rgb(estilo.COLOR_FONDO))
        # Carta que vuela, rótulo «¡CONTRADICCIÓN!» y nombres del tablero (el fondo de alerta es el telón 3D del escenario).
        self.carta = Entity(parent=self, z=-0.2, enabled=False)
        panel_tinta(self.carta, 0.24, 0.15, tono=estilo.COLOR_TARJETA)
        self.carta_txt = Text("", parent=self.carta, origin=(0, 0), z=-0.02, scale=escala_fuente(15),
                              font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self.rotulo = Text("¡CONTRADICCIÓN!", parent=self, origin=(0, 0), position=(0.07, 0.18, -0.25),
                           scale=escala_fuente(46), font=tipografia.FUENTE_TITULO, color=rgb(ROJO), enabled=False)
        self.nombres_tablero = [Text("", parent=self, origin=(0, 0), scale=escala_fuente(15), font=tipografia.FUENTE_TITULO,
                                     color=rgb(estilo.COLOR_TEXTO), enabled=False) for _ in range(4)]
        self.titulo_tablero = Text("Sospechosos", parent=self, origin=(0, 0), position=(-0.55, 0.415, -0.02),
                                   scale=escala_fuente(20), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_ACENTO),
                                   enabled=False)

    # -- API de InterfazCaso con la vista nueva --

    def fijar_caso(self, caso):
        super().fijar_caso(caso)
        self._caso = caso
        self._acusados = calc.acusados_de(getattr(caso, "datos", None))
        self.escenario.fijar_caso(getattr(caso, "id", ""), getattr(caso, "personajes", {}) or {})

    def mostrar_hablante(self, nombre, rol, retrato_json, expresion):
        self.nombre.text = nombre
        self._ajustar(self.rol, f"{rol}  ·  {expresion}" if rol else str(expresion), 0.30, self._rol_base, 0.7, 1)
        self._hablante = self._personaje_por_nombre(nombre) if retrato_json is not None else None
        self._expresion = expresion
        visible_3d = self.escenario.mostrar(self._hablante, retrato_json)
        # Respaldo: el retrato 2D si el modelo 3D no está disponible.
        if retrato_json is not None and not visible_3d:
            self.retrato.enabled = True
            self.retrato.texture = self._textura(retrato_json, expresion)
        else:
            self.retrato.enabled = False

    def _personaje_por_nombre(self, nombre):
        for pid, pj in (getattr(self._caso, "personajes", {}) or {}).items():
            if pj.get("nombre") == nombre:
                return pid
        return None

    def mostrar_texto(self, titulo, texto):
        lineas_titulo = 0
        if titulo:
            plan = diseno_adaptable.ajustar_texto(self.dialogo_titulo, ANCHO_VN - 0.06, escala_base=self._titulo_base,
                                                  escala_min=0.75, max_lineas=2, cadena=titulo)
            if plan is None:
                self.dialogo_titulo.text = titulo
            lineas_titulo = max(1, len(plan["lineas"])) if plan is not None else 1
        else:
            self.dialogo_titulo.text = ""
        self.dialogo.y = 0.072 - lineas_titulo * 0.034
        self._ajustar(self.dialogo, texto, ANCHO_VN - 0.07, self._dialogo_base, 0.72, 4 - lineas_titulo if titulo else 5)
        # Letra a letra: se guarda el texto ya partido en líneas y se va mostrando.
        self._texto_completo = self.dialogo.text
        self._t_texto = 0.0
        if not (bv.reducir_movimiento()):
            self.dialogo.text = ""
        self._siguiente.enabled = False

    def mostrar_filas(self, filas):
        self._filas_texto = list(filas)
        cajas = calc.disposicion_opciones(len(filas), ALTO_OPCIONES_VN, ANCHO_VN)
        for i in range(MAX_FILAS):
            boton, etiqueta = self._botones[i], self._etiquetas[i]
            if i >= len(filas):
                boton.enabled = etiqueta.enabled = False
                continue
            fila = filas[i]
            x, y, ancho, alto = cajas[i]
            boton.enabled = etiqueta.enabled = True
            boton.position = (x, y, 0)
            boton.scale = (ancho, alto - 0.008)
            boton.base_scale = (boton.scale_x, boton.scale_y)
            boton.fijar_habilitado(fila.habilitada)
            boton.accion = (lambda f=fila: self._acciones["fila"](f))
            etiqueta.position = (x - ancho / 2 + 0.018, y, -0.02)
            cadena = mdc.etiqueta_opcion(i, fila.texto) if fila.tipo != "salir" else fila.texto
            if not fila.habilitada and fila.motivo:
                cadena += f"   [{fila.motivo}]"
            self._ajustar(etiqueta, cadena, ancho - 0.04, self._etiqueta_base, 0.7, 2)
            etiqueta.color = rgb(estilo.COLOR_BOTON_TEXTO if fila.habilitada else estilo.COLOR_TEXTO_TENUE)
        self._vigilar(self._actualizar_tablero, filas)

    def mostrar_mensaje(self, texto, bueno=False):
        self._ajustar(self.mensaje, texto or "", ANCHO_MENSAJE, self._mensaje_base, 0.75, 3)
        self.mensaje.color = rgb((120, 240, 160) if bueno else (255, 120, 130))
        self._mensaje_t = 3.5 if texto else 0.0
        fila = self._ultima_fila
        if fila is not None and getattr(fila, "tipo", None) == "prueba" and texto:
            self._ultima_fila = None
            self._vigilar(self._reaccionar_prueba, bool(bueno), fila)

    # -- Acciones: la escena avisa de cada fila elegida (teclado o ratón) ANTES de ejecutarla --

    def al_elegir_fila(self, fila):
        self._ultima_fila = fila
        if getattr(fila, "tipo", None) == "opcion" and fila.clave in self._acusados and self._tablero:
            self._vigilar(self._elegir_acusado, self._acusados[fila.clave])

    # -- Reacciones --

    def _reaccionar_prueba(self, correcta, fila):
        reducir = bv.reducir_movimiento()
        self._reaccion = (calc.reaccion_a_prueba(correcta, self._expresion),
                          calc.DUR_CONTRADICCION if correcta else calc.DUR_REACCION)
        if correcta:
            self._t_contradiccion = 0.0
            self.carta_txt.text = "\n".join(_partir(fila.texto, 20))
            self._t_carta = 0.0 if not reducir else None
            self.rotulo.enabled = True
            _sonar("mision_exito", 0.7, 0.8)
        else:
            _sonar("mision_fallo", 0.4, 1.2)

    def _elegir_acusado(self, pid):
        self._elegido = pid
        self._t_elegido = 0.0

    def _actualizar_tablero(self, filas):
        es_tablero = calc.es_acusacion([f.clave for f in filas if f.tipo == "opcion"], self._acusados)
        if es_tablero and not self._tablero:
            self._tablero = True
            ids = []
            for f in filas:
                pid = self._acusados.get(f.clave)
                if pid and pid not in ids:
                    ids.append(pid)
            self._ids_tablero = ids
            self.escenario.tablero(ids)
            xs = calc.posiciones_tablero(len(ids), X_TABLERO_UI[1] - X_TABLERO_UI[0])
            centro = (X_TABLERO_UI[0] + X_TABLERO_UI[1]) / 2
            personajes = getattr(self._caso, "personajes", {}) or {}
            for i, etiqueta in enumerate(self.nombres_tablero):
                etiqueta.enabled = i < len(ids)
                if i < len(ids):
                    etiqueta.text = personajes.get(ids[i], {}).get("nombre", ids[i])
                    etiqueta.position = (centro + xs[i], Y_TABLERO_UI + 0.045, -0.03)
            self.titulo_tablero.enabled = True
        elif not es_tablero and self._tablero and self._t_elegido is None:
            self._cerrar_tablero()

    def _cerrar_tablero(self):
        self._tablero = False
        self._elegido = None
        self._t_elegido = None
        for etiqueta in self.nombres_tablero:
            etiqueta.enabled = False
        self.titulo_tablero.enabled = False
        self.escenario.tablero(None)
        self.escenario.mostrar(self._hablante, True)

    # -- Frame --

    def avanzar(self, dt):
        super().avanzar(dt)
        self._vigilar(self._avanzar_vn, dt)

    def _avanzar_vn(self, dt):
        reducir = bv.reducir_movimiento()
        # Texto letra a letra.
        total = len(self._texto_completo)
        self._t_texto += dt
        n = calc.letras_visibles(self._t_texto, total, reducir=reducir)
        if self.dialogo.text != self._texto_completo[:n]:
            self.dialogo.text = self._texto_completo[:n]
        hablando = n < total
        self._siguiente.enabled = not hablando and total > 0 and int(self._t_texto * 2) % 2 == 0
        apertura = calc.apertura_texto(self._texto_completo, n) if hablando else None
        # Expresión: la del nodo o la reacción a una prueba (durante unos segundos).
        expresion = self._expresion
        if self._reaccion is not None:
            nombre, resto = self._reaccion
            resto -= dt
            self._reaccion = (nombre, resto) if resto > 0 else None
            expresion = nombre
        zoom = 0.0
        if self._t_contradiccion is not None:
            self._t_contradiccion += dt
            zoom = calc.zoom_contradiccion(self._t_contradiccion, reducir=reducir)
            self.escenario.fijar_alerta(calc.alerta(self._t_contradiccion, reducir=reducir))
            escala = 1.0 if reducir else 1.0 + 0.25 * max(0.0, 1.0 - self._t_contradiccion / 0.25)
            self.rotulo.scale = escala_fuente(46) * escala
            if self._t_contradiccion >= calc.DUR_CONTRADICCION:
                self._t_contradiccion = None
                self.rotulo.enabled = False
                self.escenario.fijar_alerta(0.0)
        if self._t_carta is not None:
            self._t_carta += dt
            k = calc.suave(min(1.0, self._t_carta / 0.35))
            self.carta.enabled = self._t_carta < 1.4
            self.carta.position = (0.665 + (0.08 - 0.665) * k, 0.0 + 0.02 * k, -0.2)
            self.carta.rotation_z = 25 * (1 - k) - 6 * k
            if self._t_carta >= 1.4:
                self._t_carta = None
                self.carta.enabled = False
        if self._t_elegido is not None:
            self._t_elegido += dt
            if self._t_elegido > 1.8:
                self._cerrar_tablero()
        self.escenario.avanzar(dt, expresion, hablando and not self._tablero, apertura, zoom,
                               self._elegido, self._t_elegido or 0.0, reducir)

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if getattr(self, "_vn_roto", False):
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("interrogatorio_vn", error)
            self._vn_roto = True
            try:
                self.escenario.apagar()
                self.rotulo.enabled = self.carta.enabled = False
                self.dialogo.text = self._texto_completo
            except Exception:            # noqa: BLE001
                pass
            return None

    # Los modelos 3D cuelgan de la CÁMARA (no de esta interfaz), así que esconder la interfaz no los esconde: sin esto
    # se quedaban delante de la cámara en todo el juego al salir de la fiscalía (tapando el mundo y los minijuegos).
    def on_disable(self):
        try:
            self.escenario.esconder()
        except Exception:                # noqa: BLE001  (durante __init__ aún no hay escenario)
            pass

    def on_destroy(self):
        try:
            self.escenario.apagar()
        except Exception:                # noqa: BLE001
            pass


def _partir(texto, ancho):
    palabras, lineas, actual = str(texto).split(), [], ""
    for palabra in palabras:
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas[:3]


def _sonar(nombre, volumen=1.0, pitch=1.0):
    try:
        from frontend import audio
        audio.obtener().efecto(nombre, volumen=volumen, pitch=pitch)
    except Exception:                    # noqa: BLE001
        pass


class EscenarioVN:
    """Los modelos 3D del interrogatorio, colgados de la cámara: el que habla en plano de pecho, el resto escondido.
    Cada personaje se crea UNA vez (al hablar por primera vez) y se reutiliza (también en el tablero de sospechosos)."""

    def __init__(self):
        self.raiz = Entity(parent=camera)
        self.fondo = Entity(parent=self.raiz, model="quad", z=3.0, scale=(14, 8), color=color.rgba32(8, 10, 22, ALFA_FONDO))
        # El telón se pinta DESPUÉS del mundo y sin prueba de profundidad (tapa los retratos del decorado aunque estén
        # más cerca que él); los personajes se pintan después del telón (ORDEN_PERSONAJES).
        self.fondo.setBin("fixed", ORDEN_FONDO)
        self.fondo.setDepthTest(False)
        self.fondo.setDepthWrite(False)
        self.caso_id = ""
        self.personajes = {}
        self.actores = {}             # pid -> PersonajeNPC (o None si no carga)
        self.rostros = {}
        self.mapeo = calc.cargar_mapeo()
        self.actual = None
        self.en_tablero = None
        self._t = 0.0
        self._perfil = {}
        self._desde = {}
        self._k = {}
        self.apagado = False
        self.dueno = None             # la InterfazVN: si deja de verse, el escenario se esconde (red de seguridad)
        self.raiz.update = self._seguir_al_dueno
        self.raiz.enabled = False

    def _seguir_al_dueno(self):
        """Cada frame mientras se ve: si la interfaz que lo usa ya no se ve (desactivada ella o un padre, o destruida),
        se esconde. Así los personajes nunca se quedan pegados a la cámara fuera del interrogatorio."""
        if self.dueno is not None and not _se_ve(self.dueno):
            self.esconder()

    def esconder(self):
        """Esconde los modelos (sin apagar el escenario: la próxima vez que hable alguien vuelven a salir)."""
        self.raiz.enabled = False

    def fijar_caso(self, caso_id, personajes):
        self.caso_id = caso_id
        self.personajes = personajes

    # -- Creación de un personaje --

    def _actor(self, pid):
        if pid in self.actores:
            return self.actores[pid]
        npc = None
        retrato = (self.personajes.get(pid) or {}).get("retrato")
        try:
            npc = self._crear(pid, retrato)
        except Exception as error:      # noqa: BLE001  ese personaje sale con su retrato 2D
            bv.avisar_una_vez(f"interrogatorio_modelo_{pid}", error)
        self.actores[pid] = npc
        return npc

    def _crear(self, pid, retrato):
        from frontend import npc_calculos as nc
        from frontend import npc_nuevos_modelo as nnm
        from frontend import rostro_expresivo
        from frontend.npc_modelo import PersonajeNPC
        archivo, rol = calc.modelo_para(self.caso_id, pid, retrato, self.mapeo)
        aspecto = calc.aspecto_de(retrato)
        semilla = calc.semilla_de(pid)
        plan = nc.plan_npc(semilla, semilla, aspecto, modelo=(archivo, rol))
        if plan.get("nuevo") and not nnm.disponible(plan):
            archivo, rol = "periodista.glb", "periodista"
            plan = nc.plan_npc(semilla, semilla, aspecto, modelo=(archivo, rol))
        camiseta, pantalon = calc.colores_ropa(retrato, plan["archivo"])
        plan["colores"]["camiseta"] = camiseta
        plan["colores"]["pantalon"] = pantalon
        plan["mochila"] = None
        plan["escala"] = 1.0
        if plan["archivo"] == "ciudadano.glb":
            plan["camiseta_nueva"] = "manga"
        nombre = (self.personajes.get(pid) or {}).get("nombre", pid)
        npc = PersonajeNPC(nombre, plan, aspecto, calc.rasgos_de(retrato), parent=self.raiz)
        npc.automatico = False
        for parte in ("etiqueta", "aro", "sombra"):
            pieza = getattr(npc, parte, None)
            if pieza is not None:
                pieza.enabled = False
        npc.fijar_rumbo(180)          # de cara a la cámara
        npc.setBin("fixed", ORDEN_PERSONAJES)
        self.rostros[pid] = rostro_expresivo.instalar(npc, semilla)
        npc.enabled = False
        self._perfil[pid] = calc.perfil_de("neutral")
        self._desde[pid] = calc.perfil_de("neutral")
        self._k[pid] = 1.0
        return npc

    # -- Qué se ve --

    def mostrar(self, pid, retrato_json):
        """Pone al personaje `pid` en plano de pecho (y esconde al resto). Devuelve True si se ve en 3D."""
        if self.apagado or pid is None or retrato_json is None:
            self.actual = None
            self._esconder_todos()
            self.raiz.enabled = not self.apagado and self.en_tablero is not None
            return False
        npc = self._actor(pid)
        self.actual = pid if npc is not None else None
        if self.en_tablero is None:
            self._esconder_todos()
            if npc is not None:
                npc.enabled = True
        self.raiz.enabled = npc is not None or self.en_tablero is not None
        return npc is not None

    def _esconder_todos(self):
        for npc in self.actores.values():
            if npc is not None:
                npc.enabled = False

    def tablero(self, ids):
        """Tablero de sospechosos: los acusados en fila, más lejos (se ven pequeños). None lo cierra."""
        self.en_tablero = list(ids) if ids else None
        self._esconder_todos()
        if self.en_tablero is None:
            return
        for pid in self.en_tablero:
            npc = self._actor(pid)
            if npc is not None:
                npc.enabled = True
        self.raiz.enabled = True

    # -- Frame --

    def avanzar(self, dt, expresion, hablando, apertura, zoom, elegido, t_elegido, reducir):
        if self.apagado or not self.raiz.enabled:
            return
        self._t += dt
        aspecto = window.aspect_ratio or 16 / 9
        gestor = diseno_adaptable.obtener()
        factor = getattr(gestor, "factor", 1.0) if gestor is not None else 1.0
        fov = camera.fov or 65
        if self.en_tablero is not None:
            self._colocar_tablero(aspecto, factor, fov, elegido, t_elegido, reducir)
            for pid in self.en_tablero:
                self._animar(pid, dt, "serio" if pid != elegido else "nervioso", False, None, reducir)
            return
        pid = self.actual
        npc = self.actores.get(pid) if pid else None
        if npc is None:
            return
        # (con la ventana estrecha el FOV horizontal fijo ya lo encoge lo mismo que la interfaz: no se escala otra vez)
        distancia = DISTANCIA - ACERCAMIENTO * zoom
        x, y = calc.encuadre(X_PERSONAJE_UI * factor, Y_CORONILLA_UI * factor + 0.04 * zoom, distancia, fov, aspecto,
                             _coronilla(npc))
        perfil = self._animar(pid, dt, expresion, hablando, apertura, reducir)
        x += 0.0 if reducir else calc.balanceo(self._t, perfil["balanceo"])
        npc.position = (x, y, distancia)
        npc.cuerpo.rotation_y = 180 + (0.0 if reducir else calc.braceo(self._t, perfil["braceo"], hablando))

    def _colocar_tablero(self, aspecto, factor, fov, elegido, t_elegido, reducir):
        ids = self.en_tablero
        xs = calc.posiciones_tablero(len(ids), X_TABLERO_UI[1] - X_TABLERO_UI[0])
        centro = (X_TABLERO_UI[0] + X_TABLERO_UI[1]) / 2
        for i, pid in enumerate(ids):
            npc = self.actores.get(pid)
            if npc is None:
                continue
            distancia = DISTANCIA_TABLERO
            if pid == elegido and not reducir:
                distancia -= 1.2 * calc.suave(min(1.0, t_elegido / 0.6))
            x, y = calc.encuadre((centro + xs[i]) * factor, Y_TABLERO_UI * factor, distancia, fov, aspecto, _coronilla(npc))
            npc.position = (x, y, distancia)
            npc.cuerpo.rotation_y = 180

    def _animar(self, pid, dt, expresion, hablando, apertura, reducir):
        """Mezcla el perfil del personaje hacia `expresion` y lo aplica a postura, cara y clip. Devuelve el perfil."""
        npc = self.actores.get(pid)
        objetivo = calc.perfil_de(expresion)
        if objetivo != self._perfil.get(pid):
            actual = calc.mezclar_perfiles(self._desde[pid], self._perfil[pid], calc.suave(self._k[pid]))
            self._desde[pid], self._perfil[pid], self._k[pid] = actual, objetivo, 0.0
        self._k[pid] = calc.avance_mezcla(self._k[pid], dt, reducir=reducir)
        perfil = calc.mezclar_perfiles(self._desde[pid], self._perfil[pid], calc.suave(self._k[pid]))
        if npc is None:
            return perfil
        if getattr(npc, "_postura_vn", None) != perfil["postura"]:
            npc._postura_vn = perfil["postura"]
            npc.aplicar_postura(perfil["postura"])
        rostro = self.rostros.get(pid)
        if rostro is not None:
            rostro.perfil = perfil
            rostro.apertura_forzada = apertura
        from frontend import modelo_calculos as mc
        npc._poner_clip(mc.HABLAR if hablando else mc.IDLE, 1.0)
        return perfil

    def fijar_alerta(self, alfa):
        """Telón de fondo: azul oscuro normal, rojo de alerta con `alfa` (0..1) en la contradicción."""
        a = max(0.0, min(1.0, alfa))
        base, rojo = (8, 10, 22), ROJO
        tono = tuple(int(base[i] + (rojo[i] * 0.55 - base[i]) * a) for i in range(3))
        self.fondo.color = color.rgba32(*tono, int(ALFA_FONDO + (250 - ALFA_FONDO) * a))

    def apagar(self):
        self.apagado = True
        self.raiz.enabled = False


def _se_ve(entidad):
    """True si la entidad y todos sus padres están activos (y no se ha destruido)."""
    try:
        e, pasos = entidad, 0
        while e is not None and pasos < 64:
            if not getattr(e, "enabled", True):
                return False
            e, pasos = getattr(e, "parent", None), pasos + 1
        return True
    except Exception:                    # noqa: BLE001  destruida a medias: no se ve
        return False


def _coronilla(npc):
    try:
        from frontend import npc_postura
        return npc_postura.y_ancla_cabeza(npc) - npc_postura.MARGEN_ANCLA_CABEZA
    except Exception:                    # noqa: BLE001
        return 1.84

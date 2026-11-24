# Escena de la Fiscalía (Ursina): el interior 3D donde se juega un caso v2 de punta a punta, como un capítulo de Detroit.
# Es DUEÑA de la sesión del caso (backend/logica/casos_v2.SesionCasoV2, Protocol casos_v2_tipos.SesionCaso), de la cámara,
# de los personajes 3D, de los fundidos y del orden del flujo; la interfaz (frontend/fiscalia/hud_caso.HudCaso, contrato
# frontend/fiscalia/contrato_ui.md) dibuja y avisa por callbacks.
#
#   despacho (oficina) -> laboratorio (opcional: dos terminales; E junto a uno = sentarse, entrar al servidor y jugar el
#   parkour de siempre; al volver, a la misma silla) -> sala de interrogatorio (Inés, corte, Marcos) -> acusación en el
#   despacho -> final + diagrama -> «Salir de la Fiscalía»: al mundo, delante de la puerta, y la misión se revisa.
#   Esc: pausa del caso (de la interfaz) con «Abandonar caso» -> final de archivo -> salida. No hay otra salida a mitad.
#
# La escena no se congela: los personajes respiran, parpadean y gesticulan, la cámara cambia de plano (general, pecho,
# primer plano, contraplano; frontend/fiscalia/camaras_calculos.py) con transiciones cortas, y «respira» en reposo.
# Reducir movimiento: cortes secos, sin deriva.
#
# RESPALDO: si algo falla al construirse o en un frame, se cae sola a la sala digital de hoy (conexion.ir_a_mundo_digital)
# o, si tampoco se puede, al mundo delante de la puerta. Nunca deja al jugador encerrado ni la misión atascada.

import math
import sys
import traceback

from ursina import Entity, Text, camera, color, held_keys, mouse, scene, time, window
from ursina.lights import AmbientLight, DirectionalLight

from backend.logica import fiscalia_bandera as fb
from frontend import banderas_visuales as bv
from frontend.componentes import destruir_arbol, escala_fuente, rgb
from frontend.fiscalia import camaras_calculos as cc
from frontend.fiscalia import flujo_calculos as fc
from frontend.fiscalia import salas_calculos as sc
from frontend.fiscalia.camaras import CamaraFiscalia, a_ui, toma_viva
from frontend.piezas import encender_luz

FISCALIA = "fiscalia"
VELOCIDAD_LAB = 2.3              # m/s caminando por el laboratorio
COLOR_FONDO = (14, 16, 24)


# ======================================================================================================================
# Interfaz básica de respaldo (contrato_ui.md §6): mismos métodos que HudCaso. Se usa si hud_caso.py no está o falla.
# ======================================================================================================================

class HudBasico(Entity):

    def __init__(self, caso, *, al_elegir, al_continuar, al_abandonar, parent=None):
        super().__init__(parent=parent or camera.ui)
        self._caso = caso
        self._al_elegir, self._al_continuar, self._al_abandonar = al_elegir, al_continuar, al_abandonar
        self._vista = None
        self._texto, self._t = "", 0.0
        self._final = None
        self._confirmar = None
        self.en_pausa = False
        self._solidez = Text("", parent=self, origin=(0, 0), position=(0, 0.45), scale=escala_fuente(18),
                             color=rgb((255, 220, 60)))
        self._nombre = Text("", parent=self, origin=(-0.5, 0), position=(-0.6, -0.30), scale=escala_fuente(19),
                            color=rgb((255, 220, 60)))
        self._linea = Text("", parent=self, origin=(-0.5, 0.5), position=(-0.6, -0.34), scale=escala_fuente(18),
                           color=rgb((240, 240, 245)), wordwrap=62)
        self._opciones = Text("", parent=self, origin=(-0.5, 0.5), position=(0.25, 0.12), scale=escala_fuente(18),
                              color=rgb((240, 240, 245)))
        self._reloj = Text("", parent=self, origin=(0, 0), position=(0.6, 0.30), scale=escala_fuente(22),
                           color=rgb((255, 120, 120)))
        self._aviso = Text("", parent=self, origin=(0, 0), position=(0, -0.22), scale=escala_fuente(17),
                           color=rgb((140, 230, 255)))
        self._centro = Text("", parent=self, origin=(0, 0), position=(0, 0.05), scale=escala_fuente(20),
                            color=rgb((240, 240, 245)), wordwrap=60, z=-0.1)
        self._fondo = Entity(parent=self, model="quad", scale=(4, 0.32), position=(0, -0.38, 0.05),
                             color=color.rgba32(10, 12, 20, 200))
        self._fondo_centro = Entity(parent=self, model="quad", scale=(1.5, 0.7), position=(0, 0.05, 0.0),
                                    color=color.rgba32(10, 12, 20, 230), enabled=False)

    # -- presentar --

    def presentar(self, vista, *, ancla=None):
        nuevo = self._vista is None or self._vista.id != vista.id
        self._vista = vista
        pj = (getattr(self._caso, "personajes", {}) or {}).get(vista.personaje) or {}
        self._nombre.text = pj.get("nombre", "") if vista.personaje else ""
        if nuevo:
            self._texto, self._t = vista.texto, 0.0
            self._linea.text = "" if not bv.reducir_movimiento() else vista.texto
        self._pintar_opciones()

    def _pintar_opciones(self):
        v = self._vista
        if v is None or v.tipo not in ("rueda", "acusacion"):
            self._opciones.text = ""
            return
        filas = []
        for o in v.opciones:
            marca = "" if o.estado == "libre" else f"  {o.pista or '[bloqueada]'}"
            filas.append(f"{o.posicion + 1}. {o.etiqueta}{marca}")
        self._opciones.text = "\n".join(filas)

    def fijar_ancla(self, ancla):
        pass

    def fijar_reloj(self, restante, total):
        self._reloj.text = "" if restante is None else f"{max(0, int(math.ceil(restante)))} s"

    def fijar_solidez(self, valor):
        self._solidez.text = f"Solidez del caso {int(valor)} %"

    def aplicar_cambios(self, cambios, solidez):
        self.fijar_solidez(solidez)
        nuevas = [c.nombre for c in cambios or () if c.tipo == "evidencia" and c.nombre]
        if nuevas:
            self._aviso.text = "Prueba nueva: " + ", ".join(nuevas)

    def linea_completa(self):
        return len(self._linea.text) >= len(self._texto)

    def completar_linea(self):
        self._linea.text = self._texto

    def decir_jugador(self, texto):
        self._aviso.text = texto if fc.es_acotacion(texto) else f"«{texto}»"

    def mostrar_laboratorio(self, parkours, *, cerca=None, puerta=False):
        partes = [f"{p.nombre}: {'hecho' if p.completado else 'sin revisar'}" for p in parkours]
        extra = "  ·  E — Sentarse" if cerca else ("  ·  E — Pasar a la sala" if puerta else "")
        self._aviso.text = "   ".join(partes) + extra

    def ocultar_laboratorio(self):
        self._aviso.text = ""

    def confirmar(self, titulo, texto, *, si, no, al_responder, aviso=""):
        self._confirmar = al_responder
        self._fondo_centro.enabled = True
        extra = f"\n{aviso}" if aviso else ""
        self._centro.text = f"{titulo}\n{texto}{extra}\n\nEnter: {si}    Esc: {no}"

    def mostrar_final(self, vista, diagrama, *, al_cerrar):
        self._final = al_cerrar
        self._fondo_centro.enabled = True
        pct = getattr(diagrama, "porcentaje", 0)
        self._centro.text = f"{vista.titulo}\n\n{vista.texto}\n\nRecorrido: {pct} %\n\nEnter: Salir de la Fiscalía"
        self._opciones.text = self._linea.text = self._nombre.text = ""

    def abrir_pausa(self):
        self.en_pausa = True
        self._fondo_centro.enabled = True
        self._centro.text = "Pausa del caso\n\nEsc: seguir    Q: abandonar caso"

    def cerrar_pausa(self):
        self.en_pausa = False
        self._fondo_centro.enabled = self._final is not None or self._confirmar is not None
        if not self._fondo_centro.enabled:
            self._centro.text = ""

    @property
    def modal_abierto(self):
        return self.en_pausa or self._confirmar is not None or self._final is not None

    def entrada(self, key):
        if self._final is not None:
            if key in ("enter", "space"):
                cb, self._final = self._final, None
                cb()
            return True
        if self._confirmar is not None:
            if key in ("enter", "escape"):
                cb, self._confirmar = self._confirmar, None
                self._fondo_centro.enabled = False
                self._centro.text = ""
                cb(key == "enter")
            return True
        if self.en_pausa:
            if key == "escape":
                self.cerrar_pausa()
            elif key == "q":
                self.cerrar_pausa()
                self._al_abandonar()
            return True
        if key == "escape":
            self.abrir_pausa()
            return True
        v = self._vista
        if v is None:
            return False
        if v.tipo in ("rueda", "acusacion") and key in ("1", "2", "3", "4"):
            hueco = int(key) - 1
            o = next((o for o in v.opciones if o.posicion == hueco), None)
            if o is not None and o.estado == "libre":
                self._al_elegir(o.id)
            return True
        if v.tipo == "dialogo" and key in ("space", "enter", "left mouse down"):
            if not self.linea_completa():
                self.completar_linea()
            else:
                self._al_continuar()
            return True
        return False

    def actualizar(self, dt):
        pass

    def update(self):
        if self._texto and not self.linea_completa():
            self._t += time.dt
            self._linea.text = self._texto[:int(self._t * 55)]

    def ocultar(self):
        self.visible = False

    def mostrar(self):
        self.visible = True

    def destruir(self):
        try:
            destruir_arbol(self)
        except Exception:               # noqa: BLE001
            pass


def crear_hud(caso, **callbacks):
    """HudCaso de la interfaz; si no está o falla al construirse, el básico de arriba (con aviso por stderr)."""
    try:
        from frontend.fiscalia.hud_caso import HudCaso
        return HudCaso(caso, **callbacks)
    except Exception as error:          # noqa: BLE001
        print(f"[fiscalia] HudCaso no disponible ({type(error).__name__}: {error}); se usa la interfaz básica.",
              file=sys.stderr)
        return HudBasico(caso, **callbacks)


# ======================================================================================================================
# La escena
# ======================================================================================================================

class EscenaFiscalia(Entity):      # contenedor de escena (como escenas/escena_base.Escena: nace desactivada)

    # conexion: ConexionFlujo (fundidos, parkour, sala digital). escena_mundo: EscenaMundo. sitio: SitioFiscalia.
    # gestor: GestorEscenas. fabrica_sesion(caso, game_state) -> SesionCaso.
    def __init__(self, gestor, conexion, escena_mundo, sitio, fabrica_sesion, glitch=None, **opciones):
        opciones.setdefault("parent", scene)
        opciones.pop("enabled", None)
        super().__init__(enabled=False, **opciones)
        self._gestor, self._conexion, self._mundo, self._sitio = gestor, conexion, escena_mundo, sitio
        self._fabrica_sesion = fabrica_sesion
        self.glitch = glitch
        self.camara = CamaraFiscalia()
        self.luz = DirectionalLight(parent=self, shadows=True, shadow_map_resolution=(1024, 1024))
        self.luz.look_at((-0.5, -1.4, 0.7))
        self.ambiente = AmbientLight(parent=self, color=color.rgba32(126, 124, 136, 255))
        self._luces(False)
        self._limpiar_estado()
        self._fondo_guardado = None
        self.respaldos = 0              # cuántas veces cayó al respaldo (lo lee el arnés)
        self.ultimo_error = None

    def _limpiar_estado(self):
        self.sesion = self.caso = self.hud = None
        self.caso_id = None
        self.salas = {}
        self.planos = {}
        self.actores = {}
        self.jugador = None
        self.protagonista = None
        self.vista = None
        self.sala = None
        self.modo = None                # «conversacion» | «laboratorio» | «terminal» | «final» | «saliendo»
        self.plano = None
        self._pendiente = None          # vista a presentar al terminar el fundido en curso
        self._agenda = []               # [(t, funcion)] pasos de una secuencia corta propia
        self._t = 0.0
        self._t_linea = 0.0
        self._lab = (None, False)
        self._nivel = None
        self._antes_parkour = None
        self._saliendo = False
        self._en_respaldo = False

    # -- Ciclo de vida --

    def al_entrar(self, flujo=None, caso_id=None, regreso=None, **datos):
        try:
            if regreso is None or self.sesion is None:
                self._sin_recompensa_global(False)
            self._preparar_entorno()
            if regreso is not None and self.sesion is not None:
                self._volver_del_parkour(regreso)
                return
            self._empezar(flujo or self._mundo.flujo, caso_id)
        except Exception as error:      # noqa: BLE001
            self._respaldo("al abrir", error)

    def al_salir(self):
        try:
            if self.hud is not None:
                self.hud.ocultar()
            self.camara.soltar()
            self._luces(False)
            if self._fondo_guardado is not None:
                window.color = self._fondo_guardado
                self._fondo_guardado = None
        except Exception as error:      # noqa: BLE001
            print(f"[fiscalia] al salir: {error}", file=sys.stderr)

    def _preparar_entorno(self):
        self.camara.tomar()
        self._luces(True)
        if self._fondo_guardado is None:
            self._fondo_guardado = window.color
        window.color = rgb(COLOR_FONDO)
        mouse.locked = False

    def _luces(self, si):
        encender_luz(self.luz, si)
        encender_luz(self.ambiente, si)

    # -- Montaje del caso --

    def _empezar(self, flujo, caso_id):
        from frontend.fiscalia import salas
        self._desmontar()
        gs = getattr(flujo, "game_state", None)
        catalogo = getattr(self, "catalogo", {}) or {}
        caso = catalogo.get(caso_id)
        if gs is None or caso is None:
            raise RuntimeError(f"no se puede abrir el caso {caso_id!r} (GameState: {gs is not None})")
        self.caso_id, self.caso = caso_id, caso
        self.jugador = flujo.jugador_activo()
        self.sesion = self._fabrica_sesion(caso, gs)
        parkours = tuple(self.sesion.parkours() or ())
        niveles = tuple(p.nivel for p in parkours) or ("sector_1", "sector_2")
        self.planos = sc.planos(niveles)
        fiscal = (getattr(caso, "personajes", {}) or {}).get("fiscal", {}) or {}
        self.salas = salas.construir(self, self.planos, fiscal.get("nombre", "Fiscal Rojas"),
                                     {p.nivel: p.nombre for p in parkours})
        for p in parkours:
            pant = self.salas[sc.LABORATORIO][1]["pantallas"].get(p.nivel)
            if pant is not None:
                pant.fijar(p.completado)
        self._crear_personajes(caso)
        self.hud = crear_hud(caso, al_elegir=self._al_elegir, al_continuar=self._al_continuar,
                             al_abandonar=self._al_abandonar)
        self.hud.fijar_solidez(self.sesion.solidez)
        vista = self.sesion.vista()
        # Entramos bajo el fundido con el nombre de la Fiscalía: la primera sala se monta ya, sin otro fundido.
        self._montar_sala(vista.escena or sc.OFICINA, vista)
        self.vista = None
        self._presentar_en_negro(vista)
        self.hud.ocultar()
        self._pendiente = vista            # la interfaz entra al terminar ese fundido (_tras_fundido)
        try:
            from frontend import rendimiento
            rendimiento.precargar(self)        # salas y personajes a la GPU bajo el fundido: sin tirones luego
        except Exception:               # noqa: BLE001
            pass

    def _crear_personajes(self, caso):
        from frontend.fiscalia.personajes import Protagonista, crear_actor_caso
        self.protagonista = Protagonista(self.jugador, self)
        for pid, datos in (getattr(caso, "personajes", {}) or {}).items():
            actor = crear_actor_caso(pid, datos, caso.id, self)
            if actor is not None:
                actor.esconder()
                self.actores[pid] = actor

    def _desmontar(self):
        if self.hud is not None:
            try:
                self.hud.destruir()
            except Exception:           # noqa: BLE001
                pass
        for actor in list(self.actores.values()):
            try:
                actor.destruir()
            except Exception:           # noqa: BLE001
                pass
        if self.protagonista is not None:
            try:
                self.protagonista.destruir()
            except Exception:           # noqa: BLE001
                pass
        for raiz, _ in list(self.salas.values()):
            destruir_arbol(raiz)
        en_respaldo = self._en_respaldo
        self._limpiar_estado()
        self._en_respaldo = en_respaldo

    # -- Salas y personajes en su sitio --

    def _montar_sala(self, escena, vista=None):
        """Activa la sala `escena`, sienta (o pone de pie) a cada uno en su sitio y corta la cámara a su plano."""
        self.sala = escena
        for nombre, (raiz, _) in self.salas.items():
            raiz.enabled = nombre == escena
        plano = self.planos[escena]
        try:
            self.luz.update_bounds(self.salas[escena][0])
        except Exception:               # noqa: BLE001
            pass
        for actor in self.actores.values():
            actor.esconder()
        fiscal = self.actores.get("fiscal")
        if escena == sc.OFICINA:
            if fiscal is not None:
                fiscal.sentar(plano.asientos["hablante"])
            self.protagonista.sentar(plano.asientos["jugador"])
        elif escena == sc.SALA:
            ocupa = fc.ocupante(vista)
            actor = self.actores.get(ocupa)
            if actor is not None:
                actor.sentar(plano.asientos["hablante"])
            if fiscal is not None and "fiscal" in plano.de_pie:
                fiscal.de_pie(plano.de_pie["fiscal"])
            self.protagonista.sentar(plano.asientos["jugador"])
        else:
            if fiscal is not None:
                fiscal.de_pie(plano.de_pie["fiscal"])
            self.protagonista.de_pie(plano.entrada)
            self.protagonista.personaje.automatico = True
            self.protagonista.caminando = True
        self._ocupante = fc.ocupante(vista)

    def _cambiar_ocupante(self, vista):
        """Corte de la sala: sale el interrogado anterior y se sienta el nuevo."""
        plano = self.planos[sc.SALA]
        for pid, actor in self.actores.items():
            if pid not in ("fiscal",):
                actor.esconder()
        actor = self.actores.get(fc.ocupante(vista))
        if actor is not None:
            actor.sentar(plano.asientos["hablante"])
        self._ocupante = fc.ocupante(vista)

    def _actor_que_habla(self, vista):
        if vista is None or vista.personaje is None:
            return None
        actor = self.actores.get(vista.personaje)
        return actor if actor is not None and actor.npc.enabled else None

    def _cabezas(self, vista):
        """(cabeza de quien habla, cabeza del jugador) para las tomas; quien habla en la sala sin estar sentado (el fiscal
        tras el vidrio) cuenta como el asiento de enfrente."""
        plano = self.planos[self.sala]
        jugador = self.protagonista.cabeza() if self.protagonista else plano.asientos["jugador"].cabeza()
        actor = self._actor_que_habla(vista)
        if actor is not None and (self.sala != sc.SALA or vista.personaje == self._ocupante):
            return actor.cabeza(), jugador
        if "hablante" in plano.asientos:
            ocupa = self.actores.get(self._ocupante) if self.sala == sc.SALA else self.actores.get("fiscal")
            return (ocupa.cabeza() if ocupa is not None else plano.asientos["hablante"].cabeza()), jugador
        return jugador, jugador

    # -- Presentar un nodo --

    def _presentar(self, vista, cortar=False, tras_eleccion=False):
        anterior = self.vista
        self.vista = vista
        self._t_linea = 0.0
        if vista.tipo == "laboratorio":
            self._entrar_laboratorio(vista, cortar)
            return
        self.modo = "conversacion"
        primero = cortar or anterior is None or anterior.escena != vista.escena
        self.plano = cc.elegir_plano(vista.tipo, vista.plano, primero and vista.tipo == "dialogo", tras_eleccion,
                                     self.plano)
        if vista.tipo in ("rueda", "acusacion") and vista.plano is None and primero:
            self.plano = "general"
        h, j = self._cabezas(vista)
        toma = cc.toma(self.plano, h, j, self._lateral()) if h != j else self._toma_sala()
        # fiscalia-visual: la cámara acompaña a la cara (la postura de la expresión llega después de elegir el plano)
        viva = toma_viva(self.plano, lambda: self._cabezas(vista), self._lateral()) if h != j else None
        if cortar:
            self.camara.cortar(toma, seguir=viva)
        else:
            self.camara.ir_a(toma, seguir=viva)
        self.hud.presentar(vista, ancla=self._ancla())

    def _lateral(self):
        """Lado del plano general: sin salirse de la sala (la cámara no entra en una pared)."""
        plano = self.planos.get(self.sala)
        return 2.6 if plano is None else max(1.2, min(2.6, plano.ancho / 2 - 0.65))

    def _toma_sala(self):
        plano = self.planos[self.sala]
        return cc.toma_laboratorio(plano.origen, plano.ancho, plano.fondo)

    def _ancla(self):
        actor = self._actor_que_habla(self.vista)
        if actor is None or self.modo == "laboratorio":
            return None
        return a_ui(actor.cabeza())

    # -- Callbacks de la interfaz --

    def _ocupado(self):
        return self._pendiente is not None or self._saliendo or self.sesion is None or self.modo in (
            "terminal", "final", "saliendo")

    def _al_continuar(self):
        if self._ocupado() or self.vista is None or self.vista.tipo != "dialogo":
            return
        self._seguro(lambda: (self.sesion.continuar(), self._tras_decision(False)))

    def _al_elegir(self, id_opcion):
        if self._ocupado() or self.vista is None:
            return
        opcion = next((o for o in self.vista.opciones if o.id == id_opcion), None)
        if opcion is None:
            return

        def elegir():
            if opcion.dice:
                self.hud.decir_jugador(opcion.dice)
            self.sesion.elegir(id_opcion)
            self._tras_decision(True)
        self._seguro(elegir)

    def _al_abandonar(self):
        if self.sesion is None or self._saliendo or self.modo == "final":
            return
        self._seguro(lambda: (self.sesion.abandonar(), self._tras_decision(False)))

    def _seguro(self, accion):
        try:
            accion()
        except Exception as error:      # noqa: BLE001
            self._respaldo("acción del caso", error)

    def _tras_decision(self, tras_eleccion):
        self.hud.aplicar_cambios(self.sesion.tomar_cambios(), self.sesion.solidez)
        nueva = self.sesion.vista()
        paso = fc.transicion(self.vista, nueva)
        if paso == fc.FINAL:
            self._ir_al_final(nueva)
        elif paso == fc.FUNDIDO:
            self._fundido(fc.rotulo(nueva.escena, getattr(self.caso, "escenas", None)), nueva)
        elif paso == fc.CORTE:
            self._corte(nueva)
        else:
            self._presentar(nueva, tras_eleccion=tras_eleccion)

    def _fundido(self, rotulo, vista, escena=None):
        self.hud.ocultar()
        self._pendiente = vista
        escena = escena or vista.escena

        def en_negro():
            self._montar_sala(escena, vista)
            self.vista = None
            if vista.tipo != "final":
                self._presentar_en_negro(vista)

        self._conexion._con_transicion_lugar(lambda: self._seguro(en_negro), rotulo)

    def _presentar_en_negro(self, vista):
        """Bajo el fundido: corta la cámara a su plano (el hud se presenta al terminar el fundido)."""
        hud, self.hud = self.hud, _HudMudo()
        try:
            self._presentar(vista, cortar=True)
        finally:
            self.hud = hud

    def _corte(self, vista):
        self.hud.ocultar()
        self._pendiente = vista

        def en_negro():
            self._cambiar_ocupante(vista)
            self._presentar_en_negro(vista)

        self._conexion._con_transicion(lambda: self._seguro(en_negro))

    def _tras_fundido(self):
        vista, self._pendiente = self._pendiente, None
        if vista is None or self.hud is None:
            return
        if vista.tipo == "final":
            self._mostrar_final(vista)
            return
        self.hud.mostrar()
        self.vista = vista
        if vista.tipo == "laboratorio":
            self.hud.presentar(vista, ancla=None)
            self._refrescar_laboratorio(forzar=True)
        else:
            self.hud.presentar(vista, ancla=self._ancla())

    # -- Final y salida --

    def _ir_al_final(self, vista):
        self.modo = "final"
        if self.sala != sc.OFICINA:
            self._fundido(fc.rotulo(sc.OFICINA, getattr(self.caso, "escenas", None)), vista, escena=sc.OFICINA)
            return
        self._mostrar_final(vista)

    def _mostrar_final(self, vista):
        self.modo = "final"
        self.vista = vista
        fiscal = self.actores.get("fiscal")
        if fiscal is not None:
            fiscal.expresion = vista.expresion or "serio"
        h, j = self._cabezas(vista)
        self.camara.ir_a(cc.toma("general", h, j, self._lateral()))
        self.hud.mostrar()
        try:
            from frontend import audio
            audio.obtener().efecto("mision_exito" if vista.resultado == "exito" else "mision_fallo", volumen=0.6)
        except Exception:               # noqa: BLE001
            pass
        self.hud.mostrar_final(vista, self.sesion.diagrama(), al_cerrar=self._salir_al_mundo)

    def _salir_al_mundo(self):
        if self._saliendo or self.sesion is None:
            return
        self._saliendo = True
        self.modo = "saliendo"
        if self.hud is not None:
            self.hud.ocultar()
        titulo = getattr(self.vista, "titulo", "") if self.vista is not None else ""
        self._conexion._con_transicion(lambda: self.volver_al_mundo(f"Caso cerrado: {titulo}" if titulo else None))

    def volver_al_mundo(self, aviso=None):
        """Al mundo, delante de la puerta de la Fiscalía, con la misión revisada. Nunca lanza."""
        flujo = self._mundo.flujo
        try:
            self._desmontar()
        except Exception as error:      # noqa: BLE001
            print(f"[fiscalia] desmontar: {error}", file=sys.stderr)
        try:
            if flujo is not None:
                jugador = flujo.jugador_activo()
                jugador.x, jugador.z = self._sitio.fuera
                revisar = getattr(flujo, "revisar_misiones_digitales", None)
                if getattr(flujo, "game_state", None) is not None and revisar is not None:
                    revisar()
        except Exception as error:      # noqa: BLE001
            print(f"[fiscalia] revisar misiones: {error}", file=sys.stderr)
        from frontend.flujo_constantes import MUNDO
        self._gestor.cambiar_a(MUNDO, flujo=flujo)
        try:
            jugador = flujo.jugador_activo()
            avatar = self._mundo.avatar_de(jugador)
            if avatar is not None:
                avatar.fijar_rumbo(self._sitio.rumbo_salida)
            cam = self._mundo.camara
            cam.yaw = self._sitio.rumbo_entrada          # desde la calle, mirando al jugador y a la fachada
            cam.colocar_ya()
        except Exception:               # noqa: BLE001
            pass
        if aviso:
            try:
                self._conexion._avisar_en_el_mundo(aviso)
            except Exception:           # noqa: BLE001
                pass

    # -- Laboratorio --

    def _entrar_laboratorio(self, vista, cortar):
        self.modo = "laboratorio"
        plano = self.planos[sc.LABORATORIO]
        p = self.protagonista.personaje
        toma = cc.toma_seguir((p.x, p.z), plano.origen, plano.fondo)
        if cortar:
            self.camara.cortar(toma)
        else:
            self.camara.ir_a(toma)
        self.hud.presentar(vista, ancla=None)
        self._lab = (None, None)
        self._refrescar_laboratorio(forzar=True)

    def _refrescar_laboratorio(self, forzar=False):
        if self.protagonista is None or self.sesion is None:
            return
        plano = self.planos[sc.LABORATORIO]
        p = self.protagonista.personaje
        cerca = sc.terminal_cerca(plano, p.x, p.z)
        puerta = sc.puerta_cerca(plano, p.x, p.z) and cerca is None
        if forzar or (cerca, puerta) != self._lab:
            self._lab = (cerca, puerta)
            self.hud.mostrar_laboratorio(tuple(self.sesion.parkours()), cerca=cerca, puerta=puerta)

    def _mover_en_laboratorio(self, dt):
        plano = self.planos[sc.LABORATORIO]
        h = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
        v = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
        try:
            from frontend import mando
            eje = mando.eje_izquierdo() if hasattr(mando, "eje_izquierdo") else None
            if eje is not None and (abs(eje[0]) > 0.2 or abs(eje[1]) > 0.2):
                h, v = eje
        except Exception:               # noqa: BLE001
            pass
        p = self.protagonista.personaje
        norma = math.hypot(h, v)
        if norma < 1e-3 or self.hud.modal_abierto:
            self.protagonista.quieto()
        else:
            dx, dz = h / norma * VELOCIDAD_LAB * dt, v / norma * VELOCIDAD_LAB * dt
            x, z = sc.mover(plano, p.x, p.z, dx, dz)
            rumbo = math.degrees(math.atan2(dx, dz))
            real = math.hypot(x - p.x, z - p.z) / max(dt, 1e-4)
            self.protagonista.caminar(x, z, rumbo, real)
        if bv.reducir_movimiento():
            self.camara.cortar(cc.toma_seguir((p.x, p.z), plano.origen, plano.fondo))
        else:
            self._seguir_suave(plano, p, dt)
        self._refrescar_laboratorio()

    def _seguir_suave(self, plano, p, dt):
        meta = cc.toma_seguir((p.x, p.z), plano.origen, plano.fondo)
        actual = self.camara.actual or meta
        k = min(1.0, dt * 3.0)
        if not self.camara.en_transicion:
            self.camara.actual = cc.interpolar(actual, meta, k)

    def _tecla_laboratorio(self, key):
        if key not in ("e", "gamepad x", "gamepad a"):
            return False
        cerca, puerta = self._lab
        if cerca is not None:
            self._entrar_terminal(cerca)
        elif puerta:
            self.protagonista.quieto()
            # O10: si faltan terminales, el cuadro lo dice (sin esas pruebas el caso no llega al umbral de éxito)
            aviso = fc.aviso_puerta_laboratorio(self.sesion.parkours() if self.sesion is not None else ())
            self.hud.confirmar("¿Pasar a la sala?", "El laboratorio se cierra. No podrás volver.", si="Pasar",
                               no="Quedarme", al_responder=self._respuesta_puerta, aviso=aviso)
        return True

    def _respuesta_puerta(self, si):
        if not si or self.sesion is None or self.modo != "laboratorio":
            return
        self._seguro(lambda: (self.sesion.salir_laboratorio(), self._tras_decision(False)))

    def _entrar_terminal(self, nivel):
        plano = self.planos[sc.LABORATORIO]
        t = sc.terminal_de(plano, nivel)
        if t is None:
            return
        self.modo = "terminal"
        self._t_terminal = 0.0
        self._nivel = nivel
        self._antes_parkour = self._resultado_parkour(nivel)
        self.protagonista.quieto()
        self.hud.ocultar_laboratorio()
        self.hud.ocultar()
        self.protagonista.caminando = False
        self.protagonista.personaje.automatico = False
        self.camara.pausada = True
        con_b = self.protagonista.postura.entrar_a_pantalla(
            self._silla_b(t), self._mesa_b(), t.pantalla, cc.toma_dentro_pantalla(t.pantalla),
            al_terminar=self._lanzar_parkour)
        if con_b:
            return
        self.camara.pausada = False
        # versión simple: sentado (bajo un corte corto de cámara), acercamiento al monitor y glitch
        self.protagonista.sentar(t.asiento)
        self.camara.ir_a(cc.toma_terminal(t.pantalla), duracion=0.5)
        rapido = bv.reducir_movimiento()
        self._agenda = [(0.0 if rapido else 0.8, lambda: self.camara.ir_a(cc.toma_dentro_pantalla(t.pantalla), 0.6)),
                        (0.0 if rapido else 1.2, self._subir_glitch)]
        self._t_agenda = 0.0

    def _subir_glitch(self):
        if self.glitch is not None:
            self.glitch.subir(0.35, al_terminar=self._lanzar_parkour)
        else:
            self._lanzar_parkour()

    def _lanzar_parkour(self):
        nivel = self._nivel
        lanzar = getattr(self._conexion, "ir_a_parkour", None)
        flujo = self._mundo.flujo
        volver = lambda: self._gestor.cambiar_a(FISCALIA, flujo=flujo, regreso=nivel)   # noqa: E731
        ok = False
        self._sin_recompensa_global(True)
        if lanzar is not None:
            try:
                ok = lanzar(nivel, volver_a=volver, antesala=False)
            except TypeError:
                ok = lanzar(nivel, volver_a=volver)
        if not ok:
            self._sin_recompensa_global(False)
            if self.glitch is not None:
                self.glitch.cancelar()
            self._levantarse_del_terminal()
            self.hud.mostrar()
            self.hud.decir_jugador("(El servidor no responde. Inténtalo de nuevo.)")
        elif self.glitch is not None:
            self.glitch.desvanecer()

    def _escena_parkour(self):
        """La escena del parkour registrada en el gestor (frontend/registro_parkour.py la registra como PARKOUR)."""
        from frontend.flujo_constantes import PARKOUR
        return getattr(self._gestor, "_escenas", {}).get(PARKOUR)

    def _resultado_parkour(self, nivel):
        """Último resultado del nivel (dict de parkour_calculos.resultado_del_nivel) o None."""
        escena = self._escena_parkour()
        return None if escena is None else getattr(escena, "resultados", {}).get(nivel)

    def _sin_recompensa_global(self, activo):
        """El parkour del laboratorio NO da la evidencia global vieja ni toca el GameState (las consecuencias del caso van
        al cierre; la prueba la entrega solo sesion.completar_parkour). Se cambia el proveedor de GameState de la escena
        del parkour mientras dura (sin editar sus archivos) y se devuelve al volver."""
        try:
            escena = self._escena_parkour()
            if escena is None:
                return
            if activo:
                if getattr(self, "_proveedor_gs", None) is None:
                    self._proveedor_gs = escena._game_state
                escena._game_state = lambda: None
            elif getattr(self, "_proveedor_gs", None) is not None:
                escena._game_state, self._proveedor_gs = self._proveedor_gs, None
        except Exception as error:      # noqa: BLE001
            print(f"[fiscalia] proveedor del parkour: {error}", file=sys.stderr)

    def _volver_del_parkour(self, nivel):
        self._sin_recompensa_global(False)
        despues = self._resultado_parkour(nivel)
        if fc.parkour_completado(self._antes_parkour, despues):
            self.sesion.completar_parkour(nivel)
            self.hud.aplicar_cambios(self.sesion.tomar_cambios(), self.sesion.solidez)
            pant = self.salas[sc.LABORATORIO][1]["pantallas"].get(nivel)
            if pant is not None:
                pant.fijar(True)
        self._antes_parkour = None
        self._t_terminal = 0.0              # el tope del terminal cuenta de nuevo desde la vuelta
        self._montar_sala(sc.LABORATORIO, self.vista)
        t = sc.terminal_de(self.planos[sc.LABORATORIO], nivel)
        self.protagonista.sentar(t.asiento)
        self.protagonista.caminando = False
        self.protagonista.personaje.automatico = False
        self.modo = "terminal"
        self.camara.cortar(cc.toma_dentro_pantalla(t.pantalla))
        # con la animación de B: la cámara sale del monitor y el personaje se levanta y aparta la silla; si no, lo simple
        self.camara.pausada = True
        if self.protagonista.postura.salir_de_pantalla(self._silla_b(t), self._mesa_b(), t.pantalla,
                                                       cc.toma_terminal(t.pantalla),
                                                       al_terminar=lambda: self._seguro(self._levantar_con_b)):
            return
        self.camara.pausada = False
        self.camara.ir_a(cc.toma_terminal(t.pantalla), duracion=0.7)
        self._agenda = [(0.0 if bv.reducir_movimiento() else 1.1, self._levantarse_del_terminal)]
        self._t_agenda = 0.0

    def _silla_b(self, t):
        silla = self.salas[sc.LABORATORIO][1]["sillas"].get(t.nivel)
        return {"posicion": t.asiento.punto, "rumbo": t.asiento.rumbo, "entidad": silla}

    def _mesa_b(self):
        plano = self.planos[sc.LABORATORIO]
        x0, z0, x1, z1 = plano.limites(0.15)
        return {"altura": sc.ALTURA_MESA, "borde": 0.36, "limites": (x0, x1, z0, z1, 0.3, plano.alto - 0.1)}

    def _levantar_con_b(self):
        t = sc.terminal_de(self.planos[sc.LABORATORIO], self._nivel)
        if t is None or not self.protagonista.postura.levantarse(self._silla_b(t), self._mesa_b(), t.acceso,
                                                                 al_terminar=lambda: self._seguro(
                                                                     self._levantarse_del_terminal)):
            self._levantarse_del_terminal()

    def _levantarse_del_terminal(self):
        plano = self.planos[sc.LABORATORIO]
        t = sc.terminal_de(plano, self._nivel) if self._nivel else None
        self.protagonista.soltar_poses()     # IK fuera (piernas y brazos vuelven a la animación): de pie de verdad
        if self.camara.pausada:
            self.camara.retomar()
        if t is not None:
            x, z = t.acceso
            self.protagonista.de_pie(sc.Asiento(x, z, 200.0))
        self.protagonista.personaje.automatico = True
        self.protagonista.caminando = True
        self.modo = "laboratorio"
        self.hud.mostrar()
        if self.vista is not None:
            self.hud.presentar(self.vista, ancla=None)
        self._refrescar_laboratorio(forzar=True)

    # -- Entrada --

    def input(self, key):
        if self.sesion is None or self._saliendo or self._en_respaldo:
            return
        try:
            if key in ("space", "enter") and self.modo == "terminal" and self.protagonista.postura.saltar():
                return
            if self._pendiente is not None or self.modo == "terminal":
                return
            if self.hud is not None and self.hud.entrada(key):
                return
            if self.modo == "laboratorio":
                self._tecla_laboratorio(key)
        except Exception as error:      # noqa: BLE001
            self._respaldo("entrada", error)

    # -- Frame --

    def update(self):
        if self.sesion is None or self._en_respaldo:
            return
        try:
            self._frame(min(time.dt, 0.1))
        except Exception as error:      # noqa: BLE001
            self._respaldo("frame", error)

    def _en_transicion(self):
        try:
            return bool(self._conexion._transicion_en_curso())
        except Exception:               # noqa: BLE001
            return False

    def _frame(self, dt):
        self._t += dt
        self._t_linea += dt
        if self._pendiente is not None and not self._en_transicion():
            self._tras_fundido()
        if self._agenda:
            self._t_agenda += dt
            while self._agenda and self._t_agenda >= self._agenda[0][0]:
                _, funcion = self._agenda.pop(0)
                self._t_agenda = 0.0
                funcion()
        reducir = bv.reducir_movimiento()
        vista = self.vista
        hablante = vista.personaje if vista is not None else None
        hablando = (self.hud is not None and not self.hud.linea_completa() and self.modo == "conversacion"
                    and self._pendiente is None)
        apertura = (0.15 + 0.6 * abs(math.sin(self._t * 11.0))) if hablando else None
        for pid, actor in self.actores.items():
            if not actor.npc.enabled:
                continue
            if pid == hablante:
                actor.avanzar(dt, vista.expresion, hablando, apertura, reducir)
            else:
                actor.avanzar(dt, None, False, None, reducir)
        if self.protagonista is not None:
            self.protagonista.avanzar(dt)
        if self.modo == "laboratorio" and self._pendiente is None:
            self._mover_en_laboratorio(dt)
        elif self.modo == "terminal" and self._pendiente is None:
            # Tope (flujo_calculos.tope_terminal, 12 s fuera de fundidos): en el terminal no se atiende ninguna tecla; si
            # la animación o la apertura del parkour fallan sin avisar, el jugador queda de pie en el laboratorio.
            self._t_terminal, vencido = fc.tope_terminal(getattr(self, "_t_terminal", 0.0), dt, self._en_transicion())
            if vencido:
                print("[fiscalia] tope del terminal: el jugador se levanta solo", file=sys.stderr)
                self._agenda = []
                self._sin_recompensa_global(False)
                if self.glitch is not None:
                    try:
                        self.glitch.cancelar()
                    except Exception:   # noqa: BLE001
                        pass
                self._levantarse_del_terminal()
        self.camara.avanzar(dt)
        if self.hud is None or self._pendiente is not None:
            return
        if self.modo == "conversacion" and vista is not None:
            corre = fc.reloj_corre(vista, self.hud.linea_completa(), self.hud.modal_abierto, self._en_transicion())
            if corre and self.sesion.avanzar_tiempo(dt):
                self._tras_decision(True)
                return
            if vista.reloj_segundos is not None:
                self.hud.fijar_reloj(self.sesion.vista().restante, vista.reloj_segundos)
            else:
                self.hud.fijar_reloj(None, None)
            self.hud.fijar_ancla(self._ancla())

    # -- Respaldo --

    def _respaldo(self, donde, error):
        """Se cae a la sala digital de hoy (o al mundo). Una sola vez por caso."""
        if self._en_respaldo:
            return
        self._en_respaldo = True
        self.respaldos += 1
        self.ultimo_error = f"{donde}: {type(error).__name__}: {error}"
        print(f"[fiscalia] RESPALDO ({donde}): {type(error).__name__}: {error}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        caso_id = self.caso_id
        self._sin_recompensa_global(False)
        try:
            self._desmontar()
        except Exception:               # noqa: BLE001
            pass
        self._en_respaldo = True
        try:
            self.camara.soltar()
            self._luces(False)
        except Exception:               # noqa: BLE001
            pass

        def caer():
            self._en_respaldo = False
            ir = getattr(self._conexion, "ir_a_mundo_digital", None)
            try:
                if ir is not None and caso_id is not None and ir(caso_id):
                    return
            except Exception as error2:     # noqa: BLE001
                print(f"[fiscalia] la sala digital tampoco abrió: {error2}", file=sys.stderr)
            self.volver_al_mundo("La Fiscalía no está disponible ahora")

        try:
            from ursina import invoke
            invoke(caer, delay=0.01)        # fuera del cambio de escena en curso (al_entrar) o del frame
        except Exception:               # noqa: BLE001
            caer()


class _HudMudo:
    """Sustituto momentáneo del hud mientras se presenta un nodo bajo el fundido (el real se presenta después)."""

    def presentar(self, *a, **k):
        pass

    def mostrar_laboratorio(self, *a, **k):
        pass

    def __getattr__(self, nombre):
        return lambda *a, **k: None

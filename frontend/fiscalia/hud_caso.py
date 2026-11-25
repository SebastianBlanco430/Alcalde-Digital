# Fachada de la interfaz del caso de Fiscalía v2 (contrato_ui.md §3). Cuelga de camera.ui; no toca la sesión, la
# cámara ni `scene`: dibuja lo que la escena le pide y avisa por callbacks (al_elegir, al_continuar, al_abandonar).
#
#   Medidor «Solidez del caso NN %» arriba (medidor_solidez.py), subtítulos abajo (subtitulos.py), rueda de 4 huecos con
#   el reloj en anillo, fija en el tercio derecho (rueda.py), fichas de sospechosos en la acusación (acusacion.py),
#   chips del laboratorio (laboratorio_ui.py), pausa y confirmaciones (pausa_caso.py), final + diagrama de flujo
#   (diagrama_flujo.py). La matemática está en los *_calculos.py (puros, con tests).
#
# ENTRADA: la escena le pasa TODAS las teclas a `entrada(key)` (la interfaz no define `input`, para no recibirlas dos
# veces). Las teclas crudas del mando («gamepad a», «gamepad start»...) solo se usan si frontend/mando.py no está
# instalado: con él instalado ya llegan traducidas (A = Espacio o clic, Start/B = Escape, cruceta = flechas). El palo
# izquierdo se lee de `held_keys` cada frame: su dirección resalta el hueco de ese lado.
#
# GUARDIÁN: ningún método público lanza hacia la escena. Si algo falla dentro, se avisa UNA vez por stderr, la interfaz
# se degrada a texto plano (nombre, línea y opciones numeradas; 1-4 eligen, Espacio sigue, Esc pausa) y el caso se puede
# terminar igual. Los errores de los callbacks de la escena se avisan sin degradar la interfaz.
# REDUCIR MOVIMIENTO (banderas_visuales.reducir_movimiento()): texto de golpe, rueda sin animación, sin pulso ni temblor.

import functools
import sys
import textwrap
import traceback

from panda3d.core import ClockObject
from ursina import Entity, Text, camera, held_keys, mouse, time, window

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, rgb, panel_piel
from frontend.fiscalia import rueda_calculos as rc
from frontend.fiscalia import ui_calculos as uc

Z_HUD = -100.5          # delante del velo de los fundidos (transicion.Z_FRENTE = -100), detrás de su rótulo (-101)
MAX_OPCIONES = 4
RECARGA_REDUCIR = 1.0   # s entre lecturas del ajuste «reducir movimiento»
PALO_MANDA = 0.35       # s tras mover el palo en que el ratón no cambia el resaltado (el palo mueve también el cursor)

_CRUDAS_MANDO = {"gamepad a": "space", "gamepad b": "escape", "gamepad start": "escape",
                 "gamepad dpad up": "up arrow", "gamepad dpad down": "down arrow",
                 "gamepad dpad left": "left arrow", "gamepad dpad right": "right arrow"}


def _seguro(defecto=None):
    """Envuelve un método público: nunca lanza. Si falla, degrada la interfaz y prueba su versión en texto plano."""
    def deco(funcion):
        nombre = funcion.__name__

        @functools.wraps(funcion)
        def envoltura(self, *args, **kwargs):
            if self.__dict__.get("_destruido"):
                return defecto
            plano = getattr(self, "_plano_" + nombre, None)
            if self.__dict__.get("_degradado"):
                return self._intentar_plano(plano, nombre, defecto, args, kwargs)
            try:
                return funcion(self, *args, **kwargs)
            except Exception as error:            # noqa: BLE001
                self._degradar(nombre, error)
                return self._intentar_plano(plano, nombre, defecto, args, kwargs)
        return envoltura
    return deco


def _sonar(nombre, volumen=1.0, pitch=1.0):
    try:
        from frontend import audio
        audio.obtener().efecto(nombre, volumen=volumen, pitch=pitch)
    except Exception:                             # noqa: BLE001  sin audio: en silencio
        pass


def _validar_vista(vista):
    """Lo mínimo que la interfaz lee de una VistaNodo: si falta, ValueError (el guardián lo avisa) sin tocar el estado."""
    for campo in ("id", "tipo", "personaje", "texto"):
        if not hasattr(vista, campo):
            raise ValueError(f"vista sin «{campo}»: {type(vista).__name__}")


def _mando_instalado():
    try:
        from frontend import mando
        return mando._estado.get("instalado") is not None
    except Exception:                             # noqa: BLE001
        return False


class HudCaso(Entity):

    def __init__(self, caso, *, al_elegir, al_continuar, al_abandonar, parent=None):
        super().__init__(parent=parent if parent is not None else camera.ui, z=Z_HUD)
        self._caso = caso
        self._al_elegir = al_elegir
        self._al_continuar = al_continuar
        self._al_abandonar = al_abandonar
        self._degradado = False
        self._destruido = False
        self._avisados = set()
        self._plano = None
        self._plano_estado = {"pausa": False, "final": None, "confirmar": None}
        # Estado del flujo
        self._vista = None
        self._modo = "nada"            # nada | dialogo | rueda | acusacion | laboratorio | final
        self._ancla = None
        self._centro = None
        self._reloj = (None, None)
        self._resaltado = None
        self._eleccion_hecha = False
        self._esperando = False         # ya se pidió continuar: hasta el próximo presentar
        self._ruedas_vistas = set()
        self._pos_vistas = {}
        self._etiquetas = {}            # vista.id -> {posición: etiqueta} (para dibujar la opción ya gastada)
        self._elegidas = {}             # vista.id -> posiciones que el jugador eligió en esa rueda
        self._frame = -1
        self._t_palo = 9.0
        self._raton_prev = None
        self._t_lab = 0.0
        self._reducir = False
        self._t_reducir = 9.0
        # Piezas
        self.pausa = None
        self._confirm = None
        self._final = None
        try:
            self._construir()
        except Exception as error:                # noqa: BLE001  sin piezas: texto plano desde el principio
            self._degradar("__init__", error)

    def _construir(self):
        from frontend.fiscalia.acusacion import Ficha
        from frontend.fiscalia.laboratorio_ui import LaboratorioUI
        from frontend.fiscalia.medidor_solidez import MedidorSolidez
        from frontend.fiscalia.rueda import Rueda
        from frontend.fiscalia.subtitulos import Subtitulos
        umbrales = dict(getattr(self._caso, "umbrales", None) or {})
        self.medidor = MedidorSolidez(umbrales, parent=self)
        self.subs = Subtitulos(parent=self, enabled=False)
        self.rueda = Rueda(parent=self, z=-0.05)
        self.tablero = Rueda(fabrica=Ficha, ancho=rc.ANCHO_FICHA, alto=rc.ALTO_FICHA, parent=self, z=-0.05)
        self.tablero.datos = dict(getattr(self._caso, "personajes", None) or {})
        self.lab = LaboratorioUI(parent=self)

    # =========================================================================================== API del contrato

    @_seguro()
    def presentar(self, vista, *, ancla=None):
        if vista is None:
            return
        _validar_vista(vista)
        if ancla is not None:
            self._ancla = (float(ancla[0]), float(ancla[1]))
        tipo = getattr(vista, "tipo", "dialogo")
        modo = tipo if tipo in ("dialogo", "rueda", "acusacion", "laboratorio") else "dialogo"
        mismo = self._vista is not None and self._vista.id == vista.id and self._modo == modo
        self._vista = vista
        self._modo = modo
        self._eleccion_hecha = False
        self._esperando = False
        reducir = self._reducir_mov()
        if not mismo:
            self._resaltado = None
            instantaneo = modo in ("rueda", "acusacion") and vista.id in self._ruedas_vistas
            espera = min(uc.ESPERA_TRAS_DICE, self.subs.hablando_jugador())
            self.subs.decir(self._nombre(vista.personaje), vista.texto, instantaneo=instantaneo, espera=espera,
                            reducir=reducir)
            self._t_lab = 0.0
            for r in (self.rueda, self.tablero):
                r.esconder()
            self._centro = None
        self.subs.fijar_siguiente(modo == "dialogo")
        if modo in ("rueda", "acusacion"):
            self._ruedas_vistas.add(vista.id)
            r = self._rueda_activa()
            opciones = tuple(getattr(vista, "opciones", ()) or ())[:MAX_OPCIONES]
            ahora = {int(getattr(o, "posicion", 0)) for o in opciones}
            vistas = self._pos_vistas.setdefault(vista.id, set())
            vistas |= ahora
            etiquetas = self._etiquetas.setdefault(vista.id, {})
            for o in opciones:
                etiquetas[int(getattr(o, "posicion", 0))] = str(getattr(o, "etiqueta", "") or "")
            elegidas = self._elegidas.get(vista.id, set())
            # gastada = la eligió el jugador y ya no viene; si desapareció por otra razón, el hueco no se dibuja
            r.preparar(opciones, usados={p: etiquetas.get(p, "") if p in elegidas else "" for p in vistas - ahora})
            if self._resaltado is not None and self._resaltado not in r.ocupados():
                self._resaltado = None
            r.resaltar(self._resaltado)
            if mismo and r.visible_rueda:
                r.mostrar(animar=False)
        if modo != "laboratorio":
            self.lab.ocultar()

    @_seguro()
    def fijar_ancla(self, ancla):
        self._ancla = None if ancla is None else (float(ancla[0]), float(ancla[1]))

    @_seguro()
    def fijar_reloj(self, restante, total):
        self._reloj = (restante, total) if (restante is not None and total) else (None, None)

    @_seguro()
    def fijar_solidez(self, valor):
        self.medidor.fijar(valor)

    @_seguro()
    def aplicar_cambios(self, cambios, solidez):
        delta = 0
        for c in cambios or ():
            tipo = getattr(c, "tipo", "")
            if tipo == "solidez":
                delta += int(getattr(c, "delta", 0) or 0)
            elif tipo == "evidencia":
                nombre = getattr(c, "nombre", "") or self._nombre_prueba(getattr(c, "evidencia", None))
                self.medidor.prueba_nueva(nombre)
                _sonar("mision_exito", 0.5, 1.1)
        if delta:
            self.medidor.cambiar(solidez, delta, reducir=self._reducir_mov())
        elif solidez is not None and int(solidez) != self.medidor.valor:
            self.medidor.fijar(solidez)

    @_seguro(True)
    def linea_completa(self):
        return bool(self.subs.completa())

    @_seguro()
    def completar_linea(self):
        self.subs.completar()

    @_seguro()
    def decir_jugador(self, texto):
        self.subs.decir_jugador(texto, reducir=self._reducir_mov())

    @_seguro()
    def mostrar_laboratorio(self, parkours, *, cerca=None, puerta=False):
        self.lab.mostrar(parkours, cerca=cerca, puerta=puerta)

    @_seguro()
    def ocultar_laboratorio(self):
        self.lab.ocultar()

    @_seguro()
    def confirmar(self, titulo, texto, *, si, no, al_responder, aviso=""):
        # pendientes-a (O10): `aviso` = línea extra resaltada (p. ej. «Aún no revisaste los equipos del laboratorio…»)
        from frontend.fiscalia.pausa_caso import Confirmacion
        self._cerrar_confirmacion()

        def responder(valor):
            conf, self._confirm = self._confirm, None
            if conf is not None:
                self._destruir_luego(conf)
            self._llamar(al_responder, bool(valor))
        self._confirm = Confirmacion(titulo, texto, si, no, responder, aviso=aviso, parent=self, z=-0.3)

    @_seguro()
    def mostrar_final(self, vista, diagrama, *, al_cerrar):
        from frontend.fiscalia.diagrama_flujo import PantallaFinal
        self.cerrar_pausa()
        self._cerrar_confirmacion()
        if self._final is not None:
            self._destruir_luego(self._final)
            self._final = None
        self._modo = "final"
        self._vista = vista
        for pieza in (self.rueda, self.tablero):
            pieza.esconder()
        self.subs.enabled = False
        self.lab.ocultar()
        self.medidor.enabled = False

        def cerrar():
            self._llamar(al_cerrar)
        self._final = PantallaFinal(vista, diagrama, cerrar, solidez=self.medidor.valor,
                                    umbrales=self.medidor.umbrales, titulo_caso=getattr(self._caso, "titulo", ""),
                                    semiancho=self._semiancho(), parent=self, z=-0.2)

    @_seguro()
    def abrir_pausa(self):
        from frontend.fiscalia.pausa_caso import PausaCaso
        if self._final is not None or not self.enabled:
            return
        if self.pausa is None:
            self.pausa = PausaCaso(self.cerrar_pausa, self._abandonar_confirmado, parent=self, z=-0.4)
        self.pausa.enabled = True
        self.pausa.foco.indice = 0
        self.pausa.foco.aplicar()
        _sonar("clic_ui", 0.5)

    @_seguro()
    def cerrar_pausa(self):
        if self.pausa is not None:
            if self.pausa.confirmacion is not None:
                self._destruir_luego(self.pausa.confirmacion)
                self.pausa.confirmacion = None
            self.pausa.enabled = False

    @property
    def en_pausa(self):
        try:
            if self._degradado:
                return bool(self._plano_estado["pausa"])
            return self.pausa is not None and bool(self.pausa.enabled)
        except Exception:                         # noqa: BLE001
            return False

    @property
    def modal_abierto(self):
        try:
            if self._degradado:
                e = self._plano_estado
                return bool(e["pausa"] or e["final"] is not None or e["confirmar"] is not None)
            return self.en_pausa or self._confirm is not None or self._final is not None
        except Exception:                         # noqa: BLE001
            return False

    @_seguro(False)
    def entrada(self, key):
        if not isinstance(key, str):
            return False
        key = self._traducir(key)
        if key is None:
            return False
        if self.en_pausa:
            self.pausa.tecla(key)
            return True
        if self._confirm is not None:
            self._confirm.tecla(key)
            return True
        if self._final is not None:
            self._final.tecla(key)
            return True
        if not self.enabled:
            return False
        if key == "escape":
            self.abrir_pausa()
            return True
        if self._modo == "dialogo":
            if key in ("space", "enter", "left mouse down"):
                self._avanzar_dialogo()
                return True
            return False
        if self._modo in ("rueda", "acusacion"):
            return self._entrada_rueda(key)
        return False

    def update(self):
        self.actualizar(time.dt)

    @_seguro()
    def actualizar(self, dt):
        frame = ClockObject.getGlobalClock().getFrameCount()
        if frame == self._frame:                  # la escena y el propio update en el mismo frame: una sola vez
            return
        self._frame = frame
        dt = max(0.0, min(float(dt or 0.0), 0.1))
        reducir = self._reducir_mov(dt)
        self.subs.avanzar(dt, reducir)
        self.medidor.avanzar(dt, reducir)
        if self.pausa is not None and self.pausa.enabled:
            self.pausa.avanzar(dt)
        if self._confirm is not None:
            self._confirm.avanzar(dt)
        if self._modo == "laboratorio" and self.subs.enabled and self.subs.completa():
            self._t_lab += dt
            if self._t_lab > 6.0:                 # en el laboratorio la línea del fiscal se va sola
                self.subs.enabled = False
        if self._modo in ("rueda", "acusacion") and not self._eleccion_hecha:
            self._frame_rueda(dt, reducir)

    @_seguro()
    def ocultar(self):
        self.enabled = False

    @_seguro()
    def mostrar(self):
        self.enabled = True

    def destruir(self):
        if self.__dict__.get("_destruido"):
            return
        self._destruido = True
        try:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self)
        except Exception as error:                # noqa: BLE001
            self._avisar("destruir", error)

    # =========================================================================================== Rueda

    def _rueda_activa(self):
        return self.tablero if self._modo == "acusacion" else self.rueda

    def _frame_rueda(self, dt, reducir):
        r = self._rueda_activa()
        if not r.visible_rueda:
            if not uc.rueda_entra(self.subs.t_linea(), self.subs.largo(), self.subs.completa()):
                return
            r.mostrar(animar=not reducir)
            self._centro = None
        objetivo = rc.colocar(self._ancla, r.ancho, r.alto, self._semiancho())
        self._centro = rc.suavizar_centro(self._centro, objetivo, dt, reducir=reducir)
        r.position = (self._centro[0], self._centro[1], -0.05)
        r.fijar_reloj(*self._reloj)
        self._entrada_continua(r, dt)
        r.avanzar(dt, reducir)

    def _entrada_continua(self, r, dt):
        """Palo izquierdo del mando (dirección = hueco) y ratón por encima (solo si se movió y el palo está quieto)."""
        x = float(held_keys["gamepad left stick x"] or 0.0)
        y = float(held_keys["gamepad left stick y"] or 0.0)
        hueco = uc.direccion_a_hueco(x, y)
        if hueco is not None and hueco in r.ocupados():
            self._resaltar(hueco)
            self._t_palo = 0.0
        else:
            self._t_palo += dt
        posicion = (round(float(mouse.x), 4), round(float(mouse.y), 4))
        if self._t_palo > PALO_MANDA and self._raton_prev is not None and posicion != self._raton_prev:
            bajo = r.hueco_bajo_raton()
            if bajo is not None:
                self._resaltar(bajo)
        self._raton_prev = posicion

    def _resaltar(self, hueco):
        if hueco == self._resaltado:
            return
        self._resaltado = hueco
        self._rueda_activa().resaltar(hueco)
        if hueco is not None:
            _sonar("hover_ui", 0.35)

    def _entrada_rueda(self, key):
        r = self._rueda_activa()
        if self._eleccion_hecha:
            return True
        visible = r.visible_rueda
        if key in uc.TECLAS_NUMERO:
            hueco = uc.TECLAS_NUMERO[key]
            if visible and hueco in r.ocupados():
                self._resaltar(hueco)
                self._elegir(hueco)
            elif not visible:
                self.subs.completar()
            return True
        if key in uc.TECLAS_DIRECCION:
            if visible:
                hueco = uc.hueco_de_tecla(key, r.ocupados())
                if hueco is not None:
                    self._resaltar(hueco)
                    self._t_palo = 0.0
            return True
        if key in ("space", "enter"):
            if visible and self._resaltado is not None:
                self._elegir(self._resaltado)
            elif not self.subs.completa():
                self.subs.completar()
            return True
        if key == "left mouse down":
            hueco = r.hueco_bajo_raton() if visible else None
            if hueco is not None:
                self._resaltar(hueco)
                self._elegir(hueco)
            elif not self.subs.completa():
                self.subs.completar()
            return True
        return False

    def _elegir(self, hueco):
        r = self._rueda_activa()
        opcion = r.opcion(hueco)
        if opcion is None:
            return
        if getattr(opcion, "estado", "libre") == "bloqueada":
            r.temblar(hueco)
            _sonar("mision_fallo", 0.4, 1.3)
            return
        self._eleccion_hecha = True
        if self._vista is not None:
            self._elegidas.setdefault(self._vista.id, set()).add(int(getattr(opcion, "posicion", hueco)))
        r.esconder()
        _sonar("clic_ui", 0.7)
        self._llamar(self._al_elegir, opcion.id)

    def _avanzar_dialogo(self):
        if self._esperando:
            return
        if not self.subs.completa():
            self.subs.completar()
            return
        self._esperando = True
        self._llamar(self._al_continuar)

    # =========================================================================================== Ayudas

    def _traducir(self, key):
        """Teclas crudas del mando: solo cuentan si frontend/mando.py no las traduce ya."""
        if key.startswith("gamepad"):
            if _mando_instalado():
                return None
            return _CRUDAS_MANDO.get(key)
        return key

    def _nombre(self, personaje):
        if not personaje:
            return ""
        try:
            return str((getattr(self._caso, "personajes", {}) or {})[personaje].get("nombre", personaje))
        except Exception:                         # noqa: BLE001
            return str(personaje)

    def _nombre_prueba(self, evidencia):
        try:
            return str((getattr(self._caso, "evidencias", {}) or {})[evidencia].get("nombre", evidencia))
        except Exception:                         # noqa: BLE001
            return str(evidencia or "")

    def _semiancho(self):
        try:
            return float(window.aspect_ratio) / 2
        except Exception:                         # noqa: BLE001
            return rc.SEMIANCHO_16_9

    def _reducir_mov(self, dt=0.0):
        self._t_reducir += dt
        if self._t_reducir >= RECARGA_REDUCIR:
            self._t_reducir = 0.0
            self._reducir = bool(bv.reducir_movimiento())
        return self._reducir

    def _cerrar_confirmacion(self):
        if self._confirm is not None:
            self._destruir_luego(self._confirm)
            self._confirm = None

    def _abandonar_confirmado(self):
        self.cerrar_pausa()
        self._llamar(self._al_abandonar)

    @staticmethod
    def _destruir_luego(entidad):
        from frontend.fiscalia.pausa_caso import destruir_luego
        destruir_luego(entidad)

    def _llamar(self, callback, *args):
        """Llama a un callback de la escena; si falla, se avisa (una vez) sin degradar la interfaz."""
        if callback is None:
            return None
        try:
            return callback(*args)
        except Exception as error:                # noqa: BLE001
            if "callback" not in self._avisados:
                self._avisados.add("callback")
                print(f"[hud_caso] un callback de la escena falló: {error!r}", file=sys.stderr)
                traceback.print_exc()
            return None

    def _avisar(self, clave, error):
        if clave in self._avisados:
            return
        self._avisados.add(clave)
        try:
            print(f"[hud_caso] {clave}: falló ({error!r}); la interfaz sigue en texto plano.", file=sys.stderr)
            traceback.print_exc()
        except Exception:                         # noqa: BLE001
            pass

    # =========================================================================================== Texto plano

    def _degradar(self, nombre, error):
        self._avisar(nombre, error)
        if self._degradado:
            return
        self._degradado = True
        try:
            for hijo in list(self.children):
                hijo.enabled = False
        except Exception:                         # noqa: BLE001
            pass
        try:
            self.enabled = True
            fondo = panel_piel(self, 1.3, 0.34, tono=estilo.COLOR_PANEL, position=(0, -0.3, -0.01))
            self._plano = Text("", parent=fondo, origin=(0, 0), z=-0.01, scale=escala_fuente(19),
                               font=tipografia.FUENTE_TEXTO, color=rgb(estilo.COLOR_TEXTO))
        except Exception as error_plano:          # noqa: BLE001
            self._avisar("texto_plano", error_plano)
            self._plano = None
        self._pintar_plano()

    def _intentar_plano(self, plano, nombre, defecto, args, kwargs):
        if plano is None:
            return defecto
        try:
            return plano(*args, **kwargs)
        except Exception as error:                # noqa: BLE001
            self._avisar("plano." + nombre, error)
            return defecto

    def _pintar_plano(self):
        try:
            self._pintar_plano_sin_guardia()
        except Exception as error:                # noqa: BLE001  datos imposibles: el texto plano queda vacío
            self._avisar("pintar_plano", error)

    def _pintar_plano_sin_guardia(self):
        if self._plano is None:
            return
        e = self._plano_estado
        if e["final"] is not None:
            vista = e["final"][0]
            texto = f"{getattr(vista, 'titulo', '')}\n{getattr(vista, 'texto', '')}\n\n[Enter] Salir de la Fiscalía"
        elif e["confirmar"] is not None:
            titulo, cuerpo, si, no, _ = e["confirmar"]
            texto = f"{titulo}\n{cuerpo}\n\n[Enter] {si}    [Esc] {no}"
        elif e["pausa"]:
            texto = "Caso en pausa\n\n[Esc] Seguir    [Supr] Abandonar caso"
        elif self._vista is not None:
            v = self._vista
            nombre = self._nombre(v.personaje)
            texto = f"{nombre}: {v.texto}" if nombre else str(v.texto)
            ops = []
            for o in tuple(getattr(v, "opciones", ()) or ())[:MAX_OPCIONES]:
                etiqueta = o.etiqueta if getattr(o, "estado", "libre") != "bloqueada" else (o.pista or "[Falta una prueba]")
                ops.append(f"[{int(o.posicion) + 1}] {etiqueta}")
            if ops:
                texto += "\n\n" + "    ".join(ops)
            elif v.tipo == "dialogo":
                texto += "\n\n[Espacio] Seguir"
        else:
            texto = ""
        self._plano.text = "\n".join(textwrap.fill(linea, 70) if linea else "" for linea in texto.split("\n"))

    def _plano_presentar(self, vista, *, ancla=None):
        if vista is None:
            return
        _validar_vista(vista)
        self._vista = vista
        self._modo = getattr(vista, "tipo", "dialogo")
        self._esperando = False
        self._pintar_plano()

    def _plano_linea_completa(self):
        return True

    def _plano_confirmar(self, titulo, texto, *, si, no, al_responder, aviso=""):
        texto = f"{texto} {aviso}" if aviso else texto
        self._plano_estado["confirmar"] = (titulo, texto, si, no, al_responder)
        self._pintar_plano()

    def _plano_mostrar_final(self, vista, diagrama, *, al_cerrar):
        self._plano_estado["pausa"] = False
        self._plano_estado["final"] = (vista, al_cerrar)
        self._modo = "final"
        self._pintar_plano()

    def _plano_abrir_pausa(self):
        if self._plano_estado["final"] is None:
            self._plano_estado["pausa"] = True
            self._pintar_plano()

    def _plano_cerrar_pausa(self):
        self._plano_estado["pausa"] = False
        self._pintar_plano()

    def _plano_ocultar(self):
        self.enabled = False

    def _plano_mostrar(self):
        self.enabled = True

    def _plano_entrada(self, key):
        if not isinstance(key, str):
            return False
        key = self._traducir(key)
        if key is None:
            return False
        e = self._plano_estado
        if e["final"] is not None:
            if key in ("enter", "space"):
                _, al_cerrar = e["final"]
                e["final"] = None
                self._llamar(al_cerrar)
            return True
        if e["confirmar"] is not None:
            if key in ("enter", "escape"):
                *_, al_responder = e["confirmar"]
                e["confirmar"] = None
                self._pintar_plano()
                self._llamar(al_responder, key == "enter")
            return True
        if e["pausa"]:
            if key == "escape":
                self._plano_cerrar_pausa()
            elif key == "delete":
                e["pausa"] = False
                self._llamar(self._al_abandonar)
            return True
        if not self.enabled:
            return False
        if key == "escape":
            self._plano_abrir_pausa()
            return True
        v = self._vista
        if v is None:
            return False
        if v.tipo in ("rueda", "acusacion") and key in uc.TECLAS_NUMERO:
            for o in v.opciones:
                if int(o.posicion) == uc.TECLAS_NUMERO[key] and getattr(o, "estado", "libre") != "bloqueada":
                    self._llamar(self._al_elegir, o.id)
                    break
            return True
        if v.tipo == "dialogo" and key in ("space", "enter") and not self._esperando:
            self._esperando = True
            self._llamar(self._al_continuar)
            return True
        return False

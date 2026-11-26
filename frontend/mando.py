# Mando (gamepad) para todo el juego. Las reglas puras (qué hace cada botón, zonas muertas, cursor) viven en
# frontend/mando_calculos.py; aquí solo se conecta con Ursina.
#
# Cómo funciona SIN tocar las escenas:
#   - Ursina ya conecta los mandos que ve Panda3D: cada botón llega como la tecla «gamepad a», «gamepad dpad up»… y los palos y
#     gatillos quedan en `held_keys`. Este módulo SOLO añade una entidad que:
#       1. traduce cada botón a las teclas de siempre (Espacio, E, Tab, Escape, flechas…) según el modo, de modo que las
#          escenas, el tutorial, los minijuegos y las pausas funcionan sin saber que existe el mando;
#       2. con el ratón libre (menús, teléfono, minijuegos, diálogos) mueve el CURSOR del sistema con el palo izquierdo, hace
#          clic con A y gira la rueda con el palo derecho: así todo lo que se maneja con el ratón se maneja con el mando;
#       3. con el ratón capturado (caminar por el mundo) deja los palos a los controladores (`geometria_mundo.ejes_de_teclas`,
#          la cámara y el parkour los leen) y convierte el gatillo derecho en «correr» (Mayús);
#       4. detecta mandos conectados o desconectados con el juego abierto (Ursina solo mira al arrancar).
#   - Sin mando conectado no hace nada: ni un evento, ni una llamada al sistema (el teclado y el ratón siguen idénticos).
#
# BANDERA. MANDO = False o ALCALDE_MANDO=0: no se instala nada (el juego solo con teclado y ratón, como antes).
# GUARDIÁN. Cualquier fallo en el mando avisa UNA vez por stderr y deja de intentarlo: nunca rompe una partida.

import os
import sys

from frontend import mando_calculos as mc

MANDO = True
REVISION_S = 1.0            # cada cuánto se mira si se conectó o se desconectó un mando

_estado = {"instalado": None, "avisados": set(), "sin_cursor": False}


def activo():
    """La bandera: MANDO y ALCALDE_MANDO distinto de 0/false/no/off."""
    valor = os.environ.get("ALCALDE_MANDO", "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "on"):
        return True
    return MANDO


def _avisar_una_vez(clave, error):
    if clave in _estado["avisados"]:
        return
    _estado["avisados"].add(clave)
    try:
        print(f"[Mando] {clave}: {type(error).__name__}: {error} (el mando se desactiva; teclado y ratón siguen igual)",
              file=sys.stderr)
    except Exception:                                  # noqa: BLE001
        pass


def instalar(gestor=None):
    """Crea la entidad del mando (una sola vez). Devuelve la entidad o None (bandera apagada o fallo)."""
    if _estado["instalado"] is not None:
        return _estado["instalado"]
    if not activo():
        return None
    # Pestaña «Mando» de Ajustes con el esquema de botones (frontend/mando_ajustes.py), haya o no mando conectado.
    try:
        from frontend import mando_ajustes
        mando_ajustes.registrar()
    except Exception as error:                         # noqa: BLE001
        _avisar_una_vez("ajustes", error)
    try:
        _estado["instalado"] = _crear()
    except Exception as error:                         # noqa: BLE001
        _avisar_una_vez("instalar", error)
        return None
    return _estado["instalado"]


def pausar_cursor(pausado):
    """Con True el palo izquierdo no mueve el cursor (una escena que usa el palo para caminar con el ratón libre, como la
    práctica del tutorial de parkour). Se levanta solo en cuanto el ratón vuelve a estar capturado."""
    _estado["sin_cursor"] = bool(pausado)


def desinstalar():
    """Quita la entidad (las pruebas)."""
    entidad, _estado["instalado"] = _estado["instalado"], None
    if entidad is not None:
        try:
            from ursina import destroy
            destroy(entidad)
        except Exception:                              # noqa: BLE001
            pass


def _crear():
    from ursina import Entity

    class Mando(Entity):
        """Traductor del mando. Ver el comentario del módulo."""

        def __init__(self):
            super().__init__(name="mando", eternal=True)
            self.hay_mando = False
            self._pulsados = {}                        # botón -> teclas que mandó al pulsarlo (para soltar lo mismo)
            self._espera_revision = 0.0
            self._cursor = None                        # (x, y) en camera.ui mientras el palo lo mueve
            self._rueda = mc.RuedaDelPalo()
            self._corriendo = False                    # el gatillo derecho tiene pulsado «Mayús»
            self._roto = False
            self._firma = None
            self._revisar_mandos(forzar=True)

        # -- Mandos conectados --

        def _revisar_mandos(self, forzar=False):
            """Reconecta si cambió la lista de mandos (Ursina solo la lee al importar `ursina.gamepad`)."""
            try:
                from panda3d.core import InputDevice
                from ursina import application, input_handler
                dispositivos = list(application.base.devices.getDevices(InputDevice.DeviceClass.gamepad))
            except Exception:                          # noqa: BLE001  sin Ursina/Panda en pruebas puras
                return
            firma = tuple(str(d) for d in dispositivos)
            if firma == self._firma and not forzar:
                return
            avisar = self._firma is not None or bool(firma)
            self._firma = firma
            hubo = self.hay_mando
            self.hay_mando = bool(dispositivos)
            if hubo and not self.hay_mando:
                self._liberar_todo()                   # se desenchufó con algo apretado: nada se queda pegado
            # Iconos de mando en las ayudas con un mando conectado; al desconectarlo, vuelven las teclas y el ratón
            # (frontend/mando_iconos.py). Un fallo ahí nunca rompe el mando.
            if hubo != self.hay_mando or forzar:
                try:
                    from frontend import mando_iconos
                    mando_iconos.fijar_mando(self.hay_mando, aviso=avisar and hubo != self.hay_mando)
                except Exception as error:             # noqa: BLE001
                    _avisar_una_vez("iconos", error)
            previos = getattr(input_handler, "gamepads", None)
            if previos is not None and list(previos) == dispositivos and not forzar:
                return
            try:
                from ursina import gamepad
                input_handler.gamepads = dispositivos
                gamepad.connect_all()
            except Exception as error:                 # noqa: BLE001
                _avisar_una_vez("conectar", error)
            if avisar:
                nombre = dispositivos[0].name if dispositivos else "ninguno"
                print(f"[Mando] mandos conectados: {len(dispositivos)} ({nombre})")

        def _liberar_todo(self):
            """Suelta lo que el mando mantenía (botones, Mayús del gatillo) y pone a cero palos y gatillos."""
            from ursina import held_keys
            for boton in list(self._pulsados):
                self._soltar(boton)
            if self._corriendo:
                self._mandar("left shift", False)
            self._corriendo = False
            for tecla in getattr(self, "_gatillos", {}).values():
                self._mandar(tecla, False)
            self._gatillos = {}
            self._cursor = None
            for clave in [k for k in list(held_keys) if isinstance(k, str) and k.startswith(mc.PREFIJO)]:
                held_keys[clave] = 0

        # -- Botones --

        def input(self, key):
            if self._roto:
                return None
            try:
                self._entrada(key)
            except Exception as error:                 # noqa: BLE001
                self._roto = True
                _avisar_una_vez("entrada", error)
            return None

        def _entrada(self, key):
            parsed = mc.nombre_de_boton(key)
            if parsed is None:
                return
            boton, pulsado = parsed
            self.hay_mando = True
            if pulsado:
                self._pulsar(boton)
            else:
                self._soltar(boton)

        def _pulsar(self, boton):
            from ursina import mouse
            modo = mc.modo_de(mouse.locked)
            enviadas = []
            for tecla in mc.teclas_de(boton, modo):
                if tecla == mc.CLIC:
                    tecla = "left mouse" if self._hay_boton_bajo_el_cursor() else "space"
                enviadas.append(tecla)
                self._mandar(tecla, True)
            self._pulsados[boton] = enviadas

        def _soltar(self, boton):
            for tecla in reversed(self._pulsados.pop(boton, [])):
                if tecla == "left shift" and self._corriendo:
                    continue                               # el gatillo sigue manteniendo Mayús
                self._mandar(tecla, False)

        def _rb_apretado(self):
            return "left shift" in self._pulsados.get("right shoulder", [])

        @staticmethod
        def _hay_boton_bajo_el_cursor():
            """¿Hay algo CLICABLE bajo el cursor (un botón con `on_click` o una zona con su propio `input`)? Un edificio, un NPC, un panel o un fondo con collider no cuentan: A tiene
            que seguir siendo Espacio (saltar la cinemática, continuar un diálogo)."""
            from ursina import mouse
            e = getattr(mouse, "hovered_entity", None)
            if e is None:
                return False
            if getattr(e, "on_click", None):
                return True
            return callable(getattr(e, "input", None))      # zonas con su propio manejo del clic; un panel o fondo plano no cuenta

        @staticmethod
        def _mandar(tecla, abajo):
            """Entrega la tecla al juego por el mismo camino que el teclado (`is_raw=True`: Ursina descarta las letras sin él)."""
            from ursina import application
            base = application.base
            if tecla == "left mouse":
                base.input("left mouse down" if abajo else "left mouse up", True)
            elif abajo:
                base.input(tecla, True)
            else:
                base.input_up(tecla, True)

        # -- Cada frame --

        def update(self):
            if self._roto:
                return
            try:
                self._cuadro()
            except Exception as error:                 # noqa: BLE001
                self._roto = True
                _avisar_una_vez("cuadro", error)

        def _cuadro(self):
            from ursina import held_keys, mouse, time
            dt = time.dt
            self._espera_revision -= dt
            if self._espera_revision <= 0:
                self._espera_revision = REVISION_S
                self._revisar_mandos()
            if not self.hay_mando:
                return
            modo = mc.modo_de(mouse.locked)
            self._gatillo_correr(held_keys, modo)
            self._gatillos_tecla(held_keys, modo)
            if modo == mc.MODO_MENU and not _estado["sin_cursor"]:
                self._cursor_con_palo(held_keys, dt, mouse)
                self._rueda_con_palo(held_keys, dt)
            else:
                self._cursor = None
                self._rueda.avanzar(0.0, dt)
                if modo == mc.MODO_MUNDO:
                    _estado["sin_cursor"] = False

        def _gatillo_correr(self, held_keys, modo):
            """Gatillo derecho = Mayús mientras se camina (correr)."""
            quiere = modo == mc.MODO_MUNDO and mc.gatillo(held_keys, mc.GATILLO_DERECHO)
            if quiere and not self._corriendo:
                self._corriendo = True
                self._mandar("left shift", True)
            elif self._corriendo and not quiere:
                self._corriendo = False
                if not self._rb_apretado():                 # RB comparte Mayús: no se suelta si sigue apretado
                    self._mandar("left shift", False)

        def _gatillos_tecla(self, held_keys, modo):
            """Gatillos que son una tecla en este modo (mando_calculos.GATILLOS_TECLA: el izquierdo del mundo = T). Se
            pulsa al pasar del umbral y se suelta al bajar o al cambiar de modo."""
            apretados = getattr(self, "_gatillos", None)
            if apretados is None:
                apretados = self._gatillos = {}
            deseados = mc.GATILLOS_TECLA.get(modo, {})
            for nombre, tecla in list(apretados.items()):
                if nombre not in deseados or deseados[nombre] != tecla or not mc.gatillo(held_keys, nombre):
                    self._mandar(tecla, False)
                    del apretados[nombre]
            for nombre, tecla in deseados.items():
                if nombre not in apretados and mc.gatillo(held_keys, nombre):
                    apretados[nombre] = tecla
                    self._mandar(tecla, True)

        def _cursor_con_palo(self, held_keys, dt, mouse):
            palo = mc.palo(held_keys, mc.PALO_IZQUIERDO)
            if palo == (0.0, 0.0):
                self._cursor = None
                return
            ventana = self._ventana()
            if ventana is None:
                return
            propiedades = ventana.getProperties()
            ancho, alto = propiedades.getXSize(), propiedades.getYSize()
            if ancho <= 0 or alto <= 0:
                return
            aspecto = ancho / alto
            if self._cursor is None:
                self._cursor = (float(mouse.x), float(mouse.y))          # arranca donde esté el puntero real
            lento = mc.gatillo(held_keys, mc.GATILLO_IZQUIERDO)
            velocidad = mc.VELOCIDAD_CURSOR_LENTA if lento else mc.VELOCIDAD_CURSOR
            self._cursor = mc.mover_cursor(self._cursor, palo, dt, velocidad, aspecto)
            px, py = mc.a_pixeles(self._cursor, ancho, alto, aspecto)
            ventana.movePointer(0, px, py)

        @staticmethod
        def _ventana():
            """La ventana de Panda3D si es una ventana real (offscreen no tiene puntero que mover); las pruebas la sustituyen."""
            from ursina import application
            return application.base.win if application.window_type == "onscreen" else None

        def _rueda_con_palo(self, held_keys, dt):
            _, y = mc.palo(held_keys, mc.PALO_DERECHO)
            vuelta = self._rueda.avanzar(y, dt)
            if vuelta is not None:
                from ursina import application
                application.base.input(vuelta, True)

    return Mando()

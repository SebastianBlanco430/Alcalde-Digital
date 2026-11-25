# Teléfono en grande para la bandeja de Civitas (tecla L) y los dilemas (tecla K). Solo cambia la VISTA:
# ControlHabitos / ControlDilemas, sus fases y sus teclas (1-n, clic, Intro, Retroceso, Esc) siguen igual.
#
#   ENGANCHE. registro_habitos.registrar() llama a envolver_habitos(vigia, escena) y registro_dilemas.registrar() a
#   envolver_dilemas(vigia, escena), justo después de crear su vigía. Las dos comparten UNA ui (un solo teléfono). Si la
#   bandera ALCALDE_TELEFONO_GRANDE está en 0 no hace nada. Si no, cambia la vista del control por una VistaTelefono que
#   guarda la vista de siempre como RESPALDO:
#     - un caso sin canal en backend/datos/canales_avisos.json se ve en el panel de siempre;
#     - si algo falla al crear el teléfono, queda la vista de siempre (aviso por stderr);
#     - si algo falla al mostrar un aviso, el teléfono se apaga para la sesión y ese aviso (y los siguientes) salen en el
#       panel de siempre. El control no cambia: nada queda bloqueado ni el reloj parado.
#   TARJETA DE PRIMERA VEZ (ALCALDE_TARJETAS_AVISOS). La primera vez en la partida que llega cada tipo principal
#   (backend/logica/avisos_telefono.tipo_principal), antes del teléfono sale una tarjeta corta con dibujos. Espacio, Intro
#   o clic la cierran y abren el teléfono; Esc lo cierra todo (como siempre) y la tarjeta sale otra vez la próxima.
#   Lo visto se guarda en el flujo (FlujoConAvisosVistos, clave «avisos_vistos» de partida.json) o, sin él, en memoria.
#   TECLAS. Una capa fina sobre control.tecla: mientras la tarjeta está abierta consume las teclas; en la revisión, las
#   flechas y la rueda mueven el scroll del panel lateral. Todo lo demás pasa tal cual al control.
#   AYUDA. El «?» del marco vuelve a mostrar la tarjeta del aviso abierto; «Avisos de Civitas» en la pausa abre todas
#   las tarjetas en carrusel (flechas para pasar, Esc o Intro para cerrar).
#
# Lo que no depende de Ursina (VistaTelefono, la capa de teclas y cómo se arma cada pantalla) se prueba sin ventana con
# una «ui» falsa (tests/test_telefono_grande.py). La ui de verdad la crea _crear_ui().
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

import sys
import time

from backend.logica import avisos_telefono as at
from frontend import telefono_grande_calculos as tgc

TECLAS_ENTENDIDO = ("space", "enter", "e", "numpad enter", "left mouse down")
TECLAS_SUBIR = ("up arrow", "scroll up", "w")
TECLAS_BAJAR = ("down arrow", "scroll down", "s")
TONO_BIEN = (80, 190, 110)          # estilo.ESTADO_EXITO
TONO_MAL = (215, 180, 60)           # estilo.ESTADO_AVISO
TONO_ACENTO = (255, 220, 60)
TONO_TENUE = (170, 172, 190)        # estilo.COLOR_TEXTO_TENUE
PREFIJO_PISTA = "[Pista] "          # habitos_calculos.contenido_feed
VOLUMEN_SONIDO = 0.6
Z_TARJETA = -1.0                    # por delante del teléfono (raíz en -0,06 más sus capas)
Z_CARRUSEL = -60.0                  # por delante del menú de pausa
FASES_SCROLL = ("revision", "resultado")     # revisión de la bandeja y resultado de un dilema


def _aviso(texto):
    print(f"[telefono] {texto}", file=sys.stderr)


# ----------------------------------------------------------------------------- tarjetas vistas

class EstadoTarjetas:
    """Qué tipos ya se explicaron. Usa flujo.avisos_vistos (se guarda con la partida) o, sin él, un conjunto en memoria
    que se reinicia al cambiar de flujo (partida nueva)."""

    def __init__(self):
        self._local = at.AvisosVistos()
        self._flujo_id = None

    def vistos(self, flujo):
        try:
            propios = getattr(flujo, "avisos_vistos", None) if flujo is not None else None
        except Exception:
            propios = None
        if isinstance(propios, at.AvisosVistos):
            return propios
        if id(flujo) != self._flujo_id:
            self._local = at.AvisosVistos()
            self._flujo_id = id(flujo)
        return self._local

    def debe_mostrar(self, flujo, tipo):
        return tipo is not None and at.tarjetas_activas() and not self.vistos(flujo).visto(tipo)

    def marcar(self, flujo, tipo):
        self.vistos(flujo).marcar(tipo)


# ----------------------------------------------------------------------------- cómo se arma cada pantalla (puro)

def zonas_de(canales, canal, elementos):
    return {e["id"]: at.zona_de(canales, canal, e["id"]) for e in elementos}


def lateral_habitos(contenido, evento, marcas):
    """Lo que dice el panel lateral en cada fase (sale del mismo `contenido` que dibujaba el panel de siempre)."""
    fase = contenido["fase"]
    if fase == "marcar":
        return {"titulo": contenido["titulo"], "instruccion": contenido.get("instruccion", ""),
                "botones": [(f["texto"], f["marcado"]) for f in contenido["filas"]],
                "aviso": contenido.get("hasta", ""), "pie": contenido["pie"]}
    if fase == "decidir":
        marcados = [e["texto"] for e in (evento or {}).get("elementos", [])[:tgc.MAX_ELEMENTOS] if e["id"] in marcas]
        return {"titulo": contenido["titulo"], "instruccion": contenido.get("instruccion", ""),
                "lineas": [(f"[x] {texto}", TONO_ACENTO) for texto in marcados],
                "pie": contenido["pie"]}
    if fase == "revision":
        return {"titulo": contenido["titulo"], "texto": contenido["texto"], "instruccion": contenido.get("resumen", ""),
                "lineas": [(f["texto"], TONO_BIEN if f["acertado"] else TONO_MAL) for f in contenido.get("filas", [])],
                "pie": contenido["pie"]}
    return {"titulo": contenido.get("titulo", ""), "texto": contenido.get("texto", ""), "pie": contenido.get("pie", "")}


def lateral_feed(contenido):
    return {"titulo": contenido.get("titulo", ""), "texto": contenido.get("aviso", ""),
            "instruccion": contenido.get("contador", ""), "pie": contenido.get("pie", "")}


def lateral_dilema(contenido, resultado=None):
    """Panel lateral de un dilema: situación y pistas al decidir (las opciones tocables van SOLO en el teléfono, en su
    hoja «¿Qué haces?»: si salieran también aquí habría botones repetidos); el resultado después."""
    if resultado is None:
        opciones = contenido.get("opciones", [])
        return {"titulo": contenido.get("titulo", ""), "texto": contenido.get("situacion", ""),
                "lineas": [(f"{o['tecla']}: {o['pista']}", TONO_TENUE) for o in opciones if o.get("pista")],
                "aviso": contenido.get("aviso", ""), "pie": contenido.get("pie", "")}
    return {"titulo": resultado.get("titulo", ""), "texto": resultado.get("texto", ""), "pie": resultado.get("pie", "")}


def _revision_marcas(elementos, resultado):
    """En la revisión: (ids marcados, ids que debían taparse y quedaron a la vista), en el orden de los elementos."""
    revision = (resultado or {}).get("revision") or []
    marcados, expuestos = set(), []
    for elemento, fila in zip(elementos, revision):
        if fila.get("marcado"):
            marcados.add(elemento["id"])
        elif fila.get("debia_marcarse"):
            expuestos.append(elemento["id"])
    return marcados, expuestos


def _intro_feed():
    try:
        from frontend import habitos_calculos
        return habitos_calculos.INTRO_FEED
    except Exception:
        return None


def datos_feed(canal, contenido, hora):
    texto = contenido.get("texto") or ""
    if texto.startswith(PREFIJO_PISTA):
        texto = texto[len(PREFIJO_PISTA):]
    publicacion = texto != _intro_feed()
    return {"canal": "feed", "id": "feed", "tipo": "feed", "titulo": contenido.get("titulo", ""), "remitente": "",
            "texto": texto, "hora": hora, "plan": tgc.plan_zonas([], {}), "marcas": set(), "fase": "feed",
            "opciones": [], "decision": None, "decision_texto": "", "extra": canal, "resultado_canal": None,
            "expuestos": [], "feed": {"texto": texto, "pista": bool(contenido.get("pista")), "publicacion": publicacion,
                                      "contador": contenido.get("contador", "")}}


def datos_pantalla(canal, canales, contenido, evento, marcas, resultado, hora):
    """Datos de la pantalla del canal (los numeros de los elementos son los de las teclas 1-n)."""
    if contenido.get("fase") == "feed":
        return datos_feed(canal, contenido, hora)
    elementos = (evento or {}).get("elementos", [])
    plan = tgc.plan_zonas(elementos, zonas_de(canales, canal, elementos))
    fase = contenido["fase"]
    expuestos = []
    if fase == "revision" and (resultado or {}).get("revision"):
        marcas, expuestos = _revision_marcas(elementos, resultado)
    marcados = {n for n, ident in plan["numeros"].items() if ident in marcas}
    decision = (resultado or {}).get("decision") if fase == "revision" else None
    etiquetas = {o["id"]: o["etiqueta"] for o in (evento or {}).get("opciones", [])}
    return {"canal": canal["canal"], "id": (evento or {}).get("id"), "tipo": (evento or {}).get("tipo"),
            "titulo": (evento or {}).get("titulo", ""), "remitente": (evento or {}).get("remitente", ""),
            "texto": (evento or {}).get("texto", ""), "hora": hora, "plan": plan, "marcas": marcados, "fase": fase,
            "opciones": [o["texto"] for o in contenido.get("opciones", [])] if fase == "decidir" else [],
            "decision": decision, "decision_texto": etiquetas.get(decision, ""), "extra": canal,
            "resultado_canal": canal.get("resultados", {}).get(decision) if decision else None,
            "expuestos": expuestos, "borrador": decision == "no_publicar"}


def datos_dilema(canal, contenido, resultado, hora):
    """Datos de la pantalla para un dilema (K). `contenido`: dilemas_calculos.contenido_dilema; `resultado`: el
    control.ultimo_resultado tras elegir (o None mientras se decide)."""
    opcion = (resultado or {}).get("opcion")
    etiquetas = {o["id"]: o["etiqueta"] for o in contenido.get("opciones", [])}
    resultado_canal = canal.get("resultados", {}).get(opcion) if opcion else None
    decidiendo = resultado is None
    return {"canal": canal["canal"], "id": contenido.get("id"), "tipo": "dilema", "titulo": contenido.get("titulo", ""),
            "remitente": "", "texto": contenido.get("situacion", ""), "hora": hora, "plan": tgc.plan_zonas([], {}),
            "marcas": set(), "fase": "decidir" if decidiendo else "revision",
            "opciones": [f"{o['tecla']}  {o['etiqueta']}" for o in contenido.get("opciones", [])] if decidiendo else [],
            "decision": opcion, "decision_texto": etiquetas.get(opcion, ""), "extra": canal,
            "resultado_canal": resultado_canal, "expuestos": [],
            "borrador": not (resultado_canal or {}).get("publica", False)}


# ----------------------------------------------------------------------------- vista

class VistaTelefono:
    """Misma API que la vista del panel de hábitos (mostrar, ocultar, chip y .panel.segundos_abierto()) y que la de los
    dilemas (mostrar_dilema, mostrar_resultado). `de`: «habitos» o «dilemas» (de dónde sale el id del caso).

    `ui`: lo que dibuja (mostrar_telefono(datos, lateral, abrir, hora), ocultar_telefono(), mostrar_tarjeta(datos),
    ocultar_tarjeta(), desplazar(pasos)). `respaldo`: la vista de siempre."""

    def __init__(self, control, respaldo, escena, canales, explicaciones, ui, de="habitos"):
        self.control, self.respaldo, self.escena, self.de = control, respaldo, escena, de
        self._metodo = "mostrar"
        self._tipo_actual = None
        self.canales, self.explicaciones, self.ui = canales, explicaciones or {}, ui
        self.tarjetas = EstadoTarjetas()
        self.roto = False
        self.modo = None                # None | "tarjeta" | "telefono" | "respaldo"
        self._tipo_tarjeta = None
        self._contenido = None
        self._t_abierta = None
        self.panel = self               # el vigía pregunta vista.panel.segundos_abierto()

    # -- consulta --

    def _flujo(self):
        return getattr(self.escena, "flujo", None)

    def _hora(self):
        """Solo «hh:mm» (como en un celular): el reloj del juego dice «Día 1 · 16:20»."""
        try:
            return str(self._flujo().reloj.hora_texto()).split("·")[-1].strip()
        except Exception:
            return ""

    def segundos_abierto(self):
        return 0.0 if self._t_abierta is None else time.monotonic() - self._t_abierta

    def tarjeta_abierta(self):
        return self.modo in ("tarjeta", "ayuda")

    def telefono_abierto(self):
        return self.modo == "telefono"

    def _evento(self):
        return getattr(self.control, "_evento", None)

    def _canal_de(self, contenido):
        """(canal, evento) del aviso que se está mostrando, o (None, evento) si va al panel de siempre. En los dilemas,
        el «evento» es el contenido del dilema (el del resultado no trae id: se toma el que guarda el control)."""
        if self.de == "dilemas":
            dilema = contenido if "situacion" in contenido else (getattr(self.control, "_contenido", None) or {})
            return at.canal_de(self.canales, dilema.get("id")), dilema
        if contenido.get("fase") == "feed":
            return at.canal_de(self.canales, "feed"), None
        evento = self._evento()
        return at.canal_de(self.canales, (evento or {}).get("id")), evento

    def _tipo_evento(self, contenido, evento):
        if self.de == "dilemas":
            return "dilema"
        return "feed" if contenido.get("fase") == "feed" else (evento or {}).get("tipo")

    def _datos(self, canal, contenido, evento):
        """(datos de la pantalla, contenido del panel lateral)."""
        if self.de == "dilemas":
            resultado = getattr(self.control, "ultimo_resultado", None) if self._metodo == "mostrar_resultado" else None
            datos = datos_dilema(canal, evento or {}, resultado, self._hora())
            return datos, lateral_dilema(evento or {}, contenido if resultado is not None else None)
        marcas = set(getattr(self.control, "marcas", ()) or ())
        resultado = getattr(self.control, "ultimo_resultado", None)
        datos = datos_pantalla(canal, self.canales, contenido, evento, marcas, resultado, self._hora())
        lateral = lateral_feed(contenido) if contenido.get("fase") == "feed" else lateral_habitos(contenido, evento, marcas)
        return datos, lateral

    # -- API de la vista --

    def mostrar_dilema(self, contenido):
        self._metodo = "mostrar_dilema"
        self._mostrar(contenido)

    def mostrar_resultado(self, contenido):
        self._metodo = "mostrar_resultado"
        self._mostrar(contenido)

    def mostrar(self, contenido):
        self._metodo = "mostrar"
        self._mostrar(contenido)

    def _mostrar(self, contenido):
        if self._t_abierta is None:
            self._t_abierta = time.monotonic()
        self._contenido = contenido
        canal, evento = self._canal_de(contenido)
        if canal is None or self.roto:
            self._a_respaldo(contenido)
            return
        try:
            self.ui.vista = self        # la ui es compartida: los clics van a esta bandeja
            if self.modo == "respaldo":
                self.respaldo.ocultar()
                self.modo = None
            if self.modo == "tarjeta":
                return                  # el teléfono se pinta al cerrar la tarjeta, con lo último que llegó
            if self.modo == "ayuda":
                self.ui.ocultar_tarjeta()
                self.modo = "telefono"
            tipo = at.tipo_principal(self._tipo_evento(contenido, evento), canal)
            if self.modo is None and tipo in self.explicaciones and self.tarjetas.debe_mostrar(self._flujo(), tipo):
                self.modo = "tarjeta"
                self._tipo_tarjeta = tipo
                self.ui.mostrar_tarjeta(self.explicaciones[tipo])
                return
            primera = self.modo != "telefono"
            self.modo = "telefono"
            self._tipo_actual = tipo
            datos, lateral = self._datos(canal, contenido, evento)
            self.ui.mostrar_telefono(datos, lateral, primera, self._hora())
            if primera:
                self._sonar()
        except Exception as error:
            self._fallo(error, contenido)

    def ocultar(self):
        if self.modo is None and getattr(self.ui, "vista", self) is not self:
            # el teléfono lo está usando la otra bandeja: solo se oculta lo propio
            self._t_abierta = None
            try:
                self.respaldo.ocultar()
            except Exception as error:
                _aviso(f"no se pudo ocultar ({type(error).__name__}: {error})")
            return
        self.modo = None
        self._tipo_tarjeta = None
        self._t_abierta = None
        for hacer in (self.ui.ocultar_tarjeta, self.ui.ocultar_telefono, self.respaldo.ocultar):
            try:
                hacer()
            except Exception as error:
                _aviso(f"no se pudo ocultar ({type(error).__name__}: {error})")

    def chip(self, texto, visible):
        self.respaldo.chip(texto, visible)

    # -- tarjeta --

    def entender(self):
        """Cierra la tarjeta de primera vez y abre el teléfono (o vuelve a él desde la ayuda). False si no había."""
        if self.modo == "ayuda":
            self.modo = "telefono"
            try:
                self.ui.ocultar_tarjeta()
            except Exception as error:
                _aviso(f"no se pudo cerrar la ayuda ({type(error).__name__}: {error})")
            return True
        if self.modo != "tarjeta":
            return False
        self.tarjetas.marcar(self._flujo(), self._tipo_tarjeta)
        self.modo = None
        self._tipo_tarjeta = None
        self._t_abierta = time.monotonic()
        try:
            self.ui.ocultar_tarjeta()
        except Exception as error:
            _aviso(f"no se pudo cerrar la tarjeta ({type(error).__name__}: {error})")
        if self._contenido is not None and self.control.abierto():
            self._mostrar(self._contenido)
        return True

    def ayuda(self):
        """El «?» del marco: vuelve a mostrar la tarjeta del aviso abierto. False si no hay ninguna."""
        if self.modo != "telefono" or self._tipo_actual not in self.explicaciones:
            return False
        self.modo = "ayuda"
        try:
            self.ui.mostrar_tarjeta(self.explicaciones[self._tipo_actual])
        except Exception as error:
            _aviso(f"no se pudo abrir la ayuda ({type(error).__name__}: {error})")
            self.modo = "telefono"
            return False
        return True

    def desplazar(self, pasos):
        if self.modo != "telefono":
            return False
        try:
            return bool(self.ui.desplazar(pasos))
        except Exception as error:
            _aviso(f"scroll ({type(error).__name__}: {error})")
            return False

    # -- respaldo --

    def _a_respaldo(self, contenido):
        if self.modo in ("telefono", "tarjeta"):
            try:
                self.ui.ocultar_tarjeta()
                self.ui.ocultar_telefono()
            except Exception:
                pass
        self.modo = "respaldo"
        getattr(self.respaldo, self._metodo)(contenido)

    def _fallo(self, error, contenido):
        _aviso(f"falló al mostrar el aviso ({type(error).__name__}: {error}); se usa el panel de siempre")
        self.roto = True
        try:
            self.ui.ocultar_tarjeta()
            self.ui.ocultar_telefono()
        except Exception:
            pass
        self.modo = "respaldo"
        getattr(self.respaldo, self._metodo)(contenido)

    def _sonar(self):
        try:
            from frontend import audio
            audio.obtener().efecto("mensaje_civitas", VOLUMEN_SONIDO)
        except Exception:
            pass


# ----------------------------------------------------------------------------- teclas

def envolver_tecla(control, vista):
    """Capa fina sobre control.tecla (tarjeta abierta y scroll de la revisión). Devuelve la función original."""
    original = control.tecla

    def tecla(key, desde_apertura_s=None):
        if control.abierto() and vista.tarjeta_abierta():
            if key == "escape" or key == control.tecla_abrir:
                return original(key, desde_apertura_s)
            if key in TECLAS_ENTENDIDO and (desde_apertura_s is None or desde_apertura_s >= 0.25):
                vista.entender()
            return True
        if control.abierto() and vista.telefono_abierto() and getattr(control, "fase", None) in FASES_SCROLL:
            if key in TECLAS_SUBIR:
                vista.desplazar(-1)
                return True
            if key in TECLAS_BAJAR:
                vista.desplazar(1)
                return True
        return original(key, desde_apertura_s)

    control.tecla = tecla
    return original


# ----------------------------------------------------------------------------- enganche

def _explicaciones():
    if not at.tarjetas_activas():
        return {}
    try:
        return at.cargar_explicaciones()
    except ValueError as error:
        _aviso(f"tarjetas desactivadas: {error}")
        return {}


def _envolver(vigia, escena_mundo, fabrica_ui, de):
    if not at.telefono_grande_activo():
        return None
    try:
        control = vigia.control
        canales = at.cargar_canales()
        explicaciones = _explicaciones()
        vista = VistaTelefono(control, control.vista, escena_mundo, canales, explicaciones, None, de=de)
        vista.ui = (fabrica_ui or _ui_compartida)(escena_mundo, vista)
        envolver_tecla(control, vista)
        control.vista = vista
        vigia.vista = vista
        return vista
    except Exception as error:
        _aviso(f"no instalado en {de} ({type(error).__name__}: {error}); queda el panel de siempre")
        return None


def envolver_habitos(vigia, escena_mundo, fabrica_ui=None):
    """Cambia la vista de la bandeja de Civitas por el teléfono en grande. Devuelve la VistaTelefono o None."""
    return _envolver(vigia, escena_mundo, fabrica_ui, "habitos")


def envolver_dilemas(vigia, escena_mundo, fabrica_ui=None):
    """Lo mismo para los dilemas (K): cada dilema con canal en canales_avisos.json se ve en el teléfono."""
    return _envolver(vigia, escena_mundo, fabrica_ui, "dilemas")


_UIS = {}


def _ui_compartida(escena_mundo, vista):
    """Una sola ui (un teléfono) por escena para las dos bandejas: los clics van a la vista que la está usando."""
    ui = _UIS.get(id(escena_mundo))
    if ui is None or ui.escena is not escena_mundo:
        ui = _crear_ui(escena_mundo, vista)
        ui.escena = escena_mundo
        _UIS.clear()                     # una escena nueva (otra partida): la ui vieja muere con su escena
        _UIS[id(escena_mundo)] = ui
    return ui


# ----------------------------------------------------------------------------- ui de verdad (Ursina)

def _crear_ui(escena_mundo, vista_inicial):
    from ursina import Entity, camera, color

    from frontend import diseno_adaptable
    from frontend.marco_telefono import MarcoTelefono
    from frontend.tarjeta_aviso import TarjetaAviso
    from frontend.telefono_pantallas import (PanelLateral, PantallaChat, PantallaDM, PantallaFeed, PantallaMuro,
                                             PantallaNotificaciones, PantallaRectificar)

    class UITelefono:

        def __init__(self):
            self.vista = vista_inicial
            self.escena = escena_mundo

            def clic(n):
                self.vista.control.clic(n)

            def marcar(n):
                marcar_control = getattr(self.vista.control, "marcar", None)
                if marcar_control is not None:
                    marcar_control(n)

            self.raiz = Entity(parent=camera.ui, enabled=False, z=-0.06)
            self.fondo = Entity(parent=self.raiz, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 205), z=0.05)
            self.lateral = PanelLateral(clic, parent=self.raiz, position=(tgc.LATERAL_X, 0, -0.01))
            self.marco = MarcoTelefono(al_ayuda=lambda: self.vista.ayuda(), parent=self.raiz)
            pantalla = self.marco.pantalla
            chat = PantallaChat(clic, parent=pantalla)
            self.pantallas = {"dm": PantallaDM(marcar, clic, parent=pantalla),
                              "muro": PantallaMuro(marcar, clic, parent=pantalla),
                              "rectificar": PantallaRectificar(marcar, clic, parent=pantalla),
                              "grupo": chat, "cadena": chat,
                              "notificaciones": PantallaNotificaciones(clic, parent=pantalla),
                              "feed": PantallaFeed(parent=pantalla)}
            self.tarjeta = TarjetaAviso(lambda: self.vista.entender())
            self.tarjeta.z = Z_TARJETA            # la ayuda («?») sale por delante del teléfono abierto
            diseno_adaptable.ajustar_escala(self.raiz)
            self.carrusel = _instalar_carrusel(escena_mundo)

        def _rect_icono(self):
            try:
                icono = escena_mundo.hud.telefono_ui.icono
                x, y, _z = icono.get_position(relative_to=camera.ui)
                factor = self.raiz.scale_x or 1.0
                return (x / factor, y / factor, icono.scale_x / factor, icono.scale_y / factor)
            except Exception:
                return None

        def mostrar_telefono(self, datos, lateral, abrir, hora):
            self.raiz.enabled = True
            self.fondo.enabled = True
            elegida = self.pantallas[datos["canal"]]
            for pantalla in set(self.pantallas.values()):
                if pantalla is not elegida:
                    pantalla.ocultar()
            elegida.mostrar(datos)
            self.lateral.mostrar(lateral)
            self.marco.fijar_hora(hora)
            if abrir or not self.marco.enabled:
                self.marco.abrir(self._rect_icono())

        def ocultar_telefono(self):
            self.lateral.ocultar()
            self.fondo.enabled = False

            def apagar():
                if not self.vista.telefono_abierto():
                    self.raiz.enabled = False

            if self.raiz.enabled:
                self.marco.cerrar(apagar)

        def mostrar_tarjeta(self, datos):
            self.tarjeta.mostrar(datos)

        def ocultar_tarjeta(self):
            self.tarjeta.ocultar()

        def desplazar(self, pasos):
            return self.lateral.desplazar(pasos)

    return UITelefono()


# ----------------------------------------------------------------------------- carrusel de la pausa

def orden_carrusel(explicaciones):
    """Las tarjetas en el orden de at.TIPOS (solo las que existen)."""
    return [explicaciones[t] for t in at.TIPOS if t in explicaciones]


class Carrusel:
    """Índice del carrusel de tarjetas (puro). pasar(+1 / -1) da la vuelta."""

    def __init__(self, tarjetas):
        self.tarjetas = list(tarjetas)
        self.indice = 0

    def pasar(self, paso):
        if self.tarjetas:
            self.indice = (self.indice + paso) % len(self.tarjetas)
        return self.actual()

    def actual(self):
        return self.tarjetas[self.indice] if self.tarjetas else None


def _instalar_carrusel(escena):
    """Botón «Avisos de Civitas» en la pausa, debajo de «Cómo se juega», que abre todas las tarjetas. Nunca rompe nada:
    si falla, avisa por stderr y no hay botón."""
    try:
        from ursina import Entity

        from frontend import menu_pausa
        from frontend.componentes import a_unidades
        from frontend.componentes import boton_piel_secundario
        from frontend.tarjeta_aviso import TarjetaAviso

        estado = Carrusel(orden_carrusel(at.cargar_explicaciones()))
        if not estado.tarjetas:
            return None

        def pintar():
            tarjeta.mostrar(estado.actual(), carrusel=(estado.indice, len(estado.tarjetas)))

        def pasar(paso):
            estado.pasar(paso)
            pintar()

        tarjeta = TarjetaAviso(lambda: tarjeta.ocultar(), al_pasar=pasar)
        tarjeta.z = Z_CARRUSEL                # por delante del menú de pausa (menu_pausa.Z_FRENTE = -50)

        def abrir():
            estado.indice = 0
            pintar()

        class TeclasCarrusel(Entity):

            def input(self, key):
                if not tarjeta.abierta():
                    return
                if key in ("right arrow", "d"):
                    pasar(1)
                elif key in ("left arrow", "a"):
                    pasar(-1)
                elif key in ("enter", "space", "numpad enter"):
                    tarjeta.ocultar()

            def update(self):
                if tarjeta.abierta() and not getattr(escena, "en_pausa", False):
                    tarjeta.ocultar()

        teclas = TeclasCarrusel(parent=tarjeta.parent)
        # Esc cierra el carrusel y no la pausa (como cualquier panel registrado)
        escena.registrar_bloqueador(tarjeta.abierta, tarjeta.ocultar)
        posicion = (escena.menu_pausa.posicion_extra(1) if hasattr(escena.menu_pausa, "posicion_extra")  # VIS-005
                    else (menu_pausa.ANCHO / 2 + 0.04 + 0.15, 0.12, -0.001))
        boton = boton_piel_secundario("Avisos de Civitas", al_clic=abrir, ancho=0.30, alto=a_unidades(50),
                                      tamano_fuente_px=20, parent=escena.menu_pausa, position=posicion)
        return {"tarjeta": tarjeta, "boton": boton, "teclas": teclas, "estado": estado, "abrir": abrir}
    except Exception as error:
        _aviso(f"botón «Avisos de Civitas» no instalado ({type(error).__name__}: {error})")
        return None

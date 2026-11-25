# Tutoriales de la bandeja de Civitas (tecla L: estafas, publicar foto, tiempo de pantalla), de Rectificar y de los Dilemas.
# Los de la bandeja salen antes de abrirla; el de los Dilemas YA NO sale al abrir K: solo desde la pausa («Cómo se juega»).
#
# CÓMO SE ENGANCHA. `instalar(conexion, escena_mundo)` envuelve el `abrir` de los dos controles reales (conexion.habitos_ui y
# conexion.dilemas_ui) SIN editar registro_habitos.py ni registro_dilemas.py: justo antes de abrir el panel de verdad, si toca el
# tutorial de ese tipo, se enseña primero y, al terminar, se abre el panel real. Nunca encima de otro bloqueador (si había algo
# abierto, el control real ya no llega a abrir) y se registra como bloqueador de la escena: controles congelados y reloj parado.
#
# CÓMO SE JUEGA SIN CONSECUENCIAS. El tutorial usa un SEGUNDO panel real (el mismo código: registro_habitos._crear_vigia /
# registro_dilemas._crear_vigia) con un control propio y un FLUJO DE DEMO: no es el flujo de la partida, no aplica planes, no toca
# la billetera, los indicadores, la cola de efectos, el GameState ni el reloj. Las monedas que «salen de la billetera» son solo la
# animación de la vista (frontend/civitas_visual.py): no se descuenta nada. Los eventos de demo (backend/datos/casos_demo) nunca los
# carga la partida. Las capas visuales de Civitas y de Rectificar envuelven el panel de demo igual que el de verdad.
#
# LIMITACIÓN CONOCIDA: con el «teléfono grande» (ALCALDE_TELEFONO_GRANDE) el jugador ve estos avisos en el teléfono; la demo se
# enseña con el panel de siempre (con sus capas visuales). Así no se mezcla con la tarjeta de primera vez del teléfono ni con su
# estado guardado en la partida.

from pathlib import Path
from types import SimpleNamespace

from backend.logica import habitos_digitales as hd

RUTA_CIVITAS = Path(__file__).resolve().parent.parent / "backend" / "datos" / "casos_demo" / "tutorial_civitas.json"
HORA_DEMO = "hoy 20:00"
ID_DILEMAS = "dilemas"           # tutorial guiado de los dilemas: solo desde la pausa
MINUTOS_FEED_DEMO = 30

# Lo que esta vista necesita del controlador (frontend/registro_tutorial_mision.py) se lo da él con conectar(): una vista no
# importa controladores (contrato MVC, R3 de tests/test_arquitectura_mvc.py). Sin conectar no se abre ningún tutorial.
_CONTROL = {}


def conectar(**funciones):
    _CONTROL.update(funciones)


def _controlador():
    """Las funciones conectadas (toca, abrir_si_toca, crear_vigia_*) o None si el controlador aún no las puso."""
    return SimpleNamespace(**_CONTROL) if "toca" in _CONTROL else None


# ---------------------------------------------------------------- flujos de demo (puros: no tocan nada de la partida)

class FlujoDemoBandeja:
    """Lo mínimo que ControlHabitos le pide al flujo, sobre datos de demo. `tipo`: estafa | publicar | rectificar | feed."""

    def __init__(self, tipo):
        self.tipo = tipo
        estafas, publicaciones = hd.cargar_eventos(RUTA_CIVITAS)
        self.evento = {"estafa": estafas[0] if estafas else None, "publicar": publicaciones[0] if publicaciones else None}.get(tipo)
        self.minutos = 0
        self.respuestas = []

    def partida_terminada(self):
        return False

    def jugador_activo(self):
        raise AttributeError("sin jugador: es una demo")

    # -- Mensaje de la bandeja --

    def evento_pendiente(self):
        if self.tipo == "rectificar":
            return rectificar_demo()
        if self.evento is None:
            return None
        e = self.evento
        decisiones = hd.DECISIONES_ESTAFA if e.tipo == "estafa" else hd.DECISIONES_PUBLICAR
        return {"tipo": e.tipo, "id": e.id, "titulo": e.titulo, "remitente": e.remitente, "texto": e.texto,
                "hasta_texto": HORA_DEMO, "elementos": [{"id": x.id, "texto": x.texto} for x in e.elementos],
                "opciones": [{"id": d, "etiqueta": e.etiquetas[d]} for d in decisiones]}

    def responder_evento(self, marcas, decision):
        if self.tipo == "rectificar":
            resultado = responder_rectificar_demo(marcas, decision)
        else:
            e = self.evento
            plan = (hd.plan_estafa(e, marcas, decision, 0.0, 100) if e.tipo == "estafa"
                    else hd.plan_publicacion(e, marcas, decision, 0.0))
            revision, calidad = hd.calificar(e, marcas)
            resultado = {"tipo": e.tipo, "id": e.id, "titulo": e.titulo, "decision": decision, "texto": plan.texto,
                          "perdida": plan.perdida, "calidad": round(calidad, 2), "llega": bool(plan.retardados),
                          "revision": [{"texto": x.texto, "marcado": m, "acertado": ok, "explicacion": x.explicacion,
                                        "debia_marcarse": x.marcar} for x, m, ok in revision]}
        self.respuestas.append(resultado)               # solo se recuerda aquí: no se aplica NADA
        return resultado

    # -- Feed --

    def deslizar_feed(self):
        self.minutos += MINUTOS_FEED_DEMO
        return {"texto": hd.FEED[(self.minutos // MINUTOS_FEED_DEMO - 1) % len(hd.FEED)], "pista": False,
                "minutos_hoy": self.minutos, "hora_texto": HORA_DEMO}

    def tiempo_pantalla_hoy(self):
        return self.minutos


def rectificar_demo():
    return {"tipo": "rectificar", "id": "tutorial_rectificar", "titulo": "Compartiste algo que no era cierto",
            "remitente": "Tu publicación de ayer", "texto": "«Dicen que el comedor del barrio cierra el lunes. ¡Pásalo!»",
            "hasta_texto": HORA_DEMO,
            "elementos": [{"id": "fuente", "texto": "No tenías la fuente original"},
                          {"id": "prisa", "texto": "Lo reenviaste sin leer el comunicado"},
                          {"id": "hora", "texto": "Lo publicaste de noche (esto no es el error)"}],
            "opciones": [{"id": "rectificar", "etiqueta": "Rectificar en público"},
                         {"id": "borrar", "etiqueta": "Borrarla sin decir nada"},
                         {"id": "defender", "etiqueta": "Defender lo que dijiste"}]}


EVIDENCIAS_RECTIFICAR = {"fuente": "Sin fuente, un rumor es solo un rumor.",
                         "prisa": "Reenviar sin leer es lo que hace que un error se multiplique.",
                         "hora": "La hora de publicar no cambia que fuera falso."}
TEXTOS_RECTIFICAR = {"rectificar": "Corregiste en público: duele un momento, pero baja el daño y mejora tu fama.",
                     "borrar": "Borrarla no deshace el daño: ya hay capturas y reaparece.",
                     "defender": "Defender el error lo multiplica: más gente lo comparte."}


def responder_rectificar_demo(marcas, decision):
    debe = {"fuente", "prisa"}
    revision = [{"texto": f"{e['texto']}: {EVIDENCIAS_RECTIFICAR[e['id']]}", "marcado": e["id"] in marcas,
                 "acertado": (e["id"] in marcas) == (e["id"] in debe), "explicacion": EVIDENCIAS_RECTIFICAR[e["id"]],
                 "debia_marcarse": e["id"] in debe} for e in rectificar_demo()["elementos"]]
    aciertos = sum(r["acertado"] for r in revision)
    return {"tipo": "rectificar", "id": "tutorial_rectificar", "titulo": "Compartiste algo que no era cierto",
            "decision": decision, "texto": TEXTOS_RECTIFICAR[decision], "perdida": 0,
            "calidad": round(aciertos / len(revision), 2), "llega": decision != "rectificar", "revision": revision}


class FlujoDemoDilema:
    def __init__(self):
        self._oferta = {"id": "tutorial_dilema", "titulo": "Un mensaje que no sabes si compartir",
                        "situacion": "Un vecino te manda una captura sobre el agua del barrio. Todos en el grupo la están reenviando.",
                        "hasta": 0, "hasta_texto": HORA_DEMO,
                        "opciones": [{"id": "a", "etiqueta": "Reenviarla: por si acaso", "deltas": {}, "confianza": {}},
                                     {"id": "b", "etiqueta": "Preguntar de dónde salió antes de compartir", "deltas": {}, "confianza": {}},
                                     {"id": "c", "etiqueta": "Dejarla pasar sin decir nada", "deltas": {}, "confianza": {}}]}
        self.respuestas = []

    def partida_terminada(self):
        return False

    def jugador_activo(self):
        raise AttributeError("sin jugador: es una demo")

    def dilema_pendiente(self):
        return self._oferta

    def responder_dilema(self, opcion_id):
        textos = {"a": "Reenviaste sin comprobar: el rumor llegó a más gente.",
                  "b": "Preguntaste primero: el grupo se calmó y alguien encontró la fuente.",
                  "c": "No hiciste nada: el rumor siguió, pero no lo empujaste tú."}
        if opcion_id not in textos:
            return None
        resultado = {"dilema": "tutorial_dilema", "opcion": opcion_id, "texto": textos[opcion_id], "deltas": {}, "confianza": {},
                     "llega": True}
        self.respuestas.append(resultado)
        return resultado


class EscenaDemo:
    """La escena del mundo, pero con el flujo de demo: lo único que cambia para el panel de demo."""

    enabled = True
    en_pausa = False
    online = None
    _cinematica = False

    def __init__(self, real, flujo):
        self._real = real
        self.flujo = flujo

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)

    def controles_bloqueados(self):
        return False

    def _sincronizar_raton(self):
        self._real._sincronizar_raton()


# ---------------------------------------------------------------- adaptadores (misma interfaz que los demás)

def _destruir_capas(control):
    """Destruye lo que las capas visuales (Civitas, Rectificar, Dilemas) colgaron de la camera.ui para el panel de demo."""
    from frontend.componentes import destruir_arbol
    vista = getattr(control, "vista", None)
    visto = 0
    while vista is not None and visto < 6:
        visto += 1
        for nombre in ("telefono", "publicacion", "ayer", "burbujas"):
            entidad = vista.__dict__.get(nombre)
            if entidad is not None:
                try:
                    destruir_arbol(entidad)
                except Exception:                      # noqa: BLE001  limpieza de mejor esfuerzo
                    pass
        vista = vista.__dict__.get("_original")


class AdaptadorBandeja:
    """Estafas, publicar foto, tiempo de pantalla y rectificar sobre un segundo panel real de la bandeja."""

    TIPO = {"civitas_estafas": "estafa", "civitas_foto": "publicar", "civitas_pantalla": "feed", "rectificar": "rectificar"}

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        self.real = (contexto or {})["escena"]
        self.tipo = self.TIPO[id_]
        self.vigia = None
        self.control = None
        self._clave_turno = None
        self._al_acertar = self._al_fallar = None

    def crear_vista(self, padre, al_terminar):
        from frontend import banderas_visuales as bv
        escena = EscenaDemo(self.real, FlujoDemoBandeja(self.tipo))
        vigia = _CONTROL["crear_vigia_habitos"](escena)
        vigia.input = lambda key: None                    # las teclas las manda el tutorial, no el panel por su cuenta
        vigia.vista.chip = lambda *a, **k: None           # sin chip «L · Civitas» de la demo
        control = vigia.control
        # Las mismas capas visuales que verá el jugador (monedas, lupa, publicación viva...), sin avisos del día siguiente.
        for modulo, clase in (("frontend.civitas_visual", "VistaCivitas"), ("frontend.rectificar_visual", "VistaRectificar")):
            try:
                import importlib
                m = importlib.import_module(modulo)
                if m.activo():
                    vista_clase = getattr(m, clase)
                    bv.envolver_vista(control, vista_clase, lambda v, c=vista_clase: c(v, control, self.real))
            except Exception as error:                   # noqa: BLE001  sin esa capa: queda el panel de siempre
                bv.avisar_una_vez(f"tutorial_{self.id}_{clase}", error)
        self.vigia, self.control = vigia, control
        control.abrir()
        return vigia

    @property
    def panel(self):
        return self.vigia.vista.panel

    def elemento(self, vista, foco):
        panel = self.panel
        fase = self.control.fase
        piezas = panel.lineas if fase == "revision" else panel.filas
        if foco < len(piezas) and piezas[foco].enabled:
            return piezas[foco]
        return getattr(panel, "marco", None)

    def elemento_tecla(self, vista, k):
        return self.elemento(vista, int(k) - 1) if str(k).isdigit() and self.control.fase in ("marcar", "decidir") else None

    def poner_foco(self, vista, foco):
        """Las filas se eligen por número."""

    def enviar_tecla(self, vista, k):
        if k in ("space", "down arrow", "s") and self.control.fase == "feed":
            self.control.tecla(k, None)
        elif k.isdigit() or k in ("enter", "backspace"):
            self.control.tecla(k, None)

    def error(self, vista, paso):
        """El error a propósito de las bandejas de marcar: marca una zona normal (la siguiente tecla la desmarca)."""
        self.control.marcar(paso["foco"] + 1)

    def avanzar_juego(self, vista, dt):
        """El panel avanza solo (update del vigía de demo)."""

    def avanzar_visual(self, vista, dt):
        """Ídem."""

    def camara(self, vista, paso):
        """Sin cámara."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        """«Ahora tú»: solo vale marcar el elemento señalado; marcar otro no cambia nada y se explica."""
        control = self.control
        correcto = control._evento["elementos"][paso["foco"]]["id"]
        marcar = control.marcar

        def marcar_puerta(numero):
            elementos = control._evento["elementos"]
            if not 1 <= numero <= len(elementos) or elementos[numero - 1]["id"] != correcto:
                al_fallar()
                return False
            hecho = marcar(numero)
            if hecho:
                al_acertar()
            return hecho

        control.marcar = marcar_puerta

    def cerrar(self, vista):
        vigia, self.vigia = self.vigia, None
        if vigia is None:
            return
        try:
            vigia.control.cerrar()
        except Exception:                              # noqa: BLE001  limpieza de mejor esfuerzo
            pass
        control = vigia.control
        control.__dict__.pop("marcar", None)
        _destruir_capas(control)
        from frontend.componentes import destruir_arbol
        try:
            raiz = vigia.vista.panel
            destruir_arbol(raiz)
            chip = getattr(vigia.vista, "chip_entidad", None)
            if chip is not None:
                destruir_arbol(chip)
        except Exception:                              # noqa: BLE001
            pass
        destruir_arbol(vigia)


class AdaptadorDilema:
    """Dilemas (K): un segundo panel real con un dilema de demo; el resultado es el panel «Mañana…» de siempre."""

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        self.real = (contexto or {})["escena"]
        self.vigia = None
        self.control = None

    def crear_vista(self, padre, al_terminar):
        from frontend import banderas_visuales as bv
        escena = EscenaDemo(self.real, FlujoDemoDilema())
        vigia = _CONTROL["crear_vigia_dilemas"](escena)
        vigia.input = lambda key: None
        vigia.vista.chip = lambda *a, **k: None
        control = vigia.control
        try:
            from frontend import dilemas_visual
            if dilemas_visual.activo():
                bv.envolver_vista(control, dilemas_visual.VistaDilemaVisual,
                                  lambda v: dilemas_visual.VistaDilemaVisual(v, control, self.real))
        except Exception as error:                       # noqa: BLE001
            bv.avisar_una_vez("tutorial_dilemas_visual", error)
        self.vigia, self.control = vigia, control
        control.abrir()
        return vigia

    def elemento(self, vista, foco):
        panel = self.vigia.vista.panel
        filas = getattr(panel, "botones", None) or getattr(panel, "filas", None) or []
        return filas[foco] if foco < len(filas) and filas[foco].enabled else getattr(panel, "marco", None)

    def elemento_tecla(self, vista, k):
        return self.elemento(vista, int(k) - 1) if str(k).isdigit() else None

    def poner_foco(self, vista, foco):
        """Se elige por número."""

    def enviar_tecla(self, vista, k):
        if k.isdigit():
            self.control.tecla(k, None)

    def error(self, vista, paso):
        """Sin error a propósito."""

    def avanzar_juego(self, vista, dt):
        """El panel avanza solo."""

    def avanzar_visual(self, vista, dt):
        """Ídem."""

    def camara(self, vista, paso):
        """Sin cámara."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        raise NotImplementedError("los dilemas no tienen «Ahora tú»")

    def cerrar(self, vista):
        vigia, self.vigia = self.vigia, None
        if vigia is None:
            return
        try:
            vigia.control.cerrar()
        except Exception:                              # noqa: BLE001
            pass
        _destruir_capas(vigia.control)
        from frontend.componentes import destruir_arbol
        try:
            destruir_arbol(vigia.vista.panel)
            chip = getattr(vigia.vista, "chip_entidad", None)
            if chip is not None:
                destruir_arbol(chip)
        except Exception:                              # noqa: BLE001
            pass
        destruir_arbol(vigia)


ADAPTADORES = {"civitas_estafas": AdaptadorBandeja, "civitas_foto": AdaptadorBandeja, "civitas_pantalla": AdaptadorBandeja,
               "rectificar": AdaptadorBandeja, "dilemas": AdaptadorDilema}


# ---------------------------------------------------------------- enganche con los controles reales

def id_de_evento(evento):
    """Id del tutorial del mensaje pendiente de la bandeja (None si no hay mensaje: es el feed de tiempo de pantalla)."""
    from backend.logica import tutorial_mision as logica
    if evento is None:
        return "civitas_pantalla"
    if evento.get("tipo") == "rectificar":
        return "rectificar"
    return logica.id_tutorial({"evento_civitas": {"estafa": "estafa", "publicar": "foto"}.get(evento.get("tipo"))})


def instalar(conexion, escena_mundo):
    """Envuelve `abrir` de los controles reales. Devuelve el estado (para pruebas) o None si no hay controles."""
    rtm = _controlador()
    if rtm is None:
        return None

    estado = {"tutorial": None}

    def abierto():
        t = estado["tutorial"]
        return t is not None and not t.cerrado

    def cerrar():
        t = estado["tutorial"]
        if t is not None and not t.cerrado:
            t.saltar_todo()

    escena_mundo.registrar_bloqueador(abierto, cerrar)      # controles congelados y reloj parado (motivo PANEL)

    def envolver(control, id_de):
        original = control.abrir

        def abrir():
            if abierto():
                return True
            if _abrir_tutorial(control, id_de):
                return True
            return original()                         # sin tutorial (o si falló): el panel de verdad, como hoy

        def _abrir_tutorial(control, id_de):
            try:
                id_ = id_de(control)
                if id_ is None or not rtm.toca(id_):
                    return False
                from ursina import camera

                def al_terminar(saltado, fallo):
                    from frontend.componentes import destruir_arbol
                    t, estado["tutorial"] = estado["tutorial"], None
                    if t is not None:
                        try:
                            destruir_arbol(t)
                        except Exception:             # noqa: BLE001
                            pass
                    original()                        # y ahora, el panel de verdad

                estado["tutorial"] = rtm.abrir_si_toca(camera.ui, id_, al_terminar, contexto={"escena": escena_mundo})
                return estado["tutorial"] is not None
            except Exception:                         # noqa: BLE001  nunca impide abrir el panel real
                return False

        control.abrir = abrir

    def ver_dilemas():
        """Tutorial guiado de los dilemas desde la pausa («Cómo se juega»): siempre (aunque ya se haya visto), con el flujo
        de demo. No abre el panel real al terminar ni toca la partida. True si se abrió."""
        if abierto():
            return False
        try:
            from ursina import camera

            def al_terminar(saltado, fallo):
                from frontend.componentes import destruir_arbol
                t, estado["tutorial"] = estado["tutorial"], None
                if t is not None:
                    try:
                        destruir_arbol(t)
                    except Exception:                 # noqa: BLE001
                        pass
                try:
                    escena_mundo._sincronizar_raton()
                except Exception:                     # noqa: BLE001
                    pass

            estado["tutorial"] = rtm.abrir_si_toca(camera.ui, ID_DILEMAS, al_terminar, forzar_ver=True,
                                                   contexto={"escena": escena_mundo})
            return estado["tutorial"] is not None
        except Exception as error:                    # noqa: BLE001
            from frontend import banderas_visuales as bv
            bv.avisar_una_vez("tutorial_dilemas_pausa", error)
            return False

    estado["ver_dilemas"] = ver_dilemas
    habitos = getattr(conexion, "habitos_ui", None)
    if habitos is not None:
        def id_habitos(control):
            if control.pendiente() is None:
                return "civitas_pantalla" if hd.tiempo_pantalla_activo() else None
            return id_de_evento(control.pendiente())
        envolver(habitos, id_habitos)
    # Dilemas (K o el teléfono): ya NO se envuelven. Al llegar un dilema sale solo la tarjeta de primera vez del teléfono
    # («Lo que circula en tu red» y compañía) y después el dilema real; el tutorial guiado queda en la pausa
    # («Cómo se juega» › Dilemas), que llama a `conexion.tutorial_dilemas`.
    try:
        conexion.tutorial_dilemas = ver_dilemas
    except Exception:                                 # noqa: BLE001  conexión sin atributos libres (pruebas)
        pass
    return estado

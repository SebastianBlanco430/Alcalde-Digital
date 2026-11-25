# Rádio Comunitária en el juego real (hilo conductor, docs/HILO_CONDUCTOR.md). main.py la carga con
# extensiones.aplicar(..., modulos=MODULOS_HILO) DESPUÉS de las extensiones de siempre (necesita el vigía del reloj de
# frontend/registro_reloj.py y su pintar_final). No edita ningún módulo ajeno: usa su API pública.
#
# Un vigía cuelga del HUD del mundo (solo corre con el mundo a la vista) y, en cada frame:
#   1. Reconoce la partida (flujo nuevo = ControlRadio nuevo) y RETIENE la noche (flujo.retener_noches(True)): a las
#      20:00 el reloj espera a la radio en vez de saltar solo.
#   2. Pregunta a ControlRadio (frontend/radio_calculos.py) si toca emitir, con «libre» = el motivo de pausa del vigía del
#      reloj es None (sin minijuego, diálogo, dilema, teléfono, mapa, pausa, cinemática ni fundido).
#   3. Emite (frontend/radio_emision.py) registrado como bloqueador de la escena: el reloj se para (motivo PANEL), los
#      controles se congelan y Escape la salta. La de la noche lleva la mañana del día siguiente: al poner la primera
#      viñeta de la mañana se llama a flujo.pasar_noche() (el cielo amanece detrás del negro).
#      Tras la noche fija el contexto de los globos de los NPC (tema del día y resultado: globos.fijar_contexto_hilo).
#   4. PUENTE: envuelve escena_mundo.pintar_final; la primera vez que la partida termina emite UNA línea («puente») y
#      después deja pasar el final de siempre (cinemática o panel), sin cambiar sus textos.
# RED DE SEGURIDAD: si algo falla, se suelta la noche (retener_noches(False)) y el vigía se apaga; el juego sigue como sin
# radio. En línea no hay reloj: no hace nada.
#
# BANDERA: ALCALDE_HILO_RADIO=0 (o ALCALDE_HILO=0) -> registrar() no instala nada.

import sys

from backend.logica import globos, modo_feria, radio_guion
from frontend import radio_calculos as rc


def _indicadores(flujo):
    estado = getattr(getattr(flujo, "sesion", None), "estado_partida", None)
    try:
        return estado.indicadores() if estado is not None else {}
    except Exception:
        return {}


def _quedaron_sin_verificar(flujo):
    leer = getattr(flujo, "resumen_dia", None)
    try:
        resumen = leer() if callable(leer) else None
    except Exception:
        resumen = None
    return bool(resumen and resumen.get("pendientes", 0) > 0)


def _con_radio(flujo):
    return (flujo is not None and getattr(flujo, "reloj", None) is not None
            and callable(getattr(flujo, "pasar_noche", None)) and callable(getattr(flujo, "noche_pendiente", None))
            and callable(getattr(flujo, "retener_noches", None)))


def _corto(flujo):
    return getattr(flujo, "ritmo_feria", None) is not None or modo_feria.activo()


class Radio:
    """Lógica del vigía sin ursina más allá de crear la emisión (`crear` inyectable en pruebas)."""

    def __init__(self, escena, conexion, guion, crear=None):
        from frontend import radio_emision
        self.escena, self.conexion, self.guion = escena, conexion, guion
        self.crear = crear or radio_emision.crear_emision
        self.control = rc.ControlRadio()
        self.entidad = None
        self.apagada = False
        self._clave = None
        self._puente_visto = None           # clave de la partida cuyo puente ya se emitió
        self._puente_en_curso = False

    # -- Estado --

    def abierta(self):
        return self.entidad is not None and not getattr(self.entidad, "terminada", True)

    def saltar(self):
        if self.abierta():
            self.entidad.saltar()

    def _libre(self, flujo):
        vigia = getattr(self.conexion, "vigia_reloj", None)
        control = getattr(vigia, "control", None)
        if control is not None and callable(getattr(control, "motivo_de_pausa", None)):
            return control.motivo_de_pausa(flujo) is None
        return not self.escena.controles_bloqueados()

    # -- Frame --

    def avanzar(self, dt):
        if self._puente_en_curso:
            _franja_desenlace(False)
        if self.apagada:
            return
        flujo = self.escena.flujo
        if not _con_radio(flujo) or getattr(self.escena, "online", None) is not None:
            return
        try:
            self._avanzar(flujo, dt)
        except Exception as error:
            self._apagar(flujo, error)

    def _avanzar(self, flujo, dt):
        clave = (id(flujo), id(flujo.reloj))
        if clave != self._clave:
            self._clave = clave
            self.control = rc.ControlRadio()
            flujo.retener_noches(True)
            globos.fijar_contexto_hilo(None, None)
        reloj = flujo.reloj
        accion = self.control.paso(dt, reloj.dia(), flujo.noche_pendiente(), flujo.partida_terminada(),
                                   self._libre(flujo))
        if accion is not None:
            self._emitir(flujo, *accion)

    def _emitir(self, flujo, tipo, dia):
        estado = radio_guion.estado_ciudad(_indicadores(flujo))
        rotulo = rc.rotulo_de(self.guion)
        lectura = self.guion.lectura
        if tipo == "noche":
            diario = flujo.diario_de(dia) if callable(getattr(flujo, "diario_de", None)) else []
            resultado = radio_guion.resultado_dia(diario)
            lineas = self.guion.noche(dia, resultado, _quedaron_sin_verificar(flujo), estado, corto=_corto(flujo))
            # Los NPC del día siguiente comentan el tema del día y lo que hizo el jugador (backend/logica/globos.py).
            globos.fijar_contexto_hilo(radio_guion.tema_dia(diario, self.guion.temas), resultado)
            # radio_momento: el fondo animado de frontend/radio_emision.py (noche estrellada, amanecer o atardecer).
            vinetas = rc.vinetas_de(lineas, rotulo, lectura, marca={"radio_momento": "noche"})
            manana = self.guion.manana(dia + 1, estado) if dia + 1 <= reloj_dias(flujo) else None
            if manana:
                vinetas += rc.vinetas_de([manana], rotulo, lectura,
                                         marca={"radio_manana": True, "radio_momento": "manana"})
        else:
            manana = self.guion.manana(dia, estado)
            vinetas = rc.vinetas_de([manana] if manana else [], rotulo, lectura, marca={"radio_momento": "manana"})
        if not vinetas:
            self._cerrar(flujo, tipo, dia)
            return
        self.control.empezar()

        def al_poner(vineta, _indice):
            if vineta.get("radio_manana"):
                flujo.pasar_noche()

        self.entidad = self.crear(self.escena, vinetas, lambda: self._cerrar(flujo, tipo, dia), al_poner)
        self._raton()

    def _cerrar(self, flujo, tipo, dia):
        # Saltar la emisión también pasa la noche (la viñeta de la mañana pudo no ponerse).
        if tipo == "noche" and flujo.noche_pendiente():
            flujo.pasar_noche()
        self.control.terminar(tipo, dia)
        self._raton()

    def _raton(self):
        sincronizar = getattr(self.escena, "_sincronizar_raton", None)
        if callable(sincronizar):
            sincronizar()

    def _apagar(self, flujo, error):
        self.apagada = True
        print(f"[radio] apagada ({type(error).__name__}: {error}); la noche se salta sola", file=sys.stderr)
        try:
            flujo.retener_noches(False)
            if flujo.noche_pendiente():
                flujo.pasar_noche()
        except Exception:
            pass

    # -- Puente con el final --

    # Devuelve True mientras la línea puente está en pantalla (el final de siempre espera); False cuando ya pasó.
    def puente(self, flujo):
        if self.apagada or not _con_radio(flujo) or getattr(self.escena, "online", None) is not None:
            return False
        clave = (id(flujo), id(flujo.reloj))
        if self._puente_visto == clave:
            return self._puente_en_curso
        self._puente_visto = clave
        texto = self.guion.puente(radio_guion.estado_ciudad(_indicadores(flujo)))
        if not texto:
            return False
        try:
            self._puente_en_curso = True
            vinetas = rc.vinetas_de([texto], rc.rotulo_de(self.guion), self.guion.lectura,
                                    marca={"radio_momento": "puente"})
            self.entidad = self.crear(self.escena, vinetas, self._fin_puente)
            self._raton()
            return True
        except Exception as error:
            self._puente_en_curso = False
            print(f"[radio] puente omitido ({type(error).__name__}: {error})", file=sys.stderr)
            return False

    def _fin_puente(self):
        self._puente_en_curso = False
        _franja_desenlace(True)
        self._raton()
        refrescar = getattr(self.escena, "refrescar", None)
        if callable(refrescar):
            refrescar()


# La franja del desenlace de frontend/recta_final_vista.py («Ciudad tomada…») solo se esconde con la cinemática del final
# en pantalla; durante el puente de la radio taparía su globo. Mientras dura el puente se esconde cada frame; al terminar
# se olvida lo pintado para que su vigía la vuelva a decidir (cinemática primero, después la franja). Nunca lanza.
def _franja_desenlace(repintar):
    try:
        from frontend import recta_final_vista
        vigia = recta_final_vista._instalado.get("vigia")
        if vigia is None:
            return
        if repintar:
            vigia._desenlace_visto = None
            return
        for nombre in ("franja", "franja_titulo", "franja_texto"):
            entidad = getattr(vigia, nombre, None)
            if entidad is not None:
                entidad.enabled = False
    except Exception:
        pass


def reloj_dias(flujo):
    leer = getattr(flujo.reloj, "dias", None)
    return leer() if callable(leer) else 7


def registrar(gestor, conexion, escena_mundo):
    if not radio_guion.activo():
        return None
    try:
        from ursina import Entity, time

        radio = Radio(escena_mundo, conexion, radio_guion.GuionRadio())
        escena_mundo.registrar_bloqueador(radio.abierta, radio.saltar)
        original = escena_mundo.pintar_final

        def pintar_final(flujo):
            if radio.puente(flujo):
                return True
            return original(flujo) if original is not None else False

        escena_mundo.pintar_final = pintar_final

        class VigiaRadio(Entity):
            def update(self):
                radio.avanzar(min(time.dt, 0.1))

        vigia = VigiaRadio(parent=escena_mundo.hud)
        vigia.radio = radio
        conexion.radio_hilo = radio
        return vigia
    except Exception as error:
        print(f"[radio] no instalada ({type(error).__name__}: {error})", file=sys.stderr)
        return None

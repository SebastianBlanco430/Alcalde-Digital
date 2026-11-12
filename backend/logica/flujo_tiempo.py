# FlujoConTiempo (modelo puro, sin ursina): envuelve el flujo de la partida (FlujoPartida con sus envoltorios de economía
# y GameState) y le añade el TIEMPO del plan final, sin tocar nada de lo que envuelve (mismo patrón que FlujoConEconomia y
# FlujoConGameState: lo que no está aquí se delega con __getattr__).
#
#   flujo.reloj                      RelojPartida de la partida (backend/logica/reloj_partida.py)
#   flujo.avanzar_tiempo(dt)         ÚNICO punto que llama el frontend, una vez por frame CON EL MUNDO ACTIVO (dt en s
#                                    reales). Avanza el reloj, aplica los efectos retardados vencidos y el costo de
#                                    aislamiento, y suaviza el ambiente. Devuelve la lista de avisos nuevos.
#   flujo.partida_terminada()        True si terminó el catálogo (como antes) O si el reloj completó el día 7
#   flujo.motivo_fin()               "tiempo" | "misiones" | None
#   flujo.final_partida()            el final de FlujoConGameState (índice por grupos) + "motivo", "dia" y "hora_texto";
#                                    None si la partida no tiene consecuencias (igual que antes: el frontend pinta el panel
#                                    de siempre)
#   flujo.resumen_final()            SIEMPRE un dict: el de final_partida() o, sin GameState, el de los tres indicadores
#                                    (evaluar_final_indicadores)
#   flujo.cola_efectos               ColaEfectos (efectos_retardados.py) o None con la bandera apagada
#   flujo.aislamiento                CostoAislamiento (costo_aislamiento.py) o None con la bandera apagada
#   flujo.ambiente()                 el Ambiente suavizado (ambiente_ciudad.py); flujo.ambiente_suave es el AmbienteSuave
#   flujo.avisos_retardados          avisos de causa-efecto pendientes de mostrar (lista de dicts, el más viejo primero)
#   flujo.ultimo_aviso_retardado     el último aviso (dict) o None
#   flujo.vaciar_avisos_retardados() entrega la lista y la deja vacía (lo llama el HUD cuando los muestra)
#   flujo.tiempo_a_dict() / flujo.restaurar_tiempo(datos)    guardado (claves opcionales de backend/logica/guardado.py)
#
# AVISO (dict JSON-serializable): {"clave", "mensaje", "deltas": {indicador: cambio}, "confianza": {grupo: cambio},
# "hora": hora absoluta, "hora_texto": «Día 3 · 14:30»}.
#
# CUÁNDO SE PROGRAMA UNA CONSECUENCIA: al cerrar una misión con completar_mision(resultado) se calcula su consecuencia
# diferida (efectos_retardados.consecuencia_de_mision) y se encola para 24-48 h de juego después. Cerrar cualquier misión
# (también las digitales) cuenta como «participar» para el costo de aislamiento.
#
# FIN POR TIEMPO: al completar el día 7 la partida termina aunque queden misiones (y aunque haya una activa). Los efectos
# retardados que seguían en la cola se aplican en ese momento («las consecuencias te alcanzan»): compartir sin verificar
# el último día no sale gratis.
#
# FINAL PONDERADO (equilibrio, docs/PLAN_FINAL.md §7): con GameState el final ya no sale solo de la confianza por grupo.
# El índice es PESO_CIUDAD · índice de los tres indicadores de la ciudad + (1 - PESO_CIUDAD) · índice de los grupos
# (ponderar_final). Motivo: los deltas por grupo están escalados a acertar TODO el catálogo (47 misiones en el mapa grande)
# y en 7 días se juegan 14-20, así que el final «bueno» era inalcanzable y «compartirlo todo» podía quedar «neutro» con la
# ciudad hundida. FINAL_PONDERADO = False (o ALCALDE_FINAL_PONDERADO=0) vuelve al final de antes (solo grupos).
#
# TRAS EL FIN POR TIEMPO la misión que quedaba abierta deja de ofrecerse: mision_actual() -> None, estado_mision() ->
# SIN_MISION y puede_interactuar() -> False (la E ya no entra a ningún edificio). hay_mision_activa() no cambia.
#
# EN LÍNEA: este envoltorio solo se crea para la partida local (main.py: crear_flujo). El flujo en línea
# (frontend/online_flujo.py) no pasa por aquí: no tiene reloj, ni efectos retardados, ni cambia el protocolo.

import os
import sys

from backend.logica import ambiente_ciudad, confianza_misiones, costo_aislamiento, efectos_retardados, etapas_final, reloj_partida
from backend.logica.estado_partida import NOMBRES_INDICADORES
from backend.logica.misiones import SIN_MISION

MAX_AVISOS = 20         # avisos sin leer que se conservan (los más viejos se descartan)

FINAL_PONDERADO = True  # el final con GameState mezcla confianza por grupo e indicadores de la ciudad (ponderar_final)
PESO_CIUDAD = 0.5       # peso del índice de la ciudad en el final ponderado (0 = solo grupos, como antes)

_PROPIOS = ("_flujo", "reloj", "cola_efectos", "aislamiento", "ambiente_suave", "avisos_retardados",
            "ultimo_aviso_retardado", "_indice_etapas", "_t_indice_etapas", "_etapa_vista")
PERIODO_INDICE_ETAPAS = 0.5     # s reales entre dos lecturas del índice para el ambiente (finales por etapas)


# Final a partir de los TRES indicadores de la ciudad, para partidas sin GameState (sin confianza por grupo). Reglas
# análogas a confianza_misiones.evaluar_final: el índice es el promedio de tres componentes 0-100 donde más es mejor
# (convivencia, confianza e «información» = 100 - desinformación); >= 70 bueno, 40-69 neutro, < 40 malo; y cualquier
# componente por debajo de 20 da final malo aunque el promedio sea alto. Devuelve un dict JSON-serializable:
#   {"final", "indice", "componentes": {...}, "indicadores": {...}, "componente_critico", "pasadas", "falladas",
#    "fuente": "indicadores"}
def evaluar_final_indicadores(indicadores, pasadas=0, falladas=0):
    faltan = [n for n in NOMBRES_INDICADORES if n not in indicadores]
    if faltan:
        raise ValueError(f"Faltan indicadores para evaluar el final: {faltan}.")
    componentes = {"convivencia": float(indicadores["convivencia"]), "confianza": float(indicadores["confianza"]),
                   "informacion": 100.0 - float(indicadores["desinformacion"])}
    indice = round(sum(componentes.values()) / len(componentes), 2)
    criticos = [c for c in componentes if componentes[c] < confianza_misiones.UMBRAL_GRUPO_CRITICO]
    critico = min(criticos, key=lambda c: componentes[c]) if criticos else None
    if critico is not None or indice < confianza_misiones.UMBRAL_NEUTRO:
        final = "malo"
    elif indice >= confianza_misiones.UMBRAL_BUENO:
        final = "bueno"
    else:
        final = "neutro"
    return {"final": final, "indice": indice, "componentes": componentes,
            "indicadores": {n: indicadores[n] for n in NOMBRES_INDICADORES}, "componente_critico": critico,
            "pasadas": int(pasadas), "falladas": int(falladas), "fuente": "indicadores"}



def final_ponderado_activo():
    """¿El final con GameState pondera la ciudad? ALCALDE_FINAL_PONDERADO=1/0 manda sobre FINAL_PONDERADO."""
    valor = os.environ.get("ALCALDE_FINAL_PONDERADO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(FINAL_PONDERADO)


# Final PONDERADO: mezcla el final por grupos (dict de confianza_misiones.evaluar_final) con el de los tres indicadores
# de la ciudad (evaluar_final_indicadores). índice = peso · ciudad + (1 - peso) · grupos; mismos umbrales (>= 70 bueno,
# 40-69 neutro, < 40 malo) y un grupo crítico sigue dando final malo. NO modifica `final`: devuelve una copia con
# "final" e "indice" recalculados y, además, "indice_grupos", "indice_ciudad", "componentes", "indicadores",
# "componente_critico" (informativo: el indicador de la ciudad por debajo de 20, o None) y "fuente": "ponderado".
def ponderar_final(final, indicadores, peso=PESO_CIUDAD):
    if isinstance(peso, bool) or not isinstance(peso, (int, float)) or not 0.0 <= peso <= 1.0:
        raise ValueError(f"peso inválido: {peso!r}; debe estar entre 0 y 1.")
    ciudad = evaluar_final_indicadores(indicadores, final.get("pasadas", 0), final.get("falladas", 0))
    indice = round(peso * ciudad["indice"] + (1.0 - peso) * final["indice"], 2)
    if final.get("grupo_critico") is not None or indice < confianza_misiones.UMBRAL_NEUTRO:
        clave = "malo"
    elif indice >= confianza_misiones.UMBRAL_BUENO:
        clave = "bueno"
    else:
        clave = "neutro"
    return dict(final, final=clave, indice=indice, indice_grupos=final["indice"], indice_ciudad=ciudad["indice"],
                componentes=ciudad["componentes"], indicadores=ciudad["indicadores"],
                componente_critico=ciudad["componente_critico"], fuente="ponderado")


class FlujoConTiempo:

    # `reloj`: RelojPartida (None = uno nuevo). `efectos` / `aislamiento`: True, False o None (= la bandera de su módulo).
    def __init__(self, flujo, reloj=None, efectos=None, aislamiento=None):
        self._flujo = flujo
        self.reloj = reloj if reloj is not None else reloj_partida.RelojPartida()
        con_efectos = efectos_retardados.activo() if efectos is None else bool(efectos)
        con_aislamiento = costo_aislamiento.activo() if aislamiento is None else bool(aislamiento)
        self.cola_efectos = efectos_retardados.ColaEfectos() if con_efectos else None
        self.aislamiento = costo_aislamiento.CostoAislamiento() if con_aislamiento else None
        self.ambiente_suave = ambiente_ciudad.AmbienteSuave()
        self.avisos_retardados = []
        self.ultimo_aviso_retardado = None
        self._indice_etapas = None          # último índice leído para el ambiente (finales por etapas)
        self._t_indice_etapas = 0.0
        self._etapa_vista = None            # última etapa (con histéresis) que se vio durante la partida

    # -- Tiempo --

    # Un frame con el mundo activo: `dt` segundos reales. Devuelve los avisos que nacieron en este paso.
    def avanzar_tiempo(self, dt):
        self.reloj.avanzar(dt)
        nuevos = self._procesar_tiempo()
        self.actualizar_ambiente(dt)
        return nuevos

    # Avanza `horas` de juego de golpe (pruebas, simulación, depuración). No suaviza el ambiente.
    def avanzar_horas(self, horas):
        self.reloj.avanzar_horas(horas)
        return self._procesar_tiempo()

    def pausar_tiempo(self):
        self.reloj.pausar()

    def reanudar_tiempo(self):
        self.reloj.reanudar()

    def _estado_partida(self):
        return getattr(getattr(self._flujo, "sesion", None), "estado_partida", None)

    def _game_state(self):
        return getattr(self._flujo, "game_state", None)

    def _procesar_tiempo(self):
        ahora = self.reloj.tiempo_absoluto()
        nuevos = []
        if self.cola_efectos is not None:
            limite = float("inf") if self.reloj.terminado() else ahora
            for _hora, efecto in self.cola_efectos.vencidos(limite):
                nuevos.append(self._aplicar(efecto, ahora))
        if self.aislamiento is not None:
            # Sin misión que atender (catálogo agotado) no hay nada que ignorar: esas horas no cuentan como ausencia.
            hay_mision = getattr(self._flujo, "hay_mision_activa", None)
            if callable(hay_mision) and not hay_mision():
                self.aislamiento.participar(ahora)
            cobro = self.aislamiento.avanzar(ahora)
            if cobro.puntos:
                aviso = self._aplicar(costo_aislamiento.efecto_de(cobro.puntos), ahora, anunciar=False)
                if cobro.aviso:
                    nuevos.append(self._anunciar(dict(aviso, mensaje=cobro.aviso)))
        return nuevos

    def _aplicar(self, efecto, ahora, anunciar=True):
        aviso = efectos_retardados.aplicar(efecto, self._estado_partida(), self._game_state(), ahora)
        aviso["hora_texto"] = reloj_partida.texto_de(ahora)
        return self._anunciar(aviso) if anunciar else aviso

    def _anunciar(self, aviso):
        self.avisos_retardados.append(aviso)
        del self.avisos_retardados[:-MAX_AVISOS]
        self.ultimo_aviso_retardado = aviso
        return aviso

    # Entrega los avisos pendientes (el más viejo primero) y deja la lista vacía. `ultimo_aviso_retardado` no se toca.
    def vaciar_avisos_retardados(self):
        avisos, self.avisos_retardados = self.avisos_retardados, []
        return avisos

    # -- Ambiente --

    def ambiente(self):
        return self.ambiente_suave.ambiente()

    # Acerca el ambiente suavizado al de los indicadores actuales (dt en s reales). Lo llama avanzar_tiempo; el frontend
    # puede llamarlo aparte si quiere seguir suavizando con el reloj en pausa.
    def actualizar_ambiente(self, dt):
        estado = self._estado_partida()
        if estado is None:
            return self.ambiente_suave.ambiente()
        game_state = self._game_state()
        confianzas = game_state.confianzas() if game_state is not None else None
        if not etapas_final.activo():
            return self.ambiente_suave.actualizar(dt, estado.indicadores(), confianzas)
        return self.ambiente_suave.actualizar(dt, estado.indicadores(), confianzas, indice=self._leer_indice_etapas(dt))

    # Finales por etapas: el índice (el real o el forzado) que mueve la salud del ambiente, leído como mucho cada
    # PERIODO_INDICE_ETAPAS s, y la etapa con histéresis que se lleva vista (la usa el final).
    def _leer_indice_etapas(self, dt):
        self._t_indice_etapas -= dt
        if self._indice_etapas is None or self._t_indice_etapas <= 0:
            self._t_indice_etapas = PERIODO_INDICE_ETAPAS
            self._indice_etapas = etapas_final.indice_de_flujo(self)
            if self._indice_etapas is not None:
                self._etapa_vista = etapas_final.etapa_de_indice(self._indice_etapas, self._etapa_vista)
        return self._indice_etapas

    # Con las etapas activas el final lo decide la ETAPA del índice (el forzado, si lo hay), no los umbrales de siempre ni
    # la regla del grupo crítico. Añade "etapa" al dict.
    def _final_por_etapa(self, final):
        if not etapas_final.activo():
            return final
        forzado = etapas_final.indice_forzado()
        etapa = etapas_final.etapa_de_indice(final["indice"] if forzado is None else forzado, self._etapa_vista)
        return dict(final, final=etapas_final.final_de_etapa(etapa), etapa=etapa)

    # -- Misiones: programar la consecuencia y contar la participación --

    def completar_mision(self, resultado):
        leer_mision = getattr(self._flujo, "mision_actual", None)
        mision = leer_mision() if leer_mision is not None else None      # antes de delegar: completar pasa el turno
        activo = self._flujo.completar_mision(resultado)
        self._tras_cerrar(mision, resultado)
        return activo

    # Misiones digitales (parkour / investigación): cerrarlas también es participar. Los argumentos se pasan tal cual
    # (FlujoConGameState no recibe ninguno; FlujoConEconomia y FlujoPartida reciben el game_state).
    def revisar_misiones_digitales(self, *argumentos):
        cerro = self._flujo.revisar_misiones_digitales(*argumentos)
        if cerro and self.aislamiento is not None:
            self.aislamiento.participar(self.reloj.tiempo_absoluto())
        return cerro

    def _tras_cerrar(self, mision, resultado):
        ahora = self.reloj.tiempo_absoluto()
        if self.aislamiento is not None:
            self.aislamiento.participar(ahora)
        if self.cola_efectos is None or mision is None:
            return
        try:        # la consecuencia diferida nunca puede impedir cerrar una misión
            consecuencia = efectos_retardados.consecuencia_de_mision(mision, resultado, ahora)
            if consecuencia is not None:
                self.cola_efectos.programar(*consecuencia)
        except (ValueError, KeyError) as error:
            print(f"[tiempo] consecuencia diferida no programada: {error}", file=sys.stderr)

    # -- Tras el fin por tiempo: la misión que quedaba abierta deja de ofrecerse (el HUD la retira y la E no hace nada) --

    def mision_actual(self):
        return None if self.reloj.terminado() else self._flujo.mision_actual()

    def estado_mision(self):
        return SIN_MISION if self.reloj.terminado() else self._flujo.estado_mision()

    def puede_interactuar(self):
        return not self.reloj.terminado() and self._flujo.puede_interactuar()

    # -- Fin de la partida --

    def partida_terminada(self):
        return self.reloj.terminado() or self._flujo.partida_terminada()

    def motivo_fin(self):
        if self.reloj.terminado():
            return "tiempo"
        return "misiones" if self._flujo.partida_terminada() else None

    def _datos_fin(self):
        return {"motivo": self.motivo_fin(), "dia": self.reloj.dia(), "hora_texto": self.reloj.hora_texto()}

    def final_partida(self):
        leer_final = getattr(self._flujo, "final_partida", None)
        final = leer_final() if callable(leer_final) else None
        if final is None:
            return None
        estado = self._estado_partida()
        if estado is not None and final_ponderado_activo():
            final = ponderar_final(final, estado.indicadores())
        return dict(self._final_por_etapa(final), **self._datos_fin())

    def resumen_final(self):
        final = self.final_partida()
        if final is not None:
            return final
        estado = self._estado_partida()
        indicadores = estado.indicadores() if estado is not None else {n: 50 for n in NOMBRES_INDICADORES}
        pasadas = getattr(self._flujo, "misiones_pasadas", lambda: [])()
        falladas = getattr(self._flujo, "misiones_falladas", lambda: [])()
        return dict(self._final_por_etapa(evaluar_final_indicadores(indicadores, len(pasadas), len(falladas))), **self._datos_fin())

    # -- Guardado --

    # Claves OPCIONALES del guardado: «reloj», «efectos_retardados», «aislamiento» y «ambiente». Las que no aplican
    # (bandera apagada) no se escriben.
    def tiempo_a_dict(self):
        datos = {"reloj": self.reloj.a_dict(), "ambiente": self.ambiente_suave.a_dict()}
        if self.cola_efectos is not None:
            datos["efectos_retardados"] = self.cola_efectos.a_dict()
        if self.aislamiento is not None:
            datos["aislamiento"] = self.aislamiento.a_dict()
        return datos

    # Restaura lo que traiga `datos` (el dict completo del guardado). TOLERANTE: una clave ausente (guardado anterior al
    # reloj) o dañada deja ese componente como recién creado (día 1, 08:00; cola vacía...) y se avisa por stderr; un
    # guardado nunca puede impedir jugar. La pausa del reloj no se restaura (la decide el frontend).
    def restaurar_tiempo(self, datos):
        datos = datos if isinstance(datos, dict) else {}
        self.reloj = self._leer(datos, "reloj", lambda d: reloj_partida.RelojPartida.desde_dict(d, self.reloj.seg_por_hora()),
                                reloj_partida.RelojPartida(self.reloj.seg_por_hora()))
        self.reloj.reanudar()
        if self.cola_efectos is not None:
            self.cola_efectos = self._leer(datos, "efectos_retardados", efectos_retardados.ColaEfectos.desde_dict,
                                           efectos_retardados.ColaEfectos())
        if self.aislamiento is not None:
            self.aislamiento = self._leer(datos, "aislamiento", costo_aislamiento.CostoAislamiento.desde_dict,
                                          costo_aislamiento.CostoAislamiento())
        self.ambiente_suave = self._leer(datos, "ambiente", ambiente_ciudad.AmbienteSuave.desde_dict,
                                         ambiente_ciudad.AmbienteSuave())
        self.avisos_retardados = []
        self.ultimo_aviso_retardado = None

    @staticmethod
    def _leer(datos, clave, leer, por_defecto):
        crudo = datos.get(clave)
        if crudo is None:
            return por_defecto
        try:
            return leer(crudo)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            print(f"[tiempo] «{clave}» del guardado no se pudo leer ({error}); se empieza de cero", file=sys.stderr)
            return por_defecto

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)

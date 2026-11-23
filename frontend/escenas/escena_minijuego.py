# Escena de los minijuegos de verificar (Ursina). Se abre en el MISMO punto donde hoy se abre la escena de juego
# (frontend/conexion_flujo.py) y recibe los mismos datos (jugador, estado, mision, al_terminar, grafo_social, marco, lugar).
# Elige el minijuego de la misión (backend/datos/minijuegos_asignacion.py), lo juega y, al terminar, traduce el «bien / mal» a las
# decisiones de siempre (backend/logica/minijuegos.cerrar_lote) y entrega a `al_terminar` el MISMO resultado del lote que entrega
# EscenaJuego: de ahí en adelante pago, confianza por grupo, efectos retardados, GameState y guardado no cambian.
#
# RESPALDO. Si algo falla al abrir o durante el juego (vista que no carga, excepción en una tecla...), la escena llama a
# `al_respaldo()` (que pone ConexionFlujo: reabre la misión en la escena de juego de siempre) y no vuelve a intervenir. Un error
# nunca deja la misión atascada.
#
# Marco de monitor y «caber» en la ventana: igual que EscenaJuego (MarcoPC, ESCALA_JUEGO, diseno_adaptable).
# Reloj: la misión sigue EN_MINIJUEGO mientras se juega, así que la pausa del reloj de 7 días que ya existe se mantiene.

import logging
import random

from ursina import Entity, Text, color, time

from backend.datos import minijuegos_asignacion as asignacion
from backend.datos import minijuegos_casos
from backend.datos import minijuegos_instrucciones as instrucciones
from backend.datos.nombres_visibles import glosar_texto
from backend.logica import consecuencia_graduada
from backend.logica import minijuegos as mj
from backend.logica.lote_mision import LoteMision
from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import BotonPrimario, a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb
from frontend.escenas.escena_base import Escena
from frontend.marco_pc import ESCALA_JUEGO, MarcoPC
from frontend.minijuegos import clase_de, ui
from frontend.panel_resultado_grafo import PanelResultadoGrafo

_registro = logging.getLogger(__name__)

ASPECTO = 16 / 9
DEMORA_CONTINUAR = 0.5          # s antes de aceptar Enter/Espacio en el banner (evita pulsaciones sueltas)
Y_BANNER = -0.365
ALTO_BANNER = 0.17
# Mismo ancho que el contenido de los minijuegos (base.ANCHO_UTIL): el banner queda alineado con las tarjetas de arriba.
ANCHO_BANNER = 1.62

# Presentación 3D: la oficina del lugar es una copia PROPIA de EscenaInterior (no la del gestor), creada la primera vez que
# un minijuego 3D la pide y reutilizada después. El paquete frontend/minijuegos_3d no importa escenas (capa MVC): se la pasa
# esta fábrica.
_interior_3d = {"escena": None}


def _fabrica_interior():
    escena = _interior_3d["escena"]
    if escena is None or escena.is_empty():
        from frontend.escenas.escena_interior import EscenaInterior
        escena = EscenaInterior(escala_tiempo=0)
        _interior_3d["escena"] = escena
    return escena


def _olvidar_salida_3d():
    try:
        from frontend.minijuegos_3d import estado
        estado.olvidar()
    except Exception:                            # noqa: BLE001
        pass


class EscenaMinijuego(Escena):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.marco = MarcoPC(parent=self.parent)
        diseno_adaptable.suscribir(self._al_cambiar_aspecto)
        self.fondo = Entity(parent=self, model="quad", color=rgb(estilo.COLOR_FONDO), scale=(ASPECTO, 1), z=0.2)
        self.contenido = None
        self.minijuego = None
        self.previa = None               # pantalla «Antes de empezar» (frontend/minijuegos/pantalla_previa.py)
        self.tutorial = None             # tutorial de la primera vez (frontend/registro_tutorial_mision.py)
        self.banner = None
        self.panel_resultado = PanelResultadoGrafo(parent=self, z=-0.3)
        self.usados = {}                 # ids de casos ya jugados por minijuego (para no repetir en la partida)
        self.vista3d = None              # presentación 3D (frontend/minijuegos_3d) mientras se juega; None = 2D de hoy
        self._lugar, self._marco_activo = "", False
        self._reiniciar()

    # -- Estado de una entrada --

    def _reiniciar(self):
        self._intento = getattr(self, "_intento", 0) + 1
        self.jugador = {}
        self.estado = None
        self.mision = None
        self.grafo_social = None
        self._al_terminar = None
        self._al_respaldo = None
        self.resultado = None
        self.cerrado = False
        self.en_respaldo = False
        self.minijuego_id = None
        self.lote = None
        self.t_banner = None
        self.t_panel = None
        self.t_previa = None
        self._clase = None
        self._clase3d = None
        self._caso = None
        self._azar = None

    def _limpiar_vista(self):
        self._cerrar_3d()
        if getattr(self, "tutorial", None) is not None:
            try:
                destruir_arbol(self.tutorial)
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self.tutorial = None
        if self.previa is not None:
            try:
                destruir_arbol(self.previa)
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self.previa = None
        if self.minijuego is not None:
            try:
                destruir_arbol(self.minijuego)
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self.minijuego = None
        if self.contenido is not None:           # el contenedor vacío de la vista: sin esto queda una entidad suelta por apertura
            try:
                destruir_arbol(self.contenido)
            except Exception:                    # noqa: BLE001
                pass
            self.contenido = None
        if self.banner is not None:
            try:
                destruir_arbol(self.banner)
            except Exception:                    # noqa: BLE001
                pass
            self.banner = None
        self.panel_resultado.ocultar()

    # -- Marco y escala (igual que EscenaJuego) --

    _escala_base = 1
    _ajuste = 1.0

    def _poner_marco(self, activo, lugar):
        if activo:
            self.marco.mostrar(self._rol_visible(), lugar)
            self._escala_base = ESCALA_JUEGO
        else:
            self.marco.ocultar()
            self._escala_base = 1
        self.scale = self._escala_base * self._ajuste

    def _al_cambiar_aspecto(self, aspecto, factor):
        self._ajuste = factor
        self.scale = self._escala_base * self._ajuste

    def _rol_id(self):
        if isinstance(self.jugador, dict):
            return self.jugador.get("rol")
        return getattr(self.jugador, "rol", None)

    def _rol_visible(self):
        from backend.logica.roles import ROLES
        rol = self._rol_id()
        return ROLES[rol].nombre if rol in ROLES else (rol or "")

    # -- Ciclo de vida --

    def al_entrar(self, jugador=None, estado=None, mision=None, al_terminar=None, grafo_social=None, marco=False,
                  lugar="", al_respaldo=None, **datos):
        self._limpiar_vista()
        self._reiniciar()
        self.jugador = jugador or {}
        self.estado, self.mision, self.grafo_social = estado, mision, grafo_social
        self._al_terminar, self._al_respaldo = al_terminar, al_respaldo
        self._lugar, self._marco_activo = lugar, bool(marco)
        self._poner_marco(marco, lugar)
        try:
            self._preparar_minijuego()
            textos = instrucciones.instrucciones_de(self.minijuego_id)
            if self._abrir_tutorial(textos):         # primera vez de este tipo de misión: tutorial animado (nunca rompe)
                return
            if mj.pantalla_previa_activa() and textos is not None:
                self._mostrar_previa(textos)
            else:
                self._arrancar_minijuego()
        except Exception as error:               # noqa: BLE001  cualquier fallo: se vuelve al minijuego de siempre
            self._respaldo(error)

    def al_salir(self):
        self._intento += 1
        self._limpiar_vista()
        self._poner_marco(False, "")

    # Elige minijuego, caso y clase de la vista ANTES de la pantalla previa: si algo de eso falla, se va al respaldo sin haber
    # enseñado instrucciones de un minijuego que no se podrá jugar.
    def _preparar_minijuego(self):
        self.minijuego_id = asignacion.asignar(self.mision, habilitados=minijuegos_casos.CASOS)
        if self.minijuego_id == mj.ACTUAL or self.estado is None or self.mision is None:
            raise RuntimeError("misión sin minijuego asignado")
        casos = minijuegos_casos.CASOS[self.minijuego_id]
        usados = self.usados.setdefault(self.minijuego_id, set())
        semilla = random.randrange(1 << 30)
        self._azar = random.Random(semilla)
        caso = mj.elegir_caso(casos, self.mision, asignacion.tema_de(self.mision), usados, self._azar)
        self._caso = mj.preparar_caso(caso, self.mision)
        self._clase = clase_de(self.minijuego_id)
        # Misiones visuales (frontend/minijuegos_visual, ALCALDE_EFECTOS_UI=0 lo apaga): misma lógica, mismo resultado.
        try:
            from frontend.minijuegos_visual import clase_visual
            self._clase = clase_visual(self.minijuego_id, self._clase)
        except Exception:                        # noqa: BLE001  sin capa visual: la vista de siempre
            pass
        self._clase3d = self._elegir_3d()

    def _arrancar_minijuego(self):
        if self.contenido is None or self.contenido.is_empty():     # con la previa en el monitor ya existe: se reutiliza
            self.contenido = Entity(parent=self)
        self.minijuego = self._clase(parent=self.contenido)
        self.minijuego.empezar({"caso": self._caso, "mision": self.mision, "azar": self._azar,
                                "al_terminar": self._minijuego_terminado})
        if self.vista3d is not None:             # la previa ya estaba en el monitor 3D: el minijuego ocupa su sitio
            minijuego = self.minijuego
            self._en_3d(lambda v: v.usar_minijuego(minijuego))
        else:
            self._montar_3d()

    def _previa_en_monitor(self):
        """¿La pantalla previa va dentro del monitor 3D? Solo con presentación 3D de la familia PC y la bandera
        ALCALDE_3D_PREVIA_MONITOR encendida (por defecto). Nunca lanza."""
        clase = self._clase3d
        if clase is None or getattr(clase, "FAMILIA", None) != "pc":
            return False
        try:
            from frontend.minijuegos_3d import banderas
            return banderas.previa_en_monitor()
        except Exception:                        # noqa: BLE001
            return False

    # -- Presentación 3D (frontend/minijuegos_3d; banderas ALCALDE_MINIJUEGOS_3D y ALCALDE_3D_<ID>) --
    # La vista 2D de arriba se crea y se empieza IGUAL que siempre (misma lógica, mismo ResultadoMinijuego); la presentación
    # 3D solo la cuelga de una textura y monta el set. Cualquier fallo del 3D (al abrir o en update/input) cae al 2D de hoy
    # con la MISMA vista 2D (mismo estado de la partida en curso): _caer_a_2d. Un fallo de la vista 2D sigue yendo a
    # _respaldo (la escena de juego), como hoy.

    def _elegir_3d(self):
        try:
            from frontend.minijuegos_3d import selector
            return selector.clase_3d(self.minijuego_id)
        except Exception:                        # noqa: BLE001  sin selector: 2D
            return None

    def _montar_3d(self, con_previa=False):
        _olvidar_salida_3d()
        clase = self._clase3d
        if clase is None or self.contenido is None or (self.minijuego is None and not con_previa):
            return
        try:
            from frontend.minijuegos_3d.base import Contexto3D
            ctx = Contexto3D(self.minijuego_id, self.minijuego, self.contenido, jugador=self._jugador_3d(),
                             mision=self.mision, lugar=getattr(self.mision, "destino", "") or "",
                             fabrica_interior=_fabrica_interior, escena=self)
            self.vista3d = clase(ctx)
            self._mostrar_2d(False)
            self.vista3d.abrir()
        except Exception as error:               # noqa: BLE001  el 3D nunca deja la misión atascada
            self._caer_a_2d(error)

    def _jugador_3d(self):
        from types import SimpleNamespace
        j = self.jugador
        if isinstance(j, dict):
            return SimpleNamespace(nombre=j.get("nombre") or "Jugador", rol=j.get("rol") or "ciudadano")
        return j

    def _mostrar_2d(self, visible):
        """Fondo y marco del PC de la escena 2D: escondidos mientras se ve el 3D, de vuelta en el 2D."""
        self.fondo.enabled = bool(visible)
        if visible and self._marco_activo:
            self.marco.mostrar(self._rol_visible(), self._lugar)
        elif not visible:
            self.marco.ocultar()

    def _en_3d(self, accion):
        """Ejecuta una llamada a la presentación 3D; si lanza, cae al 2D (nunca al respaldo de la misión)."""
        if self.vista3d is None:
            return
        try:
            accion(self.vista3d)
        except Exception as error:               # noqa: BLE001
            self._caer_a_2d(error)

    def _caer_a_2d(self, error):
        vista, self.vista3d = self.vista3d, None
        self._clase3d = None                     # en este minijuego no se vuelve a intentar el 3D
        _olvidar_salida_3d()                     # cayó al 2D: la salida del edificio es la de hoy
        _registro.warning("Minijuego %r: la presentación 3D falló (%r); se sigue en 2D con la misma partida.",
                          self.minijuego_id, error, exc_info=(type(error), error, getattr(error, "__traceback__", None)))
        try:
            from frontend import banderas_visuales as bv
            bv.avisar_una_vez(f"3d_{self.minijuego_id}", error)
        except Exception:                        # noqa: BLE001
            pass
        if vista is not None:
            try:
                vista.cerrar()
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
        try:
            if self.contenido is not None:
                self.contenido.parent = self
                self.contenido.position = (0, 0, 0)
                self.contenido.scale = 1
            self._mostrar_2d(not (self.cerrado and self.t_panel is not None))
        except Exception as fallo:               # noqa: BLE001  ni el 2D se puede enseñar: el respaldo de siempre
            self._respaldo(fallo)

    def _cerrar_3d(self):
        vista, self.vista3d = getattr(self, "vista3d", None), None
        if vista is not None:
            try:
                vista.cerrar()
            except Exception:                    # noqa: BLE001
                pass
            try:
                self._mostrar_2d(True)
            except Exception:                    # noqa: BLE001
                pass

    # -- Pantalla previa («Antes de empezar») --

    def _mostrar_previa(self, textos):
        from frontend.minijuegos.pantalla_previa import PantallaPrevia
        rumor = getattr(self.mision, "rumor", "") or self._caso.get("intro", "")
        # Con tutorial para este minijuego (bandera encendida): versión corta y botón «Ver tutorial». Sin él, la de siempre.
        corta, ver = False, None
        try:
            from frontend import registro_tutorial_mision as tutorial_mision
            if tutorial_mision.hay_tutorial(self.minijuego_id):
                corta, ver = True, self._ver_tutorial
        except Exception:                        # noqa: BLE001
            pass
        # Minijuego 3D de la familia PC: la previa va DENTRO del monitor 3D (la presentación se monta ya, con la previa como
        # contenido; al empezar, la vista 2D del minijuego ocupa su sitio en el mismo monitor). Si el 3D falla, la previa
        # vuelve a pantalla completa como hoy (_caer_a_2d devuelve `contenido` a la escena).
        en_monitor = self._previa_en_monitor()
        padre = self
        if en_monitor:
            if self.contenido is None or self.contenido.is_empty():
                self.contenido = Entity(parent=self)
            padre = self.contenido
        self.previa = PantallaPrevia(self._clase.TITULO, rumor, textos, ui.ayuda_legible(self._clase.AYUDA),
                                     self._empezar_desde_previa, corta=corta, al_ver_tutorial=ver, minijuego_id=self.minijuego_id,
                                     parent=padre)
        self.t_previa = 0.0
        if en_monitor and self.vista3d is None:
            self._montar_3d(con_previa=True)

    # -- Tutorial de la primera vez (frontend/registro_tutorial_mision.py): no cambia reglas, resultados ni pagos --

    def _abrir_tutorial(self, textos, forzar_ver=False):
        """Abre el tutorial si toca. Si no toca, o falla al construirse, devuelve False y todo sigue como hoy."""
        try:
            from frontend import registro_tutorial_mision as tutorial_mision
            intento = self._intento
            self.tutorial = tutorial_mision.abrir_si_toca(
                self, self.minijuego_id, lambda saltado, fallo: self._tras_tutorial(textos, intento), forzar_ver)
        except Exception:                        # noqa: BLE001
            self.tutorial = None
        return self.tutorial is not None

    def _tras_tutorial(self, textos, intento):
        if intento != self._intento:
            return
        if self.tutorial is not None:
            try:
                destruir_arbol(self.tutorial)
            except Exception:                    # noqa: BLE001
                pass
            self.tutorial = None
        try:
            if mj.pantalla_previa_activa() and textos is not None:
                self._mostrar_previa(textos)
            else:
                self._arrancar_minijuego()
        except Exception as error:               # noqa: BLE001
            self._respaldo(error)

    def _ver_tutorial(self):
        """«Ver tutorial» de la pantalla previa: lo enseña otra vez y vuelve a la previa."""
        if self.previa is None:
            return
        textos = instrucciones.instrucciones_de(self.minijuego_id)
        destruir_arbol(self.previa)
        self.previa = None
        self.t_previa = None
        if self.vista3d is not None:             # previa en el monitor 3D: el tutorial es el de hoy (2D, pantalla completa)
            self._cerrar_3d()
            if self.contenido is not None:
                destruir_arbol(self.contenido)
                self.contenido = None
        if not self._abrir_tutorial(textos, forzar_ver=True):
            self._mostrar_previa(textos)

    def _empezar_desde_previa(self):
        if self.previa is None:
            return
        # Misma demora que el banner: la tecla con la que se entró a la misión no salta las instrucciones.
        if self.t_previa is not None and self.t_previa < DEMORA_CONTINUAR:
            self.previa.al_empezar = self._empezar_desde_previa      # el botón se «gastó»: se vuelve a armar
            return
        destruir_arbol(self.previa)
        self.previa = None
        self.t_previa = None
        self._arrancar_minijuego()

    # -- Fin del minijuego: banner y «Continuar» --

    def _minijuego_terminado(self, resultado):
        self.resultado = resultado
        self.t_banner = 0.0
        self._pintar_banner(resultado)
        self._en_3d(lambda v: v.resultado(resultado))

    def _pintar_banner(self, resultado):
        self.banner = Entity(parent=self, z=-0.1)
        try:
            from frontend.minijuegos_visual import marco_calculos
            if marco_calculos.activo():
                self._pintar_banner_papel(resultado)
                return
        except Exception as error:               # noqa: BLE001  guardián: el banner de siempre
            from frontend import banderas_visuales as bv
            bv.avisar_una_vez("marco_resultado", error)
            destruir_arbol(self.banner)
            self.banner = Entity(parent=self, z=-0.1)
        self._pintar_banner_simple(resultado)

    def _graduacion(self, resultado):
        # Con la consecuencia graduada, el título adelanta la propina (lo mismo que aplicará el flujo al cerrar).
        # En línea (EstadoRemoto, sin cartas_mision) no hay economía ni consecuencia graduada: no se promete propina.
        local = getattr(self.estado, "cartas_mision", None) is not None
        return (consecuencia_graduada.calcular(resultado.a_dict(), self.mision)
                if consecuencia_graduada.activo() and local else None)

    def _pintar_banner_papel(self, resultado):
        """Panel de resultado como marco de papel con sello redondo y palabra (sin «[OK]»)."""
        from frontend.minijuegos_visual import marco_calculos as mc
        from frontend.minijuegos_visual import marco_mesa
        bien = resultado.bien
        graduacion = self._graduacion(resultado)
        propina = graduacion.propina if graduacion is not None else 0
        por_poco = graduacion is not None and propina <= 0 and graduacion.retardado is not None
        veredicto = mc.veredicto(getattr(self.mision, "es_verdadera", False))
        pista = mc.frase_pista(glosar_texto(self.mision.destino), self.mision.pista)
        medidas = marco_mesa.panel_resultado(self.banner, ANCHO_BANNER, bien, mc.titulo_resultado(bien, por_poco),
                                             resultado.detalle, pista, veredicto=veredicto)
        x_boton = medidas["x_boton"]
        etiqueta = mc.chip_propina(propina) or mc.chip_por_poco(por_poco)
        if etiqueta:
            marco_mesa.chip(self.banner, etiqueta, x_boton, medidas["alto"] / 2 - a_unidades(17))
        self.boton = BotonPrimario("Continuar", al_clic=self.continuar, ancho=0.3, alto=0.07, parent=self.banner,
                                   position=(x_boton, -0.004, -0.01), tamano_fuente_px=22)
        Text("Enter o Espacio", parent=self.banner, origin=(0, 0), position=(x_boton, -medidas["alto"] / 2 + a_unidades(13), -0.01),
             scale=escala_fuente(17), color=rgb(mc.TEXTO_SUAVE))

    def _pintar_banner_simple(self, resultado):
        bien = resultado.bien
        panel_tinta(self.banner, ANCHO_BANNER, ALTO_BANNER, tono=estilo.COLOR_PANEL, position=(0, Y_BANNER, 0))
        titulo = "Verificaste bien" if bien else "Se te escapó algo"
        graduacion = self._graduacion(resultado)
        if graduacion is not None and graduacion.propina > 0:
            titulo += f"  ·  propina R$ {graduacion.propina}"
        elif graduacion is not None and graduacion.retardado is not None:
            titulo += "  ·  por poco"
        tono = estilo.ESTADO_EXITO if bien else estilo.ESTADO_AVISO
        x0 = -ANCHO_BANNER / 2 + a_unidades(18)
        marca = "[OK] " if bien else "[!] "
        ui.texto(self.banner, marca + titulo, 24, 1.0, tono, (x0, Y_BANNER + ALTO_BANNER / 2 - a_unidades(12)), negrita=True)
        veredicto = "cierto" if getattr(self.mision, "es_verdadera", False) else "falso"
        lineas = [resultado.detalle, f"El rumor era {veredicto}. En {glosar_texto(self.mision.destino)} se veía: {self.mision.pista}"]
        ui.texto(self.banner, "\n".join(lineas), 15, 1.18, estilo.COLOR_TEXTO,
                 (x0, Y_BANNER + ALTO_BANNER / 2 - a_unidades(46)))
        self.boton = BotonPrimario("Continuar", al_clic=self.continuar, ancho=0.3, alto=0.075, parent=self.banner,
                                   position=(ANCHO_BANNER / 2 - 0.2, Y_BANNER + 0.01, -0.01), tamano_fuente_px=22)
        Text("Enter o Espacio", parent=self.banner, origin=(0.5, 0), position=(ANCHO_BANNER / 2 - 0.2, Y_BANNER - 0.047, -0.01),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))

    def continuar(self):
        """«Continuar»: traduce el resultado a decisiones y cierra la misión (o enseña el grafo social antes)."""
        if self.cerrado or self.resultado is None or self.en_respaldo:
            return
        if self.t_banner is not None and self.t_banner < DEMORA_CONTINUAR:
            return
        self.cerrado = True
        try:
            self.lote = LoteMision(self.mision, self.grafo_social, rol=self._rol_id(), estado=self.estado)
            entrega = mj.cerrar_lote(self.estado, self.lote, self.mision, self.resultado.bien)
        except Exception as error:               # noqa: BLE001
            if self._lote_toco_el_estado():
                # Ya se aplicaron decisiones sobre el estado: reabrir la misión en la escena de siempre las repetiría.
                # Se cierra con lo que el lote alcanzó a registrar.
                _registro.error("Minijuego %r: falló al cerrar el lote tras aplicar decisiones (%s); se entrega lo registrado.",
                                self.minijuego_id, error)
                entrega = self.lote.resultado()
            else:
                self.cerrado = False
                self._respaldo(error)
                return
        # Lo bien que se verificó viaja con el resultado: backend/logica/consecuencia_graduada lo convierte en propina,
        # confianza y, si se pasó raspando, dudas al día siguiente. Sin ese envoltorio la clave se ignora.
        if isinstance(entrega, dict):
            entrega = dict(entrega, minijuego=self.resultado.a_dict())
        self._entrega = entrega
        if self.grafo_social is not None:
            self._mostrar_grafo_o_entregar()
        else:
            self._entregar()

    # ¿El lote ya aplicó (o intentó aplicar) decisiones sobre el estado? Entonces reabrir la misión las repetiría.
    def _lote_toco_el_estado(self):
        lote = self.lote
        return lote is not None and (lote.decisiones + lote.descartadas + getattr(lote, "intentos_decidir", 0)) > 0

    # El resultado ya está aplicado: si enseñar el grafo falla (panel, propagaciones, indicadores) NO se pasa por el respaldo
    # (repetiría decisiones); se registra el error y se entrega el resultado directamente. Igual por clic que por teclado.
    def _mostrar_grafo_o_entregar(self):
        try:
            self._mostrar_grafo()
        except Exception as error:               # noqa: BLE001
            _registro.error("Minijuego %r: falló al enseñar el grafo social (%s); se entrega el resultado sin él.",
                            self.minijuego_id, error)
            self.t_panel = None
            try:
                self.panel_resultado.ocultar()
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
            self._entregar()

    def _mostrar_grafo(self):
        intento = self._intento
        self._cerrar_3d()                        # el panel del grafo es el de siempre, sobre el fondo de siempre
        if self.banner is not None:
            self.banner.enabled = False
        self.minijuego.enabled = False
        self.t_panel = 0.0
        self.panel_resultado.mostrar(
            self.grafo_social, self.lote.propagaciones_con_niveles(), self.lote.deltas_acumulados,
            titulo=glosar_texto(self.mision.titulo), indicadores=self.estado.indicadores(),
            al_continuar=lambda: self._entregar(intento))

    def _entregar(self, intento=None):
        if intento is not None and intento != self._intento:
            return
        callback, self._al_terminar = self._al_terminar, None      # una sola vez
        if callback is not None:
            callback(self._entrega)

    # -- Respaldo --

    def _respaldo(self, error):
        if self.cerrado and self._lote_toco_el_estado():
            # La misión ya se cerró con decisiones aplicadas: reabrirla en la escena de siempre las repetiría. Solo se registra.
            _registro.error("Minijuego %r falló (%s) con el lote ya aplicado; no se abre el respaldo.", self.minijuego_id, error)
            return
        _registro.warning("Minijuego %r falló (%s): se usa el minijuego de siempre.", self.minijuego_id, error)
        _olvidar_salida_3d()                     # la misión sigue en la escena de juego de siempre: salida de hoy
        self.en_respaldo = True
        callback, self._al_respaldo = self._al_respaldo, None
        if callback is None:
            raise error                       # sin respaldo no se puede ocultar el fallo
        callback()

    # -- Entrada y tiempo (Ursina los llama solo con la escena activa) --

    def input(self, key):
        if self.en_respaldo or self.cerrado and self.t_panel is not None:
            return
        try:
            if self.previa is not None:
                if key in ("enter", "space", "return"):
                    self._empezar_desde_previa()
                return
            if self.resultado is not None and not self.cerrado:
                if key in ("enter", "space", "return"):
                    self.continuar()
                return
            if self.minijuego is not None and self.resultado is None:
                self.minijuego.tecla(key)
        except Exception as error:               # noqa: BLE001
            self._respaldo(error)
            return
        self._en_3d(lambda v: v.tecla(key))     # imitación 3D DESPUÉS de la tecla de siempre (nunca la decide)

    def update(self):
        if self.en_respaldo:
            return
        dt = time.dt
        self._en_3d(lambda v: v.avanzar(dt))
        try:
            if self.t_previa is not None:
                self.t_previa += dt
            if self.t_banner is not None:
                self.t_banner += dt
            if self.t_panel is not None:
                self.panel_resultado.avanzar(dt)
            if self.minijuego is not None and self.resultado is None:
                self.minijuego.avanzar(dt)
            # Misiones visuales: el sello y las estrellas siguen animándose tras terminar (avanzar_visual nunca lanza).
            if self.minijuego is not None and hasattr(self.minijuego, "avanzar_visual"):
                self.minijuego.avanzar_visual(dt)
        except Exception as error:               # noqa: BLE001
            self._respaldo(error)

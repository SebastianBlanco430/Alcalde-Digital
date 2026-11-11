# Escena del MUNDO DIGITAL (Ursina): rejilla, wireframe y neón (tema «digital» de frontend/materiales.py) donde se
# juega un caso de investigación (backend/logica/casos.py). Mundo en `scene` (decorado estático) + interfaz en
# camera.ui (frontend/casos_interfaz.py). Cámara de diálogo: se desliza hacia la estación del personaje que habla.
#
# Guarda y restaura cámara, color de fondo y niebla (como EscenaInterior): al volver, el mundo reaparece con su estado.
# No conoce al gestor: al cerrar sesión llama a `al_terminar()` con el glitch ya cubriendo la pantalla.
# El progreso de cada caso se conserva en memoria por (GameState, caso): salir y volver continúa donde se dejó.

from ursina import camera, mouse, scene, time, window

from backend.datos import parkour_loader
from backend.logica import casos, enlace_parkour
from backend.logica.casos import CasoError, SesionCaso, VistaNodo
from frontend import camara_calculos as cc
from frontend import dialogo_retratos
from frontend import materiales as mat
from frontend import mundo_digital_calculos as calc
from frontend.casos_interfaz import InterfazCaso
from frontend.componentes import destruir_arbol, rgb
from frontend.escenas.escena_base import Escena
from frontend.mundo_digital_decorado import DecoradoDigital
from frontend.niebla import activar_niebla, desactivar_niebla

FOV_DIGITAL = 65
FIN_NIEBLA = 60.0
TECLA_PARKOUR = "k"           # abre el parkour que declara el caso (botón bajo las evidencias)


class EscenaMundoDigital(Escena):

    def __init__(self, glitch=None, catalogo=None, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self.glitch = glitch
        self.catalogo = catalogo or {}
        self.interfaz = InterfazCaso({"fila": self._accion_fila}, dialogo_retratos.textura_retrato_caso)
        self._decorados = {}
        self._sesiones = {}
        self._gs_de_sesiones = None        # GameState al que pertenecen las sesiones guardadas
        self._caso = self._sesion = self._decorado = self._vista = None
        self._modo = "opciones"
        self._al_terminar = None
        # Quien lanza el parkour (lo cuelga frontend/registro_mundo_digital.py): callable(nivel_id) -> bool. None = sin botón.
        self.al_pedir_parkour = None
        self._enlace = None
        self._evidencias_antes_parkour = None
        self._bloqueo = False
        self._camara_guardada = None
        self._fondo_guardado = None
        self._cam = None
        self._t = 0.0
        self._ultimo_texto_tiempo = None

    # -- Ciclo de vida --

    def al_entrar(self, flujo=None, caso_id=None, al_terminar=None, **datos):
        gs = getattr(flujo, "game_state", None)
        caso = self.catalogo.get(caso_id)
        if gs is None or caso is None:
            raise CasoError(f"No se puede abrir el caso {caso_id!r}: sin GameState o caso inexistente.")
        self._al_terminar = al_terminar
        self._gs = gs
        self._bloqueo = False
        self._guardar_estado()
        self._caso, self._modo = caso, "opciones"
        self._sesion = self._sesion_para(gs, caso)
        self._decorado = self._decorado_de(caso)
        for d in self._decorados.values():
            d.enabled = d is self._decorado
        self.interfaz.enabled = True
        self.interfaz.fijar_caso(caso)
        mouse.locked = False
        self._refrescar(colocar=True)
        self._preparar_enlace_parkour(caso)
        self._avisar_evidencia_del_parkour()
        if self.glitch is not None:
            self.glitch.desvanecer()

    def al_salir(self):
        self.interfaz.enabled = False
        self._bloqueo = False
        self._restaurar_estado()

    def _guardar_estado(self):
        if self._camara_guardada is None:
            self._camara_guardada = {
                "parent": camera.parent, "orthographic": camera.orthographic, "fov": camera.fov,
                "position": camera.position, "rotation": camera.rotation,
                "near": camera.clip_plane_near, "far": camera.clip_plane_far}
            self._fondo_guardado = window.color
        camera.parent = scene
        camera.orthographic = False
        camera.fov = FOV_DIGITAL
        camera.clip_plane_near = 0.1
        camera.clip_plane_far = 200
        window.color = rgb(mat.tema("digital")["fondo"])
        activar_niebla(color=mat.DIGITAL_NIEBLA, fin=FIN_NIEBLA, intensidad=1.0)

    def _restaurar_estado(self):
        desactivar_niebla()
        g = self._camara_guardada
        if g is None:
            return
        camera.parent, camera.orthographic, camera.fov = g["parent"], g["orthographic"], g["fov"]
        camera.clip_plane_near, camera.clip_plane_far = g["near"], g["far"]
        camera.position, camera.rotation = g["position"], g["rotation"]
        window.color = self._fondo_guardado
        self._camara_guardada = None

    # -- Puerta al parkour (el caso la declara en su JSON; ver backend/logica/enlace_parkour.py) --

    def _preparar_enlace_parkour(self, caso):
        self._enlace = enlace_parkour.de_caso(caso.datos, parkour_loader.listar_niveles()) if self.al_pedir_parkour else None
        self._refrescar_enlace_parkour()

    # El botón se ofrece también con el caso YA RESUELTO (sin sesión): la misión de parkour puede tocar después de la de
    # investigación y el parkour solo se lanza desde aquí.
    def _refrescar_enlace_parkour(self):
        enlace = self._enlace
        if enlace is None:
            self.interfaz.mostrar_enlace(None, None, TECLA_PARKOUR, None)
            return
        recompensa = parkour_loader.cargar_nivel(enlace.nivel).recompensa.get("evidencia")
        hecho = enlace_parkour.completado(self._gs, recompensa)
        self.interfaz.mostrar_enlace(enlace.texto_completado if hecho and enlace.texto_completado else enlace.texto,
                                     enlace.pista, TECLA_PARKOUR, self.abrir_parkour)

    # Lanza el parkour dentro del mundo virtual. Al terminar o salir, quien lo lanzó nos devuelve aquí (misma sesión).
    def abrir_parkour(self):
        if self._bloqueo or self._enlace is None or self.al_pedir_parkour is None:
            return False
        self._evidencias_antes_parkour = set(self._sesion.evidencias_en_mano()) if self._sesion is not None else None
        if self.al_pedir_parkour(self._enlace.nivel):
            return True
        self._evidencias_antes_parkour = None
        if self._enlace.no_disponible:
            self.interfaz.mostrar_mensaje(self._enlace.no_disponible)
        return False

    # Al volver del parkour avisa de la evidencia ganada (la sesión ya la lee sola por evidencia.py).
    def _avisar_evidencia_del_parkour(self):
        antes, self._evidencias_antes_parkour = self._evidencias_antes_parkour, None
        if antes is None or self._sesion is None:
            return
        for nueva in sorted(set(self._sesion.evidencias_en_mano()) - antes):
            self.interfaz.mostrar_mensaje(f"Evidencia nueva: {self._caso.nombre_evidencia(nueva)}", bueno=True)

    def _sesion_para(self, gs, caso):
        # Solo se guardan las sesiones de la partida en curso: con otro GameState (partida nueva) se sueltan las de la
        # anterior (antes se acumulaban una por partida y caso, y un id() reutilizado podía cruzar partidas).
        if self._gs_de_sesiones is not gs:
            self._sesiones.clear()
            self._gs_de_sesiones = gs
        clave = (id(gs), caso.id)
        previa = self._sesiones.get(clave)
        if previa is not None and previa.gs is gs:
            return previa
        if not casos.puede_jugar(gs, caso):
            return None                      # ya resuelto: solo se muestra el resumen
        self._sesiones[clave] = SesionCaso(caso, gs)
        return self._sesiones[clave]

    def _decorado_de(self, caso):
        if caso.id not in self._decorados:
            self._decorados[caso.id] = DecoradoDigital(caso.personajes, dialogo_retratos.textura_retrato_caso, parent=self)
        return self._decorados[caso.id]

    # -- Vista actual --

    def _vista_actual(self):
        if self._sesion is not None:
            return self._sesion.vista()
        r = casos.resultado_de(self._gs, self._caso.id)
        nodo = self._caso.nodo(r.final_id)
        return VistaNodo(r.final_id, "final", nodo.get("personaje"), nodo.get("expresion"), nodo["texto"],
                         titulo=nodo.get("titulo", ""), resultado=nodo.get("resultado"))

    def _evidencias(self):
        if self._sesion is None:
            return []
        return [(e, self._caso.nombre_evidencia(e), self._caso.evidencias[e].get("descripcion", ""))
                for e in self._sesion.evidencias_en_mano()]

    def _refrescar(self, colocar=False):
        caso, v = self._caso, self._vista_actual()
        self._vista = v
        pj = caso.personajes.get(v.personaje)
        expresion = dialogo_retratos.expresion_o_base(v.expresion)
        if pj is None:
            self.interfaz.mostrar_hablante("Narrador", "", None, "neutral")
        else:
            self.interfaz.mostrar_hablante(pj["nombre"], pj.get("rol", ""), pj["retrato"], expresion)
            self._decorado.fijar_expresion(v.personaje, pj["retrato"], expresion, dialogo_retratos.textura_retrato_caso)
        self._decorado.resaltar(v.personaje)
        titulo = ""
        if v.tipo == "final":
            titulo = f"{v.titulo}  -  {calc.texto_resultado(v.resultado)}"
            if self._sesion is not None and caso.fin_por_errores:
                titulo += f"  ({calc.texto_errores(self._sesion.errores, caso.fin_por_errores['max'])})"
        self.interfaz.mostrar_texto(titulo, v.texto)
        evidencias = self._evidencias()
        self.interfaz.mostrar_evidencias(evidencias)
        self._filas = calc.filas_de_nodo(v, self._modo, [(e, n) for e, n, _ in evidencias])
        self.interfaz.mostrar_filas(self._filas)
        self._ultimo_texto_tiempo = None
        self._mostrar_tiempo()
        toma = calc.toma_dialogo(self._decorado.estaciones.get(v.personaje))
        if colocar or self._cam is None:
            self._cam = {"position": toma["position"], "target": toma["target"]}
        self._meta_cam = toma
        self._poner_camara()

    def _mostrar_tiempo(self):
        v = self._vista
        if self._sesion is None or v is None or v.restante is None:
            self.interfaz.mostrar_temporizador(None, None)
            return
        r = self._sesion.restante()
        texto = calc.formatear_tiempo(r)
        if texto != self._ultimo_texto_tiempo:
            self._ultimo_texto_tiempo = texto
            self.interfaz.mostrar_temporizador(r, v.segundos_limite)

    def _poner_camara(self):
        camera.position = self._cam["position"]
        camera.rotation = (*cc.rotacion_mirando(self._cam["position"], self._cam["target"]), 0)

    # -- Acciones --

    def _accion_fila(self, fila):
        if self._bloqueo or self._sesion is None and fila.tipo != "salir":
            return
        antes = set(self._sesion.evidencias_en_mano()) if self._sesion else set()
        try:
            self._ejecutar(fila)
        except CasoError as error:
            self.interfaz.mostrar_mensaje(str(error))
        if self._sesion is not None:
            for nueva in sorted(set(self._sesion.evidencias_en_mano()) - antes):
                self.interfaz.mostrar_mensaje(f"Evidencia nueva: {self._caso.nombre_evidencia(nueva)}", bueno=True)
        if not self._bloqueo:
            self._refrescar()

    def _ejecutar(self, fila):
        s = self._sesion
        if fila.tipo == "continuar":
            s.continuar()
        elif fila.tipo == "opcion":
            s.elegir(fila.clave)
        elif fila.tipo == "modo_pruebas":
            if not fila.habilitada:
                self.interfaz.mostrar_mensaje(fila.motivo)
            else:
                self._modo = "pruebas"
        elif fila.tipo == "cancelar":
            self._modo = "opciones"
        elif fila.tipo == "prueba":
            r = s.presentar(fila.clave)
            extra = "" if r.correcta else f" ({calc.texto_errores(r.errores, self._caso.fin_por_errores['max'])})" \
                if self._caso.fin_por_errores else ""
            self.interfaz.mostrar_mensaje((r.texto or ("Correcto." if r.correcta else "No encaja.")) + extra, bueno=r.correcta)
            self._modo = "opciones"
        elif fila.tipo == "salir":
            self.cerrar_sesion()
        if s is not None and s.nodo_actual()["tipo"] not in casos.CLAVE_OPCIONES:
            self._modo = "opciones"

    def cerrar_sesion(self):
        if self._bloqueo:
            return
        self._bloqueo = True
        if self.glitch is None:
            self._terminar()
        else:
            self.glitch.subir(calc.DURACION_GLITCH_SALIDA, al_terminar=self._terminar)

    def _terminar(self):
        callback, self._al_terminar = self._al_terminar, None
        if callback is not None:
            callback()

    # Espacio / Enter durante el glitch de salida: lo termina ya. True si actuó.
    def saltar(self):
        if not self._bloqueo or self._al_terminar is None:
            return False
        if self.glitch is not None:
            self.glitch.cancelar()
        self._terminar()
        return True

    def input(self, key):
        if self._bloqueo or self._vista is None:
            return
        if key == "escape":
            if self._modo == "pruebas":
                self._modo = "opciones"
                self._refrescar()
            else:
                self.cerrar_sesion()
            return
        if key == TECLA_PARKOUR:
            self.abrir_parkour()
            return
        if key == "p":
            fila = next((f for f in self._filas if f.tipo == "modo_pruebas"), None)
            if fila is not None:
                self._accion_fila(fila)
            return
        if key in ("enter", "space") and len(self._filas) == 1 and self._filas[0].tipo in ("continuar", "salir"):
            self._accion_fila(self._filas[0])
            return
        i = calc.indice_de_tecla(key)
        if i is not None and i < len(self._filas):
            fila = self._filas[i]
            if fila.habilitada:
                self._accion_fila(fila)
            elif fila.motivo:
                self.interfaz.mostrar_mensaje(fila.motivo)

    # -- Frame --

    def update(self):
        dt = min(time.dt, 0.1)
        self._t += dt
        if self._decorado is None or self._cam is None:
            return
        self._decorado.avanzar(self._t)
        self.interfaz.avanzar(dt)
        self._cam = {k: calc.acercar_a(self._cam[k], self._meta_cam[k], dt) for k in ("position", "target")}
        self._poner_camara()
        if self._bloqueo or self._sesion is None:
            return
        if self._sesion.avanzar_tiempo(dt):
            self._modo = "opciones"
            self.interfaz.mostrar_mensaje("Se acabó el tiempo: se tomó la opción por defecto.")
            self._refrescar()
        else:
            self._mostrar_tiempo()

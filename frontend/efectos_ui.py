# Capa común de efectos de interfaz de las misiones (Ursina, camera.ui). Da a cualquier pantalla de minijuego, tarjeta o
# panel: entrada con rebote, foco que agranda un poco, pulso al elegir, temblor y tinte rojo al fallar, destello verde con
# partículas al acertar (con sonido que sube de tono si se encadenan aciertos y un multiplicador visible «x3»), sello animado
# «VERIFICADO» / «BULO» que cae con un golpe, y de 0 a 3 estrellas + medalla.
#
# Por qué: las misiones se jugaban con tarjetas quietas; esto las hace sentir vivas SIN cambiar reglas ni resultados (los
# efectos solo leen; nunca escriben en la partida).
#
# RENDIMIENTO: todo sale de POOLS creados una vez (entidades apagadas con enabled=False y reutilizadas, como
# frontend/parkour_efectos.py). No hay update() por entidad: el dueño llama a sincronizar(dt) una vez por frame.
# La matemática está en frontend/efectos_ui_calculos.py (puro, con tests).
#
# APAGADO: ALCALDE_EFECTOS_UI=0 (o EFECTOS_UI = False). Lo consulta quien crea la capa (frontend/minijuegos_visual).
# REDUCIR MOVIMIENTO (Ajustes › Movimiento o ALCALDE_REDUCIR_MOVIMIENTO=1): sin rebotes, temblores, destellos ni partículas.
# GUARDIÁN: si sincronizar() falla, avisa una vez por stderr, devuelve las tarjetas a su tamaño y sitio y se apaga.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Mesh, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as calc
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, modelo_redondeado

EFECTOS_UI = True
VARIABLE = "ALCALDE_EFECTOS_UI"

N_PARTICULAS = 28
N_DESTELLOS = 6
N_ESTRELLAS = 3

VERDE = (88, 214, 141)
ROJO = (235, 87, 87)
DORADO = (255, 205, 64)
GRIS_ESTRELLA = (90, 96, 110)

SONIDO_ACIERTO = "clic_ui"
SONIDO_ERROR = "mision_fallo"
SONIDO_SELLO = "aterrizaje"


def activo():
    return bv.activa(EFECTOS_UI, VARIABLE)


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _sonar(nombre, volumen=1.0, pitch=1.0):
    try:
        from frontend import audio
        audio.obtener().efecto(nombre, volumen=volumen, pitch=pitch)
    except Exception:                    # noqa: BLE001  sin audio el efecto se ve igual
        pass


def malla_estrella():
    """Malla NUEVA de estrella: una malla de Ursina solo puede colgar de una entidad, así que cada estrella lleva la suya
    (se crean una vez por pantalla, en el pool de estrellas)."""
    contorno = calc.puntos_estrella(0.5, 0.22)
    vertices = [(0, 0, 0)] + [(x, y, 0) for x, y in contorno]
    return Mesh(vertices=vertices, triangles=calc.triangulos_estrella())


class EfectosUI(Entity):
    """Sistema de efectos de una pantalla. Cuélgalo del contenedor de la pantalla y llama a sincronizar(dt) cada frame."""

    def __init__(self, sonido=True, **opciones):
        opciones.setdefault("z", -0.2)
        super().__init__(**opciones)
        self.reducir = bv.reducir_movimiento()
        self.sonido = sonido
        self.racha = 0
        self.roto = False
        self._estados = {}          # id(entidad) -> dict con la entidad, su escala/x base y los efectos activos
        self._programados = []      # [restante_s, funcion]
        self._semilla = 0
        self._particulas = [self._nuevo_item(Entity(parent=self, model="quad", scale=0.011, enabled=False))
                            for _ in range(N_PARTICULAS)]
        self._destellos = [self._nuevo_item(Entity(parent=self, model="quad", enabled=False)) for _ in range(N_DESTELLOS)]
        self.rotulo_racha = Text("", parent=self, origin=(0, 0), scale=escala_fuente(30), font=tipografia.fuente_piel(titulo=True),
                                 color=_rgba(DORADO, 1), position=(0.845, 0.335, -0.01), enabled=False)
        self._t_racha = None
        self.sello_e = None
        self._t_sello = None
        self._al_golpe = None
        self._estrellas = []
        self._t_estrellas = None
        self.medalla_e = None
        self._t_medalla = None

    @staticmethod
    def _nuevo_item(entidad):
        return {"e": entidad, "t": 0.0, "dur": 0.0, "activo": False}

    # -- Tarjetas: rebote, foco, pulso, temblor --

    def _estado(self, entidad):
        clave = id(entidad)
        estado = self._estados.get(clave)
        if estado is None or estado["e"] is not entidad:
            estado = {"e": entidad, "escala": tuple(entidad.scale), "x": entidad.x, "rebote": None, "pulso": None,
                      "temblor": None, "foco": 1.0, "foco_obj": 1.0, "semilla": self._siguiente_semilla()}
            self._estados[clave] = estado
        return estado

    def _siguiente_semilla(self):
        self._semilla += 1
        return self._semilla

    def rebote(self, entidad, retardo=0.0):
        """Entrada con rebote (empieza pequeña y llega con un saltito)."""
        if self.roto or entidad is None:
            return
        estado = self._estado(entidad)
        estado["rebote"] = -retardo
        self._aplicar(estado)

    def foco(self, entidad, enfocado):
        if self.roto or entidad is None:
            return
        self._estado(entidad)["foco_obj"] = calc.escala_foco(enfocado, self.reducir)

    def pulso(self, entidad):
        """Al elegir: se encoge y vuelve."""
        if not self.roto and entidad is not None:
            self._estado(entidad)["pulso"] = 0.0

    def temblor(self, entidad):
        if not self.roto and entidad is not None:
            self._estado(entidad)["temblor"] = 0.0

    def _aplicar(self, estado):
        e = estado["e"]
        if e.is_empty():
            return False
        mult = estado["foco"]
        if estado["rebote"] is not None:
            mult *= calc.rebote(estado["rebote"], reducir=self.reducir)
        if estado["pulso"] is not None:
            mult *= calc.pulso_eleccion(estado["pulso"], reducir=self.reducir)
        sx, sy, sz = estado["escala"]
        e.scale = (sx * mult, sy * mult, sz)
        # La x solo se toca mientras tiembla (y una vez al acabar): el minijuego puede mover sus filas (cronología).
        if estado["temblor"] is not None:
            if not estado.get("toco_x"):
                estado["x"] = e.x
                estado["toco_x"] = True
            e.x = estado["x"] + calc.temblor(estado["temblor"], semilla=estado["semilla"], reducir=self.reducir)
        elif estado.get("toco_x"):
            e.x = estado["x"]
            estado["toco_x"] = False
        return True

    def _avanzar_tarjetas(self, dt):
        for clave in list(self._estados):
            estado = self._estados[clave]
            if estado["e"].is_empty():
                del self._estados[clave]
                continue
            for nombre, dur in (("rebote", calc.DUR_REBOTE), ("pulso", calc.DUR_PULSO), ("temblor", calc.DUR_TEMBLOR)):
                if estado[nombre] is not None:
                    estado[nombre] += dt
                    if estado[nombre] >= dur:
                        estado[nombre] = None
            estado["foco"] = calc.acercar(estado["foco"], estado["foco_obj"], dt)
            en_reposo = (estado["rebote"] is None and estado["pulso"] is None and estado["temblor"] is None
                         and estado["foco_obj"] == 1.0 and abs(estado["foco"] - 1.0) < 1e-3)
            if en_reposo:
                estado["foco"] = 1.0
                self._aplicar(estado)            # deja la escala base exacta y la x devuelta
                del self._estados[clave]         # en reposo no se vuelve a escribir nada sobre la tarjeta
                continue
            self._aplicar(estado)

    def restaurar(self):
        """Devuelve cada tarjeta tocada a su escala y posición originales."""
        for estado in self._estados.values():
            e = estado["e"]
            if not e.is_empty():
                e.scale = estado["escala"]
                if estado.get("toco_x"):
                    e.x = estado["x"]
        self._estados.clear()

    # -- Destellos y partículas --

    @staticmethod
    def _libre(pool):
        for item in pool:
            if not item["activo"]:
                return item
        return max(pool, key=lambda i: i["t"] / max(i["dur"], 1e-6))

    def _posicion_de(self, entidad):
        try:
            return entidad.get_position(relative_to=self)
        except Exception:                # noqa: BLE001
            return (0, 0, 0)

    def destello(self, entidad, tono):
        if self.roto or entidad is None or entidad.is_empty():
            return
        item = self._libre(self._destellos)
        pos = self._posicion_de(entidad)
        ancho = getattr(entidad, "ancho", 0.3) * entidad.scale_x
        alto = getattr(entidad, "alto", 0.1) * entidad.scale_y
        e = item["e"]
        e.model = modelo_redondeado(ancho, alto, 8)
        e.scale = (ancho, alto)
        e.position = (pos[0], pos[1], -0.02)
        item.update(t=0.0, dur=calc.DUR_DESTELLO, activo=True, tono=tono)
        e.color = _rgba(tono, calc.destello(0.0, reducir=self.reducir) * 0.55)
        e.enabled = True

    def particulas(self, entidad_o_pos, tono=VERDE, n=10):
        if self.roto or self.reducir:
            return
        if hasattr(entidad_o_pos, "get_position"):
            if entidad_o_pos.is_empty():
                return
            pos = self._posicion_de(entidad_o_pos)
        else:
            pos = entidad_o_pos
        for vx, vy in calc.velocidades_particulas(n, self._siguiente_semilla()):
            item = self._libre(self._particulas)
            item.update(t=0.0, dur=calc.DUR_PARTICULA, activo=True, vx=vx, vy=vy, x0=pos[0], y0=pos[1], tono=tono)
            item["e"].color = _rgba(tono, 1)
            item["e"].position = (pos[0], pos[1], -0.03)
            item["e"].enabled = True

    def _avanzar_pools(self, dt):
        for item in self._destellos:
            if item["activo"]:
                item["t"] += dt
                if item["t"] >= item["dur"]:
                    item["activo"] = False
                    item["e"].enabled = False
                else:
                    item["e"].color = _rgba(item["tono"], calc.destello(item["t"], reducir=self.reducir) * 0.55)
        for item in self._particulas:
            if item["activo"]:
                item["t"] += dt
                x, y, alfa = calc.particula(item["t"], item["vx"], item["vy"])
                if alfa <= 0:
                    item["activo"] = False
                    item["e"].enabled = False
                else:
                    item["e"].position = (item["x0"] + x, item["y0"] + y, -0.03)
                    item["e"].color = _rgba(item["tono"], alfa)

    # -- Acierto / error / racha --

    def acierto(self, entidad=None, sonar=True):
        self.racha += 1
        if entidad is not None:
            self.destello(entidad, VERDE)
            self.particulas(entidad, VERDE)
        if sonar and self.sonido:
            _sonar(SONIDO_ACIERTO, 0.8, calc.tono_racha(self.racha))
        self.contador_racha(self.racha)

    def error(self, entidad=None, sonar=True):
        self.racha = 0
        if entidad is not None:
            self.temblor(entidad)
            self.destello(entidad, ROJO)
        if sonar and self.sonido:
            _sonar(SONIDO_ERROR, 0.45, 0.7)
        self.contador_racha(0)

    def contador_racha(self, racha, posicion=None):
        if self.roto:
            return
        texto = calc.texto_racha(racha)
        if posicion is not None:
            self.rotulo_racha.position = posicion
        self.rotulo_racha.text = texto
        self.rotulo_racha.enabled = bool(texto)
        self._t_racha = 0.0 if texto else None

    # -- Sello, estrellas y medalla --

    def sello(self, texto, posicion=(0.45, 0.385), tono=None, al_golpe=None, retardo=0.0, escala=1.0, limites=None):
        """Sello que cae sobre `posicion` y golpea (sonido + temblor del sello). Uno por pantalla. `escala` (por defecto 1)
        reduce el sello entero (caja y texto) sin cambiar su caída. `limites` (xmin, xmax, ymin, ymax en coordenadas de
        este efecto): el panel donde debe quedar ENTERO, también mientras cae (calc.ajustar_sello)."""
        if self.roto or not texto:
            return
        tono = tono or (VERDE if texto == "VERIFICADO" else ROJO)
        if self.sello_e is None:
            self.sello_e = Entity(parent=self, z=-0.05)
            self._sello_borde = Entity(parent=self.sello_e, model=modelo_redondeado(0.34, 0.092, 10), scale=(0.34, 0.092))
            self._sello_fondo = Entity(parent=self.sello_e, model=modelo_redondeado(0.32, 0.074, 8), scale=(0.32, 0.074),
                                       z=-0.001)
            self._sello_txt = Text("", parent=self.sello_e, origin=(0, 0), scale=escala_fuente(34), z=-0.002,
                                   font=tipografia.fuente_piel(titulo=True))
        self.sello_e.position = (posicion[0], posicion[1], -0.05)
        self.sello_e.rotation_z = -9
        self._sello_txt.text = texto
        self._sello_tono = tono
        self._escala_sello = max(0.2, float(escala))
        if self._escala_sello != 1.0:           # sello reducido a petición: la caja se ajusta al texto (nunca lo desborda)
            self._ajustar_caja_sello()
        ancho = getattr(self, "_ancho_sello", 0.34) if self._escala_sello != 1.0 else 0.34
        self._final_sello, self._inicio_sello, self._inicial_sello = calc.ajustar_sello(
            posicion, ancho, 0.092, self._escala_sello, limites)
        x, y = self._inicio_sello if not self.reducir else self._final_sello
        self.sello_e.position = (x, y, -0.05)
        self._al_golpe = al_golpe
        self._t_sello = -retardo
        self._pintar_sello(0.0)
        self.sello_e.enabled = True

    def _ajustar_caja_sello(self):
        try:
            ancho = max(0.34, float(self._sello_txt.width) * float(self._sello_txt.scale_x) + 0.06)
            if abs(ancho - getattr(self, "_ancho_sello", 0.34)) < 0.004:
                return
            self._ancho_sello = ancho
            self._sello_borde.model = modelo_redondeado(ancho, 0.092, 10)
            self._sello_borde.scale = (ancho, 0.092)
            self._sello_fondo.model = modelo_redondeado(ancho - 0.02, 0.074, 8)
            self._sello_fondo.scale = (ancho - 0.02, 0.074)
        except Exception:                       # noqa: BLE001  adorno: si falla, queda la caja de siempre
            pass

    def _pintar_sello(self, alfa):
        self._sello_borde.color = _rgba(self._sello_tono, alfa)
        self._sello_fondo.color = _rgba(estilo.COLOR_FONDO, alfa * 0.92)
        self._sello_txt.color = _rgba(self._sello_tono, alfa)

    def estrellas(self, cantidad, posicion=(0.64, 0.335), retardo=0.0):
        """Muestra 3 estrellas (llenas las `cantidad` primeras) que entran de una en una."""
        if self.roto:
            return
        if not self._estrellas:
            for i in range(N_ESTRELLAS):
                self._estrellas.append(Entity(parent=self, model=malla_estrella(), scale=0.0, enabled=False))
        for i, e in enumerate(self._estrellas):
            e.position = (posicion[0] + i * 0.062, posicion[1], -0.04)
            e.color = _rgba(DORADO if i < cantidad else GRIS_ESTRELLA, 1)
            e.enabled = True
        self._cantidad_estrellas = cantidad
        self._t_estrellas = -retardo
        self._pintar_estrellas()

    def _pintar_estrellas(self):
        for i, e in enumerate(self._estrellas):
            t = self._t_estrellas - i * 0.14
            e.scale = 0.052 * calc.rebote(t, desde=0.0, reducir=self.reducir) if t >= 0 or self.reducir else 0.0

    def medalla(self, texto, posicion=(0.60, 0.335), retardo=0.0):
        """Rótulo de medalla alineado a la DERECHA en `posicion` (a la izquierda de las estrellas)."""
        if self.roto:
            return
        if self.medalla_e is None:
            self.medalla_e = Text("", parent=self, origin=(0.5, 0), scale=escala_fuente(17), font=tipografia.fuente_piel(titulo=True),
                                  color=_rgba(DORADO, 1))
        self.medalla_e.text = texto
        self.medalla_e.position = (posicion[0], posicion[1], -0.04)
        self.medalla_e.enabled = True
        self._t_medalla = -retardo
        self.medalla_e.scale = 0.0 if not self.reducir else escala_fuente(17)

    # -- Programar --

    def programar(self, retardo, funcion):
        self._programados.append([retardo, funcion])

    # -- Bucle (lo llama el dueño una vez por frame) --

    def sincronizar(self, dt):
        if self.roto:
            return
        try:
            self._sincronizar(dt)
        except Exception as error:      # noqa: BLE001  guardián: nunca tumba la pantalla
            bv.avisar_una_vez("efectos_ui", error)
            self.apagar()

    def _sincronizar(self, dt):
        if self._programados:
            pendientes = []
            for item in self._programados:
                item[0] -= dt
                if item[0] <= 0:
                    item[1]()
                else:
                    pendientes.append(item)
            self._programados = pendientes
        self._avanzar_tarjetas(dt)
        self._avanzar_pools(dt)
        if self._t_racha is not None:
            self._t_racha += dt
            self.rotulo_racha.scale = escala_fuente(30) * calc.rebote(self._t_racha, desde=1.6, reducir=self.reducir)
            if self._t_racha > calc.DUR_REBOTE:
                self._t_racha = None
        if self._t_sello is not None:
            self._t_sello += dt
            escala, alfa, golpe = calc.caida_sello(self._t_sello, reducir=self.reducir,
                                                   inicial=getattr(self, "_inicial_sello", calc.ESCALA_SELLO_INICIAL))
            self.sello_e.scale = escala * getattr(self, "_escala_sello", 1.0)
            final = getattr(self, "_final_sello", None)
            if final is not None:
                x, y = calc.posicion_caida(self._inicio_sello, final, escala,
                                           getattr(self, "_inicial_sello", calc.ESCALA_SELLO_INICIAL))
                self.sello_e.position = (x, y, -0.05)
            self._pintar_sello(alfa)
            if golpe:
                self._t_sello = None
                if self.sonido:
                    _sonar(SONIDO_SELLO, 0.9, 0.8)
                if self._al_golpe is not None:
                    golpe_cb, self._al_golpe = self._al_golpe, None
                    golpe_cb()
        if self._t_estrellas is not None:
            self._t_estrellas += dt
            self._pintar_estrellas()
            if self._t_estrellas > 0.14 * N_ESTRELLAS + calc.DUR_REBOTE:
                self._t_estrellas = None
        if self._t_medalla is not None:
            self._t_medalla += dt
            if not self.reducir:
                self.medalla_e.scale = escala_fuente(17) * calc.rebote(self._t_medalla, desde=0.0)
            if self._t_medalla > calc.DUR_REBOTE:
                self._t_medalla = None

    def apagar(self):
        """Guardián: deja las tarjetas como estaban y apaga todos los efectos."""
        self.roto = True
        try:
            self.restaurar()
        except Exception:                # noqa: BLE001
            pass
        try:
            self.enabled = False
        except Exception:                # noqa: BLE001
            pass

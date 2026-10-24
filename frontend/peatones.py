# Peatones decorativos de Ciudad Nova (Ursina): un Personaje por cada Caminante de
# frontend/peatones_calculos.py (la lógica pura). Pasean por las calles y se detienen en las plazas;
# no tienen colisión con los jugadores ni afectan al modelo de la partida. Cuelgan de EscenaMundo,
# así que solo se mueven mientras el mundo está activo.
#
# Nivel de detalle (DETALLE_POR_DISTANCIA): cada Personaje tiene su propio update() (mezcla de clips y gestos de
# la cara), que costaba ~0,1 ms por peatón y frame aunque estuviera a 80 m. Los que están a más de
# DISTANCIA_DETALLE de la cámara solo corren su update() uno de cada PASO_LEJOS frames (escalonados, para que
# no coincidan): la mezcla y la cara van más lentas, algo que a esa distancia no se ve. El paseo (posición y
# rumbo) y el esqueleto (lo reproduce Panda en C++) siguen igual en cada frame. False = todos en cada frame.

from ursina import Entity, camera, time

from frontend.peatones_calculos import aspecto_peaton, crear_peatones, rasgos_peaton
from frontend import poses
from frontend.personaje import Personaje
from frontend.npc_modelo import crear_npc

CANTIDAD = 12
USAR_MODELOS = True      # peatones con los .glb de los personajes principales (npc_modelo.py); False = muñecos de cubos
SEMILLA = 2026
DETALLE_POR_DISTANCIA = True
DISTANCIA_DETALLE = 35.0  # m desde la cámara
PASO_LEJOS = 3            # frames entre dos update() de un peatón lejano
# Tonos de ropa apagados: se distinguen de los colores vivos de los roles jugables.
ROPA = ((150, 150, 158), (170, 140, 120), (120, 150, 140), (160, 120, 140), (130, 130, 160), (150, 160, 120),
        (176, 96, 84), (92, 124, 150), (140, 110, 160), (190, 170, 110), (104, 140, 104), (170, 170, 176))


class Peatones(Entity):

    def __init__(self, mundo, cantidad=CANTIDAD, **opciones):
        super().__init__(**opciones)
        self.caminantes = crear_peatones(mundo, cantidad, SEMILLA)
        self.personajes = []
        self._quietos = set()
        self._frame = 0
        for i, caminante in enumerate(self.caminantes):
            aspecto = aspecto_peaton(i, SEMILLA)
            if USAR_MODELOS:     # copia de uno de los 4 .glb con otra ropa; si falla, el muñeco de siempre
                personaje = crear_npc(i, SEMILLA, aspecto, rasgos_peaton(i, SEMILLA), ROPA[i % len(ROPA)], parent=self)
            else:
                aspecto = dict(aspecto, rasgos=rasgos_peaton(i, SEMILLA), piel_rgb=aspecto["piel"],
                               pelo_rgb=aspecto["pelo"])
                personaje = Personaje("", ROPA[i % len(ROPA)], apariencia=aspecto, parent=self)
            personaje.etiqueta.enabled = False
            personaje.aro.enabled = False
            personaje.automatico = False              # se anima aquí, y solo mientras camina (rendimiento)
            personaje.suelo = mundo.altura
            personaje.colocar(caminante.x, caminante.z)
            personaje.fijar_rumbo(caminante.rumbo)
            self.personajes.append(personaje)

    # Un paso de `dt` segundos (los tests lo llaman a mano).
    def avanzar(self, dt):
        for caminante, personaje in zip(self.caminantes, self.personajes):
            caminante.avanzar(dt)
            personaje.colocar(caminante.x, caminante.z)
            if caminante.en_movimiento:
                personaje.mirar_hacia(caminante.rumbo)
                personaje.girar(dt)
                personaje.animar_caminar(caminante.velocidad, dt)
                self._quietos.discard(personaje)
            elif personaje not in self._quietos:      # recién parado: pose de pie, una sola vez
                personaje.aplicar_pose(poses.POSE_PARADO)
                self._quietos.add(personaje)

    def update(self):
        self.avanzar(min(time.dt, 0.1))
        if DETALLE_POR_DISTANCIA:
            self._detalle_por_distancia(camera.world_x, camera.world_z)

    # Peatones lejanos: update() propio solo uno de cada PASO_LEJOS frames (ver DETALLE_POR_DISTANCIA). Este
    # update() corre antes que el de los Personaje (son hijos, se crean después), así que vale para este frame.
    def _detalle_por_distancia(self, cx, cz):
        self._frame += 1
        limite = DISTANCIA_DETALLE ** 2
        for i, personaje in enumerate(self.personajes):
            lejos = (personaje.x - cx) ** 2 + (personaje.z - cz) ** 2 > limite
            personaje.ignore = lejos and (self._frame + i) % PASO_LEJOS != 0

# Peatones decorativos de Ciudad Nova (Ursina): un Personaje por cada Caminante de
# frontend/peatones_calculos.py (la lógica pura). Pasean por las calles y se detienen en las plazas;
# no tienen colisión con los jugadores ni afectan al modelo de la partida. Cuelgan de EscenaMundo,
# así que solo se mueven mientras el mundo está activo.

from ursina import Entity, time

from frontend.peatones_calculos import aspecto_peaton, crear_peatones
from frontend import poses
from frontend.personaje import Personaje

CANTIDAD = 12
SEMILLA = 2026
# Tonos de ropa apagados: se distinguen de los colores vivos de los roles jugables.
ROPA = ((150, 150, 158), (170, 140, 120), (120, 150, 140), (160, 120, 140), (130, 130, 160), (150, 160, 120),
        (176, 96, 84), (92, 124, 150), (140, 110, 160), (190, 170, 110), (104, 140, 104), (170, 170, 176))


class Peatones(Entity):

    def __init__(self, mundo, cantidad=CANTIDAD, **opciones):
        super().__init__(**opciones)
        self.caminantes = crear_peatones(mundo, cantidad, SEMILLA)
        self.personajes = []
        self._quietos = set()
        for i, caminante in enumerate(self.caminantes):
            personaje = Personaje("", ROPA[i % len(ROPA)], apariencia=aspecto_peaton(i, SEMILLA), parent=self)
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

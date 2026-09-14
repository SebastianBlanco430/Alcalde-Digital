import pygame
import sys
from frontend.menus.menu_principal import MenuPrincipal

ANCHO = 800
ALTO = 600

pygame.init()
pantalla = pygame.display.set_mode((ANCHO, ALTO))
reloj = pygame.time.Clock()
jugando = True

escena_actual = MenuPrincipal(pantalla)

while jugando:
    eventos = pygame.event.get()
    for evento in eventos:
        if evento.type == pygame.QUIT:
            jugando = False

    escena_actual.manejar_eventos(eventos)
    escena_actual.actualizar()
    escena_actual.dibujar()

    pygame.display.flip()
    reloj.tick(60)

pygame.quit()
sys.exit()

# hacer los nodos, los arboles, verificar que funcionen. hacer los menus basicos (principal, seleccionar la cantidad de jugadores, roles y la de juego). y ver como hacer una prueba basica de la lógica y jugabilidad.

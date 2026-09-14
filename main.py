import pygame
import sys

ANCHO = 800
ALTO = 600

pygame.init()
pantalla = pygame.display.set_mode((ANCHO, ALTO))
reloj = pygame.time.Clock()
jugando = True

while jugando:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            jugando = False

    pantalla.fill((0, 0, 0))
    pygame.display.flip()
    reloj.tick(60)

pygame.quit()
sys.exit()

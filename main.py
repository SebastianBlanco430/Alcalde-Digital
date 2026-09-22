import pygame
import sys

from frontend.escenas.pantalla_inicio import PantallaInicio
from frontend.escenas.pantalla_juego import PantallaJuego

ANCHO = 800
ALTO = 600

pygame.init()
pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Alcalde Digital")
reloj = pygame.time.Clock()
jugando = True

# Jugador de prueba: la selección real de jugador todavía no existe
# (fuera de alcance de esta entrega, la construye arquitectura-mundos).
jugador_prueba = {"nombre": "Jugador 1", "rol": "ciudadano"}

# --- Cambio de escena TEMPORAL ---------------------------------------------
# Esto es un mecanismo mínimo (un flag + un if) solo para no arrancar el
# juego directo en PantallaJuego. NO es un sistema de escenas/estados real:
# eso lo diseñará más adelante el subagente `arquitectura-mundos`. No agregar
# más pantallas a este esquema; cuando exista el sistema real, reemplazar
# todo este bloque.
pantalla_inicio = PantallaInicio(pantalla)
escena_juego = None

while jugando:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            jugando = False
        elif escena_juego is None:
            pantalla_inicio.manejar_evento(evento)
        else:
            escena_juego.manejar_evento(evento)

    if escena_juego is None:
        pantalla_inicio.actualizar()
        pantalla_inicio.dibujar()
        if pantalla_inicio.terminada:
            escena_juego = PantallaJuego(pantalla, jugador_prueba)
    else:
        escena_juego.actualizar()
        escena_juego.dibujar()

    pygame.display.flip()
    reloj.tick(60)

pygame.quit()
sys.exit()

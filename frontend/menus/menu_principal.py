import sys
import pygame
from frontend.escenas.escena import Escena
from frontend.menus.menu_sel_rol import MenuSeleccionRoles


class MenuPrincipal(Escena):

    def __init__(self, ventana):
        super().__init__(ventana)

        self.fuente_titulo = pygame.font.Font(None, 64)
        self.fuente_boton = pygame.font.Font(None, 36)

        self.boton_jugar = pygame.Rect(300, 250, 200, 50)
        self.boton_salir = pygame.Rect(300, 330, 200, 50)

    def manejar_eventos(self, eventos):
        for evento in eventos:
            if evento.type == pygame.MOUSEBUTTONDOWN:
                if evento.button == 1:
                    if self.boton_jugar.collidepoint(evento.pos):
                        return MenuSeleccionRoles(self.ventana)
                    if self.boton_salir.collidepoint(evento.pos):
                        pygame.quit()
                        sys.exit()

        return self

    def actualizar(self):
        pass

    def dibujar(self):
        self.ventana.fill((0, 0, 0))

        texto_titulo = self.fuente_titulo.render("Alcalde Digital", True, (0, 255, 0))
        self.ventana.blit(texto_titulo, (230, 100))

        texto_jugar = self.fuente_boton.render("Jugar", True, (0, 255, 0))
        texto_salir = self.fuente_boton.render("Salir", True, (0, 255, 0))

        self.ventana.blit(
            texto_jugar, (self.boton_jugar.x + 65, self.boton_jugar.y + 15)
        )
        self.ventana.blit(
            texto_salir, (self.boton_salir.x + 70, self.boton_salir.y + 15)
        )

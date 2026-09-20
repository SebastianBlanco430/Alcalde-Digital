import sys
import pygame
from backend.jugador.jugador import Jugador
from frontend.escenas.escena import Escena


class MenuSeleccionRoles(Escena):

    def __init__(self, ventana):
        super().__init__(ventana)

        self.fuente_titulo = pygame.font.Font(None, 48)
        self.fuente_boton = pygame.font.Font(None, 32)

        self.boton_ciudadano = pygame.Rect(300, 180, 200, 45)
        self.boton_periodista = pygame.Rect(300, 240, 200, 45)
        self.boton_influencer = pygame.Rect(300, 300, 200, 45)
        self.boton_candidato = pygame.Rect(300, 360, 200, 45)

        self.boton_volver = pygame.Rect(300, 450, 200, 45)

    def manejar_eventos(self, eventos):
        for evento in eventos:
            if evento.type == pygame.MOUSEBUTTONDOWN:
                if evento.button == 1:
                    pos = evento.pos

                    rol_elegido = None

                    if self.boton_ciudadano.collidepoint(pos):
                        rol_elegido = "Ciudadano"
                    elif self.boton_periodista.collidepoint(pos):
                        rol_elegido = "Periodista"
                    elif self.boton_influencer.collidepoint(pos):
                        rol_elegido = "Influencer"
                    elif self.boton_candidato.collidepoint(pos):
                        rol_elegido = "Candidato"
                    elif self.boton_volver.collidepoint(pos):
                        from frontend.menus.menu_principal import MenuPrincipal

                        return MenuPrincipal(self.ventana)

                    if rol_elegido is not None:
                        jugador = Jugador(rol_elegido)
                        # aqui se retornara la pantalla de juego, o sea entra automaticamente

        return self

    def actualizar(self):
        pass

    def dibujar(self):
        self.ventana.fill((0, 0, 0))

        texto_titulo = self.fuente_titulo.render("Selecciona tu Rol", True, (0, 255, 0))
        self.ventana.blit(texto_titulo, (260, 80))

        texto_ciudadano = self.fuente_boton.render("Ciudadano", True, (0, 255, 0))
        texto_periodista = self.fuente_boton.render("Periodista", True, (0, 255, 0))
        texto_influencer = self.fuente_boton.render("Influencer", True, (0, 255, 0))
        texto_candidato = self.fuente_boton.render("Candidato", True, (0, 255, 0))
        texto_volver = self.fuente_boton.render("Volver", True, (0, 255, 0))

        self.ventana.blit(
            texto_ciudadano,
            (self.boton_ciudadano.x + 40, self.boton_ciudadano.y + 10),
        )
        self.ventana.blit(
            texto_periodista,
            (self.boton_periodista.x + 40, self.boton_periodista.y + 10),
        )
        self.ventana.blit(
            texto_influencer,
            (self.boton_influencer.x + 40, self.boton_influencer.y + 10),
        )
        self.ventana.blit(
            texto_candidato,
            (self.boton_candidato.x + 40, self.boton_candidato.y + 10),
        )
        self.ventana.blit(
            texto_volver, (self.boton_volver.x + 60, self.boton_volver.y + 10)
        )

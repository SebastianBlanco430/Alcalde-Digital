# Registro PEREZOSO de las escenas del lobby online. main.py solo lo importa cuando
# frontend.online_config.ONLINE es True; con ONLINE=False ni este módulo ni backend.red se cargan.
#
#   registrar(gestor, mundo, semilla, al_inicio, al_empezar=None, servicios=None) -> al_online
# `al_online()` abre el menú online (se pasa a EscenaInicio como `al_online`). `al_empezar(cliente, info)` lo
# aporta quien conecte el juego en línea (T6/T7; ver online_servicios para el contenido de `info`).

from frontend.escenas import escena_ajustes
from frontend.escenas.escena_error_red import EscenaErrorRed
from frontend.escenas.escena_online_menu import EscenaOnlineMenu
from frontend.escenas.escena_sala import EscenaSala
from frontend.online_servicios import ServiciosOnline

ESCENA_ONLINE_MENU = "online_menu"
ESCENA_SALA = "online_sala"
ESCENA_ERROR_RED = "online_error"


def _seccion_online(s):
    gestor = s.gestor
    actual = gestor.actual
    s.anadir_texto("El alias y el último anfitrión se guardan solos al crear o unirte a una sala.", tenue=False)
    texto = s.anadir_texto(f"Alias: {actual.nombre_en_linea or '(sin definir)'}   ·   "
                           f"Último anfitrión: {actual.ultimo_host or '(ninguno)'}")

    def olvidar():
        gestor.cambiar(nombre_en_linea="", ultimo_host="")
        texto.text = "Alias: (sin definir)   ·   Último anfitrión: (ninguno)"
    s.anadir_boton("Datos guardados", "Olvidar", olvidar)
    s.anadir_texto("El tráfico en línea no va cifrado: usa red local o una VPN.")


def registrar(gestor, mundo, semilla, al_inicio, al_empezar=None, servicios=None):
    servicios = servicios or ServiciosOnline(mundo, semilla)
    escena_ajustes.registrar_seccion("Online", _seccion_online)

    def a_menu(pagina=None):
        gestor.cambiar_a(ESCENA_ONLINE_MENU, pagina=pagina)

    gestor.registrar(ESCENA_ONLINE_MENU, EscenaOnlineMenu(
        servicios, al_atras=al_inicio,
        al_conectado=lambda sesion: gestor.cambiar_a(ESCENA_SALA, sesion=sesion),
        al_fallo=lambda motivo, pagina: gestor.cambiar_a(ESCENA_ERROR_RED, motivo=motivo, pagina=pagina)))
    gestor.registrar(ESCENA_SALA, EscenaSala(
        al_empezar=al_empezar, al_salir=lambda: a_menu(None),
        al_fallo=lambda motivo, pagina: gestor.cambiar_a(ESCENA_ERROR_RED, motivo=motivo, pagina=pagina)))
    gestor.registrar(ESCENA_ERROR_RED, EscenaErrorRed(al_reintentar=a_menu, al_menu=al_inicio))
    return lambda: a_menu(None)

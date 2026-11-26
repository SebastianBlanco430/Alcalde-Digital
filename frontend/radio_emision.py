# Emisión de la Rádio Comunitária: SIEMPRE en 3D (frontend/radio3d_escena.py, docs/RADIO_3D.md): la cámara deja al
# jugador, orbita la torre de la radio y el globo de las cinemáticas dice cada línea. Va envuelta en un fundido a negro al
# entrar y al salir (frontend/radio_fundido.py, ALCALDE_RADIO_FUNDIDO).
#
# Cada línea pasa sola a su tiempo de lectura; Espacio/clic adelantan y Escape salta la emisión entera. Solo dibuja: qué
# decir lo decide backend/logica/radio_guion.py y cuándo, frontend/radio_calculos.py. Bandera: ALCALDE_HILO_RADIO.
#
#   crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None) -> entidad (.terminada, .saltar())
#
# Antes había una radio 2D animada de respaldo (sin torre, con ALCALDE_RADIO3D=0 o si la 3D fallaba al empezar). Se quitó:
# la radio solo se ve en 3D. Si la 3D no se puede montar (mundo sin torre, ALCALDE_RADIO3D=0 o un fallo al crearla), no
# hay emisión: al_terminar se llama enseguida y la noche pasa igual (radio_registro._cerrar), sin pantalla negra.

import sys

# API compartida con la otra parte (tests/test_a_api_compartida.py: solo se añade). Eran de la radio 2D, que se quitó:
# quedan para no romper a quien los importe, pero ya no se usan aquí.
ROTULOS = {"saltar": "Saltar", "continuar": "Seguir"}
TONO_RADIO = (196, 92, 60)
GRIS_ALTAVOZ = (40, 36, 40)
CENTRO_RADIO = (0.0, 0.07)
FRACCION_HABLANDO = 0.85


def RadioAnimada(vinetas_entidad, vinetas):    # noqa: N802  nombre de la API compartida
    """Compatibilidad: la radio 2D animada se quitó (la radio solo se ve en 3D). No dibuja nada y devuelve None."""
    return None


class _SinEmision:
    """Lo que devuelve crear_emision cuando no hay 3D: ya terminada (la radio la da por cerrada)."""
    terminada = True

    def saltar(self):
        pass


def crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None):
    from frontend import radio_fundido, radio3d_escena

    def guardia():
        # Escape pudo abrir la pausa debajo de la emisión: se cierra (como la cinemática del final).
        if getattr(escena_mundo, "en_pausa", False):
            escena_mundo.alternar_pausa(False)

    try:
        con_3d = radio3d_escena.disponible(escena_mundo)
    except Exception as error:                  # noqa: BLE001
        print(f"[radio] sin emisión 3D ({type(error).__name__}: {error})", file=sys.stderr)
        con_3d = False
    if not con_3d:
        al_terminar()
        return _SinEmision()

    def crear_3d(fin):
        return radio3d_escena.EmisionRadio3D(escena_mundo, vinetas, fin, al_poner=al_poner, guardia=guardia)

    # Fundido a negro antes y después: la emisión se crea con la pantalla ya negra. Si la 3D falla al crearse, el
    # fundido se abre y avisa al_terminar (la noche pasa igual).
    return radio_fundido.crear(escena_mundo, crear_3d, al_terminar, guardia)

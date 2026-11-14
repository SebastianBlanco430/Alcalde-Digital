# Sección «Partida» de la pantalla de Ajustes (y por tanto del menú de pausa): botón «Borrar partida guardada» con
# confirmación de DOS pasos (1.º pulsación: «Sí, borrar» y el aviso de debajo; 2.º: borra; «Cancelar» vuelve atrás).
# Entra por escena_ajustes.registrar_seccion (sin editar la escena); la llama registro_guardado.registrar().
# La lógica de los dos pasos es pura (ConfirmarBorrado) y se prueba sin ventana. El texto lleva el mensaje completo
# (no se apoya solo en el color), así que no depende del filtro de daltonismo.

from backend.logica import guardado_aviso

NOMBRE_SECCION = "Partida"
TEXTO_BORRAR = "Borrar partida guardada"
# corto para que quepa en el botón: el mensaje de debajo ya pide «Pulsa de nuevo para borrar»
TEXTO_CONFIRMAR = "Sí, borrar"
INFO = ("Tu partida se guarda solo en este equipo, en un archivo de tu carpeta de usuario. Si la borras, «Continuar» "
        "desaparece y no se puede recuperar.")
MENSAJES = {
    "borrado": "Partida borrada de este equipo. Esta partida ya no se autoguarda.",
    "nada": "No hay ninguna partida guardada.",
    "armado": "Pulsa de nuevo para borrar, o «Cancelar».",
    "": "",
}


class ConfirmarBorrado:
    """Dos pasos: pulsar() la primera vez arma la confirmación; la segunda borra. cancelar() desarma."""

    def __init__(self, borrar=None):
        self._borrar = borrar or guardado_aviso.borrar_partida
        self.armado = False

    def texto_boton(self):
        return TEXTO_CONFIRMAR if self.armado else TEXTO_BORRAR

    def pulsar(self):
        """Devuelve la clave del mensaje: «armado» (falta confirmar), «borrado» o «nada»."""
        if not self.armado:
            self.armado = True
            return "armado"
        self.armado = False
        return self._borrar()

    def cancelar(self):
        self.armado = False
        return ""


# `s` = escena_ajustes.Seccion (o un doble con anadir_texto / anadir_boton / en_mostrar).
def construir_seccion(s, borrar=None):
    estado = ConfirmarBorrado(borrar)
    s.anadir_texto(INFO, alto=0.09)
    mensaje = s.anadir_texto("", tenue=False)
    cancelar = None

    def refrescar(clave=""):
        boton.text = estado.texto_boton()          # el botón de tinta encoge el texto largo («¿Seguro? …»)
        # cambiar_texto lo vuelve a encajar en el panel; un doble de pruebas sin él solo asigna el texto
        cambiar = getattr(s, "cambiar_texto", None)
        if cambiar is not None:
            cambiar(mensaje, MENSAJES.get(clave, "") or " ")
        else:
            mensaje.text = MENSAJES.get(clave, "")
        if cancelar is not None:
            cancelar.enabled = estado.armado

    def pulsar():
        refrescar(estado.pulsar())

    def cancelar_clic():
        refrescar(estado.cancelar())

    boton = s.anadir_boton("Privacidad", TEXTO_BORRAR, pulsar)
    cancelar = s.anadir_boton("", "Cancelar", cancelar_clic)
    cancelar.enabled = False
    s.en_mostrar(lambda: refrescar(estado.cancelar()))
    return estado


def registrar(borrar=None):
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, lambda s: construir_seccion(s, borrar))

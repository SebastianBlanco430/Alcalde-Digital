# Pestaña «Movimiento» de Ajustes: el interruptor «Reducir movimiento» (sin temblores, destellos, partículas ni cámara
# lenta en las misiones visuales). Entra por el registro público de la escena de Ajustes (escena_ajustes.registrar_seccion),
# sin editarla, igual que frontend/graficos_ajustes.py. La registra frontend/registro_misiones_visuales.py.
#
# Se guarda en ajustes.json como la clave extra «reducir_movimiento» (los ajustes antiguos que no la traen leen
# «Desactivado»). ALCALDE_REDUCIR_MOVIMIENTO=1/0 manda sobre lo guardado (frontend/banderas_visuales.reducir_movimiento).

from frontend import banderas_visuales as bv

NOMBRE_SECCION = "Movimiento"
ETIQUETA = "Reducir movimiento"
DESCRIPCION = ("Quita temblores, destellos, partículas y cámara lenta de las misiones. Las animaciones pasan a "
               "aparecer directamente o con un fundido suave.")


def valor_guardado(gestor):
    return bool(gestor.actual.extras.get(bv.CLAVE_AJUSTE, bv.REDUCIR_MOVIMIENTO))


# `s` = escena_ajustes.Seccion.
def construir_seccion(s):
    from frontend.escenas.escena_ajustes import Interruptor
    fila = s._nueva_fila(ETIQUETA)
    control = Interruptor(fila, valor_guardado(s.gestor), lambda v: s.gestor.cambiar(**{bv.CLAVE_AJUSTE: bool(v)}))
    s.controles[bv.CLAVE_AJUSTE] = control
    s.filas_foco.append([control])
    s.anadir_texto(DESCRIPCION, alto=0.11)

    # «Restablecer» / «Descartar» cambian los extras: el interruptor se mantiene a la par.
    def sincronizar(ajustes, cambiadas):
        if bv.CLAVE_AJUSTE in cambiadas:
            control.fijar_valor(valor_guardado(s.gestor))

    s.gestor.suscribir(sincronizar, llamar_ya=False)


def registrar():
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)

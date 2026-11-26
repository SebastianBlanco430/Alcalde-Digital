# Pestaña «Mando» de Ajustes: el esquema del mando de Xbox One (también vale para cualquier mando que Windows vea como
# uno de Xbox). Una fila por botón con su icono (frontend/mando_iconos.py), qué hace caminando por la ciudad y qué hace
# en los menús. Los datos salen de mando_calculos.ESQUEMA, la misma tabla que usa el traductor de botones.
#
# Entra por el registro público de la escena de Ajustes (escena_ajustes.registrar_seccion), como
# frontend/movimiento_ajustes.py. La registra frontend/mando.py al instalarse (con ALCALDE_MANDO=0 no hay pestaña).
# Se ve aunque no haya mando conectado: así se puede mirar antes de enchufarlo. No importa ursina (contrato MVC: con
# ursina sería una vista importando la escena de Ajustes); los iconos los crea frontend/mando_iconos.py.

from frontend import mando_calculos as mc

NOMBRE_SECCION = "Mando"
ALTO_CABECERA = 0.05
PX_FILA = 15
X_ICONO = -0.6
X_NOMBRE = -0.565
X_MUNDO = -0.37
X_MENU = 0.16
ANCHO_MUNDO = 0.51
ANCHO_MENU = 0.48


# `s` = escena_ajustes.Seccion.
def construir_seccion(s):
    from frontend import diseno_adaptable, estilo
    from frontend.componentes import escala_fuente
    from frontend.escenas.escena_ajustes import Y_CONTENIDO, Y_FONDO_CONTENIDO, _texto
    from frontend.mando_iconos import icono_en

    alto_fila = (Y_CONTENIDO - Y_FONDO_CONTENIDO - ALTO_CABECERA) / len(mc.ESQUEMA)
    cabecera = s._nueva_fila(None, ALTO_CABECERA)
    _texto(cabecera, "Botón", X_ICONO - 0.015, 0, 16, estilo.COLOR_ACENTO, titulo=True)
    _texto(cabecera, "Caminando por la ciudad", X_MUNDO, 0, 16, estilo.COLOR_ACENTO, titulo=True)
    _texto(cabecera, "En menús, teléfono y minijuegos", X_MENU, 0, 16, estilo.COLOR_ACENTO, titulo=True)
    lado = min(alto_fila * 0.85, 0.036)
    for icono, _boton, nombre, mundo, menu in mc.ESQUEMA:
        fila = s._nueva_fila(None, alto_fila)
        icono_en(fila, icono, lado, (X_ICONO, 0, -0.004))
        _texto(fila, nombre, X_NOMBRE, 0, PX_FILA, estilo.COLOR_TEXTO_TENUE)
        for x, ancho, cadena in ((X_MUNDO, ANCHO_MUNDO, mundo), (X_MENU, ANCHO_MENU, menu)):
            t = _texto(fila, cadena, x, 0, PX_FILA, estilo.COLOR_TEXTO)
            diseno_adaptable.ajustar_texto(t, ancho, escala_base=escala_fuente(PX_FILA), escala_min=0.75, max_lineas=1)


def registrar():
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)

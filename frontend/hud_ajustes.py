# Fila «HUD» (Completo / Mínimo) de Ajustes (M3.5). Entra por el registro público de la escena de Ajustes
# (escena_ajustes.registrar_seccion), sin editarla, igual que frontend/graficos_ajustes.py y movimiento_ajustes.py.
# La registra frontend/hud.py (HudMundo) la primera vez que se crea, solo si ALCALDE_HUD_MINIMO_AJUSTE no la apaga.
# El valor es el campo `hud_modo` de backend/logica/ajustes.py; el HUD lo sigue en vivo (GestorAjustes.suscribir).
# Piel BOTW (docs/ESTILO_BOTW.md): pestaña «Estilo» con la fila «Estilo de interfaz: BOTW / Clásico», clave extra
# «ui_botw»; se aplica al reiniciar. Va en su pestaña porque en «Interfaz» ya no cabe (compactar no baja de 0,86). Sale
# siempre (la variable ALCALDE_UI_BOTW, si está puesta, manda sobre lo guardado).

from frontend import hud_modo_calculos as hm
from frontend import pase_final_calculos as pf
from frontend import pulseras_visibles_calculos as pv
from frontend import ui_botw_calculos as ub

NOMBRE_SECCION = "Interfaz"
NOMBRE_SECCION_ESTILO = "Estilo"
ETIQUETA = "HUD"
DESCRIPCION = ("Mínimo deja solo la misión y el reloj. La franja de confianza, el minimapa, el dinero y el teléfono "
               "aparecen unos segundos cuando cambian o al pulsar su tecla (M/N el mapa, Tab el teléfono).")

# M5.3 (ALCALDE_PULSERAS_VISIBLES): «Pulseras en el HUD», campo `pulseras_hud` de backend/logica/ajustes.py.
ETIQUETA_PULSERAS = "Pulseras en el HUD"
DESCRIPCION_PULSERAS = ("Siempre: las dos pulseras pequeñas junto al reloj. Al cambiar: solo 30 s cuando sube o baja "
                        "una (con el HUD en Mínimo se portan así).")

# T3 (ALCALDE_TINTA_PANTALLA): «Tinta», campo `tinta_pantalla` de backend/logica/ajustes.py (frontend/pase_final.py).
ETIQUETA_TINTA = "Tinta"
DESCRIPCION_TINTA = "Contornos: solo el borde de cada figura. Cómic: además, líneas de tinta en siluetas y pliegues."

_registrada = False


# `s` = escena_ajustes.Seccion.
def construir_seccion(s):
    if hm.activo():
        s.anadir_selector(ETIQUETA, "hud_modo", hm.opciones_selector())
        s.anadir_texto(DESCRIPCION, alto=0.11)
    if pv.activo():
        s.anadir_selector(ETIQUETA_PULSERAS, pv.CLAVE_AJUSTE, pv.opciones_selector())
        s.anadir_texto(DESCRIPCION_PULSERAS, alto=0.11)
    if pf.tinta_activa():
        s.anadir_selector(ETIQUETA_TINTA, "tinta_pantalla", pf.opciones_selector())
        s.anadir_texto(DESCRIPCION_TINTA, alto=0.08)


# Pestaña «Estilo» (extra «ui_botw»): un Selector a mano porque anadir_selector solo liga campos conocidos.
def construir_estilo(s):
    from frontend.escenas.escena_ajustes import Selector
    fila = s._nueva_fila(ub.ETIQUETA_AJUSTE)
    control = Selector(fila, ub.OPCIONES_AJUSTE, ub.indice_ajuste(ub.valor_guardado(s.gestor.actual.extras)),
                       lambda v: s.gestor.cambiar(**{ub.CLAVE_AJUSTE: bool(v)}))
    s.controles[ub.CLAVE_AJUSTE] = control
    s.filas_foco.append([control])
    s.anadir_texto(ub.DESCRIPCION_AJUSTE, alto=0.11)

    # «Restablecer» / «Descartar» cambian los extras: el selector se mantiene a la par.
    def sincronizar(ajustes, cambiadas):
        if ub.CLAVE_AJUSTE in cambiadas:
            control.fijar_indice(ub.indice_ajuste(ub.valor_guardado(s.gestor.actual.extras)))

    s.gestor.suscribir(sincronizar, llamar_ya=False)


def registrar():
    """Añade la pestaña una sola vez (registrar_seccion reconstruye la pantalla de Ajustes cada vez que se llama)."""
    global _registrada
    if _registrada:
        return False
    from frontend.escenas import escena_ajustes
    if hm.activo() or pv.activo() or pf.tinta_activa():
        escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
    escena_ajustes.registrar_seccion(NOMBRE_SECCION_ESTILO, construir_estilo)
    _registrada = True
    return True

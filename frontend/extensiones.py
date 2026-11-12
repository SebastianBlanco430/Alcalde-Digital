# Punto de extensión para las escenas nuevas (mundo digital, parkour...): main.py llama UNA vez a aplicar() y cada
# módulo registrado expone `registrar(gestor, conexion, escena_mundo)`, que crea y registra su escena y se engancha a
# la conexión. Así los subagentes no editan main.py ni conexion_flujo.py más que esa llamada única.
#
# MODULOS lista rutas de módulo. Si el módulo AÚN NO EXISTE se omite sin ruido (permite listar los de las olas
# siguientes); cualquier otro error (import roto dentro del módulo, registrar() que falla) se propaga.

import importlib

MODULOS = (
    "frontend.registro_mundo_digital",     # Ola 2, subagente A
    "frontend.registro_parkour",           # Ola 2, subagente B
    "frontend.registro_archivo_casos",     # Ola 3, subagente E (Archivo de casos, tecla J)
    "frontend.registro_consecuencias",     # Ola 3, subagente D
    "frontend.registro_guardado",          # A5: autoguardado de la partida local y «Continuar» en el menú
    "frontend.registro_veredicto",         # A2d paso 3: avisos de «+R$» y del veredicto al cerrar una misión
    "frontend.registro_ambiente_npc",      # plan final 3-5: alimenta ambiente_vivo; conducta, densidad y globos de los NPC
    "frontend.registro_manillas",          # plan final 6: manillas de Bonfim (brazalete del HUD, leyenda B y cintas en los NPC)
    "frontend.registro_reloj",             # plan final 1: chip «Día N · hh:mm», enganche de avanzar_tiempo y pantalla final de la semana
    "frontend.registro_dilemas",           # plan final 7: dilemas jugables (mensaje en el teléfono, tecla K, panel modal)
    "frontend.registro_minijuegos",         # minijuegos de verificar (6 pantallas distintas; ALCALDE_MINIJUEGOS=0 las apaga)
    "frontend.registro_ciudad_viva",       # plan final 5: la ciudad cambia de aspecto con los indicadores (luz, cielo, niebla, basura, flores...)
    "frontend.registro_etapas_final",      # finales por etapas: medidor, fuego/fiesta, NPC, tinte y música según el índice (-3..+3)
)


def aplicar(gestor, conexion, escena_mundo, modulos=MODULOS):
    aplicados = []
    for ruta in modulos:
        try:
            modulo = importlib.import_module(ruta)
        except ModuleNotFoundError as error:
            if error.name == ruta:
                continue
            raise
        modulo.registrar(gestor, conexion, escena_mundo)
        aplicados.append(ruta)
    return aplicados

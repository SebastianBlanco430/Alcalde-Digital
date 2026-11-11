# Tabla de teclas del juego (documentación ejecutable, Python puro). NO mueve ninguna tecla: cada escena sigue
# leyendo la suya. Sirve para que las escenas nuevas (mundo digital, parkour, archivo de casos) elijan teclas libres
# y para que un test detecte si dos acciones del mundo chocan o si esta tabla se desincroniza del código.
#
# Decisión de Sam (2026-11-08): el mapa grande queda en N y «Seguir misión» en M.

# Acciones del mundo 3D (EscenaMundo / ControladorJugador y sus integraciones).
TECLAS_MUNDO = {
    "mover": "wasd/flechas",
    "correr": "shift",
    "saltar": "space",
    "turbo_vehiculo": "control",
    "interactuar": "e",
    "telefono": "tab",
    "seguir_mision": "m",
    "mapa_grande": "n",
    "inventario": "i",
    "pausa": "escape",
    "telemetria": "f3",
}

# Teclas que otras partes del juego usan en el mundo y no deben reasignarse.
TECLAS_MUNDO_EXTRA = ("g", "1", "2", "3", "4", "5", "6", "7", "8", "9")     # saludos online

# Asignaciones elegidas para las funciones nuevas (libres en el mundo al 2026-11-08).
TECLA_ARCHIVO_CASOS = "j"

# Libres razonables para funciones futuras en el mundo.
TECLAS_LIBRES = ("f1", "f2", "f5", "f6", "k", "l")


# Teclas de una sola letra/fn realmente ocupadas en el mundo (sin las combinadas como wasd/flechas).
def teclas_ocupadas():
    ocupadas = set(TECLAS_MUNDO_EXTRA)
    for valor in TECLAS_MUNDO.values():
        if "/" not in valor and valor != "wasd/flechas":
            ocupadas.add(valor)
    ocupadas.update("wasd")
    ocupadas.update(("up arrow", "down arrow", "left arrow", "right arrow"))
    return ocupadas


# True si `tecla` está libre en el mundo (para validar una asignación nueva).
def esta_libre(tecla):
    return tecla.lower() not in teclas_ocupadas()

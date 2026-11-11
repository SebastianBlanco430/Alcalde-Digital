# Banderas de la economía (inventario, dinero, comercios, trabajos). Módulo mínimo y SIN importaciones del
# juego: se puede leer desde main.py y las escenas sin arrastrar nada. Todo False = el juego de antes.
#
# ECONOMIA: inventario (tecla I), chip de dinero, billetera y pago de misiones. Activa por defecto en esta
# entrega; se apaga con la variable de entorno ALCALDE_ECONOMIA=0.
# Las demás llegan en fases posteriores y por ahora están apagadas.

# BUILD DE TIENDA (publicación en una tienda de apps): contenido sensible apagado. Esta es la receta; los valores de
# abajo NO cambian (son los de desarrollo/estudio):
#   ITEMS_SENSIBLES = False  (ya es el valor por defecto: sin pistola ni cuchillo)
#   EASTER_EGGS     = False  (backend/datos/barrio_favela.py: sin «TALCO SUSPEITO» ni la armería de juguete)
#   VENDEDOR_CALLE  = revisar con la clasificación por edades (docs/CONTENIDO_Y_CLASIFICACION.md, sección 2)
#   TRABAJO_ONLINE  = False  (ya es el valor por defecto)
# Nunca activar ITEMS_SENSIBLES y VENDEDOR_CALLE a la vez en esa build. Ninguna bandera se cambia desde el juego.

import os

ECONOMIA = os.environ.get("ALCALDE_ECONOMIA") != "0"
COMERCIOS = True           # tiendas del mercado (frontend/comercios_mundo.py)
TRABAJOS = True            # puestos de trabajo con minijuego 2D (frontend/trabajo_mundo.py)
VENDEDOR_CALLE = True      # vendedor de bicarbonato (frontend/vendedor_calle.py)
GESTOS_MANO = True         # gesto de dar/recibir con las manos del personaje
ITEMS_SENSIBLES = False    # cuchillo pequeño y pistola como objetos de cintura
CANSANCIO = True           # fatiga >= 100 impide trabajar
TRABAJO_ONLINE = False     # trabajar en partidas en línea (apagado en v1)
# GAMESTATE: confianza por grupo, relaciones y flags (backend/logica/game_state.py). Solo hot-seat; ALCALDE_GAMESTATE=0 lo apaga.
GAMESTATE = os.environ.get("ALCALDE_GAMESTATE") != "0"
GAMESTATE_ONLINE = False   # en línea no hay consecuencias de confianza (el protocolo no conoce el GameState)
# ARCHIVO_CASOS: panel del Archivo de casos (tecla J en el mundo; frontend/registro_archivo_casos.py). False = no se crea.
ARCHIVO_CASOS = True
# TRANSPORTE: viaje rápido del mapa grande (mototáxi en 3 paradas y teleférico entre las dos estaciones;
# frontend/transporte_mundo.py). Solo tiene efecto con el mapa grande; con el mundo chico no existe. ALCALDE_TRANSPORTE=0 lo apaga.
TRANSPORTE = os.environ.get("ALCALDE_TRANSPORTE") != "0"
# CONSECUENCIAS: diálogo reactivo de los NPC clave, vigilancia policial en el minimapa y reacción de Seu Zé según la
# confianza (frontend/registro_consecuencias.py). Necesita GAMESTATE; ALCALDE_CONSECUENCIAS=0 la apaga.
CONSECUENCIAS = os.environ.get("ALCALDE_CONSECUENCIAS") != "0"

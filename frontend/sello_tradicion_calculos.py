# Sello de la Torre de la Tradición: la parte PURA (no importa ursina). Ver frontend/sello_tradicion.py (lo que dibuja)
# y backend/logica/sello_rumores.py (qué lleva sello y en qué capa). Hilo conductor: docs/HILO_CONDUCTOR.md.
#
# FORMA: silueta de una TORRE DE RELOJ dentro de un sello redondo (anillo de tinta): escalón, cuerpo con puerta, cornisa,
# techo a dos aguas y una esfera con dos manecillas. No es la Alcaldía (no tiene columnas ni bandera): así «sello» no
# se lee como «oficial». Todo con primitivas (rectángulos, discos y un triángulo) en un cuadrado de lado 1 centrado en 0.
#
# CAPAS (estilo_de_capa): lado en px de 720 de alto (nunca menos de LADO_MINIMO_PX para que se lea), alfa y sitio:
#   1 «esquina»: pequeño en la esquina del mensaje (se distingue);   2 «remitente»: junto al remitente, más visible;
#   3-4 «completo»: grande y opaco.  La marca de agua de los minijuegos usa alfa_marca_agua().

LADO_MINIMO_PX = 16
TONO_SELLO = (150, 46, 52)          # granate del Partido de la Tradición
TONO_PAPEL = (238, 228, 205)

# (lado_px, alfa, sitio) por capa. Crece con la semana: los días 1-2 ya se ve (pequeño, pero se distingue: antes con 16
# px y alfa 0,45 casi no se notaba); hacia el final, grande y opaco. Nunca rompe lo pactado: no dice «falso», solo firma.
CAPAS = {
    1: (20, 0.72, "esquina"),
    2: (26, 0.9, "remitente"),
    3: (36, 1.0, "completo"),
    4: (42, 1.0, "completo"),
}
# La marca de agua de los minijuegos ya asoma, muy tenue, desde el día 1.
ALFA_MARCA_AGUA = {1: 0.09, 2: 0.17, 3: 0.26, 4: 0.3}


def estilo_de_capa(capa):
    """(lado_px, alfa, sitio) de la capa; la 1 si no se conoce. El lado nunca baja de LADO_MINIMO_PX."""
    lado, alfa, sitio = CAPAS.get(capa, CAPAS[1])
    return max(LADO_MINIMO_PX, lado), alfa, sitio


def alfa_marca_agua(capa):
    """Alfa de la marca de agua en las imágenes de los minijuegos; None si la capa no la lleva."""
    return ALFA_MARCA_AGUA.get(capa)


# Piezas del emblema: dicts {"tipo": "rect" | "disco" | "tri", "x", "y", "ancho", "alto", "tono": "sello" | "papel",
# "giro"} en el cuadrado unidad. En orden de dibujo (las últimas, delante).
def piezas():
    return [
        {"tipo": "disco", "x": 0.0, "y": 0.0, "ancho": 1.0, "alto": 1.0, "tono": "sello"},
        {"tipo": "disco", "x": 0.0, "y": 0.0, "ancho": 0.86, "alto": 0.86, "tono": "papel"},
        {"tipo": "rect", "x": 0.0, "y": -0.31, "ancho": 0.5, "alto": 0.07, "tono": "sello"},
        {"tipo": "rect", "x": 0.0, "y": -0.06, "ancho": 0.3, "alto": 0.46, "tono": "sello"},
        {"tipo": "rect", "x": 0.0, "y": -0.22, "ancho": 0.09, "alto": 0.13, "tono": "papel"},
        {"tipo": "rect", "x": 0.0, "y": 0.18, "ancho": 0.38, "alto": 0.05, "tono": "sello"},
        {"tipo": "tri", "x": 0.0, "y": 0.29, "ancho": 0.38, "alto": 0.17, "tono": "sello"},
        {"tipo": "disco", "x": 0.0, "y": 0.04, "ancho": 0.19, "alto": 0.19, "tono": "papel"},
        {"tipo": "rect", "x": 0.0, "y": 0.075, "ancho": 0.022, "alto": 0.075, "tono": "sello"},
        {"tipo": "rect", "x": 0.028, "y": 0.04, "ancho": 0.056, "alto": 0.022, "tono": "sello"},
    ]


def tono_de(nombre):
    return TONO_PAPEL if nombre == "papel" else TONO_SELLO

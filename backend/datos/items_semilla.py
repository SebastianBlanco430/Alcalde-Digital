# Catálogo semilla de objetos del inventario (datos puros). Precio en R$ (None = no se vende).
# Bolsillo: celular y billetera son `fijo` (el jugador siempre los lleva). Los `sensible` (cuchillo pequeño,
# pistola) son objetos de cintura sin precio ni efecto; el juego los muestra solo tras una bandera.

from backend.logica.inventario import DefItem, PEQUENO, MEDIANO, GRANDE

_ITEMS = (
    # -- Pequeños (bolsillo) --
    DefItem("celular", "Celular", PEQUENO, 0.2, categoria="tecnologia", fijo=True,
            descripcion="Tu teléfono: mensajes de Civitas y misiones."),
    DefItem("billetera", "Billetera", PEQUENO, 0.1, categoria="dinero", fijo=True,
            descripcion="Guarda tu dinero en reales (R$)."),
    DefItem("llaves", "Llaves", PEQUENO, 0.1, categoria="llave", descripcion="Las llaves de casa."),
    DefItem("bolsita", "Bolsita vacía", PEQUENO, 0.01, apilable=5, categoria="cocina", precio=1,
            descripcion="Una bolsita de plástico vacía."),
    DefItem("bicarbonato", "Bolsita de bicarbonato", PEQUENO, 0.05, apilable=3, categoria="cocina", precio=5,
            efecto="info",
            descripcion="Es bicarbonato de sodio: sirve para cocinar y limpiar. No cura nada."),
    DefItem("audifonos", "Audífonos", PEQUENO, 0.05, categoria="tecnologia", precio=12),
    DefItem("pendrive", "Pendrive", PEQUENO, 0.02, categoria="tecnologia", precio=8),
    DefItem("recarga", "Recarga de celular", PEQUENO, 0.02, categoria="tecnologia", precio=10),
    DefItem("bala", "Bala (dulce)", PEQUENO, 0.01, apilable=10, categoria="comida", precio=1, efecto="comer",
            descripcion="Un dulce de los de la esquina."),
    # -- Medianos (cintura / mochila) --
    DefItem("linterna", "Linterna", MEDIANO, 0.3, categoria="herramienta", precio=15, cintura=True),
    DefItem("destornillador", "Destornillador", MEDIANO, 0.2, categoria="herramienta", precio=6, cintura=True),
    DefItem("libreta", "Libreta", MEDIANO, 0.15, categoria="papel", precio=4, cintura=True),
    DefItem("agua", "Botella de agua", MEDIANO, 0.5, categoria="bebida", precio=3, cintura=True, efecto="beber"),
    DefItem("cafe", "Café", MEDIANO, 0.3, categoria="bebida", precio=2, cintura=True, efecto="beber"),
    DefItem("pan", "Pan", MEDIANO, 0.1, apilable=4, categoria="comida", precio=1, cintura=True, efecto="comer"),
    DefItem("bolsa_feria", "Bolsa de feria", MEDIANO, 0.2, categoria="bolsa", precio=4, cintura=True),
    DefItem("periodico", "Periódico", MEDIANO, 0.2, categoria="papel"),
    # -- Grandes (manos) --
    DefItem("pelota", "Pelota de fútbol", GRANDE, 0.4, categoria="juego", precio=25),
    DefItem("caja_herramientas", "Caja de herramientas", GRANDE, 6.0, categoria="herramienta", precio=45),
    DefItem("botijon_gas", "Botijón de gas", GRANDE, 13.0, categoria="hogar", precio=100, dos_manos=True),
    # -- Equipo --
    DefItem("mochila", "Mochila", MEDIANO, 0.8, categoria="equipo", precio=60, ranuras=8, peso_extra=8.0,
            descripcion="Ocho ranuras más y 8 kg más de capacidad."),
    # -- Tiendas ampliadas (ALCALDE_TIENDA_AMPLIADA, backend/datos/comercios_semilla.py) --
    # Nombre en portugués, como en el barrio; la descripción en español hace de traducción. Precios en R$ dentro
    # del pago de las misiones (R$ 20-120) y ninguna comida baja más cansancio por real que el pan (10 por R$).
    # Padaria
    DefItem("pao_frances", "Pão francês", PEQUENO, 0.05, apilable=6, categoria="comida", precio=1, efecto="comer",
            descripcion="Pan de sal crujiente, el de todas las mañanas."),
    DefItem("pao_de_queijo", "Pão de queijo", PEQUENO, 0.04, apilable=6, categoria="comida", precio=3,
            efecto="comer", descripcion="Bolitas de pan de queso, calientes."),
    DefItem("sonho", "Sonho", PEQUENO, 0.08, apilable=3, categoria="comida", precio=4, efecto="comer",
            descripcion="Bola de masa frita rellena de crema."),
    DefItem("pao_doce", "Pão doce", PEQUENO, 0.07, apilable=3, categoria="comida", precio=3, efecto="comer",
            descripcion="Pan dulce con coco rallado."),
    DefItem("broa", "Broa de milho", PEQUENO, 0.08, apilable=3, categoria="comida", precio=2, efecto="comer",
            descripcion="Panecillo de maíz, un poco dulce."),
    DefItem("bolo_de_fuba", "Bolo de fubá", MEDIANO, 0.3, categoria="comida", precio=6, cintura=True,
            efecto="comer", descripcion="Porción de bizcocho de harina de maíz."),
    DefItem("pao_de_forma", "Pão de forma", MEDIANO, 0.5, categoria="comida", precio=8,
            descripcion="Pan de molde en bolsa, para llevar a casa."),
    DefItem("cafe_com_leite", "Café com leite", MEDIANO, 0.3, categoria="bebida", precio=4, cintura=True,
            efecto="beber", descripcion="Café con leche en vaso de vidrio."),
    # Lanchonete y bar
    DefItem("coxinha", "Coxinha", PEQUENO, 0.1, apilable=3, categoria="comida", precio=5, efecto="comer",
            descripcion="Croqueta de pollo en forma de gota."),
    DefItem("pastel", "Pastel", MEDIANO, 0.15, categoria="comida", precio=6, cintura=True, efecto="comer",
            descripcion="Empanada frita y crujiente, de queso o de carne."),
    DefItem("misto_quente", "Misto quente", MEDIANO, 0.2, categoria="comida", precio=7, cintura=True,
            efecto="comer", descripcion="Sándwich caliente de jamón y queso."),
    DefItem("suco_laranja", "Suco de laranja", MEDIANO, 0.4, categoria="bebida", precio=5, cintura=True,
            efecto="beber", descripcion="Jugo de naranja recién exprimido."),
    DefItem("guarana", "Guaraná", MEDIANO, 0.35, categoria="bebida", precio=4, cintura=True, efecto="beber",
            descripcion="Refresco de guaraná bien frío."),
    DefItem("acai", "Açaí na tigela", MEDIANO, 0.4, categoria="comida", precio=12, efecto="comer",
            descripcion="Tazón de açaí con granola y banana."),
    DefItem("caldo_de_cana", "Caldo de cana", MEDIANO, 0.4, categoria="bebida", precio=5, cintura=True,
            efecto="beber", descripcion="Jugo de caña de azúcar recién molida."),
    DefItem("agua_de_coco", "Água de coco", MEDIANO, 0.5, categoria="bebida", precio=5, cintura=True,
            efecto="beber", descripcion="Agua de coco verde, con pajilla."),
    # Feira
    DefItem("banana", "Banana", PEQUENO, 0.12, apilable=6, categoria="comida", precio=1, efecto="comer",
            descripcion="Una banana madura de la feria."),
    DefItem("laranja", "Laranja", PEQUENO, 0.2, apilable=4, categoria="comida", precio=1, efecto="comer",
            descripcion="Naranja dulce para pelar."),
    DefItem("mandioca", "Mandioca", MEDIANO, 1.0, categoria="comida", precio=4,
            descripcion="Un kilo de yuca para cocinar en casa."),
    # Supermercado
    DefItem("arroz", "Arroz (1 kg)", MEDIANO, 1.0, categoria="comida", precio=6,
            descripcion="Bolsa de arroz blanco."),
    DefItem("feijao", "Feijão (1 kg)", MEDIANO, 1.0, categoria="comida", precio=8,
            descripcion="Frijoles negros, la base de la feijoada."),
    DefItem("farofa", "Farofa", MEDIANO, 0.5, categoria="comida", precio=5,
            descripcion="Harina de yuca tostada para acompañar."),
    DefItem("leite", "Leite (1 L)", MEDIANO, 1.0, categoria="bebida", precio=5, efecto="beber",
            descripcion="Leche en caja."),
    DefItem("bolacha", "Bolacha", PEQUENO, 0.2, apilable=2, categoria="comida", precio=4, efecto="comer",
            descripcion="Paquete de galletas de maicena."),
    # Lan house
    DefItem("cabo_usb", "Cabo USB", PEQUENO, 0.05, categoria="tecnologia", precio=10,
            descripcion="Cable para cargar el celular."),
    DefItem("carregador", "Carregador", PEQUENO, 0.1, categoria="tecnologia", precio=15,
            descripcion="Cargador de pared para el celular."),
    DefItem("capinha", "Capinha de celular", PEQUENO, 0.05, categoria="tecnologia", precio=12,
            descripcion="Funda para proteger el teléfono."),
    # Tienda Geral (bazar y ferretería)
    DefItem("pilhas", "Pilhas (2)", PEQUENO, 0.05, apilable=3, categoria="hogar", precio=6,
            descripcion="Dos pilas AA para la linterna."),
    DefItem("lampada", "Lâmpada", MEDIANO, 0.1, categoria="hogar", precio=7, descripcion="Bombilla LED para la casa."),
    DefItem("fita_isolante", "Fita isolante", PEQUENO, 0.05, categoria="herramienta", precio=4,
            descripcion="Cinta aislante negra."),
    DefItem("guarda_chuva", "Guarda-chuva", GRANDE, 0.4, categoria="hogar", precio=18,
            descripcion="Paraguas para los días de lluvia."),
    DefItem("chinelo", "Chinelo", MEDIANO, 0.3, categoria="ropa", precio=15, descripcion="Par de chanclas de goma."),
    # -- Sensibles: sin precio ni efecto --
    DefItem("cuchillo_pequeno", "Cuchillo pequeño", MEDIANO, 0.2, categoria="sensible", cintura=True,
            sensible=True),
    DefItem("pistola", "Pistola", MEDIANO, 1.0, categoria="sensible", cintura=True, sensible=True),
)

CATALOGO_ITEMS = {item.id: item for item in _ITEMS}

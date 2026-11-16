# Puntos de entrega del trabajo «Mototaxi y entregas» (datos puros). Cada punto es la puerta de un lugar del mapa
# (`lugar`, la misma clave que usan las misiones y el GPS) y quien recibe allí el pedido: un vecino o un puesto de
# trabajo, con lo que se le lleva. Un lugar puede tener varios destinatarios: así dos turnos seguidos no se parecen.
# Los lugares que no existan en el mapa activo (mapa grande o chico) se descartan solos (backend/logica/entregas.py).

from backend.logica.entregas import PuntoEntrega

PUNTOS_ENTREGA = (
    PuntoEntrega("prefeitura_conserje", "Prefeitura", "Seu Joaquim", "el almuerzo del conserje"),
    PuntoEntrega("prefeitura_secretaria", "Prefeitura", "Dona Célia", "un sobre de documentos"),
    PuntoEntrega("se_floristeria", "Praça da Sé", "Dona Rosa", "un ramo de flores"),
    PuntoEntrega("se_lustrabotas", "Praça da Sé", "Seu Tonho", "una caja de betún"),
    PuntoEntrega("universidad_estudiante", "Universidade de Ciudad Nova", "Larissa", "unas fotocopias para el examen"),
    PuntoEntrega("universidad_cafeteria", "Universidade de Ciudad Nova", "Seu Paulo", "dos bolsas de café"),
    PuntoEntrega("hospital_enfermera", "Hospital Santa Casa", "Enfermera Bia", "una caja de medicinas"),
    PuntoEntrega("hospital_porteria", "Hospital Santa Casa", "Seu Raimundo", "el almuerzo de la portería"),
    PuntoEntrega("morro_abuela", "Morro da Esperança", "Dona Zica", "la compra del mercado"),
    PuntoEntrega("morro_obra", "Morro da Esperança", "Seu Valdir", "una bolsa de tornillos"),
    PuntoEntrega("parque_heladero", "Parque do Povo", "Seu Didi", "hielo para el carrito"),
    PuntoEntrega("parque_futbol", "Parque do Povo", "Thiago", "un balón nuevo"),
    PuntoEntrega("rodoviaria_taquilla", "Rodoviária", "Dona Graça", "el rollo de boletos"),
    PuntoEntrega("mercado_puesto", "Mercado Municipal", "Dona Neide", "una caja de mangos"),
    PuntoEntrega("mercado_pescadero", "Mercado Municipal", "Seu Benedito", "una bolsa de hielo"),
    PuntoEntrega("samba_costurera", "Escola de Samba", "Dona Ivone", "telas para los disfraces"),
    PuntoEntrega("samba_tambor", "Escola de Samba", "Mestre Jorge", "parches para los tambores"),
    PuntoEntrega("radio_locutor", "Rádio Comunitária", "Seu Ademir", "un micrófono reparado"),
    PuntoEntrega("radio_tecnica", "Rádio Comunitária", "Jéssica", "pilas para la consola"),
    PuntoEntrega("teleferico_operador", "Estação do Teleférico", "Seu Nonato", "un repuesto del cable"),
)

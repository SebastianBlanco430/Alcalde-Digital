# Constantes y estado compartido del chip del reloj (puro, sin Ursina). registro_reloj (controlador) las
# reexporta con los mismos nombres; civitas_visual y recta_final_vista (vistas) las leen de aquí.
ANCHO_CHIP, ALTO_CHIP = 0.27, 0.052
MARGEN = 0.02
# Estado de la cinemática final: el MISMO dict que registro_reloj._cine_final (se muta, nunca se reasigna).
CINE_FINAL = {"sesion": None, "vista": False, "entidad": None}

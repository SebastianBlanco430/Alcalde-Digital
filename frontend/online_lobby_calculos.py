# Lógica PURA del lobby online (sin ursina ni panda3d): validaciones de los formularios, formato de
# direcciones/códigos/ping, modelo de la sala (casillas, estados de los botones) y catálogo de motivos
# de error de red. Las escenas (escena_online_menu / escena_sala / escena_error_red) solo dibujan y
# llaman a esto; así todo lo decidible se prueba sin ventana.
#
# Nunca importa nada que abra la red: solo backend.red.saneado/huellas (puros). Se importa SOLO desde
# las escenas online, que main.py registra de forma perezosa cuando ONLINE (frontend/online_config) es True.

import ipaddress
import re
from dataclasses import dataclass, field

from backend.logica.roles import ROLES
from backend.logica.sesion import MAX_JUGADORES
from backend.red import huellas, saneado
from frontend import campo_texto_calculos as campo

# --------------------------------------------------------------------------------------------
# Constantes de los formularios
# --------------------------------------------------------------------------------------------
PUERTO_DEFECTO = 7777
PUERTO_MIN = 1024
PUERTO_MAX = 65535

AMBITO_LOCAL, AMBITO_LAN, AMBITO_ABIERTO = "local", "lan", "abierto"
AMBITOS_UI = (
    (AMBITO_LOCAL, "Solo este equipo"),
    (AMBITO_LAN, "Red local"),
    (AMBITO_ABIERTO, "Abierto a internet"),
)
AMBITO_DEFECTO = AMBITO_LAN
CONFIRMACION_ABIERTO = "ABRIR"
LARGO_CODIGO_ABIERTO = huellas.LARGO_CODIGO_ABIERTO      # 12: el anfitrión lo exige para el ámbito abierto

EXPLICACION_AMBITO = {
    AMBITO_LOCAL: "Solo juegan quienes estén en ESTE equipo (otra ventana del juego). Nadie más puede entrar.",
    AMBITO_LAN: ("Pueden entrar equipos de tu misma red (Wi-Fi o cable de casa). "
                 "Es la opción recomendada. Se rechazan conexiones de fuera de la red local."),
    AMBITO_ABIERTO: ("Escucha en TODAS las interfaces: cualquiera que sepa tu IP pública y el código puede intentar "
                     "entrar. Hace falta abrir el puerto en el router. El tráfico va SIN cifrar."),
}
AVISO_PRIVACIDAD = ("Tu alias y el último anfitrión se guardan solo en este equipo (Ajustes > Online > Olvidar). "
                    "Detalle en docs/PRIVACIDAD_ONLINE.md.")
AVISO_SIN_CIFRAR = "El tráfico no va cifrado: usa red local o VPN (Tailscale, ZeroTier, WireGuard)."
AVISO_ABIERTO = (f"Para abrir la sala a internet escribe {CONFIRMACION_ABIERTO}. Se creará un código largo "
                 f"({LARGO_CODIGO_ABIERTO} caracteres). Mejor usa una VPN y la opción «Red local».")
AYUDA_CORTAFUEGOS = (
    "Si macOS pregunta «¿Quieres permitir que Python acepte conexiones entrantes?», elige Permitir. "
    "Si lo rechazaste: Ajustes del Sistema > Red > Cortafuegos > Opciones, y permite Python. "
    "Los demás equipos deben estar en la misma red y usar la IP:puerto y el código de abajo."
)

# --------------------------------------------------------------------------------------------
# Validación de formularios (devuelven los valores limpios y un dict {campo: mensaje} de errores)
# --------------------------------------------------------------------------------------------
_ETIQUETA_DNS = re.compile(r"^[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?$")


@dataclass
class Formulario:
    valores: dict = field(default_factory=dict)
    errores: dict = field(default_factory=dict)

    @property
    def valido(self):
        return not self.errores


def validar_alias(texto):
    """(alias_limpio, mensaje_de_error|None)."""
    alias = campo.valor_final(campo.TIPO_ALIAS, texto)
    if not alias:
        return "", "Escribe un alias de 1 a 16 letras, números, espacio, - _ ."
    if saneado.validar_nombre(alias) is None:
        if saneado.es_reservado(alias):
            return alias, "Ese alias está reservado: elige otro."
        return alias, "Alias no válido (1 a 16 letras, números, espacio, - _ .)."
    return saneado.validar_nombre(alias), None


def validar_puerto(texto, minimo=PUERTO_MIN):
    """(puerto:int|None, mensaje|None). Vacío = puerto por defecto."""
    limpio = campo.valor_final(campo.TIPO_PUERTO, texto)
    if not limpio:
        return PUERTO_DEFECTO, None
    valor = int(limpio)
    if not minimo <= valor <= PUERTO_MAX:
        return None, f"El puerto debe estar entre {minimo} y {PUERTO_MAX}."
    return valor, None


def _host_valido(host):
    if not host or len(host) > 253:
        return False
    if re.fullmatch(r"[0-9.]+", host):                   # parece IPv4: debe serlo de verdad
        try:
            ipaddress.IPv4Address(host)
            return True
        except ValueError:
            return False
    if ":" in host:                                        # IPv6 sin corchetes
        try:
            ipaddress.IPv6Address(host)
            return True
        except ValueError:
            return False
    return all(_ETIQUETA_DNS.match(parte) for parte in host.split("."))


def parsear_destino(texto, puerto_defecto=PUERTO_DEFECTO):
    """«host», «host:puerto» o «[ipv6]:puerto» -> (host, puerto). ValueError con un mensaje legible."""
    limpio = campo.valor_final(campo.TIPO_HOST, texto)
    if not limpio:
        raise ValueError("Escribe la dirección del anfitrión (IP:puerto).")
    host, puerto = limpio, puerto_defecto
    if limpio.startswith("["):
        cierre = limpio.find("]")
        if cierre < 0:
            raise ValueError("Dirección IPv6 mal escrita: falta «]».")
        host = limpio[1:cierre]
        resto = limpio[cierre + 1:]
        if resto:
            if not resto.startswith(":") or not resto[1:].isdigit():
                raise ValueError("Después de «]» va «:puerto».")
            puerto = int(resto[1:])
    elif limpio.count(":") == 1:
        host, _, texto_puerto = limpio.partition(":")
        if not texto_puerto.isdigit():
            raise ValueError("El puerto debe ser un número (192.168.1.5:7777).")
        puerto = int(texto_puerto)
    if not _host_valido(host):
        raise ValueError("La dirección del anfitrión no es válida.")
    if not 1 <= puerto <= PUERTO_MAX:
        raise ValueError(f"El puerto debe estar entre 1 y {PUERTO_MAX}.")
    return host, puerto


def formatear_destino(host, puerto):
    """«host:puerto» (IPv6 entre corchetes)."""
    if ":" in host and not host.startswith("["):
        return f"[{host}]:{puerto}"
    return f"{host}:{puerto}"


def validar_crear(alias, ambito, puerto, confirmacion=""):
    """Formulario «Crear sala». Valores: alias, ambito, puerto, abierto (bool)."""
    f = Formulario()
    nombre, error = validar_alias(alias)
    if error:
        f.errores["alias"] = error
    puerto_ok, error = validar_puerto(puerto)
    if error:
        f.errores["puerto"] = error
    if ambito not in dict(AMBITOS_UI):
        f.errores["ambito"] = "Elige dónde se abre la sala."
    if ambito == AMBITO_ABIERTO and campo.valor_final(campo.TIPO_CONFIRMAR, confirmacion) != CONFIRMACION_ABIERTO:
        f.errores["confirmacion"] = f"Escribe {CONFIRMACION_ABIERTO} para confirmar que quieres abrir la sala a internet."
    f.valores = {"alias": nombre, "ambito": ambito, "puerto": puerto_ok, "abierto": ambito == AMBITO_ABIERTO}
    return f


def validar_unirse(alias, destino, codigo):
    """Formulario «Unirse». Valores: alias, host, puerto, codigo (normalizado)."""
    f = Formulario()
    nombre, error = validar_alias(alias)
    if error:
        f.errores["alias"] = error
    host = puerto = None
    try:
        host, puerto = parsear_destino(destino)
    except ValueError as e:
        f.errores["destino"] = str(e)
    norm = huellas.normalizar_codigo(campo.valor_final(campo.TIPO_CODIGO, codigo))
    if norm is None or len(norm) < huellas.LARGO_CODIGO:
        f.errores["codigo"] = f"Escribe el código de la sala ({huellas.LARGO_CODIGO} o más caracteres)."
    f.valores = {"alias": nombre, "host": host, "puerto": puerto, "codigo": norm}
    return f


# --------------------------------------------------------------------------------------------
# Formato para mostrar
# --------------------------------------------------------------------------------------------
def agrupar_codigo(codigo, grupo=4):
    """«ABCDEFGH» -> «ABCD-EFGH» (más fácil de dictar). Vacío -> ''."""
    if not codigo:
        return ""
    return "-".join(codigo[i:i + grupo] for i in range(0, len(codigo), grupo))


def codigo_visible(codigo, mostrar):
    """Código agrupado, u oculto con asteriscos (misma longitud agrupada)."""
    texto = agrupar_codigo(codigo)
    return texto if mostrar else "".join("-" if c == "-" else "*" for c in texto)


# Ping con TEXTO además de color (hay filtros de daltonismo): el color nunca es la única señal.
NIVEL_BUENO, NIVEL_ACEPTABLE, NIVEL_ALTO, NIVEL_SIN_DATO = "bueno", "aceptable", "alto", "sin_dato"
ETIQUETA_NIVEL = {NIVEL_BUENO: "Buena", NIVEL_ACEPTABLE: "Aceptable", NIVEL_ALTO: "Alta", NIVEL_SIN_DATO: "Sin dato"}
UMBRAL_BUENO_MS = 60.0
UMBRAL_ACEPTABLE_MS = 150.0


def nivel_ping(ms):
    if ms is None or isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms != ms or ms < 0:
        return NIVEL_SIN_DATO
    if ms < UMBRAL_BUENO_MS:
        return NIVEL_BUENO
    if ms < UMBRAL_ACEPTABLE_MS:
        return NIVEL_ACEPTABLE
    return NIVEL_ALTO


def texto_ping(ms):
    """«42 ms · Buena», «230 ms · Alta» o «— · Sin dato»."""
    nivel = nivel_ping(ms)
    if nivel == NIVEL_SIN_DATO:
        return "— · Sin dato"
    return f"{int(round(ms))} ms · {ETIQUETA_NIVEL[nivel]}"


# --------------------------------------------------------------------------------------------
# Modelo de la sala
# --------------------------------------------------------------------------------------------
@dataclass
class Casilla:
    indice: int
    ocupada: bool = False
    id: int = -1
    alias: str = ""
    rol: str = None
    nombre_rol: str = ""
    listo: bool = False
    conectado: bool = False
    anfitrion: bool = False
    local: bool = False
    ping_ms: float = None

    @property
    def texto_listo(self):
        if not self.ocupada:
            return ""
        return "Listo" if self.listo else "Sin confirmar"

    @property
    def texto_conexion(self):
        if not self.ocupada:
            return "Libre"
        return "Conectado" if self.conectado else "Sin conexión"

    @property
    def texto_ping(self):
        if not self.ocupada or not self.conectado:
            return ""
        return texto_ping(self.ping_ms) if self.local else "— · Sin dato"

    @property
    def nivel_ping(self):
        return nivel_ping(self.ping_ms) if (self.ocupada and self.conectado and self.local) else NIVEL_SIN_DATO


class ModeloSala:
    """Estado de la sala tal como lo cuentan los eventos de ClienteRed. Sin red ni motor."""

    def __init__(self):
        self.tu_id = None
        self.semilla = None
        self.sala = ""
        self.jugadores = []             # dicts del evento «sala»
        self.roles_libres = []
        self.estado = "conectando"
        self.motivo_cierre = None
        self.reconectando = None        # {"intento": n, "espera": s} mientras dura
        self.aviso = ""                 # último aviso no fatal (p. ej. rol tomado)
        self.inicio = None              # evento «inicio» cuando arranca la partida
        self.latencia_ms = None
        self.rechazo = None             # {"codigo", "texto"} del handshake

    # Aplica un evento del cliente. Devuelve "inicio", "cerrado", "rechazo" o None según lo que cambió de fondo.
    def aplicar(self, ev):
        t = ev.get("t")
        if t == "bienvenida":
            self.tu_id = ev.get("tu_id")
            self.semilla = ev.get("semilla")
            self.sala = ev.get("sala", "")
        elif t == "sala":
            self.jugadores = [dict(j) for j in ev.get("jugadores", [])]
            self.roles_libres = list(ev.get("roles_libres", []))
        elif t == "estado":
            self.estado = ev.get("estado", self.estado)
            if ev.get("motivo"):
                self.motivo_cierre = ev["motivo"]
        elif t == "reconectando":
            self.reconectando = {"intento": ev.get("intento", 1), "espera": ev.get("espera", 0)}
        elif t == "reconectado":
            self.reconectando = None
            self.aviso = ""
        elif t == "rechazo":
            if ev.get("codigo") == "rol_tomado":
                self.aviso = ev.get("texto") or "Ese rol ya está tomado."
                return None
            self.rechazo = {"codigo": ev.get("codigo"), "texto": ev.get("texto", "")}
            return "rechazo"
        elif t == "error":
            self.aviso = ev.get("motivo", "")
        elif t == "inicio":
            self.inicio = dict(ev)
            return "inicio"
        elif t == "cerrado":
            self.motivo_cierre = ev.get("motivo") or self.motivo_cierre
            self.estado = "cerrado"
            return "cerrado"
        elif t == "sala_cerrada":
            self.motivo_cierre = "sala_cerrada"
        elif t in ("jugador_entra", "jugador_sale", "jugador_desconectado", "jugador_reconectado"):
            pass                        # el roster llega entero en el siguiente «sala»
        return None

    def jugador(self, id_jugador):
        return next((j for j in self.jugadores if j.get("id") == id_jugador), None)

    @property
    def yo(self):
        return self.jugador(self.tu_id)

    @property
    def soy_anfitrion(self):
        yo = self.yo
        return bool(yo and yo.get("anfitrion"))

    @property
    def conectados(self):
        return [j for j in self.jugadores if j.get("conectado")]

    def casillas(self, latencia_ms=None):
        """Siempre MAX_JUGADORES casillas (las vacías, libres), ordenadas por slot."""
        por_id = {j["id"]: j for j in self.jugadores}
        salida = []
        for i in range(MAX_JUGADORES):
            j = por_id.get(i)
            if j is None:
                salida.append(Casilla(indice=i))
                continue
            rol = j.get("rol")
            local = j["id"] == self.tu_id
            salida.append(Casilla(
                indice=i, ocupada=True, id=j["id"], alias=j["nombre"], rol=rol,
                nombre_rol=ROLES[rol].nombre if rol in ROLES else "Sin rol",
                listo=bool(j.get("listo")), conectado=bool(j.get("conectado")),
                anfitrion=bool(j.get("anfitrion")), local=local,
                ping_ms=(latencia_ms if latencia_ms is not None else self.latencia_ms) if local else None))
        return salida

    def rol_de(self, rol):
        """Nombre del jugador que tiene `rol`, o None si está libre."""
        return next((j["nombre"] for j in self.jugadores if j.get("rol") == rol), None)

    # --- Estado de los botones ---
    @property
    def estoy_listo(self):
        yo = self.yo
        return bool(yo and yo.get("listo"))

    @property
    def puede_cambiar_rol(self):
        return self.estado == "en_sala" and self.yo is not None and not self.inicio

    def puede_elegir_rol(self, rol):
        return self.puede_cambiar_rol and rol in ROLES and rol in self.roles_libres

    @property
    def puede_marcar_listo(self):
        return self.estado == "en_sala" and self.yo is not None and not self.inicio

    @property
    def todos_listos(self):
        con = self.conectados
        return bool(con) and all(j.get("listo") for j in con)

    @property
    def puede_iniciar(self):
        """«Iniciar» solo para el anfitrión y cuando todos los conectados estén listos."""
        return self.soy_anfitrion and self.estado == "en_sala" and self.todos_listos and not self.inicio

    @property
    def texto_iniciar(self):
        if not self.soy_anfitrion:
            return "Solo el anfitrión inicia"
        if self.puede_iniciar:
            return "Iniciar partida"
        faltan = [j["nombre"] for j in self.conectados if not j.get("listo")]
        return f"Esperando a: {', '.join(faltan[:3])}" + ("…" if len(faltan) > 3 else "") if faltan else "Iniciar partida"

    @property
    def texto_estado(self):
        if self.estado == "cerrado":
            return "Desconectado"
        if self.reconectando:
            return f"Reconectando… (intento {self.reconectando['intento']}, en {int(round(self.reconectando['espera']))} s)"
        if self.estado == "conectando":
            return "Conectando…"
        if self.estado == "en_juego":
            return "Partida en curso"
        n = len(self.conectados)
        return f"{n} de {MAX_JUGADORES} jugadores en la sala"


# --------------------------------------------------------------------------------------------
# Motivos de error de red (escena_error_red)
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InfoError:
    codigo: str
    titulo: str
    texto: str
    reintentable: bool = True


_ERRORES = {
    "version": InfoError("version", "Versión distinta",
                         "Tu juego y el del anfitrión no hablan la misma versión del protocolo. "
                         "Actualiza ambos al mismo código y vuelve a intentarlo.", False),
    "sala_llena": InfoError("sala_llena", "Sala llena",
                            f"La sala ya tiene {MAX_JUGADORES} jugadores. Pide al anfitrión que libere un puesto."),
    "rol_tomado": InfoError("rol_tomado", "Rol tomado", "Otro jugador ya eligió ese rol. Elige uno libre."),
    "codigo_malo": InfoError("codigo_malo", "Código incorrecto",
                             "El código de la sala no coincide. Revísalo (sin O, I, L, 0 ni 1) y vuelve a intentarlo."),
    "mundo_distinto": InfoError("mundo_distinto", "Mundo distinto",
                                "Tu mundo o tu contenido no es el mismo que el del anfitrión. Reinicia el juego con la "
                                "misma semilla (ALCALDE_SEMILLA=…) que use el anfitrión.", False),
    "nombre_invalido": InfoError("nombre_invalido", "Nombre no válido",
                                 "El anfitrión no aceptó tu alias. Usa de 1 a 16 letras, números, espacio, - _ ."),
    "expulsado": InfoError("expulsado", "Te expulsaron", "El anfitrión te sacó de la sala.", False),
    "lleno_de_conexiones": InfoError("lleno_de_conexiones", "Sala ocupada",
                                     "El anfitrión tiene demasiadas conexiones abiertas ahora mismo. Prueba en un momento."),
    "anfitrion_desconectado": InfoError("anfitrion_desconectado", "Anfitrión desconectado",
                                        "Se perdió la conexión con el anfitrión o cerró la sala. "
                                        "La partida terminó para todos."),
    "tiempo_agotado": InfoError("tiempo_agotado", "Tiempo agotado",
                                "El anfitrión no respondió. Comprueba la IP, el puerto y el cortafuegos, y que esté en "
                                "la misma red (o VPN)."),
}
_SINONIMOS = {
    "sala_cerrada": "anfitrion_desconectado",
    "conexion_perdida": "anfitrion_desconectado",
    "silencio_del_anfitrion": "anfitrion_desconectado",
    "reconexion_agotada": "anfitrion_desconectado",
    "anfitrion_inundando": "anfitrion_desconectado",
    "no_se_pudo_conectar": "tiempo_agotado",
    "tiempo_agotado": "tiempo_agotado",
    "datos_de_conexion_invalidos": "nombre_invalido",
}
GENERICO = InfoError("desconocido", "No se pudo conectar", "Algo falló en la conexión. Vuelve a intentarlo.")


def info_error(motivo):
    """Motivo de red (código del anfitrión o motivo_cierre del cliente) -> InfoError. Nunca falla."""
    if not isinstance(motivo, str):
        return GENERICO
    clave = _SINONIMOS.get(motivo, motivo)
    if clave in _ERRORES:
        return _ERRORES[clave]
    if motivo == "protocolo_invalido:esperaba_reto":
        # El anfitrión rechaza con «lleno_de_conexiones» ANTES del reto y ClienteRed lo ve como protocolo roto.
        return _ERRORES["lleno_de_conexiones"]
    if motivo.startswith("protocolo_invalido"):
        return InfoError("protocolo_invalido", "Respuesta inesperada",
                         "El otro extremo no habla el protocolo del juego (¿IP o puerto de otro programa?).")
    return GENERICO


MOTIVOS_CONOCIDOS = tuple(_ERRORES)

# Segundos que espera la pantalla de «Conectando…» antes de rendirse con «tiempo agotado».
TIEMPO_CONEXION_S = 12.0

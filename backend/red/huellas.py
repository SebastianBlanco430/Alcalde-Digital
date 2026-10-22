# Huellas, código de sala, reto/respuesta HMAC y tokens del modo online. Módulo PURO (stdlib).
# Límite honesto: sin TLS, un handshake capturado permite fuerza bruta OFFLINE del código;
# por eso en modo abierto se exige un código largo y se recomienda una VPN.
import hashlib
import hmac
import json
import secrets

# Alfabeto sin caracteres ambiguos (sin 0/O, 1/I/L, 5/S, 2/Z, 8/B)
ALFABETO_CODIGO = "ACDEFGHJKMNPQRTUVWXY3469"
LARGO_CODIGO = 6
LARGO_CODIGO_ABIERTO = 12
BYTES_NONCE = 16
BYTES_TOKEN = 16          # 128 bits


def _canonico(datos):
    """Bytes canónicos de unos datos JSON-ables: claves ordenadas, sin espacios, UTF-8."""
    return json.dumps(datos, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256(datos):
    return hashlib.sha256(_canonico(datos)).hexdigest()


def huella_mundo(datos_canonicos):
    """SHA-256 (hex) del mundo: `datos_canonicos` lo arma quien llama (semilla, lugares...)."""
    return _sha256({"mundo": datos_canonicos})


def huella_contenido(datos_canonicos):
    """SHA-256 (hex) del contenido (misiones, roles...) recibido como parámetro."""
    return _sha256({"contenido": datos_canonicos})


def generar_codigo_sala(largo=LARGO_CODIGO):
    """Código aleatorio criptográfico sin caracteres ambiguos (6 por defecto)."""
    largo = max(1, int(largo))
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(largo))


def normalizar_codigo(texto):
    """Mayúsculas y sin espacios/guiones; None si tiene caracteres fuera del alfabeto."""
    if type(texto) is not str:
        return None
    limpio = "".join(c for c in texto.upper() if c not in " -")
    if not limpio or any(c not in ALFABETO_CODIGO for c in limpio):
        return None
    return limpio


def generar_nonce():
    """Reto aleatorio (hex) que el anfitrión envía en «reto»."""
    return secrets.token_hex(BYTES_NONCE)


def calcular_prueba(codigo, nonce, nombre):
    """HMAC-SHA256(código, nonce + nombre) en hex. El código nunca viaja en claro."""
    clave = (normalizar_codigo(codigo) or "").encode("utf-8")
    mensaje = (nonce + "\x00" + nombre).encode("utf-8")   # separador: evita ambigüedad
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def verificar_prueba(codigo, nonce, nombre, prueba):
    """Comprueba la prueba del cliente en tiempo constante."""
    if type(prueba) is not str:
        return False
    esperada = calcular_prueba(codigo, nonce, nombre)
    return hmac.compare_digest(esperada.encode("ascii"), prueba.encode("utf-8", "replace"))


def generar_token():
    """Token de reconexión de 128 bits (hex de 32 caracteres)."""
    return secrets.token_hex(BYTES_TOKEN)


def hash_token(token):
    """Hash del token para guardarlo en memoria en vez del token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_valido(token, hash_guardado):
    """Compara un token presentado con el hash guardado en tiempo constante."""
    if type(token) is not str or type(hash_guardado) is not str:
        return False
    return hmac.compare_digest(hash_token(token).encode("ascii"), hash_guardado.encode("utf-8", "replace"))

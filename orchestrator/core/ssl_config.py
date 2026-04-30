"""
Configuração SSL para requisições HTTP.
"""
import os
import ssl
from pathlib import Path
from typing import Union


def get_ssl_context() -> Union[ssl.SSLContext, bool]:
    """
    Retorna contexto SSL configurável baseado em variáveis de ambiente.

    Configurações via environment variables:
    - SSL_VERIFY: "true" (padrão) ou "false"
    - SSL_CERT_PATH: Caminho para certificado customizado (opcional)

    Returns:
        Union[ssl.SSLContext, bool]:
            - ssl.SSLContext: Se SSL_CERT_PATH estiver definido
            - False: Se SSL_VERIFY=false (desabilita verificação)
            - True: Padrão (verificação ativa)

    Example:
        >>> import httpx
        >>> ssl_verify = get_ssl_context()
        >>> async with httpx.AsyncClient(verify=ssl_verify) as client:
        ...     response = await client.get("https://api.example.com")
    """
    ssl_verify = os.getenv("SSL_VERIFY", "true").lower()
    cert_path = os.getenv("SSL_CERT_PATH")

    if ssl_verify == "false":
        # Para desenvolvimento apenas - desabilita verificação
        return False

    if cert_path:
        # Usa certificado customizado
        cert_path_obj = Path(cert_path)
        if not cert_path_obj.exists():
            raise FileNotFoundError(f"SSL certificate file not found: {cert_path}")

        context = ssl.create_default_context(cafile=str(cert_path_obj))
        return context

    # Padrão: verificação ativa
    return True


def get_ssl_verify() -> bool:
    """
    Retorna True se SSL deve ser verificado.

    Returns:
        bool: True se SSL_VERIFY != "false"
    """
    return os.getenv("SSL_VERIFY", "true").lower() != "false"

"""Configuración de TattileSender.

Este módulo define la clase de configuración que centraliza los parámetros
principales de la aplicación. En producción, las variables se leen del entorno
(sistema o servicio de secrets). En desarrollo se puede usar un archivo `.env`
que se cargará con herramientas como `python-dotenv`.
"""
import logging
import os

from pydantic import BaseSettings, Field


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Clase de configuración para toda la aplicación.

    Los valores se obtienen por orden de prioridad de Pydantic: argumentos
    directos, variables de entorno y, opcionalmente, archivos `.env` cuando se
    cargue con `python-dotenv` antes de iniciar la aplicación.
    """

    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_name: str = Field("tattile_sender", env="DB_NAME")
    db_user: str = Field("tattile", env="DB_USER")
    db_password: str = Field("changeme", env="DB_PASSWORD")

    certs_dir: str = Field("/etc/tattile_sender/certs", env="CERTS_DIR")
    transit_port: int = Field(33334, env="TRANSIT_PORT")
    app_env: str = Field("dev", env="APP_ENV")

    sender_enabled: bool = Field(True, env="SENDER_ENABLED")
    sender_poll_interval_seconds: int = Field(5, env="SENDER_POLL_INTERVAL_SECONDS")
    sender_max_batch_size: int = Field(50, env="SENDER_MAX_BATCH_SIZE")
    sender_default_retry_max: int = Field(3, env="SENDER_DEFAULT_RETRY_MAX")
    sender_default_backoff_ms: int = Field(1000, env="SENDER_DEFAULT_BACKOFF_MS")

    images_dir: str = Field(
        "data/images",
        env="IMAGES_DIR",
        description="Directorio base para almacenar imágenes ALPR",
    )

    @property
    def CERTS_DIR(self) -> str:
        """Alias en mayúsculas para compatibilidad con scripts auxiliares."""

        return self.certs_dir

    @property
    def IMAGES_DIR(self) -> str:
        """Alias en mayúsculas para compatibilidad con scripts auxiliares."""

        return self.images_dir

    @property
    def database_url(self) -> str:
        """Construye la URL de conexión a PostgreSQL para SQLAlchemy."""

        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _ensure_images_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem defensive
        logger.error("No se pudo crear el directorio de imágenes %s: %s", path, exc)


settings = Settings()
_ensure_images_dir(settings.images_dir)

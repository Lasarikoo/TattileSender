"""Configuración de TattileSender.

Este módulo define la clase de configuración que centraliza los parámetros
principales de la aplicación. En producción, las variables se leen del entorno
(sistema o servicio de secrets). En desarrollo se puede usar un archivo `.env`
que se cargará con herramientas como `python-dotenv`.
"""
from pydantic import BaseSettings, Field


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

    @property
    def CERTS_DIR(self) -> str:
        """Alias en mayúsculas para compatibilidad con scripts auxiliares."""

        return self.certs_dir

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


settings = Settings()

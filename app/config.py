from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    groq_api_key: Optional[str] = Field(default=None, env="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", env="GROQ_MODEL")

    mysql_host: Optional[str] = Field(default=None, env="MYSQL_HOST")
    mysql_port: int = Field(default=3306, env="MYSQL_PORT")
    mysql_user: Optional[str] = Field(default=None, env="MYSQL_USER")
    mysql_password: Optional[str] = Field(default=None, env="MYSQL_PASSWORD")
    mysql_database: Optional[str] = Field(default=None, env="MYSQL_DATABASE")

    max_sql_retries: int = Field(default=3, env="MAX_SQL_RETRIES")
    query_timeout: int = Field(default=30, env="QUERY_TIMEOUT")
    max_rows: int = Field(default=10000, env="MAX_ROWS")
    output_dir: str = Field(default="outputs", env="OUTPUT_DIR")
    log_dir: str = Field(default="logs", env="LOG_DIR")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

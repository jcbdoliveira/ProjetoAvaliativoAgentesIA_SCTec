"""Executa os 3 cenários de evidência (carrega .env automaticamente)."""
from dotenv import load_dotenv

load_dotenv()

from evidence.demo import *  # noqa: F401,F403

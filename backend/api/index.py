import sys
import os

# Adiciona o diretório backend ao path para que os imports funcionem
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, backend_dir)

from app.main import app
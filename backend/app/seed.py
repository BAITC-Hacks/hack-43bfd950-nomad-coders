from app.config import Settings
from app.service import Service


if __name__ == '__main__':
    Service(Settings.from_env()).seed_demo()
    print('Синтетический набор загружен. Повторный запуск не создаёт дубли.')

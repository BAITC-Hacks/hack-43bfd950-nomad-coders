from app.config import Settings
from app.service import Service
from app.engine_demo import seed_engine_demo


if __name__ == '__main__':
    service = Service(Settings.from_env())
    service.seed_demo()
    seed_engine_demo(service)
    print('Синтетические наборы загружены. Повторный запуск не создаёт дубли.')

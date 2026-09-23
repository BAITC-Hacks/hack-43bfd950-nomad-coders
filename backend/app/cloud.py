"""Container entrypoint: persistent synthetic seed, then one HTTP worker."""
import os

import uvicorn

from app.config import Settings
from app.main import create_app
from app.engine_demo import seed_engine_demo


def main():
    settings = Settings.from_env()
    app = create_app(settings)
    if settings.demo_enabled:
        app.state.service.seed_demo()
        seed_engine_demo(app.state.service)
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8000')), workers=1)


if __name__ == '__main__':
    main()

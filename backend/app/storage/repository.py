import json
import sqlite3
from contextlib import contextmanager


class Repository:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS objects (
                    kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY (kind, id));
                CREATE TABLE IF NOT EXISTS order_versions (
                    order_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY (order_id, revision));
            ''')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def read(db, kind, identifier):
        row = db.execute('SELECT body FROM objects WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def get(self, kind, identifier):
        with self.connection() as db:
            return self.read(db, kind, identifier)

    def list(self, kind):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM objects WHERE kind=? ORDER BY id', (kind,))]

    def save_bundle(self, entries, ignore=False):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            verb = 'INSERT OR IGNORE' if ignore else 'INSERT'
            for kind, identifier, model in entries:
                db.execute(f'{verb} INTO objects VALUES (?, ?, ?)', (kind, identifier, model.model_dump_json()))

    def create_order(self, order):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            body = order.model_dump_json()
            db.execute('INSERT INTO objects VALUES (?, ?, ?)', ('order', order.id, body))
            db.execute('INSERT INTO order_versions VALUES (?, ?, ?)', (order.id, order.revision, body))

    def mutate_order(self, identifier, change):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            order = change(self.read(db, 'order', identifier))
            body = order.model_dump_json()
            db.execute('UPDATE objects SET body=? WHERE kind=? AND id=?', (body, 'order', identifier))
            db.execute('INSERT INTO order_versions VALUES (?, ?, ?)', (identifier, order.revision, body))
            return order

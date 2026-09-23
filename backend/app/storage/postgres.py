"""PostgreSQL storage; row locks preserve optimistic order revisions across workers."""
import json
from contextlib import contextmanager

import psycopg


class PostgresRepository:
    def __init__(self, url):
        self._url = url
        with self.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS objects (
                kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (kind, id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS order_versions (
                order_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (order_id, revision))''')

    @contextmanager
    def connection(self):
        # Connection context commits successful changes, rolls back failures and closes.
        with psycopg.connect(self._url, connect_timeout=15) as db:
            yield db

    @staticmethod
    def read(db, kind, identifier, lock=False):
        sql = 'SELECT body FROM objects WHERE kind=%s AND id=%s'
        row = db.execute(sql + (' FOR UPDATE' if lock else ''), (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def get(self, kind, identifier):
        with self.connection() as db:
            return self.read(db, kind, identifier)

    def list(self, kind):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT body FROM objects WHERE kind=%s ORDER BY id', (kind,))]

    def save_bundle(self, entries, ignore=False):
        sql = 'INSERT INTO objects (kind, id, body) VALUES (%s, %s, %s)'
        if ignore:
            sql += ' ON CONFLICT (kind, id) DO NOTHING'
        with self.connection() as db:
            for kind, identifier, model in entries:
                db.execute(sql, (kind, identifier, model.model_dump_json()))

    def create_order(self, order):
        body = order.model_dump_json()
        with self.connection() as db:
            db.execute('INSERT INTO objects VALUES (%s, %s, %s)', ('order', order.id, body))
            db.execute('INSERT INTO order_versions VALUES (%s, %s, %s)', (order.id, order.revision, body))

    def mutate_order(self, identifier, change):
        with self.connection() as db:
            order = change(self.read(db, 'order', identifier, lock=True))
            body = order.model_dump_json()
            db.execute('UPDATE objects SET body=%s WHERE kind=%s AND id=%s', (body, 'order', identifier))
            db.execute('INSERT INTO order_versions VALUES (%s, %s, %s)', (identifier, order.revision, body))
            return order

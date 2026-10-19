import contextlib
import os
import sqlite3
from pathlib import Path

DATA = Path(os.environ.get('DATA_DIR', 'data')).resolve()


def init():
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'media').mkdir(exist_ok=True)
    (DATA / 'incoming').mkdir(exist_ok=True)
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE NOT NULL,
          password TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
          expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS videos (
          id TEXT PRIMARY KEY, owner TEXT REFERENCES users(id), title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'processing',
          error TEXT, duration REAL DEFAULT 0, size INTEGER DEFAULT 0,
          views INTEGER DEFAULT 0, created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS likes (
          user_id TEXT REFERENCES users(id), video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,
          PRIMARY KEY(user_id, video_id));
        CREATE TABLE IF NOT EXISTS subscriptions (
          user_id TEXT REFERENCES users(id), channel_id TEXT REFERENCES users(id),
          PRIMARY KEY(user_id, channel_id));
        CREATE TABLE IF NOT EXISTS comments (
          id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id),
          video_id TEXT REFERENCES videos(id) ON DELETE CASCADE, text TEXT NOT NULL, created INTEGER);
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id),
          video_id TEXT REFERENCES videos(id) ON DELETE CASCADE, reason TEXT, created INTEGER);
        CREATE TABLE IF NOT EXISTS unknown_calls (
          path TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS video_feed ON videos(status, created DESC);
        CREATE INDEX IF NOT EXISTS comment_video ON comments(video_id, created);
        ''')


@contextlib.contextmanager
def db():
    c = sqlite3.connect(DATA / 'mewtube.sqlite3', timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        with c:
            yield c
    finally:
        c.close()


def video(c, video_id):
    return c.execute('''SELECT v.*, u.username,
      (SELECT count(*) FROM likes WHERE video_id=v.id) likes
      FROM videos v JOIN users u ON u.id=v.owner WHERE v.id=?''', (video_id,)).fetchone()


def videos(c, query='', channel=None, subscriber=None, limit=40, offset=0):
    sql = '''SELECT v.*, u.username, (SELECT count(*) FROM likes WHERE video_id=v.id) likes
      FROM videos v JOIN users u ON u.id=v.owner WHERE v.status='ready' '''
    args = []
    if query:
        sql += 'AND (v.title LIKE ? ESCAPE \'!\' OR v.description LIKE ? ESCAPE \'!\') '
        q = '%' + query.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        args += [q, q]
    if channel:
        sql += 'AND v.owner=? '
        args.append(channel)
    if subscriber:
        sql += 'AND v.owner IN (SELECT channel_id FROM subscriptions WHERE user_id=?) '
        args.append(subscriber)
    return c.execute(sql + 'ORDER BY v.created DESC LIMIT ? OFFSET ?', [*args, limit, offset]).fetchall()

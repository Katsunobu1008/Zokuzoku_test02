"""SQLite persistence and transactional application services. DB is source of truth."""
from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DEMO_USERS = [('a', 'アオイ', '#7c92f2'), ('b', 'ミナ', '#ff80ba'),
              ('c', 'ハル', '#3dcfbf'), ('d', 'ユウ', '#f4b85d')]
COLORS = ['#80a7fb', '#fd92bc', '#61d6cc', '#e8b2ff', '#f6bd77', '#87dbfc']
FORMS = ['アクリルチャーム', 'ぬいぐるみ', 'ガラスオブジェ', 'バッグ', 'ルームライト', 'マグカップ', '文具', 'アクセサリー', '香りの雑貨', 'アート']
MOODS = ['やさしい光', '透明感', '普段使い', '幻想的', 'もふもふ', '落ち着いた色', '海の記憶', 'ギフトに', 'ミニマル', '上質な素材']


class DomainError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.status = status
        super().__init__(message)


def now() -> int:
    return int(time.time())


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # SQLite journal mode is persistent; set it before transactional setup.
        with sqlite3.connect(path) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        self._setup()

    @contextmanager
    def connect(self, write: bool = False):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=10000')
        if write:
            conn.execute('BEGIN IMMEDIATE')
        try:
            yield conn
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _setup(self):
        with self.connect(True) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ideas(
               id TEXT PRIMARY KEY, parent_id TEXT REFERENCES ideas(id), author_id TEXT NOT NULL REFERENCES users(id),
               title TEXT NOT NULL, prompt TEXT NOT NULL, category TEXT NOT NULL, mood TEXT NOT NULL,
               rights TEXT NOT NULL CHECK(rights IN ('original','licensed')),
               moderation TEXT NOT NULL DEFAULT 'approved', image_path TEXT,
               generation INTEGER NOT NULL, created_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_ideas_parent ON ideas(parent_id);
            CREATE INDEX IF NOT EXISTS ix_ideas_created ON ideas(created_at DESC);
            CREATE TABLE IF NOT EXISTS likes(idea_id TEXT NOT NULL REFERENCES ideas(id), user_id TEXT NOT NULL REFERENCES users(id),
               created_at INTEGER NOT NULL, PRIMARY KEY(idea_id,user_id));
            CREATE TABLE IF NOT EXISTS pledges(idea_id TEXT NOT NULL REFERENCES ideas(id), user_id TEXT NOT NULL REFERENCES users(id),
               points INTEGER NOT NULL CHECK(points IN (10, 50, 100)), created_at INTEGER NOT NULL,
               PRIMARY KEY(idea_id,user_id));
            CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY, idea_id TEXT NOT NULL REFERENCES ideas(id),
               user_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
               idea_id TEXT, at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS image_jobs(idea_id TEXT PRIMARY KEY REFERENCES ideas(id), state TEXT NOT NULL,
               updated_at INTEGER NOT NULL, error TEXT);
            ''')
            for uid, name, color in DEMO_USERS:
                db.execute('INSERT OR IGNORE INTO users(id,name,color) VALUES (?,?,?)', (uid, name, color))
            count = db.execute('SELECT COUNT(*) FROM ideas').fetchone()[0]
            if count == 0:
                self._seed(db)

    def _seed(self, db):
        base = now() - 86400
        # Deterministic rooted tree: 100 samples, depth not treated as quality.
        generations = {}
        for i in range(100):
            parent = None if i == 0 else f'seed-{max(0, (i - 1) // 2):03d}'
            gen = 0 if i == 0 else generations[parent] + 1
            kind, mood = FORMS[(i * 7 + (i // 9)) % len(FORMS)], MOODS[(i * 3 + i // 7) % len(MOODS)]
            generations[f'seed-{i:03d}'] = gen
            title = 'はじまりのクラゲ' if i == 0 else f'{mood}の{kind}'
            prompt = f'やさしいクラゲのモチーフ、{mood}、{kind}、海を感じるデザイン'
            db.execute('''INSERT INTO ideas(id,parent_id,author_id,title,prompt,category,mood,rights,moderation,
               generation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
               (f'seed-{i:03d}', parent, DEMO_USERS[i % 4][0], title, prompt, kind, mood,
                'original', 'approved', gen, base + i * 430))
        db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)', ('seed','seed-000',now()))
        for i in range(100):
            if i % 4 == 0:
                db.execute('INSERT INTO likes(idea_id,user_id,created_at) VALUES(?,?,?)',
                           (f'seed-{i:03d}', DEMO_USERS[(i+1)%4][0], now()))

    def _user(self, db, uid):
        if not db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
            raise DomainError('Unknown demo user', 403)

    def _idea(self, db, idea_id):
        row = db.execute('SELECT * FROM ideas WHERE id=? AND moderation=?', (idea_id,'approved')).fetchone()
        if row is None:
            raise DomainError('Idea not found', 404)
        return row

    def list_ideas(self, user='a'):
        with self.connect() as db:
            data = db.execute('''SELECT i.*, u.name AS author, u.color AS author_color,
                 (SELECT COUNT(*) FROM likes l WHERE l.idea_id=i.id) AS likes,
                 (SELECT COUNT(*) FROM pledges p WHERE p.idea_id=i.id) AS supporters,
                 (SELECT COALESCE(SUM(points),0) FROM pledges p WHERE p.idea_id=i.id) AS support_points,
                 (SELECT COUNT(*) FROM likes l WHERE l.idea_id=i.id AND l.user_id=?) AS liked,
                 (SELECT points FROM pledges p WHERE p.idea_id=i.id AND p.user_id=?) AS my_pledge
              FROM ideas i JOIN users u ON u.id=i.author_id WHERE i.moderation='approved'
              ORDER BY i.created_at ASC''', (user,user)).fetchall()
            seq = db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            return {'ideas': [dict(row) for row in data], 'seq': seq,
                    'users': [dict(row) for row in db.execute('SELECT * FROM users')]}

    def latest_seq(self):
        with self.connect() as db:
            return db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]

    def create_idea(self, actor: str, data: dict):
        title = str(data.get('title','')).strip()
        prompt = str(data.get('prompt','')).strip()
        parent = data.get('parent_id') or None
        category = str(data.get('category','')).strip() or 'その他'
        mood = str(data.get('mood','')).strip() or '自由な発想'
        rights = str(data.get('rights',''))
        if not (2 <= len(title) <= 80 and 4 <= len(prompt) <= 600 and len(category) <= 60 and len(mood) <= 60):
            raise DomainError('Title or prompt is outside allowed length')
        if rights != 'original':
            raise DomainError('MVP publishes only self-owned original creations. Licensed IP workflow is not enabled.')
        with self.connect(True) as db:
            self._user(db, actor)
            gen = 0
            if parent:
                p = self._idea(db, parent)
                gen = p['generation'] + 1
            idea_id = 'idea-' + uuid.uuid4().hex[:16]
            db.execute('''INSERT INTO ideas(id,parent_id,author_id,title,prompt,category,mood,rights,
               generation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
               (idea_id,parent,actor,title,prompt,category,mood,rights,gen,now()))
            db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)', ('created',idea_id,now()))
            return {'id': idea_id, 'generation': gen}

    def like(self, actor: str, idea_id: str):
        with self.connect(True) as db:
            self._user(db, actor);self._idea(db, idea_id)
            found = db.execute('SELECT 1 FROM likes WHERE idea_id=? AND user_id=?',(idea_id,actor)).fetchone()
            if found:
                db.execute('DELETE FROM likes WHERE idea_id=? AND user_id=?',(idea_id,actor))
            else:
                db.execute('INSERT INTO likes VALUES (?,?,?)',(idea_id,actor,now()))
            db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)',('like',idea_id,now()))
            return {'liked': not bool(found)}

    def pledge(self, actor: str, idea_id: str, points):
        if type(points) is not int or points not in (10,50,100):
            raise DomainError('Choose a simulated point amount: 10, 50 or 100')
        with self.connect(True) as db:
            self._user(db,actor);self._idea(db,idea_id)
            db.execute('''INSERT INTO pledges VALUES(?,?,?,?) ON CONFLICT(idea_id,user_id)
                DO UPDATE SET points=excluded.points, created_at=excluded.created_at''',
                (idea_id,actor,points,now()))
            db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)',('pledge',idea_id,now()))
            return {'points':points, 'status':'intent_recorded', 'charged':False}

    def comment(self, actor: str, idea_id: str, content: str):
        content = content.strip()
        if not 1 <= len(content) <= 400:
            raise DomainError('Comment must be 1-400 characters')
        with self.connect(True) as db:
            self._user(db,actor);self._idea(db,idea_id)
            db.execute('INSERT INTO comments VALUES(?,?,?,?,?)',
                       ('comment-'+uuid.uuid4().hex[:16],idea_id,actor,content,now()))
            db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)',('comment',idea_id,now()))
        return {'ok':True}

    def comments(self, idea_id):
        with self.connect() as db:
            self._idea(db,idea_id)
            return [dict(r) for r in db.execute('''SELECT c.body,c.created_at,u.name FROM comments c JOIN users u
                 ON c.user_id=u.id WHERE idea_id=? ORDER BY c.created_at DESC LIMIT 50''',(idea_id,))]

    def begin_image(self, idea_id: str, actor: str):
        with self.connect(True) as db:
            idea=self._idea(db,idea_id)
            if idea['author_id'] != actor:
                raise DomainError('Only the author can generate an image for their idea',403)
            if idea['image_path']:
                raise DomainError('This idea already has a generated image',409)
            prior=db.execute('SELECT state FROM image_jobs WHERE idea_id=?',(idea_id,)).fetchone()
            if prior and prior['state']=='running':
                raise DomainError('Generation is already running',409)
            db.execute('''INSERT INTO image_jobs VALUES(?,?,?,NULL) ON CONFLICT(idea_id)
                DO UPDATE SET state='running',updated_at=excluded.updated_at,error=NULL''',(idea_id,'running',now()))
            return dict(idea)

    def finish_image(self, idea_id: str, path: str):
        with self.connect(True) as db:
            db.execute('UPDATE ideas SET image_path=? WHERE id=?',(path,idea_id))
            db.execute('UPDATE image_jobs SET state=?,updated_at=? WHERE idea_id=?',('complete',now(),idea_id))
            db.execute('INSERT INTO events(kind,idea_id,at) VALUES(?,?,?)',('image',idea_id,now()))

    def fail_image(self, idea_id: str, message: str):
        with self.connect(True) as db:
            db.execute('UPDATE image_jobs SET state=?,updated_at=?,error=? WHERE idea_id=?',
                       ('failed',now(),message[:160],idea_id))

    def insights(self):
        with self.connect() as db:
            cats=[dict(r) for r in db.execute('''SELECT category as label,COUNT(*) as count
                    FROM ideas GROUP BY category ORDER BY count DESC LIMIT 12''')]
            moods=[dict(r) for r in db.execute('''SELECT mood as label,COUNT(*) as count
                    FROM ideas GROUP BY mood ORDER BY count DESC LIMIT 12''')]
            top=[dict(r) for r in db.execute('''SELECT i.title,i.category,i.id,
                  (SELECT COUNT(*) FROM likes l WHERE l.idea_id=i.id) as likes,
                  (SELECT COALESCE(SUM(points),0) FROM pledges p WHERE p.idea_id=i.id) as support_points
                  FROM ideas i WHERE i.moderation='approved' ORDER BY support_points DESC, likes DESC LIMIT 8''')]
            return {'categories':cats,'moods':moods,'popular':top,
                    'disclaimer':'分類・プロンプトは顧客行動の観測であり、購買需要・インサイトの証明ではありません。'}

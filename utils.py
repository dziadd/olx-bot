import sqlite3
import discord
import time

DB_PATH = "olx_bot.db"
LIMIT_WIDZIANYCH = 1000000

# Inicjalizacja bazy danych (utworzy tabele, jeśli nie istnieją)
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS widziane (link TEXT PRIMARY KEY, ts REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS obserwowane (link TEXT PRIMARY KEY, id_kanalu INTEGER)''')
        conn.commit()

init_db()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def czy_widziano(link):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM widziane WHERE link = ?', (link,))
        return cursor.fetchone() is not None

def dodaj_do_widzianych(link):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO widziane (link, ts) VALUES (?, ?)', (link, time.time()))
        
        # Ochrona przed rozrostem bazy
        cursor.execute('SELECT COUNT(*) FROM widziane')
        if cursor.fetchone()[0] > LIMIT_WIDZIANYCH:
            # Usuwa najstarsze wpisy
            cursor.execute('DELETE FROM widziane WHERE link IN (SELECT link FROM widziane ORDER BY ts ASC LIMIT 100)')
        conn.commit()

def pobierz_obserwowane():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT link, id_kanalu FROM obserwowane')
        return dict(cursor.fetchall())

def dodaj_obserwowane(link, id_kanalu):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO obserwowane (link, id_kanalu) VALUES (?, ?)', (link, id_kanalu))
        conn.commit()

def usun_obserwowane(link):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM obserwowane WHERE link = ?', (link,))
        conn.commit()

def wyczysc_obserwowane():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM obserwowane')
        conn.commit()

def licz_widziane_oferty():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM widziane')
        return cursor.fetchone()[0]

class OlxPrzyciski(discord.ui.View):
    def __init__(self, url_oferty):
        super().__init__(timeout=None)
        btn_przejdz = discord.ui.Button(label="🛒 PRZEJDŹ DO OGŁOSZENIA", url=url_oferty, style=discord.ButtonStyle.link)
        self.add_item(btn_przejdz)

import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
import random
import asyncio
import time
import datetime
import os
from dotenv import load_dotenv
from utils import dodaj_do_wl, pobierz_wl

load_dotenv()

from utils import (pobierz_obserwowane, dodaj_obserwowane, usun_obserwowane, 
                   wyczysc_obserwowane, licz_widziane_oferty, dodaj_do_widzianych, 
                   USER_AGENTS, OlxPrzyciski)
from scraper import sprawdz_olx

intents = discord.Intents.default()
intents.message_content = True

class OlxBot(commands.Bot):
    async def close(self):
        print("Trwa zamykanie przeglądarki i bota...")
        global browser_playwright, playwright_instance
        try:
            if browser_playwright:
                await browser_playwright.close()
            if playwright_instance:
                await playwright_instance.stop()
        except Exception:
            pass 
        await super().close()

bot = OlxBot(command_prefix="!", intents=intents, help_command=None)
TOKEN = os.getenv("DISCORD_TOKEN")

playwright_instance = None
browser_playwright = None
czas_startu = time.time()
licznik_petli = 0

@bot.command(name="dodaj")
async def dodaj_link(ctx, url: str):
    if "olx.pl" not in url:
        await ctx.send("To nie wygląda na poprawny link do OLX!")
        return
        
    aktualne = pobierz_obserwowane()
    if url in aktualne:
        await ctx.send("Ten link jest już na liście!")
        return
        
    dodaj_obserwowane(url, ctx.channel.id)
    await ctx.send(f"Dodano nowy link na kanał <#{ctx.channel.id}>.")

@bot.command(name="lista")
async def lista_linkow(ctx):
    aktualne = pobierz_obserwowane()
    if not aktualne:
        await ctx.send("Nie dodałeś żadnego linku.")
        return
        
    await ctx.send("**Obserwowane wyszukiwania OLX:**")
    
    for i, (link, id_kanalu) in enumerate(aktualne.items(), start=1):
        wiadomosc = f"**{i}.** <{link}> (Kanał: <#{id_kanalu}>)"
        await ctx.send(wiadomosc)

@bot.command(name="usun")
async def usun_link(ctx, numer: int):
    aktualne = pobierz_obserwowane()
    if numer < 1 or numer > len(aktualne):
        await ctx.send("Błędny numer!")
        return
    klucze = list(aktualne.keys())
    link_do_usuniecia = klucze[numer - 1]
    usun_obserwowane(link_do_usuniecia)
    await ctx.send(f"Usunięto link numer {numer}.")

@bot.command(name="wyczysc")
async def wyczysc_linki(ctx):
    wyczysc_obserwowane()
    await ctx.send("🧹 Wszystkie obserwowane linki zostały usunięte z bazy.")

@bot.command(name="status")
async def status_bota(ctx):
    ping = round(bot.latency * 1000)
    uptime_sekundy = int(time.time() - czas_startu)
    uptime = str(datetime.timedelta(seconds=uptime_sekundy))
    liczba_ofert = licz_widziane_oferty()
    
    embed = discord.Embed(title="🤖 Status Bota OLX", color=discord.Color.green())
    embed.add_field(name="Opóźnienie", value=f"{ping} ms", inline=True)
    embed.add_field(name="Czas działania", value=uptime, inline=True)
    embed.add_field(name="Ofert w bazie", value=str(liczba_ofert), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="help")
async def pomoc(ctx):
    embed = discord.Embed(
        title="Pomoc - OLX Bot",
        description="Lista dostępnych komend do zarządzania:",
        color=discord.Color.orange()
    )
    embed.add_field(name="!dodaj [link]", value="Dodaje link do bazy.", inline=False)
    embed.add_field(name="!lista", value="Wyświetla obserwowane linki.", inline=False)
    embed.add_field(name="!usun [numer]", value="Usuwa konkretny link.", inline=False)
    embed.add_field(name="!wyczysc", value="Usuwa WSZYSTKIE linki.", inline=False)
    embed.add_field(name="!status", value="Wyświetla stan serwera bota.", inline=False)
    await ctx.send(embed=embed)

@tasks.loop(seconds=15)
async def szukaj_okazji():
    global licznik_petli, browser_playwright
    
    aktualne_linki = pobierz_obserwowane()
    if not aktualne_linki:
        return

    # Mechanizm czyszczenia pamięci (zapobiega wyciekom RAM na serwerze)
    licznik_petli += 1
    if licznik_petli >= 100: # Co ~30-45 minut restartuje ukrytą przeglądarkę
        print("Restart przeglądarki w celu zwolnienia pamięci RAM...")
        if browser_playwright:
            await browser_playwright.close()
        browser_playwright = await playwright_instance.chromium.launch(headless=True)
        licznik_petli = 0

    wybrany_ua = random.choice(USER_AGENTS)
    context = await browser_playwright.new_context(
        user_agent=wybrany_ua,
        viewport={'width': 1920, 'height': 1080}
    )
    nowa_karta = await context.new_page()
    await nowa_karta.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        for link, id_kanalu in list(aktualne_linki.items()):
            nowe_oferty = await sprawdz_olx(link, nowa_karta)
            
            if len(nowe_oferty) > 0:
                kanal_docelowy = bot.get_channel(id_kanalu)
                if kanal_docelowy:
                    for oferta in nowe_oferty:
                        embed = discord.Embed(
                            title=oferta['tytul'],
                            url=oferta['link'],
                            description=oferta['opis'],
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="Cena", value=f"**{oferta['cena']}**", inline=True)
                        
                        if oferta['zdjecie'] and oferta['zdjecie'].startswith("http"):
                            embed.set_image(url=oferta['zdjecie'])
                            
                        embed.set_footer(text="OLX Bot")
                        widok = OlxPrzyciski(url_oferty=oferta['link'])
                        
                        await kanal_docelowy.send(embed=embed, view=widok)
                        dodaj_do_widzianych(oferta['link'])
                        
            await asyncio.sleep(random.uniform(4.0, 8.0))
    finally:
        await context.close()

@szukaj_okazji.before_loop
async def przed_startem_petli():
    await bot.wait_until_ready()
    global playwright_instance, browser_playwright
    if playwright_instance is None:
        playwright_instance = await async_playwright().start()
        browser_playwright = await playwright_instance.chromium.launch(headless=True)

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user} i podłączono do bazy SQLite!')
    szukaj_okazji.start() 

bot.run(TOKEN)

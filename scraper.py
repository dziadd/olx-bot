import re
from utils import czy_widziano

async def sprawdz_olx(url, page): 
    wyniki = []
    try:
        await page.goto(url)
        await page.wait_for_timeout(3000)
        
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollTo(0, 0);")
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        kafelki = page.locator('[data-cy="l-card"]')
        ilosc_ofert = await kafelki.count()
        limit = min(10, ilosc_ofert)
        
        for i in range(limit):
            pojedynczy_kafelek = kafelki.nth(i)
            link_element = pojedynczy_kafelek.locator('a').first
            
            if await link_element.count() > 0:
                link_koncowka = await link_element.get_attribute('href')
                
                if link_koncowka.startswith("http"):
                    pelny_link = link_koncowka
                else:
                    pelny_link = f"https://www.olx.pl{link_koncowka}"
                    
                czysty_link = pelny_link.split('#')[0].split('?')[0]
                
                if not czy_widziano(czysty_link):
                    tekst_surowy = await pojedynczy_kafelek.inner_text()
                    linie = [linia.strip() for linia in tekst_surowy.split('\n') if linia.strip()] 
                    
                    tytul = "Brak tytułu"
                    etykiety_do_pominiecia = ["dostawa gratis", "przesyłka olx", "promowane", "najtańsza przesyłka", "nowość"]
                    
                    for linia in linie:
                        if not any(etykieta in linia.lower() for etykieta in etykiety_do_pominiecia):
                            if len(linia) > 3 and "zł" not in linia:
                                tytul = linia
                                break
                                
                    cena = "Brak"
                    for linia in linie:
                        if 'zł' in linia:
                            cena = linia
                            break 
                    
                    try:
                        img_element = pojedynczy_kafelek.locator("img").first
                        zdjecie_url = await img_element.get_attribute("data-src")
                        
                        if not zdjecie_url:
                            zdjecie_url = await img_element.get_attribute("src")
                            
                        if zdjecie_url:
                            if zdjecie_url.startswith("data:") or "spacer" in zdjecie_url:
                                zdjecie_url = None
                            elif zdjecie_url.startswith("/"):
                                zdjecie_url = f"https://www.olx.pl{zdjecie_url}"
                    except Exception:
                        zdjecie_url = None
                        
                    opis_przedmiotu = "Brak opisu"
                    karta_opisu = None
                    try:
                        karta_opisu = await page.context.new_page()
                        await karta_opisu.goto(czysty_link, wait_until="domcontentloaded", timeout=4000)
                        html = await karta_opisu.content()
                        
                        dopasowanie = re.search(r'property="og:description"\s+content="([^"]+)"', html)
                        if not dopasowanie:
                            dopasowanie = re.search(r'name="description"\s+content="([^"]+)"', html)
                            
                        if dopasowanie:
                            opis_przedmiotu = dopasowanie.group(1).replace("Znajdź to i wiele innych ofert...", "").strip()
                            if len(opis_przedmiotu) > 250:
                                opis_przedmiotu = opis_przedmiotu[:247] + "..."
                    except Exception:
                        pass
                    finally:
                        if karta_opisu:
                            await karta_opisu.close()
                        
                    dane_oferty = {
                        "link": czysty_link,
                        "tytul": tytul,
                        "cena": cena,
                        "zdjecie": zdjecie_url,
                        "opis": opis_przedmiotu
                    }
                    wyniki.append(dane_oferty)
                    
    except Exception as e:
        print(f"Błąd podczas scrapowania OLX: {e}")
        
    return wyniki

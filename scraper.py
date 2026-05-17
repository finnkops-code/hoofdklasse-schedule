import json
import urllib.request
from datetime import datetime, timezone, timedelta

SCHEDULE_URL = "https://boxscore.stenwessel.nl/api/fetchschedule.php?competition=hb2026"

def fetch_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "nl-NL,nl;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_played(g):
    """
    Een wedstrijd is gespeeld als gamestatustext == "F" (Final),
    of als gamestatus == 3, of als er een score is.
    We checken alle drie zodat we nooit iets missen.
    """
    if g.get("gamestatustext") == "F":
        return True
    if g.get("gamestatus") == 3:
        return True
    if g.get("homeruns") is not None and g.get("awayruns") is not None:
        home = g.get("homeruns", 0)
        away = g.get("awayruns", 0)
        if home > 0 or away > 0:
            return True
    return False


def speelronde_bounds():
    """
    Geeft de donderdag en zaterdag van de meest recente speelronde.
    Speeldagen Hoofdklasse 2026: donderdag (avond) + zaterdag (doubleheader).

    Logica:
    - Ma t/m wo → vorige week do + za
    - Do t/m zo → deze week do + za
    """
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    today = now.date()
    weekday = today.weekday()  # 0=ma … 6=zo

    # Dagen terug tot de meest recente donderdag
    days_since_thursday = (weekday - 3) % 7
    thursday = today - timedelta(days=days_since_thursday)
    saturday = thursday + timedelta(days=2)
    return thursday, saturday


def format_dutch_day(dt):
    days = ["maandag", "dinsdag", "woensdag", "donderdag",
            "vrijdag", "zaterdag", "zondag"]
    months = ["", "januari", "februari", "maart", "april", "mei", "juni",
              "juli", "augustus", "september", "oktober", "november", "december"]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month]}"


def parse_game(g):
    start_str = g.get("start", "")
    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        start_dt = None

    played = is_played(g)
    innings_count = g.get("innings") or 9

    home_innings, away_innings = [], []
    for i in range(1, min(innings_count + 1, 21)):
        home_innings.append(g.get(f"runshome{i}", 0))
        away_innings.append(g.get(f"runsaway{i}", 0))

    return {
        "id":            g.get("id"),
        "datum":         start_dt.strftime("%Y-%m-%d") if start_dt else None,
        "tijdstip":      start_dt.strftime("%H:%M") if start_dt else None,
        "dag":           format_dutch_day(start_dt) if start_dt else None,
        "thuis":         g.get("homelabel"),
        "thuis_code":    g.get("homeioc"),
        "uit":           g.get("awaylabel"),
        "uit_code":      g.get("awayioc"),
        "score_thuis":   g.get("homeruns") if played else None,
        "score_uit":     g.get("awayruns") if played else None,
        "thuis_innings": home_innings if played else [],
        "uit_innings":   away_innings if played else [],
        "innings":       innings_count if played else None,
        "gamestatus":    g.get("gamestatustext", ""),
        "locatie":       g.get("location"),
        "stadion":       g.get("stadium"),
        "gespeeld":      played,
    }


def main():
    print(f"Ophalen van {SCHEDULE_URL}...")
    data = fetch_json(SCHEDULE_URL)
    games_raw = data.get("games", [])
    print(f"Wedstrijden ontvangen: {len(games_raw)}")

    thursday, saturday = speelronde_bounds()
    today = (datetime.now(timezone.utc) + timedelta(hours=2)).date()
    print(f"Meest recente speelronde: {thursday} (do) t/m {saturday} (za)")

    uitslagen = []
    programma = []

    for g in games_raw:
        game = parse_game(g)
        if not game["datum"]:
            continue
        game_date = datetime.strptime(game["datum"], "%Y-%m-%d").date()

        if game["gespeeld"] and thursday <= game_date <= saturday:
            uitslagen.append(game)
        elif not game["gespeeld"] and game_date > today:
            # Programma: alleen toekomstige wedstrijden
            programma.append(game)

    uitslagen.sort(key=lambda g: (g["datum"], g["tijdstip"] or ""))
    programma.sort(key=lambda g: (g["datum"], g["tijdstip"] or ""))
    programma = programma[:10]

    # Debug: print wat we gevonden hebben
    print(f"\nGespeelde wedstrijden in speelronde:")
    for u in uitslagen:
        print(f"  {u['datum']} {u['thuis']} {u['score_thuis']}-{u['score_uit']} {u['uit']}")

    if not uitslagen:
        print("  ⚠️  Geen uitslagen gevonden — controleer gamestatus waarden:")
        for g in games_raw[:5]:
            print(f"  id={g.get('id')} status={g.get('gamestatus')} statustext={g.get('gamestatustext')} start={g.get('start')} homeruns={g.get('homeruns')}")

    output = {
        "bijgewerkt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bron": SCHEDULE_URL,
        "speelronde": {
            "van": str(thursday),
            "tot": str(saturday),
        },
        "uitslagen": uitslagen,
        "programma": programma,
    }

    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ schedule.json opgeslagen")
    print(f"   Uitslagen deze speelronde : {len(uitslagen)}")
    print(f"   Aankomende wedstrijden    : {len(programma)}")


if __name__ == "__main__":
    main()

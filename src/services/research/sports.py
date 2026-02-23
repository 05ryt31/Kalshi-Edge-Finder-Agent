import re

from src.clients.odds_api import OddsAPIClient
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SportsResearcher:
    SPORT_KEY_MAP: dict[str, str] = {
        "NBA": "basketball_nba",
        "NCAAB": "basketball_ncaab",
        "NFL": "americanfootball_nfl",
        "NCAAF": "americanfootball_ncaaf",
        "MLB": "baseball_mlb",
        "NHL": "icehockey_nhl",
        "MLS": "soccer_usa_mls",
        "UFC": "mma_mixed_martial_arts",
        "MMA": "mma_mixed_martial_arts",
        "EPL": "soccer_epl",
    }

    TITLE_SPORT_MAP: dict[str, str] = {
        "basketball": "basketball_nba",
        "nba": "basketball_nba",
        "march madness": "basketball_ncaab",
        "football": "americanfootball_nfl",
        "nfl": "americanfootball_nfl",
        "super bowl": "americanfootball_nfl",
        "college football": "americanfootball_ncaaf",
        "baseball": "baseball_mlb",
        "mlb": "baseball_mlb",
        "world series": "baseball_mlb",
        "hockey": "icehockey_nhl",
        "nhl": "icehockey_nhl",
        "stanley cup": "icehockey_nhl",
        "soccer": "soccer_usa_mls",
        "mls": "soccer_usa_mls",
        "premier league": "soccer_epl",
        "ufc": "mma_mixed_martial_arts",
        "mma": "mma_mixed_martial_arts",
    }

    NBA_TEAMS = [
        "Lakers", "Celtics", "Warriors", "Nets", "Bucks", "76ers", "Sixers",
        "Suns", "Mavericks", "Heat", "Nuggets", "Clippers", "Grizzlies",
        "Cavaliers", "Knicks", "Raptors", "Bulls", "Hawks", "Pacers",
        "Trail Blazers", "Timberwolves", "Pelicans", "Kings", "Spurs",
        "Thunder", "Magic", "Wizards", "Hornets", "Pistons", "Jazz", "Rockets",
    ]

    NFL_TEAMS = [
        "Chiefs", "Eagles", "49ers", "Bills", "Cowboys", "Ravens", "Dolphins",
        "Lions", "Bengals", "Jaguars", "Chargers", "Steelers", "NY Jets", "Bears",
        "Packers", "Seahawks", "Vikings", "Saints", "Texans", "Broncos",
        "Commanders", "Browns", "Raiders", "Rams", "Colts", "Falcons",
        "Arizona Cardinals", "NY Giants", "Carolina Panthers", "Titans", "Buccaneers", "Patriots",
    ]

    MLB_TEAMS = [
        "Yankees", "Dodgers", "Astros", "Braves", "Mets", "Phillies",
        "Padres", "Guardians", "Mariners", "Orioles", "Rays", "Blue Jays",
        "Rangers", "Twins", "Red Sox", "Cubs", "Brewers", "STL Cardinals",
        "Diamondbacks", "Marlins", "SF Giants", "Pirates", "Reds", "Royals",
        "White Sox", "Tigers", "Angels", "Rockies", "Athletics", "Nationals",
    ]

    NHL_TEAMS = [
        "Avalanche", "Lightning", "Florida Panthers", "Bruins", "Oilers", "Rangers",
        "Hurricanes", "Maple Leafs", "Flames", "Stars", "Wild", "Penguins",
        "Kraken", "Devils", "Islanders", "Capitals", "Senators", "Predators",
        "Canucks", "Red Wings", "Sabres", "Blue Jackets", "Blackhawks",
        "Flyers", "Sharks", "Ducks", "Winnipeg Jets", "Coyotes", "Golden Knights",
    ]

    # Mapping of short (ambiguous) names to their specific team names by league
    # Used for backward compatibility in _extract_teams
    AMBIGUOUS_TEAMS: dict[str, dict[str, str]] = {
        "giants": {"nfl": "NY Giants", "mlb": "SF Giants"},
        "cardinals": {"nfl": "Arizona Cardinals", "mlb": "STL Cardinals"},
        "jets": {"nfl": "NY Jets", "nhl": "Winnipeg Jets"},
        "panthers": {"nfl": "Carolina Panthers", "nhl": "Florida Panthers"},
    }

    def __init__(self, client: OddsAPIClient) -> None:
        self.client = client

    async def research(self, market: Market) -> dict:
        sport_key = self._extract_sport_key(market)
        if not sport_key:
            return self._empty_report("Could not determine sport type")

        try:
            odds = await self.client.get_odds(sport_key)
            scores = await self.client.get_scores(sport_key)

            teams = self._extract_teams(market.title)
            relevant_odds = self._filter_relevant(odds, teams)
            relevant_scores = self._filter_relevant(scores, teams)

            return {
                "category": "sports",
                "data_sources": ["The Odds API"],
                "collected_data": {
                    "sport": sport_key,
                    "teams_identified": teams,
                    "odds": self._summarize_odds(relevant_odds),
                    "recent_scores": self._summarize_scores(relevant_scores),
                    "market_close_time": str(market.close_time),
                },
                "summary": self._generate_summary(relevant_odds, relevant_scores, teams),
            }
        except Exception as e:
            logger.error("sports_research_error", sport=sport_key, error=str(e))
            return self._empty_report(f"Error fetching sports data: {e}")

    def _extract_sport_key(self, market: Market) -> str | None:
        ticker = market.ticker.upper()
        for prefix, key in self.SPORT_KEY_MAP.items():
            if prefix in ticker:
                return key

        title_lower = market.title.lower()
        for keyword, key in self.TITLE_SPORT_MAP.items():
            if keyword in title_lower:
                return key

        for team in self.NBA_TEAMS:
            if team.lower() in title_lower:
                return "basketball_nba"
        for team in self.NFL_TEAMS:
            if team.lower() in title_lower:
                return "americanfootball_nfl"
        for team in self.MLB_TEAMS:
            if team.lower() in title_lower:
                return "baseball_mlb"
        for team in self.NHL_TEAMS:
            if team.lower() in title_lower:
                return "icehockey_nhl"

        # Check for ambiguous team names - these require additional context
        # from ticker prefix to disambiguate
        for short_name, leagues in self.AMBIGUOUS_TEAMS.items():
            if short_name in title_lower:
                # Check ticker for league prefix to disambiguate
                if "NFL" in ticker and "nfl" in leagues:
                    return "americanfootball_nfl"
                if "MLB" in ticker and "mlb" in leagues:
                    return "baseball_mlb"
                if "NHL" in ticker and "nhl" in leagues:
                    return "icehockey_nhl"
                # No ticker context - return first available league for this team
                # (NFL teams are checked first for backward compatibility)
                if "nfl" in leagues:
                    return "americanfootball_nfl"
                if "mlb" in leagues:
                    return "baseball_mlb"
                if "nhl" in leagues:
                    return "icehockey_nhl"

        return None

    def _extract_teams(self, title: str) -> list[str]:
        found: list[str] = []
        title_lower = title.lower()

        all_teams = self.NBA_TEAMS + self.NFL_TEAMS + self.MLB_TEAMS + self.NHL_TEAMS
        for team in all_teams:
            if team.lower() in title_lower:
                found.append(team)

        # Also check for short/ambiguous team names and return the disambiguated version
        # based on other context in the title
        for short_name, leagues in self.AMBIGUOUS_TEAMS.items():
            if short_name in title_lower:
                # Check if we already matched a specific version of this team
                already_matched = any(
                    short_name in team.lower() for team in found
                )
                if not already_matched:
                    # Try to disambiguate based on league keywords in title
                    sport_key = None
                    for keyword, key in self.TITLE_SPORT_MAP.items():
                        if keyword in title_lower:
                            sport_key = key
                            break

                    if sport_key:
                        if "nfl" in sport_key or "football" in sport_key:
                            if "nfl" in leagues:
                                found.append(leagues["nfl"])
                        elif "mlb" in sport_key or "baseball" in sport_key:
                            if "mlb" in leagues:
                                found.append(leagues["mlb"])
                        elif "nhl" in sport_key or "hockey" in sport_key:
                            if "nhl" in leagues:
                                found.append(leagues["nhl"])
                    else:
                        # No context to disambiguate, add all possibilities
                        found.extend(leagues.values())

        if not found:
            vs_match = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\s|$)", title, re.IGNORECASE)
            if vs_match:
                found = [vs_match.group(1).strip(), vs_match.group(2).strip()]

        return found

    def _filter_relevant(self, events: list[dict], teams: list[str]) -> list[dict]:
        if not teams:
            return events[:5]

        teams_lower = [t.lower() for t in teams]
        relevant = [
            event for event in events
            if any(
                t in (event.get("home_team", "") + " " + event.get("away_team", "")).lower()
                for t in teams_lower
            )
        ]
        return relevant if relevant else events[:5]

    def _summarize_odds(self, odds: list[dict]) -> list[dict]:
        summaries: list[dict] = []
        for event in odds[:5]:
            bookmakers = event.get("bookmakers", [])
            best_odds: dict[str, float] = {}
            for bm in bookmakers[:3]:
                for mkt in bm.get("markets", []):
                    if mkt["key"] == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            name = outcome["name"]
                            price = outcome["price"]
                            if name not in best_odds or price > best_odds[name]:
                                best_odds[name] = price

            summaries.append({
                "home": event.get("home_team", ""),
                "away": event.get("away_team", ""),
                "commence_time": event.get("commence_time", ""),
                "h2h_odds": best_odds,
            })
        return summaries

    def _summarize_scores(self, scores: list[dict]) -> list[dict]:
        return [
            {
                "home": s.get("home_team", ""),
                "away": s.get("away_team", ""),
                "scores": s.get("scores"),
                "completed": s.get("completed", False),
            }
            for s in scores[:5]
        ]

    def _generate_summary(
        self, odds: list[dict], scores: list[dict], teams: list[str]
    ) -> str:
        parts: list[str] = []
        if teams:
            parts.append(f"Teams: {', '.join(teams)}.")
        if odds:
            event = odds[0]
            home = event.get("home_team", "?")
            away = event.get("away_team", "?")
            parts.append(f"Next matchup: {away} @ {home}.")
        completed = [s for s in scores if s.get("completed")]
        if completed:
            parts.append(f"{len(completed)} recent completed game(s) found.")
        return " ".join(parts) if parts else "Sports data collected."

    def _empty_report(self, reason: str) -> dict:
        return {
            "category": "sports",
            "data_sources": [],
            "collected_data": {},
            "summary": reason,
        }

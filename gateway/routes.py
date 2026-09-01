from dataclasses import dataclass

@dataclass(frozen=True)
class ServiceRoute:
    name: str
    port: int
    prefixes: tuple[str, ...]

SERVICES = (
    ServiceRoute("main", 5010, ("/", "/help")),
    ServiceRoute("barnes_and_noble", 5011, ("/barnes_and_noble",)),
    ServiceRoute("bib_2_holdings_541", 5012, ("/bib_2_holdings_541",)),
    ServiceRoute("p_and_e_rollup_match", 5013, ("/p_and_e", "/p_and_e_rollup_match")),
    ServiceRoute("gift_fund_bibliography", 5014, ("/gift_fund_bibliography",)),
    ServiceRoute("combine_analytics_subjects_areas", 5015, ("/combine_analytics_subjects_areas", "/sql")),
    ServiceRoute("concurrent_checkouts", 5016, ("/concurrent_checkouts",)),
    ServiceRoute("film_search", 5017, ("/film_search",)),
)


def match_service(path: str) -> ServiceRoute:
    # Longest-prefix match. Main is the fallback and is deliberately last logically.
    candidates = []
    for service in SERVICES:
        for prefix in service.prefixes:
            if prefix == "/":
                continue
            if path == prefix or path.startswith(prefix + "/"):
                candidates.append((len(prefix), service))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return SERVICES[0]

from gateway.routes import match_service

def test_routes():
    assert match_service("/film_search/search").name == "film_search"
    assert match_service("/bib_2_holdings_541/").name == "bib_2_holdings_541"
    assert match_service("/").name == "main"

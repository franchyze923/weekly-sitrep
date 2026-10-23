from datetime import date

THIS = "2026-10-19"   # Monday of FAKE_TODAY's week
LAST = "2026-10-12"
NEXT = "2026-10-26"


def save(client, week, slug, text):
    return client.post("/week/{}/{}/save".format(week, slug), data={"raw_text": text})


def test_home_redirects_to_current_monday(client):
    r = client.get("/", follow_redirects=False)
    assert r.headers["location"].endswith("/week/" + THIS)


def test_any_date_snaps_to_its_monday(client):
    r = client.get("/week/2026-10-22")  # Thursday
    assert "Oct 19–25, 2026" in r.text


def test_bad_date_is_404(client):
    assert client.get("/week/not-a-date").status_code == 404


def test_current_week_has_badge_and_no_next_arrow(client):
    html = client.get("/week/" + THIS).text
    assert 'class="badge">current' in html
    assert 'title="Next week"' not in html
    assert '/week/' + LAST in html  # previous arrow


def test_past_week_shows_banner_and_next_arrow(client):
    html = client.get("/week/" + LAST).text
    assert "viewing a past week" in html
    assert 'href="/week/{}" title="Next week"'.format(THIS) in html


def test_future_week_shows_banner(client):
    assert "viewing a future week" in client.get("/week/" + NEXT).text


def test_new_week_starts_blank(client):
    save(client, LAST, "alpha", "- did last week's thing")
    this = client.get("/week/" + THIS).text
    assert "last week's thing" not in this
    assert "0 of 2 projects have reported" in this
    assert this.count("Not updated yet") == 2


def test_weeks_are_isolated_per_project(client):
    save(client, LAST, "alpha", "- week one alpha")
    save(client, THIS, "alpha", "- week two alpha")
    save(client, THIS, "beta", "- week two beta")
    last = client.get("/week/" + LAST).text
    this = client.get("/week/" + THIS).text
    assert "week one alpha" in last and "week two alpha" not in last
    assert "week two alpha" in this and "week two beta" in this and "week one alpha" not in this
    assert "1 of 2 projects have reported" in last
    assert "2 of 2 projects have reported" in this


def test_save_returns_status_and_progress(client):
    r = save(client, THIS, "alpha", "- hello")
    assert "Updated" in r.text and "tester@example.com" in r.text
    assert 'id="progress" hx-swap-oob="true"' in r.text
    assert "1 of 2 projects" in r.text


def test_whitespace_does_not_count_as_updated(client):
    r = save(client, THIS, "alpha", "   \n  ")
    assert "Not updated yet" in r.text


def test_generate_fills_summary_and_persists(client):
    r = client.post("/week/{}/alpha/generate".format(THIS), data={"raw_text": "- shipped x\n- blocked on y"})
    assert "Shipped x" in r.text and "placeholder summary" in r.text
    assert 'id="status-alpha" hx-swap-oob="true"' in r.text
    assert "Shipped x" in client.get("/week/" + THIS).text


def test_archived_project_hidden_but_history_kept(client):
    save(client, THIS, "beta", "- beta stuff")
    client.post("/projects/beta/toggle")
    html = client.get("/week/" + THIS).text
    assert "Beta" not in html and "0 of 1 projects" in html
    client.post("/projects/beta/toggle")
    assert "beta stuff" in client.get("/week/" + THIS).text


def test_rename_keeps_history(client):
    save(client, LAST, "alpha", "- old week")
    client.post("/projects/alpha/rename", data={"name": "Alpha Renamed"})
    html = client.get("/week/" + LAST).text
    assert "Alpha Renamed" in html and "old week" in html


def test_oob_progress_is_top_level_not_nested_in_status(client):
    """Regression: progress bar must not be nested inside the OOB status span,
    or HTMX inserts it into the project's badge slot."""
    import re
    for r in (save(client, THIS, "beta", "- y"),
              client.post("/week/{}/beta/generate".format(THIS), data={"raw_text": "- y"})):
        html = r.text
        assert html.count('id="progress" hx-swap-oob="true"') == 1
        status = re.search(r'<span id="status-beta" hx-swap-oob="true">(.*?)</span>', html, re.S)
        if status:
            assert "progress" not in status.group(1)


def test_version_in_footer_and_healthz(client):
    from app import __version__
    assert "v" + __version__ in client.get("/week/" + THIS).text
    assert client.get("/healthz").json()["version"] == __version__

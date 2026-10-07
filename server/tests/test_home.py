from tests.conftest import login


def test_home_is_public_and_offers_the_way_in(client, make):
    room_id = make.room(capacity=4)
    make.student(room_id=room_id)

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/auth/login">Кіру</a>' in html
    assert 'href="/auth/register">Тіркелу</a>' in html
    assert "Басқару тақтасына өту" not in html
    assert "<strong>25%</strong>" in html
    assert "3 бос орын" in html
    assert "1 студент тұрады" in html


def test_home_is_a_single_screen_without_menu_or_footer(client, make):
    make.user("user")
    guest = client.get("/").get_data(as_text=True)
    login(client, "user")
    member = client.get("/").get_data(as_text=True)

    for html in (guest, member):
        assert '<nav class="nav' not in html
        assert 'href="/rooms/"' not in html
        assert 'class="footer"' not in html
        assert "Жүйе не істей алады" not in html

    # Every other page keeps its menu and footer.
    rooms = client.get("/rooms/").get_data(as_text=True)
    assert '<nav class="nav">' in rooms and 'class="footer"' in rooms


def test_home_shows_no_personal_or_payment_data(client, make):
    student_id = make.student(name="Private Person", room_id=make.room(number="777"))
    make.payment(make.contract(student_id, number="SECRET-1"), amount="98765")

    html = client.get("/").get_data(as_text=True)

    for private in ("Private Person", "SECRET-1", "98 765", "№777"):
        assert private not in html


def test_home_on_empty_database(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<strong>0%</strong>" in html
    assert "Әзірге бөлмелер қосылмаған" in html
    assert "Әзірге тұрғындар жоқ" in html


def test_home_for_logged_in_user_links_to_dashboard_and_profile(client, make):
    make.user("user")
    login(client, "user")

    html = client.get("/").get_data(as_text=True)

    assert 'href="/dashboard">Басқару тақтасына өту</a>' in html
    assert 'href="/profile" aria-label="Менің бетім"' in html
    assert 'href="/auth/login"' not in html


def test_home_shows_occupancy_per_floor(client, make):
    first = make.room(floor=1, capacity=4)
    make.room(floor=1, capacity=4)
    make.room(floor=3, capacity=2)
    make.student(room_id=first)
    make.student(room_id=first)

    html = client.get("/").get_data(as_text=True)

    assert "<strong>1-қабат</strong>" in html and "<span>2 / 8 орын</span>" in html
    assert "<strong>3-қабат</strong>" in html and "<span>0 / 2 орын</span>" in html
    assert '<span style="width: 25%"></span>' in html


def test_home_residents_widget_counts_without_naming_anyone(client, make):
    room_id = make.room(capacity=6)
    for index in range(6):
        make.student(name=f"Resident {index}", room_id=room_id)
    make.student(name="Waiting One")
    make.student(name="Waiting Two")

    html = client.get("/").get_data(as_text=True)

    assert "6 студент тұрады" in html
    assert html.count('<span class="avatar">') == 4
    assert '<span class="avatar avatar-more">+2</span>' in html
    assert "2 студент бөлме күтуде" in html
    assert "Resident" not in html and "Waiting" not in html


def test_flash_message_is_shown_above_the_hero(client, make):
    make.user("user")
    login(client, "user")

    html = client.post("/auth/logout", follow_redirects=True).get_data(as_text=True)

    assert html.index("Жүйеден шықтыңыз") < html.index('class="lp-hero"')


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login?next=/dashboard"

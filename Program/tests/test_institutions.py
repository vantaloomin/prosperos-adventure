"""Institutions (dungeon/institutions.py): terms, the class schedule, demands as quests, and grades."""
from datetime import date, datetime, timedelta

import pytest
from test_travel import ok

from dungeon import factions, institutions, quests, record, story_clock, tiers

SCHOOL = {'institutions': [{
    'id': 'kingswood-academy', 'name': 'Kingswood Academy', 'city_id': 'kingswood', 'faction': 'cyrel-timber-guild',
    'default': True, 'core': ['letters', 'sums'],
    'terms': [{'name': 'Fall term', 'from': '09-01', 'to': '12-15'}, {'name': 'Winter term', 'from': '12-28', 'to': '02-20'}],
    'classes': [
        {'id': 'letters', 'name': 'Letters', 'days': ['mon', 'wed'], 'start': '10:00', 'place_id': 'pell-provisions'},
        {'id': 'sums', 'name': 'Sums', 'days': ['tue'], 'start': '14:00'},
        {'id': 'fencing', 'name': 'Fencing', 'days': ['fri'], 'start': '16:00', 'place_id': 'the-yard'}],
    'demands': [
        {'id': 'essay', 'kind': 'assignment', 'title': 'A weekly essay', 'every_days': 7, 'due_days': 5,
         'hook': 'Two pages on the reeve.', 'missed': 'The essay was never handed in.'},
        {'id': 'midterm', 'kind': 'exam', 'title': 'Midterm examination', 'week': 8, 'weight': 3}]}]}
MONDAY = datetime(2009, 9, 7, 8)


@pytest.fixture
def school(monkeypatch):
    monkeypatch.setattr(institutions, 'data', lambda world: SCHOOL if world == 'vallarith' else {'institutions': []})
    return SCHOOL['institutions'][0]


def test_terms_run_each_year_and_one_can_cross_the_new_year(school):
    assert institutions.term_at(school, date(2009, 10, 1))['name'] == 'Fall term 2009'
    assert institutions.term_at(school, date(2010, 1, 10)) == {'name': 'Winter term 2009', 'start': date(2009, 12, 28),
                                                               'end': date(2010, 2, 20)}
    assert institutions.term_at(school, date(2009, 12, 20)) is None
    once = {'terms': [{'name': 'Spring 2010', 'start': '2010-01-04', 'end': '2010-05-14'}]}
    assert institutions.term_at(once, date(2010, 3, 1))['name'] == 'Spring 2010'
    assert institutions.term_at(once, date(2011, 3, 1)) is None


def test_the_schedule_lists_each_meeting_of_the_chosen_classes_in_term(school):
    met = institutions.class_times(school, ['letters', 'sums'], MONDAY, MONDAY + timedelta(days=7))
    assert [(item['id'], at) for item, at in met] == [
        ('letters', datetime(2009, 9, 7, 10)), ('sums', datetime(2009, 9, 8, 14)),
        ('letters', datetime(2009, 9, 9, 10))]
    # Out of term nothing meets.
    assert institutions.class_times(school, ['letters'], datetime(2009, 12, 16), datetime(2009, 12, 27)) == []


def test_a_class_passed_elsewhere_is_missed_and_kept_in_the_record(app, school):
    with app.state.database.connect(write=True) as connection:
        institutions.enroll(connection, 'vallarith', 'kingswood-academy', None, MONDAY)
        # At the class's place for Letters; in town (no place named) for Sums.
        institutions.advance(connection, MONDAY, MONDAY + timedelta(hours=3), 'kingswood', 'pell-provisions', 'now')
        institutions.advance(connection, MONDAY + timedelta(days=1), MONDAY + timedelta(days=1, hours=7), 'kingswood',
                             'the-felled-oak', 'now')
        institutions.advance(connection, MONDAY + timedelta(days=2), MONDAY + timedelta(days=2, hours=3), 'kingswood',
                             'the-felled-oak', 'now')
        grades = institutions.grades(connection, school, 'Fall term 2009')
        assert (grades['attended'], grades['missed']) == (2, 1)
        assert any('missed Letters on Wednesday 09 September' in entry['text'] for entry in record.entries(connection))
        # Attendance alone: two of three is 67, a D.
        assert (grades['average'], grades['letter'], grades['gpa']) == (67, 'D', 1.0)


def test_demands_open_as_quests_once_and_are_graded_when_settled(app, school):
    with app.state.database.connect(write=True) as connection:
        institutions.enroll(connection, 'vallarith', 'kingswood-academy', ['letters'], MONDAY)
        # The term began on Tuesday the 1st: on Monday the first week's essay is already past due, so none opens.
        institutions.advance(connection, MONDAY, MONDAY + timedelta(hours=1), 'kingswood', 'pell-provisions', 'now')
        assert quests.rows(connection, 'open') == []
        tuesday = MONDAY + timedelta(days=1, hours=4)
        institutions.advance(connection, tuesday - timedelta(hours=1), tuesday, 'kingswood', 'pell-provisions', 'now')
        institutions.advance(connection, tuesday, tuesday + timedelta(hours=1), 'kingswood', 'pell-provisions', 'now')
        essay = [item for item in quests.rows(connection, 'open') if item['title'] == 'A weekly essay']
        # Once, due five days after the week's start; the exam is not announced yet.
        assert len(essay) == 1 and essay[0]['due_at'] == '2009-09-13T09:00'
        assert all(item['title'] != 'Midterm examination' for item in quests.rows(connection))
        quests.end(connection, essay[0]['id'], 'done', 'Handed in.')
        # Seven weeks in, that week's essay and the midterm with a week's notice; both left to lapse.
        later = datetime(2009, 10, 21, 12)
        institutions.advance(connection, later - timedelta(hours=1), later, 'kingswood', 'pell-provisions', 'now')
        midterm = next(item for item in quests.rows(connection, 'open') if item['title'] == 'Midterm examination')
        assert midterm['due_at'] == '2009-10-27T09:00' and midterm['kind'] == 'job'
        quests.check(connection, datetime(2009, 10, 28), 'now')
        assert factions.standing(connection, 'cyrel-timber-guild') == -2
        marks = connection.execute('SELECT title, weight, mark FROM story_grades ORDER BY id').fetchall()
        assert [tuple(row) for row in marks][:1] == [('A weekly essay', 1, 90)]
        assert ('Midterm examination', 3, 0) in [tuple(row) for row in marks]


def test_the_narrator_hears_today_and_the_grades_and_a_new_character_is_enrolled(client, app, school):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'persona': {'name': 'Wren'}, 'ruleset': 'narrative'}))
    with app.state.database.connect(write=True) as connection:
        assert [row['classes'] for row in institutions.enrolled(connection)] == [['letters', 'sums']]
        connection.execute("INSERT INTO story_grades (institution_id, term, title, weight, mark) VALUES "
                           "('kingswood-academy', 'Fall term 2009', 'An essay', 1, 85)")
        text = institutions.prompt_text(connection, MONDAY)
    assert 'enrolled at Kingswood Academy (Fall term 2009). Today: Letters at 10:00.' in text
    assert 'Grades so far: B (85)' in text and 'never invent another' in text
    journal = ok(client.delete('/api/story/institutions/kingswood-academy'))
    assert journal['institutions'] == []
    joined = ok(client.put('/api/story/institutions/kingswood-academy', json={'classes': ['fencing', 'nonsense']}))
    assert joined['institutions'][0]['classes'] == [{'id': 'fencing', 'name': 'Fencing'}]
    assert client.put('/api/story/institutions/nowhere', json={}).status_code == 404


def test_a_world_can_start_its_campaigns_on_its_own_date(client, app, school, monkeypatch):
    monkeypatch.setattr(tiers, 'track', lambda world: {'track': 'renown', 'name': 'Renown', 'arc': 'classic',
                                                        'pace': 'steady', 'words': ['a'] * 5, 'start': '2009-09-07T08:00'})
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'persona': {'name': 'Wren'}, 'ruleset': 'narrative'}))
    with app.state.database.connect() as connection:
        assert story_clock.now(connection, app.state.database.clock) == datetime(2009, 9, 7, 8)
    assert ok(client.get('/api/story/journal'))['institutions'][0]['term'] == 'Fall term 2009'

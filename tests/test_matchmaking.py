"""Ranking, visibility and API regressions for matchmaking integration."""

import math
from uuid import uuid4

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.exceptions import NotFound

from starup_backend.common.roles import Role
from starup_backend.demands.models import Category, Demand
from starup_backend.matchmaking import (
    calculate_match_score,
    get_investor_traction_vitrine,
    get_matchmaking_for_demand,
    get_recommended_demands_for_startup,
)
from starup_backend.reviews.models import Review
from starup_backend.solutions.models import Solution
from tests.factories import (
    CategoryFactory,
    ClientFactory,
    DemandFactory,
    InvestorFactory,
    SolutionFactory,
    StartupFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("category_match", "rating", "completed", "expected_score", "has_seal"),
    [
        (True, 5.0, 3, 96.7, True),
        (True, 4.0, 1, 73.9, True),
        (True, None, 0, 52.5, False),
        (False, None, 0, 32.5, False),
        (True, 5.0, 0, 70.0, False),
        (True, 3.0, 1, 66.9, False),
    ],
)
def test_score_formula(category_match, rating, completed, expected_score, has_seal):
    result = calculate_match_score(category_match, rating, completed)
    assert result["score"] == expected_score
    assert result["has_seal"] is has_seal
    assert result["c_setor"] == (1.0 if category_match else 0.2)
    assert result["t_maturidade"] == round(1 - math.exp(-0.5 * completed), 2)
    for name in ("c_setor", "m_auditoria", "e_economia", "t_maturidade"):
        assert 0.0 <= result[name] <= 1.0


def test_completed_work_improves_score_with_diminishing_maturity():
    scores = [calculate_match_score(True, 5.0, number) for number in range(100)]
    assert all(0.0 <= row["score"] <= 100.0 for row in scores)
    assert [row["score"] for row in scores] == sorted(row["score"] for row in scores)
    assert scores[-1]["score"] == 100.0
    assert scores[3]["e_economia"] == scores[-1]["e_economia"] == 1.0


@pytest.mark.parametrize(
    ("startup_category", "slug", "name", "matches"),
    [
        ("LOGISTICA", "logistics", "Logística", True),
        ("FINANCAS", "finance", "Finanças", True),
        ("  LOGISTICS  ", "logistics", "Logística", True),
        ("logística", "logistics", "Logística", True),
        ("tecnologia", "technology", "Tecnologia", True),
        ("agro", "agroindustria", "Agroindústria", False),
        ("financeira", "finance", "Finanças", False),
        ("", "logistics", "Logística", False),
        ("logistics", "", "Saúde", False),
    ],
)
def test_category_normalization_in_both_directions(
    startup_category, slug, name, matches
):
    category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
    demand = DemandFactory(category=category)
    startup = StartupFactory(category=startup_category)
    expected = 1.0 if matches else 0.2
    result = get_matchmaking_for_demand(demand.id)
    assert result[0]["details"]["c_setor"] == expected
    recommendations = get_recommended_demands_for_startup(startup.user)
    assert recommendations[0]["demand_id"] == demand.id
    assert recommendations[0]["details"]["c_setor"] == expected


def test_matching_category_ranks_above_unrelated_startup():
    demand = DemandFactory(category=CategoryFactory(slug="health", name="Saúde"))
    unrelated = StartupFactory(category="finance", name="A unrelated startup")
    matching = StartupFactory(category="saude", name="Z matching startup")
    matches = get_matchmaking_for_demand(demand.id)
    assert [row["startup_id"] for row in matches] == [matching.id, unrelated.id]
    assert matches[0]["score"] > matches[1]["score"]


@pytest.mark.parametrize("selector", [get_investor_traction_vitrine, "demand"])
def test_rankings_exclude_inactive_and_wrong_role_profiles(selector):
    active = StartupFactory()
    StartupFactory(user__ativo=False)
    StartupFactory(user__perfil_ativo=Role.CLIENT)
    if selector == "demand":
        results = get_matchmaking_for_demand(DemandFactory().id)
    else:
        results = selector()
    assert [row["startup_id"] for row in results] == [active.id]


def test_completed_statistics_and_seal_are_aggregated_without_private_text():
    startup = StartupFactory()
    for rating in (3, 5):
        solution = SolutionFactory(
            startup=startup,
            status=Solution.Status.COMPLETED,
            demand__visibility=Demand.Visibility.PRIVATE,
        )
        Review.objects.create(solution=solution, rating=rating)
    pending = SolutionFactory(startup=startup)
    # Corrupt/legacy rows must not count as verified client completions.
    Review.objects.create(solution=pending, rating=1)
    result = get_investor_traction_vitrine()[0]
    assert result["average_rating"] == 4.0
    assert result["review_count"] == result["completed_tests"] == 2
    assert result["has_seal"] is True
    assert "Private proposal" not in str(result)
    assert "Private legal name" not in str(result)
    assert str(pending.demand.id) not in str(result)


def test_ranking_ties_use_name_then_id():
    late = StartupFactory(name="Zulu")
    early = StartupFactory(name="Alpha")
    tied = StartupFactory(name="Alpha")
    expected = [row.id for row in sorted([early, tied], key=lambda row: str(row.id))]
    expected.append(late.id)
    assert [row["startup_id"] for row in get_investor_traction_vitrine()] == expected
    assert [
        row["startup_id"] for row in get_matchmaking_for_demand(DemandFactory().id)
    ] == expected


def test_missing_or_malformed_demand_is_not_found():
    for demand_id in (uuid4(), "not-a-uuid", None):
        with pytest.raises(NotFound):
            get_matchmaking_for_demand(demand_id)


def test_private_demand_matches_are_scoped_like_demand_detail(api_client):
    demand = DemandFactory(visibility=Demand.Visibility.PRIVATE)
    outsider = StartupFactory()
    for actor in (None, ClientFactory().user, outsider.user, InvestorFactory().user):
        api_client.force_authenticate(actor)
        response = api_client.get(f"/api/v1/matchmaking/demands/{demand.id}/")
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    api_client.force_authenticate(demand.client.user)
    response = api_client.get(f"/api/v1/matchmaking/demands/{demand.id}/")
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


@pytest.mark.parametrize(
    "status", ["ACCEPTED", "IN_PROGRESS", "DELIVERED", "COMPLETED"]
)
def test_selected_startup_can_read_private_demand_matches(api_client, status):
    solution = SolutionFactory(demand__visibility="PRIVATE", status=status)
    api_client.force_authenticate(solution.startup.user)
    response = api_client.get(f"/api/v1/matchmaking/demands/{solution.demand_id}/")
    assert response.status_code == 200


@pytest.mark.parametrize("status", ["SUBMITTED", "REJECTED", "WITHDRAWN"])
def test_unselected_startup_cannot_read_private_demand_matches(api_client, status):
    solution = SolutionFactory(demand__visibility="PRIVATE", status=status)
    api_client.force_authenticate(solution.startup.user)
    assert (
        api_client.get(f"/api/v1/matchmaking/demands/{solution.demand_id}/").status_code
        == 404
    )


@pytest.mark.parametrize("changes", [{"ativo": False}, {"perfil_ativo": Role.STARTUP}])
def test_public_matches_for_hidden_client_are_not_found(api_client, changes):
    demand = DemandFactory()
    for field, value in changes.items():
        setattr(demand.client.user, field, value)
    demand.client.user.save(update_fields=list(changes))
    assert (
        api_client.get(f"/api/v1/matchmaking/demands/{demand.id}/").status_code == 404
    )


def test_recommendations_only_include_eligible_public_open_demands():
    startup = StartupFactory(category="logistics")
    category = CategoryFactory(slug="logistics-fleet", name="Logística de frota")
    best = DemandFactory(category=category)
    other = DemandFactory()
    startup.category = category.slug
    startup.save(update_fields=["category"])
    DemandFactory(visibility="PRIVATE")
    DemandFactory(status="CANCELLED")
    DemandFactory(status="IN_PROGRESS")
    DemandFactory(status="COMPLETED", completed_at=timezone.now())
    DemandFactory(client__user__ativo=False)
    DemandFactory(client__user__perfil_ativo=Role.STARTUP)
    for status in Solution.Status.values:
        SolutionFactory(startup=startup, status=status)
    recommendations = get_recommended_demands_for_startup(startup.user)
    assert [row["demand_id"] for row in recommendations] == [best.id, other.id]
    assert recommendations[0]["score"] > recommendations[1]["score"]


def test_equal_recommendations_prefer_recent_demands():
    startup = StartupFactory()
    old, new = DemandFactory(), DemandFactory()
    assert [
        row["demand_id"] for row in get_recommended_demands_for_startup(startup.user)
    ] == [new.id, old.id]


@pytest.mark.parametrize("role", [Role.CLIENT, Role.INVESTOR])
def test_recommendations_deny_other_roles_even_with_startup_profile(api_client, role):
    startup = StartupFactory(user__perfil_ativo=role)
    api_client.force_authenticate(startup.user)
    assert api_client.get("/api/v1/matchmaking/recommended-demands/").status_code == 403
    assert get_recommended_demands_for_startup(startup.user) == []


def test_recommendations_require_active_authenticated_startup(api_client):
    url = "/api/v1/matchmaking/recommended-demands/"
    assert api_client.get(url).status_code == 403
    assert get_recommended_demands_for_startup(AnonymousUser()) == []
    inactive = StartupFactory(user__ativo=False)
    api_client.force_authenticate(inactive.user)
    assert api_client.get(url).status_code == 403
    assert get_recommended_demands_for_startup(inactive.user) == []
    no_profile = UserFactory(perfil_ativo=Role.STARTUP)
    api_client.force_authenticate(no_profile)
    assert api_client.get(url).json() == []


def test_recommendations_api_serializes_ids_dates_and_private_cache(api_client):
    startup, demand = StartupFactory(), DemandFactory()
    api_client.force_authenticate(startup.user)
    response = api_client.get("/api/v1/matchmaking/recommended-demands/")
    assert response.status_code == 200
    result = response.json()[0]
    assert result["demand_id"] == str(demand.id)
    assert result["category_id"] == str(demand.category_id)
    assert result["created_at"].endswith("Z")
    assert result["details"]["score"] == result["score"]
    assert "no-store" in response["Cache-Control"]


@pytest.mark.parametrize(
    "min_score", ["nope", "", "nan", "NaN", "inf", "-inf", "1e999", "-1", "101"]
)
def test_showcase_rejects_invalid_scores(api_client, min_score):
    response = api_client.get(
        "/api/v1/matchmaking/traction-showcase/", {"min_score": min_score}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"
    assert "min_score" in response.json()["fields"]


def test_showcase_default_and_score_filter(api_client):
    startup = StartupFactory()
    url = "/api/v1/matchmaking/traction-showcase/"
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.json()[0]["startup_id"] == str(startup.id)
    assert response.json()[0]["score"] == 52.5
    assert api_client.get(url, {"min_score": "52.5"}).json() == response.json()
    assert api_client.get(url, {"min_score": "52.6"}).json() == []
    assert api_client.get(url, {"min_score": "100"}).json() == []


def test_selectors_have_constant_query_counts(django_assert_num_queries):
    demand, startup = DemandFactory(), StartupFactory()
    StartupFactory.create_batch(5)
    DemandFactory.create_batch(5)
    with django_assert_num_queries(2):
        assert len(get_matchmaking_for_demand(demand.id)) == 6
    with django_assert_num_queries(2):
        assert len(get_recommended_demands_for_startup(startup.user)) == 6
    with django_assert_num_queries(1):
        assert len(get_investor_traction_vitrine()) == 6

"""Tests for the matchmaking system according to documented formulas."""

import pytest
from starup_backend.matchmaking import (
    calculate_match_score,
    get_investor_traction_vitrine,
    get_matchmaking_for_demand,
    get_recommended_demands_for_startup,
)
from starup_backend.demands.models import Demand, Category
from starup_backend.profiles.models import StartupProfile, ClientProfile
from starup_backend.solutions.models import Solution
from starup_backend.reviews.models import Review
from starup_backend.usuarios.models import Usuario


@pytest.mark.django_db
def test_calculate_match_score_formula():
    # 1. High match: Category matches, high rating, multiple completed tests
    result = calculate_match_score(category_match=True, average_rating=5.0, completed_tests=3)
    assert result["score"] >= 85.0
    assert result["has_seal"] is True
    assert result["c_setor"] == 1.0

    # 2. Low match: Category mismatch, no reviews, zero completed tests
    result_low = calculate_match_score(category_match=False, average_rating=None, completed_tests=0)
    assert result_low["score"] < 50.0
    assert result_low["has_seal"] is False
    assert result_low["c_setor"] == 0.2


@pytest.mark.django_db
def test_demand_matchmaking_ranking():
    cat = Category.objects.create(name="Logística", slug="logistica")
    other_cat = Category.objects.create(name="Finanças", slug="financas")

    # Client and Demand
    u_client = Usuario.objects.create(
        email="client@test.com",
        perfil_ativo="EMPRESA_CLIENTE",
        termo_privacidade_aceito=True,
    )
    client_prof = ClientProfile.objects.create(
        user=u_client,
        person_type="PJ",
        document="12345678000199",
        display_name="Empresa Cliente",
    )
    demand = Demand.objects.create(
        client=client_prof,
        category=cat,
        title="Otimização de rotas",
        description="Reduzir custo de frete",
    )

    # Startup 1: Matches category
    u1 = Usuario.objects.create(email="s1@test.com", perfil_ativo="STARTUP", termo_privacidade_aceito=True)
    s1 = StartupProfile.objects.create(user=u1, name="LogTech", category="logistica", description="Entrega rápida")

    # Startup 2: Different category
    u2 = Usuario.objects.create(email="s2@test.com", perfil_ativo="STARTUP", termo_privacidade_aceito=True)
    s2 = StartupProfile.objects.create(user=u2, name="FinTech", category="financas", description="Contabilidade")

    # Call matchmaking
    matches = get_matchmaking_for_demand(demand.id)
    assert len(matches) >= 2
    # First match should be s1 due to category alignment
    assert matches[0]["startup_id"] == s1.id
    assert matches[0]["score"] > matches[1]["score"]


@pytest.mark.django_db
def test_recommended_demands_for_startup():
    cat1 = Category.objects.create(name="Tecnologia", slug="tecnologia")
    cat2 = Category.objects.create(name="Vendas", slug="vendas")

    u_client = Usuario.objects.create(
        email="client2@test.com",
        perfil_ativo="EMPRESA_CLIENTE",
        termo_privacidade_aceito=True,
    )
    client_prof = ClientProfile.objects.create(
        user=u_client,
        person_type="PJ",
        document="98765432000188",
        display_name="Empresa Cliente 2",
    )
    d1 = Demand.objects.create(client=client_prof, category=cat1, title="App Mobile", description="App")
    d2 = Demand.objects.create(client=client_prof, category=cat2, title="Campanha", description="Vendas")

    # Startup in Tecnologia
    u_startup = Usuario.objects.create(email="tech@test.com", perfil_ativo="STARTUP", termo_privacidade_aceito=True)
    StartupProfile.objects.create(user=u_startup, name="TechSoft", category="tecnologia")

    recs = get_recommended_demands_for_startup(u_startup)
    assert len(recs) == 2
    # The first recommendation should be d1 (category match)
    assert recs[0]["demand_id"] == d1.id
    assert recs[0]["score"] > recs[1]["score"]


@pytest.mark.django_db
def test_matchmaking_endpoints_api(client):
    cat = Category.objects.create(name="Operações", slug="operacoes")
    u_client = Usuario.objects.create(
        email="c3@test.com",
        perfil_ativo="EMPRESA_CLIENTE",
        termo_privacidade_aceito=True,
    )
    client_prof = ClientProfile.objects.create(
        user=u_client,
        person_type="PJ",
        document="11223344000155",
        display_name="Empresa C3",
    )
    demand = Demand.objects.create(client=client_prof, category=cat, title="Demanda Teste", description="Desc")

    resp = client.get(f"/api/v1/matchmaking/demands/{demand.id}/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    resp_vitrine = client.get("/api/v1/matchmaking/traction-showcase/")
    assert resp_vitrine.status_code == 200
    assert isinstance(resp_vitrine.json(), list)

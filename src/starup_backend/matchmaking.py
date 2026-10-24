"""Matchmaking selectors based on completed work and client review aggregates.

Documented formula from docs/modelagem_dados_e_arquitetura_starup.md (Section 5.3):
    S_match = w1 * C_setor + w2 * M_auditoria + w3 * E_economia + w4 * T_maturidade

Weights:
    w1 = 0.25 (Sector compatibility)
    w2 = 0.35 (Client review quality: average rating / 5.0)
    w3 = 0.25 (Experience proxy derived from completed deliveries)
    w4 = 0.15 (Maturity / completed tests history: 1 - exp(-0.5 * N))

The resulting score is normalized on a scale of 0 to 100. This MVP uses completed
deliveries as a proxy for impact: financial savings and independent audits are
not collected, so these scores must not be presented as audited financial data.
"""

import math
from typing import Any
from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound

from starup_backend.common.roles import Role
from starup_backend.demands.models import Demand
from starup_backend.demands.selectors import visible_demands
from starup_backend.profiles.models import StartupProfile
from starup_backend.solutions.models import Solution


def _category_matches(startup_category: str, slug: str, name: str) -> bool:
    """Compare canonical labels without treating partial words as sectors."""
    category = slugify(startup_category)
    return bool(category) and category in {slugify(slug), slugify(name)}


def _startup_statistics():
    """Compute statistics in one query, including only confirmed completions."""
    completed = Q(solutions__status=Solution.Status.COMPLETED)
    return StartupProfile.objects.annotate(
        average_rating=Avg("solutions__review__rating", filter=completed),
        review_count=Count("solutions__review", filter=completed, distinct=True),
        completed_count=Count("solutions", filter=completed, distinct=True),
    )


def _ranked_startups():
    return (
        _startup_statistics()
        .filter(user__ativo=True, user__perfil_ativo=Role.STARTUP)
        .values(
            "id",
            "name",
            "description",
            "website",
            "category",
            "average_rating",
            "review_count",
            "completed_count",
        )
    )


def _startup_result(startup, metrics):
    return {
        "startup_id": startup["id"],
        "startup_name": startup["name"],
        "startup_description": startup["description"],
        "startup_website": startup["website"],
        "startup_category": startup["category"],
        "average_rating": startup["average_rating"],
        "review_count": startup["review_count"],
        "completed_tests": startup["completed_count"],
        "has_seal": metrics["has_seal"],
        "score": metrics["score"],
        "details": metrics,
    }


def _startup_sort_key(item):
    return (
        -item["score"],
        -(item["average_rating"] or 0),
        -item["completed_tests"],
        item["startup_name"].casefold(),
        str(item["startup_id"]),
    )


def calculate_match_score(
    category_match: bool,
    average_rating: float | None,
    completed_tests: int,
) -> dict[str, Any]:
    """Calculate the S_match score and its breakdown according to the project model."""
    # 1. C_setor in [0, 1]
    c_setor = 1.0 if category_match else 0.2

    # 2. M_auditoria in [0, 1]
    # Based on average review score (1.0 to 5.0)
    if average_rating and average_rating > 0:
        # Base factor from 1.0 to 5.0 scale
        m_auditoria = min(1.0, max(0.0, float(average_rating) / 5.0))
        # Positive client validation requires completed work and a rating >= 4.
        has_seal = average_rating >= 4.0 and completed_tests >= 1
    else:
        # Default baseline for startups without reviews yet (neutral 0.5)
        m_auditoria = 0.5
        has_seal = False

    # 3. E_economia in [0, 1]
    # In MVP, estimated from track of completed delivered solutions
    # scaled up to 1.0 with at least 3 completed tests
    e_economia = min(1.0, 0.4 + (0.2 * min(completed_tests, 3)))

    # 4. T_maturidade in [0, 1]: 1 - exp(-0.5 * N)
    t_maturidade = 1.0 - math.exp(-0.5 * completed_tests)

    # Weights: w1=0.25, w2=0.35, w3=0.25, w4=0.15
    raw_score = (
        (0.25 * c_setor)
        + (0.35 * m_auditoria)
        + (0.25 * e_economia)
        + (0.15 * t_maturidade)
    )

    # Score from 0 to 100 rounded to 1 decimal place
    score = round(max(0.0, min(100.0, raw_score * 100)), 1)

    return {
        "score": score,
        "has_seal": has_seal,
        "c_setor": round(c_setor, 2),
        "m_auditoria": round(m_auditoria, 2),
        "e_economia": round(e_economia, 2),
        "t_maturidade": round(t_maturidade, 2),
    }


def get_matchmaking_for_demand(
    demand_id: str | UUID, *, user=None
) -> list[dict[str, Any]]:
    """Rank startups for a visible demand by sector and completed work."""
    try:
        demand = (
            visible_demands(user if user is not None else AnonymousUser())
            .select_related("category")
            .get(id=demand_id)
        )
    except (Demand.DoesNotExist, ValidationError, ValueError, TypeError) as exc:
        raise NotFound() from exc

    results = []
    for s in _ranked_startups():
        category_match = _category_matches(
            s["category"], demand.category.slug, demand.category.name
        )

        metrics = calculate_match_score(
            category_match=category_match,
            average_rating=s.get("average_rating"),
            completed_tests=s.get("completed_count") or 0,
        )

        results.append(_startup_result(s, metrics))

    # Stable ordering keeps equally ranked cards from changing between requests.
    results.sort(key=_startup_sort_key)
    return results


def get_recommended_demands_for_startup(user) -> list[dict[str, Any]]:
    """Rank available public demands for a startup by sector compatibility."""
    if not user.is_authenticated or not user.ativo or user.perfil_ativo != Role.STARTUP:
        return []
    try:
        startup_profile = _startup_statistics().get(user=user)
    except StartupProfile.DoesNotExist:
        return []

    avg_rating = startup_profile.average_rating
    completed_tests = startup_profile.completed_count

    open_demands = (
        Demand.objects.filter(
            status=Demand.Status.OPEN,
            visibility=Demand.Visibility.PUBLIC,
            client__user__ativo=True,
            client__user__perfil_ativo=Role.CLIENT,
        )
        .exclude(solutions__startup=startup_profile)
        .values(
            "id",
            "title",
            "description",
            "category_id",
            "category__slug",
            "category__name",
            "created_at",
        )
        .order_by("-created_at")
    )

    results = []
    for d in open_demands:
        category_match = _category_matches(
            startup_profile.category, d["category__slug"], d["category__name"]
        )

        metrics = calculate_match_score(
            category_match=category_match,
            average_rating=avg_rating,
            completed_tests=completed_tests,
        )

        results.append(
            {
                "demand_id": d["id"],
                "title": d["title"],
                "description": d["description"],
                "category_id": d["category_id"],
                "category_name": d["category__name"],
                "category_slug": d["category__slug"],
                "created_at": d["created_at"],
                "score": metrics["score"],
                "has_seal": metrics["has_seal"],
                "details": metrics,
            }
        )

    results.sort(
        key=lambda item: (
            -item["score"],
            -item["created_at"].timestamp(),
            str(item["demand_id"]),
        ),
    )
    return results


def get_investor_traction_vitrine(min_score: float = 0.0) -> list[dict[str, Any]]:
    """Return top startups ranked by practical traction score S_match.

    The public directory includes startups without completed work. Consumers may
    request a minimum score; the seal separately identifies reviewed completions.
    """
    results = []
    for s in _ranked_startups():
        # The broad directory has no target sector, so category is held constant.
        metrics = calculate_match_score(
            category_match=True,
            average_rating=s.get("average_rating"),
            completed_tests=s.get("completed_count") or 0,
        )

        results.append(_startup_result(s, metrics))

    results.sort(key=_startup_sort_key)

    if min_score > 0:
        return [r for r in results if r["score"] >= min_score]
    return results

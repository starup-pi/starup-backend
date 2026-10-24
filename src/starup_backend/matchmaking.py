"""Matchmaking algorithm and recommendation selectors based on audited practical traction.

Documented formula from docs/modelagem_dados_e_arquitetura_starup.md (Section 5.3):
    S_match = w1 * C_setor + w2 * M_auditoria + w3 * E_economia + w4 * T_maturidade

Weights:
    w1 = 0.25 (Sector compatibility)
    w2 = 0.35 (Audit & Review quality: average rating / 5.0)
    w3 = 0.25 (Real economic/impact factor, approximated from completed delivery track)
    w4 = 0.15 (Maturity / completed tests history: 1 - exp(-0.5 * N))

The resulting score is normalized on a scale of 0 to 100.
"""

import math
from typing import Any

from django.db.models import Avg, Count, Q

from starup_backend.common.roles import Role
from starup_backend.demands.models import Demand
from starup_backend.profiles.models import StartupProfile


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
        # Audited seal multiplier: if rated >= 4.0, full confidence
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


def get_matchmaking_for_demand(demand_id: str | Any) -> list[dict[str, Any]]:
    """Rank startups for a given demand based on sector alignment and practical traction."""
    try:
        demand = Demand.objects.select_related("category").get(id=demand_id)
    except (Demand.DoesNotExist, ValueError):
        return []

    demand_category_slug = (demand.category.slug or "").strip().lower()
    demand_category_name = (demand.category.name or "").strip().lower()

    # Query active startups with aggregated review stats and completed solutions count
    startups = (
        StartupProfile.objects.filter(
            user__ativo=True,
            user__perfil_ativo=Role.STARTUP,
        )
        .annotate(
            average_rating=Avg("solutions__review__rating"),
            review_count=Count("solutions__review", distinct=True),
            completed_count=Count(
                "solutions",
                filter=Q(solutions__status="COMPLETED"),
                distinct=True,
            ),
        )
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

    results = []
    for s in startups:
        startup_cat = (s.get("category") or "").strip().lower()
        # Direct match if category equals demand slug or demand name
        category_match = (
            bool(startup_cat)
            and (
                startup_cat == demand_category_slug
                or startup_cat == demand_category_name
                or startup_cat in demand_category_slug
                or demand_category_slug in startup_cat
            )
        )

        metrics = calculate_match_score(
            category_match=category_match,
            average_rating=s.get("average_rating"),
            completed_tests=s.get("completed_count") or 0,
        )

        results.append({
            "startup_id": s["id"],
            "startup_name": s["name"],
            "startup_description": s["description"],
            "startup_website": s["website"],
            "startup_category": s["category"],
            "average_rating": s["average_rating"],
            "review_count": s["review_count"],
            "completed_tests": s["completed_count"],
            "has_seal": metrics["has_seal"],
            "score": metrics["score"],
            "details": metrics,
        })

    # Sort descending by match score, then rating, then name
    results.sort(
        key=lambda item: (
            item["score"],
            item["average_rating"] or 0,
            item["completed_tests"],
        ),
        reverse=True,
    )
    return results


def get_recommended_demands_for_startup(user) -> list[dict[str, Any]]:
    """Rank open public demands for a logged-in startup based on sector compatibility."""
    try:
        startup_profile = StartupProfile.objects.get(user=user)
    except StartupProfile.DoesNotExist:
        return []

    # Get startup metrics
    stats = (
        StartupProfile.objects.filter(id=startup_profile.id)
        .annotate(
            average_rating=Avg("solutions__review__rating"),
            completed_count=Count(
                "solutions",
                filter=Q(solutions__status="COMPLETED"),
                distinct=True,
            ),
        )
        .values("average_rating", "completed_count")
        .first()
    ) or {}

    startup_cat = (startup_profile.category or "").strip().lower()
    avg_rating = stats.get("average_rating")
    completed_tests = stats.get("completed_count") or 0

    open_demands = (
        Demand.objects.filter(
            status=Demand.Status.OPEN,
            visibility=Demand.Visibility.PUBLIC,
            client__user__ativo=True,
            client__user__perfil_ativo=Role.CLIENT,
        )
        .select_related("category")
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
        cat_slug = (d.get("category__slug") or "").strip().lower()
        cat_name = (d.get("category__name") or "").strip().lower()

        category_match = (
            bool(startup_cat)
            and (
                startup_cat == cat_slug
                or startup_cat == cat_name
                or startup_cat in cat_slug
                or cat_slug in startup_cat
            )
        )

        metrics = calculate_match_score(
            category_match=category_match,
            average_rating=avg_rating,
            completed_tests=completed_tests,
        )

        results.append({
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
        })

    results.sort(
        key=lambda item: (item["score"], item["created_at"]),
        reverse=True,
    )
    return results


def get_investor_traction_vitrine(min_score: float = 70.0) -> list[dict[str, Any]]:
    """Return top startups ranked by practical traction score S_match.

    Per Section 5.4 of docs:
    Startups with S_match >= 75 and at least 1 audited test with rating >= 4.0
    are prioritized in the investor showcase.
    """
    startups = (
        StartupProfile.objects.filter(
            user__ativo=True,
            user__perfil_ativo=Role.STARTUP,
        )
        .annotate(
            average_rating=Avg("solutions__review__rating"),
            review_count=Count("solutions__review", distinct=True),
            completed_count=Count(
                "solutions",
                filter=Q(solutions__status="COMPLETED"),
                distinct=True,
            ),
        )
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

    results = []
    for s in startups:
        # For investor vitrine, broad sector match is treated as verified
        metrics = calculate_match_score(
            category_match=True,
            average_rating=s.get("average_rating"),
            completed_tests=s.get("completed_count") or 0,
        )

        results.append({
            "startup_id": s["id"],
            "startup_name": s["name"],
            "startup_description": s["description"],
            "startup_website": s["website"],
            "startup_category": s["category"],
            "average_rating": s["average_rating"],
            "review_count": s["review_count"],
            "completed_tests": s["completed_count"],
            "has_seal": metrics["has_seal"],
            "score": metrics["score"],
            "details": metrics,
        })

    results.sort(
        key=lambda item: (
            item["score"],
            item["average_rating"] or 0,
            item["completed_tests"],
        ),
        reverse=True,
    )

    if min_score > 0:
        return [r for r in results if r["score"] >= min_score]
    return results

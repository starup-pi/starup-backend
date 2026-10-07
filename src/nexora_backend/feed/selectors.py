"""Batched feed hydration using only public field projections."""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from nexora_backend.common.roles import Role
from nexora_backend.demands.selectors import demand_projection
from nexora_backend.profiles.selectors import public_startups
from nexora_backend.reviews.models import Review

from .models import FeedPost


def public_posts():
    condition = (
        Q(
            kind="DEMAND",
            demand__visibility="PUBLIC",
            demand__client__user__ativo=True,
            demand__client__user__perfil_ativo=Role.CLIENT,
        )
        | Q(
            kind="REVIEWED_SOLUTION",
            review__solution__demand__visibility="PUBLIC",
            review__solution__demand__client__user__ativo=True,
            review__solution__demand__client__user__perfil_ativo=Role.CLIENT,
            review__solution__startup__user__ativo=True,
            review__solution__startup__user__perfil_ativo=Role.STARTUP,
        )
        | Q(
            kind="STARTUP",
            startup__user__ativo=True,
            startup__user__perfil_ativo=Role.STARTUP,
        )
    )
    return (
        FeedPost.objects.filter(condition)
        .values(
            "id",
            "position",
            "kind",
            "published_at",
            "demand_id",
            "review_id",
            "startup_id",
        )
        .order_by("-position")
    )


def hydrate_posts(posts: list[dict]) -> list[dict]:
    demand_ids = [post["demand_id"] for post in posts if post["demand_id"]]
    review_ids = [post["review_id"] for post in posts if post["review_id"]]
    startup_ids = [post["startup_id"] for post in posts if post["startup_id"]]
    demands = (
        {
            row["id"]: row
            for row in demand_projection(AnonymousUser()).filter(id__in=demand_ids)
        }
        if demand_ids
        else {}
    )
    startups = (
        {row["id"]: row for row in public_startups().filter(id__in=startup_ids)}
        if startup_ids
        else {}
    )
    reviews = (
        {
            row["id"]: row
            for row in Review.objects.filter(
                id__in=review_ids,
                solution__demand__visibility="PUBLIC",
                solution__demand__client__user__ativo=True,
                solution__demand__client__user__perfil_ativo=Role.CLIENT,
                solution__startup__user__ativo=True,
                solution__startup__user__perfil_ativo=Role.STARTUP,
            ).values(
                "id",
                "solution_id",
                "rating",
                "solution__startup_id",
                "solution__startup__name",
                "solution__demand_id",
                "solution__demand__title",
            )
        }
        if review_ids
        else {}
    )
    result = []
    for post in posts:
        if post["kind"] == "DEMAND":
            content = demands.get(post["demand_id"])
        elif post["kind"] == "STARTUP":
            content = startups.get(post["startup_id"])
        else:
            row = reviews.get(post["review_id"])
            content = (
                None
                if row is None
                else {
                    "review_id": row["id"],
                    "solution_id": row["solution_id"],
                    "rating": row["rating"],
                    "startup_id": row["solution__startup_id"],
                    "startup_name": row["solution__startup__name"],
                    "demand_id": row["solution__demand_id"],
                    "demand_title": row["solution__demand__title"],
                }
            )
        if content is not None:
            result.append(
                {
                    "id": post["id"],
                    "kind": post["kind"],
                    "published_at": post["published_at"],
                    "content": content,
                }
            )
    return result

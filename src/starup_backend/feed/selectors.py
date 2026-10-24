"""Batched feed hydration using only public field projections."""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from starup_backend.common.roles import Role
from starup_backend.demands.selectors import demand_projection
from starup_backend.profiles.selectors import public_startups
from starup_backend.reviews.models import Review

from .models import FeedPost


def public_posts(*, kind="ALL", tag=None):
    condition = (
        Q(
            kind="DEMAND",
            demand__visibility="PUBLIC",
            demand__client__user__ativo=True,
            demand__client__user__perfil_ativo=Role.CLIENT,
        )
        | Q(
            kind="REVIEWED_SOLUTION",
            review__solution__status="COMPLETED",
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
    posts = FeedPost.objects.filter(condition)
    if kind != "ALL":
        posts = posts.filter(kind=kind)
    if tag:
        posts = posts.filter(
            Q(kind="DEMAND", demand__tags__contains=[tag])
            | Q(
                kind="REVIEWED_SOLUTION",
                review__solution__demand__tags__contains=[tag],
            )
        )
    return posts.values(
        "id",
        "position",
        "kind",
        "published_at",
        "demand_id",
        "review_id",
        "startup_id",
    ).order_by("-position")


def hydrate_posts(posts: list[dict]) -> list[dict]:
    review_ids = [post["review_id"] for post in posts if post["review_id"]]
    startup_ids = [post["startup_id"] for post in posts if post["startup_id"]]
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
                solution__status="COMPLETED",
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
    demand_ids = {post["demand_id"] for post in posts if post["demand_id"]}
    demand_ids.update(row["solution__demand_id"] for row in reviews.values())
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
    result = []
    for post in posts:
        if post["kind"] == "DEMAND":
            content = demands.get(post["demand_id"])
        elif post["kind"] == "STARTUP":
            content = startups.get(post["startup_id"])
        else:
            row = reviews.get(post["review_id"])
            demand = demands.get(row["solution__demand_id"]) if row else None
            content = (
                None
                if row is None or demand is None
                else {
                    "review_id": row["id"],
                    "solution_id": row["solution_id"],
                    "rating": row["rating"],
                    "startup_id": row["solution__startup_id"],
                    "startup_name": row["solution__startup__name"],
                    "demand_id": row["solution__demand_id"],
                    "demand_title": row["solution__demand__title"],
                    "demand": demand,
                }
            )
        if content is not None:
            if post["kind"] == "DEMAND":
                author_type = "CLIENT"
                author_id = content["client_id"]
                author_name = content["client_name"]
            elif post["kind"] == "STARTUP":
                author_type = "STARTUP"
                author_id = content["id"]
                author_name = content["name"]
            else:
                author_type = "STARTUP"
                author_id = content["startup_id"]
                author_name = content["startup_name"]
            result.append(
                {
                    "id": post["id"],
                    "kind": post["kind"],
                    "published_at": post["published_at"],
                    "content": content,
                    "author_type": author_type,
                    "author_id": author_id,
                    "author_name": author_name,
                }
            )
    return result

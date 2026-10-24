"""Typed public feed representations match the OpenAPI discriminator."""

from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, serializers
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny

from starup_backend.common.serializers import StrictSerializer
from starup_backend.demands.serializers import DemandImageSerializer, DemandSerializer
from starup_backend.profiles.serializers import PublicStartupSerializer

from .models import FeedPost
from .selectors import hydrate_posts, public_posts


class FeedQuerySerializer(StrictSerializer):
    kind = serializers.ChoiceField(
        choices=["ALL", *FeedPost.Kind.values], default="ALL"
    )
    tag = serializers.CharField(max_length=30, required=False)
    cursor = serializers.CharField(max_length=1024, required=False)

    def validate_tag(self, value):
        value = value.lstrip("#").strip().casefold()
        if not value:
            raise serializers.ValidationError("Informe uma tag.")
        return value


class ReviewedSolutionContentSerializer(serializers.Serializer):
    review_id = serializers.UUIDField()
    solution_id = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    startup_id = serializers.UUIDField()
    startup_name = serializers.CharField()
    demand_id = serializers.UUIDField()
    demand_title = serializers.CharField()
    client_id = serializers.UUIDField()
    client_name = serializers.CharField()
    demand_description = serializers.CharField()
    category_name = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    images = DemandImageSerializer(many=True)

    def to_representation(self, instance):
        instance = dict(instance)
        # Reuse the public API projection rather than duplicating aliases or
        # accidentally serializing a client/user model in the feed.
        demand = DemandSerializer(instance.pop("demand")).data
        instance.update(
            client_id=demand["client_id"],
            client_name=demand["client_name"],
            demand_description=demand["description"],
            category_name=demand["category_name"],
            tags=demand["tags"],
            images=demand["images"],
        )
        return super().to_representation(instance)


class FeedSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    published_at = serializers.DateTimeField()
    author_type = serializers.ChoiceField(choices=["CLIENT", "STARTUP"])
    author_id = serializers.UUIDField()
    author_name = serializers.CharField()
    content = serializers.DictField()

    def to_representation(self, instance):
        result = super().to_representation(instance)
        content_type = {
            "DEMAND": DemandSerializer,
            "STARTUP": PublicStartupSerializer,
            "REVIEWED_SOLUTION": ReviewedSolutionContentSerializer,
        }[instance["kind"]]
        result["content"] = content_type(instance["content"]).data
        return result


class DemandFeedSerializer(FeedSerializer):
    kind = serializers.ChoiceField(choices=["DEMAND"])
    content = DemandSerializer()


class StartupFeedSerializer(FeedSerializer):
    kind = serializers.ChoiceField(choices=["STARTUP"])
    content = PublicStartupSerializer()


class ReviewedSolutionFeedSerializer(FeedSerializer):
    kind = serializers.ChoiceField(choices=["REVIEWED_SOLUTION"])
    content = ReviewedSolutionContentSerializer()


class FeedPagination(CursorPagination):
    ordering = "-position"
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        parameters=[FeedQuerySerializer],
        responses=PolymorphicProxySerializer(
            component_name="FeedPost",
            serializers={
                "DEMAND": DemandFeedSerializer,
                "STARTUP": StartupFeedSerializer,
                "REVIEWED_SOLUTION": ReviewedSolutionFeedSerializer,
            },
            resource_type_field_name="kind",
            many=True,
        ),
    )
)
class FeedView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = FeedSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        query = FeedQuerySerializer(data=self.request.query_params.dict())
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        return public_posts(kind=filters["kind"], tag=filters.get("tag"))

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        data = self.get_serializer(hydrate_posts(page), many=True).data
        response = self.get_paginated_response(data)
        response.public_representation = True
        response["Cache-Control"] = "public, max-age=0, must-revalidate"
        return response

"""Typed public feed representations match the OpenAPI discriminator."""

from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, serializers
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny

from starup_backend.demands.serializers import DemandSerializer
from starup_backend.profiles.serializers import PublicStartupSerializer

from .selectors import hydrate_posts, public_posts


class ReviewedSolutionContentSerializer(serializers.Serializer):
    review_id = serializers.UUIDField()
    solution_id = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    startup_id = serializers.UUIDField()
    startup_name = serializers.CharField()
    demand_id = serializers.UUIDField()
    demand_title = serializers.CharField()


class FeedSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    published_at = serializers.DateTimeField()
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
        responses=PolymorphicProxySerializer(
            component_name="FeedPost",
            serializers={
                "DEMAND": DemandFeedSerializer,
                "STARTUP": StartupFeedSerializer,
                "REVIEWED_SOLUTION": ReviewedSolutionFeedSerializer,
            },
            resource_type_field_name="kind",
            many=True,
        )
    )
)
class FeedView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = FeedSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        return public_posts()

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        data = self.get_serializer(hydrate_posts(page), many=True).data
        response = self.get_paginated_response(data)
        response.public_representation = True
        response["Cache-Control"] = "public, max-age=0, must-revalidate"
        return response

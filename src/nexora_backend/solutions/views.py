"""Participant-scoped API and explicit transition endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nexora_backend.common.permissions import ParticipantWritePermission

from .models import SolutionStatusEvent
from .selectors import solution_projection
from .serializers import (
    SolutionCreateSerializer,
    SolutionSerializer,
    SolutionTransitionSerializer,
    StatusEventSerializer,
)
from .services import submit_solution, transition_solution


class SolutionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    lookup_value_converter = "uuid"
    permission_classes = [ParticipantWritePermission]
    serializer_class = SolutionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return solution_projection(self.request.user)

    @extend_schema(
        request=SolutionCreateSerializer, responses={201: SolutionSerializer}
    )
    def create(self, request):
        serializer = SolutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        solution = submit_solution(actor=request.user, **serializer.validated_data)
        return Response(
            SolutionSerializer(self.get_queryset().get(id=solution.id)).data, status=201
        )

    @extend_schema(request=SolutionTransitionSerializer, responses=SolutionSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        serializer = SolutionTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transition_solution(
            actor=request.user,
            solution_id=pk,
            target=serializer.validated_data["status"],
            delivery=serializer.validated_data.get("delivery", ""),
        )
        return Response(SolutionSerializer(self.get_object()).data)

    @extend_schema(responses=StatusEventSerializer(many=True))
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        solution = self.get_object()
        events = SolutionStatusEvent.objects.filter(solution_id=solution["id"]).values(
            "previous_status", "new_status", "created_at"
        )
        return Response(StatusEventSerializer(events, many=True).data)

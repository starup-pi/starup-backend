"""The sole review mutation confirms a delivered solution."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nexora_backend.common.permissions import ClientWritePermission

from .serializers import ReviewCreateSerializer, ReviewSerializer
from .services import review_solution


class ReviewCreateView(APIView):
    permission_classes = [IsAuthenticated, ClientWritePermission]

    @extend_schema(request=ReviewCreateSerializer, responses={201: ReviewSerializer})
    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = review_solution(actor=request.user, **serializer.validated_data)
        return Response(ReviewSerializer(review).data, status=201)

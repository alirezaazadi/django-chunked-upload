from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers
from .config import settings

__all__ = [
    'InitialUploadAPIView',
    'UploadAPIView',
]


def get_upload_response_serializer():
    if serializer_class := settings.RESPONSE_SERIALIZER:
        return serializer_class
    return serializers.UploadResponseSerializer


class InitialUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    model = None

    @staticmethod
    def get_serializer_class():
        if serializer_class := settings.INIT_SERIALIZER:
            return serializer_class
        return serializers.InitialUploadRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = InitialUploadAPIView.get_serializer_class()(
            model=self.model,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        file_model = serializer.save()

        serializer = get_upload_response_serializer()(file_model, model=self.model)
        return Response(serializer.data)


class UploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    model = None

    @staticmethod
    def get_serializer_class():
        if serializer_class := settings.UPLOAD_SERIALIZER:
            return serializer_class
        return serializers.UploadSerializer

    def post(self, request, *args, **kwargs):
        serializer = UploadAPIView.get_serializer_class()(
            model=self.model,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        file_model = serializer.save()

        serializer = get_upload_response_serializer()(file_model, model=self.model)
        return Response(serializer.data)

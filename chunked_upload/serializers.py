from django.core.files.base import ContentFile
from rest_framework import serializers

from .config import settings
from . import utils

__all__ = [
    'InitialUploadRequestSerializer',
    'UploadResponseSerializer',
    'UploadSerializer',

]


class InitialUploadRequestSerializer(serializers.Serializer):
    # if unique_id is not provided, the request is considered as a new upload request (initial upload); otherwise
    # it is considered as a resume upload request
    unique_id = serializers.UUIDField(required=False, allow_null=True)

    # if offset is not provided, the request is considered as a new upload request (initial upload); otherwise
    # it is considered as a resume upload request
    offset = serializers.IntegerField(min_value=0, required=False, allow_null=True)

    # these fields are required if unique_id is not provided (new upload request)
    file_size = serializers.IntegerField(min_value=0, required=False, source='original_file_size')
    file_name = serializers.CharField(max_length=512, required=False, source='original_file_name')

    # these fields are required if unique_id is provided (resume upload request). the hash function that was used
    # to calculate the hash of the file on the client side. it will be used to check if the file is corrupted or not.
    hash_function = serializers.CharField(max_length=8, default=settings.HASH_FUNCTION)

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        fields = [
            'unique_id',
            'offset',
            'user',
            'file_size',
            'file_name',
            'hash_function',
        ]

    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model')
        super().__init__(*args, **kwargs)

    @staticmethod
    def validate_file_name(value):
        # check if the file has an extension
        if '.' not in value:
            raise serializers.ValidationError('Invalid file name. File name must have an extension')

        # sanitize the file name. and remove any path separators
        value = utils.secure_filename(value)

        return value

    def validate_hash_function(self, value):
        if value not in self.model.HashFunction.values:
            raise serializers.ValidationError('Invalid hash function')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs.get('unique_id') is None:
            # if file_unique_identifier is not provided, file_size and file_hash must be provided
            attrs_required = [
                ('file_size', 'original_file_size'),
                ('file_name', 'original_file_name')
            ]
            errors = {}
            for attr in attrs_required:
                if attrs.get(attr[1]) is None:
                    errors[attr[0]] = ['This field is required']

            if errors:
                raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        # if file_unique_identifier is not provided, create a new one

        if (file_unique_identifier := validated_data.get('unique_id')) is None:

            user = validated_data.pop('user', None)

            # check if the original file size is greater than the maximum allowed file size
            max_file_size = validated_data.get('max_file_size') or settings.MAX_FILE_SIZE

            if max_file_size is not None and validated_data['original_file_size'] > max_file_size:
                raise serializers.ValidationError(f'File size is greater than the maximum allowed file size, '
                                                  f'{utils.human_readable_size(max_file_size)}.')

            file_model = self.model(
                **validated_data,
                chunk_size=settings.CHUNK_SIZE,
            )

            if user and user.is_authenticated:
                file_model.user = user

            file_model.save()

        else:
            # if file_unique_identifier is provided, check if it exists
            try:
                file_model = self.model.objects.get(unique_id=file_unique_identifier)
            except self.model.DoesNotExist:
                raise serializers.ValidationError('File does not exist')

        return file_model


class UploadResponseSerializer(serializers.ModelSerializer):
    class Meta:
        fields = [
            'unique_id',
            'offset',
            'chunk_size',
            'status',
            'original_file_size',
            'current_file_size',
            'hr_current_file_size',
            'hr_original_file_size',
            'last_calculated_hash',
            'retry_threshold',
        ]

        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model')
        super().__init__(*args, **kwargs)
        self.Meta.model = self.model


class UploadSerializer(serializers.Serializer):
    unique_id = serializers.UUIDField()
    offset = serializers.IntegerField(min_value=0)
    chunk_hash = serializers.CharField(max_length=256, required=True, allow_null=False, allow_blank=False)
    final_hash = serializers.CharField(max_length=256, required=False, allow_null=True, allow_blank=True)

    class Meta:
        fields = [
            'unique_id',
            'offset',
        ]

    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model')
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        try:
            file_model = self.model.objects.get(unique_id=attrs['unique_id'], status__in=[
                self.model.Status.UPLOADING,
                self.model.Status.INITIAL
            ])
        except self.model.DoesNotExist:
            raise serializers.ValidationError('File does not exist or not in a valid state')

        if file_model.offset != attrs['offset']:
            raise serializers.ValidationError('Offset does not match')

        attrs['file_model'] = file_model

        return attrs

    def create(self, validated_data):

        file = self.context['request'].FILES.get('file')

        if not file:
            raise serializers.ValidationError('File is required')

        file_model = validated_data['file_model']

        file_model.append_chunk(
            chunk=ContentFile(file.read(file_model.chunk_size), name=file_model.original_file_name),
            original_chunk_hash=validated_data['chunk_hash'],
            final_hash=validated_data.get('final_hash'),
        )

        return file_model

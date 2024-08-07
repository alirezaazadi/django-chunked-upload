import hashlib
import os
import time
import uuid

from django.contrib.auth import get_user_model
from django.contrib.postgres.indexes import HashIndex
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import utils
from .config import settings

HASH_FUNCTION_MAPPING = {
    'MD5': hashlib.md5,
    'SHA1': hashlib.sha1,
    'SHA256': hashlib.sha256,
    'SHA512': hashlib.sha512,
}

User = get_user_model()


def default_upload_to(instance, filename):
    if not settings.PRESERVE_FILE_NAME:
        # get file's extension from the filename
        ext = os.path.splitext(filename)[1]

        # create a new filename using the unique_id and the extension
        filename = str(instance.unique_id.hex) + ext

    if hasattr(instance, 'user') and instance.user is not None:
        # if the instance has a user field, use it to create the path
        return time.strftime(os.path.join(
            'uploads',
            str(instance.user.id),
            '%Y/%m/%d',
            filename)
        )

    # if the instance does not have a user field, create the path without the user id
    return time.strftime(
        os.path.join(
            'uploads',
            '%Y/%m/%d',
            filename
        )
    )


class ChunkedFileUpload(models.Model):
    class HashFunction(models.TextChoices):
        MD5 = 'MD5'
        SHA1 = 'SHA1'
        SHA256 = 'SHA256'
        SHA512 = 'SHA512'

    class Status(models.TextChoices):
        INITIAL = 'INITIAL'
        UPLOADING = 'UPLOADING'
        SUCCESSFUL = 'SUCCESSFUL'
        FAILED = 'FAILED'

    unique_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text='unique identifier for the file, to relate chunks to the file'
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.INITIAL,
        help_text='status of the file and uploading process'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text='user who uploaded the file'
    )

    file = models.FileField(
        upload_to=settings.UPLOAD_PATH_FUNCTION,
        storage=settings.STORAGE_CLASS,
        null=True,
        blank=True,
        help_text='file field to store the file parts and the final file'
    )

    original_file_name = models.CharField(
        max_length=512,
        help_text='original file name to rename it after a successful upload'
    )

    max_file_size = models.PositiveBigIntegerField(
        help_text='The maximum allowed size of the file in bytes',
        default=settings.MAX_FILE_SIZE,
        null=True,
        blank=True
    )

    chunk_size = models.PositiveBigIntegerField(
        default=settings.CHUNK_SIZE,
        help_text='chunk size in bytes'
    )
    offset = models.PositiveBigIntegerField(
        default=0,
        help_text='file offset'
    )

    original_file_size = models.PositiveBigIntegerField(
        editable=False,
        help_text='original on disk file size in bytes'
    )
    current_file_size = models.PositiveBigIntegerField(
        default=0,
        help_text='current size of the file on disk in bytes'
    )

    hash_function = models.CharField(
        max_length=8,
        choices=HashFunction.choices,
        default=HashFunction.MD5,
        editable=False,
        help_text='hash function used to calculate the hash of the file'
    )

    last_calculated_hash = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text='iterative hash of the file. it store the hash of the each chunk, and the last calculated hash'
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='error message in case of failure'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text='date and time when the initial request was received',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='date and time when the last chunk was received',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='date and time when the last chunk was received (in case of success or failure)',
    )

    retry_threshold = models.PositiveIntegerField(
        default=settings.RETRY_THRESHOLD,
        help_text='Number of remained times to retry the upload in case of failure'
    )

    class Meta:
        abstract = True
        ordering = ['completed_at', '-updated_at']
        indexes = [
            models.Index(fields=['unique_id', 'status'], name='unique_id_status_idx'),
            HashIndex(fields=['unique_id'], name='unique_id_hash_idx')
        ]

    def reset_retry_threshold(self):
        self.retry_threshold = settings.RETRY_THRESHOLD

    def calculate_hash(self, chunk, original_chunk_hash) -> [bool, str]:
        hash_function = HASH_FUNCTION_MAPPING.get(self.hash_function)
        chunk_hash = hash_function(chunk.read()).hexdigest()

        if original_chunk_hash != chunk_hash:
            return False, None, 'Sent chunk is corrupted. Please retry uploading the chunk.'

        _hash = chunk_hash

        if self.last_calculated_hash:
            _hash = hash_function(
                self.last_calculated_hash.encode() + chunk_hash.encode(),
                usedforsecurity=False
            ).hexdigest()

        return True, _hash, None

    def __append(self, chunk):

        # check if the storage is not set
        storage = self.file.storage

        if not storage:
            storage = default_storage

        with storage.open(self.file.name, 'ab') as file:
            file.write(chunk.read())

    def _raise_retry(self, error, user_message=None):
        if self.retry_threshold > 0:
            self.retry_threshold -= 1
            self.save()

            if user_message:
                error = user_message

            raise ValidationError({'message': error, 'left_retries': self.retry_threshold})
        else:
            self.status = self.Status.FAILED
            self.completed_at = timezone.now()
            self.error_message = error
            self.save()
            self.delete_file()
            raise ValidationError({'message': user_message})

    def append_chunk(self, chunk, original_chunk_hash: str, final_hash: str = None):
        """
        Append a chunk to the file
        :param final_hash:
        :param original_chunk_hash:
        :param chunk:
        :return:
        """

        if self.max_file_size is not None and self.current_file_size + len(chunk) > self.max_file_size:
            self.status = self.Status.FAILED
            self.completed_at = timezone.now()
            self.error_message = 'File size exceeded the maximum allowed size'
            self.save()

            raise ValidationError(self.error_message)

        ok, _hash, error = self.calculate_hash(chunk, original_chunk_hash)

        if not self.file:
            self.file = chunk
            if self.status == self.Status.INITIAL:
                self.status = self.Status.UPLOADING
        else:
            if not ok:
                self._raise_retry(error)

            try:
                self.__append(chunk)
            except Exception as e:  # noqa
                self._raise_retry(str(e), user_message='Failed to store the chunk. Please retry uploading the chunk.')
            self.reset_retry_threshold()

        self.offset += len(chunk)
        self.current_file_size = self.offset
        self.last_calculated_hash = _hash

        if self.current_file_size == self.original_file_size:
            if self.last_calculated_hash == final_hash:
                self.status = self.Status.SUCCESSFUL
            else:
                self.error_message = 'File is corrupted'
                self.status = self.Status.FAILED

            self.completed_at = timezone.now()

        elif self.current_file_size > self.original_file_size:
            self.error_message = 'File size exceeded the original file size'
            self.status = self.Status.FAILED
            self.completed_at = timezone.now()

        self.file.close()
        self.save()

        if self.error_message or self.status == self.Status.FAILED:
            self.delete_file()
            raise ValidationError({'message': self.error_message})

    def delete_file(self):

        if not settings.PRESERVE_FAILED_UPLOAD_FILE:
            if self.file:
                storage, path = self.file.storage, self.file.path

                if not storage:
                    storage = default_storage

                if storage.exists(path):
                    storage.delete(path)

            self.file = None

    @transaction.atomic
    def delete(self, delete_file=True, *args, **kwargs):
        super().delete(*args, **kwargs)
        if delete_file:
            self.delete_file()

    @property
    def hr_current_file_size(self):
        return utils.human_readable_size(self.current_file_size)

    @property
    def hr_original_file_size(self):
        return utils.human_readable_size(self.original_file_size)

    def __str__(self):
        return u'<%s - upload_id: %s - size: %s - status: %s>' % (
            self.original_file_name, self.unique_id, self.hr_current_file_size, self.status)

    def __repr__(self):
        return self.__str__()

django-chunked-upload
=====================

A simple Django app to allow users to upload large files to Django webserver through RESTful APIs by sending
the files in multiple chunks. It also supports resuming upload after a disconnection.

Installation
------------

.. code-block:: python

    INSTALLED_APPS = (
        # ...
        'chunked_upload',
    )

Typical usage
-------------

1. Inherit from ``ChunkedUploadFile`` model:

.. code-block:: python

    from chunked_upload.models import ChunkedUpload

    class MyChunkedUpload(ChunkedUpload):
        pass

2. Inherit from ``ChunkedUploadView`` view:

.. code-block:: python

    from chunked_upload.views import UploadAPIView, InitialUploadAPIView

    class MyChunkedUploadInitialView(InitialUploadAPIView):
        model = MyChunkedUpload

    class MyChunkedUploadAPIView(UploadAPIView):
        model = MyChunkedUpload

3. Add the URLs to your ``urls.py``:

.. code-block:: python

    urlpatterns = [
        # ...
        path('api/upload/init/', MyChunkedUploadInitialView.as_view(model=MyChunkedUpload), name='api_upload_init'),
        path('api/upload/', MyChunkedUploadAPIView.as_view(model=MyChunkedUpload), name='api_upload'),
    ]

Possible error responses:
~~~~~~~~~~~~~~~~~~~~~~~~~

Settings
--------

-   ``STORAGE_CLASS`` (default: `None`)

  Specifies the storage class to be used for storing the uploaded chunks.

-   ``CHUNK_SIZE`` (default: `64 * 10 ** 6`, which is 64 MB)

  Determines the size of each chunk in bytes.

-   ``MAX_BYTES`` (default: `None`)

    Specifies the maximum size of the uploaded file in bytes. If `None`, there is no limit.

-   ``UPLOAD_PATH_FUNCTION`` (default: `'chunked_upload.models.default_upload_to'`)

  Specifies the function to generate the upload path for storing the chunks.

-   ``HASH_FUNCTION`` (default: `'MD5'`)

  Specifies the hash function to be used for hashing the uploaded chunks. Options are `'MD5'`, `'SHA1'`, `'SHA256'`, `'SHA512'`.

-   ``PRESERVE_FILE_NAME`` (default: `True`)

  Boolean value indicating whether to preserve the original filename of the uploaded file.

-   ``PRESERVE_FAILED_UPLOAD_FILE`` (default: `False`)

-   ``RETRY_THRESHOLD`` (default: `2`)

    Specifies the number of times the client can retry uploading a chunk before set it its status to ``FAILED``.

-   ``INIT_SERIALIZER`` (default: `'chunked_upload.serializers.InitialUploadRequestSerializer'`)

  Specifies the serializer class used for handling the initial upload request.

-   ``UPLOAD_SERIALIZER`` (default: `'chunked_upload.serializers.UploadSerializer'`)

  Specifies the serializer class used for handling the chunked upload.

-   ``RESPONSE_SERIALIZER`` (default: `'chunked_upload.serializers.UploadResponseSerializer'`)

  Specifies the serializer class used for generating the upload response.

Note: These settings can be overridden in your Django project's settings file (`settings.py`) by adding a `CHUNKED_UPLOAD` dictionary and specifying the desired values.


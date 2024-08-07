from django.conf import settings as dj_settings
from django.core.signals import setting_changed
from django.utils.module_loading import import_string

DEFAULTS = {
    'STORAGE_CLASS': None,
    'CHUNK_SIZE': 64 * 10 ** 6,  # 64 MB
    'MAX_FILE_SIZE': None,  # In bytes. None means no limit
    'UPLOAD_PATH_FUNCTION': 'chunked_upload.models.default_upload_to',
    'HASH_FUNCTION': 'MD5',  # MD5, SHA1, SHA256, SHA512
    'PRESERVE_FILE_NAME': True,
    'PRESERVE_FAILED_UPLOAD_FILE': False,

    'RETRY_THRESHOLD': 2,

    'INIT_SERIALIZER': 'chunked_upload.serializers.InitialUploadRequestSerializer',
    'UPLOAD_SERIALIZER': 'chunked_upload.serializers.UploadSerializer',
    'RESPONSE_SERIALIZER': 'chunked_upload.serializers.UploadResponseSerializer',
}

DEPRECATED_SETTINGS = []  # deprecated settings go here


def is_callable(value):
    # check for callables, except types
    return callable(value) and not isinstance(value, type)


def is_import_string(value):
    # check for import strings
    return isinstance(value, str) and '.' in value


class Settings:

    def __init__(self):
        # try to get `CHUNKED_UPLOAD` dictionary from django.conf.settings. if not, use defaults
        self._user_settings = getattr(dj_settings, 'CHUNKED_UPLOAD', DEFAULTS)

    def __getattr__(self, name):
        if name not in DEFAULTS:
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (self.__class__.__name__, name))

        value = self.get_setting(name)

        if is_callable(value):
            value = value()

        elif is_import_string(value):
            try:
                value = import_string(value)
            except ImportError:
                pass

        return value

    def get_setting(self, setting):
        return self._user_settings.get(setting, DEFAULTS[setting])

    def change_setting(self, setting, value, enter, **kwargs):
        # ensure a valid app setting is being overridden
        if setting not in DEFAULTS:
            return

        # if exiting, delete value to repopulate
        if enter:
            self._user_settings[setting] = value
        else:
            self._user_settings.pop(setting, None)


settings = Settings()
setting_changed.connect(settings.change_setting)

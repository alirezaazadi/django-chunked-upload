import os
import re
import unicodedata

_filename_ascii_strip_re = re.compile(r"[^A-Za-z0-9_.-]")
_windows_device_files = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}


# This function is copied from werkzeug.utils.secure_filename:
# https://github.com/pallets/werkzeug/blob/2bcb43c3574de33b36174c6dc964182ccbc14a69/src/werkzeug/utils.py#L195
def secure_filename(filename: str) -> str:
    r"""Pass it a filename, and it will return a secure version of it.  This
    filename can then safely be stored on a regular file system and passed
    to: func:`os.path.join`.  The filename returned is an ASCII only string
    for maximum portability.

    On Windows systems, the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename('i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename.  It's your responsibility
    to ensure that the filename is unique and that you abort or
    generate a random filename if the function returned an empty one.

    .. versionadded:: 0.5

    :param filename: the filename to secure
    """
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    for sep in os.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")
    filename = str(_filename_ascii_strip_re.sub("", "_".join(filename.split()))).strip(
        "._"
    )

    # On nt a couple of special files are present in each folder.
    # We have to ensure that the target file is not such a filename.
    # In this case, we prepend an underline
    if (
            os.name == "nt"
            and filename
            and filename.split(".")[0].upper() in _windows_device_files
    ):
        filename = f"_{filename}"

    return filename


def human_readable_size(size: int) -> str:
    """
    convert a file size to a human-readable format.
    :param size: int - file size in bytes
    :return: str - human-readable file size
    """
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} YB"

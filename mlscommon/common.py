import hashlib
import librsync

def calculate_sha256(file_object):
    """ Return the sha256 hexdigest of file_object.

    file_object is a Django File Object
    """
    h = hashlib.sha256()
    for chunk in file_object.chunks():
        h.update(chunk)

    file_object.seek(0)

    return h.hexdigest()

def calculate_md5(file_object):
    """ Return the sha256 hexdigest of file_object.

    file_object is a Django File Object
    """
    h = hashlib.md5()
    for chunk in file_object.chunks():
        h.update(chunk)

    file_object.seek(0)

    return h.hexdigest()

def patch_file(source, delta):
    """ Source, delta, destination are django.core.files.File objects
    """

    f = librsync.PatchFile(source, delta)
    source.seek(0)
    delta.seek(0)
    return f

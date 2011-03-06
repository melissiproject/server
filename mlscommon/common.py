import hashlib
import librsync

from django.http import HttpResponse
from django.core.servers.basehttp import FileWrapper
from django.conf import settings

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

    f = librsync.PatchedFile(source, delta)
    source.seek(0)
    delta.seek(0)
    return f

def sendfile(gridfs_file, download_name):
    """ Input is gridfs file object """

    if getattr(settings,'SENDFILE',False):
        response = HttpResponse(content_type='application/octet-stream')
        response['X-Sendfile'] = gridfs_file._id
    else:
        wrapper = FileWrapper(gridfs_file)
        response = HttpResponse(wrapper, content_type='application/octet-stream')
        # required to prevent piston from converting to string the
        # response object
        response._is_string = True

    response['Content-Length'] = gridfs_file.length
    response['Content-Transfer-Encoding'] = 'binary'
    response['Content-Disposition'] = 'attachment; filename="%s";' % download_name

    return response


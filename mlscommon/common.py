import hashlib
import librsync

from django.http import HttpResponse
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

    f = librsync.PatchFile(source, delta)
    source.seek(0)
    delta.seek(0)
    return f



# Define file output iterator
def gridFSWrapper(filedata):
    # from http://d-w.me/blog/2010/2/22/13/
    # with additions

    # Until today, I had been using Django's FileWrapper class to
    # iterate over an open GridFS and yeild chunks to an HttpResponse
    # object, however I noticed that files over 8 KB were being
    # reiterated in the output.
    #
    # As far as I could fathom, the reason why this had been occurring is
    # because Django's FileWrapper class only reads 8 KB (default) chunks
    # per yield to the calling HttpResponse object, however it became
    # apparent to me that an open GridFile does not seek forward in the
    # file by the amount read in the previous yield, instead this has to
    # be done manually.
    #
    # I came up with the below function to use as a file wrapper for a
    # GridFile. It uses the chunk size set by GridFile.chunk_size (256 K
    # per yield for my files), although it can be set to somethink like
    # 8 KB (8192 B) per yield if so required.

    # Attempt to yield file data
    try:
        # Set read seek position
        seeker = 0

        # Set bytes read per yield to the GridFile's chunk size
        bytes_per_yield = filedata.chunk_size

        # Iterate over file data
        while True:
            # Attempt to yield file chunks to HttpResponse object
            try:
                # If the current position in the file is less than or equal to the file size
                if seeker <= filedata.length:
                    # Yield chunk from file (relative to seek position)
                    yield filedata.read(bytes_per_yield)
                    # Increment seek position by bytes read per yield
                    seeker = seeker + bytes_per_yield
                    # Set new seek position in file
                    filedata.seek(seeker)

                # If the current position in the file has exceeded the file size
                else:
                    # Break the current iteration
                    break

            # Keep quiet about GeneratorExit exceptions
            except GeneratorExit:
                pass

            # Handle file chunk iteration exceptions
            except Exception, e:
                # Re-raise the exception
                raise Exception, e
                # Break the current iteration
                break

        # Close the file
        filedata.close()

    # Handle exceptions raised in previous statement (kept for debugging purposes)
    except Exception, e:
        # Re-raise the exception
        raise Exception, e

def sendfile(gridfs_file, download_name):
    """ Input is gridfs file object """

    if getattr(settings,'SENDFILE',False):
        response = HttpResponse(content_type='application/octet-stream')
        response['X-Sendfile'] = gridfs_file._id
    else:
        wrapper = gridFSWrapper(gridfs_file)
        response = HttpResponse(wrapper, content_type='application/octet-stream')
        # required to prevent piston from converting to string the
        # response object
        response._is_string = True

    response['Content-Length'] = gridfs_file.length
    response['Content-Disposition'] = "attachment; filename=%s" % download_name

    return response


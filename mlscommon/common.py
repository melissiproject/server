import hashlib
import os
import mimetypes

from django.http import HttpResponse
from django.core.servers.basehttp import FileWrapper
from django.conf import settings

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
    """ Return the md5 hexdigest of file_object.

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

def basic_sendfile(fname, download_name=None):
    if not os.path.exists(fname):
        raise Http404

    wrapper = FileWrapper(open(fname,"r"))

    content_type = mimetypes.guess_type(fname)[0]
    response = HttpResponse(wrapper, content_type=content_type)
    response['Content-Length'] = os.path.getsize(fname)

    if download_name:
        response['Content-Disposition'] = "attachment; filename=%s"%download_name

    # required to prevent piston from converting to string the
    # response object
    response._is_string = True

    return response

def x_sendfile(fname, download_name=None):
    if not os.path.exists(fname):
        raise Http404

    content_type = mimetypes.guess_type(fname)[0]
    response = HttpResponse('', content_type=content_type)
    response['Content-Length'] = os.path.getsize(fname)
    response['X-Sendfile'] = fname

    if download_name:
        response['Content-Disposition'] = "attachment; filename=%s"%download_name

    return response

if getattr(settings,'SENDFILE',False) == 'x_sendfile':
    sendfile = x_sendfile
else:
    sendfile = basic_sendfile

# caution we use our home breweded FileField form item
# to allow empty files. this is only for CreateForm
# to be changed when this code gets merged into django main
# http://code.djangoproject.com/ticket/13584
from django.forms.fields import Field
from django.forms.widgets import FileInput
from django.utils.translation import ugettext_lazy as _
from django.core import validators
from django.core.exceptions import ValidationError

class myFileField(Field):
    widget = FileInput
    default_error_messages = {
        'invalid': _(u"No file was submitted. Check the encoding type on the form."),
        'missing': _(u"No file was submitted."),
        'empty': _(u"The submitted file is empty."),
        'max_length': _(u'Ensure this filename has at most %(max)d characters (it has %(length)d).'),
    }

    def __init__(self, *args, **kwargs):
        self.max_length = kwargs.pop('max_length', None)
        self.allow_empty_file = kwargs.pop('allow_empty_file', False)
        super(myFileField, self).__init__(*args, **kwargs)

    def to_python(self, data):
        if data in validators.EMPTY_VALUES:
            return None

        # UploadedFile objects should have name and size attributes.
        try:
            file_name = data.name
            file_size = data.size
        except AttributeError:
            raise ValidationError(self.error_messages['invalid'])

        if self.max_length is not None and len(file_name) > self.max_length:
            error_values =  {'max': self.max_length, 'length': len(file_name)}
            raise ValidationError(self.error_messages['max_length'] % error_values)
        if not file_name:
            raise ValidationError(self.error_messages['invalid'])
        if not self.allow_empty_file and not file_size:
            raise ValidationError(self.error_messages['empty'])

        return data

    def clean(self, data, initial=None):
        if not data and initial:
            return initial
        return super(myFileField, self).clean(data)

from django import forms

from mlscommon.models import *
import mlscommon.common as common
from django.utils.translation import ugettext_lazy as _

class ResourceForm(forms.ModelForm):
    resource = forms.CharField(max_length=500, required=False)

    def __init__(self, user, *args, **kwargs):
        self._user = user
        super(ResourceForm, self).__init__(*args, **kwargs)

    def clean_resource(self):
        resource, created =  UserResource.objects.get_or_create(
            name = self.cleaned_data.get('resource', 'melissi'),
            user = self._user
            )
        if created:
            resource.save()

        self.instance.resource = resource

        return resource

class DropletRevisionCreateForm(ResourceForm):
    class Meta:
        model = DropletRevision
        fields = ('name', 'cell', 'content', 'content_sha256', 'number')

class DropletCreateForm(ResourceForm):
    # caution we use our home brewed FileField form item to allow
    # empty files. this is only for CreateForm to be changed when this
    # code gets merged into django main
    # http://code.djangoproject.com/ticket/13584
    content = common.myFileField(required=True, allow_empty_file=True)

    class Meta:
        model = Droplet
        fields = ('name', 'cell', 'content', 'content_sha256')

class CellCreateForm(ResourceForm):
    class Meta:
        model = Cell
        fields = ('name', 'parent')

class CellUpdateForm(ResourceForm):
    class Meta:
        model = CellRevision
        fields = ('name', 'parent', 'resource', 'number')

class CellShareCreateForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = ('mode',)

class UserCreateForm(forms.Form):
    username = forms.CharField(_('username'), required=True)
    first_name = forms.CharField(_('first name'), required=True)
    last_name = forms.CharField(_('last name'), required=True)
    email = forms.EmailField(_('e-mail address'), required=True)
    password = forms.CharField(_('password'), required=True)

class UserUpdateForm(forms.Form):
    password = forms.CharField(_('password'), required=True)

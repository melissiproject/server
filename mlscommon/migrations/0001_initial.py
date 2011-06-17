# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Cell'
        db.create_table('mlscommon_cell', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='children', null=True, to=orm['mlscommon.Cell'])),
            ('lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal('mlscommon', ['Cell'])

        # Adding model 'CellRevision'
        db.create_table('mlscommon_cellrevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cell', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.Cell'])),
            ('resource', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.UserResource'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='revision_parent', null=True, to=orm['mlscommon.Cell'])),
        ))
        db.send_create_signal('mlscommon', ['CellRevision'])

        # Adding model 'Share'
        db.create_table('mlscommon_share', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cell', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.Cell'])),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
        ))
        db.send_create_signal('mlscommon', ['Share'])

        # Adding unique constraint on 'Share', fields ['cell', 'user']
        db.create_unique('mlscommon_share', ['cell_id', 'user_id'])

        # Adding model 'Droplet'
        db.create_table('mlscommon_droplet', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('cell', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.Cell'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('content', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
            ('patch', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal('mlscommon', ['Droplet'])

        # Adding model 'DropletRevision'
        db.create_table('mlscommon_dropletrevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('droplet', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.Droplet'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('cell', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['mlscommon.Cell'])),
            ('content', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
            ('patch', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal('mlscommon', ['DropletRevision'])

        # Adding model 'UserResource'
        db.create_table('mlscommon_userresource', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('mlscommon', ['UserResource'])

        # Adding unique constraint on 'UserResource', fields ['name', 'user']
        db.create_unique('mlscommon_userresource', ['name', 'user_id'])

        # Adding model 'UserProfile'
        db.create_table('mlscommon_userprofile', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], unique=True)),
            ('quota', self.gf('django.db.models.fields.PositiveIntegerField')(default=102400)),
        ))
        db.send_create_signal('mlscommon', ['UserProfile'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'UserResource', fields ['name', 'user']
        db.delete_unique('mlscommon_userresource', ['name', 'user_id'])

        # Removing unique constraint on 'Share', fields ['cell', 'user']
        db.delete_unique('mlscommon_share', ['cell_id', 'user_id'])

        # Deleting model 'Cell'
        db.delete_table('mlscommon_cell')

        # Deleting model 'CellRevision'
        db.delete_table('mlscommon_cellrevision')

        # Deleting model 'Share'
        db.delete_table('mlscommon_share')

        # Deleting model 'Droplet'
        db.delete_table('mlscommon_droplet')

        # Deleting model 'DropletRevision'
        db.delete_table('mlscommon_dropletrevision')

        # Deleting model 'UserResource'
        db.delete_table('mlscommon_userresource')

        # Deleting model 'UserProfile'
        db.delete_table('mlscommon_userprofile')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'mlscommon.cell': {
            'Meta': {'object_name': 'Cell'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['mlscommon.Cell']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'mlscommon.cellrevision': {
            'Meta': {'object_name': 'CellRevision'},
            'cell': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.Cell']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'revision_parent'", 'null': 'True', 'to': "orm['mlscommon.Cell']"}),
            'resource': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.UserResource']"})
        },
        'mlscommon.droplet': {
            'Meta': {'object_name': 'Droplet'},
            'cell': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.Cell']"}),
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'patch': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'mlscommon.dropletrevision': {
            'Meta': {'object_name': 'DropletRevision'},
            'cell': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.Cell']"}),
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'droplet': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.Droplet']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'patch': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        'mlscommon.share': {
            'Meta': {'unique_together': "(('cell', 'user'),)", 'object_name': 'Share'},
            'cell': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mlscommon.Cell']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'mlscommon.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'quota': ('django.db.models.fields.PositiveIntegerField', [], {'default': '102400'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'unique': 'True'})
        },
        'mlscommon.userresource': {
            'Meta': {'unique_together': "(('name', 'user'),)", 'object_name': 'UserResource'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['mlscommon']

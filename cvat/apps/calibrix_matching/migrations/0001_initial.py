# Generated manually for calibrix_matching

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('engine', '0070_job_type_db_constraint'),
    ]

    operations = [
        migrations.CreateModel(
            name='ROITemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('coordinates', models.JSONField(help_text='Bounding box coordinates: {x, y, width, height}')),
                ('feature_descriptor', models.JSONField(help_text='Feature descriptor data including keypoints and descriptors')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='roi_templates', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roi_templates', to='engine.task')),
            ],
            options={
                'verbose_name': 'ROI Template',
                'verbose_name_plural': 'ROI Templates',
                'db_table': 'calibrix_matching_roitemplate',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MatchingSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('algorithm_type', models.CharField(choices=[('SIFT', 'Scale-Invariant Feature Transform'), ('SURF', 'Speeded-Up Robust Features'), ('ORB', 'Oriented FAST and Rotated BRIEF'), ('AKAZE', 'Accelerated-KAZE')], default='SIFT', max_length=20)),
                ('threshold', models.FloatField(help_text='Matching threshold between 0.0 and 1.0', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('roi_template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matching_sessions', to='calibrix_matching.roitemplate')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matching_sessions', to='engine.task')),
            ],
            options={
                'verbose_name': 'Matching Session',
                'verbose_name_plural': 'Matching Sessions',
                'db_table': 'calibrix_matching_matchingsession',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DetectionResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frame_number', models.PositiveIntegerField(help_text='Frame number in the video sequence', validators=[django.core.validators.MinValueValidator(0)])),
                ('coordinates', models.JSONField(help_text='Detected bounding box coordinates: {x, y, width, height}')),
                ('confidence_score', models.FloatField(help_text='Confidence score between 0.0 and 1.0', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('is_confirmed', models.BooleanField(default=False, help_text='Whether this detection has been confirmed by a user')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('matching_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detection_results', to='calibrix_matching.matchingsession')),
            ],
            options={
                'verbose_name': 'Detection Result',
                'verbose_name_plural': 'Detection Results',
                'db_table': 'calibrix_matching_detectionresult',
                'ordering': ['frame_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='detectionresult',
            constraint=models.UniqueConstraint(fields=('matching_session', 'frame_number'), name='calibrix_matching_detectionresult_unique_session_frame'),
        ),
    ]
# Generated manually for Calibrix Ground Truth Export History
# Copyright (C) 2024 Calibrix Corporation
# SPDX-License-Identifier: MIT

import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('calibrix_matching', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('export_id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier for this export', unique=True)),
                ('export_format', models.CharField(choices=[('coco', 'COCO JSON'), ('yolo', 'YOLO'), ('pascal_voc', 'Pascal VOC XML'), ('cvat_xml', 'CVAT XML'), ('csv', 'CSV')], help_text='Format used for export', max_length=20)),
                ('export_config', models.JSONField(default=dict, help_text='Complete export configuration used')),
                ('total_detections', models.PositiveIntegerField(help_text='Total number of detections exported')),
                ('confirmed_detections_only', models.BooleanField(default=True, help_text='Whether export included only confirmed detections')),
                ('min_confidence_threshold', models.FloatField(blank=True, help_text='Minimum confidence threshold applied', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('roi_template_filter', models.CharField(blank=True, help_text='ROI template filter applied (if any)', max_length=255, null=True)),
                ('dataset_split_used', models.BooleanField(default=False, help_text='Whether dataset splitting was applied')),
                ('dataset_splits', models.JSONField(blank=True, help_text='Dataset split configuration (train/val/test ratios)', null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', help_text='Current status of the export', max_length=20)),
                ('export_path', models.CharField(blank=True, help_text='Path to the exported file(s)', max_length=1000, null=True)),
                ('file_size_bytes', models.BigIntegerField(blank=True, help_text='Size of exported file(s) in bytes', null=True)),
                ('compression_format', models.CharField(blank=True, help_text='Compression format used (if any)', max_length=20, null=True)),
                ('quality_report', models.JSONField(blank=True, help_text='Quality control report generated during export', null=True)),
                ('validation_errors', models.JSONField(blank=True, help_text='Any validation errors encountered', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When the export was initiated')),
                ('started_at', models.DateTimeField(blank=True, help_text='When export processing actually started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When export processing completed', null=True)),
                ('duration_seconds', models.FloatField(blank=True, help_text='Total duration of export in seconds', null=True)),
                ('processing_rate', models.FloatField(blank=True, help_text='Processing rate in detections per second', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if export failed', null=True)),
                ('error_details', models.JSONField(blank=True, help_text='Detailed error information', null=True)),
                ('export_version', models.CharField(default='1.0', help_text='Version of the export format/schema used', max_length=50)),
                ('is_incremental', models.BooleanField(default=False, help_text='Whether this is an incremental export')),
                ('auto_delete_at', models.DateTimeField(blank=True, help_text='When this export should be automatically deleted', null=True)),
                ('is_archived', models.BooleanField(default=False, help_text='Whether this export has been archived')),
                ('archived_at', models.DateTimeField(blank=True, help_text='When this export was archived', null=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who initiated the export', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='export_history', to=settings.AUTH_USER_MODEL)),
                ('parent_export', models.ForeignKey(blank=True, help_text='Parent export for incremental exports', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incremental_exports', to='calibrix_matching.ExportHistory')),
                ('task', models.ForeignKey(help_text='Task this export was generated from', on_delete=django.db.models.deletion.CASCADE, related_name='export_history', to='engine.Task')),
            ],
            options={
                'verbose_name': 'Export History',
                'verbose_name_plural': 'Export Histories',
                'db_table': 'calibrix_matching_exporthistory',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ExportDownload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('download_timestamp', models.DateTimeField(auto_now_add=True, help_text='When the download occurred')),
                ('download_ip', models.GenericIPAddressField(blank=True, help_text='IP address of the downloader', null=True)),
                ('user_agent', models.CharField(blank=True, help_text='User agent string of the downloader', max_length=500, null=True)),
                ('bytes_served', models.BigIntegerField(blank=True, help_text='Number of bytes served in this download', null=True)),
                ('download_completed', models.BooleanField(default=True, help_text='Whether the download completed successfully')),
                ('downloaded_by', models.ForeignKey(blank=True, help_text='User who downloaded the export', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='export_downloads', to=settings.AUTH_USER_MODEL)),
                ('export_history', models.ForeignKey(help_text='The export that was downloaded', on_delete=django.db.models.deletion.CASCADE, related_name='download_history', to='calibrix_matching.ExportHistory')),
            ],
            options={
                'verbose_name': 'Export Download',
                'verbose_name_plural': 'Export Downloads',
                'db_table': 'calibrix_matching_exportdownload',
                'ordering': ['-download_timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='exporthistory',
            index=models.Index(fields=['task', '-created_at'], name='calibrix_ma_task_id_0a2d8e_idx'),
        ),
        migrations.AddIndex(
            model_name='exporthistory',
            index=models.Index(fields=['status', '-created_at'], name='calibrix_ma_status_9d4c7a_idx'),
        ),
        migrations.AddIndex(
            model_name='exporthistory',
            index=models.Index(fields=['export_format', '-created_at'], name='calibrix_ma_export__6f8e2b_idx'),
        ),
        migrations.AddIndex(
            model_name='exporthistory',
            index=models.Index(fields=['created_by', '-created_at'], name='calibrix_ma_created_5a9c4f_idx'),
        ),
        migrations.AddIndex(
            model_name='exporthistory',
            index=models.Index(fields=['auto_delete_at'], name='calibrix_ma_auto_de_1b3e7d_idx'),
        ),
        migrations.AddIndex(
            model_name='exportdownload',
            index=models.Index(fields=['export_history', '-download_timestamp'], name='calibrix_ma_export__2c8f9e_idx'),
        ),
        migrations.AddIndex(
            model_name='exportdownload',
            index=models.Index(fields=['downloaded_by', '-download_timestamp'], name='calibrix_ma_downloa_4a6b1c_idx'),
        ),
    ]
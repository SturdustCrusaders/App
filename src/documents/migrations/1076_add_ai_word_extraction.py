# Generated migration for AI word extraction

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1075_workflowaction_order"),
    ]

    operations = [
        # Add fields to Document model
        migrations.AddField(
            model_name='document',
            name='word_data_extracted',
            field=models.BooleanField(db_index=True, default=False, help_text='Whether AI has extracted word positions and confidence scores for this document.', verbose_name='word data extracted'),
        ),
        migrations.AddField(
            model_name='document',
            name='ai_extraction_method',
            field=models.CharField(blank=True, choices=[('azure_vision', 'Azure Computer Vision'), ('surya', 'Surya OCR')], help_text='Which AI service was used to extract words.', max_length=32, verbose_name='AI extraction method'),
        ),
        # Create DocumentPage model
        migrations.CreateModel(
            name='DocumentPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_number', models.PositiveIntegerField(help_text='1-indexed page number within the document', validators=[django.core.validators.MinValueValidator(1)], verbose_name='page number')),
                ('page_width', models.FloatField(blank=True, help_text='Page width in points (PDF) or pixels', null=True, verbose_name='page width')),
                ('page_height', models.FloatField(blank=True, help_text='Page height in points (PDF) or pixels', null=True, verbose_name='page height')),
                ('extracted_at', models.DateTimeField(auto_now_add=True, verbose_name='extracted at')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='documents.document', verbose_name='document')),
            ],
            options={
                'verbose_name': 'document page',
                'verbose_name_plural': 'document pages',
                'ordering': ('document', 'page_number'),
            },
        ),
        # Create DocumentWord model
        migrations.CreateModel(
            name='DocumentWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(db_index=True, help_text='The extracted word text', max_length=1024, verbose_name='text')),
                ('bbox_x0', models.FloatField(help_text='Bounding box left coordinate', verbose_name='bbox x0')),
                ('bbox_y0', models.FloatField(help_text='Bounding box top coordinate', verbose_name='bbox y0')),
                ('bbox_x1', models.FloatField(help_text='Bounding box right coordinate', verbose_name='bbox x1')),
                ('bbox_y1', models.FloatField(help_text='Bounding box bottom coordinate', verbose_name='bbox y1')),
                ('confidence', models.FloatField(help_text='Confidence score from the AI model (0-1)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='confidence')),
                ('language', models.CharField(blank=True, help_text='Detected language code (e.g., "en", "de")', max_length=10, verbose_name='language')),
                ('word_index', models.PositiveIntegerField(help_text='Sequential index of word on the page (for reconstruction order)', verbose_name='word index')),
                ('extracted_at', models.DateTimeField(auto_now_add=True, verbose_name='extracted at')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='words', to='documents.documentpage', verbose_name='page')),
            ],
            options={
                'verbose_name': 'document word',
                'verbose_name_plural': 'document words',
                'ordering': ('page', 'word_index'),
            },
        ),
        # Add indexes to DocumentWord
        migrations.AddIndex(
            model_name='documentword',
            index=models.Index(fields=['page', 'word_index'], name='documents_d_page_id_word_idx'),
        ),
        migrations.AddIndex(
            model_name='documentword',
            index=models.Index(fields=['text'], name='documents_d_text_idx'),
        ),
        migrations.AddIndex(
            model_name='documentword',
            index=models.Index(fields=['confidence'], name='documents_d_confid_idx'),
        ),
        # Add unique constraint to DocumentPage
        migrations.AddConstraint(
            model_name='documentpage',
            constraint=models.UniqueConstraint(fields=['document', 'page_number'], name='documents_documentpage_unique_doc_page'),
        ),
    ]

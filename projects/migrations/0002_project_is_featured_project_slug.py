# Generated by Django 5.2.1 on 2025-05-25 01:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_featured',
            field=models.BooleanField(default=False, help_text='check if this project should be featured on the home page'),
        ),
        migrations.AddField(
            model_name='project',
            name='slug',
            field=models.SlugField(blank=True, help_text='unique identifier for this project, used in urls ', unique=True),
        ),
    ]

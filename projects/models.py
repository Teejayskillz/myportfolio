from django.db import models

# Create your models here.
class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='projects_images/')
    github_url = models.URLField(blank=True, null=True )
    live_demo_url = models.URLField(blank=True, null=True)
    technologies = models.CharField(max_length=200, help_text="Comma-separated list of technologies (e.g., Django, Python, Bootstrap)")

    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['title'] 
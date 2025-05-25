from django.db import models
from django.utils.text import slugify


# Create your models here.
class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='projects_images/')
    github_url = models.URLField(blank=True, null=True )
    live_demo_url = models.URLField(blank=True, null=True)
    technologies = models.CharField(max_length=200, help_text="Comma-separated list of technologies (e.g., Django, Python, Bootstrap)")
    is_featured = models.BooleanField(default=False, help_text="check if this project should be featured on the home page")
    slug = models.SlugField(unique=True,blank=True, help_text="unique identifier for this project, used in urls ")

    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['title'] 

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Project.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)    
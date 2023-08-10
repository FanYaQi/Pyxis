from django.db import models


class GeoIndex(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')
from django.db import models


class ProductURL(models.Model):
    id = models.BigAutoField(primary_key=True)
    product_url = models.TextField(unique=True)

    class Meta:
        db_table = 'trendyol_producturl'

    def __str__(self):
        return self.product_url

class ProcessedURL(models.Model):
    product_url = models.URLField(unique=True)
    is_processed = models.BooleanField(default=False)
    last_processed = models.DateTimeField(auto_now=True)
    

class ProductID(models.Model):
    product_id = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.product_id


class Product(models.Model):
    barcode = models.CharField(max_length=50, unique=True)
    product_url = models.ForeignKey(ProductURL, on_delete=models.CASCADE, related_name="barcodes", null=True, blank=True)
    product_ids = models.ManyToManyField(ProductID, related_name="products", blank=True)
    has_id = models.BooleanField(default=False)  # ID eşleşip eşleşmediğini belirler

    def __str__(self):
        return self.barcode
    

class ProductReview(models.Model):
    product_url = models.URLField()
    date = models.BigIntegerField()
    text = models.TextField() 
    photos = models.JSONField(default=list)
    seller = models.CharField(max_length=255)
    sentiment_score = models.FloatField()
    is_sent = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False)
    
    
    def __str__(self):
        return f"Review for {self.product_url}"

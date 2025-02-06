from django.urls import path
from . import views

urlpatterns = [
    path('trendyol_all_products/', views.trendyol_all_products, name='trendyol_all_products'),
    path('trendyol_product_urls/', views.trendyol_product_urls, name='trendyol_product_urls'),
    path('login/', views.login, name='login'),
    path('get-product-ids/<str:barcode_code>/', views.get_product_ids_view, name='get_product_ids'),
    path('get-all-product-ids/', views.get_all_product_ids, name='get_all_product_ids'),
    path('analyze-products-with-ids/', views.analyze_products_with_ids, name='analyze_products_with_ids'),
    path('initialize-processed-urls/', views.initialize_processed_urls, name='initialize_processed_urls'),
    path('send-reviews/', views.send_reviews_to_product_ids, name='send_reviews_to_product_ids'),
]

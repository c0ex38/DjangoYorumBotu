import os 
import http.client
import json
import urllib.parse
import pandas as pd
from django.http import JsonResponse
from .models import Product, ProductURL, ProductID, ProductReview, ProcessedURL
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .utils import get_product_reviews
from django.db import connection
from django.conf import settings
from urllib.parse import urlparse, urlunparse

def trendyol_all_products(request):
    conn = http.client.HTTPSConnection("api.trendyol.com")
    payload = ''
    headers = {
        'Authorization': 'Basic QlREbm5HcWtVdmVIOHRTbEdGQzQ6d3dEd2M0cFhmNEo1NjNOMXBKd3c=',
        'User-Agent': '107703 - SelfIntegration'
    }

    page = 0
    total_pages = 1
    products_saved = 0

    # Mevcut verileri toplama (var olan verileri kontrol etmek için)
    existing_barcodes = set(Product.objects.values_list('barcode', flat=True))
    existing_urls = set(ProductURL.objects.values_list('product_url', flat=True))

    while page < total_pages:
        conn.request(
            "GET",
            f"/sapigw/suppliers/107703/products?page={page}&size=5000&approved=true&onSale=true",
            payload,
            headers
        )
        res = conn.getresponse()
        data = res.read()
        decoded_data = json.loads(data.decode("utf-8"))

        total_pages = decoded_data.get('totalPages', 1)

        # Ürünleri işle
        for item in decoded_data.get('content', []):
            barcode = item.get('barcode')
            product_url = item.get('productUrl')

            if barcode and product_url:
                # Eğer URL zaten mevcut değilse, ekle
                if product_url not in existing_urls:
                    product_url_obj, created = ProductURL.objects.get_or_create(product_url=product_url)
                    existing_urls.add(product_url)  # Yeni ekleneni sete ekle
                else:
                    product_url_obj = ProductURL.objects.get(product_url=product_url)

                # Eğer barkod zaten mevcut değilse, ekle
                if barcode not in existing_barcodes:
                    Product.objects.create(
                        barcode=barcode,
                        product_url=product_url_obj
                    )
                    existing_barcodes.add(barcode)  # Yeni ekleneni sete ekle
                    products_saved += 1

        page += 1

    return JsonResponse({"status": "success", "products_saved": products_saved})


def trendyol_product_urls(request):
    urls = ProductURL.objects.all()
    result = []

    for url in urls:
        barcodes = [product.barcode for product in url.barcodes.all()]
        result.append({
            "product_url": url.product_url,
            "barcodes": barcodes
        })

    return JsonResponse(result, safe=False)


def login(request):
    """Login işlemini yapar ve token döndürür."""
    conn = http.client.HTTPConnection("www.dgnonline.com")
    payload = urllib.parse.urlencode({
        'pass': 'Talipsan.4244'  # Şifre buraya yazıldı
    })
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # API isteği yap
    conn.request("POST", "/rest1/auth/login/selim.sarikaya", payload, headers)
    res = conn.getresponse()
    data = res.read()

    # Yanıtı işle
    try:
        decoded_data = json.loads(data.decode("utf-8"))
        if decoded_data.get('success') and decoded_data.get('data'):
            token = decoded_data['data'][0]['token']  # Token'ı al
            return JsonResponse({"token": token})
        else:
            return JsonResponse({"error": "Giriş başarısız", "details": decoded_data}, status=400)
    except Exception as e:
        return JsonResponse({"error": "Bir hata oluştu", "details": str(e)}, status=500)


def get_product_ids_view(request, barcode_code):
    """Verilen barkoda ait ürün ID'lerini TSoft sisteminden çeker ve kaydeder."""
    # Login işlemi
    conn = http.client.HTTPConnection("127.0.0.1", 8000)  # Yerel login endpointi
    conn.request("GET", "/trendyol/login/")
    res = conn.getresponse()
    data = res.read()
    decoded_data = json.loads(data.decode("utf-8"))

    if decoded_data.get("token"):
        token = decoded_data["token"]
    else:
        return JsonResponse({"error": "Token alınamadı", "details": decoded_data}, status=400)

    # Barkod detaylarını al
    barcode_url = f'https://dgnonline.com/rest1/subProduct/getSubProductByCode/{barcode_code}'
    barcode_params = {'token': token}

    try:
        conn = http.client.HTTPSConnection("dgnonline.com")
        payload = urllib.parse.urlencode(barcode_params)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        conn.request("POST", f"/rest1/subProduct/getSubProductByCode/{barcode_code}", payload, headers)
        res = conn.getresponse()
        barcode_response = res.read()
        barcode_response_json = json.loads(barcode_response.decode("utf-8"))

        if barcode_response_json.get("success") and barcode_response_json.get("data"):
            product_ids = []
            for product in barcode_response_json["data"]:
                product_code = product.get("MainProductCode", "MainProductCode bulunamadı")
                base_product_code = product_code.rsplit('-', 1)[0]
                productcode_url = "https://dgnonline.com/rest1/product/get"
                productcode_params = {
                    'token': token,
                    'f': f'ProductCode|{base_product_code}|contain'
                }
                conn = http.client.HTTPSConnection("dgnonline.com")
                productcode_payload = urllib.parse.urlencode(productcode_params)
                conn.request("POST", "/rest1/product/get", productcode_payload, headers)
                productcode_res = conn.getresponse()
                productcode_data = productcode_res.read()
                productcode_response_json = json.loads(productcode_data.decode("utf-8"))
                if productcode_response_json.get("success") and productcode_response_json.get("data"):
                    for prod in productcode_response_json["data"]:
                        product_id = prod["ProductId"]
                        product_ids.append(product_id)

                        # ProductID modeline kaydet
                        product_id_obj, _ = ProductID.objects.get_or_create(product_id=product_id)

                        # Product modeline ilişkilendir
                        product_obj, _ = Product.objects.get_or_create(barcode=barcode_code)
                        product_obj.product_ids.add(product_id_obj)

            return JsonResponse({"product_ids": product_ids})
        else:
            return JsonResponse({"error": f"Barkod için ürün verisi bulunamadı: {barcode_code}"}, status=404)
    except Exception as e:
        return JsonResponse({"error": "Barkod isteği sırasında bir hata oluştu", "details": str(e)}, status=500)


def get_all_product_ids(request):
    """
    Veritabanındaki tüm ürünlerin (Product) barkodlarını alır ve her bir barkod için
    ProductID'leri TSoft API'den topluca çeker ve kaydeder.
    """
    try:
        # Login işlemi ve token alma
        conn = http.client.HTTPConnection("127.0.0.1", 8000)  # Yerel login endpointi
        conn.request("GET", "/trendyol/login/")
        res = conn.getresponse()
        data = res.read()
        decoded_data = json.loads(data.decode("utf-8"))

        if decoded_data.get("token"):
            token = decoded_data["token"]
        else:
            return JsonResponse({"error": "Token alınamadı", "details": decoded_data}, status=400)

        # Veritabanından tüm ürünleri al
        products = Product.objects.all()
        if not products.exists():
            return JsonResponse({"error": "Hiçbir ürün bulunamadı."}, status=404)

        success_count = 0
        product_id_map = {}  # Her ürün için çekilen ProductID'leri saklamak için

        # Her bir ürünün barkodu için işlemleri yap
        for product in products:
            barcode = product.barcode
            barcode_url = f'https://dgnonline.com/rest1/subProduct/getSubProductByCode/{barcode}'
            barcode_params = {'token': token}

            try:
                # Barkod detaylarını API'den al
                conn = http.client.HTTPSConnection("dgnonline.com")
                payload = urllib.parse.urlencode(barcode_params)
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                conn.request("POST", f"/rest1/subProduct/getSubProductByCode/{barcode}", payload, headers)
                res = conn.getresponse()
                barcode_response = res.read()
                barcode_response_json = json.loads(barcode_response.decode("utf-8"))

                if barcode_response_json.get("success") and barcode_response_json.get("data"):
                    product_ids = []
                    for product_data in barcode_response_json["data"]:
                        product_code = product_data.get("MainProductCode", "MainProductCode bulunamadı")
                        base_product_code = product_code.rsplit('-', 1)[0]
                        productcode_url = "https://dgnonline.com/rest1/product/get"
                        productcode_params = {
                            'token': token,
                            'f': f'ProductCode|{base_product_code}|contain'
                        }
                        conn.request("POST", "/rest1/product/get", urllib.parse.urlencode(productcode_params), headers)
                        productcode_res = conn.getresponse()
                        productcode_data = productcode_res.read()
                        productcode_response_json = json.loads(productcode_data.decode("utf-8"))

                        if productcode_response_json.get("success") and productcode_response_json.get("data"):
                            for prod in productcode_response_json["data"]:
                                product_id = prod["ProductId"]
                                product_ids.append(product_id)

                                # ProductID modeline kaydet
                                product_id_obj, _ = ProductID.objects.get_or_create(product_id=product_id)

                                # Product ile ilişkilendir
                                product.product_ids.add(product_id_obj)

                    product_id_map[barcode] = product_ids  # Çekilen ID'leri sakla
                    success_count += 1

            except Exception as e:
                # Hata durumunda devam et
                continue

        return JsonResponse({
            "status": "success",
            "products_processed": len(products),
            "products_with_ids": success_count,
            "product_id_map": product_id_map
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def initialize_processed_urls(request):
    """
    Product tablosundan tüm URL'leri ProcessedURL tablosuna ekler.
    """
    product_urls = Product.objects.filter(product_ids__isnull=False).distinct().values_list('product_url__product_url', flat=True)

    for url in product_urls:
        ProcessedURL.objects.get_or_create(product_url=url)

    return JsonResponse({"status": "success", "urls_added": len(product_urls)})


  
@csrf_exempt
@require_http_methods(["POST"])
def analyze_products_with_ids(request):
    """
    Yalnızca ProductID'si bulunan ve henüz işlenmemiş URL'ler için yorumları alır ve işlenmiş olarak işaretler.
    """
    try:
        data = json.loads(request.body)
        only_positive = data.get('only_positive', False)
        batch_size = data.get('batch_size', 10)

        # İşlenmemiş URL'leri al
        unprocessed_urls = ProcessedURL.objects.filter(is_processed=False).values_list('product_url', flat=True)

        if not unprocessed_urls:
            return JsonResponse({
                'error': 'İşlenmemiş ürün URL bulunamadı.'
            }, status=404)

        total_reviews = 0

        # Her ürün URL'si için yorumları çek ve işle
        for url in unprocessed_urls:
            print(f"Orijinal URL işleniyor: {url}")

            # URL'yi /yorumlar formatına dönüştür
            parsed_url = urlparse(url)
            url_without_params = parsed_url._replace(query="")  # Parametreleri kaldır
            formatted_url = urlunparse(url_without_params) + "/yorumlar"
            print(f"Dönüştürülmüş URL: {formatted_url}")

            try:
                reviews = get_product_reviews(formatted_url, only_positive, batch_size)

                # Yorumları işleme ve veritabanına kaydetme
                for review in reviews:
                    # Yalnızca trendyol.com URL'leri için işlem yap
                    if "trendyol.com" not in formatted_url:
                        print(f"Atlandı: Trendyol olmayan URL -> {formatted_url}")
                        continue

                    print(f"Yorum: {review}")  # Yorum detaylarını konsola yazdır

                    # Veritabanında aynı yorum varsa kaydetme
                    existing_review = ProductReview.objects.filter(
                        product_url=formatted_url,
                        date=review['date'],
                        text=review['text']
                    ).exists()

                    if not existing_review:
                        ProductReview.objects.create(
                            product_url=formatted_url,
                            date=review['date'],
                            text=review['text'],
                            photos=review.get('photos', []),
                            seller=review.get('seller', ''),
                            sentiment_score=review.get('sentiment_score', 0.0),
                        )
                        print(f"Yorum kaydedildi: {review['text']}")
                    else:
                        print(f"Yorum zaten mevcut: {review['text']}")

                total_reviews += len(reviews)

                # URL'yi işlenmiş olarak işaretle
                ProcessedURL.objects.filter(product_url=url).update(is_processed=True)

            except Exception as e:
                print(f"Yorumlar alınırken hata oluştu: {formatted_url} - {str(e)}")
                continue

        return JsonResponse({
            "success": True,
            "total_reviews": total_reviews
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


       
        
def send_reviews_to_product_ids(request):
    """
    Her bir yorum (ProductReview), bağlı olduğu ProductURL'nin tüm ProductID'lerine gönderilir.
    """
    try:
        # TSoft API'ye bağlanmak için gerekli ayarlar
        conn = http.client.HTTPConnection("www.dgnonline.com")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        success_count = 0

        # Gönderilmemiş (is_sent=False) yorumları al
        reviews = ProductReview.objects.filter(is_sent=False)

        if not reviews.exists():
            return JsonResponse({"error": "Gönderilmemiş yorum bulunamadı."}, status=404)

        # Her bir yorumu işle
        for review in reviews:
            # Yorumun bağlı olduğu ProductID'leri al
            product_ids = ProductID.objects.filter(products__product_url__product_url=review.product_url)

            if not product_ids.exists():
                continue  # Eğer bağlı ProductID yoksa bu yorumu atla

            # Her ProductID için yorumu gönder
            for product_id in product_ids:
                payload = {
                    "token": "SISTEM_LOGIN_TOKEN",  # Login token burada kullanılmalı
                    "data": json.dumps([
                        {
                            "CustomerId": "110",  # Sabit bir müşteri ID kullanılıyor
                            "ProductId": str(product_id.product_id),
                            "Comment": review.text,
                            "Title": "Review Title",  # İsteğe bağlı başlık
                            "Rate": "5",  # Yıldız derecesi
                            "IsNameDisplayed": "true",
                            "ImageUrl": "",  # Görselleri eklemek isterseniz buraya yazabilirsiniz
                            "DateTimeStamp": review.date
                        }
                    ])
                }
                payload_encoded = urllib.parse.urlencode(payload)

                # API'ye POST isteği gönder
                conn.request("POST", "/rest1/product/comment", payload_encoded, headers)
                response = conn.getresponse()
                response_data = response.read().decode("utf-8")
                response_json = json.loads(response_data)

                if response_json.get("success"):
                    success_count += 1

            # Yorum başarıyla gönderildiyse, is_sent alanını True yap
            review.is_sent = True
            review.save()

        return JsonResponse({
            "status": "success",
            "reviews_sent": success_count,
            "total_reviews": reviews.count()
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def post_reviews(request):
    """
    Veritabanında bulunan tüm gönderilmemiş (is_sent=False) yorumları,
    ilgili ProductID'lere ve Excel'den alınan CustomerId'lere gönderen fonksiyon.
    """
    try:
        print("Başlatıldı: post_reviews")  # Konsola çıktı
        # 1. Login işlemi ve token alma
        print("Login işlemi başlatılıyor...")
        conn = http.client.HTTPConnection("127.0.0.1", 8000)  # Yerel login endpointi
        conn.request("GET", "/trendyol/login/")
        res = conn.getresponse()
        data = res.read()
        decoded_data = json.loads(data.decode("utf-8"))

        if decoded_data.get("token"):
            token = decoded_data["token"]
            print(f"Token alındı: {token}")  # Token bilgisi
        else:
            print("Token alınamadı.")
            return JsonResponse({"error": "Token alınamadı.", "details": decoded_data}, status=400)

        # 2. Excel'den CustomerId'leri al
        print("Excel'den CustomerId'ler alınıyor...")
        excel_path = "trendyol/customer.xlsx"  # Excel dosyasının doğru yolu
        print(f"Excel dosyası yolu: {excel_path}")
        excel_data = pd.read_excel(excel_path)
        customer_ids = excel_data["Üye Id"].dropna().tolist()
        print(f"CustomerId'ler: {customer_ids}")

        if not customer_ids:
            print("Excel'den hiçbir CustomerId alınamadı.")
            return JsonResponse({"error": "Excel'den CustomerId bulunamadı."}, status=400)

        # 3. Veritabanından gönderilmemiş yorumları al
        print("Gönderilmemiş yorumlar (is_sent=False) alınıyor...")
        reviews = ProductReview.objects.filter(is_sent=False, seller="dgn")
        print(f"Toplam gönderilmemiş yorum sayısı: {reviews.count()}")

        if not reviews.exists():
            print("Gönderilmemiş yorum bulunamadı.")
            return JsonResponse({"error": "Gönderilmemiş yorum bulunamadı."}, status=404)

        # 4. TSoft API'ye bağlanma ayarları
        print("TSoft API bağlantısı başlatılıyor...")
        conn = http.client.HTTPSConnection("www.dgnonline.com")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        success_count = 0

        # 5. Her yorum için işlemler
        for review in reviews:
            print(f"İşleniyor: Yorum (ID: {review.id}, Text: {review.text})")
            # Yorumun bağlı olduğu tüm ProductID'leri bul
            product_ids = ProductID.objects.filter(products__product_url__product_url=review.product_url)
            print(f"Yorum için bulunan ProductID'ler: {[p.product_id for p in product_ids]}")

            if not product_ids.exists():
                print("Bu yorum için ProductID bulunamadı, devam ediliyor.")
                continue  # Eğer ProductID yoksa bu yorumu atla

            # Her müşteri ID ve ProductID için yorumu gönder
            for customer_id in customer_ids:
                for product_id in product_ids:
                    fields = {
                        "token": token,
                        "data": json.dumps([
                            {
                                "CustomerId": str(customer_id),
                                "ProductId": str(product_id.product_id),
                                "Comment": review.text,
                                "Title": "Yorum Başlığı",  # Başlık ekleyebilirsiniz
                                "Rate": "5",  # Varsayılan olarak 5 yıldız
                                "IsNameDisplayed": "true",
                                "ImageUrl": review.photos[0] if review.photos else "",  # İlk görseli ekle
                                "DateTimeStamp": review.date
                            }
                        ])
                    }
                    # POST için payload'ı URL encode et
                    payload_encoded = urllib.parse.urlencode(fields)

                    print(f"Yorum gönderiliyor: {fields}")
                    conn.request("POST", "/rest1/product/comment", payload_encoded, headers)
                    response = conn.getresponse()
                    response_data = response.read().decode("utf-8")
                    response_json = json.loads(response_data)
                    print(f"API Yanıtı: {response_json}")

                    if response_json.get("success"):
                        success_count += 1

            # Yorum başarıyla gönderildiyse, is_sent=True yap
            print(f"Yorum (ID: {review.id}) başarıyla gönderildi. is_sent=True olarak işaretleniyor.")
            review.is_sent = True
            review.save()

        # Yanıt olarak gönderilen yorumları döndür
        print(f"İşlem tamamlandı. Başarıyla gönderilen yorum sayısı: {success_count}")
        return JsonResponse({
            "status": "success",
            "reviews_sent": success_count,
            "total_reviews": reviews.count()
        })

    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

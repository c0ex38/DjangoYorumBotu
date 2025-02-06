import threading
import time
import json
import random
import http.client
import urllib.parse
import pandas as pd
from django.http import JsonResponse
from .models import ProductReview, ProductID

def process_reviews():
    while True:
        try:
            # Login ve token alma
            conn = http.client.HTTPConnection("127.0.0.1", 8000)
            conn.request("GET", "/trendyol/login/")
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")
            
            try:
                token = json.loads(response_data).get("token")
                if not token:
                    print("❌ Token alınamadı")
                    time.sleep(60)
                    continue
            except json.JSONDecodeError:
                print(f"❌ Token JSON dönüşüm hatası: {response_data}")
                time.sleep(60)
                continue

            # Excel'den CustomerID al
            try:
                excel_data = pd.read_excel("trendyol/customer.xlsx")
                if "Üye Id" not in excel_data.columns:
                    raise ValueError("Üye Id sütunu bulunamadı")
                customer_ids = excel_data["Üye Id"].dropna().astype(str).tolist()
            except Exception as e:
                print(f"❌ Excel okunurken hata oluştu: {str(e)}")
                time.sleep(60)
                continue

            # Yorumları filtrele
            reviews = ProductReview.objects.filter(
                is_sent=False, 
                seller__iexact='DGN',
                is_skipped=False,
                sentiment_score__gt=0
            ).order_by('id')

            if not reviews.exists():
                print("⏳ Gönderilecek yorum bulunamadı, bekleniyor...")
                time.sleep(60)
                continue

            print(f"🔄 Toplam {reviews.count()} yorum işlenecek.")

            for review in reviews:
                try:
                    selected_customer_id = str(random.choice(customer_ids))

                    if not review.product_url:
                        print(f"⚠️ Ürün URL’si eksik: {review.id}")
                        continue
                    base_url = review.product_url.split('/yorumlar')[0].split('?')[0]

                    # Ürün ID'lerini bul
                    product_ids = ProductID.objects.filter(
                        products__product_url__product_url__icontains=base_url
                    ).distinct()

                    if not product_ids.exists():
                        print(f"⚠️ ProductID bulunamadı, atlanıyor.")
                        continue

                    sent_successfully = False
                    for product_id in product_ids:
                        try:
                            conn = http.client.HTTPSConnection("dgnonline.com")
                            payload = {
                                "token": token,
                                "data": json.dumps([{
                                    "CustomerId": selected_customer_id,
                                    "ProductId": str(product_id.product_id),
                                    "Comment": review.text,
                                    "Title": "",
                                    "Rate": "5",
                                    "DateTimeStamp": str(review.date),
                                    "IsNameDisplayed": "0"
                                }])
                            }
                            conn.request("POST", "/rest1/product/comment", 
                                        urllib.parse.urlencode(payload),
                                        {"Content-Type": "application/x-www-form-urlencoded"})
                            
                            result_data = conn.getresponse().read().decode("utf-8")

                            try:
                                result = json.loads(result_data)
                                if result.get("success"):
                                    sent_successfully = True
                                    print(f"✅ Yorum başarıyla gönderildi")
                                else:
                                    print(f"❌ API Hatası: {result}")
                            except json.JSONDecodeError:
                                print(f"❌ API Yanıtı JSON formatında değil: {result_data}")
                        
                        except Exception as e:
                            print(f"⚠️ ProductID gönderim hatası: {str(e)}")
                        finally:
                            conn.close()
                            time.sleep(1)

                    if sent_successfully:
                        review.is_sent = True
                        review.save()

                except Exception as e:
                    print(f"⚠️ Yorum işleme hatası: {str(e)}")
                    continue

            print("✅ İşlem tamamlandı, 10 dakika bekleniyor...")
            time.sleep(600)

        except Exception as e:
            print(f"❌ Genel hata: {str(e)}")
            time.sleep(600)

# Thread başlatma
def start_review_worker():
    thread = threading.Thread(target=process_reviews, daemon=True)
    thread.start()

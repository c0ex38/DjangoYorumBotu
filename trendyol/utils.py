from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
from textblob import TextBlob
from googletrans import Translator
from .models import ProductReview
from datetime import datetime

def setup_driver():
   chrome_options = Options()
   chrome_options.add_argument("--headless")
   chrome_options.add_argument("--disable-gpu")
   chrome_options.add_argument("--no-sandbox")
   chrome_options.add_argument("--disable-dev-shm-usage")
   return webdriver.Chrome(options=chrome_options)

def batch_translate(texts):
   translator = Translator()
   translations = []
   
   for text in texts:
       try:
           time.sleep(2)
           result = translator.translate(text, src='tr', dest='en')
           translations.append(result.text)
       except Exception as e:
           print(f"Çeviri hatası: {str(e)}")
           translations.append(text)
   
   return translations

def analyze_reviews_batch(reviews_batch):
   texts = [review["text"] for review in reviews_batch]
   try:
       translated_texts = batch_translate(texts)
       for review, translated_text in zip(reviews_batch, translated_texts):
           try:
               blob = TextBlob(translated_text)
               review["sentiment_score"] = round(blob.sentiment.polarity, 2)
           except:
               review["sentiment_score"] = 0
   except:
       for review in reviews_batch:
           review["sentiment_score"] = 0
   
   return reviews_batch

def scroll_to_bottom(driver):
   last_height = driver.execute_script("return document.body.scrollHeight")
   while True:
       driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
       time.sleep(1)
       new_height = driver.execute_script("return document.body.scrollHeight")
       if new_height == last_height:
           break
       last_height = new_height

def get_comment_date(comment):
   info_items = comment.find_elements(By.CLASS_NAME, "comment-info-item")
   for item in info_items:
       text = item.text
       if "202" in text:
           tr_months = {
               "Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04",
               "Mayıs": "05", "Haziran": "06", "Temmuz": "07", "Ağustos": "08", 
               "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12"
           }
           
           day, month, year = text.split()
           month = tr_months[month]
           dt = datetime.strptime(f"{day} {month} {year}", "%d %m %Y")
           return int(dt.timestamp())
           
   return None


def get_product_reviews(url, only_positive=False, batch_size=10):
    driver = setup_driver()
    translator = Translator()

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        reviews_wrapper = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "reviews-wrapper")))

        scroll_to_bottom(driver)
        comments = driver.find_elements(By.CLASS_NAME, "comment")

        reviews_list = []

        for comment in comments:
            try:
                date = get_comment_date(comment)
                text = comment.find_element(By.CLASS_NAME, "comment-text").text

                # Eğer yorum zaten kayıtlıysa atla
                existing_review = ProductReview.objects.filter(
                    product_url=url,
                    date=date,
                    text=text
                ).exists()

                if existing_review:
                    continue

                # Görselleri ayıkla ve kaydet
                photo_urls = []
                try:
                    photos = comment.find_elements(By.CSS_SELECTOR, ".review-image[style*='background-image']")
                    for photo in photos:
                        style = photo.get_attribute("style")
                        image_url = style.split('url("')[1].split('")')[0]
                        photo_urls.append(image_url)
                except Exception as e:
                    print(f"Görseller alınırken hata: {e}")

                # Satıcıyı bul
                seller = comment.find_element(By.CLASS_NAME, "seller-name-info").text

                # Yorum analizi (Google Translate ve TextBlob ile)
                translated = translator.translate(text, src='tr', dest='en')
                time.sleep(1)
                blob = TextBlob(translated.text)
                sentiment_score = round(blob.sentiment.polarity, 2)

                # Yorumları listeye ekle
                reviews_list.append({
                    "product_url": url,  # Ürünün gerçek URL'si
                    "date": date,
                    "text": text,
                    "photos": photo_urls,
                    "seller": seller,
                    "sentiment_score": sentiment_score
                })

            except Exception as e:
                print(f"Yorum işlenirken hata: {e}")
                continue

        # Yorumları veritabanına kaydet
        for review in reviews_list:
            ProductReview.objects.create(
                product_url=review["product_url"],
                date=review["date"],
                text=review["text"],
                photos=review["photos"],
                seller=review["seller"],
                sentiment_score=review["sentiment_score"]
            )

        return reviews_list

    finally:
        driver.quit()

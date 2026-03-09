import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_cello():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Cello Square 메인 페이지 접속 중...")
        # Cello Square Market Updates URL
        page.goto("https://www.cello-square.com/kr/marketupdates/marketupdates-list.do?page=1&searchType=all&hashTagId=&searchValue=")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        
        # 기사 목록 추출 (5개)
        # 전체기사 리스트: #contsList 영역 내부의 a 태그 링크
        items = page.locator("#contsList a[href]").element_handles()
        
        links = []
        for x in items:
            href = x.get_attribute("href")
            # view- 로 시작하는 상세페이지 링크만 필터링
            if href and "view-" in href:
                href = urllib.parse.urljoin(page.url, href)
                if href not in links:
                    links.append(href)
                    if len(links) >= 5:
                        break
                        
        print(f"추출할 기사 링크 {len(links)}개: {links}")
        
        # 상세 페이지 크롤링
        for i, link in enumerate(links):
            print(f"[{i+1}/{len(links)}] 상세 페이지 크롤링 중: {link}")
            try:
                page.goto(link)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                
                category = ""
                title = ""
                date = ""
                
                # 카테고리 : #sub-contents > div.title-box > h1 > em.category-text
                cat_el = page.locator("#sub-contents > div.title-box > h1 > em.category-text, .category-text").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()

                # 제목 : titleNm 형식
                title_el = page.locator(".titleNm, #sub-contents > div.title-box > h1").first
                if title_el.is_visible():
                    title_raw = title_el.inner_text().strip()
                    title = title_raw
                    # 제목에서 카테고리 텍스트 제거
                    if category and category in title_raw:
                        title = title_raw.replace(category, "").strip()

                # 날짜 : #sub-contents > div.detail-con > div > p > span.date
                date_el = page.locator("#sub-contents > div.detail-con > div > p > span.date, .date").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    import re
                    match = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", date)
                    if match:
                        date = match.group(0)

                # 본문(기사 텍스트와 이미지) : #sub-contents > div.detail-con > div > div.detail-box > div > div > div.text
                content_el = page.locator("#sub-contents .detail-box .text, #sub-contents .detail-con .detail-box").first
                if not content_el.is_visible():
                    content_el = page.locator("#sub-contents .detail-box").first
                    
                content = ""
                image_urls = []
                
                if content_el.is_visible():
                    content = content_el.inner_text().strip()
                    
                    # 본문 내 이미지 정보
                    img_els = content_el.locator("img").element_handles()
                    for img in img_els:
                        src = img.get_attribute("src")
                        if src:
                            src = urllib.parse.urljoin(page.url, src)
                            image_urls.append(src)
                
                results.append({
                    "url": link,
                    "category": category,
                    "title": title,
                    "date": date,
                    "content": content,
                    "images": image_urls
                })
            except Exception as e:
                print(f"Error scraping detail page {link}: {e}")
                
        browser.close()
        
    return results

if __name__ == "__main__":
    print("Cello Square 크롤러 시작...")
    crawled_data = crawl_cello()
    
    output_file = 'cello_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

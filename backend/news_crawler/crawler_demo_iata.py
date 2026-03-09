import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_iata():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("IATA 메인 페이지 접속 중...")
        # IATA Pressroom URL
        page.goto("https://www.iata.org/en/pressroom/")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)
        
        # 기사 목록 추출 (5개)
        # 전체기사 리스트는 body > div:nth-child(3) > div.layout-wrapper.two-column-layout > div > div > div > div.release-teasers > div.row 
        # 안쪽의 a 링크들 수집
        items = page.locator(".release-teasers .row a[href]").element_handles()
        
        links = []
        for x in items:
            href = x.get_attribute("href")
            if href and "/pressroom/20" in href: # 보통 /pressroom/2026-releases/ 등의 구조
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
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(2000)
                
                category = ""
                title = ""
                date = ""
                
                # 제목 : body > div:nth-child(3) > div.layout-wrapper.three-column-layout > div > div > div.layout-column-middle > div:nth-child(2) > h1
                title_el = page.locator(".layout-column-middle h1, .layout-column-middle h2").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                
                # 카테고리 : body > div:nth-child(3) > div.layout-wrapper.three-column-layout > div > div > div.layout-column-left > div > ul > li > a
                cat_el = page.locator(".layout-column-left ul li a").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()

                # 날짜 : body > div:nth-child(3) > div.layout-wrapper.three-column-layout > div > div > div.layout-column-middle > div.d-flex.align-items-center.justify-content-between > div:nth-child(1) > div
                # d-flex 클래스가 여러개 쓰일 수 있으므로 포괄적 처리 + 정확한 텍스트 기반 (날짜 정규식 기반)
                date_el = page.locator(".layout-column-middle .d-flex.align-items-center.justify-content-between div").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                
                if not date:
                    date_el2 = page.locator(".layout-column-middle .date, .layout-column-middle time").first
                    if date_el2.is_visible():
                        date = date_el2.inner_text().strip()
                        
                # Date: 등 불필요한 문자열 제거
                if date:
                    date = date.replace("Date:", "").strip()

                # 본문(기사 텍스트와 이미지) : body > div:nth-child(3) > div.layout-wrapper.three-column-layout > div > div > div.layout-column-middle > main 
                content_el = page.locator(".layout-column-middle main").first
                if not content_el.is_visible():
                    content_el = page.locator(".layout-column-middle .content").first
                    
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
    print("IATA 크롤러 시작...")
    crawled_data = crawl_iata()
    
    output_file = 'iata_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

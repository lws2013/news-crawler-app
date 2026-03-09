import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_oceanpress():
    results = []
    
    with sync_playwright() as p:
        # headless=True로 설정하면 브라우저 창이 보이지 않음
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("OceanPress 메인 페이지 접속 중...")
        # 1. 메인 목록 페이지 접속
        page.goto("https://www.oceanpress.co.kr/news/article_list_all.html")
        page.wait_for_load_state("domcontentloaded")
        
        # 2. 전체 기사 리스트 'art_list_all' 내에서 링크 추출
        # 'art_list_all' 클래스 내부의 아이템들을 조회합니다.
        # 보통 ul > li 형태이거나 div 형태일 수 있으므로 a 태그를 바로 찾습니다.
        items = page.locator(".art_list_all a").element_handles()
        
        links = []
        for a_tag in items:
            href = a_tag.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                
                # 기사 상세 페이지 링크인지 확인 (보통 article.html?id= 등의 패턴)
                # OceanPress의 파라미터 구조에 따라 다를 수 있으나 일단 중복 제거 후 추가합니다.
                if href not in links and "article.html" in href:
                    links.append(href)
                    if len(links) >= 5:
                        break
                        
        # 클래스에 직접 a 태그가 없는 경우 다른 방식으로 시도
        if not links:
            print(".art_list_all 내부에서 링크를 찾지 못했습니다. 일반적인 기사 링크를 시도합니다.")
            all_links = page.locator("a[href*='article.html']").element_handles()
            for a_tag in all_links:
                href = a_tag.get_attribute("href")
                if href:
                    href = urllib.parse.urljoin(page.url, href)
                    if href not in links:
                        links.append(href)
                        if len(links) >= 5:
                            break
                            
        print(f"추출할 기사 링크 {len(links)}개: {links}")
        
        # 3. 상세 페이지 크롤링
        for i, link in enumerate(links):
            print(f"[{i+1}/{len(links)}] 상세 페이지 크롤링 중: {link}")
            try:
                page.goto(link)
                page.wait_for_load_state("domcontentloaded")
                
                # 카테고리 (path_wrap)
                category = ""
                cat_el = page.locator(".path_wrap").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 제목, 부제목, 날짜 정보 (art_top)
                title = ""
                subtitle = ""
                date = ""
                
                art_top_el = page.locator(".art_top").first
                if art_top_el.is_visible():
                    # 제목 (h2)
                    title_el = art_top_el.locator("h2").first
                    if title_el.is_visible():
                        title = title_el.inner_text().strip()
                        
                    # 부제목 (h3)
                    subtitle_el = art_top_el.locator("h3").first
                    if subtitle_el.is_visible():
                        subtitle = subtitle_el.inner_text().strip()
                        
                    # 날짜 - 보통 ul > li에 날짜, 기자명 등이 섞여있음
                    # li 텍스트들 중 날짜 형식(예: 2024-01-01)이 포함된 것을 찾거나 전체 텍스트 수집
                    date_els = art_top_el.locator("ul li").element_handles()
                    for li in date_els:
                        li_text = li.inner_text().strip()
                        if "-" in li_text and ":" in li_text: # 예: 2024-02-27 10:00
                            date = li_text
                            break
                        # 날짜를 못 찾으면 일단 첫 번째 요소를 날짜로 간주할 수도 있음
                    if not date and date_els:
                        date = date_els[0].inner_text().strip()
                    
                # 본문(기사 텍스트) (cnt_view news_body_area)
                # 다중 클래스일 수 있으므로 .cnt_view 또는 .news_body_area 로 시도
                content_el = page.locator(".cnt_view.news_body_area, .cnt_view, .news_body_area").first
                
                content = ""
                image_urls = []
                
                if content_el.is_visible():
                    content = content_el.inner_text().strip()
                    
                    # 본문 내 이미지 정보 (url 형태 리스트)
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
                    "subtitle": subtitle,
                    "date": date,
                    "content": content,
                    "images": image_urls
                })
            except Exception as e:
                print(f"Error scraping detail page {link}: {e}")
                
        browser.close()
        
    return results

if __name__ == "__main__":
    print("OceanPress 크롤러 시작...")
    crawled_data = crawl_oceanpress()
    print("\n[크롤링 결과]")
    # JSON 형태로 이쁘게 출력
    with open('oceanpress_result.json', 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print("\n결과가 oceanpress_result.json 파일로 저장되었습니다.")

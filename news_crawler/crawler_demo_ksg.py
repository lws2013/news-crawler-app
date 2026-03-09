import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_ksg():
    results = []
    
    with sync_playwright() as p:
        # 가시성을 위해 headless=True로 둡니다 (False면 브라우저가 보임)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("메인 페이지 접속 중...")
        # 1. 메인 목록 페이지 접속
        page.goto("https://www.ksg.co.kr/news/main_news.jsp")
        page.wait_for_load_state("domcontentloaded")
        
        # 2. 뉴스 목록에서 5개 추출
        # .new_list 안의 <li> 하위를 조회합니다.
        items = page.locator(".new_list li").element_handles()
        if not items:
            items = page.locator(".news_list li").element_handles()
            
        links = []
        for li in items:
            # 각 li 태그 내에서 첫 번째 a 태그의 href만 가져옵니다.
            a_tag = li.query_selector("a")
            if a_tag:
                href = a_tag.get_attribute("href")
                if href:
                    href = urllib.parse.urljoin(page.url, href)
                    if href not in links:
                        links.append(href)
                        if len(links) >= 5:
                            break
                        
        # 위 방식(클래스 이름 기반)으로 찾지 못했을 경우 대체 선택자 사용 (뉴스 상세 링크)
        if not links:
            print(".new_list 클래스 또는 링크를 찾지 못해 일반 링크 추출을 시도합니다.")
            all_links = page.locator("a[href*='main_newsView.jsp?pNum=']").element_handles()
            for a_tag in all_links:
                href = a_tag.get_attribute("href")
                if href:
                    href = urllib.parse.urljoin(page.url, href)
                    links.append(href)

        # 중복 제거 (순서 리스트 유지)
        unique_links = []
        for link in links:
            if link not in unique_links:
                unique_links.append(link)
                
        # 5개만 추출
        unique_links = unique_links[:5]
        
        print(f"추출할 기사 링크 {len(unique_links)}개: {unique_links}")
        
        # 3. 상세 페이지 크롤링
        for i, link in enumerate(unique_links):
            print(f"[{i+1}/5] 상세 페이지 크롤링 중: {link}")
            try:
                page.goto(link)
                page.wait_for_load_state("domcontentloaded")
                
                # 카테고리
                category = ""
                cat_el = page.locator("#categorySpace").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 날짜
                date = ""
                date_el = page.locator("#newsRegDate").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    
                # 제목
                title = ""
                title_el = page.locator("#newsTitle").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 서브제목
                subtitle = ""
                sub_el = page.locator("#newsSubTitle1").first
                if sub_el.is_visible():
                    subtitle = sub_el.inner_text().strip()
                    
                # 뉴스 본문 
                content = ""
                content_el = page.locator("#newsContent").first
                if content_el.is_visible():
                    content = content_el.inner_text().strip()
                    
                # 본문 내 이미지 정보 (url 형태 리스트)
                image_urls = []
                # 본문 내부의 img 태그만 추출
                img_els = page.locator("#newsContent img").element_handles()
                for img in img_els:
                    src = img.get_attribute("src")
                    if src:
                        src = urllib.parse.urljoin(page.url, src)
                        image_urls.append(src)
                        
                results.append({
                    "url": link,
                    "category": category,
                    "date": date,
                    "title": title,
                    "subtitle": subtitle,
                    "content": content,
                    "images": image_urls
                })
            except Exception as e:
                print(f"Error scraping detail page {link}: {e}")
                
        browser.close()
        
    return results

if __name__ == "__main__":
    print("크롤러 시작...")
    crawled_data = crawl_news()
    print("\n[크롤링 결과]")
    # JSON 형태로 이쁘게 출력
    with open('ksg_result.json', 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
    
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print("\n결과가 ksg_result.json 파일로 저장되었습니다.")

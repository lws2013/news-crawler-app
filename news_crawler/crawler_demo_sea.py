import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_sea():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Sea-Intelligence 메인 페이지 접속 중...")
        page.goto("https://www.sea-intelligence.com/press-room")
        page.wait_for_load_state("domcontentloaded")
        
        # 전체 기사 리스트에서 링크 추출
        items = page.locator(".uk-container a[href^='/press-room/']").element_handles()
        
        links = []
        import re
        for x in items:
            href = x.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                # 동일 기사 중복 수집 방지 및 상세 페이지(숫자 ID 포함)인지 확인
                if href not in links and re.search(r"/press-room/\d+", href):
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
                page.wait_for_timeout(1000)
                
                category = ""
                title = ""
                date = ""
                
                # 날짜 및 카테고리
                # ul class="uk-margin-small-top uk-margin-remove-bottom uk-subnav uk-subnav-divider uk-flex-center"
                subnav_els = page.locator("ul.uk-subnav.uk-subnav-divider li").element_handles()
                if len(subnav_els) >= 1:
                    date = subnav_els[0].inner_text().strip()
                if len(subnav_els) >= 2:
                    category = subnav_els[1].inner_text().strip()
                
                # 제목 : h1.uk-article-title
                title_el = page.locator("h1.uk-article-title").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 본문(기사 텍스트와 이미지)
                content_el = page.locator("[property='text'], .uk-container.uk-container-small").first
                
                content = ""
                image_urls = []
                
                if content_el.is_visible():
                    content = content_el.inner_text().strip()
                    
                    # 본문 내 이미지 정보 (img 태그 추출)
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
    print("Sea-Intelligence 크롤러 시작...")
    crawled_data = crawl_sea_intelligence()
    
    output_file = 'sea_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

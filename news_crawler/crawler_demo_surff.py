import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_surff():
    results = []
    
    with sync_playwright() as p:
        # headless=True로 설정하면 브라우저 창이 보이지 않음
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("SURFF 블로그 메인 페이지 접속 중...")
        # 1. 메인 목록 페이지 접속
        page.goto("https://surff.kr/blog")
        page.wait_for_load_state("domcontentloaded")
        
        # 블로그 목록이 스크립트로 렌더링될 수 있으므로 잠시 대기
        page.wait_for_timeout(2000) 
        
        # 2. 전체 기사 리스트에서 5개의 링크 추출
        # 제공해주신 XPath: /html/body/section/section/div[5]/ul
        # 내부의 a 태그들을 수집합니다.
        
        xpath_list = "/html/body/section/section/div[5]/ul//a"
        items = page.locator(f"xpath={xpath_list}").element_handles()
        
        links = []
        for a_tag in items:
            href = a_tag.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                # 동일한 링크 중복 방지 (보통 썸네일과 제목 둘 다 a 태그로 묶여있음)
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
                # SPA 렌더링을 위해 networkidle 대기
                page.wait_for_load_state("networkidle")
                # 동적 렌더링을 위해 충분히 대기
                page.wait_for_timeout(3000) 
                
                category = ""
                title = ""
                date = ""
                
                # 카테고리 (XPath: /html/body/div[3]/section/section/div/p)
                cat_el = page.locator("xpath=/html/body/div[3]/section/section/div/p").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 제목 (XPath: /html/body/div[3]/section/section/div/h2)
                title_el = page.locator("xpath=/html/body/div[3]/section/section/div/h2").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 날짜 (XPath: /html/body/div[3]/section/section/div/ul)
                date_el = page.locator("xpath=/html/body/div[3]/section/section/div/ul").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    
                # 본문(기사 텍스트와 이미지) (XPath: /html/body/div[3]/section/section/div/div/div)
                content_el = page.locator("xpath=/html/body/div[3]/section/section/div/div/div").first
                
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
    print("SURFF 크롤러 시작...")
    crawled_data = crawl_surff()
    
    output_file = 'surff_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

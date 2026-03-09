import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_flexport():
    results = []
    
    with sync_playwright() as p:
        # headless=True로 설정하면 브라우저 창이 보이지 않음
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Flexport 메인 페이지 접속 중...")
        # 1. 메인 목록 페이지 접속
        page.goto("https://www.flexport.com/global-logistics-update/")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000) # 동적 로딩이 있을 수 있으므로 대기
        
        # 2. 전체 기사 리스트에서 링크 5개 추출
        # 제공된 정보: list 내에 listitem 영역
        # role="list" 와 role="listitem" 일 확률이 높거나 class 이름일 수 있습니다.
        # 가장 보편적인 방법으로 listitem 내부의 a 태그를 찾습니다.
        items = page.locator('[role="list"] [role="listitem"] a, .list .listitem a').element_handles()
        
        links = []
        for x in items:
            href = x.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                if href not in links:
                    links.append(href)
                    if len(links) >= 5:
                        break
                        
        # 만약 위 조건으로 찾지 못했다면 해당 섹션에 article 이나 컨테이너 내 a 태그 수집
        if not links:
            print("지정된 리스트 항목에서 링크를 못 찾아 일반적인 방식으로 기사 링크를 시도합니다.")
            all_links = page.locator("a[href*='/global-logistics-update/']").element_handles()
            for a_tag in all_links:
                href = a_tag.get_attribute("href")
                if href and href != page.url: # 메인 페이지 자기 자신은 제외
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
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                
                category = ""
                title = ""
                date = ""
                
                # class="fp-zp" 본문 영역 혹은 헤더
                # eyebrow 카테고리 : .eyebrow 
                cat_el = page.locator(".eyebrow").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 제목 : h1, .fp-Gp
                title_el = page.locator("h1, .fp-Gp").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 날짜 : p.fp-Lu 또는 p 요소 중 날짜가 있는 텍스트
                date_el = page.locator("p.fp-Lu").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                else:
                    # 못 찾으면 p 태그 중 Month dd, yyyy 포맷을 찾음
                    all_ps = page.locator("p").element_handles()
                    for p_tag in all_ps[:10]: # 상단에 위치할 확률이 높으므로
                        text = p_tag.inner_text().strip()
                        import re
                        if re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$", text):
                            date = text
                            break
                    
                # 본문 : /html/body/div[2]/div[1]/div/main/div[2]/section[1]/section[1]/div[1] 또는 .fp-nm.fp-qm
                # 다중 클래스이므로 .fp-nm.fp-qm 으로 시도하거나 XPath 사용
                content_el = page.locator(".fp-nm.fp-qm").first
                if not content_el.is_visible():
                    content_el = page.locator("xpath=/html/body/div[2]/div[1]/div/main/div[2]/section[1]/section[1]/div[1]").first
                
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
    print("Flexport 크롤러 시작...")
    crawled_data = crawl_flexport()
    
    output_file = 'flexport_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

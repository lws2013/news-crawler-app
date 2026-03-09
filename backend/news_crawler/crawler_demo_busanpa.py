import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_busanpa():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("BusanPA 메인 페이지 접속 중...")
        page.goto("https://www.busanpa.com/kor/Board.do?mCode=MN2035")
        page.wait_for_load_state("domcontentloaded")
        
        # 목록 추출
        # #container > div.contents > div:nth-child(2) > div.board.list.tac 내부의 a 태그 찾기
        items = page.locator(".board.list.tac a[onclick^='view(']").element_handles()
        
        links = []
        import re
        for x in items:
            onclick = x.get_attribute("onclick")
            if onclick and "view(" in onclick:
                match = re.search(r"view\s*\(\s*'([^']+)'\s*\)", onclick)
                if match:
                    idx = match.group(1)
                    # 실제 기사 상세페이지 형태
                    detail_url = f"https://www.busanpa.com/kor/Board.do?mode=view&mCode=MN2035&idx={idx}"
                    if detail_url not in links:
                        links.append(detail_url)
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
                
                # 카테고리 : #container > div.location > div > ul 내 button
                # button 들의 텍스트를 " > " 로 연결
                buttons = page.locator("#container > div.location > div > ul button").element_handles()
                if not buttons:
                    # button이 아니라 li일 수도 있으니 대체
                    buttons = page.locator("#container > div.location > div > ul li").element_handles()
                
                if buttons:
                    cat_texts = [b.inner_text().strip() for b in buttons if b.inner_text().strip()]
                    category = " > ".join(cat_texts)
                
                # 제목 : #container > div.contents > div:nth-child(4) > div.board.view > h3
                title_el = page.locator("#container > div.contents > div.board.view > h3").first
                if not title_el.is_visible():
                    # 구조가 약간 다를 수 있으니 .board.view h3 로 포괄적 지정
                    title_el = page.locator(".board.view h3").first
                    
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                
                # 날짜 : #container > div.contents > div:nth-child(4) > div.board.view > div.row.info > div.grid-2.init.tar.md-dn > dl > dd > span
                date_el = page.locator("#container > div.contents > div:nth-child(4) > div.board.view > div.row.info > div.grid-2.init.tar.md-dn > dl > dd > span").first
                if not date_el.is_visible():
                    date_el = page.locator(".board.view .row.info .grid-2 dd span").first
                
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    import re
                    # 만약 날짜 이외에 작성자명 등이 같이 섞여나올 경우 대비하여 포맷 파싱
                    # 예: 2026-02-24
                    match = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", date)
                    if match:
                        date = match.group(0)
                        
                # 본문(기사 텍스트와 이미지) : #container > div.contents > div:nth-child(4) > div.board.view > div.con
                content_el = page.locator("#container > div.contents > div:nth-child(4) > div.board.view > div.con").first
                if not content_el.is_visible():
                    content_el = page.locator(".board.view .con").first
                
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
    print("BusanPA 크롤러 시작...")
    crawled_data = crawl_busanpa()
    
    output_file = 'busanpa_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_ulogistics():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("ULogistics 메인 페이지 접속 중...")
        page.goto("http://www.ulogistics.co.kr/test/board.php?board=all2")
        page.wait_for_load_state("domcontentloaded")
        
        # 기사 목록 추출 (5개)
        # a href="board.php?board=all2&command=body&no=..." 형태 추출
        items = page.locator("a[href*='board=all2&command=body&no=']").element_handles()
        
        links = []
        for x in items:
            href = x.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                # 추출된 링크들이 중복될 수 있으므로 (제목, 이미지 썸네일 등)
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
                
                category = ""
                title = ""
                date = ""
                
                # 제목 : #mainTextBodyDiv > div > table > tbody > tr:nth-child(1) > td
                title_el = page.locator("#mainTextBodyDiv > div > table > tbody > tr:nth-child(1) > td").first
                if title_el.is_visible():
                    # 텍스트 전체에서 카테고리 텍스트 등을 분리할 수 있음
                    title = title_el.inner_text().strip()
                
                # 카테고리 : #mainTextBodyDiv > div > table > tbody > tr:nth-child(1) > td > span
                cat_el = page.locator("#mainTextBodyDiv > div > table > tbody > tr:nth-child(1) > td > span").first
                if cat_el.is_visible():
                    category_raw = cat_el.inner_text().strip()
                    # 제목 태그 안쪽에 카테고리가 같이 들어있는 경우 분리
                    if category_raw and category_raw in title:
                        title = title.replace(category_raw, "").strip()
                    # 괄호 제거 (예: "(보관운송)" -> "보관운송")
                    category = category_raw.strip("()[] ")

                # 날짜 : #mainTextBodyDiv > div > table > tbody > tr:nth-child(4) > td > table > tbody > tr > td.b_detail_right
                date_el = page.locator("#mainTextBodyDiv > div > table > tbody > tr:nth-child(4) > td > table > tbody > tr > td.b_detail_right").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    import re
                    match = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", date)
                    if match:
                        date = match.group(0)

                # 본문(기사 텍스트와 이미지) : #mainTextBodyDiv > table:nth-child(3) > tbody > tr
                content_el = page.locator("#mainTextBodyDiv > table:nth-child(3) > tbody > tr").first
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
    print("ULogistics 크롤러 시작...")
    crawled_data = crawl_ulogistics()
    
    output_file = 'ulogistics_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_kita():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("KITA 메인 페이지 접속 중...")
        page.goto("https://www.kita.net/shippers/board/newsList.do")
        page.wait_for_load_state("domcontentloaded")
        
        # 2. 기사 리스트에서 링크 5개 추출
        # KITA는 goDetailPage('2', 'B', '7975') 같은 자바스크립트 함수로 이동함
        # a 태그의 href가 javascript:goDetailPage... 형태이거나 자식 요소일 수 있음.
        # 가장 확실하게 a 태그 중 onclick이나 href에 goDetailPage가 포함된 것을 찾습니다.
        
        # ul class="board-list box box-radius theme-board3" 이하의 링크 수집
        items = page.locator(".board-list.box.box-radius.theme-board3 a").element_handles()
        
        links = []
        for x in items:
            href = x.get_attribute("href") or ""
            onclick = x.get_attribute("onclick") or ""
            
            target_str = href if "goDetailPage" in href else onclick
            if "goDetailPage" in target_str:
                # goDetailPage('2', 'B', '7975') 이런 형태에서 파라미터 추출
                # 좀 더 안전하고 범용적으로 처리하기 위해 그냥 해당 링크(자바스크립트)를 클릭해서 페이지 이동하는 대신 
                # 파라미터를 파싱해서 URL을 직접 만들거나, 평가(evaluate)를 활용
                import re
                match = re.search(r"goDetailPage\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)", target_str)
                if match:
                    group1 = match.group(1)
                    group2 = match.group(2)
                    id_val = match.group(3)
                    # 실제 이동하는 주소 패턴 분석 (개발자 도구 확인 결과: bbsNo 등 파라미터로 처리)
                    # 실제 이동하는 주소 패턴 수정
                    # newsView.do?morgueCode=2&dataCls=B&dataSeq=7975
                    detail_url = f"https://www.kita.net/shippers/board/newsView.do?morgueCode={group1}&dataCls={group2}&dataSeq={id_val}"
                    if detail_url not in links:
                        links.append(detail_url)
                        if len(links) >= 5:
                            break
                            
        print(f"추출할 기사 링크 {len(links)}개: {links}")
        
        # 3. 상세 페이지 크롤링
        for i, link in enumerate(links):
            print(f"[{i+1}/{len(links)}] 상세 페이지 크롤링 중: {link}")
            try:
                page.goto(link)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)
                
                category = ""
                title = ""
                date = ""
                
                # 카테고리 : .badge.cate-tag
                cat_el = page.locator(".badge.cate-tag").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 제목 : .subject
                title_el = page.locator(".subject").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 날짜 : .badge.write
                date_el = page.locator(".badge.write").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    # 작성\n2026.02.26 같은 형식이라면 앞의 "작성"을 제거
                    if "작성" in date:
                        date = date.replace("작성", "").strip()
                    
                # 본문 : .detail-body.caption.para
                content_el = page.locator(".detail-body.caption.para").first
                content = ""
                image_urls = []
                
                if content_el.is_visible():
                    content = content_el.inner_text().strip()
                    
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
    crawled_data = crawl_kita()
    output_file = 'kita_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))

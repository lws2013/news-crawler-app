import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_kotra():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("KOTRA 메인 페이지 접속 중...")
        page.goto("https://dream.kotra.or.kr/kotranews/cms/com/index.do?MENU_ID=70")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000) # JS 템플릿 로딩 대기
        
        # 기사 목록 및 pNttSn 추출
        items = page.locator(".nttTr a[data-source]").element_handles()
        
        links = []
        for x in items:
            source_id = x.get_attribute("data-source")
            if source_id:
                # 사용자가 제공한 긴 URL 패턴 중 pNttSn 변수만 필수라고 보고 구성
                # 뉴스 공통 쿼리 매개변수 적용
                detail_url = f"https://dream.kotra.or.kr/kotranews/cms/news/actionKotraBoardDetail.do?SITE_NO=3&MENU_ID=70&CONTENTS_NO=1&pNttSn={source_id}"
                if detail_url not in links:
                    links.append(detail_url)
                    if len(links) >= 9:
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
                
                # 카테고리 : txtInfo 내 categ
                cat_el = page.locator(".txtInfo .categ").first
                if cat_el.is_visible():
                    category = cat_el.inner_text().strip()
                
                # 날짜 : txtInfo 내 date
                date_el = page.locator(".txtInfo .date").first
                if date_el.is_visible():
                    date = date_el.inner_text().strip()
                    import re
                    match = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", date)
                    if match:
                        date = match.group(0)

                # 제목 : txtL
                # 클래스가 여러개 쓰일 수 있으므로 포괄적 처리
                title_el = page.locator(".txtL").first
                if title_el.is_visible():
                    title = title_el.inner_text().strip()
                    
                # 본문(기사 텍스트와 이미지) : view_txt
                content_el = page.locator(".view_txt").first
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
                
                # 첨부파일 영역 : fileArea fileTr
                attach_urls = []
                file_els = page.locator(".fileArea ul li a[data-atfilesn]").element_handles()
                for f_el in file_els:
                    onclick = f_el.get_attribute("onclick")
                    atfilesn = f_el.get_attribute("data-atfilesn")
                    
                    if onclick and "fn_fileDown" in onclick and atfilesn:
                        match = re.search(r"pNttSn=(\d+)", link)
                        if match:
                            nttSn = match.group(1)
                            # gbn=n01, pFrontYn=Y 파라미터가 사용됨
                            down_url = f"https://dream.kotra.or.kr/ajaxa/fileCpnt/fileDown.do?gbn=n01&nttSn={nttSn}&atFileSn={atfilesn}&pFrontYn=Y"
                            
                            filename_text = f_el.inner_text().strip()
                            if not filename_text:
                                filename_text = f_el.get_attribute("data-filename") or "download"
                                
                            attach_info_str = f"[{filename_text}]({down_url})"
                            if attach_info_str not in attach_urls:
                                attach_urls.append(attach_info_str)
                        
                results.append({
                    "url": link,
                    "category": category,
                    "title": title,
                    "date": date,
                    "content": content,
                    "images": image_urls,
                    "attachments": attach_urls
                })
            except Exception as e:
                print(f"Error scraping detail page {link}: {e}")
                
        browser.close()
        
    return results

if __name__ == "__main__":
    print("KOTRA 크롤러 시작...")
    crawled_data = crawl_kotra()
    
    output_file = 'kotra_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

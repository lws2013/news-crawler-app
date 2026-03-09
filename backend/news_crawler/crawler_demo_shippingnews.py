import json
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_shippingnews():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("ShippingNewsNet 메인 페이지 접속 중...")
        page.goto("https://www.shippingnewsnet.com/news/articleList.html?sc_section_code=S1N1&view_type=sm")
        page.wait_for_load_state("domcontentloaded")
        
        # 2. 전체 기사 리스트 section-list 내에서 링크 5개 추출
        items = page.locator(".section-list a, #section-list a").element_handles()
        
        links = []
        for a_tag in items:
            href = a_tag.get_attribute("href")
            if href:
                href = urllib.parse.urljoin(page.url, href)
                
                # 기사 상세 페이지 링크인지 확인
                if href not in links and "articleView.html" in href:
                    links.append(href)
                    if len(links) >= 5:
                        break
                        
        if not links:
            print("section-list 내부에서 링크를 찾지 못했습니다. 일반적인 기사 링크를 시도합니다.")
            all_links = page.locator("a[href*='articleView.html']").element_handles()
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
                
                category = ""
                title = ""
                subtitle = ""
                date = ""
                
                # 카테고리, 제목, 부제목, 날짜 (article-view-header)
                header_el = page.locator(".article-view-header").first
                if header_el.is_visible():
                    # 카테고리 (breadcrumbs 내 텍스트 합치기)
                    breadcrumb_els = header_el.locator(".breadcrumbs a, .breadcrumbs span").element_handles()
                    if breadcrumb_els:
                        cat_texts = [el.inner_text().strip() for el in breadcrumb_els if el.inner_text().strip() and el.inner_text().strip() != ">"]
                        category = " > ".join(cat_texts)
                        if not category:
                            category = header_el.locator(".breadcrumbs").inner_text().strip().replace("\n", " > ")
                        
                    # 제목 (.heading)
                    title_el = header_el.locator(".heading").first
                    if title_el.is_visible():
                        title = title_el.inner_text().strip()
                    else:
                        title_el = header_el.locator(".article-head-title, h3").first
                        if title_el.is_visible():
                            title = title_el.inner_text().strip()
                            
                    # 부제목 (sub-title)
                    subtitle_el = header_el.locator(".article-head-sub").first
                    if subtitle_el.is_visible():
                        subtitle = subtitle_el.inner_text().strip()
                        
                    # 날짜 (li.date, info-date 등)
                    date_els = header_el.locator("li").element_handles()
                    for li in date_els:
                        li_text = li.inner_text().strip()
                        if "기자" not in li_text and ("-" in li_text or "." in li_text or ":" in li_text):
                            date = li_text
                            break
                    
                # 본문(기사 텍스트와 이미지) (article-body)
                content_el = page.locator(".article-body").first
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
    print("ShippingNewsNet 크롤러 시작...")
    crawled_data = crawl_shippingnews()
    
    output_file = 'shippingnews_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
        
    print("\n[크롤링 결과]")
    print(json.dumps(crawled_data, ensure_ascii=False, indent=4))
    print(f"\n결과가 {output_file} 파일로 저장되었습니다.")

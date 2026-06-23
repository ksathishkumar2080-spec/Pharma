"""Scrapy spider for BioCentury pipeline/competitor intelligence."""
import scrapy


class BioCenturySpider(scrapy.Spider):
    name = "biocentury"
    allowed_domains = ["biocentury.com"]
    start_urls = ["https://www.biocentury.com/oncology"]

    custom_settings = {
        "USER_AGENT": "OncologyIntelBot/1.0",
        "DOWNLOAD_DELAY": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        for article in response.css("article, .article-item, .news-item"):
            title = article.css("h2::text, h3::text, .title::text").get("").strip()
            url = article.css("a::attr(href)").get("")
            summary = article.css(".summary::text, .excerpt::text, p::text").get("").strip()
            if title:
                yield {
                    "source": "BioCentury",
                    "title": title,
                    "url": response.urljoin(url),
                    "summary": summary,
                }
        next_page = response.css(".pagination a.next::attr(href), a[rel=next]::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

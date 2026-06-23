"""Scrapy spider for CancerGRACE community discussions."""
import scrapy


class CancerGRACESpider(scrapy.Spider):
    name = "cancergrace"
    allowed_domains = ["cancergrace.org"]
    start_urls = ["https://cancergrace.org/forums"]

    custom_settings = {
        "USER_AGENT": "OncologyIntelBot/1.0",
        "DOWNLOAD_DELAY": 3,
    }

    def parse(self, response):
        for topic in response.css(".topic, .forum-topic, li.topic-item"):
            title = topic.css("a::text").get("").strip()
            url = topic.css("a::attr(href)").get("")
            if title:
                yield {"source": "CancerGRACE", "title": title, "url": response.urljoin(url)}

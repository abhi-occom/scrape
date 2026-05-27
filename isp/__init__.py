"""
ISP Mini Crawler Module
-----------------------
Auto-discovers plan pages from any ISP URL and scrapes
NBN, Opticomm, RedTrain, and Supa plan details.

Usage:
    from isp.main_crawler import ISPCrawler
    crawler = ISPCrawler("https://www.telstra.com.au/internet")
    results = crawler.run()
"""
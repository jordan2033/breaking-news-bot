#!/usr/bin/env python3
"""
Breaking News Bot for GitHub Actions - 2026 Market Edition
Focus: ES (S&P 500) and NQ (Nasdaq) High-Impact Triggers
"""

import os
import sys
import feedparser
import requests
from datetime import datetime
import hashlib

# ============================================
# CONFIGURATION
# ============================================

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK', '')

# 2026 RELEVANT KEYWORDS
# Categorized for clarity (Internal logic uses the flat list)
MACRO_ECON = [
    "FOMC", "FED RATE", "INTEREST RATE", "INFLATION", "CPI", "PPI", 
    "NFP", "NONFARM PAYROLLS", "UNEMPLOYMENT", "YIELD CURVE", "10Y"
]

POLICY_2026 = [
    "OBBBA", "TAX CUT", "DEREGULATION", "GOVERNMENT SHUTDOWN", 
    "MIDTERM ELECTION", "SUPREME COURT TARIFF", "USMCA"
]

TECH_AI_NQ = [
    "AI MONETIZATION", "RUBIN CHIP", "SEMICONDUCTOR TARIFF", 
    "QUANTUM COMPUTING", "SOVEREIGN AI", "HYPERSCALER CAPEX", "CES 2026"
]

GEOPOLITICAL_ENERGY = [
    "VENEZUELA OIL", "MADURO", "CRUDE OIL", "OPEC+", "TAIWAN STRAIT", 
    "TRADE WAR", "CHINA EXPORT BAN", "LITHIUM SUPPLY"
]

# Combined list for the bot
MAJOR_KEYWORDS = MACRO_ECON + POLICY_2026 + TECH_AI_NQ + GEOPOLITICAL_ENERGY
# Add urgent triggers
URGENT_TRIGGERS = ["BREAKING", "URGENT", "ALERT", "HALT", "FLASH"]

RSS_FEEDS = [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&format=rss"},
    {"name": "Investing.com", "url": "https://www.investing.com/rss/news.rss"},
    {"name": "MarketWatch", "url": "http://feeds.marketwatch.com/marketwatch/topstories/"}
]

# ============================================
# BOT CLASS
# ============================================

class BreakingNewsBot:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.seen_news = set()
        
    def is_major_news(self, title):
        title_upper = title.upper()
        
        # Priority 1: High-alert words
        if any(word in title_upper for word in URGENT_TRIGGERS):
            return True
        
        # Priority 2: 2026 Market Keywords
        if any(keyword in title_upper for keyword in MAJOR_KEYWORDS):
            return True
        
        return False
    
    def fetch_news(self):
        all_news = []
        for feed in RSS_FEEDS:
            try:
                print(f"📡 Checking {feed['name']}...")
                feed_data = feedparser.parse(feed['url'])
                
                for entry in feed_data.entries[:15]: # Slightly more depth
                    if self.is_major_news(entry.title):
                        news_id = hashlib.md5(f"{entry.title}".encode()).hexdigest()
                        
                        if news_id not in self.seen_news:
                            all_news.append({
                                "title": entry.title,
                                "link": entry.link,
                                "source": feed['name'],
                                "published": entry.get('published', 'Recent'),
                                "id": news_id
                            })
                            self.seen_news.add(news_id)
                            
            except Exception as e:
                print(f"❌ Error with {feed['name']}: {e}")
        return all_news
    
    def send_to_discord(self, news_item):
        # Determine if it's a "Mega Alert" for coloring
        is_urgent = any(word in news_item['title'].upper() for word in URGENT_TRIGGERS)
        color = 0xFF0000 if is_urgent else 0x00ff00 # Red for urgent, Green for news

        message = {
            "username": "2026 Futures Edge",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2491/2491417.png",
            "embeds": [{
                "title": f"🔔 {news_item['title']}",
                "url": news_item['link'],
                "color": color,
                "fields": [
                    {"name": "Source", "value": news_item['source'], "inline": True},
                    {"name": "Status", "value": "🚨 HIGH IMPACT" if is_urgent else "📊 Market Info", "inline": True}
                ],
                "footer": {"text": f"2026 Market Pulse • {news_item['published']}"},
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        try:
            response = requests.post(self.webhook_url, json=message)
            return response.status_code == 204
        except Exception as e:
            print(f"❌ Discord Error: {e}")
            return False

    def run_once(self):
        if not self.webhook_url:
            print("❌ ERROR: No Discord webhook configured!")
            return
        
        major_news = self.fetch_news()
        
        if not major_news:
            print("✅ No new major market movers found.")
            return
        
        # Sort or filter for the very latest
        for news in major_news[:5]: 
            self.send_to_discord(news)
            print(f"✅ Alert Sent: {news['title'][:60]}...")

def main():
    webhook_url = os.environ.get('DISCORD_WEBHOOK', '')
    bot = BreakingNewsBot(webhook_url)
    bot.run_once()

if __name__ == "__main__":
    main()

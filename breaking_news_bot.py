#!/usr/bin/env python3
"""
Breaking News Bot for GitHub Actions
Optimized for scheduled execution
"""

import os
import sys
import feedparser
import requests
from datetime import datetime
import hashlib
import json

# ============================================
# CONFIGURATION
# ============================================

# Discord webhook URL will come from GitHub Secrets
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK', '')

# Keywords to watch for (same as before)
MAJOR_KEYWORDS = [
    "FOMC", "FEDERAL RESERVE", "FED RATE", "INTEREST RATE",
    "CPI", "CONSUMER PRICE INDEX", "INFLATION",
    "PPI", "PRODUCER PRICE INDEX",
    "NFP", "NONFARM PAYROLLS", "JOBS REPORT", "UNEMPLOYMENT",
    "TRUMP", "ELECTION 2024", "BIDEN",
    "MARKET CRASH", "RECESSION", "OIL PRICE", "CRUDE OIL",
    "BITCOIN", "CRYPTO", "WAR", "CONFLICT"
]

RSS_FEEDS = [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Reuters", "url": "http://feeds.reuters.com/reuters/businessNews"},
    {"name": "Bloomberg", "url": "https://www.bloomberg.com/markets/rss"}
]

# ============================================
# BOT CLASS
# ============================================

class BreakingNewsBot:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.seen_news = set()
        
    def is_major_news(self, title):
        """Check if news is important"""
        title_upper = title.upper()
        
        # Check urgent words
        if any(word in title_upper for word in ["BREAKING", "URGENT", "ALERT"]):
            return True
        
        # Check major keywords
        if any(keyword in title_upper for keyword in MAJOR_KEYWORDS):
            return True
        
        return False
    
    def fetch_news(self):
        """Fetch and filter news"""
        all_news = []
        
        for feed in RSS_FEEDS:
            try:
                print(f"📡 Checking {feed['name']}...")
                feed_data = feedparser.parse(feed['url'])
                
                for entry in feed_data.entries[:10]:
                    if self.is_major_news(entry.title):
                        news_id = hashlib.md5(f"{entry.title}{feed['name']}".encode()).hexdigest()
                        
                        if news_id not in self.seen_news:
                            all_news.append({
                                "title": entry.title,
                                "link": entry.link,
                                "source": feed['name'],
                                "published": entry.get('published', ''),
                                "id": news_id
                            })
                            self.seen_news.add(news_id)
                            
            except Exception as e:
                print(f"❌ Error with {feed['name']}: {e}")
        
        return all_news
    
    def send_to_discord(self, news_item):
        """Send alert to Discord"""
        # Truncate if too long
        title = news_item['title']
        if len(title) > 200:
            title = title[:197] + "..."
        
        message = {
            "username": "News Alert Bot",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2491/2491417.png",
            "embeds": [{
                "title": f"🚨 {title}",
                "url": news_item['link'],
                "color": 0xFF0000,
                "fields": [
                    {"name": "Source", "value": news_item['source'], "inline": True},
                    {"name": "Time", "value": news_item['published'][:20], "inline": True}
                ],
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        try:
            response = requests.post(self.webhook_url, json=message)
            if response.status_code == 204:
                print(f"✅ Posted: {news_item['title'][:50]}...")
                return True
            else:
                print(f"❌ Failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def run_once(self):
        """Single execution for GitHub Actions"""
        print("=" * 60)
        print("🚀 GITHUB ACTIONS BREAKING NEWS BOT")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not self.webhook_url:
            print("❌ ERROR: No Discord webhook configured!")
            print("💡 Set DISCORD_WEBHOOK secret in GitHub repository settings")
            return
        
        print("🔍 Checking for breaking news...")
        major_news = self.fetch_news()
        
        if not major_news:
            print("✅ No new major breaking news found.")
            return
        
        print(f"📰 Found {len(major_news)} major news items.")
        
        # Send alerts
        for news in major_news[:3]:  # Limit to top 3
            self.send_to_discord(news)
        
        print("✅ Execution complete!")

# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main function for GitHub Actions"""
    webhook_url = os.environ.get('DISCORD_WEBHOOK', '')
    
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK environment variable not set!")
        print("💡 Add it in GitHub repository Settings → Secrets → Actions")
        sys.exit(1)
    
    bot = BreakingNewsBot(webhook_url)
    bot.run_once()

if __name__ == "__main__":
    main()

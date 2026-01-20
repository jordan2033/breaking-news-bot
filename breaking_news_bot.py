#!/usr/bin/env python3
"""
Breaking News Bot for GitHub Actions - 2026 Market Edition
Focus: ES (S&P 500) and NQ (Nasdaq) High-Impact Triggers
Optimized for GitHub Actions with rate limiting
"""

import os
import sys
import feedparser
import requests
from datetime import datetime, timedelta
import hashlib
import time
import json
from typing import List, Dict, Set
import re

# ============================================
# CONFIGURATION
# ============================================

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK', '')
SEEN_NEWS_FILE = 'seen_news.json'  # Persist across runs

# 2026 MARKET-SPECIFIC KEYWORDS (SORTED BY IMPACT)
HIGH_IMPACT_ES_NQ = [
    # FED & Monetary Policy (Highest Impact)
    "FOMC", "FED RATE DECISION", "INTEREST RATE HIKE", "INTEREST RATE CUT",
    "QUANTITATIVE TIGHTENING", "BALANCE SHEET", "POWELL", "CENTRAL BANK",
    
    # Inflation & Employment
    "CPI", "PCE", "INFLATION REPORT", "NONFARM PAYROLLS", "NFP",
    "UNEMPLOYMENT RATE", "JOLTS", "WAGE GROWTH",
    
    # Economic Indicators
    "GDP", "RECESSION", "MANUFACTURING PMI", "SERVICES PMI",
    "RETAIL SALES", "CONSUMER CONFIDENCE",
    
    # Fiscal Policy
    "GOVERNMENT SHUTDOWN", "DEBT CEILING", "BUDGET DEFICIT",
    "TAX LEGISLATION", "STIMULUS PACKAGE",
    
    # Geopolitical (Market Moving)
    "TAIWAN STRAIT", "CHINA TARIFF", "TRADE WAR", "SANCTIONS",
    "MIDDLE EAST CONFLICT", "OIL EMBARGO", "RUSSIA UKRAINE",
    
    # Technology & AI (NQ Specific)
    "AI REGULATION", "SEMICONDUCTOR BAN", "CHIP ACT", "ANTITRUST",
    "APPLE", "MICROSOFT", "NVIDIA", "META", "TESLA", "GOOGLE",
    
    # Energy & Commodities
    "OPEC+", "CRUDE OIL", "NATURAL GAS", "ENERGY CRISIS",
    "VENEZUELA OIL", "SAUDI ARAMCO",
    
    # Financial System
    "BANK FAILURE", "COMMERCIAL REAL ESTATE", "DEBT DEFAULT",
    "MONEY MARKET", "REPO MARKET", "MARGIN CALL"
]

# URGENCY TRIGGERS (Auto-highlight)
URGENT_TRIGGERS = [
    "BREAKING", "URGENT", "ALERT", "FLASH", "JUST IN",
    "HALT", "SUSPENDED", "CRASH", "PLUNGE", "SURGE",
    "EMERGENCY", "CRISIS", "WARNING"
]

# RSS FEEDS WITH PRIORITY WEIGHTS
RSS_FEEDS = [
    {
        "name": "Reuters Breaking News",
        "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "priority": 10,  # Highest
        "delay": 0.5
    },
    {
        "name": "Bloomberg Markets",
        "url": "https://www.bloomberg.com/markets/rss",
        "priority": 9,
        "delay": 0.5
    },
    {
        "name": "Financial Times US",
        "url": "https://www.ft.com/?format=rss",
        "priority": 8,
        "delay": 0.5
    },
    {
        "name": "CNBC Market News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "priority": 7,
        "delay": 0.5
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "priority": 6,
        "delay": 0.5
    },
    {
        "name": "MarketWatch Top Stories",
        "url": "http://feeds.marketwatch.com/marketwatch/topstories/",
        "priority": 5,
        "delay": 0.5
    }
]

# ============================================
# UTILITY FUNCTIONS
# ============================================

def load_seen_news() -> Set[str]:
    """Load previously seen news IDs from file"""
    try:
        if os.path.exists(SEEN_NEWS_FILE):
            with open(SEEN_NEWS_FILE, 'r') as f:
                data = json.load(f)
                
                # Clean old entries (older than 48 hours)
                cutoff_time = datetime.now() - timedelta(hours=48)
                cleaned_data = {
                    news_id: timestamp 
                    for news_id, timestamp in data.items()
                    if datetime.fromisoformat(timestamp) > cutoff_time
                }
                
                # Update file with cleaned data
                with open(SEEN_NEWS_FILE, 'w') as fw:
                    json.dump(cleaned_data, fw)
                
                return set(cleaned_data.keys())
    except Exception as e:
        print(f"⚠️ Error loading seen news: {e}")
    
    return set()

def save_seen_news(news_id: str):
    """Save a news ID to the seen file"""
    try:
        if os.path.exists(SEEN_NEWS_FILE):
            with open(SEEN_NEWS_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        
        data[news_id] = datetime.now().isoformat()
        
        with open(SEEN_NEWS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"⚠️ Error saving seen news: {e}")

def calculate_impact_score(title: str) -> int:
    """Calculate impact score for news item"""
    title_upper = title.upper()
    score = 0
    
    # Urgent triggers add high score
    for trigger in URGENT_TRIGGERS:
        if trigger in title_upper:
            score += 100
    
    # Keyword scoring (more specific = higher score)
    for keyword in HIGH_IMPACT_ES_NQ:
        if keyword in title_upper:
            # Longer keywords get higher scores (more specific)
            score += len(keyword.split()) * 10
    
    # Time sensitivity (recent keywords)
    recent_keywords = ["TODAY", "NOW", "MINUTES AGO", "JUST", "LIVE"]
    for word in recent_keywords:
        if word in title_upper:
            score += 20
    
    return score

def generate_news_id(title: str, source: str) -> str:
    """Generate unique ID for news item"""
    # Use title + first 10 chars of source for uniqueness
    combined = f"{title[:100]}_{source[:10]}"
    return hashlib.md5(combined.encode()).hexdigest()

# ============================================
# BOT CLASS
# ============================================

class BreakingNewsBot2026:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.seen_news = load_seen_news()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BreakingNewsBot/2026)'
        })
    
    def is_relevant_news(self, title: str) -> tuple[bool, int]:
        """Check if news is relevant and calculate impact score"""
        title_upper = title.upper()
        
        # Immediate rejections
        irrelevant_terms = ["SPORTS", "ENTERTAINMENT", "CELEBRITY", "RECIPE", 
                           "WEATHER", "HOROSCOPE", "GOSSIP", "FASHION"]
        if any(term in title_upper for term in irrelevant_terms):
            return False, 0
        
        # Calculate impact score
        score = calculate_impact_score(title)
        
        # Minimum threshold for relevance
        is_relevant = score >= 30  # Adjust this threshold as needed
        
        return is_relevant, score
    
    def fetch_feed(self, feed_config: Dict) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        news_items = []
        
        try:
            # Add delay between requests
            time.sleep(feed_config.get("delay", 1))
            
            print(f"📡 Checking {feed_config['name']}...")
            feed_data = feedparser.parse(feed_config['url'])
            
            if not feed_data.entries:
                print(f"  ⚠️ No entries found in {feed_config['name']}")
                return news_items
            
            for entry in feed_data.entries[:10]:  # Check top 10 per feed
                title = entry.title.strip()
                
                # Check relevance and score
                is_relevant, score = self.is_relevant_news(title)
                if not is_relevant:
                    continue
                
                # Generate unique ID
                news_id = generate_news_id(title, feed_config['name'])
                
                # Check if already seen
                if news_id in self.seen_news:
                    continue
                
                # Extract publication time
                published = entry.get('published', '')
                if not published and hasattr(entry, 'updated'):
                    published = entry.updated
                
                news_items.append({
                    "id": news_id,
                    "title": title,
                    "link": entry.link,
                    "source": feed_config['name'],
                    "published": published,
                    "score": score,
                    "priority": feed_config['priority'],
                    "summary": entry.get('summary', '')[:200]
                })
                
                # Mark as seen immediately
                self.seen_news.add(news_id)
                save_seen_news(news_id)
                
        except Exception as e:
            print(f"❌ Error fetching {feed_config['name']}: {e}")
        
        return news_items
    
    def fetch_all_news(self) -> List[Dict]:
        """Fetch news from all configured feeds"""
        all_news = []
        
        # Sort feeds by priority (highest first)
        sorted_feeds = sorted(RSS_FEEDS, key=lambda x: x['priority'], reverse=True)
        
        for feed in sorted_feeds:
            news_items = self.fetch_feed(feed)
            all_news.extend(news_items)
        
        return all_news
    
    def categorize_news(self, title: str) -> str:
        """Categorize news for Discord formatting"""
        title_upper = title.upper()
        
        # FED & Monetary
        fed_keywords = ["FOMC", "FED", "INTEREST RATE", "POWELL", "INFLATION"]
        if any(keyword in title_upper for keyword in fed_keywords):
            return "🏛️ FED/Monetary"
        
        # Economic Data
        econ_keywords = ["CPI", "NFP", "GDP", "UNEMPLOYMENT", "PMI", "RETAIL"]
        if any(keyword in title_upper for keyword in econ_keywords):
            return "📊 Economic Data"
        
        # Geopolitical
        geo_keywords = ["TAIWAN", "CHINA", "RUSSIA", "UKRAINE", "SANCTIONS", "WAR"]
        if any(keyword in title_upper for keyword in geo_keywords):
            return "🌍 Geopolitical"
        
        # Technology
        tech_keywords = ["AI", "CHIP", "SEMICONDUCTOR", "ANTITRUST", "TECH"]
        if any(keyword in title_upper for keyword in tech_keywords):
            return "🤖 Technology"
        
        # Energy
        energy_keywords = ["OIL", "OPEC", "ENERGY", "CRUDE", "GAS"]
        if any(keyword in title_upper for keyword in energy_keywords):
            return "⚡ Energy"
        
        # Financial
        fin_keywords = ["BANK", "STOCK", "MARKET", "TRADING", "INVEST"]
        if any(keyword in title_upper for keyword in fin_keywords):
            return "💹 Financial"
        
        return "📰 General"
    
    def format_discord_message(self, news_item: Dict) -> Dict:
        """Format news for Discord webhook"""
        title = news_item['title']
        is_urgent = any(word in title.upper() for word in URGENT_TRIGGERS)
        
        # Determine color based on urgency and score
        if is_urgent:
            color = 0xFF0000  # Red
            emoji = "🚨"
        elif news_item['score'] > 80:
            color = 0xFFA500  # Orange
            emoji = "⚠️"
        elif news_item['score'] > 50:
            color = 0xFFFF00  # Yellow
            emoji = "📈"
        else:
            color = 0x00FF00  # Green
            emoji = "📰"
        
        category = self.categorize_news(title)
        
        # Create summary with truncation
        summary = news_item.get('summary', '')
        if not summary:
            summary = title[:150] + ("..." if len(title) > 150 else "")
        
        embed = {
            "title": f"{emoji} {title[:200]}",
            "url": news_item['link'],
            "color": color,
            "description": summary,
            "fields": [
                {
                    "name": "Category",
                    "value": category,
                    "inline": True
                },
                {
                    "name": "Source",
                    "value": news_item['source'],
                    "inline": True
                },
                {
                    "name": "Impact Score",
                    "value": f"`{news_item['score']}/100`",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"2026 Futures Edge • {news_item['published'][:25] if news_item['published'] else 'Recent'}"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        message = {
            "username": "2026 Market Pulse",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2695/2695415.png",
            "embeds": [embed]
        }
        
        # Add mention for high-impact news
        if is_urgent or news_item['score'] > 80:
            message["content"] = "@here **High Impact Alert**"
        
        return message
    
    def send_to_discord(self, message_data: Dict) -> bool:
        """Send message to Discord"""
        try:
            response = self.session.post(
                self.webhook_url,
                json=message_data,
                timeout=10
            )
            
            if response.status_code == 204:
                return True
            else:
                print(f"❌ Discord error: {response.status_code} - {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to send to Discord: {e}")
            return False
    
    def run_once(self):
        """Single execution for GitHub Actions"""
        print("=" * 60)
        print("🚀 2026 BREAKING NEWS BOT - GITHUB ACTIONS")
        print("=" * 60)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Seen News Cache: {len(self.seen_news)} items")
        print("=" * 60)
        
        if not self.webhook_url:
            print("❌ ERROR: No Discord webhook configured!")
            print("💡 Set DISCORD_WEBHOOK secret in GitHub repository settings")
            return
        
        # Fetch all news
        all_news = self.fetch_all_news()
        
        if not all_news:
            print("✅ No new relevant market news found.")
            return
        
        print(f"📊 Found {len(all_news)} relevant news items.")
        
        # Sort by impact score (highest first)
        all_news.sort(key=lambda x: (x['score'], x['priority']), reverse=True)
        
        # Limit to top 3 to avoid rate limits
        top_news = all_news[:3]
        
        # Send alerts
        success_count = 0
        for i, news in enumerate(top_news, 1):
            print(f"\n📤 Sending alert {i}/{len(top_news)}:")
            print(f"   Title: {news['title'][:80]}...")
            print(f"   Score: {news['score']}, Source: {news['source']}")
            
            message = self.format_discord_message(news)
            if self.send_to_discord(message):
                success_count += 1
                print(f"   ✅ Sent successfully")
            else:
                print(f"   ❌ Failed to send")
            
            # Small delay between sends
            if i < len(top_news):
                time.sleep(1)
        
        print("=" * 60)
        print(f"✅ Execution complete. Sent {success_count}/{len(top_news)} alerts.")
        print(f"📈 Total seen news in cache: {len(self.seen_news)}")
        print(f"⏰ End Time: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)

# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main entry point for GitHub Actions"""
    webhook_url = os.environ.get('DISCORD_WEBHOOK', '')
    
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK environment variable not set!")
        print("💡 Add it in GitHub repository Settings → Secrets → Actions")
        sys.exit(1)
    
    # Initialize and run bot
    bot = BreakingNewsBot2026(webhook_url)
    bot.run_once()

if __name__ == "__main__":
    main()

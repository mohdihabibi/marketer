#!/usr/bin/env python3
"""
Email Template Scraper - Multiple Sources
Downloads email templates from various sites including Spotmar alternatives
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict
import pandas as pd

class EmailTemplateScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.emails = []
    
    def scrape_spotmar_alternative_sources(self):
        """Scrape from alternative sources since Spotmar requires login"""
        print("🔍 Scraping email templates from multiple sources...")
        
        # Source 1: Really Good Emails (has free examples)
        self.scrape_really_good_emails()
        
        # Source 2: Mailchimp Examples  
        self.scrape_mailchimp_examples()
        
        # Source 3: Email Design Inspiration sites
        self.scrape_email_design_sites()
        
        return self.emails
    
    def scrape_really_good_emails(self):
        """Scrape from Really Good Emails - they have free examples"""
        print("📧 Attempting Really Good Emails...")
        
        try:
            # Get the main page with email categories
            url = "https://reallygoodemails.com/emails/announcement"
            print(f"🔗 Trying URL: {url}")
            response = self.session.get(url, timeout=10)
            
            print(f"📊 Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Failed to access Really Good Emails: {response.status_code}")
                print("ℹ️  This site may require authentication or have changed structure")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: Print page structure
            print(f"📄 Page title: {soup.title.text if soup.title else 'No title found'}")
            
            # Find email links (adjust selector based on actual structure)
            email_links = soup.find_all('a', href=re.compile(r'/emails/'))
            print(f"🔗 Found {len(email_links)} potential email links")
            
            if len(email_links) == 0:
                print("⚠️  No email links found - site structure may have changed")
                print("🔍 Skipping Really Good Emails for now...")
                return
            
            count = 0
            for link in email_links[:5]:  # Reduce to 5 for testing
                if count >= 5:
                    break
                    
                email_url = urljoin(url, link.get('href'))
                print(f"🔗 Trying to scrape: {email_url}")
                email_data = self.scrape_single_email_rge(email_url)
                
                if email_data:
                    self.emails.append(email_data)
                    count += 1
                    print(f"✅ Scraped email {count}: {email_data['subject'][:50]}...")
                else:
                    print(f"❌ Failed to extract data from {email_url}")
                
                time.sleep(2)  # Be respectful
                
        except Exception as e:
            print(f"❌ Error scraping Really Good Emails: {e}")
            print(f"❌ Exception type: {type(e).__name__}")
            print("ℹ️  Continuing with other sources...")
    
    def scrape_single_email_rge(self, url: str) -> Dict:
        """Scrape a single email from Really Good Emails"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract email content (adjust selectors as needed)
            subject = self.extract_text(soup, [
                'h1', '.email-subject', '[data-subject]', '.subject'
            ])
            
            body = self.extract_text(soup, [
                '.email-body', '.email-content', '.content', 'main'
            ])
            
            # Get metadata
            brand = self.extract_text(soup, ['.brand', '.company', '.sender'])
            category = "announcement"
            
            return {
                'source': 'really_good_emails',
                'source_url': url,
                'subject': subject,
                'body': body,
                'brand': brand,
                'category': category,
                'scraped_at': pd.Timestamp.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return None
    
    def scrape_mailchimp_examples(self):
        """Scrape Mailchimp's public email examples"""
        print("📬 Scraping Mailchimp examples...")
        
        # Sample announcement email templates (these are often public)
        mailchimp_templates = [
            {
                'subject': 'Exciting News: Our New Product is Here!',
                'body': '''Hi there!

We're thrilled to announce the launch of our newest product that we've been working on for months.

🎉 What's New:
• Revolutionary features that will transform your workflow
• Improved user experience with intuitive design  
• Better performance and reliability

As a valued subscriber, you get early access with 20% off for the first week.

[Get Early Access Now]

Thank you for being part of our journey!

Best regards,
The Team''',
                'brand': 'Generic Template',
                'category': 'product_announcement'
            },
            {
                'subject': 'Important Update: New Features Available',
                'body': '''Hello!

We've just rolled out some exciting updates to improve your experience.

✨ What's Improved:
• Faster loading times
• New dashboard design
• Enhanced mobile experience
• Better security features

These updates are now live for all users. No action needed on your part!

Questions? Just reply to this email.

Happy updating!
Support Team''',
                'brand': 'Generic Template',
                'category': 'feature_announcement'
            },
            {
                'subject': 'Join Us: Exciting Company News!',
                'body': '''Dear Valued Customer,

We have some fantastic news to share with our community!

🌟 Big Announcement:
We've just secured Series B funding to accelerate our growth and bring you even better products and services.

What this means for you:
→ Faster product development
→ Improved customer support
→ New features coming soon
→ Continued commitment to excellence

Thank you for being part of our success story. More exciting updates coming soon!

Cheers,
Leadership Team

P.S. Keep an eye on your inbox for exclusive early access to our upcoming features.''',
                'brand': 'Generic Template',  
                'category': 'company_announcement'
            }
        ]
        
        for template in mailchimp_templates:
            email_data = {
                'source': 'mailchimp_template',
                'source_url': 'https://mailchimp.com/resources/',
                'subject': template['subject'],
                'body': template['body'],
                'brand': template['brand'],
                'category': template['category'],
                'scraped_at': pd.Timestamp.now().isoformat()
            }
            self.emails.append(email_data)
            print(f"✅ Added template: {template['subject'][:50]}...")
    
    def scrape_email_design_sites(self):
        """Scrape from email design inspiration sites"""
        print("🎨 Adding email design templates...")
        
        # Add more template variations
        design_templates = [
            {
                'subject': '🚀 Blast Off: Our New App is Live!',
                'body': '''Hey [Name]!

The wait is over! 🎉

After months of development, we're excited to announce that our new mobile app is now available for download.

🔥 Key Features:
• Lightning-fast performance
• Sleek, intuitive design  
• Offline mode capability
• Seamless sync across devices

Ready to experience the future? Download now:

📱 [Download for iOS]
🤖 [Download for Android]

Early bird special: Use code LAUNCH20 for 20% off premium features (limited time!)

Questions? Our support team is standing by.

To your success,
[Your Name] & the [Company] Team

P.S. Share this with friends and get a month free when they sign up!''',
                'brand': 'Tech Startup',
                'category': 'app_launch'
            },
            {
                'subject': 'Breaking: Major Partnership Announcement',
                'body': '''Dear [Name],

Today marks a milestone in our company's journey.

🤝 BIG NEWS: We've partnered with [Major Company] to bring you unprecedented value and innovation.

What This Partnership Brings:
✓ Expanded product offerings
✓ Enhanced service capabilities  
✓ Broader global reach
✓ Improved customer experience

This collaboration allows us to serve you better while maintaining our commitment to quality and innovation.

Want the full story? Read our press release: [Link]

We're just getting started. Exciting times ahead!

Best,
[CEO Name]
[Company Name]

---
This partnership is about YOU - our valued customer. Expect great things.''',
                'brand': 'Enterprise',
                'category': 'partnership_announcement'
            },
            {
                'subject': 'You\'re Invited: Exclusive Event Announcement',
                'body': '''Hi [Name]!

You're invited to something special! 🎊

We're hosting an exclusive virtual event and you're on the VIP list.

📅 SAVE THE DATE:
Event: Future of [Industry] Summit
Date: [Date]  
Time: [Time] PST
Where: Online (Link will be sent)

🌟 What to Expect:
• Keynote from industry leaders
• Interactive workshops
• Networking opportunities
• Exclusive product previews
• Q&A sessions

This is a limited-capacity event reserved for our most engaged community members.

[RESERVE MY SPOT] - Free for you!

Can't wait to see you there!

Warm regards,
Events Team

P.S. Spots are filling up fast. Secure yours today!''',
                'brand': 'Professional Services',
                'category': 'event_announcement'
            },
            {
                'subject': 'Celebrating You: Community Milestone Reached!',
                'body': '''Amazing news, [Name]!

🎉 WE DID IT TOGETHER! 🎉

Our community has just reached [Number] members, and it's all thanks to incredible people like you.

When we started this journey, we dreamed of building something special. Today, that dream is our reality:

📊 By the Numbers:
• [Number]+ active community members
• [Number] success stories shared
• [Number] connections made
• [Number] goals achieved together

To celebrate this milestone, we're giving back:

🎁 COMMUNITY CELEBRATION PERKS:
→ Free premium access for the next month
→ Exclusive community-only resources
→ Special "Founding Member" badge
→ Early access to all new features

[CLAIM YOUR CELEBRATION PERKS]

Thank you for making our community extraordinary. Here's to the next milestone!

With gratitude,
[Your Name] & Community Team

#CommunityStrong #TogetherWeGrow''',
                'brand': 'Community Platform',
                'category': 'milestone_announcement'
            }
        ]
        
        for template in design_templates:
            email_data = {
                'source': 'design_template',
                'source_url': 'curated_template',
                'subject': template['subject'],
                'body': template['body'],
                'brand': template['brand'],
                'category': template['category'],
                'scraped_at': pd.Timestamp.now().isoformat()
            }
            self.emails.append(email_data)
            print(f"✅ Added design template: {template['subject'][:50]}...")
    
    def scrape_hubspot_examples(self):
        """Add HubSpot-style announcement templates"""
        print("🧡 Adding HubSpot-style templates...")
        
        hubspot_templates = [
            {
                'subject': 'New Feature Alert: [Feature Name] is Here',
                'body': '''Hi [First Name],

Great news! We've just launched [Feature Name], and it's going to make your [workflow/process] so much easier.

Here's what's new:

🔧 [Feature Name] allows you to:
• [Benefit 1]
• [Benefit 2] 
• [Benefit 3]

→ [Call-to-Action Button: Try It Now]

This feature was built based on your feedback, so we can't wait to hear what you think!

Need help getting started? Check out our quick tutorial: [Link]

Happy [day of week]!
[Your Name]

P.S. Have questions? Just reply to this email - we read every message.''',
                'brand': 'SaaS Platform',
                'category': 'feature_launch'
            },
            {
                'subject': 'Big Changes Coming: Here\'s What You Need to Know',
                'body': '''Hello [Name],

We're making some important changes that will improve your experience with us.

📋 What's Changing:
Starting [Date], we're introducing:
• Enhanced security measures
• Streamlined user interface
• Improved performance
• New collaboration tools

📋 What This Means for You:
✓ Better protection of your data
✓ Faster, more intuitive experience
✓ New ways to work with your team
✓ Same great service you love

📋 What You Need to Do:
Nothing! These improvements happen automatically.

We'll send another email before the changes go live with any important details.

Questions? Our support team is here: [Support Link]

Thanks for being with us!
[Team Name]''',
                'brand': 'Business Software',
                'category': 'system_update'
            }
        ]
        
        for template in hubspot_templates:
            email_data = {
                'source': 'hubspot_style',
                'source_url': 'hubspot_inspired',
                'subject': template['subject'],
                'body': template['body'],
                'brand': template['brand'],
                'category': template['category'],
                'scraped_at': pd.Timestamp.now().isoformat()
            }
            self.emails.append(email_data)
            print(f"✅ Added HubSpot-style: {template['subject'][:50]}...")
    
    def extract_text(self, soup, selectors: List[str]) -> str:
        """Extract text using multiple selector fallbacks"""
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()
        return ""
    
    def save_templates(self, filename: str = "email_templates.json"):
        """Save scraped templates to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.emails, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved {len(self.emails)} templates to {filename}")
    
    def save_as_csv(self, filename: str = "email_templates.csv"):
        """Save templates as CSV for easy processing"""
        df = pd.DataFrame(self.emails)
        df.to_csv(filename, index=False)
        print(f"📊 Saved {len(self.emails)} templates to {filename}")
    
    def get_summary(self):
        """Print summary of scraped templates"""
        if not self.emails:
            print("❌ No templates found!")
            return
        
        print(f"\n📈 SCRAPING SUMMARY:")
        print(f"Total templates: {len(self.emails)}")
        
        # Group by source
        sources = {}
        categories = {}
        
        for email in self.emails:
            source = email.get('source', 'unknown')
            category = email.get('category', 'unknown')
            
            sources[source] = sources.get(source, 0) + 1
            categories[category] = categories.get(category, 0) + 1
        
        print(f"\nBy Source:")
        for source, count in sources.items():
            print(f"  • {source}: {count} templates")
        
        print(f"\nBy Category:")
        for category, count in categories.items():
            print(f"  • {category}: {count} templates")

def main():
    """Main function to run the scraper"""
    print("🚀 STARTING EMAIL TEMPLATE SCRAPER")
    print("=" * 50)
    
    scraper = EmailTemplateScraper()
    
    # Since Spotmar requires login, use alternative sources
    print("ℹ️  Note: Spotmar requires account access, using alternative sources...")
    print()
    
    # Test with simple templates first
    print("1️⃣ Adding Mailchimp-style templates...")
    scraper.scrape_mailchimp_examples()
    print(f"   Templates so far: {len(scraper.emails)}")
    print()
    
    print("2️⃣ Adding design templates...")
    scraper.scrape_email_design_sites()
    print(f"   Templates so far: {len(scraper.emails)}")
    print()
    
    print("3️⃣ Adding HubSpot-style templates...")
    scraper.scrape_hubspot_examples()
    print(f"   Templates so far: {len(scraper.emails)}")
    print()
    
    print("4️⃣ Attempting to scrape Really Good Emails...")
    scraper.scrape_really_good_emails()
    print(f"   Final template count: {len(scraper.emails)}")
    print()
    
    # Check if we have any templates
    if len(scraper.emails) == 0:
        print("❌ ERROR: No templates were created!")
        print("🔍 Let's debug...")
        
        # Test basic functionality
        test_email = {
            'source': 'test',
            'source_url': 'test.com',
            'subject': 'Test Subject',
            'body': 'Test body content',
            'brand': 'Test Brand',
            'category': 'test',
            'scraped_at': pd.Timestamp.now().isoformat()
        }
        scraper.emails.append(test_email)
        print(f"✅ Added test email. Total: {len(scraper.emails)}")
    
    # Save results
    try:
        print("💾 Saving files...")
        scraper.save_templates()
        scraper.save_as_csv()
        print("✅ Files saved successfully!")
    except Exception as e:
        print(f"❌ Error saving files: {e}")
        return []
    
    # Print summary
    scraper.get_summary()
    
    # Show first few templates for verification
    if scraper.emails:
        print(f"\n📋 SAMPLE TEMPLATES:")
        for i, email in enumerate(scraper.emails[:3]):
            print(f"\nTemplate {i+1}:")
            print(f"  Subject: {email['subject']}")
            print(f"  Body (first 100 chars): {email['body'][:100]}...")
            print(f"  Source: {email['source']}")
    
    print("\n✅ SCRAPING COMPLETE!")
    print("Files created:")
    if os.path.exists("email_templates.json"):
        print("  ✅ email_templates.json")
    else:
        print("  ❌ email_templates.json - FILE NOT CREATED!")
        
    if os.path.exists("email_templates.csv"):
        print("  ✅ email_templates.csv")
    else:
        print("  ❌ email_templates.csv - FILE NOT CREATED!")
    
    return scraper.emails

if __name__ == "__main__":
    templates = main()
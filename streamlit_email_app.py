import streamlit as st
import openai
from pinecone import Pinecone
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import time
from typing import List, Dict, Optional
import base64
from io import BytesIO
from PIL import Image

# =============================================================================
# CONFIGURATION
# =============================================================================

# API Keys - IMPORTANT: Use Streamlit secrets in production
OPENAI_API_KEY = "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"
PINECONE_API_KEY = "pcsk_5P4Y18_HdB9GEWSDJ4GsC5dmu3WaKAseq5gPYp61FTQw8kw5L83P7sqEbnNkdCRQNrkhS9"
openai.api_key = OPENAI_API_KEY

# Initialize OpenAI client
if OPENAI_API_KEY != "your_openai_key_here":
    openai.api_key = OPENAI_API_KEY
    # For newer versions of openai library, use:
    # client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    st.error("⚠️ OpenAI API key not configured. Please set OPENAI_API_KEY in Streamlit secrets.")

# Initialize Pinecone
if PINECONE_API_KEY != "your_pinecone_key_here":
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index("email-campaigns")
    except Exception as e:
        st.warning(f"Pinecone initialization failed: {e}")
        pc = None
        index = None
else:
    pc = None
    index = None

# =============================================================================
# CORE FUNCTIONALITY
# =============================================================================

class EmailGenerator:
    def __init__(self):
        self.index = index
        
    def extract_product_images(self, url: str) -> List[str]:
        """Extract product images from the website"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find product images with improved selectors
            image_urls = []
            
            # Enhanced selectors for product images
            image_selectors = [
                'img[alt*="product" i]',
                'img[class*="product" i]', 
                'img[id*="product" i]',
                'img[src*="product" i]',
                '.hero img',
                '.banner img',
                '.featured img',
                'main img',
                '.gallery img',
                '.showcase img',
                'img[alt*="hero" i]',
                'img[class*="hero" i]'
            ]
            
            for selector in image_selectors:
                try:
                    images = soup.select(selector)
                    for img in images:
                        src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                        if src:
                            # Convert relative URLs to absolute
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                src = f"{url.rstrip('/')}{src}"
                            elif not src.startswith('http'):
                                src = f"{url.rstrip('/')}/{src}"
                            
                            # Filter out unwanted images
                            if not any(x in src.lower() for x in ['icon', 'logo', 'avatar', 'thumb', 'favicon']):
                                # Check image dimensions if possible
                                width = img.get('width')
                                height = img.get('height')
                                if width and height:
                                    try:
                                        w, h = int(width), int(height)
                                        if w > 200 and h > 200:  # Only larger images
                                            image_urls.append(src)
                                    except ValueError:
                                        image_urls.append(src)
                                else:
                                    image_urls.append(src)
                except Exception as e:
                    continue
            
            # Remove duplicates and limit
            unique_images = list(dict.fromkeys(image_urls))[:8]
            
            # Validate URLs
            valid_images = []
            for img_url in unique_images:
                try:
                    img_response = requests.head(img_url, timeout=5)
                    if img_response.status_code == 200:
                        content_type = img_response.headers.get('content-type', '')
                        if 'image' in content_type:
                            valid_images.append(img_url)
                except:
                    continue
                    
                if len(valid_images) >= 5:  # Limit to 5 valid images
                    break
            
            return valid_images
            
        except Exception as e:
            st.error(f"Error extracting images: {e}")
            return []
    
    def generate_product_image(self, product_info: Dict) -> Optional[str]:
        """Generate a custom product image using DALL-E"""
        try:
            if OPENAI_API_KEY == "your_openai_key_here":
                st.error("OpenAI API key not configured for image generation.")
                return None
                
            # Create a detailed prompt for product image generation
            product_name = product_info.get('product_name', 'product')
            description = product_info.get('product_description', '')
            campaign_type = product_info.get('campaign_type', 'announcement')
            
            # Analyze website content for visual cues
            website_info = product_info.get('website_info', {})
            website_title = website_info.get('title', '')
            
            # Create targeted image generation prompt
            product_lower = (product_name + description).lower()
            
            if any(word in product_lower for word in ['app', 'mobile', 'software', 'platform', 'saas']):
                if 'mobile' in product_lower or 'app' in product_lower:
                    image_prompt = f"Modern smartphone mockup displaying {product_name} mobile app interface, clean UI design, professional product photography, white background, high quality commercial style"
                else:
                    image_prompt = f"Modern laptop displaying {product_name} web application dashboard, clean professional interface, office environment, commercial photography style"
            elif any(word in product_lower for word in ['physical', 'device', 'gadget', 'tool', 'hardware']):
                image_prompt = f"Professional product photography of {product_name}, clean white studio background, perfect lighting, commercial product shot, high resolution"
            elif any(word in product_lower for word in ['service', 'consulting', 'business']):
                image_prompt = f"Modern professional graphic representing {product_name} service, clean minimal design, business style, commercial quality"
            else:
                # Generic product image
                image_prompt = f"Professional marketing visual for {product_name}, modern clean aesthetic, {description[:50]}, commercial photography style, high quality"
            
            # Add safety and quality modifiers
            image_prompt = f"{image_prompt}, professional, clean, modern, high quality, commercial grade"
            
            st.info(f"🎨 Generating image with prompt: {image_prompt[:100]}...")
            
            # Generate image with DALL-E 3
            try:
                # For newer openai library versions (v1.0+)
                response = openai.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )
                image_url = response.data[0].url
            except Exception as api_error:
                # Fallback for older API versions
                try:
                    response = openai.Image.create(
                        prompt=image_prompt,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response['data'][0]['url']
                except Exception as fallback_error:
                    st.error(f"Image generation failed: {fallback_error}")
                    return None
            
            return image_url
            
        except Exception as e:
            st.error(f"Error generating product image: {str(e)}")
            return None
    
    def create_email_html(self, email_content: Dict, image_url: Optional[str] = None) -> str:
        """Create HTML version of the email with image"""
        
        subject = email_content.get('subject', '')
        body = email_content.get('body', '')
        cta = email_content.get('cta', 'Learn More')
        
        # Convert body text to HTML with better formatting
        html_body = body.replace('\n\n', '</p><p>').replace('\n', '<br>')
        html_body = f"<p>{html_body}</p>"
        
        # Handle bullet points and lists better
        if any(marker in body for marker in ['•', '*', '-', '1.', '2.']):
            lines = body.split('\n')
            formatted_lines = []
            in_list = False
            list_type = 'ul'
            
            for line in lines:
                line = line.strip()
                if line:
                    # Check for bullet points
                    if line.startswith(('•', '*', '-')) and len(line) > 2:
                        if not in_list:
                            formatted_lines.append('<ul>')
                            in_list = True
                            list_type = 'ul'
                        clean_line = re.sub(r'^[•*-]\s*', '', line)
                        formatted_lines.append(f'<li>{clean_line}</li>')
                    # Check for numbered lists
                    elif re.match(r'^\d+\.\s+', line):
                        if not in_list:
                            formatted_lines.append('<ol>')
                            in_list = True
                            list_type = 'ol'
                        elif list_type == 'ul':
                            formatted_lines.append('</ul><ol>')
                            list_type = 'ol'
                        clean_line = re.sub(r'^\d+\.\s*', '', line)
                        formatted_lines.append(f'<li>{clean_line}</li>')
                    else:
                        if in_list:
                            formatted_lines.append(f'</{list_type}>')
                            in_list = False
                        if line:
                            formatted_lines.append(f'<p>{line}</p>')
                else:
                    if in_list:
                        formatted_lines.append(f'</{list_type}>')
                        in_list = False
            
            if in_list:
                formatted_lines.append(f'</{list_type}>')
            
            html_body = ''.join(formatted_lines)
        
        # Enhanced HTML email template with better styling
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .email-container {{
                        width: 100% !important;
                        padding: 10px !important;
                    }}
                    .header-title {{
                        font-size: 24px !important;
                    }}
                    .cta-button {{
                        padding: 12px 20px !important;
                    }}
                }}
            </style>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f8f9fa;">
            
            <div class="email-container" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 20px; text-align: center;">
                    <h1 class="header-title" style="color: white; margin: 0; font-size: 28px; font-weight: 600;">{subject}</h1>
                </div>
                
                <div style="padding: 30px 20px;">
                    
                    {f'''
                    <div style="text-align: center; margin: 30px 0;">
                        <img src="{image_url}" alt="Product Image" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                    </div>
                    ''' if image_url else ''}
                    
                    <div style="font-size: 16px; margin: 25px 0; color: #444;">
                        {html_body}
                    </div>
                    
                    <div style="text-align: center; margin: 40px 0;">
                        <a href="#" class="cta-button" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: 600; display: inline-block; transition: all 0.3s ease; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);">{cta}</a>
                    </div>
                    
                </div>
                
                <div style="background-color: #f8f9fa; border-top: 1px solid #eee; padding: 20px; text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #666;">
                        Best regards,<br>
                        <strong>Your Team</strong>
                    </p>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #999;">
                        You received this email because you subscribed to our updates.
                    </p>
                </div>
                
            </div>
            
        </body>
        </html>
        """
        
        return html_template
    
    def create_streamlit_preview(self, email_content: Dict, image_url: Optional[str] = None) -> None:
        """Create a Streamlit-native email preview that works reliably"""
        
        subject = email_content.get('subject', '')
        body = email_content.get('body', '')
        cta = email_content.get('cta', 'Learn More')
        
        # Create preview container
        with st.container():
            # Email header with gradient background
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 30px 20px;
                border-radius: 15px 15px 0 0;
                text-align: center;
                margin-bottom: 0;
            ">
                <h1 style="
                    color: white;
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">{subject}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            # Email body container
            st.markdown(f"""
            <div style="
                background: white;
                padding: 30px 20px;
                border-radius: 0 0 15px 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                border: 1px solid #e1e5e9;
                border-top: none;
            ">
            """, unsafe_allow_html=True)
            
            # Image section
            if image_url:
                col1, col2, col3 = st.columns([1, 3, 1])
                with col2:
                    try:
                        st.image(
                            image_url, 
                            caption="", 
                            use_column_width=True,
                            output_format="auto"
                        )
                        st.markdown("<br>", unsafe_allow_html=True)
                    except Exception as e:
                        st.warning(f"⚠️ Could not display image: {str(e)}")
                        st.text(f"Image URL: {image_url}")
            
            # Process and display body content
            formatted_body = body
            
            # Handle bullet points
            if '•' in body or '*' in body or '-' in body:
                lines = body.split('\n')
                formatted_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line.startswith(('•', '*', '-')) and len(line) > 2:
                        clean_line = re.sub(r'^[•*-]\s*', '', line)
                        formatted_lines.append(f"• {clean_line}")
                    elif line:
                        formatted_lines.append(line)
                
                formatted_body = '\n'.join(formatted_lines)
            
            # Display body text
            st.markdown(f"""
            <div style="
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
                line-height: 1.6;
                color: #333;
                white-space: pre-line;
                margin-bottom: 30px;
            ">{formatted_body}</div>
            """, unsafe_allow_html=True)
            
            # CTA Button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown(f"""
                <div style="text-align: center;">
                    <a href="#" style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 15px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        font-weight: 600;
                        display: inline-block;
                        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                        transition: all 0.3s ease;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    ">{cta}</a>
                </div>
                """, unsafe_allow_html=True)
            
            # Email footer
            st.markdown("""
            <div style="
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                text-align: center;
                font-size: 14px;
                color: #666;
            ">
                <p style="margin: 0;">
                    Best regards,<br>
                    <strong>Your Team</strong>
                </p>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #999;">
                    You received this email because you subscribed to our updates.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Close container
            st.markdown("</div>", unsafe_allow_html=True)
        
    def scrape_website(self, url: str) -> Dict[str, str]:
        """Extract key information from a website with better error handling"""
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title with fallbacks
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
            else:
                # Fallback to h1
                h1_tag = soup.find('h1')
                if h1_tag:
                    title = h1_tag.text.strip()
            
            # Get meta description with fallbacks
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
            else:
                # Fallback to og:description
                og_desc = soup.find('meta', attrs={'property': 'og:description'})
                if og_desc:
                    description = og_desc.get('content', '')
            
            # Get main content (improved extraction)
            content_parts = []
            
            # Try to find main content area first
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main', re.I))
            
            if main_content:
                paragraphs = main_content.find_all('p')
            else:
                paragraphs = soup.find_all('p')
            
            for p in paragraphs[:8]:  # First 8 paragraphs
                text = p.get_text().strip()
                if len(text) > 50 and not any(skip in text.lower() for skip in ['cookie', 'privacy', 'terms']):
                    content_parts.append(text)
            
            main_content = ' '.join(content_parts)[:1500]  # Increased limit
            
            # Extract keywords from headings
            headings = []
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                heading_text = heading.get_text().strip()
                if heading_text and len(heading_text) < 100:
                    headings.append(heading_text)
            
            return {
                'title': title[:200],  # Limit length
                'description': description[:500],
                'content': main_content,
                'headings': headings[:5],  # Top 5 headings
                'url': url
            }
            
        except requests.exceptions.RequestException as e:
            st.error(f"Network error scraping website: {e}")
            return {'title': '', 'description': '', 'content': '', 'headings': [], 'url': url}
        except Exception as e:
            st.error(f"Error scraping website: {e}")
            return {'title': '', 'description': '', 'content': '', 'headings': [], 'url': url}
    
    def find_similar_emails(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """Find similar emails from the vector database"""
        if not self.index:
            # Return enhanced mock data if Pinecone not configured
            return [
                {
                    'score': 0.89,
                    'subject': '🚀 Exciting Product Launch: Revolutionary App Now Available!',
                    'category': 'product_launch',
                    'body': 'We are thrilled to announce the launch of our groundbreaking mobile app that will transform how you manage your daily tasks. With cutting-edge features and an intuitive interface, this app is designed to boost your productivity by 300%.',
                    'brand': 'TechCorp',
                    'has_discount': False,
                    'has_urgency': True
                },
                {
                    'score': 0.85,
                    'subject': '✨ New Feature Alert: Enhanced User Experience',
                    'category': 'feature_announcement', 
                    'body': 'Get ready for an improved experience with our latest feature updates. We have listened to your feedback and implemented powerful new tools that will streamline your workflow.',
                    'brand': 'ProductCo',
                    'has_discount': True,
                    'has_urgency': False
                },
                {
                    'score': 0.82,
                    'subject': '🎉 Special Launch Offer: 50% Off Premium Features',
                    'category': 'special_offer',
                    'body': 'To celebrate our new product launch, we are offering an exclusive 50% discount on all premium features. This limited-time offer expires in 48 hours.',
                    'brand': 'StartupXYZ',
                    'has_discount': True,
                    'has_urgency': True
                }
            ]
        
        try:
            # Generate embedding for the query
            response = openai.embeddings.create(
                input=[query_text],
                model="text-embedding-ada-002"
            )
            query_embedding = response.data[0].embedding
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            similar_emails = []
            for match in results.matches:
                similar_emails.append({
                    'score': float(match.score),
                    'subject': match.metadata.get('subject', ''),
                    'body': match.metadata.get('body', ''),
                    'category': match.metadata.get('category', ''),
                    'brand': match.metadata.get('brand', ''),
                    'has_discount': match.metadata.get('has_discount', False),
                    'has_urgency': match.metadata.get('has_urgency', False)
                })
            
            return similar_emails
            
        except Exception as e:
            st.error(f"Error finding similar emails: {e}")
            # Return mock data as fallback
            return self.find_similar_emails("", top_k)  # This will return mock data
    
    def generate_email_content(self, user_input: Dict, similar_emails: List[Dict]) -> Dict[str, str]:
        """Generate new email content based on user input and similar examples"""
        
        if OPENAI_API_KEY == "your_openai_key_here":
            return {
                'subject': f"🚀 Introducing {user_input.get('product_name', 'Our New Product')}",
                'body': f"We're excited to announce {user_input.get('product_name', 'our new product')}!\n\n{user_input.get('product_description', 'This innovative solution will transform your experience.')}\n\nKey benefits:\n• Enhanced productivity\n• User-friendly design\n• Reliable performance\n\nDon't miss out on this opportunity to upgrade your experience!",
                'cta': 'Get Started Today',
                'generated_at': datetime.now().isoformat()
            }
        
        # Prepare context from similar emails
        examples_context = ""
        for i, email in enumerate(similar_emails[:3]):  # Use top 3 examples
            examples_context += f"\nExample {i+1} (Score: {email['score']:.2f}):\nSubject: {email['subject']}\nCategory: {email['category']}\nBody: {email['body'][:200]}...\n"
        
        # Enhanced prompt with better instructions
        website_context = ""
        website_info = user_input.get('website_info', {})
        if website_info.get('title'):
            website_context = f"\nWebsite Analysis:\n- Title: {website_info['title']}\n- Description: {website_info.get('description', 'N/A')}\n- Key Content: {website_info.get('content', 'N/A')[:200]}..."
        
        prompt = f"""
You are an expert email marketer specializing in high-converting campaigns. Generate a compelling marketing email that drives action.

USER INPUT:
- Product/Company: {user_input.get('product_name', 'N/A')}
- Description: {user_input.get('product_description', 'N/A')}
- Campaign Type: {user_input.get('campaign_type', 'announcement')}
- Target Audience: {user_input.get('target_audience', 'general audience')}
- Key Message: {user_input.get('key_message', 'N/A')}
{website_context}

SUCCESSFUL EMAIL EXAMPLES FOR REFERENCE:
{examples_context}

REQUIREMENTS:
1. Create a compelling subject line (45-60 characters) with emoji if appropriate
2. Write an engaging email body (250-400 words) that:
   - Hooks the reader in the first sentence
   - Clearly explains the value proposition
   - Uses bullet points for key benefits
   - Creates urgency or excitement
   - Maintains a conversational tone
3. Include a strong, action-oriented call-to-action
4. Match the tone and effectiveness of the similar examples
5. Make it specific to the user's product/service
6. Use formatting like bullets and emojis strategically

OUTPUT FORMAT (exactly as shown):
Subject: [compelling subject line with emoji]

Body:
[Hook sentence that grabs attention]

[Value proposition paragraph]

Key benefits:
• [Benefit 1]
• [Benefit 2] 
• [Benefit 3]

[Urgency or social proof paragraph]

[Closing with clear next step]

CTA: [Strong action-oriented call-to-action]
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert email marketer who writes high-converting marketing emails. Always follow the exact output format requested."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content
            
            # Parse the response with better error handling
            lines = generated_content.split('\n')
            subject = ""
            body = ""
            cta = ""
            
            current_section = None
            body_lines = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('Subject:'):
                    subject = line.replace('Subject:', '').strip()
                    current_section = 'subject'
                elif line.startswith('Body:'):
                    current_section = 'body'
                elif line.startswith('CTA:'):
                    cta = line.replace('CTA:', '').strip()
                    current_section = 'cta'
                elif current_section == 'body' and line:
                    body_lines.append(line)
            
            body = '\n'.join(body_lines).strip()
            
            # Fallback if parsing fails
            if not subject or not body:
                subject = f"🚀 Introducing {user_input.get('product_name', 'Our New Product')}"
                if not body:
                    body = f"We're excited to share something amazing with you!\n\n{user_input.get('product_description', 'Our latest innovation is here.')}\n\n✨ Don't miss out on this opportunity!"
                if not cta:
                    cta = "Learn More"
            
            return {
                'subject': subject,
                'body': body,
                'cta': cta,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            st.error(f"Error generating email: {e}")
            # Return fallback content
            return {
                'subject': f"🚀 Introducing {user_input.get('product_name', 'Our New Product')}",
                'body': f"We're excited to announce {user_input.get('product_name', 'our new product')}!\n\n{user_input.get('product_description', 'This innovative solution will transform your experience.')}\n\nKey benefits:\n• Enhanced performance\n• User-friendly design\n• Reliable results\n\nReady to get started?",
                'cta': 'Get Started Today',
                'generated_at': datetime.now().isoformat()
            }

# =============================================================================
# STREAMLIT UI (Enhanced)
# =============================================================================

def main():
    # Page config
    st.set_page_config(
        page_title="AI Email Generator Pro",
        page_icon="📧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Enhanced Custom CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.8rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .email-preview {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 2rem;
        border-radius: 15px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .similarity-score {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: bold;
        display: inline-block;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 4px solid #667eea;
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<div class="main-header">🚀 AI Email Generator Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Generate compelling marketing emails using AI and successful email examples</div>', unsafe_allow_html=True)
    
    # Show API status
    col1, col2, col3 = st.columns(3)
    with col1:
        if OPENAI_API_KEY != "your_openai_key_here":
            st.success("✅ OpenAI Connected")
        else:
            st.error("❌ OpenAI API Key Missing")
    with col2:
        if pc and index:
            st.success("✅ Pinecone Connected")
        else:
            st.warning("⚠️ Using Mock Data")
    with col3:
        st.info("🔧 Ready to Generate")
    
    # Initialize the generator
    generator = EmailGenerator()
    
    # Sidebar for user input
    with st.sidebar:
        st.header("📝 Campaign Details")
        
        # Basic information
        with st.expander("🎯 Basic Information", expanded=True):
            product_name = st.text_input(
                "Product/Company Name", 
                placeholder="e.g., TaskMaster Pro",
                help="Enter the name of your product, service, or company"
            )
            
            campaign_type = st.selectbox(
                "Campaign Type",
                [
                    "Product Launch", 
                    "Feature Announcement", 
                    "Company News", 
                    "Event Invitation", 
                    "Special Offer", 
                    "Newsletter",
                    "Welcome Series",
                    "Re-engagement"
                ],
                help="Select the type of email campaign you want to create"
            )
            
            product_description = st.text_area(
                "Product/Service Description",
                placeholder="Brief description of what you're announcing or promoting...",
                height=120,
                help="Provide details about your product or the announcement"
            )
        
        with st.expander("👥 Audience & Messaging"):
            target_audience = st.selectbox(
                "Target Audience",
                [
                    "Small Business Owners", 
                    "Tech Professionals", 
                    "Consumers", 
                    "Enterprise", 
                    "Students", 
                    "Marketing Professionals",
                    "General Audience"
                ]
            )
            
            key_message = st.text_input(
                "Key Message/Value Prop",
                placeholder="What's the main benefit or exciting news?",
                help="The core message you want to communicate"
            )
            
            tone = st.selectbox(
                "Email Tone",
                ["Professional", "Friendly", "Exciting", "Urgent", "Casual", "Formal"]
            )
        
        # Website analysis
        with st.expander("🌐 Website Analysis"):
            website_url = st.text_input(
                "Website URL (Optional)", 
                placeholder="https://yourwebsite.com",
                help="We'll analyze your website to better understand your brand"
            )
            
            analyze_website = st.button("🔍 Analyze Website", disabled=not website_url)
            
            if analyze_website and website_url:
                with st.spinner("Analyzing website..."):
                    website_info = generator.scrape_website(website_url)
                    st.session_state.website_info = website_info
                    if website_info.get('title'):
                        st.success("✅ Website analyzed successfully!")
                        st.write(f"**Title:** {website_info['title'][:50]}...")
                        if website_info.get('description'):
                            st.write(f"**Description:** {website_info['description'][:100]}...")
                    else:
                        st.error("Failed to analyze website. Please check the URL.")
        
        # Generate button
        st.markdown("---")
        generate_button = st.button(
            "🚀 Generate Email", 
            type="primary", 
            use_container_width=True,
            disabled=not (product_name and product_description)
        )
        
        if not product_name or not product_description:
            st.warning("⚠️ Please fill in product name and description to generate email")
    
    # Main content area
    if generate_button:
        # Prepare user input
        user_input = {
            'product_name': product_name,
            'product_description': product_description,
            'campaign_type': campaign_type,
            'target_audience': target_audience,
            'key_message': key_message,
            'tone': tone,
            'website_info': st.session_state.get('website_info', {})
        }
        
        # Create search query for similar emails
        search_query = f"{campaign_type} {product_description} {key_message} {target_audience}"
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Find similar emails
        status_text.text("🔍 Finding similar emails...")
        progress_bar.progress(20)
        similar_emails = generator.find_similar_emails(search_query)
        
        # Step 2: Generate content
        status_text.text("✍️ Generating your email...")
        progress_bar.progress(50)
        generated_email = generator.generate_email_content(user_input, similar_emails)
        
        progress_bar.progress(70)
        
        # Main layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("📧 Generated Email")
            
            # Image generation options
            status_text.text("🎨 Setting up image options...")
            progress_bar.progress(80)
            
            image_option = st.radio(
                "Product Image Options:",
                ["No Image", "Generate AI Image", "Use Website Images"],
                horizontal=True,
                help="Choose how to add visual content to your email"
            )
            
            image_url = None
            
            if image_option == "Generate AI Image":
                if OPENAI_API_KEY == "your_openai_key_here":
                    st.error("❌ OpenAI API key required for image generation")
                else:
                    with st.spinner("🎨 Generating custom product image..."):
                        image_url = generator.generate_product_image(user_input)
                        if image_url:
                            st.success("✅ Custom image generated!")
                            st.image(image_url, caption="Generated product image", width=300)
                        else:
                            st.error("Failed to generate image. Continuing without image.")
                        
            elif image_option == "Use Website Images" and website_url:
                with st.spinner("🔍 Finding product images on website..."):
                    website_images = generator.extract_product_images(website_url)
                    if website_images:
                        st.success(f"✅ Found {len(website_images)} images")
                        
                        # Display images for selection
                        cols = st.columns(min(3, len(website_images)))
                        selected_idx = 0
                        
                        for i, img_url in enumerate(website_images[:3]):
                            with cols[i % 3]:
                                try:
                                    st.image(img_url, caption=f"Image {i+1}", width=150)
                                    if st.button(f"Select #{i+1}", key=f"select_img_{i}"):
                                        selected_idx = i
                                        image_url = img_url
                                except:
                                    st.error(f"Failed to load image {i+1}")
                        
                        if not image_url and website_images:
                            image_url = website_images[0]  # Default to first image
                            
                    else:
                        st.warning("No suitable images found on website")
            
            progress_bar.progress(90)
            status_text.text("📧 Finalizing email...")
            
            # Display generated email in an attractive format
            st.markdown('<div class="email-preview">', unsafe_allow_html=True)
            
            # Subject line
            st.subheader("📬 Subject Line")
            subject_col1, subject_col2 = st.columns([4, 1])
            with subject_col1:
                st.text_input("", value=generated_email['subject'], disabled=True, key="subject_display")
            with subject_col2:
                subject_length = len(generated_email['subject'])
                if subject_length <= 50:
                    st.success(f"✅ {subject_length} chars")
                elif subject_length <= 60:
                    st.warning(f"⚠️ {subject_length} chars")
                else:
                    st.error(f"❌ {subject_length} chars")
            
            # Product image
            if image_url:
                st.subheader("🖼️ Product Image")
                img_col1, img_col2 = st.columns([1, 2])
                with img_col1:
                    st.image(image_url, caption="Email image", width=200)
                with img_col2:
                    st.info("✨ This image will be included in your email to increase engagement and visual appeal.")
            
            # Email body
            st.subheader("📝 Email Body")
            body_col1, body_col2 = st.columns([4, 1])
            with body_col1:
                st.text_area("", value=generated_email['body'], height=250, disabled=True, key="body_display")
            with body_col2:
                word_count = len(generated_email['body'].split())
                st.metric("Word Count", word_count)
                if 200 <= word_count <= 400:
                    st.success("✅ Optimal length")
                else:
                    st.warning("⚠️ Consider adjusting")
            
            # Call to action
            st.subheader("🎯 Call to Action")
            st.text_input("", value=generated_email['cta'], disabled=True, key="cta_display")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            progress_bar.progress(100)
            status_text.text("✅ Email generated successfully!")
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            
            # Email preview and actions
            st.markdown("---")
            
            # HTML email preview
            preview_option = st.selectbox(
                "📱 Email Preview Options:",
                ["No Preview", "Interactive Preview", "HTML Code", "Browser Preview"],
                help="Choose how to preview your email"
            )
            
            if preview_option != "No Preview":
                st.subheader("📧 Email Preview")
                
                if preview_option == "Interactive Preview":
                    # Use the new Streamlit-native preview
                    st.markdown("### 📱 How your email will look:")
                    generator.create_streamlit_preview(generated_email, image_url)
                    
                elif preview_option == "HTML Code":
                    # Show the HTML code
                    html_email = generator.create_email_html(generated_email, image_url)
                    st.markdown("### 💻 HTML Source Code:")
                    st.code(html_email, language='html')
                    st.info("💡 Copy this HTML code to use in your email marketing platform")
                    
                elif preview_option == "Browser Preview":
                    # Try the HTML component with better error handling
                    html_email = generator.create_email_html(generated_email, image_url)
                    st.markdown("### 🌐 Browser Simulation:")
                    
                    try:
                        # Create a simpler HTML version for components
                        simple_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="utf-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <style>
                                body {{ 
                                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                                    margin: 0; 
                                    padding: 20px; 
                                    background-color: #f5f5f5;
                                }}
                                .email-container {{ 
                                    max-width: 600px; 
                                    margin: 0 auto; 
                                    background: white;
                                    border-radius: 8px;
                                    overflow: hidden;
                                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                                }}
                                .header {{ 
                                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    color: white; 
                                    padding: 30px 20px; 
                                    text-align: center; 
                                }}
                                .content {{ 
                                    padding: 30px 20px; 
                                    line-height: 1.6;
                                }}
                                .cta {{ 
                                    text-align: center; 
                                    margin: 30px 0; 
                                }}
                                .button {{ 
                                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    color: white; 
                                    padding: 15px 30px; 
                                    text-decoration: none; 
                                    border-radius: 25px; 
                                    display: inline-block;
                                    font-weight: 600;
                                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                                }}
                                img {{ 
                                    max-width: 100%; 
                                    height: auto; 
                                    border-radius: 8px;
                                    margin: 20px 0;
                                }}
                                .footer {{
                                    background-color: #f8f9fa;
                                    border-top: 1px solid #eee;
                                    padding: 20px;
                                    text-align: center;
                                    font-size: 14px;
                                    color: #666;
                                }}
                            </style>
                        </head>
                        <body>
                            <div class="email-container">
                                <div class="header">
                                    <h1 style="margin: 0; font-size: 24px;">{generated_email['subject']}</h1>
                                </div>
                                <div class="content">
                                    {'<div style="text-align: center;"><img src="' + image_url + '" alt="Product Image"></div>' if image_url else ''}
                                    <div style="white-space: pre-line;">{generated_email['body']}</div>
                                    <div class="cta">
                                        <a href="#" class="button">{generated_email['cta']}</a>
                                    </div>
                                </div>
                                <div class="footer">
                                    <p style="margin: 0;">Best regards,<br><strong>Your Team</strong></p>
                                </div>
                            </div>
                        </body>
                        </html>
                        """
                        
                        # Try to render with st.components
                        st.components.v1.html(simple_html, height=700, scrolling=True)
                        
                    except Exception as e:
                        st.error(f"Browser preview failed: {e}")
                        st.info("💡 The browser preview feature may not work in all environments. Try 'Interactive Preview' instead!")
                        
                        # Show fallback info
                        st.warning("**Fallback:** Download the HTML file and open it in your browser for the full preview.")
                        
                        # Show basic info
                        st.markdown("**Email Summary:**")
                        st.write(f"**Subject:** {generated_email['subject']}")
                        if image_url:
                            st.write(f"**Image:** Included")
                        st.write(f"**Content Length:** {len(generated_email['body'])} characters")
                        st.write(f"**Call to Action:** {generated_email['cta']}")
            
            # Action buttons
            st.subheader("📥 Download & Actions")
            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            
            with action_col1:
                if st.button("🔄 Regenerate", help="Generate a new version"):
                    st.rerun()
            
            with action_col2:
                # Text version download
                full_email = f"Subject: {generated_email['subject']}\n\n{generated_email['body']}\n\nCall to Action: {generated_email['cta']}"
                if image_url:
                    full_email = f"Image URL: {image_url}\n\n{full_email}"
                
                st.download_button(
                    label="📋 Download Text",
                    data=full_email,
                    file_name=f"email_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    help="Download as plain text"
                )
            
            with action_col3:
                # HTML version download
                html_email = generator.create_email_html(generated_email, image_url)
                st.download_button(
                    label="📧 Download HTML",
                    data=html_email,
                    file_name=f"email_html_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    help="Download as HTML email"
                )
            
            with action_col4:
                if st.button("💾 Save Email", help="Save to session for later"):
                    # Save to session state
                    if 'saved_emails' not in st.session_state:
                        st.session_state.saved_emails = []
                    
                    saved_email = generated_email.copy()
                    saved_email['image_url'] = image_url
                    saved_email['user_input'] = user_input
                    
                    st.session_state.saved_emails.append(saved_email)
                    st.success("✅ Email saved!")
        
        with col2:
            st.header("🎯 Similar Examples")
            st.write("AI found these successful emails:")
            
            for i, email in enumerate(similar_emails[:3]):
                with st.expander(f"📧 Example {i+1}", expanded=i==0):
                    # Similarity score badge
                    score_color = "success" if email['score'] > 0.8 else "warning" if email['score'] > 0.6 else "error"
                    st.markdown(f'<div class="similarity-score">Match: {email["score"]:.0%}</div>', unsafe_allow_html=True)
                    
                    st.write(f"**Subject:** {email['subject']}")
                    st.write(f"**Category:** {email.get('category', 'N/A')}")
                    
                    # Show email preview
                    preview_text = email['body'][:200] + "..." if len(email['body']) > 200 else email['body']
                    st.write(f"**Preview:** {preview_text}")
                    
                    # Show features with icons
                    features = []
                    if email.get('has_discount'):
                        features.append("💰 Discount")
                    if email.get('has_urgency'):
                        features.append("⚡ Urgency")
                    if email.get('brand'):
                        features.append(f"🏢 {email['brand']}")
                    
                    if features:
                        st.write(f"**Features:** {' | '.join(features)}")
            
            # Email performance metrics (mock data for demo)
            st.markdown("---")
            st.subheader("📊 Expected Performance")
            
            # Calculate predicted metrics based on similar emails
            avg_score = sum(e['score'] for e in similar_emails[:3]) / len(similar_emails[:3]) if similar_emails else 0.75
            
            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                predicted_open_rate = min(45, int(avg_score * 35 + 10))
                st.metric("Open Rate", f"{predicted_open_rate}%", delta="3%")
            with metric_col2:
                predicted_ctr = min(8, int(avg_score * 6 + 1))
                st.metric("Click Rate", f"{predicted_ctr}%", delta="1.2%")
            
            # Tips based on generated content
            st.subheader("💡 Optimization Tips")
            tips = []
            
            if len(generated_email['subject']) > 60:
                tips.append("📏 Consider shortening subject line")
            if '🚀' in generated_email['subject'] or '✨' in generated_email['subject']:
                tips.append("😊 Great use of emojis!")
            if any(word in generated_email['body'].lower() for word in ['limited', 'hurry', 'expires']):
                tips.append("⏰ Good urgency elements")
            if image_url:
                tips.append("🖼️ Visual content will boost engagement")
            
            for tip in tips[:3]:
                st.info(tip)
    
    # Show saved emails section
    if st.session_state.get('saved_emails'):
        st.markdown("---")
        st.header("💾 Saved Emails")
        
        saved_cols = st.columns(min(3, len(st.session_state.saved_emails)))
        
        for i, email in enumerate(st.session_state.saved_emails):
            with saved_cols[i % 3]:
                with st.container():
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>{email['subject'][:30]}...</h4>
                        <p><strong>Campaign:</strong> {email['user_input']['campaign_type']}</p>
                        <p><strong>Generated:</strong> {email['generated_at'][:10]}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"📧 View #{i+1}", key=f"view_saved_{i}"):
                        with st.expander(f"Saved Email #{i+1}", expanded=True):
                            st.write(f"**Subject:** {email['subject']}")
                            st.write(f"**Body:** {email['body']}")
                            st.write(f"**CTA:** {email['cta']}")
                            if email.get('image_url'):
                                st.image(email['image_url'], width=200)
                            
                            # Download saved email
                            html_email = generator.create_email_html(email, email.get('image_url'))
                            st.download_button(
                                label=f"📥 Download #{i+1}",
                                data=html_email,
                                file_name=f"saved_email_{i+1}.html",
                                mime="text/html",
                                key=f"download_saved_{i}"
                            )
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <p>🚀 <strong>AI Email Generator Pro</strong> - Powered by OpenAI & Advanced Analytics</p>
        <p>Generate high-converting marketing emails in seconds</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
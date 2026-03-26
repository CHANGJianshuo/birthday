#!/usr/bin/env python3
"""Analyze WeChat chat data and output statistics as JSON."""

import json
import re
import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from html import unescape

HTML_FILE = "/home/birthday/texts/私聊_Serendipity.html"
OUTPUT_FILE = "/home/birthday/stats.json"

# Read HTML and extract WEFLOW_DATA
with open(HTML_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Extract JSON array
match = re.search(r'window\.WEFLOW_DATA\s*=\s*(\[.*?\]);\s*</script>', content, re.DOTALL)
if not match:
    # try without semicolon
    match = re.search(r'window\.WEFLOW_DATA\s*=\s*(\[.*?\])\s*;?\s*$', content, re.MULTILINE | re.DOTALL)

data_str = match.group(1)
messages = json.loads(data_str)

print(f"Total messages loaded: {len(messages)}")

# Extract text from HTML bubble
def extract_text(html_b):
    """Extract plain text from the bubble HTML."""
    # Get message-text content
    texts = re.findall(r'<div class="message-text">(.*?)</div>', html_b)
    result = []
    for t in texts:
        # Remove inline emoji img tags
        t = re.sub(r'<img[^>]*?/>', '', t)
        # Remove other HTML tags
        t = re.sub(r'<[^>]+>', '', t)
        t = unescape(t).strip()
        if t and t not in ['[表情包]', '[图片]']:
            result.append(t)
    return ' '.join(result)

def extract_time_str(html_b):
    """Extract datetime string from bubble."""
    m = re.search(r'<div class="message-time">(.*?)</div>', html_b)
    return m.group(1) if m else None

def has_image(html_b):
    """Check if message contains an image."""
    return 'message-media image' in html_b

def extract_image_src(html_b):
    """Extract image src from bubble."""
    m = re.search(r'src="(\.\./images/[^"]+)"', html_b)
    return m.group(1) if m else None

def has_emoji(html_b):
    """Check if message contains custom emoji/sticker."""
    return 'message-media emoji' in html_b

def has_voice(html_b):
    return '<audio' in html_b

def has_video(html_b):
    return 'message-media video' in html_b

# Process all messages
text_messages = []  # (timestamp, sender, text)
all_texts_s0 = []  # Serendipity's texts
all_texts_s1 = []  # 常小黄's texts
image_messages = []  # messages with images
emoji_count = 0
voice_count = 0
video_count = 0
call_count = 0

hourly_dist = Counter()
daily_dist = defaultdict(int)
monthly_dist = defaultdict(int)

# Track latest chat time per day
latest_per_day = {}

for msg in messages:
    ts = msg['t']
    sender = msg['s']  # 0=Serendipity, 1=常小黄
    bubble = msg['b']

    dt = datetime.fromtimestamp(ts)
    hour = dt.hour
    date_str = dt.strftime('%Y-%m-%d')
    month_str = dt.strftime('%Y-%m')
    time_str = dt.strftime('%H:%M')

    hourly_dist[hour] += 1
    daily_dist[date_str] += 1
    monthly_dist[month_str] += 1

    # Track latest time per day
    if date_str not in latest_per_day or time_str > latest_per_day[date_str]:
        latest_per_day[date_str] = time_str

    text = extract_text(bubble)
    if text:
        text_messages.append((ts, sender, text))
        if sender == 0:
            all_texts_s0.append(text)
        else:
            all_texts_s1.append(text)

    if has_image(bubble):
        img_src = extract_image_src(bubble)
        if img_src:
            image_messages.append({
                'ts': ts,
                'sender': sender,
                'src': img_src,
                'date': dt.strftime('%Y-%m-%d %H:%M')
            })

    if has_emoji(bubble):
        emoji_count += 1
    if has_voice(bubble):
        voice_count += 1
    if has_video(bubble):
        video_count += 1
    if '[语音通话]' in bubble or '[视频通话]' in bubble:
        call_count += 1

# Basic stats
total_msgs = len(messages)
first_ts = messages[0]['t']
last_ts = messages[-1]['t']
first_dt = datetime.fromtimestamp(first_ts)
last_dt = datetime.fromtimestamp(last_ts)
days_span = (last_dt - first_dt).days + 1

s0_count = sum(1 for m in messages if m['s'] == 0)
s1_count = sum(1 for m in messages if m['s'] == 1)

# Find the latest chat time overall
latest_times = sorted(latest_per_day.items(), key=lambda x: x[1], reverse=True)
latest_chat = latest_times[0] if latest_times else None

# Find peak chatting hour
peak_hour = hourly_dist.most_common(1)[0]

# Find the most active day
most_active_day = max(daily_dist.items(), key=lambda x: x[1])

# Keyword counts
keywords_to_check = ['晚安', '早安', '好的', '哈哈', '想你', '想我', '开心', '吃饭', '睡觉', '宝', '嗯嗯', '好吧', 'hhh', '加油', '辛苦']
keyword_counts = {}
all_text_combined = ' '.join(all_texts_s0 + all_texts_s1)
for kw in keywords_to_check:
    cnt = all_text_combined.lower().count(kw.lower())
    if cnt > 0:
        keyword_counts[kw] = cnt

# Word frequency (simple character bigram for Chinese)
# Use simple segmentation: split by common patterns
def simple_word_freq(texts, top_n=30):
    """Simple word frequency without jieba."""
    # Count 2-4 char phrases
    stop_words = set(['的', '了', '是', '在', '我', '你', '他', '她', '它', '们', '这', '那', '有', '没', '不', '也', '都', '就', '会', '可以', '什么', '怎么', '吗', '呢', '啊', '哦', '嗯', '呀', '吧', '啦', '哒', '嘛', '哇', '噢', '嘿', '诶', '额', '唉', '哎', '一个', '一下', '然后', '还是', '但是', '因为', '所以', '如果', '虽然', '而且', '或者', '已经', '正在', '需要', '应该', '可能', '觉得', '知道', '这个', '那个', '自己', '一样', '这样', '那样', '现在', '今天', '明天', '昨天'])
    word_counter = Counter()
    for text in texts:
        # Remove common noise
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'[a-zA-Z0-9\s\.,!?，。！？~～…\-\+\(\)（）""''「」\u200b]+', ' ', text)
        # Extract 2-3 char segments
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        for length in [2, 3]:
            for j in range(len(chars) - length + 1):
                word = ''.join(chars[j:j+length])
                if word not in stop_words:
                    word_counter[word] += 1
        # Also count single meaningful chars
    return word_counter.most_common(top_n)

# Try to use jieba if available
try:
    import jieba
    def jieba_word_freq(texts, top_n=30):
        stop_words = set(['的', '了', '是', '在', '我', '你', '他', '她', '它', '们', '这', '那', '有', '没有', '不', '也', '都', '就', '会', '可以', '什么', '怎么', '吗', '呢', '啊', '哦', '嗯', '呀', '吧', '啦', '哒', '嘛', '哇', '噢', '嘿', '诶', '额', '唉', '哎', '一个', '一下', '然后', '还是', '但是', '因为', '所以', '如果', '虽然', '而且', '或者', '已经', '正在', '需要', '应该', '可能', '觉得', '知道', '这个', '那个', '自己', '一样', '这样', '那样', '现在', '今天', '明天', '昨天', '不是', '还有', '可以', '不了', '就是', '一点', '没有', '真的', '好的', '不会', '怎么', '为什么', '表情包', '图片', '语音转文字'])
        counter = Counter()
        for text in texts:
            text = re.sub(r'\[.*?\]', '', text)
            words = jieba.cut(text)
            for w in words:
                w = w.strip()
                if len(w) >= 2 and w not in stop_words and not re.match(r'^[\s\d\w\.,!?，。！？~～…\-\+\(\)（）""'']+$', w):
                    counter[w] += 1
        return counter.most_common(top_n)

    word_freq_s0 = jieba_word_freq(all_texts_s0, 20)
    word_freq_s1 = jieba_word_freq(all_texts_s1, 20)
    word_freq_all = jieba_word_freq(all_texts_s0 + all_texts_s1, 30)
    print("Using jieba for word segmentation")
except ImportError:
    word_freq_s0 = simple_word_freq(all_texts_s0, 20)
    word_freq_s1 = simple_word_freq(all_texts_s1, 20)
    word_freq_all = simple_word_freq(all_texts_s0 + all_texts_s1, 30)
    print("Using simple segmentation (jieba not available)")

# Prepare hourly distribution as list
hourly_list = [hourly_dist.get(h, 0) for h in range(24)]

# Daily distribution sorted
daily_sorted = sorted(daily_dist.items())

# Monthly distribution sorted
monthly_sorted = sorted(monthly_dist.items())

# Select some representative images (up to 6)
selected_images = image_messages[:13]  # all images

# Stats output
stats = {
    'total_messages': total_msgs,
    'first_date': first_dt.strftime('%Y-%m-%d'),
    'last_date': last_dt.strftime('%Y-%m-%d'),
    'days_span': days_span,
    'serendipity_count': s0_count,
    'changxiaohuang_count': s1_count,
    'emoji_count': emoji_count,
    'voice_count': voice_count,
    'video_count': video_count,
    'call_count': call_count,
    'image_count': len(image_messages),
    'latest_chat': {'date': latest_chat[0], 'time': latest_chat[1]} if latest_chat else None,
    'peak_hour': {'hour': peak_hour[0], 'count': peak_hour[1]},
    'most_active_day': {'date': most_active_day[0], 'count': most_active_day[1]},
    'hourly_distribution': hourly_list,
    'daily_distribution': daily_sorted,
    'monthly_distribution': monthly_sorted,
    'keyword_counts': keyword_counts,
    'word_freq_serendipity': word_freq_s0,
    'word_freq_changxiaohuang': word_freq_s1,
    'word_freq_all': word_freq_all,
    'images': selected_images,
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(f"\nStats saved to {OUTPUT_FILE}")
print(f"\n--- Summary ---")
print(f"Total messages: {total_msgs}")
print(f"Date range: {first_dt.strftime('%Y-%m-%d')} ~ {last_dt.strftime('%Y-%m-%d')} ({days_span} days)")
print(f"Serendipity sent: {s0_count}, 常小黄 sent: {s1_count}")
print(f"Emoji/stickers: {emoji_count}, Voice: {voice_count}, Images: {len(image_messages)}, Calls: {call_count}")
print(f"Latest chat: {latest_chat}")
print(f"Peak hour: {peak_hour[0]}:00 ({peak_hour[1]} msgs)")
print(f"Most active day: {most_active_day}")
print(f"\nKeyword counts: {keyword_counts}")
print(f"\nTop words (all): {word_freq_all[:15]}")
print(f"\nTop words (Serendipity): {word_freq_s0[:10]}")
print(f"\nTop words (常小黄): {word_freq_s1[:10]}")
print(f"\nImages found: {len(image_messages)}")
for img in image_messages:
    print(f"  {img['date']} - sender:{img['sender']} - {img['src']}")

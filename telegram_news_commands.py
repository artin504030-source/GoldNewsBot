import os, json, html, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ARCHIVE=ROOT/'news_archive.json'
OFFSET=ROOT/'telegram_update_offset.json'
TOKEN=os.getenv('BOT_TOKEN')
API=f'https://api.telegram.org/bot{TOKEN}' if TOKEN else ''
ALIASES={'/today':'day','/daily':'day','/day':'day','/news_today':'day','/week':'week','/weekly':'week','/news_week':'week','/month':'month','/monthly':'month','/news_month':'month'}
PERIODS={'day':('🗞 اخبار روز',1),'week':('📰 اخبار هفته',7),'month':('🌍 اخبار ماه',30)}
def parse_time(item):
    for key in ('published_utc','archived_at_utc'):
        raw=item.get(key)
        if raw:
            try:
                dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError,TypeError): pass
    return None
def load_archive(path=ARCHIVE):
    try:
        rows=json.loads(Path(path).read_text(encoding='utf-8'))
        return rows if isinstance(rows,list) else []
    except (OSError,ValueError): return []
def format_period_news(period,items,now=None,limit=8):
    if period not in PERIODS: return 'دستور نامعتبر است. /help را ببینید.'
    label,days=PERIODS[period]; now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: now=now.replace(tzinfo=timezone.utc)
    cutoff=now-timedelta(days=days); selected=[]
    for item in items:
        dt=parse_time(item)
        if dt and cutoff<=dt<=now: selected.append((dt,item))
    selected.sort(key=lambda x:x[0],reverse=True)
    if not selected: return f'{label}\n\nدر آرشیو {days} روز گذشته خبر ثبت‌شده‌ای یافت نشد.'
    lines=[label,f'📆 بازه: {days} روز گذشته | 📊 تعداد خبر: {len(selected)}','────────────']
    for i,(dt,item) in enumerate(selected[:limit],1):
        title=html.escape(str(item.get('title') or 'بدون عنوان')); cat=html.escape(str(item.get('category') or 'خبر')); imp=html.escape(str(item.get('importance') or 'نامشخص'))
        link=str(item.get('link') or ''); date=dt.strftime('%Y-%m-%d %H:%M UTC')
        lines.append(f'{i}) <b>{title}</b>\n🏷 {cat} | اهمیت: {imp}\n🕒 {date}')
        if link.startswith(('https://','http://')): lines.append(f'🔗 <a href="{html.escape(link,quote=True)}">منبع خبر</a>')
        lines.append('')
    if len(selected)>limit: lines.append(f'\nℹ️ {len(selected)-limit} خبر دیگر در آرشیو موجود است.')
    lines.append('\n⚠️ اخبار بر اساس آرشیو ذخیره‌شده است؛ ممکن است همه اخبار بازار پوشش داده نشود.')
    return '\n'.join(lines)
def help_message():
    return ('🤖 <b>دستورات اخبار گلد نیوز</b>\n\n'
        '/today، /daily یا /news_today — اخبار ۲۴ ساعت اخیر\n'
        '/week، /weekly یا /news_week — اخبار ۷ روز اخیر\n'
        '/month، /monthly یا /news_month — اخبار ۳۰ روز اخیر\n'
        '/help — راهنمای دستورات\n\nخبرها از آرشیو ثبت‌شده نمایش داده می‌شوند.')
def build_reply(command,items,now=None):
    cmd=command.strip().split()[0].lower().split('@',1)[0]
    period=ALIASES.get(cmd)
    if cmd in ('/help','/start'): return help_message()
    if period: return format_period_news(period,items,now)
    return 'دستور شناخته نشد. /help را بفرستید.'
def telegram(method,**kwargs):
    r=requests.post(f'{API}/{method}',json=kwargs,timeout=30); r.raise_for_status(); data=r.json()
    if not data.get('ok'): raise RuntimeError(data)
    return data.get('result')
def main():
    if not TOKEN: raise SystemExit('BOT_TOKEN secret is missing')
    archive=load_archive(); offset=0
    try: offset=int(json.loads(OFFSET.read_text()).get('offset',0))
    except (OSError,ValueError,TypeError): pass
    updates=telegram('getUpdates',offset=offset,timeout=0,allowed_updates=['message']); next_offset=offset
    for update in updates:
        next_offset=max(next_offset,int(update.get('update_id',0))+1)
        msg=update.get('message') or {}; text=msg.get('text') or ''; chat=msg.get('chat') or {}; chat_id=chat.get('id')
        if not chat_id or not text.startswith('/'): continue
        telegram('sendMessage',chat_id=chat_id,text=build_reply(text,archive),parse_mode='HTML',disable_web_page_preview=True)
    OFFSET.write_text(json.dumps({'offset':next_offset}),encoding='utf-8')
    print(f'Handled {len(updates)} updates; next offset {next_offset}')
if __name__=='__main__': main()

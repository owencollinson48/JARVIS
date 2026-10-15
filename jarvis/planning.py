"""Local calendar, meaningful proactive notices and explicit cross-channel task commands."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Blueprint, current_app, jsonify, request
from . import storage

bp=Blueprint('planning',__name__,url_prefix='/api/planning')
DEFAULTS=dict(timezone='UTC',interval=15,quiet_start=22,quiet_end=7,proactive=True)


def connect():return storage.connect(current_app.config['DATABASE'])


def config(db):
    row=db.execute("SELECT value FROM settings WHERE key='planner_config'").fetchone()
    return {**DEFAULTS,**(json.loads(row[0]) if row else {})}


def now_local(db):return datetime.now(ZoneInfo(config(db)['timezone']))


def quiet(db):
    cfg=config(db);hour=now_local(db).hour;a,b=cfg['quiet_start'],cfg['quiet_end']
    return (a<=hour<b) if a<b else (hour>=a or hour<b) if a!=b else False


def local_datetime(value,zone):
    try:
        parsed=datetime.fromisoformat(value)
        z=ZoneInfo(zone)
        if parsed.tzinfo:return parsed.astimezone(timezone.utc)
        aware=parsed.replace(tzinfo=z)
        if aware.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)!=parsed:
            raise ValueError('That local time does not exist during the clock change.')
        if aware.utcoffset()!=parsed.replace(tzinfo=z,fold=1).utcoffset():
            raise ValueError('That local time is ambiguous during the clock change. Supply an explicit UTC offset.')
        return aware.astimezone(timezone.utc)
    except (TypeError,ZoneInfoNotFoundError):raise ValueError('Choose a valid date/time and IANA timezone.') from None


def occurrences(db,days=14):
    current=now_local(db);finish=current+timedelta(days=days);result=[]
    for row in db.execute('SELECT * FROM calendar_events ORDER BY start'):
        item=dict(row);zone=ZoneInfo(item['timezone'])
        initial=datetime.fromisoformat(item['start']).astimezone(zone)
        initial_end=datetime.fromisoformat(item['end']).astimezone(zone)
        count=53 if item['recurrence']=='weekly' else 1
        for week in range(count):
            start=(initial.replace(tzinfo=None)+timedelta(weeks=week)).replace(tzinfo=zone)
            end=(initial_end.replace(tzinfo=None)+timedelta(weeks=week)).replace(tzinfo=zone)
            if item['until_date'] and start.date()>date.fromisoformat(item['until_date']):break
            if end<current or start>finish:continue
            result.append({**item,'start':start.isoformat(),'end':end.isoformat()})
    return sorted(result,key=lambda e:datetime.fromisoformat(e['start']))[:300]


def brief(db):
    current=now_local(db);today=current.date()
    tasks=[dict(row) for row in db.execute('SELECT * FROM tasks WHERE completed=0 ORDER BY due,priority')]
    events=occurrences(db)
    conflicts=[]
    for index,a in enumerate(events):
        for b in events[index+1:]:
            if {a['kind'],b['kind']}!={'work','university'}:continue
            if max(datetime.fromisoformat(a['start']),datetime.fromisoformat(b['start']))<min(datetime.fromisoformat(a['end']),datetime.fromisoformat(b['end'])):
                conflicts.append(dict(first=a['title'],second=b['title'],start=max(datetime.fromisoformat(a['start']),datetime.fromisoformat(b['start'])).isoformat()))
    slots=[]
    for day_offset in range(7):
        day=today+timedelta(days=day_offset)
        for hour in (9,11,14,16,18):
            start=datetime.combine(day,datetime.min.time(),ZoneInfo(config(db)['timezone']))+timedelta(hours=hour)
            end=start+timedelta(hours=2)
            if start<current:continue
            if not any(datetime.fromisoformat(e['start'])<end and datetime.fromisoformat(e['end'])>start for e in events):
                slots.append(dict(start=start.isoformat(),end=end.isoformat(),basis='No conflict in your saved calendar only; unrecorded commitments are unknown.'))
        if len(slots)>=3:break
    overdue=[t for t in tasks if t['due']<today.isoformat()]
    soon=[t for t in tasks if 0<=(date.fromisoformat(t['due'])-today).days<=3]
    next_shift=next((e for e in events if e['kind']=='work'),None)
    return dict(date=today.isoformat(),timezone=config(db)['timezone'],overdue=overdue,approaching=soon,
                events=events,conflicts=conflicts,study_suggestions=slots[:3],next_shift=next_shift,
                summary=f'{len(overdue)} overdue tasks, {len(soon)} deadlines within three days, {len(conflicts)} saved university/work conflicts. Only saved data is included.')


def notice(db,key,category,body,task_id=None):
    db.execute('INSERT OR IGNORE INTO notices(dedupe,category,body,task_id,created) VALUES(?,?,?,?,?)',
               (key,category,body,task_id,datetime.now(timezone.utc).isoformat()))


def tick(db,force=False):
    cfg=config(db)
    if not cfg['proactive'] or quiet(db):return
    data=brief(db);today=data['date']
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    previous=db.execute("SELECT value FROM settings WHERE key='planner_last'").fetchone()
    stamp=db.execute("SELECT value FROM settings WHERE key='planner_tick'").fetchone()
    now=datetime.now(timezone.utc)
    changed=not previous or previous[0]!=fingerprint
    if not force and not changed and stamp and (now-datetime.fromisoformat(stamp[0])).total_seconds()<cfg['interval']*60:return
    for task in data['overdue']:
        notice(db,f'overdue:{task["id"]}:{task["due"]}:{today}','deadlines',f'Task {task["id"]}: {task["title"]} is overdue (saved due date {task["due"]}). Would prioritising it help?',task['id'])
    for task in data['approaching']:
        notice(db,f'due:{task["id"]}:{task["due"]}:{today}','deadlines',f'Task {task["id"]}: {task["title"]} is due {task["due"]}. Would you like to plan a study session?',task['id'])
    for conflict in data['conflicts']:
        notice(db,'conflict:'+hashlib.sha256(json.dumps(conflict,sort_keys=True).encode()).hexdigest(),'important',f'Saved calendar conflict: {conflict["first"]} overlaps {conflict["second"]}. Please review the times.')
    if data['next_shift']:
        shift=data['next_shift']
        if datetime.fromisoformat(shift['start']).date().isoformat()==today:
            notice(db,f'shift:{shift["id"]}:{shift["start"]}','work',f'Your next saved shift is {shift["title"]}, starting {shift["start"]}.')
    hour=now_local(db).hour
    for category,start,end in [('morning',7,12),('evening',18,22)]:
        if start<=hour<end:notice(db,f'{category}:{today}',category,data['summary'])
    for key,value in [('planner_last',fingerprint),('planner_tick',now.isoformat())]:
        db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))


def state(db):
    tick(db)
    return dict(config=config(db),briefing=brief(db),events=[dict(r) for r in db.execute('SELECT * FROM calendar_events ORDER BY start')],
                notices=[dict(r) for r in db.execute('SELECT * FROM notices ORDER BY id DESC LIMIT 60')])


@bp.get('/state')
def get_state():
    with connect() as db:return jsonify(state(db))


@bp.put('/settings')
def settings():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('Choose planning settings.')
    try:ZoneInfo(data.get('timezone',''))
    except (ZoneInfoNotFoundError,ValueError,TypeError):raise ValueError('Use an IANA timezone such as Australia/Brisbane.') from None
    if type(data.get('interval')) is not int or not 5<=data['interval']<=120:raise ValueError('Check interval must be 5–120 minutes.')
    if any(type(data.get(k)) is not int or not 0<=data[k]<=23 for k in ('quiet_start','quiet_end')):raise ValueError('Quiet hours must be 0–23.')
    if type(data.get('proactive')) is not bool:raise ValueError('Choose whether proactivity is enabled.')
    with connect() as db:db.execute("INSERT INTO settings VALUES('planner_config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({k:data[k] for k in DEFAULTS}),))
    return jsonify(ok=True)


def event_values(data):
    if not isinstance(data,dict) or not isinstance(data.get('title'),str) or not 1<=len(data['title'].strip())<=160:raise ValueError('Enter an event title (1–160 characters).')
    if data.get('kind') not in ('university','work','personal','study'):raise ValueError('Choose a valid event type.')
    with connect() as db:zone=config(db)['timezone']
    start=local_datetime(data.get('start'),zone);end=local_datetime(data.get('end'),zone)
    if not timedelta(0)<end-start<=timedelta(days=7):raise ValueError('End must follow start, within seven days.')
    repeat=data.get('recurrence','none');until=data.get('until_date') or None
    if repeat not in ('none','weekly'):raise ValueError('Choose none or weekly recurrence.')
    if repeat=='weekly':
        if not until or not start.astimezone(ZoneInfo(zone)).date()<=date.fromisoformat(until)<=start.astimezone(ZoneInfo(zone)).date()+timedelta(days=365):raise ValueError('Weekly recurrence needs an end date within one year.')
    pause=data.get('break_minutes',0)
    if type(pause) is not int or not 0<=pause<(end-start).total_seconds()/60:raise ValueError('Break length must be shorter than the event.')
    return (data['title'].strip(),data['kind'],start.isoformat(),end.isoformat(),zone,repeat,until,pause)


@bp.post('/events')
def add_event():
    values=event_values(request.get_json(silent=True))
    with connect() as db:
        cursor=db.execute('INSERT INTO calendar_events(title,kind,start,end,timezone,recurrence,until_date,break_minutes) VALUES(?,?,?,?,?,?,?,?)',values)
        return jsonify(id=cursor.lastrowid),201


@bp.put('/events/<int:identifier>')
def edit_event(identifier):
    values=event_values(request.get_json(silent=True))
    with connect() as db:
        if not db.execute('UPDATE calendar_events SET title=?,kind=?,start=?,end=?,timezone=?,recurrence=?,until_date=?,break_minutes=? WHERE id=?',(*values,identifier)).rowcount:return jsonify(error='Event not found.'),404
    return jsonify(ok=True)


@bp.delete('/events/<int:identifier>')
def delete_event(identifier):
    with connect() as db:
        if not db.execute('DELETE FROM calendar_events WHERE id=?',(identifier,)).rowcount:return jsonify(error='Event not found.'),404
    return jsonify(ok=True)


@bp.put('/notices/<int:identifier>')
def read_notice(identifier):
    with connect() as db:db.execute("UPDATE notices SET status='read' WHERE id=?",(identifier,))
    return jsonify(ok=True)


def task_command(db,content,channel='desktop'):
    """Only explicit instructions write tasks; ambiguous pronouns never guess."""
    today=now_local(db).date();text=content.strip().rstrip('.!?')
    def day(value):
        value=value.lower().strip()
        if value=='tomorrow':return today+timedelta(days=1)
        if value=='today':return today
        weekdays=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
        if value in weekdays:return today+timedelta(days=(weekdays.index(value)-today.weekday())%7 or 7)
        return date.fromisoformat(value)
    match=re.fullmatch(r'remind me to (.{1,160}?) (today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{4}-\d{2}-\d{2})',text,re.I)
    if match:
        due=day(match[2]).isoformat();cursor=db.execute("INSERT INTO tasks(title,due,priority,project,completed) VALUES(?,?,'Medium','Personal Life',0)",(match[1],due))
        identifier=cursor.lastrowid
        db.execute("INSERT INTO channel_context VALUES('owner',?) ON CONFLICT(channel) DO UPDATE SET task_id=excluded.task_id",(identifier,))
        return dict(reply=f'Saved task {identifier}: {match[1]}, due {due}. Notification delivery follows your approved rules.',task_id=identifier)
    match=re.fullmatch(r'(?:move|reschedule) (it|task \d+) to (today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{4}-\d{2}-\d{2})',text,re.I)
    if match:
        if match[1].lower()=='it':
            row=db.execute("SELECT task_id FROM channel_context WHERE channel='owner'").fetchone()
            if not row or row[0] is None:return dict(reply='Which task do you mean? Say move task followed by its number and the new date.')
            identifier=row[0]
        else:identifier=int(match[1].split()[1])
        due=day(match[2]).isoformat()
        if not db.execute('UPDATE tasks SET due=? WHERE id=?',(due,identifier)).rowcount:return dict(reply='That task no longer exists. Please name another task number.')
        db.execute("INSERT INTO channel_context VALUES('owner',?) ON CONFLICT(channel) DO UPDATE SET task_id=excluded.task_id",(identifier,))
        return dict(reply=f'Task {identifier} moved to {due}.',task_id=identifier)
    return None

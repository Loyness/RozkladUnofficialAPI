from flask import Flask, request, Response
import os
import json
import time

import download_info

app = Flask(__name__)

_CACHE = {
    'data': None,
    'url': None,
    'ts': 0
}


def load_data(url=None, refresh=False, ttl=60):
    if url is None:
        url = os.environ.get('ROZKLAD_URL')
    now = time.time()
    if not refresh and _CACHE['data'] is not None and _CACHE['url'] == url and (now - _CACHE['ts']) < ttl:
        return _CACHE['data']
    html = download_info.fetch(url)
    data = download_info.parse(html)
    _CACHE.update({'data': data, 'url': url, 'ts': now})
    return data


def json_resp(obj, status=200):
    return Response(json.dumps(obj, ensure_ascii=False, indent=2), mimetype='application/json', status=status)


@app.route('/') # Головна сторінка
def index():
    return json_resp({'message': 'Вітаю у не оффіційному Rozklad API! Використовуй після адреси /predms, /auds, /days, /unums_c, /classes, /class_schedule, /teachers, /teacher_schedule кінцеві точки.'})

@app.route('/predms') # Предмети
def get_predms():
    data = load_data()
    predms = data.get('predms') if isinstance(data, dict) else None
    if predms is None:
        return json_resp({'error': 'predms not available'}, 404)
    return json_resp(predms)

@app.route('/auds') # Класи
def get_auds():
    data = load_data()
    auds = data.get('auds') if isinstance(data, dict) else None
    if auds is None:
        return json_resp({'error': 'auds not available'}, 404)
    return json_resp(auds)

@app.route('/days') # Дні тижня
def get_days():
    data = load_data()
    days = data.get('days') if isinstance(data, dict) else None
    if days is None:
        return json_resp({'error': 'days not available'}, 404)
    return json_resp(days)


@app.route('/unums_c') # Номери уроків (Для класів)
def get_unums_c():
    data = load_data()
    unums = data.get('unums_c') if isinstance(data, dict) else None
    if unums is None:
        return json_resp({'error': 'unums_c not available'}, 404)
    return json_resp(unums)


@app.route('/classes') # Класи
def list_classes():
    data = load_data()
    classes = data.get('classes') if isinstance(data, dict) else None
    if not classes:
        return json_resp({'error': 'classes not available'}, 404)
    out = {cid: info.get('name') for cid, info in classes.items()}
    return json_resp(out)

def find_class(classes, identifier):
    if identifier in classes:
        return classes[identifier]
    for cid, info in classes.items():
        if info.get('name') == identifier:
            return info
    return None

@app.route('/class_schedule') # Розклад для класу
def class_schedule():
    cls_id = request.args.get('id')
    cls_name = request.args.get('name')
    refresh = request.args.get('refresh') == '1'
    data = load_data(refresh=refresh)
    classes = data.get('classes') if isinstance(data, dict) else None
    if not classes:
        return json_resp({'error': 'classes not available'}, 404)
    target = None
    if cls_id:
        target = classes.get(str(cls_id)) or classes.get(int(cls_id))
    if not target and cls_name:
        target = find_class(classes, cls_name)
    if not target:
        return json_resp({'error': 'class not found; provide id or exact name (e.g. "1-А")'}, 404)
    return json_resp({'name': target.get('name'), 'roz': target.get('roz')})


@app.route('/teachers') # Вчителі
def list_teachers():
    data = load_data()
    teachers = data.get('teachers') if isinstance(data, dict) else None
    if not teachers:
        return json_resp({'error': 'teachers not available'}, 404)
    out = {tid: info.get('name') for tid, info in teachers.items()}
    return json_resp(out)


def find_teacher_by_name(teachers, name):
    for tid, info in teachers.items():
        if info.get('name') == name:
            return tid, info
    return None, None


@app.route('/teacher_schedule') # Розклад для вчителя
def teacher_schedule():
    t_id = request.args.get('id')
    t_name = request.args.get('name')
    refresh = request.args.get('refresh') == '1'
    data = load_data(refresh=refresh)
    teachers = data.get('teachers') if isinstance(data, dict) else None
    if not teachers:
        return json_resp({'error': 'teachers not available'}, 404)
    target = None
    if t_id:
        target = teachers.get(str(t_id)) or teachers.get(int(t_id))
    if not target and t_name:
        tid, info = find_teacher_by_name(teachers, t_name)
        if tid:
            target = info
    if not target:
        return json_resp({'error': 'teacher not found; provide id or exact name (e.g. "Іванюк А.І.")'}, 404)
    return json_resp({'name': target.get('name'), 'roz': target.get('roz')})

@app.route('/classes_convenient') # Розклад для класу у зручному для використання форматі
def classes_converted():
    c_id = request.args.get('id')
    c_name = request.args.get('name')
    query = c_id or c_name
    
    data = load_data()
    classes = data.get('classes', {})
    teachers = data.get('teachers', {})
    subjects = data.get('predms', {})
    auds = data.get('auds', {})

    target_class = find_class(classes, query)
    
    if not target_class:
        return json_resp({'error': 'Class not found'}, 404)

    readable_schedule = {}
    original_roz = target_class.get('roz', {})

    for day, periods in original_roz.items():
        readable_schedule[day] = {}
        for period_num, lessons in periods.items():
            readable_lessons = []
            for lesson in lessons:
                subject_name = subjects.get(str(lesson.get('p')), "Unknown Subject")
                
                lesson_details = []
                for n in lesson.get('nums', []):
                    teacher_id = str(n.get('t'))
                    teacher_info = teachers.get(teacher_id, {})
                    teacher_name = teacher_info.get('name', "Unknown Teacher")
                    room_name = auds.get(str(n.get('a')), "Unknown Room")
                    
                    lesson_details.append({
                        "teacher": teacher_name,
                        "room": room_name,
                        "group": n.get('g')
                    })

                readable_lessons.append({
                    "subject": subject_name,
                    "details": lesson_details
                })
            readable_schedule[day][period_num] = readable_lessons

    return json_resp({
        "class_name": target_class.get('name'),
        "schedule": readable_schedule
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)

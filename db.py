from datetime import datetime, timedelta

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

from models import User, Task, Subtask
from config import DB_URI

engine = create_engine(DB_URI)
Session = sessionmaker()
Session.configure(bind=engine)
session = Session()


def get_reminders():
    return session.query(Task).filter_by(reminder=True).all()


def register_user(uid):
    u = User(uid)
    session.add(u)
    session.commit()


def find_tasks(uid):
    return session.query(Task).filter(or_(Task.owner == uid, Task.assignee == uid)).all()


def find_subtasks(parent):
    return session.query(Subtask).filter_by(parent=parent).all()


def new_task(uid, task):
    t = Task(owner=uid, note=task)
    session.add(t)
    session.commit()


def check_for_task(owner, note):
    return session.query(Task).filter_by(owner=owner, note=note).first()


def check_for_sub(note, parent):
    return session.query(Subtask).filter_by(note=note, parent=parent)


def new_subtask(sub, main):
    s = Subtask(note=sub, parent=main)
    session.add(s)
    session.commit()


def find_by_note(uid, note):
    return session.query(Task).filter_by(owner=uid, note=note).first()


def remove_task(uid, note):
    session.query(Task).filter_by(owner=uid, note=note).delete()
    session.commit()


def remove_sub(uid, parent, note):
    session.query(Subtask).filter_by(note=note,
                                     parent=find_by_note(uid, note=parent).id).delete()
    session.commit()


def make_assignee(uid, note, assignee):
    if find_user(uid=assignee) and uid is not assignee:
        task = session.query(Task).filter_by(owner=uid, note=note).first()
        task.assignee = assignee
        session.commit()


def find_user(uid):
    return session.query(User).filter_by(id=uid).first()


def reminder(uid, note):
    task = find_by_note(uid=uid, note=note)

    task.reminder = True if not task.reminder else False
    session.commit()
    return 'on' if task.reminder else 'off'


def style(uid):
    user = find_user(uid=uid)
    user.style = True if (user.style is False) else False
    session.commit()
    return 'traditional' if user.style else 'kanban'


def finish(uid, note):
    find_by_note(uid=uid, note=note).done = True
    session.commit()


def change_note(uid, note, new_note):
    session.query(Task).filter_by(owner=uid, note=note).first().note = new_note
    session.commit()


def change_deadline(uid, note, new_value):
    session.query(Task).filter_by(owner=uid, note=note).first().deadline = new_value
    session.commit()


def get_style(uid):
    return session.query(User).filter_by(id=uid).first().style


def get_done(uid):
    return session.query(Task).filter_by(owner=uid, done=True).all()


def get_undone(uid):
    return session.query(Task).filter_by(owner=uid, done=False).all()

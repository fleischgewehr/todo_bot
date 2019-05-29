from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    style = Column(Boolean, default=True)   # true - traditional

    children = relationship('Task', backref='parent_rel', passive_deletes=True)

    def __init__(self, id_, style=True):
        self.id = id_
        self.style = style

    def __repr__(self):
        return f'<User {self.id}>'


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    note = Column(String, nullable=False)
    deadline = Column(DateTime, default=None)
    reminder = Column(Boolean, default=False)
    done = Column(Boolean, default=False)
    owner = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    assignee = Column(Integer, default=0)   # person who was assigned to this task

    children = relationship('Subtask', backref='parent_rel', passive_deletes=True)

    def __init__(self, note, owner):
        self.note = note
        self.owner = owner

    def __repr__(self):
        return f'<Task: {self.note} until {self.deadline} is {self.done}>'


class Subtask(Base):
    __tablename__ = 'subtasks'

    id = Column(Integer, primary_key=True)
    note = Column(String, nullable=False)
    done = Column(Boolean, default=False)
    parent = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'))

    def __init__(self, note, parent):
        self.note = note
        self.parent = parent

    def __repr__(self):
        return f'<Sub-task: {self.note} of {self.parent} is {self.done}>'

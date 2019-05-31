from datetime import datetime, timedelta

import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler

from config import API_TOKEN
from db import *
from misc import *

bot = telebot.TeleBot(API_TOKEN)


# job for scheduler
def reminder_job():
    tasks = get_reminders()
    for task in tasks:
        if task.deadline - datetime.now() <= timedelta(days=3):
            bot.send_message(task.owner, f'It\'s almost deadline for '
            f'your {task.note} task!')


# cancel decorator
def cancel(func):
    def is_cancelled(message, *args, **kwargs):
        if message.text == '/cancel':
            k = types.ReplyKeyboardRemove()
            bot.reply_to(message, 'Cancelled', reply_markup=k)
            return
        return func(message, *args, **kwargs)
    return is_cancelled


@bot.message_handler(commands=['start'])
def start_message(message):
    if not find_user(message.chat.id):
        register_user(message.chat.id)
    bot.send_message(message.chat.id, 'Welcome. Type /help to get command list')


@bot.message_handler(commands=['help'])
def help_msg(message):
    bot.reply_to(message, HELP_MSG)


@bot.message_handler(commands=['show'])
def show_tasks(message):
    uid = message.chat.id
    if get_style(uid=uid) is True:  # traditional view
        tasks = find_tasks(uid)
        msg = '<b>HERE ARE YOUR TASKS:</b>\n\n'
        for task in tasks:
            subs = find_subtasks(parent=task.id)
            msg += f'- {task.note} is <b>{STATE[task.done]}</b>\n'
            if task.deadline:
                msg += f'\t<i>until {datetime.strftime(task.deadline, "%d.%m.%Y")}</i>\n'
            if subs:
                for sub in subs:
                    msg += f'\t* {sub.note} is <b>{STATE[sub.done]}</b>\n'
            msg += '\n'
    else:   # kanban view
        done = get_done(uid=uid)
        undone = get_undone(uid=uid)
        msg = '<b>TO-DO:</b>\n\n'
        msg = kanban_list(tasks=undone, msg=msg)
        msg += '<b>DONE:</b>\n\n'
        msg = kanban_list(tasks=done, msg=msg)

    bot.send_message(message.chat.id, msg, parse_mode='HTML')


def kanban_list(tasks, msg):
    for task in tasks:
        subs = find_subtasks(parent=task.id)
        msg += f'- {task.note}\n'
        if task.deadline:
            msg += f'\t<i>until {datetime.strftime(task.deadline, "%d.%m.%Y")}</i>\n'
        if subs:
            for sub in subs:
                msg += f'\t* {sub.note}\n'
        msg += '\n'
    return msg


@bot.message_handler(commands=['task'])
def add_task(message):
    msg = bot.reply_to(message, 'Send me task description (max 100 characters)')
    bot.register_next_step_handler(msg, process_task)


@cancel
def process_task(message):
    uid = message.chat.id
    task = message.text
    if len(task) <= 100 and not check_for_task(owner=uid, note=task):
        try:
            new_task(uid=uid, task=task)
            bot.reply_to(message, 'OK! You can specify other details using /edit')

        except Exception as e:
            bot.reply_to(message, 'Whoops, something went wrong')
        return

    bot.reply_to(message, 'It\'s wrong out there, try again')


@bot.message_handler(commands=['sub'])
def add_subtask(message):
    parent_select = types.ReplyKeyboardMarkup(one_time_keyboard=True,
                                              resize_keyboard=True)
    tasks = find_tasks(uid=message.chat.id)
    if len(tasks) % 2 == 1:
        tasks.append(Task(note='---', owner=None))

    paired = list(zip(tasks[0::2], tasks[1::2]))  # make paired tuples of tasks
    for pair in paired:
        parent_select.add(pair[0].note, pair[1].note)

    msg = bot.reply_to(message, 'OK! Now choose the main task',
                       reply_markup=parent_select)
    bot.register_next_step_handler(msg, process_subtask)


@cancel
def process_subtask(message):
    if check_for_task(owner=message.chat.id, note=message.text):
        msg = bot.reply_to(message,
                           'Send me sub-task description (max 50 characters)')
        bot.register_next_step_handler(msg, finish_subtask,
                                       parent_task=message.text)
        return

    bot.reply_to(message, 'There is no such task')


@cancel
def finish_subtask(message, parent_task=None):
    task = message.text
    uid = message.chat.id

    if len(task) <= 50 and \
            check_for_sub(note=task,
                          parent=find_by_note(uid=uid, note=parent_task).id) is not None:
        try:
            if task[0] == '/':
                task = task[1:]
            new_subtask(sub=task,
                        main=find_by_note(uid=uid, note=parent_task).id)
            bot.reply_to(message, 'Done')
        except Exception as e:
            bot.reply_to(message, 'An error occurred. Try again')
        return

    bot.reply_to(message, f'Something is wrong. Try again')


@bot.message_handler(commands=['edit'])
def edit_task(message):
    tasks = find_tasks(uid=message.chat.id)

    task_select = types.ReplyKeyboardMarkup(one_time_keyboard=True,
                                            resize_keyboard=True)

    # if tasks are odd, add dummy to keep the symmetry
    if len(tasks) % 2 == 1:
        tasks.append(Task(note='---', owner=None))

    paired = list(zip(tasks[0::2], tasks[1::2]))  # make paired tuples of tasks
    for pair in paired:
        task_select.add(pair[0].note, pair[1].note)

    msg = bot.reply_to(message, 'Choose a task', reply_markup=task_select)
    bot.register_next_step_handler(msg, edit_menu)


@cancel
def edit_menu(message, note=None):
    if find_by_note(uid=message.chat.id, note=message.text):
        option_select = types.ReplyKeyboardMarkup(one_time_keyboard=True,
                                                  resize_keyboard=True)
        option_select.add('Finish', 'Delete')
        if not note:
            option_select.add('Change note', 'Reminder')
            option_select.add('Deadline', 'Assignee')
            option_select.add('Sub-tasks')

        msg = bot.reply_to(message, 'Choose option', reply_markup=option_select)
        bot.register_next_step_handler(msg, process_option,
                                       note=note if note else message.text)
    else:
        k = types.ReplyKeyboardRemove()
        bot.reply_to(message, 'No such task', reply_markup=k)


@cancel
def process_option(message, note=None):
    option = message.text
    uid = message.chat.id
    k = types.ReplyKeyboardRemove()

    try:
        if option == 'Sub-tasks':
            subs = find_subtasks(parent=find_by_note(uid=uid, note=note).id)
            if not subs:
                bot.reply_to(message, 'This task have no sub-tasks')
                types.ReplyKeyboardRemove()
                return

            task_select = types.ReplyKeyboardMarkup(one_time_keyboard=True,
                                                    resize_keyboard=True)
            # if tasks are odd, add dummy to keep the symmetry
            if len(subs) % 2 == 1:
                subs.append(Task(note='---', owner=None))

            paired = list(zip(subs[0::2], subs[1::2]))  # make paired tuples of tasks
            for pair in paired:
                task_select.add(pair[0].note, pair[1].note)

            msg = bot.reply_to(message, 'Now choose an option',
                               reply_markup=task_select)
            bot.register_next_step_handler(msg, edit_menu, note=note)
            return

        elif option == 'Finish':
            finish(uid=uid, note=note)
            bot.reply_to(message, 'Done', reply_markup=k)
            return

        elif option == 'Reminder':
            if find_by_note(uid=uid, note=note).deadline is None:
                bot.reply_to(message, 'This task have no deadline', reply_markup=k)
                return
            state = reminder(uid=uid, note=note)
            bot.reply_to(message, f'OK! Reminder turned {state}', reply_markup=k)

        elif option == 'Delete':
            remove_task(uid=uid, note=note)
            bot.reply_to(message, 'Deleted', reply_markup=k)

        elif option == 'Change note':
            msg = bot.reply_to(message, 'Send new description', reply_markup=k)
            bot.register_next_step_handler(msg, set_new_value,
                                           note=note, option='Change note')
        elif option == 'Deadline':
            msg = bot.reply_to(message, 'Send a date in format \'DD.MM.YYYY\'', reply_markup=k)
            bot.register_next_step_handler(msg, set_new_value,
                                           note=note, option='Deadline')
        elif option == 'Assignee':
            msg = bot.reply_to(message, 'Send me Telegram ID of your assignee', reply_markup=k)
            bot.register_next_step_handler(msg, set_new_value,
                                           note=note, option='Assignee')

    except Exception as e:
        bot.reply_to(message, 'Something went wrong, try again', reply_markup=k)


@cancel
def set_new_value(message, note, option):
    uid = message.chat.id
    new_value = message.text

    try:
        if option == 'Change note':
            change_note(uid=uid, note=note, new_note=new_value)
        elif option == 'Assignee':
            make_assignee(uid=uid, note=note, assignee=new_value)
        elif option == 'Deadline':
            val = datetime.strptime(new_value, '%d.%m.%Y')
            if not val < datetime.now():
                change_deadline(uid=uid, note=note, new_value=val)
        bot.reply_to(message, 'Done')

    except Exception as e:
        bot.reply_to(message, 'Whoops! Something is wrong, try again')


@bot.message_handler(commands=['style'])
def change_style(message):
    state = style(uid=message.chat.id)
    bot.reply_to(message, f'Style changed to {state}')


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(reminder_job, 'cron', hour=18, timezone='utc')
    scheduler.start()
    bot.polling()

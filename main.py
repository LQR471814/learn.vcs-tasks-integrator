import logging
import time
from datetime import datetime
from threading import Thread

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from learnvcs import Client, NoEntreeError

from cli import Day, TaskContext


def refresh_daemon(credentials: Credentials) -> None:
    if credentials.expired:
        credentials.refresh(Request())
    while True:
        time.sleep((credentials.expiry - datetime.today()).total_seconds())
        credentials.refresh(Request())


def is_weekend() -> bool:
    today = datetime.today()
    return today.day == 5 or today.day == 6


#? Just in case one is looking for the documentation of
#? the python Google Tasks api here is the link
#? https://googleapis.github.io/google-api-python-client/docs/dyn/tasks_v1.html
#? since it's an absolute pain to find
def main(logger: logging.Logger = logging) -> None:
    context = TaskContext()

    Thread(
        target=refresh_daemon,
        args=[context.credentials],
        daemon=True
    ).start()

    service = build('tasks', 'v1', credentials=context.credentials)
    tasks = service.tasks()
    tasklists = service.tasklists()

    try:
        for l in tasklists.list().execute()['items']:
            if l['title'] == context.listname:
                tasklists.delete(tasklist=l['id']).execute()
    except HttpError as err:
        logger.error(err)

    list_id = tasklists.insert(
        body={'title': context.listname}).execute()['id']

    courses_a, courses_b = context.courses

    current_date = datetime.today()
    current_day = context.daystart

    assignment_cache: set[int] = set()

    while True:
        t1 = time.perf_counter()

        if is_weekend() and not context.check_weekends:
            today = datetime.today()
            future = datetime(today.year, today.month, today.day + 1)
            time.sleep((future - today).seconds)
            continue

        if (datetime.today() - current_date).days > 0:
            new_day = Day.B if current_day == Day.A else Day.A
            logger.info(f'Day swap {current_day} -> {new_day}')
            current_day = new_day
            current_date = datetime.today()

        # ? Refresh VCS client just in case
        vcsclient = Client.login(context.username, context.password)
        course_assignments: list[tuple[str, list[str]]] = []

        courses = courses_a if current_day == Day.A else courses_b
        logger.info(f'Today\'s Courses: {courses}')

        for class_name, class_id in courses:
            # * Insert course subtasks
            try:
                course_assignments.append((class_name, vcsclient.homework(class_id)))
            except NoEntreeError:
                continue

        logger.info(f'Assignments {course_assignments} Cache {assignment_cache}')

        new_cache = set()
        cleared = False
        for name, value in course_assignments:
            hashed_assignment = hash(tuple(value))
            if hashed_assignment not in assignment_cache:
                logger.info(f'Course {name} cache invalidated, updating...')

                #? Clear all previous tasks if cache is invalid
                if not cleared:
                    itemlist = tasks.list(tasklist=list_id).execute()
                    if itemlist.get('items') is not None:
                        batch = service.new_batch_http_request()
                        for task in itemlist['items']:
                            batch.add(tasks.delete(tasklist=list_id, task=task['id']))
                        batch.execute()
                    cleared = True

                # ? Create course task
                course_task_id = tasks.insert(
                    tasklist=list_id,
                    body={'title': name}
                ).execute()['id']

                # ? Create course subtasks
                batch = service.new_batch_http_request()
                subtasks: list[str] = []
                for text in value:
                    batch.add(
                        tasks.insert(tasklist=list_id, body={'title': text}),
                        callback=lambda _, r, __ : subtasks.append(r['id'])
                    )
                batch.execute()

                batch = service.new_batch_http_request()
                for subtask_id in subtasks:
                    batch.add(tasks.move(
                        tasklist=list_id,
                        task=subtask_id,
                        parent=course_task_id,
                    ))
                batch.execute()

            new_cache.add(hashed_assignment)
        assignment_cache = new_cache

        t2 = time.perf_counter()
        logger.info(
            f'Fetched assignments and updated tasks in {round(t2 - t1, 2)}s'
        )

        # ? Wait 4 hours before fetching homework again
        # ? as teachers may post in the morning just before their class
        time.sleep(60 * 60 * 4)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('tasks-integrator')
    logger.setLevel(logging.INFO)

    main(logger)

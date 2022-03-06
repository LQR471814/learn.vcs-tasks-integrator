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
        time.sleep((credentials.expiry - datetime.now()).total_seconds())
        credentials.refresh(Request())


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

    current_date = datetime.now()
    current_day = context.daystart

    previous_assignments: dict[str, list[str]] = {}

    while True:
        t1 = time.perf_counter()

        if (datetime.now() - current_date).days > 0:
            if current_day == Day.A:
                current_day = Day.B
            else:
                current_day = Day.A
            current_date = datetime.now()

        # ? Refresh VCS client just in case
        vcsclient = Client.login(context.username, context.password)
        assignments: dict[str, list[str]] = {}

        courses = courses_a if current_day == Day.A else courses_b
        logger.info(f'Courses: {courses}')

        for class_name, class_id in courses:
            # * Insert course subtasks
            try:
                assignments[class_name] = vcsclient.homework(class_id)
            except NoEntreeError:
                continue

        if assignments != previous_assignments:
            tasks.clear(tasklist=list_id).execute()

            for name in assignments:
                # ? Create course task
                course_task_id = tasks.insert(
                    tasklist=list_id,
                    body={'title': name}
                ).execute()['id']

                # ? Create course subtasks
                for text in assignments[name]:
                    subtask_id = tasks.insert(
                        tasklist=list_id,
                        body={'title': text}
                    ).execute()['id']

                    tasks.move(
                        tasklist=list_id,
                        task=subtask_id,
                        parent=course_task_id
                    ).execute()

                previous_assignments[class_id] = assignments

        t2 = time.perf_counter()
        logger.info(
            f'Fetched assignments and updated tasks in {round(t2 - t1, 2)}s'
        )

        # ? Wait 4 hours before fetching homework again
        time.sleep(60 * 60 * 4)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('tasks-integrator')
    logger.setLevel(logging.INFO)

    main(logger)

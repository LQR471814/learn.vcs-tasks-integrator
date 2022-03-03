import argparse
from dis import disco
import logging
import time
from datetime import datetime
from threading import Thread

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from learnvcs import Client, NoEntreeError


def refresh_daemon(credentials: Credentials) -> None:
    if credentials.expired:
        credentials.refresh(Request())
    while True:
        time.sleep((credentials.expiry - datetime.now()).total_seconds())
        credentials.refresh(Request())


CourseList = list[tuple[str, int]]


class TaskContext:
    username: str
    password: str
    listname: str
    credentials: Credentials

    ab: bool
    daystart: str
    courses: tuple[CourseList, CourseList] | CourseList

    def __init__(
        self, username: str, password: str,
        listname: str, credentials: Credentials,
        ab: bool, daystart: str, courses: tuple[CourseList, CourseList] | CourseList
    ) -> None:
        self.username = username
        self.password = password
        self.listname = listname
        self.credentials = credentials
        self.ab = ab
        self.daystart = daystart
        self.courses = courses


def construct_context() -> TaskContext:
    # * Parse arguments
    parser = argparse.ArgumentParser(
        description="Integrates learn@vcs with Google Tasks"
    )

    parser.add_argument('--debug', action='store_true')

    parser.add_argument(
        '--ab', help='Enable A/B day course distinction',
        action='store_true'
    )

    parser.add_argument(
        '--daystart',
        help="The day to start on 'A' or 'B', "
            'this will only take effect when --ab is present',
        default='A'
    )

    parser.add_argument(
        '--username', help='learn@VCS username',
        required=True
    )

    parser.add_argument(
        '--password', help='learn@VCS password',
        required=True
    )

    parser.add_argument(
        '--listname', help='The name of the tasklist to add assignments to',
        default='Learn@VCS Assignments'
    )

    args = parser.parse_args()

    # * Pick classes
    vcsclient = Client.login(args.username, args.password)

    discovered_courses = list(vcsclient.courses().items())
    courses: tuple[CourseList, CourseList] | CourseList = []

    def choose_courses(suffix: str = '') -> CourseList:
        result = []
        print(f'Choose the courses you would like to check {suffix}. (seperated by commas: 0, 2, 4...)')
        for i, c in enumerate(discovered_courses):
            print(f'[{i}] {c}')

        for choice in input(' > ').split(','):
            if len(choice.strip()) > 0:
                result.append(discovered_courses[choice])

        return result

    if not args.ab:
        courses = choose_courses()
    else:
        courses = (
            choose_courses('for day A'),
            choose_courses('for day B'),
        )

    # * Authenticate Google Tasks
    auth = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json",
        scopes=["https://www.googleapis.com/auth/tasks"]
    )

    if args.debug:
        auth.run_local_server()
    else:
        auth.run_console()

    return TaskContext(
        username=args.username,
        password=args.password,
        listname=args.listname,
        credentials=auth.credentials,
        ab=args.ab,
        courses=courses,
    )


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('tasks-integrator')
    logger.setLevel(logging.INFO)

    context = construct_context()

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
        body={'title': context.listname}
    ).execute()['id']

    if not context.ab:
        previous_assignments: dict[str, list[str]] = {}
        while True:
            t1 = time.perf_counter()

            # ? Refresh VCS client just in case
            vcsclient = Client.login(context.username, context.password)
            assignments: dict[str, list[str]] = {}
            for class_name, class_id in context.courses:
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
            logger.info(f'Fetched assignments and updated tasks in {round(t2 - t1, 2)}s')

            # ? Wait 4 hours before fetching homework again
            time.sleep(60 * 60 * 4)
    else:
        init_day = datetime.now()
        previous_assignments: dict[str, list[str]] = {}
        while True:
            t1 = time.perf_counter()

            delta = (datetime.now() - init_day).days % 2
            if delta > 0:


            # ? Refresh VCS client just in case
            vcsclient = Client.login(context.username, context.password)
            assignments: dict[str, list[str]] = {}
            for class_name, class_id in context.courses:
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
            logger.info(f'Fetched assignments and updated tasks in {round(t2 - t1, 2)}s')

            # ? Wait 4 hours before fetching homework again
            time.sleep(60 * 60 * 4)
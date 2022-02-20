import argparse
import logging
import time
from datetime import datetime
from threading import Thread

import httplib2
from google.auth.transport import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from learnvcs import Client, NavigationConfig, NoEntreeError


def refresh_daemon(credentials: Credentials) -> None:
    if credentials.expired:
        credentials.refresh(Request())
    while True:
        time.sleep((credentials.expiry - datetime.now()).total_seconds())
        credentials.refresh(Request())


if __name__ == '__main__':
    http = httplib2.Http(cache=".cache")

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Integrates learn@vcs with Google Tasks"
    )

    parser.add_argument('--debug', action='store_true')
    parser.add_argument(
        'courses',
        type=str,
        help='Check for assignments for this specific course',
        nargs='+',
    )
    parser.add_argument(
        '--username',
        help='learn@VCS username',
        required=True
    )
    parser.add_argument(
        '--password',
        help='learn@VCS password',
        required=True
    )
    parser.add_argument(
        '--listname',
        help='The name of the tasklist to add assignments to',
        default='Learn@VCS Assignments'
    )

    args = parser.parse_args()

    vcsclient = Client.login(args.username, args.password)
    class_ids: list[tuple[str, int]] = []
    courses = vcsclient.courses()
    for name in courses:
        for c in args.courses:
            if c.lower() in name.lower():
                class_ids.append((name, courses[name]))
                break

    logging.info(class_ids)

    auth = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json", scopes=["https://www.googleapis.com/auth/tasks"]
    )

    if args.debug:
        auth.run_local_server()
    else:
        auth.run_console()

    Thread(target=refresh_daemon, args=[auth.credentials], daemon=True).start()
    service = build('tasks', 'v1', credentials=auth.credentials)

    tasks = service.tasks()
    tasklists = service.tasklists()

    try:
        for l in tasklists.list().execute()['items']:
            if l['title'] == args.listname:
                tasklists.delete(tasklist=l['id']).execute()
    except HttpError as err:
        logging.error(err)

    list_id = tasklists.insert(body={'title': args.listname}).execute()['id']

    previous_assignments: dict[int, list[str]] = {}
    while True:
        t1 = time.perf_counter()
        for name, class_id in class_ids:
            # * Insert course subtasks
            try:
                # ? Refresh VCS client just in case
                vcsclient = Client.login(args.username, args.password)
                assignments = vcsclient.homework(
                    class_id,
                    NavigationConfig(datetime(2022, 2, 18))
                )
            except NoEntreeError:
                continue

            if assignments != previous_assignments.get(class_id):
                tasks.clear(tasklist=list_id).execute()

                # ? Create course task
                course_task_id = tasks.insert(
                    tasklist=list_id,
                    body={'title': name}
                ).execute()['id']

                # ? Create course subtasks
                for text in assignments:
                    subtask_id = tasks.insert(
                        tasklist=list_id,
                        body={'title': text}
                    ).execute()['id']
                    tasks.move(tasklist=list_id, task=subtask_id, parent=course_task_id).execute()

                previous_assignments[class_id] = assignments
        t2 = time.perf_counter()
        logging.info(f'Fetched assignments and updated tasks in {round(t2 - t1, 2)}s')

        # ? Wait 4 hours before fetching homework again
        time.sleep(60 * 60 * 4)

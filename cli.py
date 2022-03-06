from enum import Enum
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from learnvcs import Client

CourseList = list[tuple[str, int]]

class Day(Enum):
    A = "A"
    B = "B"

class TaskContext:
    username: str
    password: str
    listname: str
    credentials: Credentials

    daystart: str
    courses: tuple[CourseList, CourseList]
    check_weekends: bool

    def __init__(self) -> None:
        # * Parse arguments
        parser = argparse.ArgumentParser(
            description="Integrates learn@vcs with Google Tasks"
        )

        parser.add_argument('--debug', action='store_true')

        parser.add_argument(
            '--check-weekends',
            help=f"Alternate days and scan assignments on the weekends.",
            action='store_true',
            default=False
        )

        parser.add_argument(
            '--day-start',
            help=f"The day to start on '{Day.A}' or '{Day.B}', "
            'this will only take effect when --ab is present',
            default=Day.A
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

        self.username = args.username
        self.password = args.password
        self.listname = args.listname
        self.daystart = args.day_start
        self.check_weekends = args.check_weekends

        # * Pick classes
        vcsclient = Client.login(args.username, args.password)

        discovered_courses = list(vcsclient.courses().items())

        def choose_courses(suffix: str = '') -> CourseList:
            result = []

            print(
                f'Choose the courses you would like to check {suffix}. '
                '(seperated by commas: 0, 2, 4...)'
            )

            for i, c in enumerate(discovered_courses):
                print(f'[{i}] {c}')

            for choice in input(' > ').split(','):
                if len(choice.strip()) > 0:
                    result.append(discovered_courses[int(choice)])

            return result

        self.courses = (
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

        self.credentials = auth.credentials


from __future__ import unicode_literals

import logging
import os

from edx_rest_api_client.client import EdxRestApiClient
from flask import Flask, g
from flask_ask import Ask, question, session, statement

app = Flask(__name__)
ask = Ask(app, '/')
logging.getLogger('flask_ask').setLevel(logging.DEBUG)

APP_NAME = 'edX'
SPOKEN_NAME = 'ed ex'

ACCESS_TOKEN_URL = os.environ['ACCESS_TOKEN_URL']
APP_OAUTH_CLIENT_ID = os.environ['OAUTH_CLIENT_ID']
APP_OAUTH_CLIENT_SECRET = os.environ['OAUTH_CLIENT_SECRET']

LMS_API_URL = os.environ['LMS_API_URL']
CATALOG_API_URL = os.environ['CATALOG_API_URL']

QUESTION_KEY = 'QUESTION'
ENROLLMENTS_KEY = 'ENROLLMENTS'


class APIError(Exception):
    pass


def app_access_token():
    access_token = getattr(g, '_app_access_token', None)
    if not access_token:
        access_token, __ = EdxRestApiClient.get_oauth_access_token(
            ACCESS_TOKEN_URL, APP_OAUTH_CLIENT_ID, APP_OAUTH_CLIENT_SECRET, token_type='jwt'
        )
        g._app_access_token = access_token

    return access_token


def user_access_token():
    return getattr(session.user, 'accessToken', None)


def lms_api_client():
    return EdxRestApiClient(LMS_API_URL, oauth_access_token=user_access_token(), append_slash=False)


def catalog_api_client():
    return EdxRestApiClient(CATALOG_API_URL, jwt=app_access_token())


@ask.launch
def launch():
    if user_access_token():
        speech_text = 'Welcome to the {} app. You can request your current enrollments.'.format(SPOKEN_NAME)
        return question(speech_text).reprompt(speech_text).simple_card(APP_NAME, speech_text)
    else:
        speech_text = 'Welcome to the {} app. You must be logged in to continue.'.format(SPOKEN_NAME)
        return question(speech_text).reprompt(speech_text).link_account_card()


def get_enrollments():
    try:
        _enrollments = lms_api_client().enrollment.v1.enrollment.get()
        _enrollments = {enrollment['course_details']['course_id']: {} for enrollment in _enrollments}
        return _enrollments
    except:
        logging.exception('An error occurred while retrieving enrollments.')
        raise APIError


def get_course_names(_enrollments):
    # TODO Determine how to deal with Unicode characters
    course_run_keys = ','.join(_enrollments.keys())

    # TODO Pagination
    course_runs = catalog_api_client().course_runs.get(keys=course_run_keys)['results']

    for course_run in course_runs:
        _enrollments[course_run['key']].update({
            'title': course_run['title']
        })

    return _enrollments


def search_catalog(query):
    kwargs = {
        'partner': 'edx',
        'end__gt': 'now',
        'content_type': 'courserun',
        'page': 1,
        'page_size': 10,
        'q': query,
    }
    return catalog_api_client().search.all.get(**kwargs)['results']


def _change_enrollment(course_key, active):
    try:
        data = {
            'mode': 'audit',
            'course_details': {
                'course_id': course_key,
                'is_active': active
            },
        }
        lms_api_client().enrollment.v1.enrollment.post(data)
    except:
        logging.exception('An error occurred while enrolling the user.')
        raise APIError


def enroll_user():
    _change_enrollment('course-v1:DavidsonX+DavNowX_Voting+3T2016', True)


def unenroll_user():
    _change_enrollment('course-v1:DavidsonX+DavNowX_Voting+3T2016', False)


@ask.intent('EdXEnrollmentsIntent')
def enrollments():
    if user_access_token():
        try:
            _enrollments = get_enrollments()
        except APIError:
            speech_text = 'An error occurred while contacting the {} server. Please try again.'.format(SPOKEN_NAME)
            return statement(speech_text).simple_card(APP_NAME, speech_text)

        enrollment_count = len(_enrollments)

        if enrollment_count <= 0:
            speech_text = 'You are not currently enrolled in any courses'
            return statement(speech_text).simple_card(APP_NAME, speech_text)

        word = 'course' if enrollment_count == 1 else 'courses'
        speech_text = 'You are currently enrolled in {count} {word}. Would you like me to list them?'.format(
            count=enrollment_count, word=word)

        session.attributes[ENROLLMENTS_KEY] = _enrollments

        return question(speech_text).reprompt(speech_text).simple_card(APP_NAME, speech_text)
    else:
        speech_text = 'You must be logged in to get your enrollment status.'
        return statement(speech_text).link_account_card()


@ask.intent('EdXEnrollIntent')
def enroll():
    if user_access_token():
        try:
            enroll_user()
            # TODO Pull course name from API
            speech_text = 'You have been enrolled in US Voting Access and Fraud. '
            reprompt = 'How else may I assist you?'
            speech_text += reprompt

            return question(speech_text).reprompt(reprompt).simple_card(APP_NAME, speech_text)
        except APIError:
            speech_text = 'An error occurred while contacting the {} server. Please try again.'.format(SPOKEN_NAME)
            return statement(speech_text).simple_card(APP_NAME, speech_text)
    else:
        speech_text = 'You must be logged in to enroll in a course.'
        return statement(speech_text).link_account_card()


@ask.intent('EdXUnenrollIntent')
def unenroll():
    # NOTE (CCB): The Enrollment API only supports unenrollment requests for server-to-server calls
    speech_text = 'I am not yet able to unenroll learners. Please visit your course dashboard to unenroll from courses.'
    return statement(speech_text).simple_card(APP_NAME, speech_text)

    if user_access_token():
        try:
            unenroll_user()
            # TODO Pull course name from API
            speech_text = 'You have been un-enrolled from US Voting Access and Fraud'
            return statement(speech_text).simple_card(APP_NAME, speech_text)
        except APIError:
            speech_text = 'An error occurred while contacting the {} server. Please try again.'.format(SPOKEN_NAME)
            return statement(speech_text).simple_card(APP_NAME, speech_text)
    else:
        speech_text = 'You must be logged in to un-enroll in a course.'
        return statement(speech_text).link_account_card()


@ask.intent('AMAZON.CancelIntent')
@ask.intent('AMAZON.NoIntent')
def end():
    if session.new:
        return help()

    speech_text = 'Okay'
    return statement(speech_text).simple_card(APP_NAME, speech_text)


@ask.intent('AMAZON.YesIntent')
def continue_interaction():
    if session.new:
        return help()

    speech_text = '<speak><p>Your courses include</p>'
    _enrollments = get_course_names(session.attributes[ENROLLMENTS_KEY])

    for enrollment in _enrollments.values():
        speech_text += '<p>{}</p>'.format(enrollment['title'])

    reprompt = 'How else may I assist you?'
    speech_text += '{}</speak>'.format(reprompt)
    return question(speech_text).reprompt(reprompt).simple_card(APP_NAME, speech_text)


@ask.intent('EdXListEnrollmentsIntent')
def list_enrollments():
    if user_access_token():
        try:
            _enrollments = get_enrollments()
            _enrollments = get_course_names(_enrollments)
        except APIError:
            speech_text = 'An error occurred while contacting the {} server. Please try again.'.format(SPOKEN_NAME)
            return statement(speech_text).simple_card(APP_NAME, speech_text)

        enrollment_count = len(_enrollments)

        if enrollment_count <= 0:
            speech_text = 'You are not currently enrolled in any courses'
            return statement(speech_text).simple_card(APP_NAME, speech_text)

        word = 'course. It is' if enrollment_count == 1 else 'courses. They are'
        speech_text = '<speak><p>You are currently enrolled in {count} {word}</p>'.format(
            count=enrollment_count, word=word)

        for enrollment in _enrollments.values():
            speech_text += '<p>{}</p>'.format(enrollment['title'])

        reprompt = 'How else may I assist you?'
        speech_text += '{}</speak>'.format(reprompt)
        return question(speech_text).reprompt(reprompt).simple_card(APP_NAME, speech_text)
    else:
        speech_text = 'You must be logged in to get your enrollment status.'
        return statement(speech_text).link_account_card()


@ask.intent('EdXAboutIntent')
def about():
    speech_text = "<speak><p>Founded by Harvard University and MIT in 2012, {} is an online learning destination and " \
                  "MOOC provider, offering high-quality courses from the world's best universities and institutions " \
                  "to learners everywhere.</p>".format(SPOKEN_NAME)
    speech_text += '<p>The mission of {} is to Increase access to high-quality education for everyone everywhere, ' \
                   'Enhance teaching and learning on campus and online, and Advance teaching and learning through ' \
                   'research</p>'.format(SPOKEN_NAME)
    reprompt = 'How else may I assist you?'
    speech_text += '{}</speak>'.format(reprompt)
    return question(speech_text).reprompt(reprompt).simple_card(APP_NAME, speech_text)


@ask.intent('EdXSearchIntent', mapping={'subject': 'Subject'})
def search(subject):
    courses = search_catalog(subject)
    count = len(courses)

    if count <= 0:
        speech_text = 'I found no courses about {subject}'.format(subject=subject)
    else:
        word = 'course about {subject}. It is' if count == 1 else 'courses about {subject}. They are'
        word = word.format(subject=subject)
        speech_text = '<speak><p>I found {count} {word}</p>'.format(count=count, word=word)

        for course in courses:
            speech_text += '<p>{}</p>'.format(course['title'])

        speech_text += '</speak>'

    return statement(speech_text).simple_card(APP_NAME, speech_text)


@ask.intent('AMAZON.HelpIntent')
def help():
    speech_text = 'You can request your current enrollment count'
    return statement(speech_text).simple_card(APP_NAME, speech_text)


@ask.session_ended
def session_ended():
    return '', 200


if __name__ == '__main__':
    app.run(debug=True)

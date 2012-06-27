#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MicroPsi server application.

This version of MicroPsi is meant to be deployed as a web server, and accessed through a browser.
For local use, simply start this server and point your browser to "http://localhost:6543".
The latter parameter is the default port and can be changed as needed.
"""

__author__ = 'joscha'
__date__ = '15.05.12'

VERSION = "0.1"

import micropsi_core.runtime
import user
import bottle
from bottle import route, post, run, request, response, template, static_file
import argparse
import os
from uuid import uuid1

# from IPython import embed	#devV

DEFAULT_PORT = 6543
DEFAULT_HOST = "localhost"

APP_PATH = os.path.dirname(__file__)
RESOURCE_PATH = os.path.join(os.path.dirname(__file__),"..","resources")

bottle.debug( True ) #devV
bottle.TEMPLATE_PATH.insert( 0, os.path.join(APP_PATH, 'view', ''))

session_token = None

@route('/static/<filepath:path>')
def server_static(filepath):
    return static_file(filepath, root=os.path.join(APP_PATH, 'static'))

@route("/")
def index():
    if not request.get_cookie("token"):
        session_token = None
    else:
        session_token = request.get_cookie("token")

    return template("nodenet",
        version = VERSION,
        user = usermanager.get_user_id_for_session_token(session_token),
        permissions = usermanager.get_permissions_for_session_token(session_token))

@route("/about")
def about():
    return template("about", version = VERSION)

@route("/docs")
def about():
    return template("documentation", version = VERSION)

@route("/contact")
def about():
    return template("contact", version = VERSION)

@route("/logout")
def logout():
    if request.get_cookie("token"):
        session_token = request.get_cookie("token")
        usermanager.end_session(session_token)
    session_token = None
    response.delete_cookie("token")
    return template("nodenet",
        version = VERSION,
        user = usermanager.get_user_id_for_session_token(session_token),
        permissions = usermanager.get_permissions_for_session_token(session_token))


@route("/login")
def login():
    if not usermanager.users:  # create first user
        return template("signup", version = VERSION, first_user = True, userid="admin")

    return template("login",
        version = VERSION,
        user = usermanager.get_user_id_for_session_token(session_token),
        permissions = usermanager.get_permissions_for_session_token(session_token))

@post("/login_submit")
def login_submit():
    user_id = request.forms.userid
    password = request.forms.password

    # log in new user
    session_token = usermanager.start_session(user_id, password, request.forms.get("keep_logged_in"))
    if session_token:
        response.set_cookie("token", session_token)
        # redirect to start page
        return template("nodenet",
            version = VERSION,
            user = usermanager.get_user_id_for_session_token(session_token),
            permissions = usermanager.get_permissions_for_session_token(session_token))
    else:
        # login failed, retry
        if user_id in usermanager.users:
            return template("login", version = VERSION, userid=user_id, password=password,
                password_error="Re-enter the password",
                login_error="User name and password do not match",
                cookie_warning = (session_token is None),
                permissions = usermanager.get_permissions_for_session_token(session_token))
        else:
            return template("login", version = VERSION, userid=user_id, password=password,
                userid_error="Re-enter the user name",
                login_error="User unknown",
                cookie_warning = (session_token is None),
                permissions = usermanager.get_permissions_for_session_token(session_token))

@route("/signup")
def signup():
    if request.get_cookie("token"):
        session_token = request.get_cookie("token")
    else:
        session_token = None

    if not usermanager.users:  # create first user
        return template("signup", version = VERSION, first_user = True, cookie_warning = (session_token is None))

    return template("signup", version = VERSION,
        permissions = usermanager.get_permissions_for_session_token(session_token),
        cookie_warning = (session_token is None))

@post("/signup_submit")
def signup_submit():
    if request.get_cookie("token"):
        session_token = request.get_cookie("token")
    else:
        session_token = None
    user_id = request.forms.userid
    password = request.forms.password
    role = request.forms.get('permissions')
    (success, result) = user.check_for_url_proof_id(user_id, existing_ids = usermanager.users.keys())
    permissions = usermanager.get_permissions_for_session_token(session_token)

    if success:
        # check if permissions in form are consistent with internal permissions
        if ((role == "Administrator" and ("create admin" in permissions or not usermanager.users)) or
            (role == "Full" and "create full" in permissions) or
            (role == "Restricted" and "create restricted" in permissions)):
            if usermanager.create_user(user_id, password, role, uid = uuid1().hex):
                # log in new user
                session_token = usermanager.start_session(user_id, password, request.forms.get("keep_logged_in"))
                response.set_cookie("token", session_token)
                # redirect to start page
                return template("nodenet",
                    version = VERSION,
                    user = usermanager.get_user_id_for_session_token(session_token),
                    permissions = usermanager.get_permissions_for_session_token(session_token))
            else:
                return fatality("User creation failed for an obscure internal reason.")
        else:
            return fatality("Permission inconsistency during user creation.")
    else:
        # something wrong with the user id, retry
        return template("signup", version = VERSION, userid=user_id, password=password, userid_error=result,
            permissions = permissions, cookie_warning = (session_token is None))

@route("/change_password")
def change_password():
    if request.get_cookie("token"):
        session_token = request.get_cookie("token")
        return template("change_password", version = VERSION,
            userid = usermanager.get_user_id_for_session_token(session_token),
            permissions = usermanager.get_permissions_for_session_token(session_token))
    else:
        return fatality("Cannot change password outside of a session")

@post("/change_password_submit")
def change_password_submit():
    if request.get_cookie("token"):
        session_token = request.get_cookie("token")

        old_password = request.forms.old_password
        new_password = request.forms.new_password
        user_id = usermanager.get_user_id_for_session_token(session_token)

        if usermanager.test_password(user_id, old_password):
            usermanager.set_user_password(user_id, new_password)
            return template("nodenet",
                version = VERSION,
                user = usermanager.get_user_id_for_session_token(session_token),
                permissions = usermanager.get_permissions_for_session_token(session_token))

        else:
            return template("change_password", version = VERSION, userid=user_id, old_password=old_password,
                new_password=new_password, old_password_error="Wrong password, please try again")
    else:
        return fatality("Cannot change password outside of a session")



def fatality(message):
    """returns a web page with the error message"""
    return template("error", msg = message)



def main(host=DEFAULT_HOST, port=DEFAULT_PORT):
    global micropsi
    global usermanager
    micropsi = micropsi_core.runtime.MicroPsiRuntime()
    usermanager = user.UserManager(user_file = open(os.path.join(RESOURCE_PATH, user.USER_FILE_NAME), "w+"))
    run(host=host, port=port, reloader=True) #devV

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Start the MicroPsi server.")
    parser.add_argument('-d', '--host', type=str, default=DEFAULT_HOST)
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    main(host = args.host, port = args.port)





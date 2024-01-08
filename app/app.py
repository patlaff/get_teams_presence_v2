import identity.web
import requests
from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from celery import Celery, Task
from celery.schedules import crontab
import time
#from sense_hat import SenseHat

import app_config as app_config

__version__ = "0.7.0"  # The version of this sample, for troubleshooting purpose

# Sense Hat stuff:
# sense = SenseHat()
# sense.low_light = True

def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

app = Flask(__name__)
app.config.from_object(app_config)
assert app.config["REDIRECT_PATH"] != "/", "REDIRECT_PATH must not be /"
app.config.update(
    CELERY=dict(
        broker_url="pyamqp://guest@localhost//",
        result_backend="pyamqp://guest@localhost//"
    ),
)
celery_app = celery_init_app(app)
Session(app)

celery = Celery(
    app.import_name,
    broker='pyamqp://guest@localhost//',
    # include=['tasks']
)
celery.conf.update(app.config)

app.config['CELERYBEAT_SCHEDULE'] = {
    'print-hello-world-every-minute': {
        'task': 'tasks.print_hello_world',
        'schedule': crontab(minute='*'),
    },
}


@celery.task
def print_hello_world():
    print("Hello World")


@celery.task()
def getPresence():
    token = auth.get_token_for_user(app_config.SCOPE)
    if "error" in token:
        return redirect(url_for("login"))
    api_result = requests.get(
        app_config.ENDPOINT,
        headers={'Authorization': 'Bearer ' + token['access_token']},
        timeout=30,
    ).json()
    # Parse Graph Response to get current User Activity
    activity = api_result['activity']
    # Present message if user is busy, otherwise sleep for 60 seconds
    if activity in ['InACall', 'InAConferenceCall', 'Presenting']:
        print("ON AIR")
        # sense.show_message(
        #     "On Air", 
        #     text_colour=(0,0,255), 
        #     scroll_speed=0.2
        # )
        # sense.clear()
    else:
        print("Not Busy")
        time.sleep(60)
    return activity


# This section is needed for url_for("foo", _external=True) to automatically
# generate http scheme when this sample is running on localhost,
# and to generate https scheme when it is deployed behind reversed proxy.
# See also https://flask.palletsprojects.com/en/2.2.x/deploying/proxy_fix/
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.jinja_env.globals.update(Auth=identity.web.Auth)  # Useful in template for B2C
auth = identity.web.Auth(
    session=session,
    authority=app.config["AUTHORITY"],
    client_id=app.config["CLIENT_ID"],
    client_credential=app.config["CLIENT_SECRET"],
)


@app.route("/login")
def login():
    return render_template("login.html", version=__version__, **auth.log_in(
        scopes=app_config.SCOPE, # Have user consent to scopes during log-in
        redirect_uri=url_for("auth_response", _external=True), # Optional. If present, this absolute URL must match your app's redirect_uri registered in Azure Portal
        prompt="select_account",  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
    ))


@app.route(app_config.REDIRECT_PATH)
def auth_response():
    result = auth.complete_log_in(request.args)
    if "error" in result:
        return render_template("auth_error.html", result=result)
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    return redirect(auth.log_out(url_for("index", _external=True)))


@app.route("/")
def index():
    if not auth.get_user():
        return redirect(url_for("login"))
    return render_template('index.html', user=auth.get_user(), version=__version__)

        
@app.route("/get_presence")
def get_presence():
    presence = print_hello_world.delay()
    return render_template('display.html', result="success!")


if __name__ == "__main__":
    app.run(
        # debug=True
    )

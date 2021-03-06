import atexit
import os
from datetime import datetime

from flask import Flask, abort, jsonify, flash, redirect, render_template, request, url_for
from flask_sockets import Sockets

from lib.advertiser import MDNSAdvertiser
from lib.browser import MDNSBrowser
from lib.calendar_store import CalendarStore

import json
import time

app = Flask(__name__)
sockets = Sockets(app)

app.config['DEBUG'] = True

calendar_store = CalendarStore()

# calendar_store.load_seed_data()
# This is a hack, we're at a hackathon
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
  advertiser = MDNSAdvertiser()
  advertiser.setup()
  browser = MDNSBrowser(calendar_store)


@app.route('/')
def index():
  return render_template('index.html', calendars=calendar_store.all(), calendars_json=calendar_store.all_json())


@app.route('/calendars.json')
def calendars_json():
  return calendar_store.all_json()


@sockets.route('/calendars.socket')
def calendars_socket(ws):
  calendar_store.add_ws(ws)
  while not ws.closed:
    try:
      message = ws.receive()
      if message is not None and message != "":
        data = json.loads(message)
        action = data['action']
        if action == "set_selected":
          calendar_store.set_selected(data['ids'])

      ws.send(calendar_store.all_json())
    # HACK: multi-level hack. Should use proper error class (import :() and message comparison should use constants
    except Exception as e:
      if str(e) == "Socket is dead":
        calendar_store.remove_ws(ws)
      else:
        raise e
  calendar_store.remove_ws(ws)

@app.route('/generate-calendar')
def generate_calendar():
  calendar_store.generate_calendar()
  return calendar_store.all_json()


@app.route('/aggregate.ics')
def serve_aggregate():
  data = ''
  for calendar in calendar_store.all():
    if calendar.selected:
      content = calendar.get_content()
      data += content + '\n'
  return data


@atexit.register
def stop_advertiser():
  advertiser.teardown()


if __name__ == '__main__':
  # app.run()
  from gevent import pywsgi
  from geventwebsocket.handler import WebSocketHandler
  server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
  server.serve_forever()

#!/usr/bin/env python2

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

make_active = False
if len(sys.argv) < 2 or sys.argv[1] not in ['on', 'off']:
  print('Please give a value of "on" or "off".')
  exit(1)

if sys.argv[1] == 'on':
  make_active = True

acc = appscale_info.get_appcontroller_client()
result = acc.set_read_only(str(make_active).lower())
if result != 'OK':
  print(result)
  exit(1)

if make_active:
  print('Datastore writes are now disabled.')
else:
  print('Datastore writes are now enabled.')

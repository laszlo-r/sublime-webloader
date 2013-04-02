
sublime-less-watch
==================

A Sublime 2 plugin to live-update CSS via less.js and (web)sockets.

Uses Tornado to start a local http server; websockets to reach the server from the browser; and httplib in the plugin to send the server live edits.

**Still very much in development, but suggestions and fixes are welcome.**

How to use:
-----------
- install the plugin (no package control yet)
- run `python watch-server.py` in whatever shell you prefer
- include your .less file on the page, and a less.js, a prototype.js, and the less-watch.js as well
- if you want, you can redefine the server in the link tag: `<link rel='stylesheet/less' href='your.less?server=localhost:9000' type='text/css' />`
- edit your .less files, and check the css updates in the javascript console

TODO:
-----

- done: the plugin now only tries to connect when actual editing happens, and with a low timeout (0.05s, still can trigger the slow plugins warning)
  - could put these blocking connections under sublime.set_timeout(callback, millisecs) -- which is blocking, sadly
- test server with multiple sites and files: plugin -> server -> client process works find, but:
  - should insert style elements under their respective link/style tags (overriding order counts with multiple files)
- settings (server host, port, urls; different update methods, like updating full blocks, with a reasonable delay)
- checking proper updating of various CSS selectors (less selector generating method may differ from the simple join-by-spaces used here)
- submit to package control <http://wbond.net/sublime_packages/package_control/package_developers>
- check if hashing is needed at all: custom style tag ids can get pretty long, but this way they are filterable, unlike hashes
- multiple selections: in a well-structured less file you probably factor out frequently used values into variables, so multiple updates are not a priority; a full refresh would be is necessary, which is slow with large files on each modification; consider threading or other async solutions?
  - could only send the current key-value pair, between previous and next semicolons or brackets
- decide if basic validation would help (less network traffic), or not necessary (sublime and less handle the frequent updates well)
- as less.js doesn't expose an individual reload method, currently .less file reloads refresh all .less files

Credits:
--------

- server code based on [Tornado][1], plugin code on the [sublime API][2] and standard python library
- uses less.js from [lesscss.org][3], and [prototype][4] for simplifying life
- simple and fast javascript hashing from [werxltd.com][5]

License:
--------
Contact: <http://rozsahegyi.info>
License: <http://creativecommons.org/licenses/by-sa/3.0>


  [1]: http://www.tornadoweb.org/
  [2]: http://www.sublimetext.com/docs/2/api_reference.html
  [3]: http://lesscss.org/
  [4]: http://prototypejs.org/
  [5]: http://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/

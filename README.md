
sublime-less-watch
==================

A Sublime 2 plugin to live-update CSS via less.js and (web)sockets.

Uses Tornado to start a local http server; websockets to reach the server from the browser; and httplib in the plugin to send the server live edits.

**Still very much in development, but suggestions and fixes are welcome.**

TODO:
-----

- delayed connection on window activation (or very fast timeouts)
- settings (server host, port, urls; different update methods, like updating full blocks, with a reasonable delay)
- checking proper updating of various CSS selectors (less selector generating method may differ from the simple join-by-spaces used here)
- test server with multiple sites and files
- submit to package control <http://wbond.net/sublime_packages/package_control/package_developers>
- check if hashing is needed at all

Credits:
--------

- server code based on [Tornado][1], plugin code on the [sublime API][2] and standard python library
- (obviously) uses less.js from [lesscss.org][3]
- simple and fast javascript hashing from [werxltd.com][4]

  [1]: http://www.tornadoweb.org/
  [2]: http://www.sublimetext.com/docs/2/api_reference.html
  [3]: http://lesscss.org/
  [4]: http://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/

License:
--------
Contact: <http://rozsahegyi.info>
License: <http://creativecommons.org/licenses/by-sa/3.0>

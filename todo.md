
TODO:
-----
- add: standard logging
- fix: currently clients can call self.server, which could have exited and been deleted meanwhile
- fix: after a restarted server, a client's on_send returned None -- verify if this still happens
- test: utf8 characters in urls and paths, test linux paths (currently first bit removed with paths like file:///C:/)
- test: various sites settings, virthosts, symlinked paths, etc
- test: speed with large css/less files, add a small timeout if needed
- lesscss is apache 2 licensed (free, include all credits)

Simple changelog
----------------
+ file urls can be urlencoded, also test file:/// mode; seems to work with (ascii) escaped urls
+ implement clients setting; set ip limit on clients to prevent flooding/hacks
+ implement save_parsed_less: find the less file in client.files; save the parsed content beside it as .css; has to be enabled in settings!
+ complete js command: quick panel if multiple clients, send to selected (or current) client
+ server command: start/stop/restart; also sends 'cmd file multi line content' to all clients
+ implement sites setting; work with the examples listed in the settings file
+ when changing settings, plugin should notice, and clients should update their patterns; implemented for important settings
+ webloader.js runs on dom:loaded, can be put anywhere on the page
+ converting less: less parser now gets a rootpath (prefixes url()), which is the relative path between the page and the less file
+ update readme
+ server and websocket now build upon SocketServer classes, using select()
+ submit to package control
+ rewrote css/less updates, should work with valid css, and multi-selections; full-file updates, but only when changes matter
+ updates go into a 'css:' or the existing 'less:' style tag; less files saved as css now get proper url() paths
+ added a reload page command for F5; added commands to command palette; better client selection when multiple clients
+ replaced prototype.js with native calls, works standalone (except for less.js, if using .less files)
+ if multiple clients (with the same url), remember or guess the currently selected client
+ fixed overlooked error of leaving in a Prototype.Ajax dependency
+ css parsing now runs in threads to avoid slow plugin warning
